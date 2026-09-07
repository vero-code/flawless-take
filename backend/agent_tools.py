"""
agent_tools.py - Autonomous Tools for Flawless Take Continuity Agent

Defines callable tools with Google GenAI function calling schemas for:
- Querying scene state and continuity memory in SQLite
- Retrieving previous take check/comparison reports
- Checking shooting script continuity notes
- Comparing recorded takes
- Emitting real-time continuity alerts to Kafka topic & SSE crew feed
- Generating and exporting official PDF continuity logs
- Synthesizing discovered violations into a structured department action checklist
"""
import json
import logging
import os
import re
import time
from typing import Callable

import database
import safety_config
import storage

logger = logging.getLogger(__name__)

# Callback hook to publish alerts to Kafka & SSE from main.py
_publish_event_fn: Callable = None


def register_event_publisher(fn: Callable) -> None:
    """Register the backend's event broadcaster/Kafka publisher."""
    global _publish_event_fn
    _publish_event_fn = fn


async def get_scene_continuity_state(scene: str, character: str) -> dict:
    """
    Get the accumulated continuity memory, drift status, and historical takes for a scene and character.
    Args:
        scene: Scene slug or heading (e.g. 'EXT. ROOFTOP - NIGHT')
        character: Character name (e.g. 'Alice')
    Returns:
        Dictionary containing total takes, drift_status (STABLE, DRIFTING, or CRITICAL),
        baseline_take, list of previous take summaries, and active discrepancy tags.
    """
    try:
        chronology = await database.get_scene_chronology(scene, character)
        if not chronology:
            return {
                "status": "new_scene",
                "message": f"No previous takes recorded for {character} in {scene}. This scene has no baseline yet.",
                "total_takes": 0,
                "drift_status": "STABLE",
            }

        from main import _build_scene_state
        return _build_scene_state(scene, character, chronology)
    except Exception as exc:
        logger.exception("get_scene_continuity_state failed")
        return {"error": str(exc)}


async def query_take_records(scene: str = "", character: str = "", limit: int = 10) -> list:
    """
    Search and retrieve past take checks or comparison records from the SQLite continuity database.
    Args:
        scene: Optional scene filter (e.g. 'EXT. ROOFTOP - NIGHT')
        character: Optional character filter (e.g. 'Alice')
        limit: Maximum number of records to return (default 10)
    Returns:
        List of recent take records with ID, kind, take number, risk level, match score, and created date.
    """
    try:
        records = await database.list_records(
            scene=scene.strip() if scene else None,
            character=character.strip() if character else None,
            limit=limit,
        )
        results = []
        for r in records:
            results.append(
                {
                    "id": r.get("id"),
                    "kind": r.get("kind"),
                    "scene": r.get("scene"),
                    "character": r.get("character"),
                    "take": r.get("take"),
                    "take_ref": r.get("take_ref"),
                    "take_current": r.get("take_current"),
                    "risk_level": r.get("risk_level"),
                    "match_score": r.get("match_score"),
                    "created_at": r.get("created_at"),
                }
            )
        return results
    except Exception as exc:
        logger.exception("query_take_records failed")
        return [{"error": str(exc)}]


async def get_take_full_report(record_id: int) -> dict:
    """
    Fetch the full continuity report and photo details for a specific take or comparison record ID.
    Args:
        record_id: Unique database ID of the take check or comparison
    Returns:
        Complete record data including Gemini continuity report, photo preview URLs, and metadata.
    """
    try:
        rec = await database.get_record(record_id)
        if not rec:
            return {"error": f"Record with ID {record_id} not found."}
        return {
            "id": rec.get("id"),
            "kind": rec.get("kind"),
            "scene": rec.get("scene"),
            "character": rec.get("character"),
            "take": rec.get("take") or f"{rec.get('take_ref')} vs {rec.get('take_current')}",
            "risk_level": rec.get("risk_level"),
            "match_score": rec.get("match_score"),
            "report": rec.get("report"),
            "preview_ref_url": storage.url(rec.get("preview_ref")) if rec.get("preview_ref") else None,
            "preview_cur_url": storage.url(rec.get("preview_cur")) if rec.get("preview_cur") else None,
        }
    except Exception as exc:
        logger.exception("get_take_full_report failed")
        return {"error": str(exc)}


