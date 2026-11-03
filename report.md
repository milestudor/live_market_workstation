# Assignment 4.1 · Meridian Market Workstation

**Status:** Working Part 4.1 implementation; this report is a draft until the student reviews it and adds the demonstration video.

- **Repository:** https://github.com/milestudor/live_market_workstation
- **Application commit:** To be filled after the verified application commit.
- **30–60 second demonstration/process video:** **Pending — add an instructor-accessible link before submitting.** See the [demo checklist](https://github.com/milestudor/live_market_workstation/blob/main/docs/demo.md).

## Completed

Built a local Vue frontend, FastAPI backend and SQLite database. Yahoo Finance supplies streaming observations; the backend forwards chart snapshots through WebSockets. Candlesticks and historical/available observed volume appear with a five-symbol watchlist, interval selection, source provenance, source age, source/receipt timestamps, and feed/browser connection state.

SQLite preserves immutable observation versions and every delivery receipt. Duplicate, revised, and out-of-order messages follow documented rules. Live/Replay controls beneath the chart allow receipt-based scrubbing, play/pause, restart, and JSON export. The application retains saved data during feed failure and can be exercised offline with a separately labeled synthetic fixture.

## Design decisions

The dark workstation uses TradingView Lightweight Charts for financial chart interaction. Replay filters available receipts before selecting the latest revision, preventing future corrections from leaking into an earlier view. A stream-built candle is labeled partial; an ended interval does not imply full market coverage. Source age is independent of browser/feed connection status.

Yahoo does not supply unique trade IDs in this stream. This app treats changed payloads with the same symbol/source/type/timestamp as revisions and preserves raw messages. This documented policy can collapse distinct same-timestamp events; it is not an exchange trade ledger.

## Verification and revised approach

- 17 automated backend checks passed, including duplicate/revision/late-arrival policies, known candle/volume examples, as-of replay, persistence, WebSocket delivery, validation, and failure handling.
- Production frontend build passed. Desktop and mobile browser checks passed against an isolated synthetic database; those checks are not live-provider evidence.
- Actual after-hours Yahoo observations reached SQLite, the local WebSocket endpoint, and the browser. A captured AAPL price matched its stored version and chart close. See the [live-path capture](https://github.com/milestudor/live_market_workstation/blob/main/docs/evidence/live-check.json) and [screenshot](https://github.com/milestudor/live_market_workstation/blob/main/docs/evidence/live-dashboard.png).
- An initial macOS TLS certificate failure was resolved using a trusted certifi bundle while keeping verification enabled. Real after-hours messages omitted volume; the implementation was revised to display unavailable volume instead of a misleading zero. Generated aggregation code and its verification are discussed in the [evidence log](https://github.com/milestudor/live_market_workstation/blob/main/docs/evidence.md).
- Automated checks are configured in GitHub Actions; local results are distinguished from hosted workflow results in the evidence log.

## Limitations and remaining submission work

The student must still review/explain the generated code, record and link the short video, and verify instructor access. Regular-session streamed volume has not yet been observed; actual after-hours price streaming and historical volume have been verified. Stream coverage and cumulative-volume allocation can be partial. Replay is accelerated receipt playback, not a backtest. The slider covers the latest 2,000 receipts; charts show at most 600 bars. The initial local backend rebuilds snapshots from stored observations and is not optimized for a large long-running archive.

Indicators, trading/accounting, backtesting, and AI text/vision/audio belong to Parts 4.2–4.3 and are intentionally unimplemented.

## Supporting documentation

[README and startup](https://github.com/milestudor/live_market_workstation/blob/main/README.md) · [Architecture and SQLite schema](https://github.com/milestudor/live_market_workstation/blob/main/docs/design.md) · [Agent instructions](https://github.com/milestudor/live_market_workstation/blob/main/AGENTS.md) · [AI-use disclosure](https://github.com/milestudor/live_market_workstation/blob/main/AI-USE.md) · [Curated evidence](https://github.com/milestudor/live_market_workstation/blob/main/docs/evidence.md)

Upload only this `report.md` to Canvas after completing the pending items. Keep code in the linked repository.
