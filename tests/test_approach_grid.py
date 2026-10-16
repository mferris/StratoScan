#!/usr/bin/env python3
"""The landing heatmap keeps every landing, as counts on a grid (2026-10-14).

It kept the last 6,000 raw positions, one a second per landing: on RDU that
was the last 15-40 landings. Now each landing adds one to every ~200 m
square it passed through. These checks run deploy/approach-store.py's own
code, and the page's binning under node, so the two cannot drift apart.

Run: python3 tests/test_approach_grid.py
"""
import importlib.util
import json
import os
import pathlib
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


tmp = tempfile.mkdtemp()
os.environ["STATE_DIRECTORY"] = tmp
spec = importlib.util.spec_from_file_location("approach_store", ROOT / "deploy" / "approach-store.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

RDU = (-78.7875, 35.8776)


def track(start, end, n=300):
    """One landing's points, one a second along a straight line."""
    return [[start[0] + (end[0] - start[0]) * k / n, start[1] + (end[1] - start[1]) * k / n] for k in range(n)]


north = track((RDU[0] + 0.01, RDU[1] + 0.18), (RDU[0], RDU[1]))
south = track((RDU[0] - 0.01, RDU[1] - 0.18), (RDU[0], RDU[1]))

# ---- counting ----------------------------------------------------------------
s = m.fresh_store()
check(m.add_landing(s, north, "a1b2c3", now=1000), "a landing is counted")
cells_one = len(s["cells"])
check(cells_one > 50 and all(n == 1 for n in s["cells"].values()),
      "once in each square it passed through, however many points fell in it")
check(not m.add_landing(s, north, "a1b2c3", now=1030), "the same aircraft from a second browser counts once")
check(m.add_landing(s, north, "a1b2c3", now=1000 + m.DEDUPE_S + 1), "but its next landing counts")
check(m.add_landing(s, north, None, now=1400) and m.add_landing(s, south, "d4e5f6", now=1400),
      "a landing without a hex (an older page) counts, and so does another aircraft's")
counts = sorted(s["cells"].values())
check(s["landings"] == 4 and counts[-1] == 4 and counts.count(3) == cells_one - 1,
      "the squares on the path flown three times count 3, the runway square all 4 landings")
pts = m.to_points(s)
check(len(pts) == len(s["cells"]) and all(len(p) == 3 for p in pts), "GET gives [lon, lat, landings] per square")
check(max(p[2] for p in pts) == 4 and all(abs(p[0] - RDU[0]) < 0.2 and abs(p[1] - RDU[1]) < 0.2 for p in pts),
      "at the squares' centres")

# every landing is kept: 10,000 landings later the store is still small
s = m.fresh_store()
rng = random.Random(7)
for k in range(10000):
    a = rng.uniform(0, 6.283)
    import math
    jitter = (rng.uniform(-0.004, 0.004), rng.uniform(-0.004, 0.004))
    start = (RDU[0] + 0.2 * math.cos(a if k % 2 else 1.4) + jitter[0], RDU[1] + 0.2 * math.sin(a if k % 2 else 1.4) + jitter[1])
    m.add_landing(s, track(start, RDU, 200), None, now=k)
size = len(json.dumps(s, separators=(",", ":")))
check(s["landings"] == 10000 and len(s["cells"]) <= m.MAX_CELLS, "10,000 landings are all counted")
check(size < 1_500_000, f"in a file that stays small ({size // 1000} KB, half of them from every direction)")
s["cells"] = {f"{i},{i}": 1 for i in range(m.MAX_CELLS)}
s["cells"]["busy"] = 99
m.add_landing(s, north, None, now=0)
check(len(s["cells"]) <= m.MAX_CELLS and s["cells"].get("busy") == 99,
      "past the cap the least-used squares make room, never the busy ones")

# ---- POST bodies ---------------------------------------------------------------
check(m.parse_landing({"hex": "a1b2c3", "points": north}) == (north, "a1b2c3"), "a landing with its hex")
check(m.parse_landing(north) == (north, None), "a bare list from an older page")
check(m.parse_landing({"hex": "NOT A HEX", "points": north}) == (north, None), "a bad hex is ignored, the landing kept")
check(m.parse_landing({"points": [[1, 2, 3]]}) is None and m.parse_landing({"points": []}) is None
      and m.parse_landing({"points": [[200, 0]]}) is None and m.parse_landing("x") is None,
      "anything else is refused")

# ---- the old points list converts once -------------------------------------------
old = north[:200] + south[:150] + north[:100]
with open(m.STORE_PATH, "w") as f:
    json.dump(old, f)
store, dirty = m.load_store()
check(store["landings"] == 3, "the old list's landings are told apart by the jumps between them")
check(max(store["cells"].values()) == 2 and not dirty, "a square counts once per run of points in it")
check(json.load(open(m.V1_BACKUP)) == old, "the old points are kept beside it")
on_disk = json.load(open(m.STORE_PATH))
check(on_disk.get("v") == 2 and on_disk["cells"] == store["cells"], "and the grid is written at once, not at the next flush")
again, _ = m.load_store()
check(again["cells"] == store["cells"], "a grid loads back as it was")

# ---- over HTTP --------------------------------------------------------------------
os.remove(m.STORE_PATH)
m._store, m._dirty, m._recent = None, False, {}
srv = m.http.server.ThreadingHTTPServer(("127.0.0.1", 0), m.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/approaches"
def post(body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req, timeout=5).status
    except urllib.error.HTTPError as e:
        return e.code
check(post({"hex": "a1b2c3", "points": north}) == 204 and post({"hex": "a1b2c3", "points": north}) == 204
      and post(south) == 204, "POST takes landings")
check(post({"points": [["x", 1]]}) == 400, "and refuses a bad one")
got = json.load(urllib.request.urlopen(url, timeout=5))
check(sorted(p[2] for p in got)[-1] == 1 + 1 and m._store["landings"] == 2,
      "GET returns the squares, the repeat counted once")
check(m._dirty and not os.path.exists(m.STORE_PATH), "kept in memory until the flush")
m.flush()
check(json.load(open(m.STORE_PATH))["landings"] == 2, "which writes it")
srv.shutdown()

# ---- the page bins the same way -----------------------------------------------------
html = (ROOT / "index.html").read_text()
start = html.index("const APPROACH_CELL_DEG")
end = html.index("// ---- Sighting counts")
block = html[start:end]
check("APPROACH_MAX_POINTS" not in html, "the page no longer caps the map at 6,000 points")
check(html.count("commitApproachTrack(pl.approachPoints, pl.hex)") == 2, "both ways a landing is confirmed send its hex")
heat = html[html.index("id: 'approaches-heat'"):][:4000]
check("'heatmap-weight': ['get', 'w']" in heat, "the heatmap weighs each square by its landings")
if not shutil.which("node"):
    print("skip page checks (no node)")
else:
    coords = [[rng.uniform(-180, 180), rng.uniform(-85, 85)] for _ in range(3000)]
    coords += [[k * 0.002 + 0.001, -k * 0.002 - 0.001] for k in range(-500, 500)]      # half-way points
    coords += [[RDU[0], RDU[1]], [0.0, 0.0], [-0.001, 0.001]]
    js = "let map = null; const posted = []; const APPROACH_STORE_URL = '/approaches';\nfunction storeWrite(url, body) { posted.push(body); return Promise.resolve(); }\nfunction drain(r) { return r; }\n" + block + r"""
const coords = JSON.parse(process.argv[1]);
const keys = coords.map(([lon, lat]) => approachCellOf(lon, lat));
commitApproachTrack(JSON.parse(process.argv[2]), 'a1b2c3');
commitApproachTrack(JSON.parse(process.argv[2]), 'a1b2c3');
commitApproachTrack(JSON.parse(process.argv[3]), undefined);
const g = approachPointsGeoJSON();
const ws = g.features.map(f => f.properties.w);
console.log(JSON.stringify({ keys, posted: JSON.parse(JSON.stringify(posted)), n: approachCells.size,
  wmax: Math.max(...ws), wmin: Math.min(...ws) }));
"""
    r = subprocess.run(["node", "-e", js, json.dumps(coords), json.dumps(north), json.dumps(south)],
                       capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stderr[-800:])
    py = [m.cell_of(lon, lat) for lon, lat in coords]
    check(o.get("keys") == py, f"the page and the store put all {len(coords)} test points in the same squares")
    check(o.get("posted", [{}])[0] == {"hex": "a1b2c3", "points": north} and o["posted"][2] == {"points": south},
          "the page posts a landing with its hex")
    s = m.fresh_store()
    for t in (north, north, south):
        m.add_landing(s, t, None, now=0)
    check(o.get("n") == len(s["cells"]), "and counts it locally just as the store does")
    check(o.get("wmax") == 1 and abs(o.get("wmin", 0) - 0.5) < 1e-9,
          "the busiest square (3 landings) weighs 1, a once-flown one log 2 / log 4")

shutil.rmtree(tmp, ignore_errors=True)
print("approach grid checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
