from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(title="Flawless Take API")

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Check-take — draft route
# ---------------------------------------------------------------------------
@app.post("/api/check-take")
async def check_take(
    scene: str = Form(...),
    take: str = Form(...),
    character: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    """
    Accepts a scene description, take number, character name, and an image
    file. Returns a stub response — Gemini + Kafka integration to follow.
    """
    image_bytes = await file.read()

    # TODO: send image_bytes + scene/take/character to Gemini for analysis
    # TODO: publish result event to Confluent Kafka topic

    return {
        "scene": scene,
        "take": take,
        "character": character,
        "filename": file.filename,
        "size_bytes": len(image_bytes),
        "result": "stub — Gemini analysis not yet implemented",
    }
