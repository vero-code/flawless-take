import urllib.request
import json
import sys

def run_tests():
    print("--- STEP 1: Verify Frontend Dev Server ---")
    try:
        resp = urllib.request.urlopen("http://localhost:5173", timeout=5)
        html = resp.read().decode("utf-8")
        print("Frontend status:", resp.status, "HTML length:", len(html))
        assert "root" in html
        print("[PASS] Frontend is serving Vite app")
    except Exception as e:
        print("[FAIL] Frontend test failed:", e)
        return False

    print("\n--- STEP 2: Verify Autonomous Agent Tool Invocation (Multi-step) ---")
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/agent/query",
            data=json.dumps({
                "prompt": "Check scene continuity for Alice in EXT. ROOFTOP - NIGHT. If there is a discrepancy, emit a crew alert to makeup.",
                "scene": "EXT. ROOFTOP - NIGHT",
                "character": "Alice"
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=35)
        data = json.loads(resp.read().decode("utf-8"))
        print("Agent actions taken:", data.get("actions_taken"))
        print("Tool calls count:", len(data.get("tool_calls", [])))
        for tc in data.get("tool_calls", []):
            print(f"  * Called: {tc.get('tool')}")
            print(f"    Args: {tc.get('args')}")
            print(f"    Result status: {type(tc.get('result'))}")
        print("Agent reply preview:", str(data.get("response", ""))[:200])
        assert len(data.get("tool_calls", [])) > 0
        print("[PASS] Multi-step agent tool execution verified")
    except Exception as e:
        print("[FAIL] Agent query test failed:", e)
        return False

    print("\n--- STEP 3: Verify Agent PDF Tool Calling ---")
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/agent/query",
            data=json.dumps({
                "prompt": "Export continuity PDF log for record ID 5.",
                "scene": "EXT. ROOFTOP - NIGHT"
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode("utf-8"))
        print("PDF Tool actions taken:", data.get("actions_taken"))
        tool_results = [tc for tc in data.get("tool_calls", []) if tc.get("tool") == "export_continuity_pdf"]
        assert len(tool_results) > 0
        pdf_res = tool_results[0].get("result", {})
        print("PDF Result:", pdf_res)
        assert pdf_res.get("status") == "generated"
        print("[PASS] Agent PDF generation verified")
    except Exception as e:
        print("[FAIL] Agent PDF test failed:", e)
        return False

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
