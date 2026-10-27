#!/usr/bin/env python3
"""Ring tests are worked out round the receiver rounded to 0.01 degrees
(2026-10-26), in the core feed (counts.heard, notHeard, on978) and in the
network comparison (the ghosts, mine and network, the scorecard's bearings,
and so the network's trails the core feed keeps). Their answers reach the
public page, so they say nothing finer than the public receiver.json does:
two receiver positions in the same 0.01 degree cell give identical answers,
with aircraft just outside the 20 nm ring on the side one of them lies.

Run: python3 tests/test_ring_same_cell.py
"""
import importlib.util
import json
import math
import os
import pathlib
import sys
import tempfile

os.environ["STRATOSCAN_CORE_LOOKUPS"] = "0"
os.environ["STRATOSCAN_NET_RELAY"] = "0"
os.environ["STATE_DIRECTORY"] = tempfile.mkdtemp()
root = pathlib.Path(__file__).resolve().parent.parent


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, root / "deploy" / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cf = load("cf", "core-feed.py")
nc = load("nc", "network-compare.py")
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


A = (35.8776, -78.7875)       # RDU
B = (35.8824, -78.7930)       # ~0.4 nm away, in the same 0.01 degree cell
check(round(A[0], 2) == round(B[0], 2) and round(A[1], 2) == round(B[1], 2), "the two positions share a 0.01 degree cell")


def place(bearings, nm, first, prefix):
    """Aircraft `nm` from A on each bearing."""
    out = []
    for i, brg in enumerate(bearings):
        b = math.radians(brg)
        lat = A[0] + nm * math.cos(b) / 60
        lon = A[1] + nm * math.sin(b) / (60 * math.cos(math.radians(A[0])))
        out.append({"hex": "%s%04x" % (prefix, first + i), "flight": "TST%d" % i, "lat": round(lat, 6),
                    "lon": round(lon, 6), "alt_baro": 3000 + 700 * i, "seen": 1, "seen_pos": 1})
    return out


# Some aircraft well inside the ring, and some just outside 20 nm of A on the
# side B lies (B is ~0.4 nm north-west of A): inside a ring round B, outside
# one round A. The antenna heard some; the network has those and others.
inner = list(range(0, 360, 45))
edge = list(range(290, 345, 5))
antenna = place(inner, 10, 0, "a1") + place(edge, 20.2, 16, "a1")
network = place(inner, 10, 0, "a1") + place(inner, 12, 32, "c0") + place(edge, 20.2, 48, "c0")

# ---- the core feed -----------------------------------------------------------
cf._now = lambda: 1000.0
t = tempfile.mkdtemp()
cf.AIRCRAFT_JSON = os.path.join(t, "aircraft.json")
cf.RECEIVER_JSON = os.path.join(t, "receiver.json")
with open(cf.AIRCRAFT_JSON, "w") as f:
    json.dump({"now": 1000, "aircraft": antenna}, f)


def core_answer(home):
    with open(cf.RECEIVER_JSON, "w") as f:
        json.dump({"lat": home[0], "lon": home[1]}, f)
    feed = cf.Feed(trails=False)
    feed._network_raw = lambda: [dict(a, type="B738") for a in network]
    return feed.build(with_network=True)


ca, cb = core_answer(A), core_answer(B)
check(ca["counts"]["heard"] > 0 and ca["counts"]["notHeard"] > 0, "the ring has aircraft in it: %s" % ca["counts"])
check(ca["counts"] == cb["counts"], "the core feed's ring counts are the same from both: %s and %s" % (ca["counts"], cb["counts"]))
check(json.dumps(ca, sort_keys=True) == json.dumps(cb, sort_keys=True), "and so is the whole /api/aircraft answer")
c = (35.88, -78.79)
check(getattr(cf, "ring_centre", lambda h: None)(A) == c, "the ring is centred on the rounded position")
inside = sum(1 for a in antenna if cf._nm(c[0], c[1], a["lat"], a["lon"]) <= cf.RING_NM)
check(ca["counts"]["heard"] == inside, "and counts what is within 20 nm of it (%d)" % inside)
check(getattr(cf, "ring_centre", lambda h: 0)(None) is None, "no receiver position: no ring")

# ---- the network comparison ----------------------------------------------------
asked = []
where = {}


def fake_get_json(url, timeout=6, limit=0, deadline_s=0):
    asked.append(url)
    if url == nc.LOCAL_RECEIVER:
        return {"lat": where["home"][0], "lon": where["home"][1]}
    if url == nc.LOCAL_AIRCRAFT:
        return {"aircraft": antenna}
    return {"ac": [dict(a, t="B738") for a in network]}


nc.get_json = fake_get_json
nc.load_store = lambda: {}


def network_answer(home):
    where["home"] = home
    nc._store = None
    p = nc.build_payload()
    p.pop("at")
    p["stats"].pop("since")
    card = nc.scorecard(nc.current())
    card.pop("since")
    return p, card


(pa, sa), (pb, sb) = network_answer(A), network_answer(B)
check(pa["ac"] and pa["mine"] and pa["network"], "the comparison has ghosts and counts: mine %d, network %d, %d ghosts"
      % (pa["mine"], pa["network"], len(pa["ac"])))
check(pa["mine"] == pb["mine"] and pa["network"] == pb["network"], "mine and network are the same from both")
check(sorted(g["hex"] for g in pa["ac"]) == sorted(g["hex"] for g in pb["ac"]), "the same ghosts go out from both")
check(json.dumps(pa, sort_keys=True) == json.dumps(pb, sort_keys=True), "and so does the whole /network answer")
check(sa == sb and sa["byBearing"] == sb["byBearing"], "the scorecard (/network/stats), bearings included, is the same from both")


def trails_from(ghosts):
    """/api/trails as the core feed keeps it from two answers ten seconds apart."""
    feed = cf.Feed(trails=False)
    for step in (0, 1):
        cf._now = lambda: 1000.0 + 10 * step
        feed._note_trails([dict(g, lat=g["lat"] + 0.01 * step) for g in ghosts])
    return feed.trails.payload(1010.0)


ta, tb = trails_from(pa["ac"]), trails_from(pb["ac"])
check(ta["trails"] and ta == tb, "and so are the network's trails (/api/trails) the core feed keeps from it")
check(all("/35.88/-78.79/" in u for u in asked if u.startswith("https://")), "the question to the network is the rounded point")
check(nc.home() == (35.88, -78.79), "home() is the rounded position")

print("ring cell checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
