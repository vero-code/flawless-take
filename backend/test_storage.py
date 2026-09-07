"""
test_storage.py - Unit tests for Storage Layer
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import storage


def test_mime_extension_resolution():
    print("[1/3] Testing MIME Extension Resolution...")
    assert storage._ext_from_mime("image/jpeg") == ".jpg"
    assert storage._ext_from_mime("image/png") == ".png"
    assert storage._ext_from_mime("image/webp") == ".webp"
    assert storage._ext_from_mime("unknown/type") == ".jpg"
    print("  OK: MIME extensions resolved.")


def test_url_generation():
    print("[2/3] Testing URL Generation...")
    url = storage.url("abc-123.jpg")
    assert url == "/uploads/abc-123.jpg"
    print("  OK: Local URL format verified.")


async def test_async_save():
    print("[3/3] Testing Local Image Persistence...")
    dummy_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    filename = await storage.save(dummy_bytes, "image/png")
    assert filename.endswith(".png")
    file_path = storage.UPLOADS_DIR / filename
    assert file_path.exists(), f"Uploaded file {file_path} not found on disk"
    assert file_path.read_bytes() == dummy_bytes
    # Cleanup test artifact
    file_path.unlink(missing_ok=True)
    print("  OK: Image saved to uploads and cleaned up.")


if __name__ == "__main__":
    print("=== Flawless Take Storage Unit Tests ===\n")
    try:
        test_mime_extension_resolution()
        test_url_generation()
        asyncio.run(test_async_save())
        print("\n=== ALL STORAGE TESTS PASSED ===")
    except Exception as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        sys.exit(1)
