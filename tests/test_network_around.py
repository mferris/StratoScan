#!/usr/bin/env python3
"""/network/around (roadmap 2.23 on the kiosk, 2026-10-08): the network's
aircraft round a point the radar's screen is looking at, from adsb.lol
through the unit. The point is rounded to 0.05 degrees, the radius clamped
to 25-250 nm, an answer kept per place for a few seconds, and adsb.lol asked
at most every few seconds whoever asks (the public page can)."""
import importlib.util
import os
import pathlib
import sys
import tempfile

os.environ["STATE_DIRECTORY"] = tempfile.mkdtemp()
os.environ["STRATOSCAN_NET_RELAY"] = "0"      # the cases below ask adsb.lol directly; the relay's are at the end
root = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("nc", root / "deploy" / "network-compare.py")
nc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nc)

fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


asked = []
sample = {"ac": [
    {"hex": "A1B2C3", "flight": "UAL123 ", "lat": 36.1, "lon": -79.2, "alt_baro": 35000, "gs": 450, "track": 90,
     "seen_pos": 1.5, "t": "B738", "r": "N123UA", "squawk": "1200", "baro_rate": -500, "category": "A3"},
    {"hex": "~c0ffee1", "lat": 36.2, "lon": -79.1},        # a placeholder address: dropped
    {"hex": "a3d3f6", "lat": None, "lon": -79.0},          # no position: dropped
    {"hex": "abcdef", "lat": 35.9, "lon": -78.9, "geom_rate": 200},
]}


def fake_get_json(url, timeout=6, limit=0):
    asked.append((url, limit))
    return sample


nc.get_json = fake_get_json
out = nc.around_payload(35.8261, -78.7863, 300, now=1000.0)
check(asked and asked[-1][0].endswith("/v2/point/35.85/-78.8/250"), "the point is rounded to 0.05 degrees and the radius clamped to 250: %s" % (asked and asked[-1][0]))
check(asked[-1][1] == nc.AROUND_MAX_BODY, "a busy disc may be a few MB")
check([a["hex"] for a in out["ac"]] == ["a1b2c3", "abcdef"], "real 24-bit addresses only, lower case")
a = out["ac"][0]
check(a["flight"] == "UAL123" and a["type"] == "B738" and a["reg"] == "N123UA" and a["vrate"] == -500 and a["alt"] == 35000,
      "the fields the page draws survive")
check(out["ac"][1]["vrate"] == 200, "geom_rate is the fallback vertical rate")
check(out["centre"] == {"lat": 35.85, "lon": -78.8} and out["radius"] == 250 and out["fetched"] == 0.0, "the answer says where and how far")

n = len(asked)
again = nc.around_payload(35.83, -78.79, 250, now=1004.0)
check(len(asked) == n and again["fetched"] == 4.0 and "stale" not in again, "the same place within %d s: the kept answer, nothing asked" % nc.AROUND_CACHE_S)
elsewhere = nc.around_payload(40.7, -74.0, 100, now=1003.0)
check(elsewhere is None and len(asked) == n, "another place within %d s of the last question: refused (429)" % nc.AROUND_UPSTREAM_GAP_S)
elsewhere = nc.around_payload(40.7, -74.0, 100, now=1006.0)
check(elsewhere is not None and len(asked) == n + 1 and asked[-1][0].endswith("/v2/point/40.7/-74.0/100"), "and asked once the gap has passed")
later = nc.around_payload(35.83, -78.79, 250, now=1010.5)
check(len(asked) == n + 1 and later.get("stale") is True, "the first place, past its keep time but inside the gap: its last answer, marked stale")
small = nc.around_payload(35.83, -78.79, 3, now=1030.0)
check(asked[-1][0].endswith("/25"), "a radius below 25 nm is raised to it")
check(not any(k.startswith("/network/around") for k in []) and "/network/around" in open(root / "deploy" / "network-compare.py").read(), "the handler routes it")