async def check_script_continuity(scene_heading: str, character: str = "") -> dict:
    """
    Cross-reference requirements from the shooting script or established baseline for a given scene and character.
    Args:
        scene_heading: Scene heading or title (e.g. 'EXT. ROOFTOP - NIGHT')
        character: Character name (e.g. 'Alice')
    Returns:
        Script continuity guidelines, wardrobe, makeup, SFX wounds, and props specifications.
    """
    try:
        records = await database.list_records(scene=scene_heading, character=character, limit=10)
        if not records:
            return {
                "scene": scene_heading,
                "character": character,
                "grounded": False,
                "guidelines": f"No shooting script or historical takes recorded for '{character}' in '{scene_heading}'. Operating with fresh baseline.",
            }

        grounded_recs = [r for r in records if r.get("script_grounded")]
        target_rec = grounded_recs[0] if grounded_recs else records[0]
        report_text = target_rec.get("report", "")

        # Extract structured guidelines from the actual recorded report
        guidelines_parts = []
        makeup_match = re.search(r"(?:1\.\s*\*\*Makeup[^*]*\*\*|Makeup & Hair:?)\s*([^\n\r]+(?:\n[^\n\r#2-4]+)?)", report_text, re.IGNORECASE)
        wardrobe_match = re.search(r"(?:2\.\s*\*\*Wardrobe[^*]*\*\*|Wardrobe:?)\s*([^\n\r]+(?:\n[^\n\r#134]+)?)", report_text, re.IGNORECASE)
        props_match = re.search(r"(?:3\.\s*\*\*Props[^*]*\*\*|Props:?)\s*([^\n\r]+(?:\n[^\n\r#124]+)?)", report_text, re.IGNORECASE)

        if makeup_match:
            guidelines_parts.append(f"Makeup/Hair: {makeup_match.group(1).strip()[:180]}")
        if wardrobe_match:
            guidelines_parts.append(f"Wardrobe: {wardrobe_match.group(1).strip()[:180]}")
        if props_match and "no differences" not in props_match.group(1).lower() and "no prop" not in props_match.group(1).lower():
            guidelines_parts.append(f"Props: {props_match.group(1).strip()[:180]}")

        if guidelines_parts:
            guidelines_summary = "; ".join(guidelines_parts)
        else:
            cleaned_lines = [l.strip() for l in report_text.splitlines() if l.strip() and not l.startswith("#")]
            guidelines_summary = " ".join(cleaned_lines[:3])[:250] if cleaned_lines else "Established visual baseline in production log."

        source_label = "Shooting script grounded" if grounded_recs else "Established visual baseline"
        return {
            "scene": scene_heading,
            "character": character,
            "grounded": bool(grounded_recs),
            "guidelines": f"{source_label} (Take {target_rec.get('take', '1')}): {guidelines_summary}",
            "reference_record_id": target_rec.get("id"),
            "take_reference": target_rec.get("take"),
        }
    except Exception as exc:
        logger.exception("check_script_continuity failed")
        return {"error": str(exc)}


async def compare_recorded_takes(scene: str, take_ref: str, take_current: str, character: str = "") -> dict:
    """
    Compare two specific recorded takes for a scene and character to determine differential continuity drift.
    Args:
        scene: Scene heading (e.g. 'EXT. ROOFTOP - NIGHT')
        take_ref: Reference take number (e.g. '1')
        take_current: Current take number (e.g. '2')
        character: Character name (e.g. 'Alice')
    Returns:
        Comparison summary, match score (GOOD / FAIR / POOR), risk level, and discrepancies.
    """
    try:
        chronology = await database.get_scene_chronology(scene, character)
        comparisons = [
            r for r in chronology
            if r.get("kind") == "comparison"
            and str(r.get("take_ref")) == str(take_ref)
            and str(r.get("take_current")) == str(take_current)
        ]
        if comparisons:
            comp = comparisons[0]
            return {
                "found_existing_comparison": True,
                "record_id": comp.get("id"),
                "take_ref": take_ref,
                "take_current": take_current,
                "match_score": comp.get("match_score"),
                "risk_level": comp.get("risk_level"),
                "differences_summary": comp.get("report", "")[:350],
            }
        return {
            "found_existing_comparison": False,
            "message": f"No direct comparison recorded between Take {take_ref} and Take {take_current} in database.",
        }
    except Exception as exc:
        return {"error": str(exc)}


