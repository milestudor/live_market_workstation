"""Deterministic aggregation shared by live display and as-of replay."""
from datetime import datetime
from zoneinfo import ZoneInfo

WATCHLIST = [
    {'symbol':'AAPL','name':'Apple Inc.','sector':'Technology','color':'#a6b4ca'},
    {'symbol':'MSFT','name':'Microsoft Corp.','sector':'Technology','color':'#63a7ee'},
    {'symbol':'NVDA','name':'NVIDIA Corp.','sector':'Semiconductors','color':'#91bc65'},
    {'symbol':'AMZN','name':'Amazon.com Inc.','sector':'Consumer discretionary','color':'#e8b265'},
    {'symbol':'SPY','name':'SPDR S&P 500 ETF','sector':'Broad market ETF','color':'#b09ae8'},
]
SYMBOLS = [x['symbol'] for x in WATCHLIST]
NY = ZoneInfo('America/New_York')


def candles(observations, interval=60, now=0):
    bars, ticks = {}, {}
    # Historical minute bars are a separate provenance; stream buckets replace
    # overlapping history, rather than inventing volume by summing both sources.
    for o in observations:
        t = int(o['source_time']) // interval * interval
        p = o['payload']
        if o['kind'] == 'bar':
            b = bars.setdefault(t, {'time':t,'open':p['open'],'high':p['high'],'low':p['low'],
                'close':p['close'],'volume':0,'coverage':'historical','complete':True})
            b.update(high=max(b['high'],p['high']), low=min(b['low'],p['low']), close=p['close'])
            b['volume'] += p['volume']
            b['complete'] = b['complete'] and p.get('complete', False)
        else:
            ticks.setdefault(t, []).append(o)
    previous_volume, previous_day = None, None
    for t in sorted(ticks):
        group = sorted(ticks[t], key=lambda o:(o['source_time'], o['id']))
        prices = [o['payload']['price'] for o in group]
        volume = 0 if any(o['payload'].get('day_volume') is not None for o in group) else None
        for o in group:
            day = datetime.fromtimestamp(o['source_time'], NY).date()
            cumulative = o['payload'].get('day_volume')
            if cumulative is not None:
                if day == previous_day and previous_volume is not None:
                    volume += max(0, cumulative - previous_volume)
                previous_volume, previous_day = cumulative, day
        bars[t] = {'time':t,'open':prices[0],'high':max(prices),'low':min(prices),'close':prices[-1],
            'volume':volume,'coverage':'observed ticks · '+('volume unavailable' if volume is None else 'partial'),'complete':t+interval <= now}
    for b in bars.values():
        b['complete'] = b['complete'] and b['time']+interval <= now
    return sorted(bars.values(), key=lambda b:b['time'])[-600:]