# A wide view: discs on a grid, merged, within a window of questions.
d, covered = nc.view_discs(35.0, -80.0, 100)
check(len(d) == 1 and d[0][2] == 130 and covered == 130, "a view 100 nm out: one disc of 130")
d, covered = nc.view_discs(35.0, -80.0, 300)
check(len(d) == 4 and covered == 353 and all(r == 250 for _, _, r in d), "300 nm out: a 2 x 2 grid of 250 nm discs covering 353")
d, covered = nc.view_discs(35.0, -80.0, 900)
check(len(d) == 9 and covered == 530, "900 nm out: 3 x 3 at most, covering 530")
import math as _m
gap = _m.hypot((d[1][1] - d[0][1]) * 60 * _m.cos(_m.radians(35.0)), (d[1][0] - d[0][0]) * 60)
check(abs(gap - nc.TILE_SPACING_NM) < 2, "discs spaced %.0f nm, so they leave no gap" % gap)
asked.clear()
nc.TILE_PACE_S = 0; nc.TILE_RETRY_S = 0          # no waiting in a test
nc.TILE_IN_THREAD = False                        # and the discs fetched inline, not in the background
out = nc.tiles_payload(35.0, -80.0, 900, now=2000.0)
check(len(asked) == 9 and out["discs"] == 9 and out["covered"] == 530 and out["answered"] == 9 and out["partial"] is False and out["pending"] == 0,
      "nine questions for nine discs, all answered")
check([a["hex"] for a in out["ac"]] == ["a1b2c3", "abcdef"], "the same aircraft in several discs is one aircraft")
again = nc.tiles_payload(35.01, -80.01, 900, now=2005.0)
check(len(asked) == 9 and again["fetched"] == 5.0, "the same view again: the kept answer")
other = nc.tiles_payload(45.0, -90.0, 900, now=2006.0)
check(other is None and len(asked) == 9, "another wide view inside the window: refused, nine questions already")
other = nc.tiles_payload(45.0, -90.0, 900, now=2021.0)
check(other is not None and len(asked) == 18, "and answered once the window has passed")

# A refusal: one more try, then the disc is left out and the answer says partial.
import urllib.error as _ue
calls = {"n": 0}
def refusing_get_json(url, timeout=6, limit=0):
    calls["n"] += 1
    asked.append((url, limit))
    if "/44." in url or "/45." in url:            # the top row of discs is refused every time
        raise _ue.HTTPError(url, 429, "calm", {}, None)
    return sample
nc.get_json = refusing_get_json
asked.clear()
nc._tiles["cache"].clear(); nc._tiles["discs"].clear(); nc._tiles["calls"] = []
out = nc.tiles_payload(40.0, -80.0, 900, now=3000.0)
check(out is not None and out["partial"] is True and out["answered"] == 6 and out["discs"] == 9,
      "three refused discs are left out, six answered, and the answer says partial")
refused = [u for u, _ in asked if "/45.89/" in u]
check(len(refused) == 6, "each refused disc was asked twice (%d asks)" % len(refused))
# In the background (as on the unit): the first answer comes at once with what is known.
def slow_get_json(url, timeout=6, limit=0):
    _t.sleep(0.1)                                # a real question takes a moment
    return fake_get_json(url, timeout, limit)
import time as _t
nc.get_json = slow_get_json
asked.clear(); nc._tiles["cache"].clear(); nc._tiles["discs"].clear(); nc._tiles["calls"] = []; nc._tiles["busy"].clear()
nc.TILE_IN_THREAD = True
nc.TILE_PACE_S = 0.05
first = nc.tiles_payload(50.0, -100.0, 900, now=4000.0)
check(first is not None and first["pending"] == 9 and first["answered"] == 0 and first["ac"] == [], "a new wide view answers at once: nothing yet, nine discs pending")
for _ in range(100):
    if not nc._tiles["busy"]: break
    _t.sleep(0.05)
later = nc.tiles_payload(50.0, -100.0, 900, now=4001.0)
check(later["pending"] == 0 and later["answered"] == 9 and len(later["ac"]) == 2, "a moment later the discs have been fetched and the view is whole")
# While one worker is fetching, another view starts no second one.
asked.clear(); nc._tiles["cache"].clear(); nc._tiles["discs"].clear(); nc._tiles["calls"] = []; nc._tiles["busy"].clear()
nc.TILE_PACE_S = 0.3
one = nc.tiles_payload(50.0, -100.0, 900, now=5000.0)
_t.sleep(0.15)
two = nc.tiles_payload(30.0, -100.0, 900, now=5000.2)
check(one["pending"] == 9 and two is None, "a second wide view while the first is being fetched: nothing started, 429 for now")
for _ in range(200):
    if not nc._tiles["busy"]: break
    _t.sleep(0.05)
