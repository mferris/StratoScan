#!/usr/bin/env python3
"""The public page never names a private aircraft's registered owner, and
never carries a count worked out from the receiver's exact position.

The core feed (/api/aircraft) carries each private aircraft's registered
owner, from public registries: on the radar's own screens that is registry
metadata beside the registration. A stranger on the public page is a
different matter: a person's name beside a live position (legal audit
2026-10-09 item 10; privacy audit 2026-10-12). The public gateway serves the
feed with owners removed; the LAN never passes the gateway, so the owner's
screens keep them.

The feed's ring counts and each aircraft's close passes (sightings.nearby)
are emptied on the public path too (2026-10-26): both are measured from
where the radar is, and nothing public needs them.

Run: python3 tests/test_public_core_feed.py
"""
import importlib.util
import json
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("fg", root / "deploy" / "funnel-gateway.py")
fg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fg)
public_core_feed = getattr(fg, "public_core_feed", fg.strip_owners)
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


feed = {"now": 1.0, "counts": {"heard": 2, "notHeard": 1, "on978": 0}, "aircraft": [
    {"hex": "a00001", "flight": "N123AB", "lat": 35.9, "lon": -78.8, "owner": {"name": "A Private Person", "country": "US"},
     "sightings": {"total": 7, "nearby": 3}},
    {"hex": "a00002", "flight": "DAL123", "lat": 35.8, "lon": -78.7, "owner": None, "sightings": {"total": 1, "nearby": 0}},
    {"hex": "a00003", "flight": "N456CD", "lat": 35.7, "lon": -78.6, "source": "network"},
    "not an aircraft",
]}
out = fg.strip_owners(json.loads(json.dumps(feed)))
check(all(not (isinstance(a, dict) and a.get("owner")) for a in out["aircraft"]), "no aircraft keeps an owner")
check("owner" in out["aircraft"][0] and out["aircraft"][0]["owner"] is None, "the key stays, emptied, so the page's shape is unchanged")
check(out["aircraft"][0]["flight"] == "N123AB" and out["aircraft"][0]["lat"] == 35.9 and out["counts"]["heard"] == 2,
      "strip_owners leaves everything else as the feed sent it")
check("A Private Person" not in json.dumps(out), "the name is gone from the body")
check(fg.strip_owners({"aircraft": "odd"}) == {"aircraft": "odd"} and fg.strip_owners([1]) == [1], "an odd answer passes through untouched")
check(fg.CORE_FEED_PUBLIC_STRIPPED == ("owner",), "only the owner is stripped: the operator and route are about the flight, not a person")

pub = public_core_feed(json.loads(json.dumps(feed)))
check(pub["counts"] is None, "the public feed carries no ring counts (they are worked out round the receiver)")
check(pub["aircraft"][0]["sightings"] == {"total": 7, "nearby": None} and pub["aircraft"][1]["sightings"]["nearby"] is None,
      "nor any aircraft's close passes; its visits stay")
check(pub["aircraft"][0]["owner"] is None and "A Private Person" not in json.dumps(pub), "and no owners")
check(pub["aircraft"][0]["lat"] == 35.9 and pub["aircraft"][2] == feed["aircraft"][2] and pub["now"] == 1.0,
      "everything else is as the feed sent it")
check(public_core_feed({"aircraft": "odd"}) == {"aircraft": "odd"} and public_core_feed([1]) == [1]
      and public_core_feed({"aircraft": [{"sightings": "odd"}]}) == {"aircraft": [{"sightings": "odd"}]},
      "an odd answer passes through untouched")

check(getattr(fg, "PUBLIC_REWRITES", {}).get(fg.CORE_FEED_PATH) is public_core_feed,
      "the public gateway serves /api/aircraft through public_core_feed")
check(fg.CORE_FEED_PATH == "/api/aircraft" and fg.Handler._normalise("/API/aircraft/?x=1") == fg.CORE_FEED_PATH
      and fg.Handler._normalise("/x/../api/%61ircraft") == fg.CORE_FEED_PATH, "in every spelling lighttpd would route there")
page = (root / "index.html").read_text()
check("if (c.owner && pl)" in page, "the page shows an owner only when the feed carries one")
check("feed.counts" not in page and ".counts.heard" not in page, "the page does not read the feed's counts")
app = (root / "ios" / "Shared" / "Aircraft.swift").read_text()
check("FeedCounts?" in app and "try? c.decodeIfPresent(FeedSightings.self" in app,
      "the app decodes both as optional, so a null leaves the rest of its feed intact")

print("public core feed checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
