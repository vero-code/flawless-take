"""
scene_memory.py - Scene State & Historical Continuity Memory

Provides pure extraction, aggregation, and prompt formatting logic
for accumulated scene takes, continuity drift assessment, and timeline synthesis.
Decouples domain memory logic from main.py and agent_tools.py.
"""
from __future__ import annotations

import re
from typing import Any

import storage


def extract_risk(text: str) -> str:
    """Pull LOW / MEDIUM / HIGH out of the Gemini report, or return UNKNOWN."""
    m = re.search(r"\b(LOW|MEDIUM|HIGH)\b", text, re.IGNORECASE)
    return m.group(1).upper() if m else "UNKNOWN"


def extract_match_score(text: str) -> str:
    """Pull POOR / FAIR / GOOD out of the Gemini comparison report, or return UNKNOWN."""
    m = re.search(r"\b(POOR|FAIR|GOOD)\b", text, re.IGNORECASE)
    return m.group(1).upper() if m else "UNKNOWN"


def extract_take_summary(report: str, risk: str) -> str:
    """
    Extract a concise 1-sentence verdict from a report (max ~140 chars)
    to keep historical memory compact and avoid context bloat.
    """
    if not report:
        return f"Risk rated {risk}"

    def _clean(s: str) -> str:
        s = re.sub(r"^\s*[-*•\d.]+\s*", "", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        s = re.sub(r"\*([^*]+)\*", r"\1", s)
        s = re.sub(r"^(?:Rating|Risk|Score|Summary|Verdict)\s*[:—\-]\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+", " ", s).strip()
        if len(s) > 140:
            return s[:137] + "..."
        return s

    # 1. Look for explicit Summary line (standard in comparison reports)
    m = re.search(r"(?:^|\n)\s*[-*•]?\s*(?:Summary|Verdict):\s*([^\n\r]+)", report, re.IGNORECASE)
    if m:
        summary_text = _clean(m.group(1))
        if summary_text:
            return summary_text

    # 2. Look for Overall continuity risk explanation (standard in check reports)
    m = re.search(r"(?:4\.\s*\*\*Overall[^\n]*\*\*|Overall continuity risk:?)\s*([^\n\r]+)", report, re.IGNORECASE)
    if m:
        text = _clean(m.group(1))
        text = re.sub(r"^(?:LOW|MEDIUM|HIGH)\s*[-—:]\s*", "", text, flags=re.IGNORECASE).strip()
        if text:
            return text

    # 3. Fallback: first non-header, non-boilerplate descriptive line
    for line in report.splitlines():
        line_clean = line.strip()
        if (
            line_clean
            and not line_clean.startswith("#")
            and not line_clean.startswith("You are")
            and "No differences detected" not in line_clean
            and "CONTINUITY LOG" not in line_clean.upper()
            and len(line_clean) > 10
        ):
            clean_str = _clean(line_clean)
            if clean_str and len(clean_str) > 8:
                return clean_str

    return f"Risk rated {risk}"


def extract_key_issues(report: str) -> list[str]:
    """
    Extract up to 3 short phrases representing flagged discrepancies.
    """
    if not report:
        return []
    issues: list[str] = []
    for line in report.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        if (
            "No differences detected" in line_clean
            or line_clean.startswith("#")
            or "CONTINUITY LOG" in line_clean.upper()
            or "Carefully examine" in line_clean
            or "Format your response" in line_clean
            or "Match score:" in line_clean
            or "Continuity risk:" in line_clean
            or "Summary:" in line_clean
        ):
            continue
        m = re.search(r"^[-*•]\s*(.+)$", line_clean)
        if m:
            item = m.group(1).strip()
            item = re.sub(r"\*\*([^*]+)\*\*", r"\1", item)
            item = re.sub(r"\*([^*]+)\*", r"\1", item)
            item = re.sub(r"\s+", " ", item).strip()
            if 8 < len(item) < 90 and "difference" not in item.lower() and "scene:" not in item.lower():
                issues.append(item)
                if len(issues) >= 3:
                    break
    return issues


def format_scene_memory_prompt(
    scene: str,
    character: str,
    chronology: list[dict[str, Any]],
    max_recent: int = 4,
) -> str:
    """
    Builds an ultra-compact memory summary of prior takes for the Gemini prompt.
    Ensures context window is never bloated even with 20+ takes.
    """
    if not chronology:
        return ""

    total = len(chronology)
    first_rec = chronology[0]
    baseline_take = first_rec.get("take") or first_rec.get("take_ref") or "1"

    lines = [
        f"SCENE STATE MEMORY: Scene '{scene}', Character '{character}' has {total} previous recorded take(s).",
        f"Established Baseline: Take {baseline_take}.",
    ]

    if total > max_recent:
        older_count = total - max_recent
        lines.append(f"• Takes 1 to {older_count}: Prior baseline & intermediary takes recorded in continuity log.")
        recent_records = chronology[-max_recent:]
    else:
        recent_records = chronology

    lines.append("Recent take verdicts:")
    for r in recent_records:
        t_label = r.get("take") or f"{r.get('take_ref')}->{r.get('take_current')}"
        risk = (r.get("risk_level") or "UNKNOWN").upper()
        summary = extract_take_summary(r.get("report") or "", risk)
        lines.append(f"  • Take {t_label} [{risk}]: {summary}")

    active_issues = []
    for r in recent_records:
        for iss in extract_key_issues(r.get("report") or ""):
            if iss not in active_issues and len(active_issues) < 3:
                active_issues.append(iss)

    if active_issues:
        lines.append(f"Active continuity concerns from prior takes: {'; '.join(active_issues)}.")

    lines.append(
        "Agent Directive: Cross-reference against this memory. Flag if past issues are [RESOLVED], [PERSISTENT], or if [NEW DRIFT] appeared. Note trend under 'Scene Drift Trend'."
    )
    return "\n".join(lines)


def build_scene_state(
    scene: str,
    character: str,
    chronology: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Builds the structured scene state response for the API, agent tools, & frontend timeline.
    """
    if not chronology:
        return {
            "scene": scene,
            "character": character,
            "total_takes": 0,
            "drift_status": "STABLE",
            "baseline_take": None,
            "timeline": [],
            "known_discrepancies": [],
        }

    first_rec = chronology[0]
    baseline_take = first_rec.get("take") or first_rec.get("take_ref") or "1"

    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "UNKNOWN": 0}
    timeline = []
    known_issues = []

    for r in chronology:
        risk = (r.get("risk_level") or "UNKNOWN").upper()
        risk_counts[risk] = risk_counts.get(risk, 0) + 1

        take_label = r.get("take") or f"{r.get('take_ref')} vs {r.get('take_current')}"
        summary = extract_take_summary(r.get("report") or "", risk)
        issues = extract_key_issues(r.get("report") or "")
        for iss in issues:
            if iss not in known_issues and len(known_issues) < 5:
                known_issues.append(iss)

        timeline.append(
            {
                "id": r.get("id"),
                "kind": r.get("kind"),
                "take_label": take_label,
                "take": r.get("take"),
                "take_ref": r.get("take_ref"),
                "take_current": r.get("take_current"),
                "risk_level": risk,
                "match_score": r.get("match_score"),
                "created_at": r.get("created_at"),
                "summary": summary,
                "preview_ref_url": storage.url(r.get("preview_ref")) if r.get("preview_ref") else None,
                "preview_cur_url": storage.url(r.get("preview_cur")) if r.get("preview_cur") else None,
            }
        )

    if risk_counts["HIGH"] >= 2 or (risk_counts["HIGH"] >= 1 and risk_counts["MEDIUM"] >= 2):
        drift_status = "CRITICAL"
    elif risk_counts["HIGH"] >= 1 or risk_counts["MEDIUM"] >= 1:
        drift_status = "DRIFTING"
    else:
        drift_status = "STABLE"

    return {
        "scene": scene,
        "character": character,
        "total_takes": len(chronology),
        "drift_status": drift_status,
        "baseline_take": baseline_take,
        "timeline": timeline,
        "known_discrepancies": known_issues,
    }


# Backwards compatibility aliases
_extract_risk = extract_risk
_extract_match_score = extract_match_score
_extract_take_summary = extract_take_summary
_extract_key_issues = extract_key_issues
_format_scene_memory_prompt = format_scene_memory_prompt
_build_scene_state = build_scene_state
