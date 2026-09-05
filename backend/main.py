from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai.interactions import DocumentContent, ImageContent, TextContent, TextResponseFormat

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

    # TODO: publish event to Confluent Kafka topic

    return {
        "scene": scene,
        "take": take,
        "character": character,
        "filename": file.filename,
        "size_bytes": len(image_bytes),
        "result": analysis,
        "script_grounded": bool(script_context.strip()),
    }
