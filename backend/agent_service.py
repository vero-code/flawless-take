"""
agent_service.py - Autonomous AI Continuity Supervisor Service

Coordinates the Gemini tool-calling agent using Google Cloud ADK / Vertex AI
ContinuitySupervisorAgent, managing execution and trace logging.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import gemini_client
from agent_engine.agent import ContinuitySupervisorAgent

logger = logging.getLogger(__name__)

# Cached agent instance
_agent_instance: Optional[ContinuitySupervisorAgent] = None


def get_agent() -> ContinuitySupervisorAgent:
    """Returns a singleton ContinuitySupervisorAgent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ContinuitySupervisorAgent(model=gemini_client.DEFAULT_MODEL)
        _agent_instance.set_up()
    return _agent_instance


async def run_agent_query(
    prompt: str,
    scene: str = "",
    character: str = "",
    script_context: str = "",
) -> dict[str, Any]:
    """
    Executes a user command through the autonomous tool-calling Gemini agent.
    Delegates directly to ContinuitySupervisorAgent to maintain a single source of truth.
    """
    agent = get_agent()
    return await agent.async_query(
        prompt=prompt,
        scene=scene,
        character=character,
        script_context=script_context,
    )
