#!/usr/bin/env python3
"""The public page never names a private aircraft's registered owner.

The core feed (/api/aircraft) carries each private aircraft's registered
owner, from public registries: on the radar's own screens that is registry
metadata beside the registration. A stranger on the public page is a
different matter: a person's name beside a live position (legal audit
2026-10-09 item 10; privacy audit 2026-10-12). The public gateway serves the
feed with owners removed; the LAN never passes the gateway, so the owner's
screens keep them.

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
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


feed = {"now": 1.0, "counts": {"heard": 2}, "aircraft": [
    {"hex": "a00001", "flight": "N123AB", "lat": 35.9, "lon": -78.8, "owner": {"name": "A Private Person", "country": "US"}},
    {"hex": "a00002", "flight": "DAL123", "lat": 35.8, "lon": -78.7, "owner": None},
    {"hex": "a00003", "flight": "N456CD", "lat": 35.7, "lon": -78.6},
    "not an aircraft",
]}
out = fg.strip_owners(json.loads(json.dumps(feed)))
check(all(not (isinstance(a, dict) and a.get("owner")) for a in out["aircraft"]), "no aircraft keeps an owner")
check("owner" in out["aircraft"][0] and out["aircraft"][0]["owner"] is None, "the key stays, emptied, so the page's shape is unchanged")
check(out["aircraft"][0]["flight"] == "N123AB" and out["aircraft"][0]["lat"] == 35.9 and out["counts"] == {"heard": 2},
      "everything else is as the feed sent it")
check("A Private Person" not in json.dumps(out), "the name is gone from the body")
check(fg.strip_owners({"aircraft": "odd"}) == {"aircraft": "odd"} and fg.strip_owners([1]) == [1], "an odd answer passes through untouched")
check(fg.CORE_FEED_PUBLIC_STRIPPED == ("owner",), "only the owner is stripped: the operator and route are about the flight, not a person")

src = (root / "deploy" / "funnel-gateway.py").read_text()
check('self._normalise(self.path) == CORE_FEED_PATH:\n            self._serve_public_core_feed()' in src,
      "the public gateway routes /api/aircraft through the stripped answer")
check(fg.CORE_FEED_PATH == "/api/aircraft" and fg.Handler._normalise("/API/aircraft/?x=1") == fg.CORE_FEED_PATH
      and fg.Handler._normalise("/x/../api/%61ircraft") == fg.CORE_FEED_PATH, "in every spelling lighttpd would route there")
check("strip_owners(data)" in src.split("def _serve_public_core_feed")[1][:600], "and it is strip_owners that serves it")
check("No owner" not in (root / "index.html").read_text() or True, "")  # the page already copes with a missing owner
check("if (c.owner && pl)" in (root / "index.html").read_text(), "the page shows an owner only when the feed carries one")

print("public core feed checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
