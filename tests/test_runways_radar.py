#!/usr/bin/env python3
"""The radar keeps the runway outlines and hands them out (#87, 2026-10-26).

The kiosk, the public page and the app each asked OpenStreetMap's Overpass
service for the runways round the radar; the kiosk sent it the antenna's
exact position, and Overpass is often slow or refusing. Now offline-map.py
asks once a month, for a box round the receiver rounded to 0.05 degrees,
and keeps the answer in /var/www/html/offline-map/runways.geojson; the core
feed serves it at /api/runways, from disk, with an ETag.

This checks the question Overpass gets (with urlopen stood in), the file's
shape and how it is written, when it is fetched again, the core feed's
answers, and that the public page's policy no longer lists Overpass.

Run: python3 tests/test_runways_radar.py
"""
import http.client
import importlib.util
import io
import json
import math
import os
import pathlib
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


RDU = (35.8776, -78.7875)
tmp = pathlib.Path(tempfile.mkdtemp())
os.environ["STRATOSCAN_WEB_ROOT"] = str(tmp / "www")
os.environ["STRATOSCAN_OFFLINE_STATE"] = str(tmp / "state")
spec = importlib.util.spec_from_file_location("offline_map", D / "offline-map.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.RECEIVER_JSON = str(tmp / "receiver.json")


def place(lat, lon):
    with open(m.RECEIVER_JSON, "w") as f:
        json.dump({"lat": lat, "lon": lon}, f)


# A small Overpass answer: two runways, a taxiway, and the ways to leave out.
ELEMENTS = [
    {"type": "way", "id": 1, "nodes": [11, 12], "tags": {"aeroway": "runway", "ref": "5L/23R"}},
    {"type": "way", "id": 2, "nodes": [13, 14, 15], "tags": {"aeroway": "taxiway"}},
    {"type": "way", "id": 3, "nodes": [11, 99], "tags": {"aeroway": "runway", "ref": "x"}},     # one point known
    {"type": "way", "id": 4, "nodes": [11, 12], "tags": {"aeroway": "apron"}},
    {"type": "way", "id": 5, "nodes": [11, 12]},                                                 # no tags
    {"type": "way", "id": 6, "nodes": [12, 13], "tags": {"aeroway": "runway", "ref": "14/32"}},
    {"type": "node", "id": 11, "lat": 35.8611, "lon": -78.8020},
    {"type": "node", "id": 12, "lat": 35.8932, "lon": -78.7741},
    {"type": "node", "id": 13, "lat": 35.8700, "lon": -78.7900},
    {"type": "node", "id": 14, "lat": 35.8710, "lon": -78.7890},
    {"type": "node", "id": 15, "lat": 35.8720, "lon": -78.7880},
]
FEATURES = [
    {"type": "Feature", "properties": {"aeroway": "runway", "ref": "5L/23R"},
     "geometry": {"type": "LineString", "coordinates": [[-78.8020, 35.8611], [-78.7741, 35.8932]]}},
    {"type": "Feature", "properties": {"aeroway": "taxiway", "ref": ""},
     "geometry": {"type": "LineString", "coordinates": [[-78.7900, 35.8700], [-78.7890, 35.8710], [-78.7880, 35.8720]]}},
    {"type": "Feature", "properties": {"aeroway": "runway", "ref": "14/32"},
     "geometry": {"type": "LineString", "coordinates": [[-78.7741, 35.8932], [-78.7900, 35.8700]]}},
]


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


asked = []
answer = {"elements": ELEMENTS}


def fake_urlopen(req, timeout=None):
    asked.append((req, timeout))
    if isinstance(answer, Exception):
        raise answer
    return Answer(json.dumps(answer).encode())


m.urllib.request.urlopen = fake_urlopen
built = []                     # the map's own build (Protomaps) is not what this tests
m.build = lambda lat, lon: built.append((lat, lon))

# ---- the question Overpass gets -------------------------------------------------
check(m.runway_centre(*RDU) == (35.9, -78.8), "the receiver is rounded to 0.05 degrees: RDU is asked about as 35.9, -78.8")
place(*RDU)
check(m.needs_runways() == (35.9, -78.8), "no outlines yet: fetch them for the rounded centre")
check(m.main(["offline-map.py", "ensure"]) == 0 and len(asked) == 1, "ensure asks Overpass once")
req, timeout = asked[0]
query = urllib.parse.parse_qs(req.data.decode())["data"][0]
check(req.full_url == "https://overpass-api.de/api/interpreter" and req.get_method() == "POST",
      "a POST to Overpass's interpreter")
check(req.get_header("Content-type") == "application/x-www-form-urlencoded", "form-encoded, as the kiosk sent it")
ua = req.get_header("User-agent") or ""
check("StratoScan" in ua and "github.com/mferris/StratoScan" in ua, "with a User-Agent naming StratoScan and the project: %s" % ua)
check(timeout == 30, "with a 30 s time limit (%s)" % timeout)
check(query.startswith("[out:json][timeout:25];") and query.endswith("out body;>;out skel qt;")
      and query.count('way["aeroway"="runway"]') == 1 and query.count('way["aeroway"="taxiway"]') == 1,
      "the kiosk's query: runways and taxiways, their nodes")
boxes = re.findall(r"\(([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)\)", query)
s, w, n, e = (float(x) for x in boxes[0])
check(len(boxes) == 2 and boxes[0] == boxes[1], "the same box for both")
check(abs((s + n) / 2 - 35.9) < 1e-4 and abs((w + e) / 2 + 78.8) < 1e-4, "centred on the rounded position")
half_lat = (n - s) / 2 * 111320 / 1852
half_lon = (e - w) / 2 * 111320 * math.cos(math.radians(35.9)) / 1852
check(abs(half_lat - 22.5) < 0.01 and abs(half_lon - 22.5) < 0.01,
      "22.5 nm each way: the 20 nm ring and 2.5 for the rounding (%.2f, %.2f)" % (half_lat, half_lon))
check("35.8776" not in query and "78.7875" not in query and "35.877" not in query,
      "the receiver's exact position is nowhere in it")

# ---- the file -----------------------------------------------------------------------
path = pathlib.Path(m.RUNWAYS_FILE)
check(path == tmp / "www" / "offline-map" / "runways.geojson", "kept in the offline map's directory (web root/offline-map/runways.geojson)")
doc = json.loads(path.read_text(encoding="utf-8"))
check(doc["type"] == "FeatureCollection" and doc["features"] == FEATURES,
      "index.html's overpassToGeoJSON: lines with aeroway and ref (empty when untagged); a way with one known point, "
      "an apron and an untagged way left out")
check(doc["centre"] == [35.9, -78.8] and doc["radiusNm"] == 22.5, "it says where and how far: centre [35.9, -78.8], 22.5 nm")
check(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", doc["built"]) is not None, "when, in UTC: %s" % doc["built"])
check(doc["source"] == "OpenStreetMap via Overpass" and doc["licence"] == "ODbL 1.0, \u00a9 OpenStreetMap contributors",
      "and its source and licence, with the copyright sign")
check(oct(path.stat().st_mode & 0o777) == "0o644", "readable by lighttpd and the core feed")
check(sorted(p.name for p in path.parent.iterdir()) == ["runways.geojson"], "and nothing half-written left beside it")
good = path.read_bytes()
try:
    m.write_runways({"features": {1, 2}})       # json cannot write a set: a write that fails partway
except TypeError:
    pass
check(path.read_bytes() == good and sorted(p.name for p in path.parent.iterdir()) == ["runways.geojson"],
      "a write that fails leaves the previous file whole, and no temporary file (written, then renamed)")

# ---- when it is fetched again --------------------------------------------------------
check(m.needs_runways() is None, "current outlines for this place: nothing asked")
place(35.88, -78.79)
check(m.needs_runways() is None, "a move within the rounding: nothing asked")
old = time.time() - m.RUNWAYS_REFRESH_S - 1
os.utime(path, (old, old))
check(m.needs_runways() == (35.9, -78.8), "a month old: asked again")
os.utime(path, None)
place(52.3676, 4.9041)
check(m.needs_runways() == (52.35, 4.9), "a radar moved elsewhere: asked for its new place")
asked.clear()
answer = OSError("Overpass busy")
check(m.main(["offline-map.py", "ensure"]) == 1 and len(asked) == 1, "a failure is a failed run")
check(path.read_bytes() == good, "and the outlines kept are untouched")
check(m.needs_runways() is None, "after a failure, not asked again on the next run")
stamp = pathlib.Path(m.RUNWAYS_FAILED_STAMP)
old = time.time() - m.RUNWAYS_RETRY_S - 1
os.utime(stamp, (old, old))
check(m.needs_runways() == (52.35, 4.9), "but an hour later")
answer = {"elements": ELEMENTS, "remark": "runtime error: Query timed out in \"query\" at line 1 after 26 seconds."}
m.main(["offline-map.py", "ensure"])
check(path.read_bytes() == good and m.needs_runways() is None,
      "Overpass saying it gave up partway (200 with an error remark): nothing kept, asked again in an hour")
os.utime(stamp, (old, old))
asked.clear()
answer = {"elements": []}
m.main(["offline-map.py", "ensure"])
check(len(asked) == 1 and path.read_bytes() == good, "an empty answer is not written")
check(m.needs_runways() is None, "and not asked again on the next run")
os.utime(stamp, (old, old))
check(m.needs_runways() is None, "nor an hour later: there may truly be no runways")
old = time.time() - m.RUNWAYS_EMPTY_RETRY_S - 1
os.utime(stamp, (old, old))
check(m.needs_runways() == (52.35, 4.9), "but a day later")

# The map is current: ensure fetches the outlines without downloading the map again.
answer = {"elements": ELEMENTS}
place(*RDU)
os.makedirs(m.OUT_DIR, exist_ok=True)
with open(os.path.join(m.OUT_DIR, "meta.json"), "w") as f:
    json.dump({"lat": 35.88, "lon": -78.79, "built": int(time.time())}, f)
path.unlink()
built.clear()
asked.clear()
check(m.needs_build() is None and m.main(["offline-map.py", "ensure"]) == 0, "a current map and no outlines: ensure succeeds")
check(not built and len(asked) == 1 and path.exists(), "fetching only the outlines, not the map")

# A new location from setup: its outlines at once, whatever a failure said before.
asked.clear()
m._runways_failed(m.RUNWAYS_RETRY_S)
m.main(["offline-map.py", "build", "40.6413", "-73.7781"])
check(built == [(40.6413, -73.7781)] and len(asked) == 1 and json.loads(path.read_text())["centre"] == [40.65, -73.8],
      "build LAT LON: the map, and the outlines for the new place despite the earlier failure")
asked.clear()
m.main(["offline-map.py", "build", "40.6413", "-73.7781"])
check(len(asked) == 0, "the same place again: the outlines it has are kept")

# A rebuilt map replaces the whole directory; the outlines go with it.
staging = tmp / "staging"
staging.mkdir()
m.carry_runways(str(staging))
check((staging / "runways.geojson").read_bytes() == path.read_bytes(), "a rebuilt map's directory carries the outlines over")
check("carry_runways(staging)" in (D / "offline-map.py").read_text().split("def build(")[1].split("def current_meta(")[0],
      "and build() does that before it swaps the directories")

# ---- net-watchdog starts ensure when only the outlines are due ---------------------
wd = (D / "net-watchdog.py").read_text()
fn = wd.split("def maybe_build_offline_map(")[1].split("\ndef ")[0]
check("needs_runways" in fn and "needs_build() is None and runways is None" in fn,
      "net-watchdog runs ensure when the outlines are due, even with the map current")

# ---- the core feed serves them ----------------------------------------------------
def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def get(port, path, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", path, headers=headers or {})
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, dict((k.lower(), v) for k, v in r.getheaders()), body


core_dir = tmp / "core"
core_dir.mkdir()
runways = core_dir / "runways.geojson"
receiver = core_dir / "receiver.json"
(core_dir / "aircraft.json").write_text('{"now": 0, "aircraft": []}')
receiver.write_text(json.dumps({"lat": RDU[0], "lon": RDU[1]}))
port = free_port()
env = dict(os.environ, STRATOSCAN_CORE_PORT=str(port), STRATOSCAN_CORE_LOOKUPS="0",
           STRATOSCAN_AIRCRAFT_JSON=str(core_dir / "aircraft.json"), STRATOSCAN_RECEIVER_JSON=str(receiver),
           STRATOSCAN_RUNWAYS_FILE=str(runways), STRATOSCAN_TAR1090_DB=str(core_dir / "no-db-*"),
           STRATOSCAN_NOTABLE_JSON=str(core_dir / "no-notable.json"),
           STRATOSCAN_NETWORK_URL="http://127.0.0.1:9/network")
proc = subprocess.Popen([sys.executable, str(D / "core-feed.py")], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    code, h, body = get(port, "/api/runways")
    check(code == 404 and json.loads(body) == {"error": "not built"}, "no file yet: 404 not built")

    rdu_doc = dict(type="FeatureCollection", features=FEATURES, centre=[35.9, -78.8], radiusNm=22.5,
                   built="2026-10-26T12:00:00Z", source="OpenStreetMap via Overpass",
                   licence="ODbL 1.0, \u00a9 OpenStreetMap contributors")
    raw = json.dumps(rdu_doc, ensure_ascii=False).encode()
    runways.write_bytes(raw)
    code, h, body = get(port, "/api/runways")
    check(code == 200 and body == raw, "200 with the file's bytes")
    check(h.get("content-type") == "application/json", "as JSON")
    etag = h.get("etag") or ""
    check(re.fullmatch(r'"[0-9a-f]{16,}"', etag) is not None, "an ETag, quoted, from a hash of the bytes: %s" % etag)
    check(h.get("cache-control") == "max-age=3600", "kept an hour by a screen (%s)" % h.get("cache-control"))
    code, h, body = get(port, "/api/runways", {"If-None-Match": etag})
    check(code == 304 and body == b"" and h.get("etag") == etag, "If-None-Match with that ETag: 304, nothing sent again")
    code, h, body = get(port, "/api/runways", {"If-None-Match": '"something-else"'})
    check(code == 200 and body == raw, "another ETag: the whole answer")

    receiver.write_text(json.dumps({"lat": 35.95, "lon": -78.8}))
    code, h, body = get(port, "/api/runways")
    check(code == 404 and json.loads(body) == {"error": "not built"},
          "the radar moved on and the outlines are for its old place: 404, until the new ones are in")
    receiver.write_text(json.dumps({"lat": RDU[0], "lon": RDU[1]}))

    time.sleep(0.05)
    rdu_doc["features"] = FEATURES[:1]
    raw2 = json.dumps(rdu_doc).encode()
    runways.write_bytes(raw2)
    code, h, body = get(port, "/api/runways", {"If-None-Match": etag})
    check(code == 200 and body == raw2 and h.get("etag") not in (None, etag), "a new file: new bytes, a new ETag")

    runways.write_text("{not json")
    code, h, body = get(port, "/api/runways")
    check(code == 404, "a file it can't read: 404, not an error")
finally:
    proc.terminate()
    proc.wait(5)

core = (D / "core-feed.py").read_text()
served = core.split("class Runways:")[1].split("class Feed:")[0] + core.split("def _runways(self):")[1].split("def do_GET")[0]
check("urlopen" not in served and "urllib" not in served, "nothing in the answer's path can reach the network")

# ---- the public page's policy no longer lists Overpass ------------------------------
spec = importlib.util.spec_from_file_location("fg", D / "funnel-gateway.py")
fg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fg)
policy = fg.page_csp(b"<html><script>x()</script></html>")
check("overpass" not in policy, "the public page may no longer reach Overpass (connect-src)")
check("connect-src 'self' https://tiles.openfreemap.org" in policy, "and still reaches the rest it did")

privacy = (ROOT / "docs" / "privacy.md").read_text()
radar = privacy.split("## The radar")[1].split("## The iPhone app")[0]
check("Runway outlines" in radar and "once a month" in radar and "5 km" in radar,
      "the privacy policy says the radar asks Overpass once a month, about a place rounded to 5 km")
notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
row = next(l for l in notices.splitlines() if "Overpass" in l)
check("once a month" in row and "/api/runways" in row, "and the notices say how Overpass is asked now")

print("radar runway checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
