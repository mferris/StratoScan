#!/usr/bin/env python3
"""
Checks for deploy/events.py (unit events for paired phones).

What matters:
- the rules match the kiosk's own alerts exactly;
- an event never carries a position;
- each pass is reported once, not once per poll;
- a flood is capped, but an emergency never is;
- a relay that is down loses nothing but stale events, and a relay that
  refuses a batch cannot block the ones behind it.

Run: python3 tests/test_events.py
"""
import gzip
import importlib.util
import json
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
failures, checks = [], 0


def check(label, cond):
    global checks
    checks += 1
    if not cond:
        failures.append(label)


tmp = tempfile.mkdtemp()
db = os.path.join(tmp, "db-test")
os.makedirs(db)


def gz(name, obj):
    with open(os.path.join(db, name + ".js"), "wb") as f:
        f.write(gzip.compress(json.dumps(obj).encode()))


gz("icao_aircraft_types2", {"B407": ["BELL 407", "H1T", "L"],
                            "B744": ["BOEING 747-400", "L4J", "H"],
                            "C172": ["CESSNA 172 Skyhawk", "L1P", "L"]})
gz("A", {"BC123": ["N407XX", "B407", "00", None], "children": ["A9"]})
gz("A9", {"0001": ["N744CK", "B744", "00", "BOEING 747-400"],
          "0002": ["N172AB", "C172", "00", None]})
notable_path = os.path.join(tmp, "notable.json")
with open(notable_path, "w") as f:
    json.dump({"v": 1, "ac": {"c0ffee": ["Dictator Alert", "Civ", "", "Gulfstream G650"],
                              "a11111": ["Police Forces", "Gov", "State Police", "Bell 407"]}}, f)

os.environ["FLIGHTRADAR_RELAY_STATE"] = os.path.join(tmp, "relay")
os.environ["FLIGHTRADAR_RELAY_URL"] = "https://relay.example"
os.environ["FLIGHTRADAR_TAR1090_DB"] = os.path.join(tmp, "db-*")
os.environ["FLIGHTRADAR_NOTABLE_JSON"] = notable_path
os.environ["FLIGHTRADAR_EVENTS_RUN"] = os.path.join(tmp, "run")
spec = importlib.util.spec_from_file_location("events", os.path.join(HERE, "..", "deploy", "events.py"))
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

# ---- the same rules as the kiosk --------------------------------------------------
page = open(os.path.join(HERE, "..", "index.html"), encoding="utf-8").read()

block = re.search(r"const MILITARY_HEX_RANGES = \[(.*?)\];", page, re.S).group(1)
page_mil = [(int(a, 16), int(b, 16), c)
            for a, b, c in re.findall(r"\[(0x[0-9a-f]+),\s*(0x[0-9a-f]+),\s*'([^']+)'\]", block)]
check("military ranges match index.html", page_mil == ev.MILITARY_HEX_RANGES and len(page_mil) > 10)

block = re.search(r"const NOTABLE_TYPES = new Map\(\[(.*?)\]\);", page, re.S).group(1)
page_types = dict(re.findall(r"\['([^']+)',\s*'([^']+)'\]", block))
check("notable types match index.html", page_types == ev.NOTABLE_TYPES and len(page_types) > 20)

block = re.search(r"const NOTABLE_LABELS = \{(.*?)\n\};", page, re.S).group(1)
page_labels = {}
for m in re.finditer(r"""(?:'(?P<k1>[^']*)'|"(?P<k2>[^"]*)")\s*:\s*'(?P<v>[^']*)'""", block):
    page_labels[m.group("k1") if m.group("k1") is not None else m.group("k2")] = m.group("v")
check("notable labels match index.html", page_labels == ev.NOTABLE_LABELS and len(page_labels) > 40)
check("the low radius is the kiosk's nearby radius",
      f"const ALERT_RADIUS_NM = {ev.LOW_RADIUS_NM};" in page)

# ---- type database ----------------------------------------------------------------
t = ev.TypeDb()
info = t.lookup("abc123")
check("a direct shard entry is found", info["reg"] == "N407XX" and info["type_code"] == "B407")
check("its type falls back to the type table", info["type"] == "Bell 407" and info["desc"] == "H1T")
info = t.lookup("a90001")
check("a child shard is descended into", info["reg"] == "N744CK" and info["type"] == "Boeing 747-400")
check("an unknown hex is empty, not an error", t.lookup("ffffff")["type"] is None)
check("a missing database is empty, not an error",
      ev.TypeDb(os.path.join(tmp, "nothing-*")).lookup("abc123")["type"] is None)


def ac(hex_, dist=None, alt=3000, **k):
    a = {"hex": hex_, "seen": 0.5, "alt_baro": alt, "lat": 35.1, "lon": -78.9, "flight": "TEST1   "}
    if dist is not None:
        a["r_dst"], a["r_dir"] = dist, 50.0
    a.update(k)
    return a


