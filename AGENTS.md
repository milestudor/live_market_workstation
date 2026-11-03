# Project instructions

- Scope is Assignment 4.1: Vue frontend, FastAPI backend, SQLite, Yahoo streaming, charts and replay. Do not silently implement 4.2/4.3 or real trading.
- Preserve immutable observation versions and delivery receipts. Filter by receipt sequence before choosing authoritative revisions for replay.
- Never replace an unavailable live feed with fabricated data. Keep synthetic fixtures isolated and visibly labeled.
- Preserve source and receipt times, candle finality, partial coverage, volume availability, and source provenance. Do not describe all volume as exact.
- Keep server bindings on localhost. Keep TLS verification enabled. Never commit databases, credentials, dependencies, or local environments.
- Use backend/requirements.txt and frontend/package-lock.json for reproducibility. Verify the yfinance adapter's private API contract on upgrades.
- Run `.venv/bin/python -m pytest -q`, `cd frontend && npm run build`, and relevant browser tests after behavior changes.
- Update README, docs/design.md, docs/evidence.md, AI-USE.md and report.md when claims or behavior change. Distinguish actual provider observations from mocked tests.
- Student must review and be able to explain generated code; do not invent evidence, commit IDs, video links, or model details.
