"""
routers/history.py - Scene State, History Records, and PDF Continuity Log Endpoints
"""
from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Response

import database
import pdf_export
import scene_memory
import storage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["History & Continuity State"])


def _attach_preview_urls(record: dict) -> dict:
    """Mutate *record* in-place to add resolved preview_ref_url / preview_cur_url."""
    record["preview_ref_url"] = storage.url(record["preview_ref"]) if record.get("preview_ref") else None
    record["preview_cur_url"] = storage.url(record["preview_cur"]) if record.get("preview_cur") else None
    return record


@router.get("/api/scene-state")
async def get_scene_state(
    scene: str = Query(..., description="Scene heading/name"),
    character: str = Query(..., description="Character name"),
) -> dict:
    """
    Return accumulated continuity memory, drift status (STABLE / DRIFTING / CRITICAL),
    baseline take, and chronological take timeline for a given scene and character.
    """
    chronology = await database.get_scene_chronology(scene, character)
    return scene_memory.build_scene_state(scene, character, chronology)


@router.get("/api/history")
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
    for r in records:
        _attach_preview_urls(r)
    return records


@router.get("/api/history/{record_id}")
async def history_record(record_id: int) -> dict:
    """Return a single history record by id, including the full report."""
    record = await database.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return _attach_preview_urls(record)


@router.delete("/api/history/{record_id}")
async def delete_history_record(record_id: int) -> dict[str, str]:
    """Delete a single history record by id."""
    deleted = await database.delete_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"status": "deleted", "id": str(record_id)}


@router.get("/api/history/{record_id}/pdf")
async def export_history_pdf(record_id: int):
    """Generate and return an official Continuity Log PDF for a record."""
    record = await database.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    try:
        pdf_bytes = pdf_export.generate_continuity_pdf(record)
    except Exception as exc:
        logger.exception("Failed to generate PDF")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}") from exc

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
