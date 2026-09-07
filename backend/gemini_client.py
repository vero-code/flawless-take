"""
gemini_client.py - Centralised Gemini GenAI Client Singleton

Single source of truth for:
- DEFAULT_MODEL: active Gemini model name (overridable via GEMINI_MODEL env var)
- get_genai_client(): cached genai.Client for API-key or Vertex AI ADC auth

Import DEFAULT_MODEL wherever "gemini-3.8-flash" was previously hardcoded.
Import get_genai_client() instead of constructing genai.Client() inline.
"""
from __future__ import annotations

import os

from google import genai

# ---------------------------------------------------------------------------
# Default model — single source of truth across the whole backend
# ---------------------------------------------------------------------------
DEFAULT_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# ---------------------------------------------------------------------------
# Shared singleton client (API-key auth)
# Used by vision.py endpoints and agent_tools.py
# NOTE: agent_engine/agent.py manages its own client because it also supports
#       Vertex AI Application Default Credentials (vertexai=True).
# ---------------------------------------------------------------------------
_client: genai.Client | None = None


def get_genai_client() -> genai.Client:
    """
    Return a module-level cached genai.Client authenticated via GEMINI_API_KEY.
    Raises RuntimeError if the key is not set.
    Call this from any module that needs a client for direct API-key auth.
    """
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to backend/.env and restart."
        )
    _client = genai.Client(api_key=api_key)
    return _client


def reset_client() -> None:
    """Reset the cached client (useful in tests)."""
    global _client
    _client = None
