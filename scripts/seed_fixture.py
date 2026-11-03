"""Deterministic SYNTHETIC observations for isolated offline tests, never the live DB."""
import argparse
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.store import Store
from backend.market import SYMBOLS

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--db',required=True,help='New, isolated test database path')
args=parser.parse_args()
path=Path(args.db)
if path.exists():
    raise SystemExit('Refusing to modify an existing database. Choose a new fixture path.')
s=Store(path)
start=1793716200  # fixed Nov 3, 2026 session, synthetic values
for index,symbol in enumerate(SYMBOLS):
    price=[230,420,185,220,580][index]
    for i in range(150):
        close=price+math.sin(i/9)*.4+.015
        s.ingest(symbol,'fixture-synthetic','bar',start+i*60,{'open':price,'high':max(price,close)+.2,'low':min(price,close)-.2,'close':close,'volume':1000+i*23,'complete':True},start+i*60+60)
        price=close
# Exercise duplicate, revised, and late arrivals with honest fixture provenance.
for ts,price,volume in [(start+9001,235,100),(start+9001,235,100),(start+9001,236,100),(start+9005,237,140),(start+9003,234,120)]:
    s.ingest('AAPL','fixture-synthetic','tick',ts,{'price':price,'day_volume':volume},start+9010)
print(s.stats())
s.close()