def scan(det, *aircraft, now=1_000_000):
    return det.scan({"aircraft": list(aircraft)}, now=now)


def kinds(evs):
    return sorted(e["kind"] for e in evs)


# ---- emergencies ------------------------------------------------------------------
d = ev.Detector()
out = scan(d, ac("aaaaa1", dist=200, alt=30000, squawk="7700"))
check("7700 is an emergency at any range", kinds(out) == ["emergency"])
check("it says what kind", out[0]["label"] == "emergency" and out[0]["squawk"] == "7700")
check("not again on the next poll", scan(d, ac("aaaaa1", dist=199, alt=30000, squawk="7700"), now=1_000_005) == [])
check("again once the cooldown has passed",
      kinds(scan(d, ac("aaaaa1", dist=150, alt=30000, squawk="7700"), now=1_000_000 + 31 * 60)) == ["emergency"])
out = scan(d, ac("aaaaa2", emergency="lifeguard"))
check("readsb's emergency state counts, even with no position", kinds(out) == ["emergency"]
      and out[0]["label"] == "medical")
check("7600 is a radio failure", scan(d, ac("aaaaa3", dist=50, squawk="7600"))[0]["label"] == "radio failure")

# ---- low overhead -----------------------------------------------------------------
d = ev.Detector()
check("low and close is an event", kinds(scan(d, ac("a90002", dist=1.0, alt=2000))) == ["low_overhead"])
check("close but high is not", scan(d, ac("aaaab1", dist=1.0, alt=9000)) == [])
check("low but not close is not", scan(d, ac("aaaab2", dist=3.0, alt=2000)) == [])
check("on the ground is not", scan(d, ac("aaaab3", dist=0.5, alt="ground")) == [])
check("a stale aircraft is ignored", scan(d, ac("aaaab4", dist=1.0, alt=2000, seen=60)) == [])
check("TIS-B (no real address) is ignored", scan(d, ac("~aaaab5", dist=1.0, alt=2000)) == [])

# ---- helicopters ------------------------------------------------------------------
d = ev.Detector()
out = scan(d, ac("abc123", dist=1.0, alt=1000))
check("a helicopter close by is a helicopter event, and not also a low one", kinds(out) == ["helicopter"])
check("it carries the type from the database", out[0]["type"] == "Bell 407" and out[0]["reg"] == "N407XX")
check("still only a helicopter while its own cooldown runs",
      scan(d, ac("abc123", dist=0.8, alt=900), now=1_000_010) == [])
check("category A7 is a helicopter with no database entry",
      kinds(scan(d, ac("aaaac1", dist=2.5, alt=1500, category="A7"))) == ["helicopter"])
check("a helicopter far away is not", scan(d, ac("aaaac2", dist=10, alt=1500, category="A7")) == [])

# ---- notable ----------------------------------------------------------------------
d = ev.Detector()
out = scan(d, ac("c0ffee", dist=20, alt=40000))
check("a listed aircraft is notable", kinds(out) == ["notable"])
check("with the neutral label, never plane-alert-db's own",
      out[0]["label"] == "VIP aircraft" and "Dictator" not in json.dumps(out))
check("no operator unless notable-db kept one", "operator" not in out[0])
out = scan(d, ac("a11111", dist=20, alt=2000))
check("a kept operator is included", out and out[0].get("operator") == "State Police")
out = scan(d, ac("ae1234", dist=25, alt=20000))
check("a military address is notable", out and out[0]["label"] == "US military")
out = scan(d, ac("a90001", dist=12, alt=35000))
check("a notable type is notable", out and out[0]["label"] == "Boeing 747")
check("nothing notable beyond the radius", scan(d, ac("ae2222", dist=40, alt=20000)) == [])
check("an ordinary aircraft is nothing", scan(d, ac("a90002", dist=12, alt=8000)) == [])
check("a notable aircraft is reported once per pass", scan(d, ac("c0ffee", dist=10, alt=40000), now=1_000_100) == [])

# ---- what leaves the unit ---------------------------------------------------------
d = ev.Detector()
out = scan(d, ac("abc123", dist=1.3, alt=1049, r_dir=100.0),
           ac("aaaaa1", dist=3.2, alt=1234, squawk="7700"))
text = json.dumps(out).lower()
for word in ('"lat"', '"lon"', "latitude", "longitude", "r_dst", "r_dir", '"track"'):
    check(f"no event carries {word}", word not in text)
heli = [e for e in out if e["kind"] == "helicopter"][0]
check("distance is rounded to half a mile", heli["dist_nm"] == 1.5)
check("direction is a compass point, not a bearing", heli["dir"] == "E")
check("altitude is rounded to 100 ft", heli["alt_ft"] == 1000)
check("callsign is trimmed", heli["flight"] == "TEST1")

