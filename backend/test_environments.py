"""
test_environments.py - Verification for Agent Builder, Environments & Webhook Fulfillment
"""
import json
import sys
from pathlib import Path

# Ensure backend directory is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

import environments


def test_environment_resolution():
    print("[1/3] Testing Serving Environment & Metadata...")
    env = environments.get_current_environment()
    assert env in ("development", "staging", "production"), f"Invalid environment: {env}"

    meta = environments.get_environment_metadata()
    assert meta["active_environment"] == env
    assert meta["current_version"] == "1.0.0"
    assert len(meta["immutable_snapshots"]) >= 2
    assert "agent_builder" in meta
    print(f"  OK: Active Environment: '{env}', Version: {meta['current_version']}, Snapshots: {len(meta['immutable_snapshots'])}")


def test_agent_builder_webhook():
    print("[2/3] Testing Agent Builder / Dialogflow CX Webhook Protocol...")
    # 1. Test check_continuity tag
    req1 = {
        "fulfillmentInfo": {"tag": "check_continuity"},
        "sessionInfo": {
            "parameters": {"scene": "Scene 14A", "character": "Detective Miller"}
        }
    }
    resp1 = environments.handle_agent_builder_webhook(req1)
    assert "fulfillmentResponse" in resp1
    assert len(resp1["fulfillmentResponse"]["messages"]) > 0
    reply1 = resp1["fulfillmentResponse"]["messages"][0]["text"]["text"][0]
    assert "Scene 14A" in reply1
    assert "Detective Miller" in reply1
    print("  OK: Webhook check_continuity tag handled successfully.")

    # 2. Test generate_checklist tag
    req2 = {
        "fulfillmentInfo": {"tag": "generate_checklist"},
        "sessionInfo": {
            "parameters": {"scene": "Scene 14A"}
        }
    }
    resp2 = environments.handle_agent_builder_webhook(req2)
    reply2 = resp2["fulfillmentResponse"]["messages"][0]["text"]["text"][0]
    assert "Department Action Checklist" in reply2
    print("  OK: Webhook generate_checklist tag handled successfully.")


def test_agent_builder_spec():
    print("[3/3] Testing Agent Builder Declarative Spec...")
    spec_path = Path(__file__).parent / "agent_builder_spec.json"
    assert spec_path.exists(), "agent_builder_spec.json not found"
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    assert spec["name"] == "flawless-take-agent-builder-spec"
    assert len(spec["environments"]) == 3
    assert len(spec["tools"]) == 3
    print(f"  OK: Spec validated. {len(spec['environments'])} environments, {len(spec['tools'])} tools.")


if __name__ == "__main__":
    print("=== Flawless Take Agent Builder & Environments Verification ===\n")
    try:
        test_environment_resolution()
        test_agent_builder_webhook()
        test_agent_builder_spec()
        print("\n=== ALL ENVIRONMENT & AGENT BUILDER TESTS PASSED ===")
    except Exception as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        sys.exit(1)
