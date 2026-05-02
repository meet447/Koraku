# Koraku Agent

A **ReAct-style AI agent** built from scratch in Python. It uses **Claude** or OpenAI-compatible APIs to think through problems, use tools, and stream every step to the client in real-time via **Server-Sent Events (SSE)**.

---

## Architecture

```
┌─────────────┐      SSE (text/event-stream)      ┌─────────────────────┐
│   Browser   │ ◄────────────────────────────────► │   FastAPI Server    │
│   (UI)      │                                    │   (Python)          │
└─────────────┘                                    └─────────────────────┘
                                                            │
                              ┌─────────────────────────────┼─────────────────────────────┐
                              │                             │                             │
                              ▼                             ▼                             ▼
                    ┌─────────────────┐           ┌─────────────────┐           ┌─────────────────┐
                    │  Unified LLM    │           │   ReAct loop    │           │  Tool registry  │
                    │ (Anthropic or   │◄─────────►│  ``src/agent``  │◄─────────►│ ``src/tools``   │
                    │  OpenAI-compat) │           └─────────────────┘           └─────────────────┘
                    └─────────────────┘
```

### ReAct Loop

1. **User** sends a message
2. **LLM** thinks step-by-step (`thinking_delta` events streamed live)
3. **LLM** decides to use a **tool** (`tool_use` events with incremental JSON)
4. **Tool executes** and result is fed back as a `user` message
5. **LLM** thinks again with the new context
6. Repeat until the LLM provides a **final answer**

---

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run with Prism/Bonsai (Default — No API Key!)

```bash
python main.py
```

The API listens on **http://127.0.0.1:8000** (`GET /` returns service metadata). For the browser chat UI, run the **web/** Next.js app (see below).

### 3. Add Premium Tools (Optional)

For better research quality, add Exa and Firecrawl:

```bash
export EXA_API_KEY=your-exa-key
export FIRECRAWL_API_KEY=your-firecrawl-key
python main.py
```

### 4. Run with Anthropic Claude

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
export AGENT_LLM_PROVIDER=anthropic
python main.py
```

---

## Tools

| Tool | Description | API Key Required |
|------|-------------|-----------------|
| `Bash` | Execute shell commands safely | No |
| `Glob` | Find files matching patterns (`*.py`, `src/**/*.ts`) | No |
| `Grep` | Search file contents with regex | No |
| `Read` | Read file contents with line numbers | No |
| `Write` | Create or overwrite files | No |
| `Edit` | Replace text in files (exact match) | No |
| `WebSearch` | Search the web via DuckDuckGo | No |
| `WebFetch` | Lightweight page fetch for simple HTML | No |
| `ExaSearch` | **Neural search** — finds semantically relevant content | **Yes** (exa.ai) |
| `Firecrawl` | **JS-aware scraping** — handles SPAs, dynamic content | **Yes** (firecrawl.dev) |
| `FirecrawlMap` | Crawl a site to discover all linked URLs | **Yes** (firecrawl.dev) |

---

## Project Structure

Layout follows a small **monorepo**: Python API under `src/`, Next.js UI under `web/`, shared contracts in `src/core/models.py` and `src/llm/canonical.py`.

```
.
├── main.py                 # Uvicorn entry (loads ``src.server:app``)
├── requirements.txt
├── .env.example
├── docs/                   # Design notes (e.g. data lifecycle)
├── tests/                  # Pytest suite (mirror ``src/`` domains where helpful)
│   ├── api/
│   ├── automations/
│   └── test_*.py
│
├── src/                    # Python package: ``import src....``
│   ├── server.py         # FastAPI app factory + routes mount
│   ├── api/              # HTTP routers (chat, health, composio, …)
│   ├── agent/            # ReAct loop, sessions, context manager
│   ├── llm/              # Providers, streaming normalization, sanitize
│   ├── tools/            # Tool registry + builtins (Read, Bash, …)
│   ├── integrations/     # Composio, Blaxel, Supabase chat history, …
│   ├── streaming/        # Koraku SSE envelope (``koraku.*`` outer events)
│   ├── workspace/        # Paths, sandbox context
│   ├── automations/      # Saved automation tools + presentation
│   └── core/             # Settings, auth, redact
│
└── web/                    # Next.js 15 app (``npm run dev`` on :3000)
    └── src/
        ├── app/          # Routes + koraku-api BFF proxies
        ├── components/
        ├── hooks/
        └── lib/
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API root (JSON: service name, version, pointers) |
| `/stream` | POST | SSE streaming agent (JSON body; GET removed) |
| `/health` | GET | Health check + mode (live/demo) |

---

## SSE Event Format

The agent streams events in this format:

```
data: {"type": "agent.started", "data": {"session_id": "...", "mode": "live"}}

data: {"type": "stream_event", "event": {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}}}

data: {"type": "stream_event", "event": {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "Let me search..."}}}

data: {"type": "stream_event", "event": {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "...", "name": "WebSearch", "input": {}}}}

data: {"type": "stream_event", "event": {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": "{\"query\": \"best ..."}}}

data: {"type": "tool_execution", "data": {"tool": "WebSearch", "input": {"query": "..."}, "id": "..."}}

data: {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "...", "content": "...", "is_error": false}]}}

data: {"type": "agent.completed", "data": {"reason": "finished"}}

event: done
data: {}
```

