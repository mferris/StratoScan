#!/usr/bin/env python3
"""core-feed.py tells each aircraft's band (2026-10-10): '978' when this
radar's 978 decoder decoded it lately, '978 via 1090' for an ADS-R
rebroadcast, otherwise '1090' -- and the page shows both the per-aircraft
line and the header count."""
import importlib.util
import os
import pathlib
import sys

os.environ["STRATOSCAN_CORE_LOOKUPS"] = "0"
root = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("cf", root / "deploy" / "core-feed.py")
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


clock = [1000.0]
cf._now = lambda: clock[0]
u = cf.UatHeard(start=False)
u.note(b'{"address": "A1B2C3", "callsign": "N12345"}')
u.note(b'not json')
u.note(b'{"address": "xyz"}')
check(u.heard("a1b2c3"), "an address the 978 decoder reported is remembered, in lower case")
check(cf.band_of({"type": "adsb_icao"}, "a1b2c3", u) == "978", "heard directly on 978")
check(cf.band_of({"type": "adsr_icao"}, "c0ffee", u) == "978 via 1090", "an ADS-R rebroadcast is a 978 aircraft re-sent on 1090")
check(cf.band_of({"type": "adsb_icao"}, "c0ffee", u) == "1090", "everything else is 1090")
check(cf.band_of({}, "c0ffee", None) == "1090", "no 978 decoder at all: 1090")
clock[0] += cf.UAT_KEEP_S + 1
check(not u.heard("a1b2c3"), "after UAT_KEEP_S without a 978 message, no longer counted as 978")

feed = cf.Feed(lookups=type("L", (), {"routes": {}, "owners": {}, "want_route": lambda *a: None, "want_owner": lambda *a: None})(), uat=u)
u.note(b'{"address": "abcdef"}')
out = feed.label({"hex": "abcdef", "flight": "N1", "lat": 35.8, "lon": -78.7, "type": "adsb_icao"}, "antenna")
check(out["band"] == "978", "the feed's aircraft carries its band")
net = feed.label({"hex": "123456", "lat": 35.8, "lon": -78.7}, "network")
check("band" not in net, "a network aircraft has no band (the radar did not hear it)")

page = (root / "index.html").read_text()
check("Heard on</div>" in page and "978 MHz (UAT)" in page, "the detail panel says what it was heard on")
check("ON 978" in page, "the header counts aircraft on 978 when there are any")
check("pl.band = c.band" in page, "the page keeps the feed's band on each plane")
print("core band checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
