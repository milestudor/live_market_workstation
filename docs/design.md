# Design notes · Part 4.1

## Intent and interface

Meridian borrows the useful workstation hierarchy from TradingView: selected instrument and quote, central candlestick/volume chart, interval controls, adjacent watchlist, and connection details. The dark slate palette uses teal and rose for price direction and amber for stale/unavailable data. Live/Replay controls sit below the chart as requested. The layout stacks panels on small windows. Search, controls, help focus management, and responsive browser checks support keyboard and smaller-screen use.

The frontend uses Vue 3 and TradingView Lightweight Charts 5; FastAPI owns external connections and data policy; SQLite owns durable evidence. The chart library supplies candlesticks, histograms, pan/zoom, crosshair, and price/time scales. It does not supply market data. This local app has no orders or AI endpoint. Future features can consume the same normalized snapshots without placing strategy logic in chart components.

## Data flow

1. FastAPI creates the SQLite schema and starts two tasks.
2. Startup history requests use `yfinance.Ticker.history`, two days, one-minute, `auto_adjust=False`. Blocking provider work runs in a worker thread; returned rows are ingested on the async task. History requests run per symbol; failures do not remove stored data.
3. The Yahoo stream subscribes to the five-symbol watchlist with `yfinance.AsyncWebSocket`. `backend/feed.py` owns message iteration, using the pinned package's socket and protobuf decoder. This small adapter deliberately avoids the package listener's internal indefinite reconnect loop so the app controls retries and can detect a closed socket. Its private `_ws` and `_decode_message` dependencies must be rechecked on a package upgrade.
4. The callback validates symbols, numeric prices/volume, and timestamps. Yahoo milliseconds become UTC seconds. Raw decoded messages are retained in the tick payload. Invalid messages are rejected; no chart or database entry is invented.
5. `Store.ingest` writes an immutable observation version (or recognizes an identical latest version) and a delivery receipt in one SQLite transaction.
6. The local `/ws/market` endpoint sends the selected symbol's snapshot, watchlist quotes, feed state, and database counters every second. This is a transport cadence, not an assertion that Yahoo sent new data every second.
7. Vue renders data using source timestamps and updates source age separately from connection state. It shows historical vs streaming provenance and partial or unavailable streamed volume.
8. Replay fetches receipt metadata and requests an as-of snapshot through HTTP. The upstream feed continues recording; the chart remains pinned to the selected historical receipt until Live is selected.

One backend process is supported. Read-only API work may run in FastAPI's thread pool; SQLite uses `check_same_thread=False`. All production ingestion is serialized by async backend tasks, and SQLite transactions contain the version + receipt pair. SQLite WAL and foreign keys are enabled. Do not run multiple workers or a separate writer against the same live database. There is no authentication because access is loopback-only; WebSocket Origin checks reject other websites. HTTP APIs expose no application write route. Frontend and backend share an origin through Vite's proxy or FastAPI static serving.

## SQLite schema

`observations`:

| Column | Meaning |
| --- | --- |
| `id` | Local immutable version key |
| `identity` | `source:kind:symbol:source_time` rounded to millisecond precision |
| `revision` | Consecutive version number within an identity |
| `symbol`, `source`, `kind` | Instrument, provenance, and `tick`/`bar` |
| `source_time` | Provider observation time, UTC seconds; historical bars use interval start |
| `received_time` | First local receipt of this version, UTC seconds |
| `payload` | Canonical JSON: OHLCV + provider completion for history, price/cumulative volume/raw message for stream |
| `fingerprint` | SHA-256 of the canonical payload |

`UNIQUE(identity, revision)` prevents duplicate version numbers; indexes support symbol and identity lookups.

`deliveries`:

| Column | Meaning |
| --- | --- |
| `seq` | Monotonic local receipt sequence; authoritative replay cursor |
| `observation_id` | Foreign key to the delivered immutable version |
| `received_time` | Time of this delivery, including duplicate deliveries |
| `duplicate` | Whether this delivery matched the identity's latest payload |

A bar payload preserves its provider-derived `complete` flag. Stream candles are deterministic derived views over stored tick versions; their time-boundary finality is calculated at the live clock or replay receipt time, not stored as a provider guarantee. The raw timestamps and revisions needed to recreate that state remain durable.

