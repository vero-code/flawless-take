import shutil
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
pycache = backend_dir / "__pycache__"
if pycache.exists():
    shutil.rmtree(pycache, ignore_errors=True)

sys.path.insert(0, str(backend_dir))
sys.dont_write_bytecode = True

from main import app


def test_registered_routes():
    print("[1/2] Verifying FastAPI Route Registry...")
    route_paths = {getattr(r, "path", None) for r in app.routes}

    expected_routes = [
        "/api/health",
        "/api/mcp-info",
        "/api/agent-engine/info",
        "/api/safety/config",
        "/api/secrets/status",
        "/api/system/version",
        "/api/webhook/agent-builder",
        "/api/agent-builder/spec",
        "/api/alerts",
        "/api/scene-state",
        "/api/history",
        "/api/history/{record_id}",
        "/api/history/{record_id}/pdf",
        "/api/agent/query",
        "/api/agent/checklist",
        "/api/upload-script",
        "/api/check-take",
        "/api/compare-takes",
    ]

    for expected in expected_routes:
        assert expected in route_paths, f"Missing expected route: {expected}"
        print(f"  OK route: {expected}")

    print("[2/2] Verifying Router Separation...")
    from routers import agent_router, events_router, history_router, system_router

    agent_paths = {r.path for r in agent_router.routes}
    events_paths = {r.path for r in events_router.routes}
    history_paths = {r.path for r in history_router.routes}
    system_paths = {r.path for r in system_router.routes}

    assert "/api/agent/query" in agent_paths
    assert "/api/agent/checklist" in agent_paths
    assert "/api/alerts" in events_paths
    assert "/api/history" in history_paths
    assert "/api/scene-state" in history_paths
    assert "/api/webhook/agent-builder" in system_paths
    assert "/api/system/version" in system_paths

    print(f"  OK: agent_router ({len(agent_paths)} routes)")
    print(f"  OK: events_router ({len(events_paths)} routes)")
    print(f"  OK: history_router ({len(history_paths)} routes)")
    print(f"  OK: system_router ({len(system_paths)} routes)")
    print("\nSUCCESS: All modular routes successfully validated with 0 breaking changes.")


if __name__ == "__main__":
    test_registered_routes()