async def emit_crew_alert(
    scene: str,
    take: str,
    character: str,
    risk_level: str,
    alert_message: str,
    department: str = "makeup",
) -> dict:
    """
    Emit a real-time continuity alert to the film crew via Confluent Kafka and on-set tablet broadcast (SSE).
    Args:
        scene: Scene heading (e.g. 'EXT. ROOFTOP - NIGHT')
        take: Take number that caused the violation (e.g. '2')
        character: Character name (e.g. 'Alice')
        risk_level: 'LOW', 'MEDIUM', or 'HIGH'
        alert_message: Concise description of the continuity violation or drift
        department: Responsible crew department ('makeup', 'hair', 'wardrobe', 'props')
    Returns:
        Delivery status confirmation.
    """
    payload = {
        "event": "autonomous_agent_alert",
        "timestamp": time.time(),
        "scene": scene,
        "take": str(take),
        "character": character,
        "risk_level": risk_level.upper(),
        "department": department,
        "message": alert_message,
        "source": "Flawless Take Agent Copilot",
    }
    try:
        if _publish_event_fn:
            _publish_event_fn(payload)
            logger.info("Agent alert emitted: %s", alert_message)
            return {
                "status": "delivered",
                "target_topic": "flawless-take-events",
                "department": department,
                "risk_level": risk_level.upper(),
                "broadcast_via_sse": True,
                "alert_message": alert_message,
            }
        return {"status": "error", "message": "Event publisher not registered."}
    except Exception as exc:
        logger.exception("emit_crew_alert failed")
        return {"status": "error", "error": str(exc)}


async def export_continuity_pdf(record_id: int) -> dict:
    """
    Trigger generation of an official Hollywood-standard Continuity Log PDF for a record.
    Args:
        record_id: Database ID of the take check or comparison
    Returns:
        Status and download URL for the PDF.
    """
    try:
        rec = await database.get_record(record_id)
        if not rec:
            return {"error": f"Record with ID {record_id} not found."}

        pdf_url = f"/api/history/{record_id}/pdf"
        return {
            "status": "ready",
            "record_id": record_id,
            "download_url": pdf_url,
            "scene": rec.get("scene"),
            "take": rec.get("take") or f"{rec.get('take_ref')}_vs_{rec.get('take_current')}",
        }
    except Exception as exc:
        return {"error": str(exc)}


async def generate_department_checklist(
    scene: str,
    character: str,
    discrepancies: str,
    next_take: str = "",
) -> dict:
    """
    Synthesize a list of identified continuity discrepancies into a structured,
    department-ready action checklist for makeup, wardrobe, hair, and props crews.
    Call this tool after identifying violations via get_scene_continuity_state or compare_recorded_takes.
    Args:
        scene: Scene heading (e.g. 'EXT. ROOFTOP - NIGHT')
        character: Character name (e.g. 'Alice')
        discrepancies: Plain-text description of all identified continuity violations,
                       one violation per line or comma-separated.
        next_take: The upcoming take number these fixes must be applied before (e.g. '3')
    Returns:
        Structured JSON checklist keyed by department with priority and timestamp.
    """
    try:
        from google import genai
        from google.genai import types as gtypes

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"error": "GEMINI_API_KEY not set"}

        client = genai.Client(api_key=api_key)

        synthesis_prompt = f"""\
You are a Hollywood script supervisor. Based on the following continuity discrepancies found on set, \
create a structured action checklist for each crew department.

Scene: {scene}
Character: {character}
Before Take: {next_take or 'next take'}

Identified Discrepancies:
{discrepancies}

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):
{{
  "next_take": "{next_take or 'next'}",
  "scene": "{scene}",
  "character": "{character}",
  "priority": "HIGH" | "MEDIUM" | "LOW",
  "departments": {{
    "makeup": ["<specific actionable fix>", ...],
    "wardrobe": ["<specific actionable fix>", ...],
    "hair": ["<specific actionable fix>", ...],
    "props": ["<specific actionable fix>", ...]
  }},
  "generated_at": {int(time.time())}
}}

Be extremely specific and concise. Each fix must be a single, executable instruction for the crew member.
If a department has no issues, use an empty array [].
"""

        resp = await client.aio.models.generate_content(
            model="gemini-3.8-flash",
            contents=synthesis_prompt,
            config=gtypes.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                safety_settings=safety_config.get_safety_settings(),
            ),
        )

        raw = (resp.text or "").strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        checklist = json.loads(raw)
        checklist["status"] = "generated"
        logger.info("Department checklist generated for %s / %s", scene, character)
        return checklist

    except json.JSONDecodeError as exc:
        logger.exception("Checklist JSON parse failed")
        return {"error": f"Failed to parse checklist JSON: {exc}", "raw": raw if 'raw' in dir() else ""}
    except Exception as exc:
        logger.exception("generate_department_checklist failed")
        return {"error": str(exc)}
