import asyncio
from contextlib import asynccontextmanager, suppress
import os
from pathlib import Path
import time

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import certifi
import yfinance as yf

# Python.org macOS installs may lack a system CA bundle; keep TLS verification on.
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from backend.feed import YahooStream
from backend.market import SYMBOLS, WATCHLIST, candles
from backend.store import Store

ROOT = Path(__file__).resolve().parents[1]


class MarketService:
    def __init__(self, store, enabled=True):
        self.store = store
        self.enabled = enabled
        self.state = 'connecting' if enabled else 'disabled'
        self.detail = 'Connecting to Yahoo Finance' if enabled else 'Live feed disabled for offline testing'
        self.last_received = None
        self.connected_at = None
        self.history_state = 'not requested'
        self.errors = 0

    async def receive(self, message):
        try:
            symbol = message.get('id')
            if symbol not in SYMBOLS or not message.get('price') or not message.get('time'):
                return
            source_time = float(message['time']) / 1000
            now = time.time()
            if source_time > now + 300:
                raise ValueError('Source timestamp is in the future')
            payload = {'price': float(message['price']), 'day_volume': float(message['day_volume']) if message.get('day_volume') is not None else None,
                'market_hours': message.get('market_hours'), 'raw': message}
            self.store.ingest(symbol, 'yahoo-stream', 'tick', source_time, payload, now)
            self.last_received = now
            self.state, self.detail = 'connected', 'Yahoo stream receiving observations'
        except (ValueError, TypeError, OverflowError):
            self.errors += 1

    async def stream(self):
        delay = 2
        while True:
            try:
                self.state, self.detail = 'connecting', 'Connecting to Yahoo Finance'
                async with YahooStream(verbose=False) as stream:
                    await stream.subscribe(SYMBOLS)
                    self.connected_at = time.time()
                    self.state, self.detail = 'waiting', 'Subscribed; waiting for a Yahoo price update'
                    listener = asyncio.create_task(stream.listen(self.receive))
                    try:
                        while not listener.done():
                            done, _ = await asyncio.wait({listener}, timeout=15)
                            if done:
                                await listener
                                break
                            if time.time() - max(self.last_received or 0, self.connected_at) > 120:
                                raise TimeoutError('No upstream observations for 120 seconds')
                    finally:
                        listener.cancel()
                        with suppress(asyncio.CancelledError):
                            await listener
                delay = 2
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.state = 'unavailable'
                self.detail = f'Yahoo feed unavailable ({type(exc).__name__}); retrying in {delay}s'
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def history(self):
        self.history_state = 'loading'
        count = 0
        for symbol in SYMBOLS:
            try:
                frame = await asyncio.to_thread(lambda s=symbol: yf.Ticker(s).history(period='2d', interval='1m', auto_adjust=False, raise_errors=True))
                now = time.time()
                for index, row in frame.iterrows():
                    if row[['Open','High','Low','Close','Volume']].isna().any():
                        continue
                    ts = index.timestamp()
                    self.store.ingest(symbol,'yahoo-history','bar',ts,{
                        'open':float(row['Open']),'high':float(row['High']),'low':float(row['Low']),
                        'close':float(row['Close']),'volume':float(row['Volume']), 'complete':ts+60<=now},now)
                    count += 1
            except Exception:
                self.errors += 1
        self.history_state = f'{count} historical bars loaded' if count else 'Historical request unavailable; saved records remain accessible'

    def snapshot(self, symbol, interval=60, as_of=None):
        now = time.time()
        if as_of is not None:
            row = self.store.db.execute('SELECT received_time FROM deliveries WHERE seq<=? ORDER BY seq DESC LIMIT 1',(as_of,)).fetchone()
            now = row[0] if row else 0
        observations = self.store.current(symbol, as_of)
        chart = candles(observations, interval, now)
        latest = max(observations, key=lambda x:(x['source_time'],x['kind']=='tick',x['id']), default=None)
        first = chart[0]['open'] if chart else None
        price = (latest['payload'].get('price',latest['payload'].get('close')) if latest else None)
        # A historical timestamp is the interval START; never call this a live quote.
        return {'symbol':symbol,'candles':chart,'price':price,'source_time':latest['source_time'] if latest else None,
            'receipt_time':latest['received_time'] if latest else None,'source':latest['source'] if latest else None,
            'change':(price-first)/first*100 if first and price else None,'as_of_time':now,
            'mode':'replay' if as_of is not None else 'live'}

    def status(self):
        now = time.time()
        state = self.state
        if state == 'connected' and self.last_received and now-self.last_received>30:
            state = 'quiet'
        return {'state':state,'detail':self.detail,'last_received':self.last_received,
            'history':self.history_state,'rejected':self.errors,'stats':self.store.stats(),'server_time':now}


def create_app(db_path=None, live=None):
    @asynccontextmanager
    async def lifespan(app):
        store = Store(db_path or os.getenv('MARKET_DB',str(ROOT/'data/market.sqlite3')))
        enabled = (os.getenv('MARKET_LIVE','1')=='1') if live is None else live
        app.state.market = MarketService(store, enabled)
        tasks = [asyncio.create_task(app.state.market.stream()),asyncio.create_task(app.state.market.history())] if enabled else []
        yield
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        store.close()

    app = FastAPI(title='Meridian Market Workstation', lifespan=lifespan)

    def valid(symbol):
        if symbol not in SYMBOLS:
            raise HTTPException(404,'Symbol is not in the watchlist')

    @app.get('/api/status')
    def status():
        return app.state.market.status()

    @app.get('/api/watchlist')
    def watchlist():
        return WATCHLIST

    @app.get('/api/snapshot/{symbol}')
    def snapshot(symbol:str, interval:int=Query(60), as_of:int|None=Query(None,ge=0)):
        valid(symbol)
        if interval not in (60,300,900):
            raise HTTPException(422,'Interval must be 60, 300, or 900 seconds')
        return app.state.market.snapshot(symbol,interval,as_of)

    @app.get('/api/events/{symbol}')
    def events(symbol:str):
        valid(symbol)
        return {'events': app.state.market.store.events(symbol), 'limit':2000}

    @app.websocket('/ws/market')
    async def websocket(ws:WebSocket):
        # Local browser only; disallow cross-site WebSocket initiation.
        origin = ws.headers.get('origin','')
        from urllib.parse import urlparse
        if origin and urlparse(origin).hostname not in ('localhost','127.0.0.1','[::1]','::1'):
            await ws.close(code=1008)
            return
        symbol = ws.query_params.get('symbol','AAPL')
        if symbol not in SYMBOLS:
            await ws.close(code=1008)
            return
        try:
            interval = int(ws.query_params.get('interval','60'))
        except ValueError:
            await ws.close(code=1008)
            return
        if interval not in (60,300,900):
            await ws.close(code=1008)
            return
        await ws.accept()
        try:
            while True:
                service = app.state.market
                await ws.send_json({'type':'snapshot','data':service.snapshot(symbol,interval),'status':service.status(),
                    'watchlist':[dict(item, **{k:v for k,v in service.snapshot(item['symbol'],interval).items() if k in ('price','change','source_time','source')}) for item in WATCHLIST]})
                await asyncio.sleep(1)
        except (WebSocketDisconnect, RuntimeError, OSError):
            pass

    dist = ROOT/'frontend/dist'
    if dist.exists():
        app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
    return app

app = create_app()
