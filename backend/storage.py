"""
File storage layer for image previews.

Current implementation: local disk under backend/uploads/.
To migrate to GCS: set GCS_BUCKET in .env — the save() function
will write to the bucket instead, and url() will return a signed URL.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

GCS_BUCKET = os.getenv("GCS_BUCKET")  # None → local disk


async def save(image_bytes: bytes, mime_type: str) -> str:
    """
    Persist image bytes and return a filename/key.
    Local: writes to backend/uploads/<uuid>.<ext>
    GCS (future): uploads to GCS_BUCKET, returns blob name.
    """
    ext = _ext_from_mime(mime_type)
    filename = f"{uuid.uuid4().hex}{ext}"

    if GCS_BUCKET:
        # Future: from google.cloud import storage
        # client = storage.Client()
        # bucket = client.bucket(GCS_BUCKET)
        # blob = bucket.blob(filename)
        # blob.upload_from_string(image_bytes, content_type=mime_type)
        raise NotImplementedError("GCS upload not yet wired — set GCS_BUCKET after adding google-cloud-storage")

    (UPLOADS_DIR / filename).write_bytes(image_bytes)
    return filename


def url(filename: str) -> str:
    """
    Return the URL to access the stored image.
    Local: relative path served by FastAPI static files.
    GCS (future): signed URL or public URL.
    """
    if GCS_BUCKET:
        return f"https://storage.googleapis.com/{GCS_BUCKET}/{filename}"
    return f"/uploads/{filename}"


def _ext_from_mime(mime: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime, ".jpg")
