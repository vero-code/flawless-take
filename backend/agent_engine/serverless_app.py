"""
serverless_app.py - Google Cloud Serverless Agent Engine Runtime
Lightweight FastAPI container entrypoint for Google Cloud Run / Vertex AI Agent Engine.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure parent backend directory is on sys.path
_CURRENT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _CURRENT_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_engine.agent import ContinuitySupervisorAgent
import database

app = FastAPI(
    title="Flawless Take Agent Engine Runtime",
    description="Google Cloud ADK / Vertex AI Serverless Agent Engine for Film Continuity Supervision",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global singleton agent
_agent: Optional[ContinuitySupervisorAgent] = None


@app.on_event("startup")
async def startup_event():
    global _agent
    await database.init_db()
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    _agent = ContinuitySupervisorAgent(model=model)
    try:
        _agent.set_up()
    except Exception as e:
        # Warning only on startup in case env vars are supplied per-request
        print(f"[Agent Engine Warning] set_up deferred: {e}", file=sys.stderr)


class AgentQueryRequest(BaseModel):
    prompt: str = Field(..., description="User instruction or question for the continuity agent")
    scene: str = Field("", description="Active scene identifier")
    character: str = Field("", description="Active character identifier")
    script_context: str = Field("", description="Extracted script continuity notes")


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Cloud Run / Vertex AI liveness and readiness probe."""
    return {
        "status": "healthy",
        "service": "flawless-take-agent-engine",
        "framework": "Google Cloud ADK",
        "agent_ready": _agent is not None and _agent._is_setup,
    }


@app.get("/spec")
async def get_agent_spec() -> Dict[str, Any]:
    """Returns the official Google Cloud ADK manifest."""
    manifest_path = _CURRENT_DIR / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"error": "manifest.json not found"}


@app.post("/query")
async def execute_query(req: AgentQueryRequest) -> Dict[str, Any]:
    """
    Executes a query through the ADK Continuity Supervisor Agent.
    """
    global _agent
    if _agent is None or not _agent._is_setup:
        model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        _agent = ContinuitySupervisorAgent(model=model)
        try:
            _agent.set_up()
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize Agent Engine: {exc}",
            )

    try:
        result = await _agent.async_query(
            prompt=req.prompt,
            scene=req.scene,
            character=req.character,
            script_context=req.script_context,
        )
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent execution error: {exc}",
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
