"""
routers package - Modular FastAPI APIRouters for Flawless Take.
"""
from event_bus import router as events_router
from .agent import router as agent_router
from .history import router as history_router
from .system import router as system_router

__all__ = ["agent_router", "events_router", "history_router", "system_router"]