check(len(asked) == 9 and not nc._tiles["fetching"], "the first worker alone asked its nine, then stopped")
nc.get_json = fake_get_json

# ---- the lattice, through the relay (performance audit 2026-10-09) ----------
import json as _json
# The unit and the relay must agree on the lattice to four decimals, or the
# relay refuses the disc: these are relay/src/netcache.js's answers.
for (lat, lon), want in [((35.8261, -78.7863), (34.8387, -77.6471)), ((51.5, -0.1), (52.2581, -4.7368)),
                         ((-33.9, 151.2), (-34.8387, 148.2353)), ((89.9, 10), (87.0968, 45.0)),
                         ((0, 0), (0.0, 2.9032)), ((40, -74), (40.6452, -76.5957))]:
    check(nc.lattice_centre(lat, lon) == want, "lattice centre for %s is %s (the relay's)" % ((lat, lon), want))
worst = 0
for lat10 in range(-899, 900, 37):
    for lon10 in range(-1800, 1800, 43):
        c = nc.lattice_centre(lat10 / 10, lon10 / 10)
        worst = max(worst, nc.haversine(lat10 / 10, lon10 / 10, c[0], c[1])[0])
check(worst < nc.LATTICE_R_NM, "no point on Earth is farther than %.0f nm from its nearest centre" % worst)

def covers(lat, lon, discs, reach):
    for k in range(36):
        b = math.radians(k * 10)
        plat = lat + reach * math.cos(b) / 60
        plon = lon + reach * math.sin(b) / (60 * math.cos(math.radians(lat)))
        if min(nc.haversine(plat, plon, d[0], d[1])[0] for d in discs) > nc.LATTICE_R_NM:
            return False
    return True

import math
c = nc.lattice_centre(35.8, -78.8)
d, reach = nc.plan_discs(c[0], c[1], 100, lattice=True)
check(d == [(c[0], c[1], 250)] and reach == 130, "a view at a lattice centre: that one disc, reaching 130")
d, reach = nc.plan_discs(35.8261, -78.7863, 100, lattice=False)
check(d == [(35.8261, -78.7863, 130)] and reach == 130, "without the relay, a disc round the view as before")
ok_all, counts = True, []
for lat10 in range(-600, 601, 73):
    for lon10 in range(-1800, 1800, 97):
        for half in (30, 100, 300, 900):
            d, reach = nc.plan_discs(lat10 / 10, lon10 / 10, half, lattice=True)
            counts.append(len(d))
            if not (1 <= len(d) <= nc.LATTICE_MAX_DISCS and reach >= 25 and covers(lat10 / 10, lon10 / 10, d, reach)):
                ok_all = False
            if half <= 190 and reach != int(max(25, min(250, half * 1.3))):
                ok_all = False
check(ok_all, "every view's discs cover its reach, and a view that fits one disc reaches as far as before (max %d discs)" % max(counts))
d, reach = nc.plan_discs(35.8261, -78.7863, 900, lattice=True)
check(len(d) == nc.LATTICE_MAX_DISCS and reach >= 300, "a continent-wide view: %d discs reaching %d nm" % (len(d), reach))

class FakeRelay:
    """Stands in for heartbeat.py: whether the relay is on, and its answers."""
    on = True
    asked = []               # (method, path)
    answer = None            # (status, bytes), an exception to raise, a list of them in turn, or None for the sample
    shared = []              # discs handed up
    @staticmethod
    def relay_on():
        return FakeRelay.on
    @staticmethod
    def relay_fetch(method, path, body=None, timeout=0, limit=0):
        FakeRelay.asked.append((method, path))
        if method == "PUT":
            FakeRelay.shared.append(_json.loads(body))
            return 204, b""
        a = FakeRelay.answer
        if isinstance(a, list):
            a = a.pop(0) if a else None
        if isinstance(a, Exception):
            raise a
        return a if a else (200, _json.dumps(sample).encode())

def reset():
    nc._tiles["cache"].clear(); nc._tiles["discs"].clear(); nc._tiles["calls"] = []; nc._tiles["busy"].clear()
    nc._tiles["fetching"] = False
    FakeRelay.asked.clear(); FakeRelay.shared.clear(); asked.clear()

