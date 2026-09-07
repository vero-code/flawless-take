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
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from pydantic import BaseModel

import agent_service
import agent_tools
import database
import environments
import mcp_server as _mcp_server
import safety_config
import scene_memory
import secrets_manager
import storage

logger = logging.getLogger(__name__)

# Always load from backend/.env relative to this file, regardless of cwd
load_dotenv(Path(__file__).parent / ".env")
# Resolve Studio Secrets dynamically (Google Cloud Secret Manager or local .env)
secrets_manager.load_studio_secrets()

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


_alert_subscribers: set[asyncio.Queue[str]] = set()


def _broadcast_event(payload: dict) -> None:
    """Broadcast an alert payload to all connected SSE clients."""
    data_str = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    dead = set()
    for q in _alert_subscribers:
        try:
            q.put_nowait(data_str)
        except Exception:
            dead.add(q)
    _alert_subscribers.difference_update(dead)


def _publish_event(payload: dict) -> None:
    """Serialize payload to JSON, broadcast locally, and produce to Kafka."""
    _broadcast_event(payload)
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
    agent_tools.register_event_publisher(_publish_event)
    yield


app = FastAPI(title="Flawless Take API", lifespan=lifespan)

# Serve uploaded preview images
app.mount("/uploads", StaticFiles(directory=str(storage.UPLOADS_DIR)), name="uploads")

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:8000",   # MCP Inspector / local studio clients
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Phase 4 Step 5: Mount MCP server (SSE transport at /mcp)
# ---------------------------------------------------------------------------
app.mount("/mcp", _mcp_server.mcp_app)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/mcp-info")
async def mcp_info() -> dict:
    """Return MCP server metadata for the UI status badge."""
    return {
        "server_name": "Flawless Take Studio MCP",
        "version": "1.0.0",
        "transport": "SSE",
        "sse_endpoint": "/mcp/sse",
        "tools": _mcp_server.MCP_TOOL_NAMES,
        "tool_count": len(_mcp_server.MCP_TOOL_NAMES),
        "claude_desktop_config": {
            "mcpServers": {
                "flawless-take": {
                    "url": "http://localhost:8000/mcp/sse"
                }
            }
        },
    }


# ---------------------------------------------------------------------------
# Phase 4 Step 6: Google Cloud Agent Development Kit (ADK) & Agent Engine Info
# ---------------------------------------------------------------------------
@app.get("/api/agent-engine/info")
async def agent_engine_info() -> dict:
    """Return Google Cloud ADK Agent Engine packaging status and specifications."""
    manifest_file = Path(__file__).parent / "agent_engine" / "manifest.json"
    manifest_data = {}
    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

    return {
        "status": "ready",
        "framework": "Google Cloud Agent Development Kit (ADK)",
        "agent_name": manifest_data.get("name", "flawless-take-continuity-supervisor"),
        "version": manifest_data.get("version", "1.0.0"),
        "model": manifest_data.get("model", {}).get("name", "gemini-3.8-flash"),
        "entrypoint": "agent_engine.agent:ContinuitySupervisorAgent",
        "serverless_app": "agent_engine.serverless_app:app",
        "tools_count": len(manifest_data.get("tools", [])),
        "deployment_targets": [
            "Google Cloud Vertex AI Reasoning Engine / Agent Engine",
            "Google Cloud Run (Serverless Container)",
        ],
        "dockerfile": "Dockerfile.agent_engine",
        "manifest": manifest_data,
    }


# ---------------------------------------------------------------------------
# Phase 5 Step 1: Safety & Guardrails Policy Endpoint
# ---------------------------------------------------------------------------
@app.get("/api/safety/config")
async def safety_config_info() -> dict:
    """Return active Gemini Safety Settings and film studio guardrails policy."""
    return safety_config.get_safety_policy_metadata()


# ---------------------------------------------------------------------------
# Phase 5 Step 2: Studio Secrets Status Endpoint (Google Secret Manager)
# ---------------------------------------------------------------------------
@app.get("/api/secrets/status")
async def secrets_status() -> dict:
    """Return safe audit status of studio secrets and Secret Manager integration."""
    return secrets_manager.get_secrets_status()


