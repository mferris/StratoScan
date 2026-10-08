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
print("network around checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
