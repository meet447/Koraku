# Contributing to Koraku

Thanks for helping improve the open-source SDK.

## Setup

```bash
git clone https://github.com/meet447/Koraku.git
cd Koraku
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,server,all]"
cp .env.example .env
pytest -q
```

## Scope

This repository contains **`koraku/`** and **`packages/koraku-client/`** only.

## Pull requests

- Keep PRs focused; include tests for behavior changes.
- Run `pytest` and `./scripts/verify-sdk-wheel.sh` before opening a PR.
- Do not commit secrets or `.env` files.
