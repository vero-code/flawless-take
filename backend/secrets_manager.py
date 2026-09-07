"""
secrets_manager.py - Studio Secrets Manager for Google Cloud Secret Manager

Provides secure, production-grade credential resolution for film studio assets.
Dynamically resolves sensitive keys (Gemini API, Confluent Kafka) from
Google Cloud Secret Manager in cloud environments, with transparent fallback
to local .env for on-set offline workstations and development laptops.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("flawless_take.secrets")

# List of critical film studio secrets managed by Flawless Take
STUDIO_SECRET_KEYS = [
    "GEMINI_API_KEY",
    "CONFLUENT_BOOTSTRAP_SERVERS",
    "CONFLUENT_API_KEY",
    "CONFLUENT_API_SECRET",
    "CONFLUENT_TOPIC",
]

_secret_manager_client = None
_gcp_project_id: Optional[str] = None


def _init_client():
    global _secret_manager_client, _gcp_project_id
    if _secret_manager_client is not None:
        return _secret_manager_client

    _gcp_project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    use_sm = os.getenv("USE_SECRET_MANAGER", "false").lower() in ("true", "1", "yes")

    if use_sm or _gcp_project_id:
        try:
            from google.cloud import secretmanager
            _secret_manager_client = secretmanager.SecretManagerServiceClient()
            logger.info("Initialized Google Cloud Secret Manager client for project: %s", _gcp_project_id)
        except ImportError:
            logger.warning(
                "google-cloud-secret-manager is not installed. Falling back to local environment."
            )
            _secret_manager_client = None
        except Exception as exc:
            logger.warning(
                "Failed to initialize Secret Manager client (%s). Falling back to local environment.",
                exc,
            )
            _secret_manager_client = None

    return _secret_manager_client


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Fetches a secret. First attempts Google Cloud Secret Manager (if configured),
    then falls back to os.environ / .env.
    """
    client = _init_client()
    project = _gcp_project_id or os.getenv("GOOGLE_CLOUD_PROJECT")

    if client and project:
        # Secret Manager naming: hyphens instead of underscores (e.g. GEMINI-API-KEY or gemini-api-key)
        secret_aliases = [
            key,
            key.replace("_", "-"),
            key.lower().replace("_", "-"),
        ]
        for alias in secret_aliases:
            name = f"projects/{project}/secrets/{alias}/versions/latest"
            try:
                response = client.access_secret_version(request={"name": name})
                secret_val = response.payload.data.decode("UTF-8").strip()
                if secret_val:
                    logger.debug("Successfully resolved secret '%s' from Google Cloud Secret Manager.", key)
                    return secret_val
            except Exception:
                continue

    # Local fallback
    val = os.getenv(key)
    return val if val is not None else default


def load_studio_secrets(keys: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Resolves and populates all studio secrets into os.environ.
    Ensures third-party libraries (google-genai, confluent_kafka) receive keys seamlessly.
    """
    target_keys = keys or STUDIO_SECRET_KEYS
    loaded = {}
    for k in target_keys:
        secret_val = get_secret(k)
        if secret_val:
            os.environ[k] = secret_val
            loaded[k] = secret_val

    logger.info("Loaded %d studio secret(s) into active environment.", len(loaded))
    return loaded


def mask_secret(value: Optional[str]) -> str:
    """Masks secret values for audit display: 'AIzaS...4xQ' or 'Not configured'."""
    if not value:
        return "Not configured"
    val = str(value).strip()
    if len(val) <= 8:
        return "****"
    return f"{val[:4]}...{val[-4:]}"


def get_secrets_status() -> Dict[str, Any]:
    """
    Provides safe, non-leaking status of all studio secrets for security audits.
    """
    client = _init_client()
    project = _gcp_project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
    using_sm = client is not None and bool(project)

    status_entries = []
    for k in STUDIO_SECRET_KEYS:
        val = os.getenv(k)
        is_configured = bool(val)
        status_entries.append({
            "key": k,
            "configured": is_configured,
            "masked_preview": mask_secret(val),
            "source": "Google Cloud Secret Manager" if using_sm else "Local Environment (.env)",
        })

    return {
        "status": "secure",
        "provider": "Google Cloud Secret Manager" if using_sm else "Local Environment (.env)",
        "gcp_project": project or "None (Local)",
        "secrets_count": len([s for s in status_entries if s["configured"]]),
        "secrets": status_entries,
    }
