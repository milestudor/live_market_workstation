import asyncio
import math

import pytest
from fastapi.testclient import TestClient

from backend.main import MarketService, create_app
from backend.market import candles
from backend.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path/'test.sqlite3')
    yield s
    s.close()


def tick(s, ts, price, volume=100, receipt=None):
    return s.ingest('AAPL','yahoo-stream','tick',ts,{'price':price,'day_volume':volume},receipt or ts+1)


def test_duplicate_receipts_do_not_inflate_volume(store):
    tick(store,120,10,100)
    seq, duplicate = tick(store,120,10,100)
    assert duplicate
    assert store.stats() == {'observations':1,'deliveries':2,'duplicates':1,'revisions':0}
    assert candles(store.current('AAPL'),60,180)[0]['volume'] == 0


def test_revisions_are_as_of_receipt_not_future(store):
    first,_ = tick(store,120,10)
    second,_ = tick(store,120,12,120,200)
    assert store.current('AAPL',first)[0]['payload']['price'] == 10
    assert store.current('AAPL',second)[0]['payload']['price'] == 12
    assert store.stats()['revisions'] == 1
    assert candles(store.current('AAPL',first),60,121)[0]['complete'] is False
    assert candles(store.current('AAPL',second),60,200)[0]['complete'] is True


def test_late_tick_rebuilds_open_close_and_volume_in_source_order(store):
    tick(store,125,12,120,200)
    tick(store,130,11,150,201)
    before = store.events('AAPL')[-1]['seq']
    tick(store,121,10,100,202)
    old = candles(store.current('AAPL',before),60,202)[0]
    new = candles(store.current('AAPL'),60,202)[0]
    assert old['open'] == 12
    assert (new['open'],new['high'],new['low'],new['close'],new['volume']) == (10,12,10,11,50)


def test_revised_tick_removes_old_extreme(store):
    tick(store,121,10,100)
    tick(store,122,30,120)
    seq,_ = tick(store,122,11,120)
    b = candles(store.current('AAPL',seq),60,200)[0]
    assert b['high'] == 11
    assert b['volume'] == 20


def test_volume_reset_and_missing_baseline(store):
    tick(store,121,10,100)
    tick(store,181,11,130)
    tick(store,182,12,5)
    tick(store,183,13,9)
    result = candles(store.current('AAPL'),60,300)
    assert [b['volume'] for b in result] == [0,34]


def test_stream_replaces_overlapping_history_without_double_count(store):
    store.ingest('AAPL','yahoo-history','bar',120,{'open':9,'high':20,'low':8,'close':15,'volume':1000,'complete':True},180)
    tick(store,125,12,100,190)
    tick(store,126,13,120,191)
    b = candles(store.current('AAPL'),60,200)[0]
    assert b['volume'] == 20
    assert b['high'] == 13
    assert 'partial' in b['coverage']


def test_five_minute_aggregation_and_clock_boundary(store):
    tick(store,301,10,100)
    tick(store,420,12,150)
    tick(store,599,9,180)
    b = candles(store.current('AAPL'),300,599)[0]
    assert (b['open'],b['high'],b['low'],b['close'],b['volume'],b['complete']) == (10,12,9,9,80,False)
    assert candles(store.current('AAPL'),300,600)[0]['complete'] is True


@pytest.mark.parametrize('price',[float('nan'),float('inf'),0,-1])
def test_invalid_prices_rejected(store,price):
    with pytest.raises(ValueError):
        tick(store,120,price)
    assert store.stats()['deliveries'] == 0


def test_persistence_survives_reopen(tmp_path):
    path = tmp_path/'records.sqlite3'
    s=Store(path);tick(s,120,10);s.close()
    s=Store(path)
    assert s.current('AAPL')[0]['payload']['price'] == 10
    s.close()


def test_unavailable_feed_and_websocket_path(tmp_path):
    app=create_app(tmp_path/'api.sqlite3',live=False)
    with TestClient(app) as client:
        assert client.get('/api/status').json()['state']=='disabled'
        assert client.get('/api/snapshot/NOPE').status_code==404
        assert client.get('/api/snapshot/AAPL?interval=2').status_code==422
        assert client.get('/api/snapshot/AAPL?as_of=-1').status_code==422
        assert client.get('/api/snapshot/AAPL?as_of=0').json()['candles']==[]
        asyncio.run(app.state.market.receive({'id':'AAPL','price':123,'time':'1700000000000','day_volume':'1000'}))
        with client.websocket_connect('/ws/market?symbol=AAPL') as ws:
            message=ws.receive_json()
            assert message['data']['price']==123
            assert message['data']['source']=='yahoo-stream'
            assert message['status']['stats']['observations']==1
        assert len(client.get('/api/events/AAPL').json()['events'])==1


def test_source_failure_sets_unavailable_and_retries(store,monkeypatch):
    class BrokenFeed:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):raise ConnectionError('offline test')
        async def __aexit__(self,*args):pass
    monkeypatch.setattr('backend.main.YahooStream',BrokenFeed)
    service=MarketService(store)
    async def check():
        task=asyncio.create_task(service.stream())
        await asyncio.sleep(.01)
        assert service.state=='unavailable'
        assert 'ConnectionError' in service.detail
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    asyncio.run(check())


def test_missing_volume_is_not_a_zero_volume_claim(store):
    tick(store,120,10,None)
    b=candles(store.current('AAPL'),60,180)[0]
    assert b['volume'] is None
    assert 'volume unavailable' in b['coverage']


def test_volume_baseline_resets_on_new_eastern_day(store):
    tick(store,1793716200,10,1000)
    tick(store,1793802600,11,2000)
    result=candles(store.current('AAPL'),60,1793803000)
    assert [b['volume'] for b in result]==[0,0]


def test_feed_adapter_returns_on_clean_socket_close():
    from backend.feed import YahooStream
    class EmptySocket:
        def __aiter__(self):return self
        async def __anext__(self):raise StopAsyncIteration
    stream=YahooStream(verbose=False)
    stream._ws=EmptySocket()
    with pytest.raises(ConnectionError):
        asyncio.run(stream.listen(lambda message:None))
