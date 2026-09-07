"""
routers/system.py - System Metadata, Multi-Environment, Safety, Secrets & Webhook Endpoints
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request

import environments
import mcp_server as _mcp_server
import safety_config
import secrets_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System & Environments"])


@router.get("/api/health")
async def health() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}


@router.get("/api/mcp-info")
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


@router.get("/api/agent-engine/info")
async def agent_engine_info() -> dict:
    """Return Google Cloud ADK Agent Engine packaging status and specifications."""
    manifest_file = Path(__file__).resolve().parent.parent / "agent_engine" / "manifest.json"
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
        "cloud_run_service": "flawless-take-agent-engine",
        "manifest": manifest_data,
    }


@router.get("/api/safety/config")
async def safety_configuration() -> dict:
    """Return active Gemini safety threshold configuration and guardrails metadata."""
    return safety_config.get_safety_policy_metadata()


@router.get("/api/secrets/status")
async def secrets_status() -> dict:
    """Audit status of production credentials without exposing sensitive tokens."""
    return secrets_manager.get_secrets_status()


@router.get("/api/system/version")
async def system_version() -> dict:
    """Return active serving environment, immutable version history, and Agent Builder metadata."""
    return environments.get_environment_metadata()


@router.post("/api/webhook/agent-builder")
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


@router.get("/api/agent-builder/spec")
async def agent_builder_spec() -> dict:
    """Return the official Google Cloud Agent Builder / Dialogflow CX specification."""
    spec_path = Path(__file__).resolve().parent.parent / "agent_builder_spec.json"
    if spec_path.exists():
        with open(spec_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"error": "agent_builder_spec.json not found"}
