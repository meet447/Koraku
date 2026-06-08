# Packaging

## PyPI (`koraku`)

The published wheel contains **`koraku`** and **`koraku.*` only**.

CI verifies the wheel layout via `tests/test_wheel_layout.py` and `scripts/verify-sdk-wheel.sh`.

```bash
pip install koraku
pip install "koraku[server]"   # FastAPI + uvicorn
pip install "koraku[all]"      # common self-host extras
```

## npm (`@koraku/client`)

TypeScript SSE client: `packages/koraku-client/`. Published separately from the Python wheel.
