# Koraku roadmap

Koraku is built in two phases: an **open-source self-hosted webapp** anyone can run, then a **hosted cloud product** with multi-tenant scale and extra clients.

## Phase 1 — OSS webapp (now)

**Goal:** Clone → configure → chat with tools in under 30 minutes. No Koraku-operated services required.

| In scope | Out of scope (defer to Phase 2) |
|----------|----------------------------------|
| Self-host Python API + Next.js UI | Multi-tenant orgs / billing |
| Supabase auth (optional) | Managed Koraku Cloud |
| `execution_target=server` (tools on API host) | Durable detached runs across replicas |
| Optional Blaxel for `cloud` sandboxes | Mobile apps |
| Optional Composio connections | iMessage / SMS bridges |
| Embeddable `koraku` Python SDK + `@koraku/client` | Per-tenant quotas / usage metering |

**Success:** A contributor or solo user runs Docker Compose (or manual install), signs in (or runs demo mode), and gets a smooth chat + tools experience on their own machine or VM.

See [SELF_HOST.md](SELF_HOST.md) for the runbook.

## Phase 2 — Koraku Cloud (later)

**Goal:** Same agent core, plus control plane for production SaaS and new surfaces.

Planned capabilities (not committed to a date):

1. **Multi-tenant control plane** — org/workspace IDs on auth, sessions, runs, and storage
2. **Durable detached runs** — Redis (or queue) run store + SSE pub/sub (no sticky sessions)
3. **Hosted deploy** — managed API + web, cloud sandboxes by default
4. **Mobile clients** — `@koraku/client` + native auth
5. **Messaging** — iMessage/SMS/webhook adapters → async agent jobs

Phase 2 **imports** the `koraku` package; it does not fork the ReAct loop.

## SDK layering (plan for both phases)

```
koraku (PyPI)          Agent, Tool, LLM, Koraku facade
    ↑
koraku-server          FastAPI, SSE, optional extras [composio, blaxel]
    ↑
@koraku/client (npm)   SSE client for any web/mobile app
    ↑
web/ (OSS)             Reference Next.js UI — not required to embed
    ↑
cloud/ (future)        Tenants, run queue, billing, push/SMS — not in OSS repo yet
```

### Interfaces to keep stable

| Interface | OSS | Cloud |
|-----------|-----|-------|
| Auth | `supabase` / `api_key` / `none` | + org claims, tenant API keys |
| Session store | `memory` / `redis` | Redis with tenant prefix |
| Run store | in-process (detached) | Redis pub/sub |
| HTTP + SSE | `POST /stream`, `koraku.*` events | Same contract, versioned |

## How to contribute by phase

- **Phase 1 PRs:** install friction, UX polish, docs, self-host defaults, bug fixes in `web/` and `koraku-server`
- **Phase 2 PRs:** wait until we open a `cloud/` package or separate repo; design docs and interfaces only until then
