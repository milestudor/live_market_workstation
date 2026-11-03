# Meridian · Live Market Workstation

A local Vue + FastAPI + SQLite market workstation for Assignment **4.1**. Yahoo Finance observations travel through the backend to a candlestick/volume chart over WebSockets and remain available for receipt-order replay.

**Scope:** market observation, persistence, and replay. No indicators, trading, backtests, model decisions, chat, vision, or audio yet. Those belong to 4.2–4.3. No real orders or credentials are used.

## Start on macOS / Linux

Prerequisites: Python **3.13**, Node **24**, npm, internet access for installation and Yahoo data.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
./scripts/dev.sh
```

Open **http://127.0.0.1:5173**. FastAPI runs at port 8000; its interactive API documentation is at http://127.0.0.1:8000/docs. Stop the foreground script with Control-C to stop both services. Servers bind to loopback only.

The backend **creates `data/market.sqlite3` and its schema automatically** on first startup. No manual SQL, API key, `.env`, or Yahoo login is required. SQLite files, local environments, and test artifacts are ignored by Git. Do not run multiple backend processes against the same database.

For a single-server build:

```sh
cd frontend
npm run build
cd ..
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000. Build the frontend **before** starting this server.

## Using the workstation

- Select AAPL, MSFT, NVDA, AMZN, or SPY in the watchlist. This is an illustrative observation set, not investment advice.
- Select 1-, 5-, or 15-minute candles. Pan/zoom the chart, hover for OHLC/volume, and use **Fit chart to data** to reset the view. Axis labels and tooltips use Eastern time; storage uses UTC epoch seconds.
- Check **upstream feed**, **browser connection**, **source age**, **source timestamp**, and **receipt timestamp** separately. Connected transport does not prove current source data. Age over 60 seconds is flagged; this threshold is a display policy, not a provider latency guarantee.
- The quote change is relative to the first open in the loaded chart window (up to 600 bars), **not previous-day close**. Watchlist values remain current while the selected chart is in Replay.
- Use **Replay** beneath the chart to scrub stored receipts, play/pause, restart, change playback speed, or export the latest receipt window as JSON. Speed means 1, 10, or 50 receipts per 400 ms, not simulated market seconds. Replay is not a backtest.
- The replay slider covers the latest **2,000 receipts** for the selected symbol. Earlier records still supply as-of context. The chart shows at most 600 aggregated bars. All underlying observations remain in SQLite.
- **Help** explains provenance, partial coverage, volume availability, revisions, and replay behavior.

## Honest data boundaries

Yahoo history supplies two days of unadjusted regular-session minute bars at startup. The asynchronous Yahoo price stream supplies observations thereafter; there is no fake live fallback. History and streaming have different provenance. A streamed bucket replaces overlapping historical data and is labeled partial: it contains only captured ticks. No missing candles are fabricated.

Yahoo can omit `day_volume`, particularly in after-hours messages. Missing volume stays **unavailable**, not zero. When cumulative volume is supplied, the first reading is a baseline; later nonnegative differences are attributed to the later observation's bucket. The baseline resets on a new Eastern calendar day or counter reset. This is an approximation, not an exchange trade tape. Historical volume remains available on historical bars.

“Forming” indicates an unsettled interval. “Interval ended” indicates its boundary has passed; it does **not** guarantee full market coverage. Historical source timestamps identify interval starts. Stream timestamps identify price observation times. A still-provisional historical bar is not silently promoted to a final provider value merely because wall time advances.

Yahoo has no unique trade ID in this feed. Identity uses source + kind + symbol + timestamp at millisecond precision. A different payload with the same identity is a revision; distinct trades at an identical timestamp could be collapsed. Raw messages and immutable revisions preserve the evidence for inspection. See [design notes](docs/design.md).

## Offline operation and tests

To revisit your own saved Yahoo data without contacting Yahoo:

```sh
MARKET_LIVE=0 ./scripts/dev.sh
```

For reproducible **synthetic test data**, use a NEW isolated path (the seed refuses to overwrite an existing file):

```sh
mkdir -p work
.venv/bin/python scripts/seed_fixture.py --db work/browser.sqlite3
MARKET_LIVE=0 MARKET_DB=work/browser.sqlite3 ./scripts/dev.sh
```

The application identifies fixture provenance as **Synthetic fixture**. Never present fixture tests as proof of a live provider connection. The normal startup does not seed synthetic data.

Run automated checks:

```sh
.venv/bin/python -m pytest -q
cd frontend
npm run build
npx playwright install chromium
# Seed ../work/browser.sqlite3 once from the repository root first.
npm run test:e2e
```

Browser tests use an isolated offline backend at port 8010. They cover symbol search, interval selection, replay controls, export, help, offline messaging, client errors, and responsive overflow. GitHub Actions runs backend checks, the build, and desktop/mobile browser tests on pushes and pull requests.

Optional environment variables: `MARKET_LIVE=0` disables Yahoo calls; `MARKET_DB=/absolute/path/file.sqlite3` chooses a database; `SSL_CERT_FILE` can supply an existing trusted CA bundle. The app defaults the latter to certifi's bundle to support Python.org macOS installations while retaining TLS verification.

## Documents and evidence

- [Architecture, schema, and data policies](docs/design.md)
- [Verification and curated AI evidence](docs/evidence.md)
- [AI-use disclosure](AI-USE.md)
- [Agent instructions](AGENTS.md)
- [Part 4.1 report draft](report.md)
- [30–60 second demo checklist](docs/demo.md)

The report still needs an accessible demonstration video and the student's review. Upload **only `report.md`** to Canvas. Do not upload source files, SQLite data, or ZIP files.

## Sources and attribution

- [Assignment reference: TradingView](https://www.tradingview.com/chart/)
- [Lightweight Charts documentation](https://tradingview.github.io/lightweight-charts/docs) and [repository](https://github.com/tradingview/lightweight-charts)
- [yfinance documentation](https://ranaroussi.github.io/yfinance/) and [streaming documentation](https://ranaroussi.github.io/yfinance/reference/yfinance.websocket.html)
- [yfinance on PyPI](https://pypi.org/project/yfinance/)
- [Finnhub reference](https://finnhub.io/docs/api) (not integrated; Yahoo remains the required live source)

Charts use TradingView Lightweight Charts™. Copyright © 2025 TradingView, Inc. https://www.tradingview.com/ . The built-in attribution logo and visible TradingView link remain enabled. The application references their chart library, not TradingView's hosted data feed. yfinance is independent of and not endorsed by Yahoo. Review the providers' data terms; this project is for local educational use.
