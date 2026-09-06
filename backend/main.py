from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure backend/ siblings (database, storage) are importable regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))

from confluent_kafka import Consumer, Producer
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai.interactions import DocumentContent, ImageContent, TextContent, TextResponseFormat

import database
import storage

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    yield


app = FastAPI(title="Flawless Take API", lifespan=lifespan)

# Serve uploaded preview images
app.mount("/uploads", StaticFiles(directory=str(storage.UPLOADS_DIR)), name="uploads")

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
# Alerts — SSE stream that consumes flawless-take-events from Kafka
# ---------------------------------------------------------------------------
def _make_consumer() -> Consumer | None:
    """Create a fresh Kafka Consumer. Returns None if credentials are absent."""
    bootstrap = os.getenv("CONFLUENT_BOOTSTRAP_SERVERS")
    api_key = os.getenv("CONFLUENT_API_KEY")
    api_secret = os.getenv("CONFLUENT_API_SECRET")
    if not all([bootstrap, api_key, api_secret]):
        return None
    c = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": api_key,
            "sasl.password": api_secret,
            "group.id": f"flawless-alerts-{int(time.time())}",  # unique group → always read latest
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
        }
    )
    c.subscribe([KAFKA_TOPIC])
    return c


async def _sse_generator():
    """Yield SSE-formatted strings by polling Kafka in a thread pool."""
    loop = asyncio.get_event_loop()
    consumer = await loop.run_in_executor(None, _make_consumer)

    if consumer is None:
        yield "data: {\"error\": \"Kafka not configured\"}\n\n"
        return

    # send a heartbeat immediately so the browser connection opens
    yield ": heartbeat\n\n"

    try:
        while True:
            msg = await loop.run_in_executor(None, lambda: consumer.poll(1.0))
            if msg is None:
                # no message — send keep-alive comment so the connection stays open
                yield ": keep-alive\n\n"
                continue
            if msg.error():
                logger.error("Kafka consumer error: %s", msg.error())
                yield f"data: {{\"error\": \"{msg.error()}\"}}\n\n"
                continue
            try:
                payload = json.loads(msg.value().decode())
            except Exception:
                continue
            yield f"data: {json.dumps(payload)}\n\n"
    finally:
        await loop.run_in_executor(None, consumer.close)


@app.get("/api/alerts")
async def alerts():
    """
    Server-Sent Events stream. Connect with EventSource('/api/alerts').
    Each event is a JSON-encoded Kafka message from flawless-take-events.
    """
    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if proxied
        },
    )


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
    risk = _extract_risk(analysis)

    # Save preview image and persist to DB (best-effort)
    try:
        preview_filename = await storage.save(image_bytes, mime_type)
    except Exception:
        logger.exception("Storage save failed — continuing without preview")
        preview_filename = None

    record_id = await database.save_check(
        scene=scene,
        character=character,
        take=take,
        risk_level=risk,
        script_grounded=bool(script_context.strip()),
        report=analysis,
        preview_ref=preview_filename,
    )

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
            "risk_level": risk,
        }
    )

    return {
        "id": record_id,
        "scene": scene,
        "take": take,
        "character": character,
        "filename": file.filename,
        "size_bytes": len(image_bytes),
        "result": analysis,
        "script_grounded": bool(script_context.strip()),
        "preview_url": storage.url(preview_filename) if preview_filename else None,
    }


def _extract_risk(text: str) -> str:
    """Pull LOW / MEDIUM / HIGH out of the Gemini report, or return UNKNOWN."""
    m = re.search(r"\b(LOW|MEDIUM|HIGH)\b", text, re.IGNORECASE)
    return m.group(1).upper() if m else "UNKNOWN"


def _extract_match_score(text: str) -> str:
    """Pull POOR / FAIR / GOOD out of the Gemini comparison report, or return UNKNOWN."""
    m = re.search(r"\b(POOR|FAIR|GOOD)\b", text, re.IGNORECASE)
    return m.group(1).upper() if m else "UNKNOWN"


# ---------------------------------------------------------------------------
# Compare-takes prompt
# ---------------------------------------------------------------------------
def _build_comparison_prompt(
    scene: str,
    take_ref: str,
    take_current: str,
    character: str,
    script_context: str = "",
) -> str:
    script_section = (
        f"\n\nSCRIPT REFERENCE:\n{script_context}\n"
        if script_context.strip()
        else ""
    )
    return f"""You are an experienced on-set continuity supervisor comparing two photographs.

IMAGE 1 is the REFERENCE take. IMAGE 2 is the CURRENT take being evaluated.

Production details:
  • Scene:          {scene}
  • Reference take: {take_ref}
  • Current take:   {take_current}
  • Character:      {character}{script_section}

Your task: identify every visible continuity difference between the two images.

Provide your report in exactly these four sections:

1. **Makeup & Hair differences** — note any change in foundation, lip colour, eye makeup, SFX wounds, hair position, flyaways, stubble length. If identical, state "No differences detected."
2. **Wardrobe differences** — note any change in collar position, buttons, garment distressing, accessories, jewellery. If identical, state "No differences detected."
3. **Props differences** — note any change in hand-held or on-body props. If identical, state "No differences detected."
4. **Overall assessment**
   - Continuity risk: LOW / MEDIUM / HIGH
   - Match score: GOOD (minor or no issues) / FAIR (some fixable issues) / POOR (significant mismatches)
   - Summary: one sentence describing the most critical discrepancy, or "Takes match well."

Be precise: describe exact location and nature of each difference (e.g. "collar popped in reference, flat in current", "SFX wound appears lighter/smaller in current take").
Do not describe elements that are the same between the two images."""


