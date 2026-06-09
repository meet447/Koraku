# Koraku SDK

Embeddable ReAct agent for Python apps, HTTP services, and web clients. **Local-first by default.**

## Choose an integration mode

| Your project | Install | How you run Koraku |
|--------------|---------|-------------------|
| **Python script / CLI / bot** | `pip install koraku` | In-process via `Koraku(...)` |
| **Self-hosted HTTP API** | `pip install "koraku[server]"` | `uvicorn koraku.server_sdk:app` |
| **Web app (React, Next.js, …)** | `@koraku/client` (npm) | Point at your Koraku API |

## Quick start (in-process)

```python
from koraku import Koraku, KorakuConfig

agent = Koraku(KorakuConfig.from_env())  # reads .env / FIREWORKS_API_KEY, etc.
async for event in agent.stream("Summarize this repo"):
    print(event)
```

Or with explicit config:

```python
agent = Koraku(KorakuConfig(fireworks_api_key="...", workspace="."))
```

**LLM providers:** [LLM.md](./LLM.md) (Fireworks, Anthropic, OpenAI-compatible).

```python
Koraku(KorakuConfig.fireworks(api_key="..."))
Koraku(KorakuConfig.anthropic(api_key="..."))
Koraku(KorakuConfig.openai_compat("ollama", base_url="http://127.0.0.1:11434/v1", model="llama3.2"))
```

## Configuration

SDK settings: `koraku.core.sdk_settings.SdkSettings` / `KorakuConfig`.

| Concern | Default (OSS) | Env |
|---------|---------------|-----|
| Execution | `local` | `DEFAULT_EXECUTION_TARGET` |
| Memory | `filesystem` | `MEMORY_BACKEND` |
| Auth (HTTP server) | `none`, auth not required | `AUTH_BACKEND`, `REQUIRE_AUTH_FOR_CHAT` |
| Session store | in-memory | `SESSION_STORE_BACKEND=redis`, `REDIS_URL` |

Copy [`.env.example`](../.env.example) — OSS auth defaults are open for local dev.

Optional plugins: Composio (`COMPOSIO_API_KEY`), web tools (`EXA_API_KEY`, `FIRECRAWL_API_KEY`), MCP (`pip install "koraku[mcp]"`, `.koraku/mcp.json`).

## Workspace files

| Path | Purpose |
|------|---------|
| `.koraku/Memory.md` | Standing preferences and facts |
| `.koraku/Soul.md` | Persona / tone |
| `.koraku/personalization.json` | Optional agent display name |
| `.koraku/skills/*/SKILL.md` | Modular skills + `/slash` commands |
| `.koraku/automations/*.json` | Scheduled / event automations |
| `.koraku/runs/<run_id>/` | Per-run audit logs (transcript, tool_calls) |
| `.koraku/mcp.json` | Stdio MCP server definitions |

## Self-hosted HTTP server

```bash
cp .env.example .env   # add LLM keys
uvicorn koraku.server_sdk:app --reload --port 8000
```

| Route | Purpose |
|-------|---------|
| `GET /health` | Liveness |
| `POST /stream` | Chat SSE |
| `POST /api/interaction/respond` | AskUser / tool approval |
| `POST /api/action/execute` | One-click action cards |
| `POST /api/automations/trigger/{event_key}` | Event automations |
| `GET /api/composio/*` | Composio proxy (when configured) |

Enable cron automations: `create_sdk_app(enable_automation_scheduler=True)`.

Ops: `GET /health/detail` with `HEALTH_DETAIL_TOKEN`.

## Auth (self-hosted API)

| Backend | When to use |
|---------|-------------|
| `none` | **Default.** Local dev; set `REQUIRE_AUTH_FOR_CHAT=false` |
| `api_key` | Single-tenant SaaS; `KORAKU_API_KEY` + `Authorization: Bearer …` |

## Install

```bash
pip install koraku
pip install "koraku[server]"
pip install "koraku[all]"
```

## Python — custom tools

```python
from koraku import Koraku, KorakuConfig, Tool

async def my_tool(query: str) -> str:
    return f"Echo: {query}"

agent = Koraku(
    KorakuConfig(fireworks_api_key="..."),
    tools=[Tool(name="Echo", description="Echo text", input_schema={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }, handler=my_tool)],
)
```

See [`examples/embed_python.py`](../examples/embed_python.py), [`examples/from_env.py`](../examples/from_env.py).

Run from the repo root after `cp .env.example .env` and setting an LLM key:

```bash
python examples/from_env.py
python examples/embed_python.py
```

| Example | What it shows |
|---------|----------------|
| [`from_env.py`](../examples/from_env.py) | `.env` config + `stream_text()` |
| [`embed_python.py`](../examples/embed_python.py) | Minimal `stream_events()` loop |
| [`multi_turn_session.py`](../examples/multi_turn_session.py) | `KorakuSession` multi-turn chat |
| [`ask_user.py`](../examples/ask_user.py) | AskUser + `permission_mode="plan"` |
| [`research_subagents.py`](../examples/research_subagents.py) | Task tool + `AgentDefinition` |
| [`llm_providers.py`](../examples/llm_providers.py) | Fireworks, Anthropic, OpenAI-compat |

