# LLM providers (Koraku SDK)

Koraku routes all model calls through **`UnifiedLLMClient`**, which normalizes requests to a single canonical shape and streams the same event types regardless of backend.

## Built-in providers

| Provider id | Backend | Configure |
|-------------|---------|-----------|
| `fireworks` (default) | Fireworks OpenAI-compatible API | `FIREWORKS_API_KEY`, `FIREWORKS_MODEL` |
| `anthropic` | Native Anthropic Messages API + tools | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |

## OpenAI-compatible providers

Any HTTP API that speaks the OpenAI Chat Completions protocol (Ollama, vLLM, OpenAI, Groq, Together, local proxies) registers as a **named provider id**.

### Option A — SDK presets (recommended for embedders)

```python
from koraku import Koraku, KorakuConfig

# Fireworks
agent = Koraku(KorakuConfig.fireworks(api_key="...", model="accounts/fireworks/models/kimi-k2p6"))

# Anthropic
agent = Koraku(KorakuConfig.anthropic(api_key="...", model="claude-3-5-sonnet-20241022"))

# Ollama / vLLM / OpenAI / Groq / …
agent = Koraku(KorakuConfig.openai_compat(
    "ollama",
    base_url="http://127.0.0.1:11434/v1",
    api_key="ollama",  # often unused for local Ollama
    model="llama3.2",
))
```

Set `llm_provider` to the same id you pass to `openai_compat()` (e.g. `"ollama"`).

### Option B — register at runtime

```python
from koraku import OpenAICompatProvider
from koraku.llm import register_openai_compat_provider

register_openai_compat_provider(OpenAICompatProvider(
    id="groq",
    label="Groq",
    base_url="https://api.groq.com/openai/v1",
    api_key="gsk_...",
    default_model="llama-3.3-70b-versatile",
    models=("llama-3.3-70b-versatile",),
))
```

Then `Koraku(KorakuConfig(llm_provider="groq"))`.

### Option C — environment variables (servers / `.env`)

**Comma-separated ids** plus per-id env vars (`{PREFIX}_BASE_URL`, `{PREFIX}_API_KEY`, `{PREFIX}_MODEL`, optional `{PREFIX}_MODELS`, `{PREFIX}_LABEL`):

```bash
LLM_PROVIDER=openai
LLM_OPENAI_COMPAT_IDS=openai,groq
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
```

**Legacy local proxy** (auto-registers id `custom`):

```bash
CUSTOM_BASE_URL=http://127.0.0.1:1234/v1
CUSTOM_MODEL=llama-3.3-70b
LLM_PROVIDER=custom
```

**JSON blob** (good for Docker / Render env):

```bash
LLM_OPENAI_COMPAT_JSON='[{"id":"together","base_url":"https://api.together.xyz/v1","api_key":"...","default_model":"meta-llama/Llama-3-70b-chat-hf"}]'
LLM_PROVIDER=together
```

### Option D — `KorakuConfig` JSON field

```python
KorakuConfig(
    llm_provider="together",
    llm_openai_compat_json='[{"id":"together", ...}]',
)
```

Or pass `openai_compat_providers=(OpenAICompatProvider(...),)` on `KorakuConfig` — serialized into settings automatically.

## Per-turn overrides

HTTP `POST /stream` accepts `provider` and `model` in the JSON body.

In-process:

```python
async for event in agent.stream("Hi", provider="anthropic", model="claude-3-5-sonnet-20241022"):
    ...
```

Subagents (`AgentDefinition`) can set their own `provider` / `model`.

## Inspect configured providers

```python
from koraku import Koraku, KorakuConfig
from koraku.llm import configured_provider_ids, describe_provider, list_providers

agent = Koraku(KorakuConfig.fireworks(api_key="..."))
print(agent.list_providers())           # ['fireworks']
print(agent.list_providers(detailed=True))  # UI-shaped blocks

print(describe_provider("fireworks"))
print(configured_provider_ids())
```

HTTP: `GET /api/chat-models` returns the same catalog for web UIs.

## Architecture

```
Koraku.stream() / Agent.run()
        ↓
UnifiedLLMClient(provider_override)
        ↓
  ┌─────────────┬──────────────────┐
  │  anthropic  │ OpenAICompatBackend │  ← fireworks + all openai_compat ids
  └─────────────┴──────────────────┘
        ↓
CanonicalChatRequest → normalized SSE stream events
```

Module reference:

| Module | Purpose |
|--------|---------|
| `koraku.llm.client.UnifiedLLMClient` | Provider routing |
| `koraku.llm.catalog` | Model list, resolution, `ui_chat_models()` |
| `koraku.llm.openai_compat_registry` | Named OpenAI-compat providers |
| `koraku.llm.dx` | `list_providers`, `describe_provider` helpers |

See [`examples/llm_providers.py`](../examples/llm_providers.py).