There is no manual database initialization. A new database gets the schema automatically. There is no destructive reset endpoint or automatic pruning. Schema migrations are not yet needed for the initial version; add an explicit migration before changing an existing schema.

## Identity and revision policy

- Identical latest payload and identity: reuse the version and append a receipt marked duplicate. This cannot inflate candle price or volume.
- Different payload, same identity: append a revision and its receipt. This includes changes to ancillary raw fields as well as prices. Do not update an earlier row in place.
- Reversion from A to B to A: append a third version. A hash match against any older revision does not erase the intervening change.
- Out-of-order arrival: retain receipt order, but rebuild candles in provider/source-time order. A late tick can change open/high/low/close and observed volume. Replay before its receipt still shows the earlier view.
- Yahoo has no stable unique trade ID here. Same-symbol, same-timestamp distinct events may be treated as revisions. The assignment's identity requirement is met by a documented local policy, not a claim of exchange-level event identity. Millisecond rounding is explicit; the raw timestamp is retained.

## Candles and volume

Buckets use UTC epoch floor division by 60, 300, or 900 seconds. Prices are sorted by source time; open and close use the first/last observation; high and low are extrema. Historical minute bars can aggregate into longer intervals. Streamed buckets replace overlapping historical buckets to avoid double-counting volume or presenting mixed coverage as complete.

A streamed candle is provisional until the bucket boundary; its ended state says nothing about total market coverage. Historical bars are final only when their provider snapshot was requested after the original minute ended and the aggregate boundary has passed. A historical current bar that was provisional is left provisional until another provider observation revises it. There is no synthesized final close.

Stream OHLC is partial: the application may have joined mid-interval, missed updates, or observed only occasional price quotes. The cumulative `day_volume` baseline is unknown until the first value arrives, so that first value contributes zero *observed delta*. Later nonnegative differences are assigned to the later sample's bucket. A date or counter reset establishes a new baseline. Missing cumulative fields do not mean zero trading: all-missing buckets have null volume, omitted from the histogram and labeled unavailable. A delta spanning a gap cannot be allocated precisely inside that gap. No candles are interpolated.

The real after-hours provider messages observed on November 3 omitted `day_volume`; the chart consequently has historical volume and unavailable streaming volume. Verify regular-session streamed volume during market hours before claiming that provider behavior. This is distinct from automated fixture tests that supply known cumulative fields.

## As-of replay and limits

The SQL query filters delivered versions by `seq <= cursor` **before** selecting the highest revision per identity. Using the newest revision first would leak future corrections. The evaluation clock becomes the selected receipt's `received_time`; a replay candle cannot become ended based on the present wall clock. Historical bars may be old market data but first become known to this workstation on their actual fetch receipt.

The slider is a receipt timeline, not original exchange timing. Replay advances fixed receipt counts every 400 ms and is not a strategy backtest. The latest 2,000 receipts are exposed to the slider/export; earlier available versions still form chart context. Charts display up to 600 bars. Database records are retained without pruning. Snapshot queries currently rebuild from all authoritative observations for a symbol, so a long-running multi-day tick archive will need indexed time-window queries, caching, or materialized bars. This small local coursework build does not claim production scale.

## Failures and verification

- Provider connection failures: visible unavailable state, retry backoff 2–30 seconds, stored data remains accessible.
- No messages for 30 seconds after receiving data: feed quiet; source age continues growing independently.
- No upstream observation for 120 seconds: fresh connection attempted. Healthy active streams are not forcibly reset on a fixed timer.
- Browser disconnect: reconnect after three seconds with a visible transport warning.
- Startup history unavailable: retain saved records; history result appears in Help. A new empty database displays a clear waiting state.
- Synthetic data: explicit fixture source, isolated file, no automatic fallback.
- TLS: use certifi's trusted CA bundle where no `SSL_CERT_FILE` was set, without disabling verification.

Tests check receipt/version policy, as-of revisions, late observations, price extrema after correction, volume boundaries, missing volume, aggregation, finality, validation, reopening SQLite, the local WebSocket route, unavailable provider behavior, and clean socket closure. Browser checks cover the controls and responsive layouts. See [evidence](evidence.md) for actual results and provider observations.
