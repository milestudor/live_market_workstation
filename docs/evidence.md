# Verification and curated evidence · November 3, 2026

This is a selected, redacted development record, not a complete chat export. No credentials, private third-party material, or local database is included. Synthetic checks and actual provider observations are identified separately.

## Results

| Check | Evidence | Result and boundary |
| --- | --- | --- |
| Backend | `backend/tests/test_market.py`; `.venv/bin/python -m pytest -q` | 17 passed. Deterministic fixtures cover versioning, duplicate receipts, late data, revisions, source-order OHLC/volume, missing volume, resets, interval finality, persistence, validation, WebSocket delivery, provider failure, and clean socket closure. One dependency deprecation warning about FastAPI/Starlette's use of httpx; no failing checks. |
| Frontend build | `cd frontend && npm run build` | Production build passed. |
| Desktop browser | `frontend/tests/workstation.spec.js`, 1440 × 1050 | Passed. Isolated synthetic SQLite fixture, live provider disabled. |
| Mobile browser | Same test, 390 × 844 | Passed. Controls, help, and horizontal overflow checked. Export control is intentionally hidden on the smallest layout, so its download is exercised in the desktop run. |
| Actual Yahoo | [Live-path capture](evidence/live-check.json) | Real after-hours AAPL stream observation matched its SQLite version and the local WebSocket chart close. Capture at 5:31 PM Eastern. No synthetic values used in this check. |
| Actual browser | [Screenshot](evidence/live-dashboard.png) | Running localhost UI, actual Yahoo history + stream, source-age display, and explicit unavailable stream volume. Narrow-window view. |
| Offline/failure | Automated provider connection exception + offline browser backend | Unavailable/retry state and explicit disabled-feed UI verified with controlled fixtures. Initial real TLS failure was also observed; this was a local certificate problem, not a proven Yahoo outage. |
| Clean checkout | Application commit `737db649140fb1cc1fe10e299c4d2e1a4b4dafbb` | Fresh Python environment + pinned requirements, fresh `npm ci`, 17 backend checks, production build, and both browser projects passed. No tracked changes remained in the checkout. |

The live capture recorded 4,007 immutable observation versions and 11,814 delivery receipts, including 7,807 duplicates and 4 revisions. Repeated startup history requests explain most duplicates; duplicate receipts remain visible without multiplying chart volume. These counters are a capture, not an expected stable test result. The initial history request loaded 3,900 minute bars across five symbols (two sessions).

## Selected development entries

### 1. Scope and interface

- **Intent / instruction excerpt:** “All that should be completed up to this point is 4.1”; “dark TradingView-style workstation”; replay “beneath the chart, with a clear Live/Replay switch.”
- **Resulting files:** `frontend/src/App.vue`, `frontend/src/style.css`, `backend/main.py`, `docs/design.md`.
- **Observation:** Browser showed the central candlestick/volume chart, watchlist, separate source-age and connection indicators, and lower replay controls. Desktop and mobile browser checks passed.
- **Decision:** Keep 4.2/4.3 indicators, trading, backtesting and AI out of this implementation. Use AAPL, MSFT, NVDA, AMZN, SPY as an illustrative watchlist.
- **Uncertainty:** Student design/code review and demonstration remain to be completed.

### 2. Identity, revisions, duplicates and replay

- **Intent / instruction excerpt:** “Preserve observation identity, source and receipt times, revisions, and whether a candle is complete”; “test how duplicate, revised, and out-of-order observations are handled.”
- **Generated code:** `backend/store.py`, especially `ingest` and `current`; `backend/market.py` for source-order candle rebuilding.
- **Verification:** Duplicate deliveries create one version/two receipts; a revised price is invisible before the later receipt; a late earlier-source tick changes the open only after arrival; a correction removes an obsolete high; known cumulative volume examples match expected deltas.
- **Decision:** Append immutable versions plus every delivery receipt; filter by receipt cursor before selecting the latest revision. Derive stream candle boundary state at the as-of clock.
- **Remaining uncertainty:** Yahoo supplies no stable trade ID here. Same-timestamp messages may be distinct events but are treated as revisions; this is explicitly disclosed rather than described as exact exchange identity.

