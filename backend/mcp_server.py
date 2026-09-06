"""
mcp_server.py - Studio MCP Server for Flawless Take

Exposes all 8 Flawless Take continuity tools via the Model Context Protocol (MCP),
allowing studio editing systems, Claude Desktop, Cursor, and custom agents to query
on-set continuity data without custom API integrations.

Transports:
  - SSE (HTTP):  mounted at /mcp by main.py  ->  http://localhost:8000/mcp/sse
  - stdio:       python mcp_server.py         ->  for Claude Desktop local integration
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure siblings (agent_tools, database, storage) are importable when run standalone
sys.path.insert(0, str(Path(__file__).parent))

from fastmcp import FastMCP

import agent_tools

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="Flawless Take Studio MCP",
    instructions=(
        "You are connected to Flawless Take — an on-set AI continuity supervisor "
        "for film & television productions. Use the provided tools to query scene "
        "continuity state, take history, script requirements, crew alerts, and "
        "department action checklists from the production database."
    ),
)

# ---------------------------------------------------------------------------
# Tool 1: Scene Continuity State
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_scene_continuity_state(scene: str, character: str) -> dict:
    """
    Get accumulated continuity memory, drift status (STABLE/DRIFTING/CRITICAL),
    baseline take, and historical take summaries for a scene and character.
    """
    return await agent_tools.get_scene_continuity_state(scene=scene, character=character)


# ---------------------------------------------------------------------------
# Tool 2: Query Take Records
# ---------------------------------------------------------------------------
@mcp.tool()
async def query_take_records(scene: str = "", character: str = "", limit: int = 10) -> list:
    """
    Search and retrieve past take check or comparison records from the SQLite
    continuity database. Filter by scene, character, or retrieve most recent.
    """
    return await agent_tools.query_take_records(scene=scene, character=character, limit=limit)


# ---------------------------------------------------------------------------
# Tool 3: Get Full Take Report
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_take_full_report(record_id: int) -> dict:
    """
    Fetch the complete Gemini continuity analysis report, photo preview URLs,
    risk level, and metadata for a specific take check or comparison record ID.
    """
    return await agent_tools.get_take_full_report(record_id=record_id)


# ---------------------------------------------------------------------------
# Tool 4: Check Script Continuity
# ---------------------------------------------------------------------------
@mcp.tool()
async def check_script_continuity(scene_heading: str, character: str = "") -> dict:
    """
    Cross-reference requirements from the shooting script for a given scene
    and character: wardrobe specs, SFX wounds, makeup notes, and props.
    """
    return await agent_tools.check_script_continuity(
        scene_heading=scene_heading, character=character
    )


# ---------------------------------------------------------------------------
# Tool 5: Compare Recorded Takes
# ---------------------------------------------------------------------------
@mcp.tool()
async def compare_recorded_takes(
    scene: str, take_ref: str, take_current: str, character: str = ""
) -> dict:
    """
    Retrieve and compare two specific recorded takes for a scene and character.
    Returns match score (GOOD/FAIR/POOR), risk level, and discrepancy summary.
    """
    return await agent_tools.compare_recorded_takes(
        scene=scene, take_ref=take_ref, take_current=take_current, character=character
    )


# ---------------------------------------------------------------------------
# Tool 6: Emit Crew Alert
# ---------------------------------------------------------------------------
@mcp.tool()
async def emit_crew_alert(
    scene: str,
    take: str,
    character: str,
    risk_level: str,
    alert_message: str,
    department: str = "makeup",
) -> dict:
    """
    Emit a real-time continuity alert to the film crew via Confluent Kafka
    and on-set tablet broadcast (SSE). Use for HIGH or MEDIUM violations.
    risk_level must be 'LOW', 'MEDIUM', or 'HIGH'.
    department must be 'makeup', 'hair', 'wardrobe', or 'props'.
    """
    return await agent_tools.emit_crew_alert(
        scene=scene,
        take=take,
        character=character,
        risk_level=risk_level,
        alert_message=alert_message,
        department=department,
    )


# ---------------------------------------------------------------------------
# Tool 7: Export Continuity PDF
# ---------------------------------------------------------------------------
@mcp.tool()
async def export_continuity_pdf(record_id: int) -> dict:
    """
    Trigger generation of a Hollywood-standard Continuity Log PDF for a record
    and return the download URL. Record must exist in the database.
    """
    return await agent_tools.export_continuity_pdf(record_id=record_id)


# ---------------------------------------------------------------------------
# Tool 8: Generate Department Checklist
# ---------------------------------------------------------------------------
@mcp.tool()
async def generate_department_checklist(
    scene: str,
    character: str,
    discrepancies: str,
    next_take: str = "",
) -> dict:
    """
    Synthesize identified continuity violations into a structured,
    department-ready action checklist (makeup, wardrobe, hair, props) for the
    crew to execute before the next take. Returns JSON keyed by department.
    """
    return await agent_tools.generate_department_checklist(
        scene=scene,
        character=character,
        discrepancies=discrepancies,
        next_take=next_take,
    )


# ---------------------------------------------------------------------------
# ASGI app for FastAPI mounting (SSE transport)
# ---------------------------------------------------------------------------
mcp_app = mcp.http_app(path="/")

# Tool names for the /api/mcp-info endpoint
MCP_TOOL_NAMES = [
    "get_scene_continuity_state",
    "query_take_records",
    "get_take_full_report",
    "check_script_continuity",
    "compare_recorded_takes",
    "emit_crew_alert",
    "export_continuity_pdf",
    "generate_department_checklist",
]

# ---------------------------------------------------------------------------
# stdio entry point for Claude Desktop local integration
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
