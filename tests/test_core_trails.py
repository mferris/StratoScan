#!/usr/bin/env python3
"""The radar keeps where each aircraft has been, for a screen that has just opened (#84).

The app's trails used to start when it opened, while the kiosk's ran back a
quarter of an hour (the owner's ask, 2026-10-25). The core feed now keeps a
trail per aircraft, from the antenna and from the network, in memory, and
serves it at /api/trails. Straight stretches are collapsed as they're recorded.

Run: python3 tests/test_core_trails.py
"""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import threading
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
tmp = tempfile.mkdtemp()
os.environ["STRATOSCAN_AIRCRAFT_JSON"] = os.path.join(tmp, "aircraft.json")
os.environ["STRATOSCAN_RECEIVER_JSON"] = os.path.join(tmp, "receiver.json")
os.environ["STRATOSCAN_CORE_LOOKUPS"] = "0"
os.environ["STRATOSCAN_NET_RELAY"] = "0"
os.environ["STRATOSCAN_CORE_PORT"] = "0"
sys.path.insert(0, str(ROOT / "deploy"))
spec = importlib.util.spec_from_file_location("core_feed", ROOT / "deploy" / "core-feed.py")
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


t = cf.Trails()
# east along a straight line at 35,000 ft: the middle points go, the ends stay
for i in range(10):
    t.note("abc123", [1000.0 + 5 * i, 35.80, -78.90 + 0.01 * i, 35000])
pts = t.d["abc123"]
check(len(pts) == 2 and pts[0][2] == -78.90 and pts[-1][2] == round(-78.90 + 0.09, 2),
      "a straight leg is two points, however long")
# a turn north: a corner is kept
for i in range(1, 6):
    t.note("abc123", [1045.0 + 5 * i, 35.80 + 0.01 * i, -78.81, 35000])
check(len(t.d["abc123"]) == 3, "a turn keeps its corner")
# a climb along a straight line keeps its points: altitude changes the colour
c = cf.Trails()
for i in range(6):
    c.note("cl1mb0", [2000.0 + 5 * i, 35.80, -78.90 + 0.005 * i, 2000 + 500 * i])
check(len(c.d["cl1mb0"]) == 6, "a climb on a straight line keeps its points (the colour follows altitude)")
# nothing new: same position, or an older time
n = len(c.d["cl1mb0"])
c.note("cl1mb0", [2025.0, 35.80, -78.90 + 0.025, 4500])
c.note("cl1mb0", [1990.0, 35.70, -78.70, 1000])
check(len(c.d["cl1mb0"]) == n, "the same position again, or an older one, adds nothing")

# the payload: ages, not times, and only the last TRAIL_KEEP_S
p = t.payload(now=1100.0)
tr = p["trails"]["abc123"]
check(tr[0][0] == 100.0 and tr[-1][0] == 30.0 and tr[0][1:3] == [35.80, -78.90],
      "points come as seconds ago, so a screen with another clock reads them right")
check(p["keepS"] == cf.TRAIL_KEEP_S == 900, "a quarter of an hour, as long as the app keeps one")
part = t.payload(now=1000.0 + cf.TRAIL_KEEP_S + 20)
check([q[0] for q in part["trails"]["abc123"]] == [875.0, 850.0],
      "points older than a quarter of an hour are dropped")
late = t.payload(now=1070.0 + cf.TRAIL_KEEP_S + 1)
check("abc123" not in late["trails"] and "abc123" not in t.d, "and an aircraft long gone is forgotten")
one = cf.Trails()
one.note("solo00", [5000.0, 35.8, -78.8, 1000])
check("solo00" not in one.payload(5001.0)["trails"], "a single point is not a trail")

# readsb's record and the network's both turn into points; no position, no point
p1 = cf._trail_point({"hex": "a1", "lat": 35.8, "lon": -78.8, "alt_baro": "ground", "seen_pos": 2.0}, 100.0)
p2 = cf._trail_point({"hex": "a2", "lat": 35.9, "lon": -78.7, "alt": 12000}, 100.0)
check(p1 == [98.0, 35.8, -78.8, 0] and p2 == [100.0, 35.9, -78.7, 12000],
      "the position's own age (seen_pos) dates it; on the ground is 0 ft")
check(cf._trail_point({"hex": "a3", "alt_baro": 5000}, 100.0) is None, "an aircraft with no position adds nothing")

# the feed: the antenna's aircraft sampled, the network's noted when fetched
json.dump({"lat": 35.8776, "lon": -78.7875}, open(os.environ["STRATOSCAN_RECEIVER_JSON"], "w"))
feed = cf.Feed(lookups=type("L", (), {"routes": {}, "owners": {}, "want_route": lambda *a: None,
                                      "want_owner": lambda *a: None})(),
               uat=type("U", (), {"heard": lambda self, h: False})(), sightings=type("S", (), {"get": lambda self: {}})(),
               trails=False)
feed._note_trails([{"hex": "~ABC456", "lat": 35.9, "lon": -78.8, "alt_baro": 9000},
                   {"hex": "abc789"}])
check(list(feed.trails.d) == ["abc456"], "the antenna's record is keyed as the feed keys it (lower case, no ~)")
cf.FEED = feed
srv = cf.http.server.ThreadingHTTPServer(("127.0.0.1", 0), cf.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
feed.trails.note("abc456", [cf._now() + 1, 35.95, -78.75, 9100])
with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/trails", timeout=5) as r:
    body = json.load(r)
check(r.status == 200 and "abc456" in body["trails"] and len(body["trails"]["abc456"]) == 2,
      "/api/trails serves them")
srv.shutdown()

src = (ROOT / "deploy" / "core-feed.py").read_text()
net = src[src.index("    def _network_raw(self):"):src.index("    def label(self, a, source")]
check("self._note_trails(ac)" in net, "the network's aircraft are noted each time they are fetched")
gw = (ROOT / "deploy" / "funnel-gateway.py").read_text()
check('READ_ONLY_PUBLIC_PATHS = ("/sightings", "/approaches", "/network", "/api")' in gw,
      "the public gateway passes /api/trails read-only, as it does /api/aircraft")

# ---- the app seeds its trails from the radar's ---------------------------------
app_feed = (ROOT / "ios" / "Shared" / "AircraftFeedClient.swift").read_text()
check('APIConfig.url("/api/trails")' in app_feed and "struct Trails: Decodable" in app_feed,
      "the app asks the radar for its trails")
vm = (ROOT / "ios" / "StratoScan" / "ViewModels" / "RadarViewModel.swift").read_text()
poll = vm[vm.index("    private func pollRadar() async {"):]
poll = poll[:poll.index("\n    }\n") + 6]
check("if needTrails && !DemoFeed.isOn" in poll and "Task { await seedTrails() }" in poll,
      "once, after the first good look at the radar, not in its way")
res = vm[vm.index("    func resume() {"):vm.index("    private var needTrails")]
check("needTrails = true" in res, "and again when the app comes back after a while")
check(vm.count("applyRadarTrail(to:") >= 4, "aircraft that show up just after the fetch get theirs too")
ps = (ROOT / "ios" / "StratoScan" / "Models" / "PlaneState.swift").read_text()
seed = ps[ps.index("func seedHistory("):ps.index("init(hex: String, from n: NormalizedAircraft)")]
check("$0.at < first" in seed and "history = add + history" in seed,
      "only points older than the phone's own go in front of its trail")

print("core trail checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
