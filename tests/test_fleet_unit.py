#!/usr/bin/env python3
"""
Checks for a radar joining and leaving a fleet (roadmap 1.13) in
deploy/heartbeat.py: health reports go on while it's in one and back the way
they were after, and the extras an administrator sees are counts and a name,
never a location.

Run: python3 tests/test_fleet_unit.py
"""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
failures = []
checks = 0


def check(label, condition):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


tmp = tempfile.mkdtemp()
os.environ["STRATOSCAN_RELAY_STATE"] = tmp
os.environ["STRATOSCAN_RELAY_URL"] = "https://relay.example"
spec = importlib.util.spec_from_file_location("hb", os.path.join(HERE, "..", "deploy", "heartbeat.py"))
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)

calls, sent = [], []
replies = {}


def fake_call(method, path, payload=None):
    calls.append((method, path, payload))
    return replies.get(path, (200, {"ok": True}))


hb._call = fake_call
hb.send = lambda report=None: (sent.append(1) or (True, "HTTP 200"))
local = {hb.SETUP_HELLO: {"name": "Mom's radar", "unit": "x", "claimed": True},
         hb.VISITS_URL: {"days": [{"date": f"2026-10-0{i}", "views": i, "unique": i // 2, "bots": 9,
                                  "hours": [1] * 24} for i in range(1, 10)]}}
hb._local_json = lambda url: local.get(url, {})

# ---- not in a fleet ------------------------------------------------------------------------
check("not in a fleet to start with", hb.fleet() == {})
check("and a report carries nothing extra", hb.fleet_extras() == {})

# ---- joining ------------------------------------------------------------------------------
hb.set_enabled(False)
replies["/v1/unit/fleet"] = (200, {"ok": True, "fleet": {"name": "Family"}})
r = hb.fleet_join("abcd-efgh-jkmn")
check("joining sends the code to the relay", calls[-1] == ("POST", "/v1/unit/fleet", {"code": "abcd-efgh-jkmn"}))
check("and says which fleet", r == {"fleet": {"name": "Family"}} and hb.fleet()["name"] == "Family")
check("it turns health reports on", hb.enabled() is True)
check("and sends one straight away", sent == [1])
check("remembering they were off before", hb.fleet()["health_was"] is False)

x = hb.fleet_extras()
check("in a fleet, a report carries the radar's name", x.get("name") == "Mom's radar")
check("and its last week of visit counts", len(x.get("visits", [])) == 7 and x["visits"][-1] == {"date": "2026-10-09", "views": 9, "unique": 4})
check("counts only: no hours, robots or anything else", set(x["visits"][0]) == {"date", "views", "unique"})
check("and never a location", not ({"lat", "lon", "latitude", "longitude"} & set(json.dumps(x).replace('"', " ").split())))

# ---- refused --------------------------------------------------------------------------------
replies["/v1/unit/fleet"] = (404, {"error": "That invite code isn't right, or has been replaced."})
try:
    hb.fleet_join("wrong")
    refused = None
except ValueError as e:
    refused = str(e)
check("a wrong code says why, in words", refused == "That invite code isn't right, or has been replaced.")
check("and leaves the fleet as it was", hb.fleet()["name"] == "Family")

# ---- leaving --------------------------------------------------------------------------------
r = hb.fleet_leave()
check("leaving tells the relay", calls[-1][:2] == ("POST", "/v1/unit/fleet/leave"))
check("and forgets the fleet", r == {"fleet": None} and hb.fleet() == {})
check("and puts health reports back the way they were", hb.enabled() is False)
check("after which reports carry nothing extra again", hb.fleet_extras() == {})

hb.set_enabled(True)
replies["/v1/unit/fleet"] = (200, {"ok": True, "fleet": {"name": "Club"}})
hb.fleet_join("ABCDEFGHJKMN")
hb.fleet_leave()
check("someone who had reports on keeps them on after leaving", hb.enabled() is True)

replies["/v1/unit/fleet/leave"] = (0, {"error": "Couldn't reach the StratoScan service (URLError)."})
hb.fleet_join("ABCDEFGHJKMN")
try:
    hb.fleet_leave()
    left = True
except ValueError:
    left = False
check("an unreachable relay doesn't pretend to have left", left is False and hb.fleet().get("name") == "Club")

# ---- setupd checks the code's shape before anything leaves the radar --------------------------
sd_spec = importlib.util.spec_from_file_location("setupd", os.path.join(HERE, "..", "deploy", "setupd.py"))
sd = importlib.util.module_from_spec(sd_spec)
sd_spec.loader.exec_module(sd)
bad = 0
for v in (None, "", "x" * 40, "abcd;rm -rf /", "ABCD\nEFGH"):
    try:
        sd.fleet_join(v)
    except sd.Err:
        bad += 1
    except Exception:
        pass
check("setupd refuses anything that isn't shaped like an invite code", bad == 5)
check("joining and leaving hold the state lock", {"fleet_join", "fleet_leave"} <= sd.MUTATING)

print(f"{checks - len(failures)}/{checks} fleet (radar side) checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
