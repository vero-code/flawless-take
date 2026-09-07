"""
agent.py - Google Cloud ADK & Vertex AI Agent Engine Specification
Autonomous AI Continuity Supervisor for Film & Television Production.

Adheres to:
- Google Cloud Agent Development Kit (ADK) Runner standards
- Google Cloud Vertex AI Reasoning Engine interface (set_up, query)
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure parent backend directory is on sys.path for local module resolution
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_CURRENT_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from google import genai
from google.genai import types

import agent_tools
import safety_config

logger = logging.getLogger("agent_engine.continuity_agent")

AGENT_SYSTEM_INSTRUCTION = """\
You are Flawless Take's Autonomous AI Continuity Supervisor and On-Set Assistant for film & television productions.
You serve directors, script supervisors, and head of makeup/wardrobe departments on set.

You have access to 8 production tools:
1. `get_scene_continuity_state`: to check the scene's memory, baseline take, drift status (STABLE/DRIFTING/CRITICAL), and active discrepancy flags.
2. `query_take_records`: to list and filter past checks or comparisons in SQLite database.
3. `get_take_full_report`: to fetch the full continuity analysis report and photo preview URLs for a specific record.
4. `check_script_continuity`: to inspect shooting script guidelines for wardrobe, makeup, and props.
5. `compare_recorded_takes`: to inspect differences and match scores between two specific takes.
6. `emit_crew_alert`: to emit a real-time warning to the crew (via Confluent Kafka topic & SSE feed) if you find a high or medium continuity violation.
7. `export_continuity_pdf`: to create an official Hollywood-standard Continuity Log PDF.
8. `generate_department_checklist`: to synthesize identified violations into a structured, department-ready fix checklist (makeup, wardrobe, hair, props) that the crew can act on before the next take.

AGENT BEHAVIOR RULES:
- **Autonomous Tool Selection**: Do not guess or hallucinate historical facts. When asked about takes, scenes, or continuity status, call the appropriate tools to look up the ground truth.
- **Proactive Alerting**: When asked to investigate or take action on a scene where a serious or escalating continuity issue exists (e.g. SFX wound missing, unbuttoned collar, wrong prop), emit an alert to the responsible department (makeup, hair, or wardrobe).
- **Actionable Fix Generation**: After identifying continuity violations, automatically call `generate_department_checklist` to produce a concrete, department-keyed list of fix instructions (e.g. "Apply 4 cm prosthetic blood laceration to right cheek") for the crew to execute before the next take. Do not omit this step when violations are found.
- **Conciseness & Film-Grade Tone**: Keep your explanations clear, direct, and factual. Film sets move rapidly.
- **Language**: Strictly respond in English. All film continuity analysis, discrepancy reports, department recommendations, and tool status explanations must always be in clear, professional film-production English.
"""


class ContinuitySupervisorAgent:
    """
    Google Cloud Agent Development Kit (ADK) & Vertex AI Reasoning Engine compliant
    agent for autonomous on-set film continuity supervision.
    """

    def __init__(
        self,
        model: str = "gemini-3.8-flash",
        project: Optional[str] = None,
        location: str = "us-central1",
    ) -> None:
        self.model = model
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT", "")
        self.location = location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self._client: Optional[genai.Client] = None
        self._tools_list: List[Any] = []
        self._is_setup: bool = False

    def set_up(self) -> None:
        """
        Vertex AI Reasoning Engine / ADK lifecycle hook.
        Initializes GenAI / Vertex client and registers production tools.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            # Fall back to Vertex AI Application Default Credentials if project is provided
            if self.project:
                self._client = genai.Client(
                    vertexai=True,
                    project=self.project,
                    location=self.location,
                )
            else:
                raise ValueError(
                    "Either GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT must be configured "
                    "for ContinuitySupervisorAgent."
                )
        else:
            self._client = genai.Client(api_key=api_key)

        self._tools_list = [
            agent_tools.get_scene_continuity_state,
            agent_tools.query_take_records,
            agent_tools.get_take_full_report,
            agent_tools.check_script_continuity,
            agent_tools.compare_recorded_takes,
            agent_tools.emit_crew_alert,
            agent_tools.export_continuity_pdf,
            agent_tools.generate_department_checklist,
        ]
        self._is_setup = True
        logger.info(
            "ContinuitySupervisorAgent initialized with model %s and %d tools.",
            self.model,
            len(self._tools_list),
        )

    def get_tools(self) -> List[Any]:
        """Returns the registered tool callables."""
        if not self._is_setup:
            self.set_up()
        return self._tools_list

    async def async_query(
        self,
        prompt: str,
        scene: str = "",
        character: str = "",
        script_context: str = "",
    ) -> Dict[str, Any]:
        """
        Asynchronous execution of the agent reasoning loop.
        Returns:
            {
                "response": str,
                "tool_calls": list[dict],
                "actions_taken": list[str],
                "model": str,
                "status": "success"
            }
        """
        if not self._is_setup:
            self.set_up()

        # Guardrails: validate prompt against malicious injection directives
        is_safe, reason = safety_config.validate_script_content_safety(prompt)
        if not is_safe:
            raise ValueError(f"Safety guardrail triggered: {reason}")

        context_prefix = ""
        if scene or character:
            context_prefix = f"[Active Context: Scene: '{scene or 'Not specified'}', Character: '{character or 'Not specified'}']\n"
        if script_context:
            context_prefix += f"[Script Notes Reference:\n{script_context[:300]}]\n"

        full_prompt = f"{context_prefix}{prompt}".strip()

        chat = self._client.aio.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=AGENT_SYSTEM_INSTRUCTION,
                tools=self._tools_list,
                temperature=0.4,
                safety_settings=safety_config.get_safety_settings(),
            ),
        )

        try:
            resp = await chat.send_message(full_prompt)
            reply_text = resp.text or ""
        except Exception as exc:
            logger.exception("Agent query execution failed")
            raise RuntimeError(f"Agent reasoning failed: {exc}") from exc

        # Extract tool calls and responses from chat trajectory
        tool_calls: List[Dict[str, Any]] = []
        actions_taken: List[str] = []
        pending_calls: Dict[str, Dict[str, Any]] = {}

        history = chat.get_history()
        for msg in history:
            for part in msg.parts:
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    call_info = {
                        "tool": fc.name,
                        "args": dict(fc.args) if fc.args else {},
                        "result": None,
                    }
                    pending_calls[fc.name] = call_info
                    tool_calls.append(call_info)
                    if fc.name not in actions_taken:
                        actions_taken.append(fc.name)

                if getattr(part, "function_response", None):
                    fr = part.function_response
                    if fr.name in pending_calls:
                        resp_val = fr.response
                        if isinstance(resp_val, dict) and "result" in resp_val:
                            pending_calls[fr.name]["result"] = resp_val["result"]
                        else:
                            pending_calls[fr.name]["result"] = resp_val

        return {
            "status": "success",
            "response": reply_text,
            "tool_calls": tool_calls,
            "actions_taken": actions_taken,
            "model": self.model,
        }

    def query(
        self,
        prompt: str,
        scene: str = "",
        character: str = "",
        script_context: str = "",
    ) -> Dict[str, Any]:
        """
        Synchronous interface matching Vertex AI Reasoning Engine specification:
        `agent.query(prompt=...)`
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run,
                    self.async_query(
                        prompt=prompt,
                        scene=scene,
                        character=character,
                        script_context=script_context,
                    ),
                ).result()
        else:
            return loop.run_until_complete(
                self.async_query(
                    prompt=prompt,
                    scene=scene,
                    character=character,
                    script_context=script_context,
                )
            )
