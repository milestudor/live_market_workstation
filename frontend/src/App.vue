<script setup>
import {
  ref,
  computed,
  onMounted,
  onBeforeUnmount,
  watch,
  nextTick,
} from "vue";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  ColorType,
} from "lightweight-charts";
import {
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Radio,
  Database,
  Clock3,
  Play,
  Pause,
  RotateCcw,
  Maximize2,
  Crosshair,
  WifiOff,
  CircleHelp,
  X,
  Layers,
  ChevronRight,
  Download,
} from "lucide-vue-next";

const selected = ref("AAPL"),
  interval = ref(60),
  mode = ref("live");
const watchlist = ref([]),
  snapshot = ref({ candles: [] }),
  status = ref({ state: "connecting", stats: {} });
const transport = ref("connecting"),
  error = ref(""),
  help = ref(false),
  query = ref("");
const modalEl = ref(null);
let previousFocus;
watch(help, async (value) => {
  if (value) {
    previousFocus = document.activeElement;
    await nextTick();
    modalEl.value?.querySelector("button")?.focus();
  } else {
    previousFocus?.focus();
  }
});
function trapFocus(e) {
  if (e.key !== "Tab") return;
  const buttons = modalEl.value.querySelectorAll("button");
  const first = buttons[0],
    last = buttons[buttons.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    last.focus();
    e.preventDefault();
  } else if (!e.shiftKey && document.activeElement === last) {
    first.focus();
    e.preventDefault();
  }
}
const chartEl = ref(null),
  events = ref([]),
  cursor = ref(0),
  playing = ref(false),
  speed = ref(10);
const replayBusy = ref(false),
  now = ref(Date.now() / 1000),
  hover = ref(null);
let chart,
  candleSeries,
  volumeSeries,
  socket,
  reconnect,
  heartbeat,
  playback,
  disposed = false,
  replayRequest = 0;
const formatPrice = (v) =>
  v == null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(v);
const number = (v) =>
  v == null
    ? "—"
    : Intl.NumberFormat("en-US", {
        notation: "compact",
        maximumFractionDigits: 1,
      }).format(v);
const datetime = (v) =>
  v
    ? new Date(v * 1000).toLocaleString("en-US", {
        timeZone: "America/New_York",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }) + " ET"
    : "No observations yet";
const active = computed(
  () =>
    watchlist.value.find((x) => x.symbol === selected.value) || {
      name: "Apple Inc.",
      sector: "Technology",
    },
);
const shownWatchlist = computed(() =>
  watchlist.value.filter((x) =>
    (x.symbol + " " + x.name).toLowerCase().includes(query.value.toLowerCase()),
  ),
);
const last = computed(() => snapshot.value.candles?.at(-1));
const inspected = computed(() => hover.value || last.value);
const sourceAge = computed(() =>
  snapshot.value.source_time
    ? Math.max(
        0,
        Math.floor(
          (mode.value === "replay" ? snapshot.value.as_of_time : now.value) -
            snapshot.value.source_time,
        ),
      )
    : null,
);
const ageLabel = computed(() =>
  sourceAge.value === null
    ? "No data"
    : sourceAge.value < 60
      ? `${sourceAge.value}s ago`
      : sourceAge.value < 3600
        ? `${Math.floor(sourceAge.value / 60)}m ago`
        : `${Math.floor(sourceAge.value / 3600)}h ago`,
);
const stale = computed(() => sourceAge.value === null || sourceAge.value > 60);
const stateLabel = computed(
  () =>
    ({
      connecting: "Connecting",
      connected: "Receiving",
      waiting: "Awaiting updates",
      quiet: "Feed quiet",
      unavailable: "Feed unavailable",
      disabled: "Offline mode",
    })[status.value.state] || "Unavailable",
);
const rising = computed(() => (snapshot.value.change ?? 0) >= 0);
const replayEvent = computed(() => events.value[cursor.value]);
const banner = computed(
  () =>
    error.value ||
    (transport.value === "disconnected"
      ? "Connection to the local server lost. Reconnecting automatically."
      : status.value.state === "unavailable"
        ? status.value.detail
        : status.value.state === "disabled"
          ? "Live feed is disabled. Explore stored observations in Replay."
          : mode.value === "live" && stale.value && snapshot.value.source_time
            ? "Source data is older than 60 seconds. Markets may be closed or the feed may be delayed."
            : ""),
);

