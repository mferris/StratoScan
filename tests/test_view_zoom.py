#!/usr/bin/env python3
"""A pinch zooms about the spot under the fingers, wherever the view is
(2026-10-14).

On RDU's panel, panned far from the radar and pinching in, the view "zooms in
and jumps to the right and down": setView limited the view's offset in screen
pixels, and zooming in multiplies the offset of a far-off place until it hit
that limit, which dragged the view back towards the radar. Near the radar it
worked, because the offsets stayed small. The limit is a distance now.

The page's own view code is run under node with a stand-in canvas.

Run: python3 tests/test_view_zoom.py
"""
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
html = (ROOT / "index.html").read_text()
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


start = html.index("const VIEW_MIN_SCALE")
end = html.index("function zoomViewAbout")
end = html.index("\n}\n", end) + 3
block = html[start:end]
check("VIEW_MAX_NM_FROM_HOME / RANGE_NM" in block, "the view's limit is a distance from the radar")

if not shutil.which("node"):
    print("skip behaviour checks (no node)")
else:
    js = r"""
const W = 1080, CX = 540, CY = 540, R = 500, RANGE_NM = 20;
const view = { ox: 0, oy: 0, scale: 1 };
const home = { lat: 35.8776, lon: -78.7875 };
let viewFeedOn = false, viewLocked = false, followHex = null, canvasDirty = false;
function syncMapToView() {} function viewLooksBeyondRing() { return false; } function refreshViewFeed() {}
const locEl = {}; function formatLoc() { return ''; }
const cls = { toggle() {} }; const document = { getElementById: () => ({ classList: cls }) };
function setTimeout() { return 0; } function clearTimeout() {}
""" + block + r"""
function at(x, y) {
  const nmPerPx = RANGE_NM / (R * view.scale);
  const east = (x - CX - view.ox) * nmPerPx, north = -(y - CY - view.oy) * nmPerPx;
  const lat = home.lat + north / 60;
  return { lat, lon: home.lon + east / (60 * Math.cos(lat * Math.PI / 180)) };
}
function drift(a, b) { return Math.hypot((a.lat - b.lat) * 60, (a.lon - b.lon) * 60 * Math.cos(a.lat * Math.PI / 180)); }
function pinchIn(awayNm, steps = 10) {
  const sc = RANGE_NM / 400;                      // 400 nm across
  setView(awayNm / RANGE_NM * R * sc, 0, sc);     // the view centred awayNm west of the radar
  const mx = CX + 60, my = CY + 40, before = at(mx, my);
  for (let i = 0; i < steps; i++) zoomViewAbout(1.35, mx, my);
  return { drift: drift(before, at(mx, my)), rangeNm: RANGE_NM / view.scale };
}
const out = { near: pinchIn(30), far: pinchIn(600), farther: pinchIn(1800) };
setView(0, 0, 1);
setView(1e9, -1e9, 1);                           // a swipe that would leave the continent
const nmAway = Math.hypot(view.ox, view.oy) / R * RANGE_NM;
out.capNm = nmAway;
console.log(JSON.stringify(out));
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stderr[-600:])
    check(o.get("near", {}).get("drift", 99) < 0.01, "pinching in near the radar keeps the spot under the fingers")
    check(o.get("far", {}).get("drift", 99) < 0.01 and o.get("far", {}).get("rangeNm", 0) < 30,
          "and 600 nm away (it drifted 440 nm back towards the radar before)")
    check(o.get("farther", {}).get("drift", 99) < 0.01, "and 1,800 nm away")
    cap = o.get("capNm", 0)
    check(2400 < cap < 3600, f"a wild swipe still stops a continent away (about {cap:.0f} nm), not lost for good")

print("view zoom checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
