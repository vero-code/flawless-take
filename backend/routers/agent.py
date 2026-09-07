"""
routers/agent.py - Autonomous Continuity Agent and Department Checklist Endpoints
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import agent_service
import agent_tools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Autonomous Agent Copilot"])


class AgentQueryRequest(BaseModel):
    prompt: str
    scene: str = ""
    character: str = ""
    script_context: str = ""


@router.post("/query")
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


class ChecklistRequest(BaseModel):
    scene: str
    character: str
    discrepancies: str  # plain-text violations, one per line or comma-separated
    next_take: str = ""


@router.post("/checklist")
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