async function get(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}
function renderChart(fit = false) {
  if (!chart) return;
  const data = snapshot.value.candles || [];
  candleSeries.setData(
    data.map(({ time, open, high, low, close }) => ({
      time,
      open,
      high,
      low,
      close,
    })),
  );
  volumeSeries.setData(
    data.map((b) =>
      b.volume == null
        ? { time: b.time }
        : {
            time: b.time,
            value: b.volume,
            color: b.close >= b.open ? "#39c5a445" : "#ef778345",
          },
    ),
  );
  if (fit && data.length) chart.timeScale().fitContent();
}
function connect() {
  clearTimeout(reconnect);
  if (socket) {
    socket.onclose = null;
    socket.onmessage = null;
    socket.onopen = null;
    socket.onerror = null;
    socket.close();
  }
  transport.value = "connecting";
  const ws = new WebSocket(
    `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/market?symbol=${selected.value}&interval=${interval.value}`,
  );
  socket = ws;
  ws.onopen = () => {
    transport.value = "connected";
    error.value = "";
  };
  ws.onmessage = (e) => {
    const message = JSON.parse(e.data);
    status.value = message.status;
    watchlist.value = message.watchlist;
    if (mode.value === "live") {
      const fit = !snapshot.value.candles?.length;
      snapshot.value = message.data;
      renderChart(fit);
    }
  };
  ws.onclose = () => {
    if (disposed) return;
    transport.value = "disconnected";
    reconnect = setTimeout(connect, 3000);
  };
  ws.onerror = () => {
    transport.value = "disconnected";
  };
}
async function changeMode(value) {
  playing.value = false;
  mode.value = value;
  hover.value = null;
  error.value = "";
  ++replayRequest;
  if (value === "replay") {
    events.value = [];
    cursor.value = 0;
    try {
      const symbol = selected.value;
      const result = await get(`/api/events/${symbol}`);
      if (mode.value !== "replay" || selected.value !== symbol) return;
      events.value = result.events;
      cursor.value = 0;
      await seek(true);
    } catch (e) {
      error.value = e.message;
    }
  } else {
    events.value = [];
    snapshot.value = { candles: [] };
    connect();
  }
}
async function seek(fit = false) {
  const request = ++replayRequest,
    symbol = selected.value;
  replayBusy.value = true;
  try {
    const result = await get(
      `/api/snapshot/${symbol}?interval=${interval.value}&as_of=${replayEvent.value?.seq || 0}`,
    );
    if (
      request !== replayRequest ||
      mode.value !== "replay" ||
      selected.value !== symbol
    )
      return;
    snapshot.value = result;
    hover.value = null;
    renderChart(true);
  } catch (e) {
    if (request === replayRequest) error.value = e.message;
  } finally {
    if (request === replayRequest) replayBusy.value = false;
  }
}
async function select(symbol) {
  selected.value = symbol;
  playing.value = false;
  hover.value = null;
  snapshot.value = { candles: [] };
  renderChart();
  connect();
  if (mode.value === "replay") await changeMode("replay");
}
async function changeInterval(value) {
  interval.value = value;
  hover.value = null;
  if (mode.value === "replay") await seek(true);
  else {
    snapshot.value = { candles: [] };
    connect();
  }
}
function togglePlayback() {
  if (cursor.value >= events.value.length - 1) cursor.value = 0;
  playing.value = !playing.value;
}
function exportRecords() {
  const blob = new Blob(
    [
      JSON.stringify(
        {
          symbol: selected.value,
          mode: mode.value,
          observations: events.value,
        },
        null,
        2,
      ),
    ],
    { type: "application/json" },
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `meridian-${selected.value}-receipts.json`;
  a.click();
  URL.revokeObjectURL(url);
}
onMounted(async () => {
  chart = createChart(chartEl.value, {
    autoSize: true,
    layout: {
      background: { type: ColorType.Solid, color: "#10141d" },
      textColor: "#7e8a9f",
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      fontSize: 11,
      attributionLogo: true,
    },
    grid: {
      vertLines: { color: "#1b223035" },
      horzLines: { color: "#232b3945" },
    },
    rightPriceScale: {
      borderColor: "#252d3a",
      scaleMargins: { top: 0.12, bottom: 0.24 },
    },
    timeScale: {
      borderColor: "#252d3a",
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 5,
      tickMarkFormatter: (t, type) =>
        new Date(t * 1000).toLocaleString("en-US", {
          timeZone: "America/New_York",
          ...(type <= 2
            ? { month: "short", day: "numeric" }
            : { hour: "2-digit", minute: "2-digit", hour12: false }),
        }),
    },
    crosshair: {
      mode: 0,
      vertLine: { color: "#677386", labelBackgroundColor: "#323e50" },
      horzLine: { color: "#677386", labelBackgroundColor: "#323e50" },
    },
    localization: {
      locale: "en-US",
      timeFormatter: (t) =>
        new Date(t * 1000).toLocaleString("en-US", {
          timeZone: "America/New_York",
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        }) + " ET",
    },
  });
  candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: "#3bc7a5",
    downColor: "#ec7886",
    borderVisible: false,
    wickUpColor: "#3bc7a5",
    wickDownColor: "#ec7886",
  });
  volumeSeries = chart.addSeries(HistogramSeries, {
    priceFormat: { type: "volume" },
    priceScaleId: "volume",
    lastValueVisible: false,
    priceLineVisible: false,
  });
  chart
    .priceScale("volume")
    .applyOptions({ scaleMargins: { top: 0.82, bottom: 0 }, visible: false });
  chart.subscribeCrosshairMove((p) => {
    hover.value =
      snapshot.value.candles?.find((b) => b.time === p.time) || null;
  });
  try {
    watchlist.value = await get("/api/watchlist");
  } catch (e) {
    error.value = e.message;
  }
  connect();
  heartbeat = setInterval(() => (now.value = Date.now() / 1000), 1000);
  playback = setInterval(async () => {
    if (!playing.value || replayBusy.value) return;
    if (cursor.value >= events.value.length - 1) {
      playing.value = false;
      return;
    }
    cursor.value = Math.min(
      events.value.length - 1,
      cursor.value + Number(speed.value),
    );
    await seek();
  }, 400);
});
onBeforeUnmount(() => {
  disposed = true;
  ++replayRequest;
  clearInterval(heartbeat);
  clearInterval(playback);
  clearTimeout(reconnect);
  socket?.close();
  chart?.remove();
});
</script>

