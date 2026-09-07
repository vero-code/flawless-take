"""
main.py - Flawless Take Application Entrypoint

Configures FastAPI, mounts FastMCP server, attaches modular APIRouters,
initializes lifecycle event publishers, and provides production SPA static hosting.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import agent_tools
import database
import event_bus
import mcp_server as _mcp_server
import secrets_manager
import storage
from routers import (
    agent_router,
    events_router,
    history_router,
    system_router,
    vision_router,
)

logger = logging.getLogger(__name__)

# Always load from backend/.env relative to this file, regardless of cwd
load_dotenv(Path(__file__).parent / ".env")
# Resolve Studio Secrets dynamically (Google Cloud Secret Manager or local .env)
secrets_manager.load_studio_secrets()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize SQLite database and wire event publisher."""
    await database.init_db()
    agent_tools.register_event_publisher(event_bus.publish_event)
    yield


app = FastAPI(title="Flawless Take API", lifespan=lifespan)

# Serve uploaded preview images
app.mount("/uploads", StaticFiles(directory=str(storage.UPLOADS_DIR)), name="uploads")

# ---------------------------------------------------------------------------
# CORS — allow Vite dev server & MCP inspector
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:8000",   # MCP Inspector / local studio clients
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Mount FastMCP server (SSE transport at /mcp)
# ---------------------------------------------------------------------------
app.mount("/mcp", _mcp_server.mcp_app)

# ---------------------------------------------------------------------------
# Include Modular API Routers (System, History, Agent, Events, Vision)
# ---------------------------------------------------------------------------
app.include_router(system_router)
app.include_router(history_router)
app.include_router(agent_router)
app.include_router(events_router)
app.include_router(vision_router)

# ---------------------------------------------------------------------------
# Production SPA Static Hosting (React build in dist/)
# ---------------------------------------------------------------------------
_dist_dir = Path(__file__).resolve().parent.parent / "dist"
if not _dist_dir.exists():
    _dist_dir = Path(__file__).resolve().parent / "dist"

if _dist_dir.exists():
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Do not intercept API, MCP, or Uploads routes
        if full_path.startswith("api/") or full_path.startswith("mcp") or full_path.startswith("uploads/"):
            raise HTTPException(status_code=404, detail="Not found")
        target_file = _dist_dir / full_path
        if full_path and target_file.is_file():
            return FileResponse(str(target_file))
        return FileResponse(str(_dist_dir / "index.html"))