# ---- approaching aircraft (Live Activity) -----------------------------------------
def inbound(hex_, dist, bearing, track, gs, alt, **k):
    """An aircraft dist nm away at `bearing` from the antenna, flying `track`."""
    return ac(hex_, dist=dist, alt=alt, r_dir=bearing, track=track, gs=gs, **k)

d = ev.Detector()
out = scan(d, inbound("a90002", 8.0, 0, 180, 180, 3000))           # 8 nm north, heading straight at us
appr = [e for e in out if e["kind"] == "approach"]
check("a low plane heading our way is an approach", len(appr) == 1 and appr[0]["label"] == "Low overhead")
check("with the time to the pass (8 nm at 180 kt = 160 s)", appr and appr[0]["eta_s"] == 160)
check("an approach carries no position", appr and not any(k in appr[0] for k in ("lat", "lon", "r_dst", "r_dir")))
check("not again while it is on its way", [e for e in scan(d, inbound("a90002", 6.0, 0, 180, 180, 3000), now=1_000_040)
                                          if e["kind"] == "approach"] == [])
check("no end before the pass", not any(e["kind"] == "approach_end" for e in scan(d, now=1_000_100)))
out = scan(d, now=1_000_000 + 160 + ev.APPROACH_END_AFTER_S + 1)
check("an end shortly after the pass", [e["kind"] for e in out] == ["approach_end"] and out[0]["hex"] == "a90002")

d = ev.Detector()
check("too far out yet (8 nm at 120 kt = 240 s) is nothing",
      [e for e in scan(d, inbound("a90002", 8.0, 0, 180, 120, 3000)) if e["kind"] == "approach"] == [])
check("heading away is nothing",
      [e for e in scan(d, inbound("a90002", 5.0, 0, 0, 180, 3000)) if e["kind"] == "approach"] == [])
check("passing 3 nm wide is nothing",       # 5 nm east heading north: closest 5 nm, abeam now
      [e for e in scan(d, inbound("a90003", 5.0, 90, 0, 180, 3000)) if e["kind"] == "approach"] == [])
wide = ev.closest_approach({"r_dst": 5.0, "r_dir": 0.0, "track": 270.0, "gs": 180})
check("the geometry: crossing 5 nm north heading west never comes closer than 5 nm", wide and abs(wide[1] - 5.0) < 0.01 and wide[0] <= 0.5)
check("a high airliner overhead in 2 minutes is not an approach",
      [e for e in scan(d, inbound("a90002", 5.0, 0, 180, 180, 33000)) if e["kind"] == "approach"] == [])
out = scan(d, inbound("aaaac9", 2.8, 90, 270, 80, 1200, category="A7"))   # helicopter 2.8 nm east, heading west
appr = [e for e in out if e["kind"] == "approach"]
check("a helicopter heading our way is an approach", appr and appr[0]["label"] == "Helicopter")
check("a hovering helicopter predicts nothing",
      ev.closest_approach({"r_dst": 2.0, "r_dir": 0.0, "track": 180.0, "gs": 5}) is None)

# ---- flood control ----------------------------------------------------------------
d = ev.Detector()
many = [ac(f"b{i:05x}", dist=1.0, alt=2000) for i in range(80)]
out = scan(d, *many)
check("at most MAX_PER_HOUR ordinary events an hour", len(out) == ev.MAX_PER_HOUR)
out = scan(d, ac("bfffff", dist=100, squawk="7700"), now=1_000_010)
check("an emergency is never capped", kinds(out) == ["emergency"])
check("the cap frees up after an hour",
      len(scan(d, ac("cccccc", dist=1.0, alt=2000), now=1_000_000 + 3601)) == 1)
scan(d, now=1_000_000 + 8 * 3600)
check("finished passes are forgotten", len(d.fired) == 0)

# ---- sending ----------------------------------------------------------------------
posted, replies = [], []


def fake_post(batch):
    posted.append(list(batch))
    return replies.pop(0) if replies else (200, b"{}")


s = ev.Sender(post=fake_post)
now = 2_000_000
s.add([{"kind": "low_overhead", "ts": now, "hex": f"{i:06x}"} for i in range(25)])
line = s.flush(now)
check("sends a batch of at most BATCH", len(posted[-1]) == ev.BATCH and len(s.queue) == 5 and "sent" in line)
check("waits the minimum gap before the next request", s.flush(now + 1) is None)
s.flush(now + ev.MIN_SEND_GAP_S)
check("then sends the rest", len(s.queue) == 0 and len(posted) == 2)

