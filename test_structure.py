"""Quick validation that the agent structure loads correctly."""
import asyncio
import sys


def test_tool_result_policy():
    from src.tools.policy import tool_stdout_indicates_error

    assert tool_stdout_indicates_error("", tool_name="WebFetch") is True
    assert tool_stdout_indicates_error("Error: timeout", tool_name="Bash") is True
    assert tool_stdout_indicates_error("Error: Fetch failed: x", tool_name="WebFetch") is True
    assert tool_stdout_indicates_error("No matches.", tool_name="Grep") is False
    assert tool_stdout_indicates_error('[{"url": "https://x"}]', tool_name="WebSearch") is False


def test_openai_native_tool_call_merge():
    from src.llm import _accumulate_openai_tool_call_deltas, _tool_call_slots_to_blocks

    slots: dict[int, dict[str, str]] = {}
    _accumulate_openai_tool_call_deltas(slots, [
        {"index": 0, "id": "call_1", "type": "function", "function": {"name": "Glob", "arguments": ""}},
    ])
    _accumulate_openai_tool_call_deltas(slots, [
        {"index": 0, "function": {"arguments": "{\"pattern\":"}},
    ])
    _accumulate_openai_tool_call_deltas(slots, [
        {"index": 0, "function": {"arguments": " \"*.py\"}"}},
    ])
    blocks = _tool_call_slots_to_blocks(slots)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "tool_use"
    assert blocks[0]["name"] == "Glob"
    assert blocks[0]["input"]["pattern"] == "*.py"


def test_imports():
    print("Testing imports...")
    from src.core.config import settings
    from src.core.models import SessionState, AgentMessage
    from src.tools import AVAILABLE_TOOLS, get_tool, get_tool_schemas
    from src.llm import UnifiedLLMClient
    from src.agent import Agent
    from src.server import app
    print(f"  Agent: {settings.agent_name} v{settings.version}")
    print(f"  Tools loaded: {len(AVAILABLE_TOOLS)}")
    for t in AVAILABLE_TOOLS:
        print(f"    - {t.name}")
    wf = get_tool("WebFetch")
    if wf is not None:
        assert get_tool("WebPage") is wf
    print("  All imports OK")


async def _run_tool_smoke_async():
    print("\nTesting tools...")
    from src.tools import bash_tool, glob_tool, grep_tool, read_tool

    # Test bash
    result = await bash_tool.run(command="echo 'hello from agent'")
    assert "hello from agent" in result, f"Bash failed: {result}"
    print("  Bash: OK")

    # Test glob
    result = await glob_tool.run(pattern="*.py")
    assert "main.py" in result, f"Glob failed: {result}"
    print("  Glob: OK")

    # Test grep
    result = await grep_tool.run(pattern="class Agent", include="*.py")
    assert "src/agent/run.py" in result, f"Grep failed: {result}"
    print("  Grep: OK")

    # Test read
    result = await read_tool.run(file_path="main.py")
    assert "uvicorn" in result, f"Read failed: {result}"
    print("  Read: OK")

    print("  All tools OK")


def test_tools():
    asyncio.run(_run_tool_smoke_async())


def test_server_routes():
    print("\nTesting server routes...")
    from fastapi.testclient import TestClient
    from src.server import app

    client = TestClient(app)

    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    print("  /health: OK")

    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("service")
    assert body.get("health") == "/health"
    print("  / (API root): OK")

    resp = client.get("/stream")
    assert resp.status_code == 405
    print("  GET /stream (deprecated): OK")

    resp = client.post("/stream", json={})
    assert resp.status_code == 422
    print("  POST /stream (validation): OK")

    from src.server import MODE as server_mode

    if server_mode == "unconfigured":
        resp = client.post("/stream", json={"msg": "hi"})
        assert resp.status_code == 200
        ct = resp.headers.get("content-type") or ""
        assert "text/event-stream" in ct
        assert "koraku.started" in resp.text or "data:" in resp.text
        print("  POST /stream (SSE body): OK")
    else:
        print("  POST /stream (SSE body skipped — LLM configured)")

    print("  All routes OK")


def main():
    print("=" * 50)
    print("Koraku Agent - Structure Validation")
    print("=" * 50)

    test_tool_result_policy()
    test_openai_native_tool_call_merge()
    test_imports()
    test_tools()
    test_server_routes()

    print("\n" + "=" * 50)
    print("All tests passed!")
    print("=" * 50)
    print("\nTo run the API server:")
    print("  export ANTHROPIC_API_KEY=your-key")
    print("  python main.py")
    print("\nAPI: http://127.0.0.1:8000  |  Browser UI: cd web && npm run dev")


if __name__ == "__main__":
    main()