### 3. Failed live approach: certificate verification

- **Intent:** Connect to the real Yahoo source and verify the path through the running app.
- **Observed failure:** Initial `yfinance.AsyncWebSocket` connection raised `SSLCertVerificationError` on this Python.org macOS installation. Stored historical data could still render, which demonstrated why history alone is insufficient proof of streaming.
- **Revised code:** `backend/main.py` defaults `SSL_CERT_FILE` to `certifi.where()` only when the environment did not specify another bundle.
- **Verification:** Subsequent actual provider updates reached SQLite and the browser. The live-path JSON cross-checks one persisted observation and WebSocket chart close.
- **Decision:** Repair trusted CA resolution; never disable TLS verification.
- **Remaining uncertainty:** Other environments may require their own valid trust bundle; source/network availability is outside the app's guarantee.

### 4. Revised volume interpretation

- **Intent:** Display corresponding volume without inventing market observations.
- **Observed problem:** The real after-hours messages contained price, timestamp and market-hours information, but no `day_volume`. Treating a missing cumulative field as a zero-volume observation would imply more knowledge than the feed supplied.
- **Revised code:** `backend/market.py` returns null volume for all-missing stream buckets; `App.vue` renders whitespace in the histogram and labels the coverage “volume unavailable.”
- **Verification:** Real raw sample in `evidence/live-check.json` has no volume. The missing-volume unit test requires null, while separate synthetic cumulative-volume tests check known arithmetic.
- **Decision:** Preserve missingness, retain historical volume, and clearly separate historical vs partial streamed coverage.
- **Remaining uncertainty:** Regular-session Yahoo cumulative volume was not observed during this after-hours session. Per-trade volume allocation remains approximate even when cumulative fields are available.

### 5. Provider lifecycle and browser-test revision

- **Intent:** Keep feed failure observable and make small-window behavior testable.
- **Code inspection:** Pinned yfinance's listener owns an indefinite reconnect loop. The local `backend/feed.py` adapter instead returns/raises on close so the app owns retries. Its private package dependencies are isolated and documented; the clean-close unit check guards against a closed-socket loop.
- **Test revision:** Browser tests initially could not launch without Chromium. After installing the project-local test browser, the desktop test passed; the mobile test timed out trying to use a header help button hidden in the compact layout. The test was changed to use the visible rail help button.
- **Verification:** Both browser projects then passed, including keyboard-capable help, interval/symbol changes, replay scrubbing/playback, and absence of page errors or horizontal overflow.
- **Remaining uncertainty:** The provider adapter must be rechecked on yfinance upgrades. Browser tests deliberately do not contact Yahoo and cannot prove provider uptime.

## Student follow-through

Review the generated code and documentation, run the app yourself, record the 30–60 second combined demo/process video, add its accessible link to `report.md`, and verify instructor access to the repository/video. No video, Canvas upload, or student presentation has been completed by this build.

## Clean-checkout verification

A separate clone of application commit `737db649140fb1cc1fe10e299c4d2e1a4b4dafbb` was created after committing the application. A fresh Python virtual environment installed `backend/requirements.txt`; the frontend installed from `package-lock.json` with `npm ci`. Backend result: **17 passed**. Frontend result: **production build passed**. The isolated fixture was seeded into a new database; desktop/mobile browser result: **2 passed**. The clone had no tracked file changes afterward. A previously downloaded Chromium binary was reused; the clone did not reuse frontend modules or the root Python environment.

This verification covers local reproducibility on this Mac. The [GitHub Actions run for commit `055a80e`](https://github.com/milestudor/live_market_workstation/actions/runs/41732322570) also completed successfully on Ubuntu at 5:39 PM Eastern on November 3, 2026: pinned dependency installs, 17 backend checks, production build, and both browser projects passed. The report points to the tested application commit; subsequent documentation-only commits fill in evidence metadata.
