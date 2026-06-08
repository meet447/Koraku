# Koraku SDK

Embeddable ReAct agent for Python apps, HTTP services, and web clients.

## Choose an integration mode

| Your project | Install | How you run Koraku |
|--------------|---------|-------------------|
| **Python script / CLI / bot** | `pip install koraku` | In-process via `Koraku(...)` |
| **Cloud SaaS / backend service** | `pip install "koraku[all]"` | Host with uvicorn, call HTTP/SSE |
| **Web app (React, Next.js, …)** | `@koraku/client` (npm) | Point at your hosted Koraku API |

The Koraku web app in `web/` is a **reference UI** — not required for embedding.

## Configuration layers

| Layer | Module | What it loads |
|-------|--------|----------------|
| **SDK** | `koraku.core.sdk_settings.SdkSettings` | LLM keys, tools, Composio, local/cloud execution target, filesystem memory |
| **Cloud** | `koraku_cloud.cloud_settings.CloudSettings` | Supabase, auth, Redis sessions, Blaxel, automations, SendBlue |

Embedders use **`KorakuConfig` / `SdkSettings` only** — no Supabase env required. Koraku Cloud lives in the separate [koraku-cloud](https://github.com/meet447/koraku-cloud) repo; it registers **product hooks** at startup (`bootstrap_cloud()`) for Supabase chat, personalization, and Supabase-backed automations.

The SDK defaults to **local-first** behavior: workspace files (`.koraku/Memory.md`, `.koraku/Soul.md`), filesystem learned memory, local automations (`.koraku/automations/`), Composio, and the embeddable agent loop.

```python
from koraku import Koraku, KorakuConfig

# Local-first (only an LLM key required)
agent = Koraku(KorakuConfig(fireworks_api_key="...", workspace="."))
```

Optional SDK plugins: Composio (`COMPOSIO_API_KEY`), web tools (`EXA_API_KEY`, `FIRECRAWL_API_KEY`). Cloud-only: Supermemory, Blaxel, Supabase (see repo `.env.example`).

**LLM providers:** see [docs/LLM.md](./LLM.md) for Fireworks, Anthropic, and OpenAI-compatible backends (Ollama, OpenAI, Groq, …).

```python
# Presets
Koraku(KorakuConfig.fireworks(api_key="..."))
Koraku(KorakuConfig.anthropic(api_key="..."))
Koraku(KorakuConfig.openai_compat("ollama", base_url="http://127.0.0.1:11434/v1", model="llama3.2"))
```

## Auth backends (embed / SaaS)

Set `AUTH_BACKEND` (or `KORAKU_AUTH_BACKEND`) on the server:

| Backend | Env | Use when |
|---------|-----|----------|
| `supabase` (default) | `SUPABASE_JWT_SECRET` or JWKS | Koraku web app + multi-user |
| `api_key` | `KORAKU_API_KEY` | Service-to-service, single-tenant SaaS |
| `none` | — | Local OSS with `REQUIRE_AUTH_FOR_CHAT=false` |

Clients send `Authorization: Bearer <token>` for `supabase` and `api_key`.

## SDK server vs Cloud server

| App module | Routes | Use |
|------------|--------|-----|
| `koraku.server_sdk` | `/health`, `/stream`, `/api/composio/*`, `/api/chat-models` | Embedders, self-host without Supabase |
| `koraku_cloud.app` | SDK routes + `/runs`, `/api/personalization`, automations, memory graph, SendBlue, workspace | Koraku Cloud product only |

Supabase chat history and personalization load only when Cloud product hooks are registered (see `koraku/core/product_hooks.py` and `koraku_cloud.bootstrap` in the Cloud repo).

## Workspace personalization (SDK)

| File | Purpose |
|------|---------|
| `.koraku/Memory.md` | Standing preferences and facts the user edits |
| `.koraku/Soul.md` | Persona / tone |
| `.koraku/personalization.json` | Optional agent display name |
| `.koraku/skills/*/SKILL.md` | Optional modular skills loaded into the system prompt |
| `.koraku/automations/*.json` | Scheduled automations (SDK HTTP server with `enable_automation_scheduler=True`) |

## Session store (multi-worker)

| Backend | Env | Use when |
|---------|-----|----------|
| `memory` | — | Single uvicorn worker / dev |
| `redis` | `REDIS_URL` | Multiple API replicas |

Set `SESSION_STORE_BACKEND=redis` when using `REDIS_URL` so chat sessions survive load balancing.

Ops snapshot: `GET /health/detail` with `HEALTH_DETAIL_TOKEN`.

## Publishing

Tag a release (`git tag v0.2.0 && git push origin v0.2.0`) to trigger `.github/workflows/release.yml`:

- **PyPI** — requires GitHub environment `pypi` with [trusted publishing](https://docs.pypi.org/trusted-publishers/)
- **npm** — requires GitHub environment `npm` with `NPM_TOKEN` secret

## Install

```bash
# Core SDK only (in-process agent)
pip install -e .

# Full self-hosted stack (FastAPI server + integrations)
pip install -e ".[all]"
```

## Python — in-process embed

```python
from koraku import Koraku, KorakuConfig, Tool

async def my_tool(query: str) -> str:
    return f"Echo: {query}"

agent = Koraku(
    KorakuConfig(fireworks_api_key="...", llm_provider="fireworks"),
    tools=[Tool(name="Echo", description="Echo text", input_schema={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }, handler=my_tool)],
)

async for event in agent.stream("Use Echo on hello"):
    print(event)
```

See [`examples/embed_python.py`](../examples/embed_python.py).

## Python — configure process defaults

```python
from koraku import configure, KorakuConfig

configure_sdk(KorakuConfig(fireworks_api_key="...").to_sdk_settings())
# or: configure(KorakuConfig(...).to_settings())  # merged view
```

## HTTP — remote agent service

Run the **SDK server** (no Supabase product routes):

```bash
KORAKU_SERVER_APP=sdk uvicorn koraku.server_sdk:app --reload
# monorepo Cloud API: ./scripts/run-api.sh  →  koraku_cloud.app:app
```

Then call `POST /stream` from any language. Optional: `GET /health`, Composio routes when `COMPOSIO_API_KEY` is set.

Koraku Cloud uses `koraku_cloud.app:app` with personalization, automations, detached runs, and Supabase-backed chat — not part of the public SDK wheel.

## TypeScript / web

```bash
cd packages/koraku-client && npm install && npm run build
```

```typescript
import { KorakuClient } from "@koraku/client";

const client = new KorakuClient("http://127.0.0.1:8000", {
  Authorization: "Bearer <token>",
});

for await (const inner of client.streamInnerEvents("Hello")) {
  console.log(inner);
}
```

## AskUser and permission modes

Koraku can pause mid-turn for structured user input (inspired by Claude Agent SDK `AskUserQuestion`).

| `permission_mode` | Behavior |
|-------------------|----------|
| `default` | Normal tool access |
| `plan` | Read/search/AskUser/TodoWrite only until the user confirms a plan |
| `read_only` | Read and search tools only |
| `confirm_sensitive` | Bash, Write, Edit, Composio, and automation mutations require approval |

Env: `PERMISSION_MODE=plan`, `ENABLE_ASK_USER=true`, `ASK_USER_TIMEOUT_SECONDS=600`.

**HTTP:** while `POST /stream` is open, answer via `POST /api/interaction/respond`:

```json
{ "interaction_id": "<from koraku.question>", "answers": { "Tone": "Warm" } }
```

For tool approval (`koraku.approval`):

```json
{ "interaction_id": "<id>", "approved": true }
```

**In-process:**

```python
async for event in agent.stream("...", permission_mode="plan"):
    if event.get("type") == "agent.question":
        Koraku.respond_to_interaction(event["data"]["interaction_id"], {"answers": {"Tone": "Warm"}})
```

Optional embedder hooks (`AgentHooks.pre_tool_use` / `post_tool_use`) block or audit individual tools.

See [`examples/ask_user.py`](../examples/ask_user.py).

## Subagents (Task tool)

Register named workers on `KorakuConfig.agents` or `AgentRunContext.agents`, then the lead agent can call **Task**:

```python
from koraku import AgentDefinition, Koraku, KorakuConfig

agent = Koraku(KorakuConfig(
    fireworks_api_key="...",
    agents={
        "researcher": AgentDefinition(
            description="Web + file research",
            prompt="You are a researcher...",
            tools=("WebSearch", "Read", "Write"),
            max_steps=16,
        ),
    },
))
```

Each definition sets `description` (shown to the lead agent), `prompt`, optional `tools`, `model`, `provider`, and `max_steps`. Nested Task calls are limited by `SUBAGENT_MAX_DEPTH` (default `1`).

SSE: nested tool activity appears under `koraku.subagent` with `task: true`. See [`examples/research_subagents.py`](../examples/research_subagents.py).

## Multi-turn sessions (in-process)

For chat apps, use **`KorakuSession`** instead of one-shot ``stream()``:

```python
from koraku import Koraku, KorakuConfig

koraku = Koraku(KorakuConfig(fireworks_api_key="..."))

async with koraku.session() as chat:
    await chat.send("Remember: my favorite color is teal.")
    async for event in chat.stream():
        handle(event)

    await chat.send("What's my favorite color?")
    async for event in chat.stream():
        handle(event)
```

- ``send()`` queues a user message; ``stream()`` runs one turn and yields the same raw events as ``Koraku.stream()``.
- Conversation history lives in ``chat.state`` (`SessionState`) across turns.
- ``send_and_stream(message)`` combines both steps for simple scripts.

See [`examples/multi_turn_session.py`](../examples/multi_turn_session.py).

## Workspace slash commands (skills)

Place skills at `.koraku/skills/<slug>/SKILL.md`. Users invoke them in chat:

```text
/weekly-review scan my todos and calendar
```

The agent loads that skill's full instructions for the turn. Skill slugs also appear in `GET /api/chat-models` / SSE `system/init` as `slash_commands`.

```python
from koraku.tools.skills import list_skills, slash_commands_for_ui

print(list_skills("."))
print(slash_commands_for_ui("."))
```

## SDK ergonomics

```python
from koraku import Koraku, KorakuConfig, collect_assistant_text, is_completed

# Load from .env / environment
agent = Koraku(KorakuConfig.from_env())

# One-shot text helper
reply = await agent.stream_text("Summarize this in one sentence.")

# Or fold raw events yourself
async for event in agent.stream("Hello"):
    if is_completed(event):
        break
```

See [`examples/from_env.py`](../examples/from_env.py).

## Package layout

| Package | Install | Purpose |
|---------|---------|---------|
| `koraku` | `pip install koraku` | Agent core, tools, LLM (`Koraku`, `Tool`, `Agent`) |
| `koraku[server]` | `pip install "koraku[server]"` | SDK FastAPI app (`/health`, `/stream`, Composio); run with uvicorn |
| `koraku[composio]` | optional | Connected-app toolkits |
| `koraku[blaxel]` | optional | Cloud sandbox execution |
| `koraku[all]` | `pip install "koraku[all]"` | Full self-hosted stack |
| `@koraku/client` | `packages/koraku-client` | TypeScript SSE client for web/cloud apps |
| `koraku_cloud` | monorepo only (not on PyPI) | Koraku Cloud product: Supabase routes, automations, detached runs |

Product code lives in `koraku_cloud/`. The PyPI wheel ships `koraku` only. See [PACKAGING.md](./PACKAGING.md).

## Migration from `src/`

The old `import src.agent` layout is removed. Use `koraku` instead:

```python
# before
from src.agent import Agent

# after
from koraku import Agent
# or
from koraku.agent import Agent
```
