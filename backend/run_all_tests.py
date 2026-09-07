"""
run_all_tests.py - Unified Master Test Runner for Flawless Take Studio
"""
import os
import subprocess
import sys
import time
from pathlib import Path

# Fix Windows cp1251/cp866 console encoding for Unicode/emojis
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).parent
ROOT_DIR = BACKEND_DIR.parent

# Ordered list of test suites to execute
TEST_SUITES = [
    ("Storage Layer", "backend/test_storage.py"),
    ("Database Repository", "backend/test_database.py"),
    ("Scene Memory & Drift", "backend/test_scene_memory.py"),
    ("Safety & Guardrails", "backend/test_safety.py"),
    ("Studio Secrets", "backend/test_secrets.py"),
    ("FastAPI Route Registry", "backend/test_routers.py"),
    ("Agent Builder & Envs", "backend/test_environments.py"),
    ("ADK Local Agent Engine", "backend/agent_engine/test_local.py"),
]


def run_suite(name: str, rel_path: str, python_exe: str) -> tuple[bool, float, str]:
    target = ROOT_DIR / rel_path
    if not target.exists():
        return False, 0.0, f"File not found: {target}"

    env = os.environ.copy()
    if "GEMINI_API_KEY" not in env or not env["GEMINI_API_KEY"]:
        env["GEMINI_API_KEY"] = "dummy_test_key"

    start_time = time.time()
    try:
        res = subprocess.run(
            [python_exe, str(target)],
            cwd=str(ROOT_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        elapsed = time.time() - start_time
        success = (res.returncode == 0)
        output = res.stdout if success else (res.stdout + "\n" + res.stderr)
        return success, elapsed, output
    except Exception as exc:
        elapsed = time.time() - start_time
        return False, elapsed, str(exc)


def main():
    # Detect appropriate Python binary (virtualenv preferred)
    venv_py = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    python_exe = str(venv_py) if venv_py.exists() else sys.executable

    print("======================================================================")
    print("           🎬 FLAWLESS TAKE — AUTOMATED TEST RUNNER 🎬                ")
    print(f" Python Interpreter: {python_exe}")
    print(f" Workspace Root:     {ROOT_DIR}")
    print("======================================================================\n")

    results = []
    total_start = time.time()

    for name, path in TEST_SUITES:
        print(f"▶ Running: {name:<25} ({path})...", end="", flush=True)
        success, elapsed, output = run_suite(name, path, python_exe)
        results.append((name, path, success, elapsed, output))
        if success:
            print(f" \033[92mPASS\033[0m ({elapsed:.2f}s)")
        else:
            print(f" \033[91mFAIL\033[0m ({elapsed:.2f}s)")
            # Print brief error info
            for line in output.strip().splitlines()[-4:]:
                print(f"    │ {line}")

    total_time = time.time() - total_start
    passed_count = sum(1 for r in results if r[2])
    total_count = len(results)

    print("\n======================================================================")
    print("                         TEST RUN SUMMARY                             ")
    print("======================================================================")
    for name, path, success, elapsed, _ in results:
        status_str = "✅ PASS" if success else "❌ FAIL"
        print(f" {status_str} │ {name:<26} │ {elapsed:>6.2f}s │ {path}")

    print("----------------------------------------------------------------------")
    print(f" Total Suites: {total_count}  |  Passed: {passed_count}  |  Failed: {total_count - passed_count}")
    print(f" Total Elapsed Time: {total_time:.2f}s")
    print("======================================================================")

    if passed_count != total_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
