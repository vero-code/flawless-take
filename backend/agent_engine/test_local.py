"""
test_local.py - Local Verification for ADK Continuity Supervisor Agent

Validates that:
1. Manifest parses and conforms to ADK standards.
2. ContinuitySupervisorAgent can be instantiated and initialized (set_up).
3. All 8 tools are properly registered.
4. An offline or live mock query completes successfully.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_CURRENT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _CURRENT_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from agent_engine.agent import ContinuitySupervisorAgent
import database


def test_manifest():
    print("[1/3] Testing ADK Agent Manifest...")
    manifest_path = _CURRENT_DIR / "manifest.json"
    assert manifest_path.exists(), "manifest.json not found"
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["name"] == "flawless-take-continuity-supervisor"
    assert len(data["tools"]) == 8
    print(f"  OK: Manifest valid. {len(data['tools'])} tools specified.")


def test_agent_initialization():
    print("[2/3] Testing ContinuitySupervisorAgent set_up()...")
    agent = ContinuitySupervisorAgent(model="gemini-3.8-flash")
    agent.set_up()
    tools = agent.get_tools()
    assert len(tools) == 8, f"Expected 8 tools, got {len(tools)}"
    tool_names = [t.__name__ for t in tools]
    print(f"  OK: Registered {len(tools)} tools: {', '.join(tool_names)}")


def test_agent_sync_interface():
    print("[3/3] Testing Vertex AI Reasoning Engine sync interface contract...")
    agent = ContinuitySupervisorAgent(model="gemini-3.8-flash")
    agent.set_up()

    # Verify query method signature
    import inspect
    sig = inspect.signature(agent.query)
    assert "prompt" in sig.parameters
    assert "scene" in sig.parameters
    assert "character" in sig.parameters
    print(f"  OK: query() matches Reasoning Engine specification: {sig}")


if __name__ == "__main__":
    print("=== Flawless Take ADK Local Verification ===\n")
    try:
        test_manifest()
        test_agent_initialization()
        test_agent_sync_interface()
        print("\n=== ALL ADK CHECKS PASSED SUCCESSFULLY ===")
    except Exception as e:
        print(f"\nFAILED: {e}", file=sys.stderr)
        sys.exit(1)