---

## Auto-Detected Research Depth

The agent automatically decides how deep to go based on your prompt:

| Detection | Trigger Words | Behavior |
|-----------|--------------|----------|
| **Quick** (≤3 words) | "hello", "list files" | 15 steps, basic prompt, sequential tools |
| **Medium** (1 deep keyword) | "explain", "how does" | 20 steps, research prompt |
| **Deep** (≥2 deep keywords) | "best", "compare", "review", "2025", "comprehensive" | 30 steps, research prompt, parallel tools, retries, working memory |

### What Happens in Deep Mode

1. **Parallel search** — Multiple search queries run simultaneously
2. **Parallel fetching** — 2-3 top results fetched at the same time
3. **Auto-retry** — Failed sources retried with exponential backoff
4. **Working memory** — Tracks verified findings across all steps
5. **Cross-verification** — Prompts model to check facts across sources

### Streaming Thinking

Every token is streamed live to the UI:

```python
async for event in self.client.messages.stream(...):
    if event.type == "content_block_delta" and event.delta.type == "thinking_delta":
        yield {"type": "content_block_delta", "delta": {"thinking_delta": event.delta.thinking}}
```

### Parallel Tool Execution

When the model requests multiple tools, they run concurrently:

```python
# Deep mode: fetch 3 URLs at the same time
results = await asyncio.gather(
    firecrawl(url1),
    firecrawl(url2),
    exa_search(query),
)
```

### ReAct Loop with Memory

```python
while step_count < max_steps:
    # 1. Auto-detect depth from user query
    mode, max_steps, prompt = classify_query(user_input)

    # 2. Inject working memory into context
    messages = inject_memory(messages, working_memory)

    # 3. Stream LLM response
    async for event in llm.stream(messages, tools):
        yield event

    # 4. Execute tools in parallel
    results = await execute_tools_parallel(tool_uses)

    # 5. Update working memory with findings
    working_memory.extend(extract_findings(results))

    # 6. Feed results back
    messages.append({"role": "user", "content": results})
```

---

## Configuration

Set via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_LLM_PROVIDER` | `custom_openai` | Backend: `anthropic`, `custom_openai`, or `demo` |
| `ANTHROPIC_API_KEY` | — | Claude API key (for `anthropic` provider) |
| `AGENT_ANTHROPIC_MODEL` | `claude-3-5-sonnet-20241022` | Claude model name |
| `AGENT_CUSTOM_BASE_URL` | `https://prism-ml-bonsai-demo.hf.space/v1` | OpenAI-compatible endpoint |
| `AGENT_CUSTOM_MODEL` | `Bonsai-8B-Q1_0` | Model name for custom endpoint |
| `AGENT_CUSTOM_API_KEY` | — | API key for custom endpoint (if required) |
| `AGENT_PORT` | `8000` | Server port |
| `AGENT_MAX_TOKENS` | `4096` | Max tokens per response |
| `AGENT_MAX_STEPS` | `15` | Max tool-use iterations |

---

## Testing

### Structure + smoke (no API key for most checks)

From the repo root (with dev dependencies installed, e.g. ``pip install -r requirements.txt``):

```bash
pytest tests/test_structure.py -q
# or, without pytest:
python tests/test_structure.py
```

### Full suite

```bash
pytest -q
```

### Start Server

```bash
# Demo mode
python main.py

# Live mode
export ANTHROPIC_API_KEY=sk-...
python main.py
```

### Next.js frontend (`web/`)

From another terminal (with the Python server still on port 8000):

```bash
cd web
npm install
npm run dev
```

Open **http://127.0.0.1:3000**. The app proxies SSE and APIs to the agent via `next.config.ts` rewrites (override the backend with `KORAKU_BACKEND_URL` if needed).

**Detached chat (mobile / tab-switch):** set `NEXT_PUBLIC_KORAKU_DETACHED_CHAT` in `web/` to `always` (every turn uses `POST /runs` + subscribe SSE), `heavy` (long prompts ≥3200 chars or any images use detached runs), or leave unset for inline `POST /stream` only. The backend exposes `GET /runs/{run_id}/status` (JSON: `running` | `completed` | `not_found`) for reconnect UX; buffers are per-worker RAM (see `docs/DATA_LIFECYCLE.md`).

---

## Extending the Agent

### Add a New Tool

```python
# src/tools.py

async def _my_tool(query: str) -> str:
    return f"Result for {query}"

my_tool = Tool(
    name="MyTool",
    description="Does something useful",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to query"}
        },
        "required": ["query"]
    },
    handler=_my_tool,
)

TOOLS.append(my_tool)
```

The agent will automatically discover it because `get_tool_schemas()` reads from the `TOOLS` list.

### Use a Different LLM Provider

Replace `src/llm.py` with your own client (OpenAI, Ollama, Bedrock, etc.) as long as it yields events in the same format:

```python
{"type": "message_start", "message": {...}}
{"type": "content_block_start", "index": N, "content_block": {...}}
{"type": "content_block_delta", "index": N, "delta": {...}}
{"type": "content_block_stop", "index": N}
{"type": "message_delta", "delta": {...}}
{"type": "message_stop", "message": {...}}
{"type": "assistant_message", "message": {...}}
```

---

## License

MIT
# Koraku