# ---------------------------------------------------------------------------
# Compare-takes route
# ---------------------------------------------------------------------------
@app.post("/api/compare-takes")
async def compare_takes(
    scene: str = Form(...),
    take_ref: str = Form(...),
    take_current: str = Form(...),
    character: str = Form(...),
    reference: UploadFile = File(...),
    current: UploadFile = File(...),
    script_context: str = Form(""),
) -> dict:
    """
    Accepts two images (reference take + current take) and returns a structured
    diff report from Gemini. Publishes a takes_comparison event to Kafka.
    """
    ref_bytes = await reference.read()
    cur_bytes = await current.read()

    ref_content = ImageContent(
        data=base64.b64encode(ref_bytes).decode(),
        mime_type=reference.content_type or "image/jpeg",
    )
    cur_content = ImageContent(
        data=base64.b64encode(cur_bytes).decode(),
        mime_type=current.content_type or "image/jpeg",
    )
    prompt_content = TextContent(
        text=_build_comparison_prompt(
            scene, take_ref, take_current, character, script_context
        )
    )

    try:
        interaction = _get_client().interactions.create(
            model=MODEL,
            input=[ref_content, cur_content, prompt_content],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini error: {exc}") from exc

    analysis = interaction.output_text or ""
    risk = _extract_risk(analysis)
    match_score = _extract_match_score(analysis)
    ref_mime = reference.content_type or "image/jpeg"
    cur_mime = current.content_type or "image/jpeg"

    # Save preview images (best-effort)
    try:
        preview_ref = await storage.save(ref_bytes, ref_mime)
        preview_cur = await storage.save(cur_bytes, cur_mime)
    except Exception:
        logger.exception("Storage save failed — continuing without previews")
        preview_ref = preview_cur = None

    record_id = await database.save_comparison(
        scene=scene,
        character=character,
        take_ref=take_ref,
        take_current=take_current,
        risk_level=risk,
        match_score=match_score,
        script_grounded=bool(script_context.strip()),
        report=analysis,
        preview_ref=preview_ref,
        preview_cur=preview_cur,
    )

    _publish_event(
        {
            "event": "takes_comparison",
            "timestamp": time.time(),
            "scene": scene,
            "take_ref": take_ref,
            "take_current": take_current,
            "character": character,
            "ref_filename": reference.filename,
            "cur_filename": current.filename,
            "script_grounded": bool(script_context.strip()),
            "risk_level": risk,
            "match_score": match_score,
        }
    )

    return {
        "id": record_id,
        "scene": scene,
        "take_ref": take_ref,
        "take_current": take_current,
        "character": character,
        "ref_filename": reference.filename,
        "cur_filename": current.filename,
        "differences": analysis,
        "risk_level": risk,
        "match_score": match_score,
        "script_grounded": bool(script_context.strip()),
        "preview_ref_url": storage.url(preview_ref) if preview_ref else None,
        "preview_cur_url": storage.url(preview_cur) if preview_cur else None,
    }


# ---------------------------------------------------------------------------
# History endpoints
# ---------------------------------------------------------------------------
@app.get("/api/history")
async def history(
    scene: str | None = Query(None),
    character: str | None = Query(None),
    limit: int = Query(100, le=500),
) -> list[dict]:
    """
    Return continuity check history, newest first.
    Optional query params: scene, character, limit.
    """
    records = await database.list_records(scene=scene, character=character, limit=limit)
    # Attach preview URLs
    for r in records:
        r["preview_ref_url"] = storage.url(r["preview_ref"]) if r.get("preview_ref") else None
        r["preview_cur_url"] = storage.url(r["preview_cur"]) if r.get("preview_cur") else None
    return records


@app.get("/api/history/{record_id}")
async def history_record(record_id: int) -> dict:
    """Return a single history record by id, including the full report."""
    record = await database.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    record["preview_ref_url"] = storage.url(record["preview_ref"]) if record.get("preview_ref") else None
    record["preview_cur_url"] = storage.url(record["preview_cur"]) if record.get("preview_cur") else None
    return record


@app.delete("/api/history/{record_id}")
async def delete_history_record(record_id: int) -> dict[str, str]:
    """Delete a single history record by id."""
    deleted = await database.delete_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"status": "deleted", "id": str(record_id)}

