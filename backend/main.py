from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from pathlib import Path

from confluent_kafka import Producer
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai.interactions import DocumentContent, ImageContent, TextContent, TextResponseFormat

logger = logging.getLogger(__name__)

# Always load from backend/.env relative to this file, regardless of cwd
load_dotenv(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Gemini client — lazily created on first request so a missing key produces
# a clear 500 instead of crashing the server process at startup.
# ---------------------------------------------------------------------------
MODEL = "gemini-3.8-flash"
_gemini: genai.Client | None = None


def _get_client() -> genai.Client:
    global _gemini
    if _gemini is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GEMINI_API_KEY is not set. Add it to backend/.env and restart.",
            )
        _gemini = genai.Client(api_key=api_key)
    return _gemini


# ---------------------------------------------------------------------------
# Confluent Kafka producer — lazily created, None when credentials are absent
# (publishing is best-effort and never blocks the HTTP response)
# ---------------------------------------------------------------------------
KAFKA_TOPIC = os.getenv("CONFLUENT_TOPIC", "flawless-take-events")
_producer: Producer | None = None


def _get_producer() -> Producer | None:
    """Return a cached Producer, or None if Confluent credentials are not set."""
    global _producer
    if _producer is not None:
        return _producer
    bootstrap = os.getenv("CONFLUENT_BOOTSTRAP_SERVERS")
    api_key = os.getenv("CONFLUENT_API_KEY")
    api_secret = os.getenv("CONFLUENT_API_SECRET")
    if not all([bootstrap, api_key, api_secret]):
        return None
    _producer = Producer(
        {
            "bootstrap.servers": bootstrap,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": api_key,
            "sasl.password": api_secret,
        }
    )
    return _producer


def _publish_event(payload: dict) -> None:
    """Serialize payload to JSON and produce to Kafka. Errors are logged, never raised."""
    producer = _get_producer()
    if producer is None:
        logger.debug("Kafka producer not configured — skipping event publish.")
        return

    def _on_delivery(err, msg):
        if err:
            logger.error("Kafka delivery failed: %s", err)
        else:
            logger.info("Kafka event delivered → %s [%d]", msg.topic(), msg.partition())

    try:
        producer.produce(
            topic=KAFKA_TOPIC,
            value=json.dumps(payload, ensure_ascii=False).encode(),
            on_delivery=_on_delivery,
        )
        producer.poll(0)  # trigger delivery callbacks without blocking
    except Exception:
        logger.exception("Kafka produce() raised unexpectedly")


app = FastAPI(title="Flawless Take API")

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Script upload — extract scene & character notes from a PDF shooting script
# ---------------------------------------------------------------------------
_SCRIPT_EXTRACT_PROMPT = """\
You are a script supervisor reading a shooting script.
Extract structured notes that would help a makeup/continuity department.

Return a JSON object with this exact shape:
{
  "scenes": [
    {
      "scene_number": "string",
      "heading": "string",
      "characters": ["string"],
      "continuity_notes": "string"
    }
  ],
  "characters": [
    {
      "name": "string",
      "appearance_notes": "string"
    }
  ],
  "general_notes": "string"
}

Rules:
- Only include scenes and characters actually present in the document.
- continuity_notes should mention wardrobe, makeup, props, or physical state described in the scene.
- appearance_notes should describe the character's established look across all their scenes.
- general_notes should capture any production-wide continuity concerns.
- If a field has no relevant content, use an empty string or empty array.
"""


@app.post("/api/upload-script")
async def upload_script(file: UploadFile = File(...)) -> dict:
    """
    Accepts a PDF shooting script and returns structured scene/character
    continuity notes extracted by Gemini.
    """
    if file.content_type not in ("application/pdf",):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()

    doc_content = DocumentContent(
        data=base64.b64encode(pdf_bytes).decode(),
        mime_type="application/pdf",
    )
    prompt_content = TextContent(text=_SCRIPT_EXTRACT_PROMPT)

    try:
        interaction = _get_client().interactions.create(
            model=MODEL,
            input=[doc_content, prompt_content],
            response_format=TextResponseFormat(mime_type="application/json"),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini error: {exc}") from exc

    try:
        notes = json.loads(interaction.output_text or "{}")
    except json.JSONDecodeError:
        notes = {"raw": interaction.output_text}

    return {
        "filename": file.filename,
        "size_bytes": len(pdf_bytes),
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Continuity prompt
# ---------------------------------------------------------------------------
def _build_prompt(
    scene: str,
    take: str,
    character: str,
    script_context: str = "",
) -> str:
    script_section = (
        f"\n\nSCRIPT REFERENCE FOR THIS SCENE:\n{script_context}\n"
        if script_context.strip()
        else ""
    )

    return f"""You are an experienced on-set continuity supervisor reviewing footage for a film production.

You have been given a reference photograph from the following shoot:
  • Scene:     {scene}
  • Take:      {take}
  • Character: {character}{script_section}

Carefully examine the image and provide a structured continuity report covering:

1. **Makeup & Hair** — skin tone consistency, foundation, lipstick, eye makeup, hair position/styling, flyaways.
2. **Wardrobe** — visible clothing items, collar/lapel position, buttons, jewellery, accessories.
3. **Props** — any hand-held or on-body props visible in frame.
4. **Overall continuity risk** — rate as LOW / MEDIUM / HIGH and briefly explain why.

Format your response with the four numbered sections above.
Be concise but specific: note the exact detail (e.g. "top shirt button undone", "lipstick slightly darker on lower lip").
{
    "Cross-reference the script notes above and flag any deviations from the described character state."
    if script_context.strip()
    else "If something cannot be assessed because it is out of frame or unclear, say so explicitly rather than guessing."
}"""


# ---------------------------------------------------------------------------
# Check-take route
# ---------------------------------------------------------------------------
@app.post("/api/check-take")
async def check_take(
    scene: str = Form(...),
    take: str = Form(...),
    character: str = Form(...),
    file: UploadFile = File(...),
    script_context: str = Form(""),
) -> dict:
    """
    Accepts scene metadata, an image, and optional script context extracted
    from an uploaded PDF. Runs Gemini continuity analysis and returns the report.
    """
    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"

    image_content = ImageContent(
        data=base64.b64encode(image_bytes).decode(),
        mime_type=mime_type,
    )
    text_content = TextContent(
        text=_build_prompt(scene, take, character, script_context)
    )

    try:
        interaction = _get_client().interactions.create(
            model=MODEL,
            input=[image_content, text_content],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini error: {exc}") from exc

    analysis = interaction.output_text or ""

    _publish_event(
        {
            "event": "continuity_check",
            "timestamp": time.time(),
            "scene": scene,
            "take": take,
            "character": character,
            "filename": file.filename,
            "size_bytes": len(image_bytes),
            "script_grounded": bool(script_context.strip()),
            "risk_level": _extract_risk(analysis),
        }
    )

    return {
        "scene": scene,
        "take": take,
        "character": character,
        "filename": file.filename,
        "size_bytes": len(image_bytes),
        "result": analysis,
        "script_grounded": bool(script_context.strip()),
    }


def _extract_risk(text: str) -> str:
    """Pull LOW / MEDIUM / HIGH out of the Gemini report, or return UNKNOWN."""
    m = re.search(r"\b(LOW|MEDIUM|HIGH)\b", text, re.IGNORECASE)
    return m.group(1).upper() if m else "UNKNOWN"
