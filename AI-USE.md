# AI-use disclosure

Date: November 3, 2026. This document describes the assistance used in this project; the student should review it and add any other tools used outside this chat.

- **Agent/editor:** OpenAI Codex desktop app. Used to review the assignment, inspect official library documentation, choose the interface, generate Vue/FastAPI/SQLite code, build deterministic tests, inspect the running browser, and write setup/design/evidence/report drafts.
- **Model:** The session identifies this coding agent as GPT-6-based Codex. An exact selectable backend model/version is not exposed in the available session metadata; no more specific model name is asserted.
- **Tools:** Local Python/Node/Git tooling; web access for official yfinance/TradingView references; computer/browser inspection for the localhost app; pytest and Playwright for automated checks; Prettier for readable frontend formatting. No subagents were used.
- **App AI integrations:** None. Market/model/audio services are separate assignment stages. This version sends only watchlist symbols/market-data requests to Yahoo; it sends no market or account context to an AI decision service.
- **Revised approaches:** macOS certificate resolution was fixed with a trusted CA bundle. Missing streamed after-hours volume was changed from an apparent zero to an unavailable value. A small yfinance listener adapter makes close/retry behavior observable. See `docs/evidence.md`.
- **Student ownership:** Generated code has not yet been independently reviewed or explained by the student in this session. Before submission, the student should trace `receive → ingest → current → candles → WebSocket → Vue`, explain revision/as-of behavior and partial volume, run the app, and record the demonstration. Do not claim that student review or recording has already happened.
