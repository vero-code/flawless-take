"""
test_secrets.py - Verification for Studio Secrets & Google Cloud Secret Manager
"""
import os
import sys
from pathlib import Path

# Ensure backend directory is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

import secrets_manager


def test_mask_secret():
    print("[1/3] Testing Secret Masking Logic...")
    assert secrets_manager.mask_secret(None) == "Not configured"
    assert secrets_manager.mask_secret("") == "Not configured"
    assert secrets_manager.mask_secret("12345") == "****"
    masked = secrets_manager.mask_secret("AIzaSyD1234567890abcdefXYZ")
    assert masked.startswith("AIza")
    assert masked.endswith("tXYZ") or masked.endswith("XYZ")
    assert "..." in masked
    print(f"  OK: Masked format verified: {masked}")


def test_secret_resolution():
    print("[2/3] Testing Dynamic Secret Resolution & Fallback...")
    # Set a mock secret in environment
    os.environ["MOCK_TEST_SECRET"] = "super-secret-studio-key-1234"
    val = secrets_manager.get_secret("MOCK_TEST_SECRET")
    assert val == "super-secret-studio-key-1234"

    # Test default fallback
    fallback = secrets_manager.get_secret("NON_EXISTENT_KEY", default="default-studio-val")
    assert fallback == "default-studio-val"
    print("  OK: Local fallback resolution works seamlessly.")


def test_secrets_status():
    print("[3/3] Testing Studio Secrets Audit Status...")
    status = secrets_manager.get_secrets_status()
    assert status["status"] == "secure"
    assert "provider" in status
    assert "secrets" in status
    assert isinstance(status["secrets"], list)

    for entry in status["secrets"]:
        assert "key" in entry
        assert "configured" in entry
        assert "masked_preview" in entry
        assert "source" in entry
        # Verify raw secret is never present in masked preview
        raw_val = os.getenv(entry["key"])
        if raw_val and len(raw_val) > 8:
            assert raw_val != entry["masked_preview"], f"Secret leaked in masked preview: {entry['key']}"

    print(f"  OK: Secrets status verified. Provider: {status['provider']}, Secrets checked: {len(status['secrets'])}")


if __name__ == "__main__":
    print("=== Flawless Take Studio Secrets Verification ===\n")
    try:
        test_mask_secret()
        test_secret_resolution()
        test_secrets_status()
        print("\n=== ALL STUDIO SECRETS TESTS PASSED ===")
    except Exception as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        sys.exit(1)