# ---------------------------------------------------------------------------
# Phase 5 Step 4: Agent Deployment & Multi-Environment (Agent Builder)
# ---------------------------------------------------------------------------
@app.get("/api/system/version")
async def system_version() -> dict:
    """Return active serving environment, immutable version history, and Agent Builder metadata."""
    return environments.get_environment_metadata()


@app.post("/api/webhook/agent-builder")
async def agent_builder_webhook(request: Request) -> dict:
    """
    Official Google Cloud Agent Builder / Dialogflow CX webhook fulfillment endpoint.
    Handles intent tags (check_continuity, generate_checklist, emit_alert).
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    return await environments.handle_agent_builder_webhook_async(body)


@app.get("/api/agent-builder/spec")
async def agent_builder_spec() -> dict:
    """Return the official Google Cloud Agent Builder / Dialogflow CX specification."""
    spec_path = Path(__file__).parent / "agent_builder_spec.json"
    if spec_path.exists():
        with open(spec_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"error": "agent_builder_spec.json not found"}


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


async def _sse_generator(request: Request):
    """Yield SSE-formatted strings without blocking threads or event loop."""
    q: asyncio.Queue[str] = asyncio.Queue()
    _alert_subscribers.add(q)
    yield ": heartbeat\n\n"
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await asyncio.wait_for(q.get(), timeout=10.0)
                yield data
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
    finally:
        _alert_subscribers.discard(q)


@app.get("/api/alerts")
async def alerts(request: Request):
    """
    Server-Sent Events stream. Connect with EventSource('/api/alerts').
    Broadcasts real-time events to connected browser tabs without blocking.
    """
    return StreamingResponse(
        _sse_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
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
# Risk, score, and scene memory delegates (implementation in scene_memory.py)
# ---------------------------------------------------------------------------
_extract_risk = scene_memory.extract_risk
_extract_match_score = scene_memory.extract_match_score
_extract_take_summary = scene_memory.extract_take_summary
_extract_key_issues = scene_memory.extract_key_issues
_format_scene_memory_prompt = scene_memory.format_scene_memory_prompt
_build_scene_state = scene_memory.build_scene_state


# ---------------------------------------------------------------------------
# Continuity prompt
# ---------------------------------------------------------------------------
def _build_prompt(
    scene: str,
    take: str,
    character: str,
    script_context: str = "",
    scene_memory: str = "",
) -> str:
    script_section = (
        f"\n\nSCRIPT REFERENCE FOR THIS SCENE:\n{script_context}\n"
        if script_context.strip()
        else ""
    )
    memory_section = (
        f"\n\nPRIOR SCENE MEMORY (HISTORICAL CONTINUITY CONTEXT):\n{scene_memory}\n"
        if scene_memory.strip()
        else ""
    )
    drift_section = (
        "\n5. **Scene Drift Trend** — state [RESOLVED], [PERSISTENT], or [NEW DRIFT] relative to prior takes."
        if scene_memory.strip()
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
    if (script_context.strip() or scene_memory.strip())
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
    from an uploaded PDF. Runs Gemini continuity analysis with state tracking.
    """
    # 1. Fetch prior scene chronology for state tracking
    chronology = await database.get_scene_chronology(scene, character)
    scene_memory = _format_scene_memory_prompt(scene, character, chronology)

    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"

    image_content = ImageContent(
        data=base64.b64encode(image_bytes).decode(),
        mime_type=mime_type,
    )
    text_content = TextContent(
        text=_build_prompt(scene, take, character, script_context, scene_memory)
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

    updated_chronology = await database.get_scene_chronology(scene, character)
    scene_state = _build_scene_state(scene, character, updated_chronology)

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
# Compare-takes prompt
# ---------------------------------------------------------------------------
def _build_comparison_prompt(
    scene: str,
    take_ref: str,
    take_current: str,
    character: str,
    script_context: str = "",
    scene_memory: str = "",
) -> str:
    script_section = (
        f"\n\nSCRIPT REFERENCE:\n{script_context}\n"
        if script_context.strip()
        else ""
    )
    memory_section = (
        f"\n\nPRIOR SCENE MEMORY (ACCUMULATED CONTINUITY HISTORY):\n{scene_memory}\n"
        if scene_memory.strip()
        else ""
    )
    drift_instruction = (
        "\n   - Scene Drift Trend: [RESOLVED] / [PERSISTENT] / [NEW DRIFT] with a 1-sentence explanation comparing against scene memory."
        if scene_memory.strip()
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
    # 1. Fetch prior scene chronology for state tracking
    chronology = await database.get_scene_chronology(scene, character)
    scene_memory = _format_scene_memory_prompt(scene, character, chronology)

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
            scene, take_ref, take_current, character, script_context, scene_memory
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

    updated_chronology = await database.get_scene_chronology(scene, character)
    scene_state = _build_scene_state(scene, character, updated_chronology)

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


# ---------------------------------------------------------------------------
# Scene State & Memory endpoint
# ---------------------------------------------------------------------------
@app.get("/api/scene-state")
async def get_scene_state(
    scene: str = Query(..., description="Scene heading/name"),
    character: str = Query(..., description="Character name"),
) -> dict:
    """
    Return accumulated continuity memory, drift status (STABLE / DRIFTING / CRITICAL),
    baseline take, and chronological take timeline for a given scene and character.
    """
    chronology = await database.get_scene_chronology(scene, character)
    return _build_scene_state(scene, character, chronology)



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


@app.get("/api/history/{record_id}/pdf")
async def export_history_pdf(record_id: int):
    """Generate and return an official Continuity Log PDF for a record."""
    record = await database.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    try:
        import pdf_export
        pdf_bytes = pdf_export.generate_continuity_pdf(record)
    except Exception as exc:
        logger.exception("Failed to generate PDF")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}") from exc

    from urllib.parse import quote
    from fastapi.responses import Response

    scene_part = str(record.get("scene", "scene")).strip().replace(" ", "_")
    take_part = record.get("take") or f"{record.get('take_ref')}_vs_{record.get('take_current')}" or "log"
    raw_name = f"continuity_{scene_part}_take_{take_part}.pdf"
    encoded_name = quote(raw_name)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
        },
    )