nc.heartbeat = FakeRelay
nc.RELAY = True
nc.TILE_IN_THREAD = True; nc.TILE_RETRY_S = 0
check(nc.relay_on() is True, "with reports on, the discs come through the relay")
reset()
out = nc.tiles_payload(c[0], c[1], 100, now=6000.0)
check(FakeRelay.asked == [("GET", "/v1/net/disc/%s/%s" % (c[0], c[1]))] and not asked, "the one disc is asked of the relay, not adsb.lol")
check(out is not None and out["via"] == "relay" and out["answered"] == 1 and out["pending"] == 0 and out["covered"] == 130,
      "a single lattice disc is fetched before answering, like a disc round the view was")
check([a["hex"] for a in out["ac"]] == ["a1b2c3", "abcdef"], "both aircraft are within 130 nm of the view")
near = nc.tiles_payload(c[0], c[1], 25, now=6001.0)
check(near["ac"] == [] and near["answered"] == 1 and len(FakeRelay.asked) == 1,
      "a closer view of the same disc: nothing asked again, and aircraft beyond its reach are left out")
reset()
nc.TILE_IN_THREAD = False
wide = nc.tiles_payload(35.8261, -78.7863, 900, now=7000.0)
check(wide is not None and wide["discs"] == 16 and wide["answered"] == 16 and len(FakeRelay.asked) == 16 and not asked,
      "a continent-wide view: sixteen lattice discs from the relay")
check(all(p.count("/") == 5 and p.startswith("/v1/net/disc/") for _, p in FakeRelay.asked), "disc paths carry the centre only; the relay fixes the radius")
# Not cached yet, and this unit's turn to fetch: adsb.lol itself, then the disc is handed up for the others.
reset()
FakeRelay.answer = (404, b'{"error":"not cached","fetch":true}')
out = nc.tiles_payload(c[0], c[1], 100, now=8000.0)
check(out is not None and len(asked) == 1 and asked[0][0].endswith("/v2/point/%s/%s/250" % (c[0], c[1])),
      "'not cached, you fetch': the same lattice disc from adsb.lol directly")
check([m for m, _ in FakeRelay.asked] == ["GET", "PUT"] and FakeRelay.shared == [sample], "and handed up to the relay, as adsb.lol gave it")
# Another radar is fetching it: wait, ask again, and it is there.
reset()
nc.RELAY_WAIT_S = 0
FakeRelay.answer = [(404, b'{"error":"not cached","fetching":true,"retry_after":2}'), None]
out = nc.tiles_payload(c[0], c[1], 100, now=8100.0)
check(out is not None and not asked and [m for m, _ in FakeRelay.asked] == ["GET", "GET"] and len(out["ac"]) == 2,
      "'another radar is fetching it': waited, asked again, served from the relay, adsb.lol left alone")
reset()
FakeRelay.answer = [(404, b'{"fetching":true}'), (404, b'{"fetching":true}'), (404, b'{"fetching":true}')]
out = nc.tiles_payload(c[0], c[1], 100, now=8200.0)
check(out is not None and len(asked) == 1 and not FakeRelay.shared, "a lease that never delivers: adsb.lol itself after two waits, nothing handed up")
# The relay will not serve this unit (reports only just turned on): adsb.lol itself, for the same lattice disc.
reset()
FakeRelay.answer = (403, b'{"error":"turn health reports on first"}')
out = nc.tiles_payload(c[0], c[1], 100, now=9000.0)
check(out is not None and len(asked) == 1 and not FakeRelay.shared, "403 from the relay: adsb.lol directly, nothing handed up")
reset()
FakeRelay.answer = _ue.URLError("no route to host")
out = nc.tiles_payload(c[0], c[1], 100, now=10000.0)
check(out is not None and len(asked) == 1 and out["via"] == "relay", "the relay unreachable: adsb.lol directly, the picture unchanged")
FakeRelay.answer = None
nc.RELAY = False
check(nc.relay_on() is False, "STRATOSCAN_NET_RELAY=0 keeps everything direct whatever heartbeat says")
nc.TILE_IN_THREAD = True
print("network around checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
