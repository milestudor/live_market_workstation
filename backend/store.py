"""Append-only observation versions and delivery receipts. Times are UTC seconds."""
import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS observations (
              id INTEGER PRIMARY KEY, identity TEXT NOT NULL, revision INTEGER NOT NULL,
              symbol TEXT NOT NULL, source TEXT NOT NULL, kind TEXT NOT NULL,
              source_time REAL NOT NULL, received_time REAL NOT NULL,
              payload TEXT NOT NULL, fingerprint TEXT NOT NULL,
              UNIQUE(identity, revision));
            CREATE INDEX IF NOT EXISTS obs_symbol ON observations(symbol, id);
            CREATE INDEX IF NOT EXISTS obs_identity ON observations(identity, revision);
            CREATE TABLE IF NOT EXISTS deliveries (
              seq INTEGER PRIMARY KEY, observation_id INTEGER NOT NULL REFERENCES observations(id),
              received_time REAL NOT NULL, duplicate INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS delivery_obs ON deliveries(observation_id, seq);
        ''')
        self.db.commit()

    def ingest(self, symbol, source, kind, source_time, payload, received_time=None):
        if kind not in ('tick', 'bar') or not math.isfinite(source_time) or source_time <= 0:
            raise ValueError('Invalid observation type or time')
        values = [payload.get('price')] if kind == 'tick' else [payload.get(k) for k in ('open','high','low','close')]
        if any(v is None or not math.isfinite(float(v)) or float(v) <= 0 for v in values):
            raise ValueError('Prices must be finite and positive')
        volume = payload.get('day_volume' if kind == 'tick' else 'volume')
        if kind == 'bar' and volume is None:
            raise ValueError('Historical bars require volume')
        if volume is not None and (not math.isfinite(float(volume)) or float(volume) < 0):
            raise ValueError('Volume must be finite and nonnegative')
        if kind == 'bar' and not (payload['low'] <= min(payload['open'], payload['close']) <= max(payload['open'], payload['close']) <= payload['high']):
            raise ValueError('Invalid OHLC range')
        received_time = time.time() if received_time is None else received_time
        identity = f'{source}:{kind}:{symbol}:{source_time:.3f}'
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
        fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
        with self.db:
            prev = self.db.execute('SELECT * FROM observations WHERE identity=? ORDER BY revision DESC LIMIT 1', (identity,)).fetchone()
            duplicate = bool(prev and prev['fingerprint'] == fingerprint)
            if duplicate:
                obs_id = prev['id']
            else:
                cur = self.db.execute('INSERT INTO observations(identity,revision,symbol,source,kind,source_time,received_time,payload,fingerprint) VALUES(?,?,?,?,?,?,?,?,?)',
                    (identity, prev['revision'] + 1 if prev else 1, symbol, source, kind, source_time, received_time, encoded, fingerprint))
                obs_id = cur.lastrowid
            cur = self.db.execute('INSERT INTO deliveries(observation_id,received_time,duplicate) VALUES(?,?,?)', (obs_id, received_time, int(duplicate)))
        return cur.lastrowid, duplicate

    def events(self, symbol, limit=2000):
        rows = self.db.execute('''SELECT d.seq, d.received_time AS receipt_time, d.duplicate, o.*
          FROM deliveries d JOIN observations o ON o.id=d.observation_id WHERE o.symbol=?
          ORDER BY d.seq DESC LIMIT ?''', (symbol, limit)).fetchall()
        return [dict(r) | {'payload': json.loads(r['payload'])} for r in reversed(rows)]

    def current(self, symbol, as_of=None):
        # Filter BEFORE selecting latest versions: replay must never see later revisions.
        rows = self.db.execute('''WITH available AS (
          SELECT o.*, MIN(d.seq) AS first_seq FROM observations o JOIN deliveries d ON d.observation_id=o.id
          WHERE o.symbol=? AND (? IS NULL OR d.seq<=?) GROUP BY o.id),
          ranked AS (SELECT *, ROW_NUMBER() OVER(PARTITION BY identity ORDER BY revision DESC) AS rank FROM available)
          SELECT * FROM ranked WHERE rank=1 ORDER BY source_time, id''', (symbol, as_of, as_of)).fetchall()
        return [dict(r) | {'payload': json.loads(r['payload'])} for r in rows]

    def stats(self):
        return dict(self.db.execute('''SELECT
          (SELECT COUNT(*) FROM observations) AS observations,
          (SELECT COUNT(*) FROM deliveries) AS deliveries,
          (SELECT COALESCE(SUM(duplicate),0) FROM deliveries) AS duplicates,
          (SELECT COUNT(*) FROM observations WHERE revision>1) AS revisions''').fetchone())

    def close(self):
        self.db.close()