s = ev.Sender(post=fake_post)
s.add([{"kind": "notable", "ts": now, "hex": "000001"}])
replies.append((503, b""))
line = s.flush(now)
check("a relay error keeps the events", len(s.queue) == 1 and "retrying" in line)
check("and backs off", s.flush(now + 5) is None)
replies.append((None, b"URLError"))
s.flush(now + ev.BACKOFF_S[0])
check("backs off further after repeated failures", s.next_try >= now + ev.BACKOFF_S[0] + ev.BACKOFF_S[1])
s.flush(now + 10_000)
check("a stale event expires instead of arriving late", len(s.queue) == 0)

s = ev.Sender(post=fake_post)
s.add([{"kind": "notable", "ts": now, "hex": "000002"}, {"kind": "notable", "ts": now, "hex": "000003"}])
replies.append((400, b""))
s.flush(now)
check("a batch the relay refuses is dropped, so it cannot block the queue", len(s.queue) == 0)

s = ev.Sender(post=fake_post)
s.add([{"kind": "low_overhead", "ts": now, "hex": f"{i:06x}"} for i in range(ev.QUEUE_MAX + 10)])
check("the queue is bounded; overflow drops the oldest",
      len(s.queue) == ev.QUEUE_MAX and s.queue[0]["hex"] == f"{10:06x}")

s = ev.Sender(post=lambda batch: (200, b'{"ok":true,"stored":0,"phones":0}'))
s.add([{"kind": "notable", "ts": now, "hex": "000004"}, {"kind": "notable", "ts": now, "hex": "000005"}])
line = s.flush(now)
check("a relay with no paired phone turns events off", s.unpaired and "events off" in line and not s.queue)

# ---- unpaired: pause, never write (the service's storage is read-only) -------------
os.makedirs(ev.hb.STATE_DIR, exist_ok=True)
with open(ev.CONFIG, "w") as f:
    json.dump({"enabled": True}, f)
air = os.path.join(tmp, "aircraft.json")
ev.AIRCRAFT_JSON = air
posts = []
reply = {"body": b'{"ok":true,"stored":0,"phones":0}'}
svc = ev.Service(detector=ev.Detector(), sender=ev.Sender(post=lambda b: (posts.append(b), (200, reply["body"]))[1]))
real_set = ev.set_enabled
ev.set_enabled = lambda on: (_ for _ in ()).throw(OSError(30, "Read-only file system"))


def feed(hex_):
    with open(air, "w") as f:
        json.dump({"aircraft": [ac(hex_, dist=1.0, alt=2000)]}, f)
    t = os.path.getmtime(air) + 1
    os.utime(air, (t, t))


try:
    feed("dd0001")
    svc.tick()
    check("an unpaired reply pauses the service without writing the setting", svc.paused_at is not False and len(posts) == 1)
    feed("dd0002")
    svc.sender.next_try = 0
    svc.tick()
    check("while paused, nothing more is sent", len(posts) == 1)
    time.sleep(0.01)
    with open(ev.CONFIG, "w") as f:
        json.dump({"enabled": True}, f)
    t = os.path.getmtime(ev.CONFIG) + 5
    os.utime(ev.CONFIG, (t, t))
    reply["body"] = b'{"ok":true,"stored":1,"phones":1}'
    feed("dd0003")
    svc.sender.next_try = 0
    svc.tick()
    check("pairing again (the setting rewritten) resumes it", svc.paused_at is False and len(posts) == 2)
finally:
    ev.set_enabled = real_set
    with open(ev.CONFIG, "w") as f:
        json.dump({"enabled": False}, f)

# ---- a restart does not report the same pass again ----------------------------------
fired = os.path.join(tmp, "fired.json")
d = ev.Detector()
scan(d, ac("abc123", dist=1.0, alt=1000))
d.save(fired)
d2 = ev.Detector()
d2.load(fired, now=1_000_060)
check("what was reported survives a restart", scan(d2, ac("abc123", dist=0.9, alt=900), now=1_000_060) == [])
d3 = ev.Detector()
d3.load(fired, now=1_000_000 + 7 * 3600)
check("but long-finished passes are not carried over", len(d3.fired) == 0)
with open(fired, "w") as f:
    f.write("not json")
d4 = ev.Detector()
d4.load(fired)
check("a damaged file is ignored, not fatal", d4.fired == {})

# ---- opt-in -----------------------------------------------------------------------
check("off until a phone is paired", ev.enabled() is False)
try:
    import cryptography  # noqa: F401
    ev.set_enabled(True)
    check("turning it on persists", ev.enabled() is True)
    ev.set_enabled(False)
    check("and off again", ev.enabled() is False)
except ImportError:
    pass

if failures:
    print(f"{len(failures)} of {checks} events checks FAILED:")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print(f"{checks}/{checks} events checks passed")