<template>
  <div class="workstation">
    <aside class="rail" aria-label="Workspace navigation">
      <a href="/" class="brand-mark" aria-label="Meridian home"
        ><Activity :size="23"
      /></a>
      <div class="rail-divider"></div>
      <button
        class="rail-button active"
        title="Market workstation"
        aria-label="Market workstation"
      >
        <Layers :size="20" /></button
      ><button
        class="rail-button"
        title="About this workstation"
        aria-label="About this workstation"
        @click="help = true"
      >
        <CircleHelp :size="20" /></button
      ><span class="rail-bottom">M.</span>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <div class="wordmark">MERIDIAN<span>MARKET WORKSTATION</span></div>
        <div class="top-actions">
          <span class="local-badge"><i></i> LOCAL WORKSPACE</span
          ><span class="header-divider"></span
          ><button
            class="icon-button"
            aria-label="Help and data notes"
            @click="help = true"
          >
            <CircleHelp :size="18" />
          </button>
          <div class="avatar">MT</div>
        </div>
      </header>
      <main>
        <div class="page-heading">
          <div>
            <div class="eyebrow">YOUR MARKET, IN FOCUS</div>
            <h1>Market overview<span class="title-dot">.</span></h1>
            <p>A clear view of the market. A record of every observation.</p>
          </div>
          <div class="session-info">
            <span
              class="session-dot"
              :class="{ good: status.state === 'connected' }"
            ></span>
            <div>
              <strong>{{ stateLabel }}</strong
              ><span>Yahoo Finance · US watchlist</span>
            </div>
          </div>
        </div>
        <div class="market-layout">
          <section class="chart-card">
            <div class="instrument-bar">
              <div class="instrument-title">
                <div class="stock-logo" :style="{ color: active.color }">
                  {{ selected.slice(0, 1) }}
                </div>
                <div>
                  <h2>
                    {{ selected }} <span>{{ active.name }}</span>
                  </h2>
                  <p>{{ active.sector }}<span>·</span>USD</p>
                </div>
              </div>
              <div class="instrument-label">
                MARKET OBSERVATION <Radio :size="13" />
              </div>
            </div>
            <div class="quote-row">
              <div class="quote">
                <strong>{{ formatPrice(snapshot.price) }}</strong
                ><span :class="rising ? 'positive' : 'negative'">
                  <ArrowUpRight v-if="rising" :size="15" /><ArrowDownRight
                    v-else
                    :size="15"
                  />{{
                    snapshot.change == null
                      ? "—"
                      : `${rising ? "+" : ""}${snapshot.change.toFixed(2)}%`
                  }}<small>chart window</small></span
                >
              </div>
              <span class="source-chip" :class="{ warning: stale }"
                ><Clock3 :size="12" />{{
                  snapshot.source === "fixture-synthetic"
                    ? "Fixture · "
                    : mode === "replay"
                      ? "Recorded · "
                      : ""
                }}{{ ageLabel }}</span
              >
            </div>
            <div class="chart-toolbar">
              <div class="timeframes">
                <button
                  v-for="[value, label] in [
                    [60, '1m'],
                    [300, '5m'],
                    [900, '15m'],
                  ]"
                  :key="value"
                  :class="{ selected: interval === value }"
                  @click="changeInterval(value)"
                >
                  {{ label }}</button
                ><span class="tool-divider"></span
                ><span class="chart-type"><Activity :size="14" /> Candles</span>
              </div>
              <div class="chart-tools">
                <span>Price & volume</span
                ><button
                  class="icon-button"
                  aria-label="Fit chart to data"
                  title="Fit chart to data"
                  @click="chart.timeScale().fitContent()"
                >
                  <Maximize2 :size="15" />
                </button>
              </div>
            </div>
            <div class="ohlc">
              <template v-if="inspected"
                ><span
                  v-for="[key, label] in [
                    ['open', 'O'],
                    ['high', 'H'],
                    ['low', 'L'],
                    ['close', 'C'],
                  ]"
                  :key="key"
                  >{{ label }}
                  <b
                    :class="
                      key === 'close'
                        ? inspected.close >= inspected.open
                          ? 'positive'
                          : 'negative'
                        : ''
                    "
                    >{{ formatPrice(inspected[key]) }}</b
                  ></span
                ><span class="volume-readout"
                  >Vol <b>{{ number(inspected.volume) }}</b></span
                ><span
                  class="bar-tag"
                  :class="{ provisional: !inspected.complete }"
                  >{{ inspected.complete ? "Interval ended" : "Forming" }}</span
                ></template
              ><span v-else>Waiting for market observations</span>
            </div>
            <div class="chart-wrap">
              <div ref="chartEl" class="chart-canvas"></div>
              <div v-if="!snapshot.candles?.length" class="empty-chart">
                <Activity :size="32" />
                <h3>
                  {{
                    mode === "replay"
                      ? "No recorded observations yet"
                      : "Waiting for the first observation"
                  }}
                </h3>
                <p>
                  {{
                    mode === "replay"
                      ? "Run the live feed to save observations for replay."
                      : "Yahoo data will appear here when available."
                  }}
                </p>
                <span>Saved data stays available if the feed is offline.</span>
              </div>
              <div class="chart-watermark" aria-hidden="true">
                {{ selected
                }}<span
                  >{{ interval / 60 }} MIN ·
                  {{
                    snapshot.source === "fixture-synthetic"
                      ? "SYNTHETIC FIXTURE"
                      : "YAHOO FINANCE"
                  }}</span
                >
              </div>
            </div>
            <div class="chart-footnote">
              <span
                ><i class="volume-dot"></i>Volume
                <span class="muted">{{
                  last?.coverage || "No coverage yet"
                }}</span></span
              ><span>Chart times: ET</span>
            </div>
            <div class="playback-panel">
              <div class="playback-top">
                <div class="mode-switch" aria-label="Data mode">
                  <button
                    :class="{ active: mode === 'live' }"
                    @click="changeMode('live')"
                  >
                    <Radio :size="13" /> Live</button
                  ><button
                    :class="{ active: mode === 'replay' }"
                    @click="changeMode('replay')"
                  >
                    <RotateCcw :size="13" /> Replay
                  </button>
                </div>
                <span class="recording-label"
                  ><i
                    :class="{
                      recording:
                        mode === 'live' && status.state === 'connected',
                    }"
                  ></i
                  >{{
                    mode === "live"
                      ? "Observations saved to SQLite"
                      : `${events.length.toLocaleString()} saved receipts · latest window`
                  }}</span
                >
              </div>
              <div v-if="mode === 'live'" class="live-explainer">
                <div class="mini-wave">
                  <span></span><span></span><span></span><span></span
                  ><span></span>
                </div>
                <div>
                  <strong>Follow the feed. Keep the history.</strong>
                  <p>
                    Switch to Replay to revisit exactly what the workstation
                    received.
                  </p>
                </div>
                <ChevronRight :size="18" />
              </div>
              <div v-else class="replay-controls">
                <button
                  class="icon-button"
                  aria-label="Restart replay"
                  :disabled="!events.length"
                  @click="
                    cursor = 0;
                    playing = false;
                    seek(true);
                  "
                >
                  <RotateCcw :size="16" /></button
                ><button
                  class="play-button"
                  :disabled="!events.length"
                  :aria-label="playing ? 'Pause replay' : 'Play replay'"
                  @click="togglePlayback"
                >
                  <Pause v-if="playing" :size="16" /><Play v-else :size="16" />
                </button>
                <div class="scrubber">
                  <input
                    aria-label="Replay position"
                    type="range"
                    min="0"
                    :max="Math.max(0, events.length - 1)"
                    v-model.number="cursor"
                    :disabled="!events.length"
                    @input="
                      playing = false;
                      seek();
                    "
                  /><span
                    >{{ datetime(replayEvent?.receipt_time)
                    }}<b
                      >{{ events.length ? cursor + 1 : 0 }} /
                      {{ events.length }}</b
                    ></span
                  >
                </div>
                <select aria-label="Replay speed" v-model="speed">
                  <option :value="1">1 receipt</option>
                  <option :value="10">10 receipts</option>
                  <option :value="50">50 receipts</option></select
                ><button
                  class="icon-button"
                  aria-label="Export replay receipts"
                  :disabled="!events.length"
                  @click="exportRecords"
                >
                  <Download :size="17" />
                </button>
              </div>
            </div>
          </section>
          <aside class="right-column">
            <section class="watchlist-card">
              <div class="panel-heading">
                <h2>Watchlist <span>05</span></h2>
                <span class="tiny-label">{{
                  mode === "replay" ? "LIVE WATCHLIST" : "US MARKET"
                }}</span>
              </div>
              <div class="watch-search">
                <Crosshair :size="14" /><input
                  aria-label="Filter watchlist"
                  v-model="query"
                  placeholder="Find a symbol…"
                /><span>/</span>
              </div>
              <div class="watch-columns">
                <span>SYMBOL / NAME</span><span>PRICE / CHANGE</span>
              </div>
              <button
                class="watch-row"
                v-for="item in shownWatchlist"
                :key="item.symbol"
                :class="{ chosen: item.symbol === selected }"
                @click="select(item.symbol)"
              >
                <span
                  class="watch-icon"
                  :style="{ color: item.color, background: item.color + '12' }"
                  >{{ item.symbol.slice(0, 1) }}</span
                ><span class="watch-name"
                  ><strong>{{ item.symbol }}</strong
                  ><small>{{ item.name }}</small></span
                ><span class="watch-price"
                  ><strong>{{ formatPrice(item.price) }}</strong
                  ><small
                    :class="(item.change ?? 0) >= 0 ? 'positive' : 'negative'"
                    >{{
                      item.change == null
                        ? "No observations"
                        : `${item.change >= 0 ? "+" : ""}${item.change.toFixed(2)}%`
                    }}</small
                  ></span
                >
              </button>
              <div v-if="!shownWatchlist.length" class="no-results">
                No matching symbols
              </div>
              <div class="watchlist-note">
                <Clock3 :size="12" /><span
                  >Changes measured across the chart window.<br />Quotes can be
                  delayed; check source age.</span
                >
              </div>
            </section>
            <section class="feed-card">
              <div class="panel-heading">
                <h2>Data connection</h2>
                <span
                  class="status-pip"
                  :class="{ good: status.state === 'connected' }"
                ></span>
              </div>
              <div class="connection-route">
                <div class="route-icon"><Radio :size="19" /></div>
                <div>
                  <strong>Yahoo Finance</strong
                  ><span>Streaming price observations</span>
                </div>
              </div>
              <dl class="connection-details">
                <div>
                  <dt>Upstream feed</dt>
                  <dd
                    :class="status.state === 'connected' ? 'positive' : 'amber'"
                  >
                    {{ stateLabel }}
                  </dd>
                </div>
                <div>
                  <dt>Browser connection</dt>
                  <dd>
                    {{
                      transport === "connected"
                        ? "Connected"
                        : transport === "connecting"
                          ? "Connecting"
                          : "Reconnecting"
                    }}
                  </dd>
                </div>
                <div>
                  <dt>Selected source</dt>
                  <dd>
                    {{
                      snapshot.source === "yahoo-stream"
                        ? "Yahoo stream"
                        : snapshot.source === "yahoo-history"
                          ? "Yahoo history"
                          : snapshot.source === "fixture-synthetic"
                            ? "Synthetic fixture"
                            : "—"
                    }}
                  </dd>
                </div>
                <div>
                  <dt>Source age</dt>
                  <dd :class="{ amber: stale }">{{ ageLabel }}</dd>
                </div>
              </dl>
              <div class="feed-timestamp">
                <Clock3 :size="13" /><span
                  >Source timestamp<strong>{{
                    datetime(snapshot.source_time)
                  }}</strong
                  ><span class="receipt-note"
                    >Received {{ datetime(snapshot.receipt_time) }}</span
                  ></span
                >
              </div>
            </section>
          </aside>
        </div>
        <div v-if="banner" class="notice" role="status">
          <WifiOff :size="15" /><span>{{ banner }}</span
          ><button class="text-button" @click="connect">Reconnect</button>
        </div>
        <section class="records-strip">
          <div class="records-title">
            <div class="database-icon"><Database :size="19" /></div>
            <div>
              <h2>A persistent market record</h2>
              <p>Source time. Receipt time. Every revision.</p>
            </div>
          </div>
          <div class="record-metric">
            <span>OBSERVATIONS</span
            ><strong>{{ number(status.stats?.observations ?? 0) }}</strong>
          </div>
          <div class="record-metric">
            <span>RECEIPTS</span
            ><strong>{{ number(status.stats?.deliveries ?? 0) }}</strong>
          </div>
          <div class="record-metric">
            <span>DUPLICATES</span
            ><strong>{{ number(status.stats?.duplicates ?? 0) }}</strong>
          </div>
          <div class="record-metric">
            <span>REVISIONS</span
            ><strong>{{ number(status.stats?.revisions ?? 0) }}</strong>
          </div>
          <button class="text-button" @click="help = true">
            How data is stored <ArrowUpRight :size="14" />
          </button>
        </section>
        <footer>
          <span>MERIDIAN <i>/</i> Local market workstation</span
          ><span
            >Observation & replay · Part 4.1 <i>·</i> No trading enabled</span
          ><a
            href="https://www.tradingview.com/"
            target="_blank"
            rel="noreferrer"
            >TradingView Lightweight Charts™ © 2025 TradingView, Inc.</a
          >
        </footer>
      </main>
    </div>
    <div class="modal-backdrop" v-if="help" @click.self="help = false">
      <section
        class="help-modal"
        ref="modalEl"
        @keydown="trapFocus"
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-title"
        @keydown.esc="help = false"
        tabindex="-1"
      >
        <button
          class="icon-button modal-close"
          aria-label="Close help"
          @click="help = false"
        >
          <X :size="20" />
        </button>
        <div class="eyebrow">WORKSTATION NOTES</div>
        <h2 id="help-title">Know what you’re looking at.</h2>
        <p>
          Meridian records Yahoo Finance observations locally. It is an
          educational market viewer; Part 4.1 has no orders, strategies, or AI
          decisions.
        </p>
        <h3>Live doesn’t always mean current</h3>
        <p>
          The Yahoo connection can be open while an instrument is quiet or
          closed. Source age measures time since the selected observation’s
          source timestamp. Historical bar timestamps mark the start of the
          interval.
        </p>
        <h3>Price & volume coverage</h3>
        <p>
          Historical bars seed the chart. Streamed buckets replace overlapping
          history and show only observed ticks. Their OHLC and cumulative-volume
          deltas can be partial. When Yahoo omits volume, it is shown as
          unavailable rather than zero. The first cumulative-volume reading
          establishes a baseline; it contributes no volume. “Interval ended”
          describes time, not complete market coverage. There is no
          interpolation across gaps.
        </p>
        <h3>Receipts, revisions & replay</h3>
        <p>
          SQLite keeps immutable versions and every delivery receipt. Identical
          consecutive observations count as duplicates. Changed values at the
          same source timestamp create revisions. Yahoo supplies no unique trade
          ID: same-timestamp messages are treated as revisions, which may
          collapse distinct trades. Replay uses only records received by the
          selected receipt, with no later revisions.
        </p>
        <h3>Replay controls</h3>
        <p>
          The timeline contains the latest 2,000 receipts for a symbol. Play
          advances every 400 ms at the selected receipt count; this is
          accelerated observation replay, not a backtest or original-time
          playback. Earlier saved context remains visible.
        </p>
        <p class="help-history">{{ status.history }}</p>
        <button class="primary-button" @click="help = false">
          Back to the market
        </button>
      </section>
    </div>
  </div>
</template>
