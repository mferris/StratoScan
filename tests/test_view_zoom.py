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
end = html.index("function zoomViewAbout(k")
end = html.index("\n}\n", end) + 3
block = html[start:end]
check("VIEW_MAX_EAST_NM" in block and "VIEW_MAX_LAT" in block, "the view's limits are the world map's edges")

if not shutil.which("node"):
    print("skip behaviour checks (no node)")
else:
    js = r"""
const W = 1080, CX = 540, CY = 540, R = 500, RANGE_NM = 20;
const view = { ox: 0, oy: 0, scale: 1 };
const home = { lat: 35.8776, lon: -78.7875 };
let map = null;   // no map here: the radar's own maths (the map path is checked in a browser)
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
// Pan so the view is centred on (lat, lon), as viewCentreLatLon reads it.
function centreOn(lat, lon, sc) {
  const pxPerNm = R * sc / RANGE_NM;
  let dl = lon - home.lon; if (dl > 180) dl -= 360; if (dl < -180) dl += 360;
  const east = dl * 60 * Math.cos(lat * Math.PI / 180), north = (lat - home.lat) * 60;
  setView(-east * pxPerNm, north * pxPerNm, sc);
}
function pinchIn(lat, lon, steps = 12) {
  centreOn(lat, lon, RANGE_NM / 400);            // 400 nm across
  const mx = CX + 60, my = CY + 40, before = at(mx, my);
  for (let i = 0; i < steps; i++) zoomViewAbout(1.35, mx, my);
  return { drift: drift(before, at(mx, my)), rangeNm: RANGE_NM / view.scale };
}
const out = {
  near: pinchIn(36.1, -79.3),          // Greensboro
  far: pinchIn(41.9, -87.6),           // Chicago, 550 nm
  france: pinchIn(48.86, 2.35),        // Paris: still jumped home with the first fix
  tokyo: pinchIn(35.7, 139.7),         // across the dateline
};
setView(0, 0, 1);
setView(-1e12, 1e12, 1);                         // a swipe off the top left of the world
const pxPerNm = R / RANGE_NM;
out.edge = { east: -view.ox / pxPerNm, lat: home.lat + view.oy / pxPerNm / 60 };
console.log(JSON.stringify(out));
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stderr[-600:])
    for key, what in (("near", "near the radar"), ("far", "over Chicago"),
                      ("france", "over France (still jumped home with the first fix)"), ("tokyo", "over Tokyo")):
        d = o.get(key, {})
        check(d.get("drift", 99) < 0.01 and d.get("rangeNm", 99) < 30, f"a pinch in keeps the spot under the fingers {what}")
    src = html.split("function zoomViewAbout(k")[1][:900]
    check("if (map && viewFarFromHome()) { zoomViewAboutOnMap(sc, mx, my); return; }" in src,
          "far from the radar the zoom is worked out on the real map (checked in a browser: Paris 0.06 km, Tokyo 0.03 km of drift)")
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("//"))
    check("isStyleLoaded" not in code,
          "and not only while the map's style is settled (a refresh made one step slide 19 km)")
    e = o.get("edge", {})
    check(abs(abs(e.get("east", 0)) - 180 * 60) < 1, "a wild swipe stops at the far side of the world, not beyond")
    check(abs(e.get("lat", 0) - 85) < 0.01, "and no nearer a pole than the map can show (85 degrees)")

print("view zoom checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
