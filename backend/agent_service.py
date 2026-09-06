"""
agent_service.py - Autonomous AI Continuity Supervisor Service

Coordinates the Gemini tool-calling agent using google-genai SDK,
orchestrating autonomous multi-step reasoning, tool execution, and trace logging.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from google import genai
from google.genai import types

import agent_tools

logger = logging.getLogger(__name__)

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

MODEL = "gemini-3.8-flash"


def _get_tools_list():
    return [
        agent_tools.get_scene_continuity_state,
        agent_tools.query_take_records,
        agent_tools.get_take_full_report,
        agent_tools.check_script_continuity,
        agent_tools.compare_recorded_takes,
        agent_tools.emit_crew_alert,
        agent_tools.export_continuity_pdf,
        agent_tools.generate_department_checklist,
    ]


async def run_agent_query(
    prompt: str,
    scene: str = "",
    character: str = "",
    script_context: str = "",
) -> dict[str, Any]:
    """
    Executes a user command through the autonomous tool-calling Gemini agent.
    Returns:
        {
            "response": str,
            "tool_calls": list[dict],
            "actions_taken": list[str],
            "model": str
        }
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)

    # Build context-aware prompt if scene/character are active
    context_prefix = ""
    if scene or character:
        context_prefix = f"[Active Context: Scene: '{scene or 'Not specified'}', Character: '{character or 'Not specified'}']\n"
    if script_context:
        context_prefix += f"[Script Notes Reference:\n{script_context[:300]}]\n"

    full_prompt = f"{context_prefix}{prompt}".strip()

    chat = client.aio.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=AGENT_SYSTEM_INSTRUCTION,
            tools=_get_tools_list(),
            temperature=0.4,
        ),
    )

    try:
        resp = await chat.send_message(full_prompt)
        reply_text = resp.text or ""
    except Exception as exc:
        logger.exception("Agent execution failed")
        raise RuntimeError(f"Agent reasoning failed: {exc}") from exc

    # Extract tool execution trace from chat history
    tool_calls: list[dict[str, Any]] = []
    actions_taken: list[str] = []

    history = chat.get_history()
    # History contains turns: user prompt, model tool call, user tool response, model final reply
    pending_calls = {}
    for msg in history:
        for part in msg.parts:
            if getattr(part, "function_call", None):
                fc = part.function_call
                call_id = fc.name
                call_info = {
                    "tool": fc.name,
                    "args": dict(fc.args) if fc.args else {},
                    "result": None,
                }
                pending_calls[call_id] = call_info
                tool_calls.append(call_info)
                if fc.name not in actions_taken:
                    actions_taken.append(fc.name)

            if getattr(part, "function_response", None):
                fr = part.function_response
                call_id = fr.name
                if call_id in pending_calls:
                    resp_val = fr.response
                    if isinstance(resp_val, dict) and "result" in resp_val:
                        pending_calls[call_id]["result"] = resp_val["result"]
                    else:
                        pending_calls[call_id]["result"] = resp_val

    return {
        "response": reply_text,
        "tool_calls": tool_calls,
        "actions_taken": actions_taken,
        "model": MODEL,
    }
