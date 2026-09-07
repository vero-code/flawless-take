"""
safety_config.py - Google Gemini Safety Settings & Film Studio Guardrails

Configures official Google GenAI moderation filters (SafetySettings)
calibrated specifically for film and television on-set production.

Balancing:
  1. Zero tolerance for Hate Speech, Harassment, and Sexually Explicit content (BLOCK_LOW_AND_ABOVE).
  2. Calibrated protection for Dangerous Content (BLOCK_MEDIUM_AND_ABOVE) to ensure
     theatrical SFX makeup (prosthetic lacerations, fake stage blood, bullet hits)
     and prop stunt weapons are evaluated for continuity without false-positive blocks.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from google.genai import types

logger = logging.getLogger("flawless_take.safety")

# Film Studio Production Safety Calibration
FILM_SAFETY_SETTINGS: List[types.SafetySetting] = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
]


def get_safety_settings() -> List[types.SafetySetting]:
    """
    Returns the active Gemini SafetySettings for Flawless Take.
    """
    return FILM_SAFETY_SETTINGS


def get_safety_policy_metadata() -> Dict[str, Any]:
    """
    Returns a human-readable and machine-auditable description of the
    production safety filters for UI status badges and security audits.
    """
    return {
        "status": "active",
        "policy": "Hollywood Production Studio Standard",
        "moderation_engine": "Google Gemini Safety Filters",
        "rules": [
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_LOW_AND_ABOVE",
                "rationale": "Zero tolerance for hate speech in crew notes and scripts.",
            },
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_LOW_AND_ABOVE",
                "rationale": "Strict prevention of harassment or abusive on-set communications.",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_LOW_AND_ABOVE",
                "rationale": "Strict protection of talent and creative imagery against inappropriate content.",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                "rationale": (
                    "Calibrated for film productions: permits theatrical SFX props, "
                    "prosthetic wound makeup, and stage combat continuity while blocking "
                    "genuine dangerous or harmful instructions."
                ),
            },
        ],
        "guardrails": {
            "sfx_makeup_permitted": True,
            "theatrical_props_permitted": True,
            "prompt_injection_shield": True,
            "hallucination_prevention": "Tool-grounded responses only",
        },
    }


def validate_script_content_safety(content: str) -> tuple[bool, str]:
    """
    Pre-flight guardrail check on incoming script or prompt text.
    Returns (is_safe: bool, reason: str).
    """
    if not content:
        return True, "Empty content is safe"

    # Fast heuristic check for common malicious prompt injections targeting crew tools
    injection_patterns = [
        "ignore all previous instructions",
        "disregard system prompt",
        "bypass safety filter",
        "override safety settings",
    ]
    lower = content.lower()
    for pattern in injection_patterns:
        if pattern in lower:
            logger.warning("Safety guardrail triggered: prompt injection pattern '%s' detected.", pattern)
            return False, f"Prompt contains restricted directive: '{pattern}'"

    return True, "Passed safety validation"
