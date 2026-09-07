"""
test_scene_memory.py - Unit tests for Scene Memory & Continuity Drift Logic
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import scene_memory


def test_extract_risk():
    print("[1/5] Testing Risk Extraction...")
    assert scene_memory.extract_risk("Overall continuity risk: HIGH") == "HIGH"
    assert scene_memory.extract_risk("Verdict: MEDIUM risk due to hair displacement") == "MEDIUM"
    assert scene_memory.extract_risk("Continuity looks clean. LOW risk.") == "LOW"
    assert scene_memory.extract_risk("No rating present here.") == "UNKNOWN"
    print("  OK: Risk extraction verified.")


def test_extract_match_score():
    print("[2/5] Testing Match Score Extraction...")
    assert scene_memory.extract_match_score("Match score: GOOD") == "GOOD"
    assert scene_memory.extract_match_score("Overall match is FAIR") == "FAIR"
    assert scene_memory.extract_match_score("POOR continuity match") == "POOR"
    assert scene_memory.extract_match_score("Indeterminate") == "UNKNOWN"
    print("  OK: Match score extraction verified.")


def test_extract_take_summary():
    print("[3/5] Testing Take Summary Extraction...")
    report1 = """
# CONTINUITY CHECK
- Summary: Tie knot shifted 2 inches lower on right collar.
- Continuity risk: MEDIUM
"""
    summary1 = scene_memory.extract_take_summary(report1, "MEDIUM")
    assert "Tie knot shifted" in summary1

    report2 = """
4. **Overall continuity risk**: HIGH - Blood splatter pattern on cheek does not match reference take.
"""
    summary2 = scene_memory.extract_take_summary(report2, "HIGH")
    assert "Blood splatter" in summary2
    print("  OK: Take summary extraction verified.")


def test_extract_key_issues():
    print("[4/5] Testing Key Issues Extraction...")
    report = """
# Breakdown
- Detective badge missing from left chest pocket.
- Wristwatch switched from silver to leather strap.
- Hair parted on opposite side.
- Additional minor shadow issue.
"""
    issues = scene_memory.extract_key_issues(report)
    assert len(issues) == 3
    assert "Detective badge" in issues[0]
    print(f"  OK: Key issues extracted ({len(issues)} items).")


def test_scene_memory_prompt_format():
    print("[5/5] Testing Scene Memory Prompt Synthesis...")
    chronology = [
        {"take": "1", "take_ref": "1", "risk": "LOW", "summary": "Clean baseline take"},
        {"take": "2", "take_ref": "1", "risk": "LOW", "summary": "Good match"},
        {"take": "3", "take_ref": "1", "risk": "MEDIUM", "summary": "Tie slightly loose"},
    ]
    prompt = scene_memory.format_scene_memory_prompt("Scene 14A", "Miller", chronology)
    assert "Scene 14A" in prompt
    assert "Miller" in prompt
    assert "3 previous recorded take(s)" in prompt
    assert "Take 1" in prompt
    print("  OK: Prompt formatted cleanly without context bloat.")


if __name__ == "__main__":
    print("=== Flawless Take Scene Memory Unit Tests ===\n")
    try:
        test_extract_risk()
        test_extract_match_score()
        test_extract_take_summary()
        test_extract_key_issues()
        test_scene_memory_prompt_format()
        print("\n=== ALL SCENE MEMORY TESTS PASSED ===")
    except Exception as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        sys.exit(1)