### Stream events (Python)

Raw dicts (HTTP-compatible):

```python
async for raw in agent.stream("Hello"):
    if raw.get("type") == "agent.completed":
        ...
```

Typed wrappers (recommended):

```python
from koraku import (
    EventType,
    KorakuEvent,
    PermissionModes,
    ExecutionTargets,
    ProviderInfo,
)

async for event in agent.stream_events("Hello"):
    if event.completed is not None:
        print(event.completed.reason, event.completed.steps)
    elif event.question is not None:
        Koraku.answer_question(event.question.interaction_id, {"Goal": "Work"})
    elif event.approval is not None:
        Koraku.approve_tool(event.approval.interaction_id, approved=True)
    elif event.text:
        print(event.text, end="")
```

| API | Purpose |
|-----|---------|
| `EventType.agent.*` | Event type string constants |
| `KorakuEvent.question` / `.completed` / `.approval` / `.action` | Typed payloads |
| `KorakuEvent.llm` / `.text` | Inner LLM stream + assistant text |
| `Koraku.answer_question()` / `.approve_tool()` | AskUser + tool approval |
| `PermissionModes` / `ExecutionTargets` | Mode constants |
| `ProviderInfo` | `list_providers(detailed=True)` |
| `session.last_assistant_text()` | Multi-turn session helpers |

`KorakuEvent` adds `.data`, `.questions`, `.interaction_id`, `.assistant_text`, and `.is_*` helpers. `parse_event(raw)` wraps a dict you already have.

## TypeScript / web

```bash
cd packages/koraku-client && npm install && npm run build
```

```typescript
import { KorakuClient, slashCommandsFromInit, respondToInteraction } from "@koraku/client";

const client = new KorakuClient("http://127.0.0.1:8000");
for await (const event of client.streamChat("Hello")) {
  // koraku.question, koraku.action, koraku.event, …
}
```

## AskUser and permission modes

| `permission_mode` | Behavior |
|-------------------|----------|
| `default` | Normal tool access |
| `plan` | Read/search/AskUser/TodoWrite until plan confirmed |
| `read_only` | Read and search only |
| `confirm_sensitive` | Bash/Write/Edit/Composio/automation writes need approval |

Env: `PERMISSION_MODE`, `ENABLE_ASK_USER`, `ASK_USER_TIMEOUT_SECONDS`.

HTTP: answer via `POST /api/interaction/respond`. In-process: `Koraku.respond_to_interaction(...)`.

Embedder hooks: `AgentHooks.pre_tool_use` / `post_tool_use`. See [`examples/ask_user.py`](../examples/ask_user.py).

## Subagents (Task tool)

```python
from koraku import AgentDefinition, Koraku, KorakuConfig

agent = Koraku(KorakuConfig(
    fireworks_api_key="...",
    agents={
        "researcher": AgentDefinition(
            description="Web + file research",
            prompt="You are a researcher...",
            tools=("WebSearch", "Read", "Write"),
        ),
    },
))
```

See [`examples/research_subagents.py`](../examples/research_subagents.py).

## Multi-turn sessions

```python
async with koraku.session() as chat:
    await chat.send("Remember: my favorite color is teal.")
    async for event in chat.stream():
        ...
```

See [`examples/multi_turn_session.py`](../examples/multi_turn_session.py).

## Slash commands (skills)

```text
/weekly-review scan my todos and calendar
```

Slugs appear in SSE `system/init` as `slash_commands`. See `koraku.tools.skills`.

## SDK ergonomics

```python
from koraku import Koraku, KorakuConfig, collect_assistant_text, is_completed

agent = Koraku(KorakuConfig.from_env())
reply = await agent.stream_text("One sentence summary.")
```

Helpers in `koraku.sdk_events`: `is_question`, `is_approval`, `is_action`, `is_run_log`, etc.

## Run artifacts

When `ENABLE_RUN_ARTIFACTS=true` (default): `.koraku/runs/<run_id>/` with `transcript.jsonl`, `tool_calls.jsonl`, `meta.json`.

## One-click actions

**ProposeAction** tool → `koraku.action` SSE → `POST /api/action/execute`.

## Event automations

`trigger_mode: "event"` + `event_key` → `POST /api/automations/trigger/{event_key}`.

## MCP servers

`.koraku/mcp.json` + `pip install "koraku[mcp]"`. Tools: `mcp_<server>_<tool>`.

## Package layout

| Package | Purpose |
|---------|---------|
| `koraku` | Core SDK (`Koraku`, `Tool`, agent loop) |
| `koraku[server]` | FastAPI app |
| `koraku[composio]` | Connected apps |
| `koraku[mcp]` | MCP stdio servers |
| `koraku[all]` | Common self-host bundle |
| `@koraku/client` | TypeScript SSE client |

PyPI ships `koraku` only. See [PACKAGING.md](./PACKAGING.md).

## Publishing

Tag `v0.2.0` → GitHub Actions release (PyPI + npm). See workflow in `.github/workflows/release.yml`.

## Migration from `src/`

```python
# before: from src.agent import Agent
from koraku import Agent
```
