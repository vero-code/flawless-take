"""
routers/vision.py - Vision & Take Continuity Analysis Endpoints

Handles Gemini multimodal visual continuity inspection for:
- PDF Shooting script continuity note extraction
- Single take visual inspection against scene memory
- Dual-take comparative differential analysis
"""
from __future__ import annotations

import json
import logging
import os
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from google import genai
from google.genai import types

import database
import event_bus
import safety_config
import scene_memory
import storage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Vision & Continuity Analysis"])

MODEL = "gemini-3.8-flash"
_gemini: genai.Client | None = None


def _get_client() -> genai.Client:
    """Return cached genai.Client, or raise 500 if GEMINI_API_KEY is not set."""
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
# Script upload prompt & endpoint
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


@router.post("/api/upload-script")
async def upload_script(file: UploadFile = File(...)) -> dict:
    """
    Accepts a PDF shooting script and returns structured scene/character
    continuity notes extracted by Gemini.
    """
    if file.content_type not in ("application/pdf",):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()
    client = _get_client()

    try:
        resp = await client.aio.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                _SCRIPT_EXTRACT_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                safety_settings=safety_config.get_safety_settings(),
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini error: {exc}") from exc

    raw_text = (resp.text or "").strip()
    try:
        notes = json.loads(raw_text)
    except json.JSONDecodeError:
        notes = {"raw": raw_text}

    return {
        "filename": file.filename,
        "size_bytes": len(pdf_bytes),
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Single Take Continuity Prompt & Endpoint
# ---------------------------------------------------------------------------
def _build_prompt(
    scene: str,
    take: str,
    character: str,
    script_context: str = "",
    scene_memory_text: str = "",
) -> str:
    script_section = (
        f"\n\nSCRIPT REFERENCE FOR THIS SCENE:\n{script_context}\n"
        if script_context.strip()
        else ""
    )
    memory_section = (
        f"\n\nPRIOR SCENE MEMORY (HISTORICAL CONTINUITY CONTEXT):\n{scene_memory_text}\n"
        if scene_memory_text.strip()
        else ""
    )
    drift_section = (
        "\n5. **Scene Drift Trend** — state [RESOLVED], [PERSISTENT], or [NEW DRIFT] relative to prior takes."
        if scene_memory_text.strip()
        else ""
    )

    return f"""You are an experienced on-set continuity supervisor reviewing footage for a film production.

You have been given a reference photograph from the following shoot:
  • Scene:     {scene}
  • Take:      {take}
  • Character: {character}{script_section}{memory_section}

Carefully examine the image and provide a structured continuity report covering:

1. **Makeup & Hair** — skin tone consistency, foundation, lipstick, eye makeup, hair position/styling, flyaways.
2. **Wardrobe** — visible clothing items, collar/lapel position, buttons, jewellery, accessories.
3. **Props** — any hand-held or on-body props visible in frame.
4. **Overall continuity risk** — rate as LOW / MEDIUM / HIGH and briefly explain why.{drift_section}

Format your response with the numbered sections above.
Be concise but specific: note the exact detail (e.g. "top shirt button undone", "lipstick slightly darker on lower lip").
{
    "Cross-reference the script notes and scene memory above and flag any deviations from established state."
    if (script_context.strip() or scene_memory_text.strip())
    else "If something cannot be assessed because it is out of frame or unclear, say so explicitly rather than guessing."
}"""


@router.post("/api/check-take")
async def check_take(
    scene: str = Form(...),
    take: str = Form(...),
    character: str = Form(...),
    file: UploadFile = File(...),
    script_context: str = Form(""),
) -> dict:
    """
    Accepts scene metadata, an image, and optional script context extracted
    from an uploaded PDF. Runs Gemini continuity analysis with state tracking.
    """
    chronology = await database.get_scene_chronology(scene, character)
    mem_prompt = scene_memory.format_scene_memory_prompt(scene, character, chronology)

    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"
    client = _get_client()

    prompt_text = _build_prompt(scene, take, character, script_context, mem_prompt)

    try:
        resp = await client.aio.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt_text,
            ],
            config=types.GenerateContentConfig(
                safety_settings=safety_config.get_safety_settings(),
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini error: {exc}") from exc

    analysis = (resp.text or "").strip()
    risk = scene_memory.extract_risk(analysis)

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

    event_bus.publish_event(
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

    updated_chronology = await database.get_scene_chronology(scene, character)
    scene_state = scene_memory.build_scene_state(scene, character, updated_chronology)

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
        "scene_state": scene_state,
    }


# ---------------------------------------------------------------------------
# Compare Takes Prompt & Endpoint
# ---------------------------------------------------------------------------
def _build_comparison_prompt(
    scene: str,
    take_ref: str,
    take_current: str,
    character: str,
    script_context: str = "",
    scene_memory_text: str = "",
) -> str:
    script_section = (
        f"\n\nSCRIPT REFERENCE:\n{script_context}\n"
        if script_context.strip()
        else ""
    )
    memory_section = (
        f"\n\nPRIOR SCENE MEMORY (ACCUMULATED CONTINUITY HISTORY):\n{scene_memory_text}\n"
        if scene_memory_text.strip()
        else ""
    )
    drift_instruction = (
        "\n   - Scene Drift Trend: [RESOLVED] / [PERSISTENT] / [NEW DRIFT] with a 1-sentence explanation comparing against scene memory."
        if scene_memory_text.strip()
        else ""
    )
    return f"""You are an experienced on-set continuity supervisor comparing two photographs.

IMAGE 1 is the REFERENCE take. IMAGE 2 is the CURRENT take being evaluated.

Production details:
  • Scene:          {scene}
  • Reference take: {take_ref}
  • Current take:   {take_current}
  • Character:      {character}{script_section}{memory_section}

Your task: identify every visible continuity difference between the two images.

Provide your report in exactly these four sections:

1. **Makeup & Hair differences** — note any change in foundation, lip colour, eye makeup, SFX wounds, hair position, flyaways, stubble length. If identical, state "No differences detected."
2. **Wardrobe differences** — note any change in collar position, buttons, garment distressing, accessories, jewellery. If identical, state "No differences detected."
3. **Props differences** — note any change in hand-held or on-body props. If identical, state "No differences detected."
4. **Overall assessment**
   - Continuity risk: LOW / MEDIUM / HIGH
   - Match score: GOOD (minor or no issues) / FAIR (some fixable issues) / POOR (significant mismatches)
   - Summary: one sentence describing the most critical discrepancy, or "Takes match well."{drift_instruction}

Be precise: describe exact location and nature of each difference (e.g. "collar popped in reference, flat in current", "SFX wound appears lighter/smaller in current take").
Do not describe elements that are the same between the two images."""


@router.post("/api/compare-takes")
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
    diff report from Gemini. Publishes a takes_comparison event to Kafka and SSE.
    """
    chronology = await database.get_scene_chronology(scene, character)
    mem_prompt = scene_memory.format_scene_memory_prompt(scene, character, chronology)

    ref_bytes = await reference.read()
    cur_bytes = await current.read()
    ref_mime = reference.content_type or "image/jpeg"
    cur_mime = current.content_type or "image/jpeg"

    prompt_text = _build_comparison_prompt(
        scene, take_ref, take_current, character, script_context, mem_prompt
    )

    client = _get_client()
    try:
        resp = await client.aio.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(data=ref_bytes, mime_type=ref_mime),
                types.Part.from_bytes(data=cur_bytes, mime_type=cur_mime),
                prompt_text,
            ],
            config=types.GenerateContentConfig(
                safety_settings=safety_config.get_safety_settings(),
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini error: {exc}") from exc

    analysis = (resp.text or "").strip()
    risk = scene_memory.extract_risk(analysis)
    match_score = scene_memory.extract_match_score(analysis)

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

    event_bus.publish_event(
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

    updated_chronology = await database.get_scene_chronology(scene, character)
    scene_state = scene_memory.build_scene_state(scene, character, updated_chronology)

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
        "scene_state": scene_state,
    }
