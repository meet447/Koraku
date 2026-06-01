# Changelog

## Unreleased

### Added
- Docker Compose stack for OSS self-host (`docker compose up`)
- Server execution mode for chat without Blaxel (`ALLOW_SERVER_EXECUTION_IN_CHAT`)
- Setup banner when API or LLM is misconfigured
- Local demo: open `/app` without Supabase when auth env vars are unset

## 0.2.0 — 2026-06-01

### Added
- Embeddable `koraku` Python package (`Koraku`, `KorakuConfig`, injectable settings)
- `@koraku/client` TypeScript SSE SDK
- Pluggable auth (`supabase`, `api_key`, `none`) and session store (`memory`, `redis`)
- Release workflow for PyPI + npm (tag `v*`)
- SDK docs (`docs/SDK.md`) and embed example

### Changed
- Python package moved from `src/` to `koraku/` (`src/` is a deprecated shim)