# ---------------------------------------------------------------------------
# Phase 4: Autonomous Agent Copilot (AFC Tool Calling)
# ---------------------------------------------------------------------------
class AgentQueryRequest(BaseModel):
    prompt: str
    scene: str = ""
    character: str = ""
    script_context: str = ""


@app.post("/api/agent/query")
async def agent_query_endpoint(req: AgentQueryRequest) -> dict:
    """Run autonomous agent query with tool calling."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    try:
        result = await agent_service.run_agent_query(
            prompt=req.prompt,
            scene=req.scene,
            character=req.character,
            script_context=req.script_context,
        )
        return result
    except Exception as exc:
        logger.exception("Agent query failed")
        raise HTTPException(status_code=500, detail=f"Agent execution error: {exc}") from exc


# ---------------------------------------------------------------------------
# Phase 4 Step 3: Direct Department Action Checklist endpoint
# ---------------------------------------------------------------------------
class ChecklistRequest(BaseModel):
    scene: str
    character: str
    discrepancies: str            # plain-text violations, one per line or comma-separated
    next_take: str = ""


@app.post("/api/agent/checklist")
async def generate_checklist_endpoint(req: ChecklistRequest) -> dict:
    """
    Directly invoke the generate_department_checklist tool without a full agent loop.
    Returns a structured department action checklist JSON.
    """
    if not req.discrepancies.strip():
        raise HTTPException(status_code=400, detail="discrepancies cannot be empty")
    try:
        result = await agent_tools.generate_department_checklist(
            scene=req.scene,
            character=req.character,
            discrepancies=req.discrepancies,
            next_take=req.next_take,
        )
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Checklist generation failed")
        raise HTTPException(status_code=500, detail=f"Checklist generation error: {exc}") from exc


# ---------------------------------------------------------------------------
# Phase 5 Step 3: Production SPA Static Hosting (React build in dist/)
# ---------------------------------------------------------------------------
_dist_dir = Path(__file__).resolve().parent.parent / "dist"
if not _dist_dir.exists():
    _dist_dir = Path(__file__).resolve().parent / "dist"

if _dist_dir.exists():
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Do not intercept API, MCP, or Uploads routes
        if full_path.startswith("api/") or full_path.startswith("mcp") or full_path.startswith("uploads/"):
            raise HTTPException(status_code=404, detail="Not found")
        target_file = _dist_dir / full_path
        if full_path and target_file.is_file():
            return FileResponse(str(target_file))
        return FileResponse(str(_dist_dir / "index.html"))
