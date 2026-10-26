#!/usr/bin/env python3
"""The kiosk and the public page draw the radar's own runway outlines (#87, 2026-10-26).

The page asked OpenStreetMap's Overpass API for the runways itself: from the
kiosk at every start, and from every visitor's browser on the public page,
with the antenna's exact position in the query, and with no time limit. The
radar now keeps a copy (deploy/offline-map.py, about once a month, by its
position rounded to 0.05 degrees) and core-feed.py serves it at /api/runways.
The page asks only that, with a limit, keeps its localStorage copy, and asks
again every few minutes while the radar has none.

The page's own loadRunways() and loadCachedRunways() run under node with a
stand-in radar, clock, map and localStorage.

Run: python3 tests/test_page_runways.py
"""
import json
import pathlib
import re
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


code = "\n".join(l for l in html.splitlines() if not l.strip().startswith("//"))
check("overpass-api.de" not in html and "OVERPASS_" not in code and "overpassToGeoJSON" not in code,
      "the page never asks Overpass, so no viewer sends it the antenna's position")
check("const RUNWAYS_URL = '/api/runways';" in code, "it asks the radar's own copy, on the page's own address")
check("map.on('load', loadCachedRunways);" in code and "map.on('load', loadRunways);" in code,
      "the kept copy is drawn as the map loads, and the radar asked behind it")


def function(head):
    if head not in code:
        return ""
    start = code.index(head)
    return code[start:code.index("\n}\n", start) + 3]


def line(pattern):
    m = re.search(pattern, code, re.M)
    return m.group(0) if m else ""


src = "\n".join([
    line(r"^const RUNWAYS_URL = .*$"), line(r"^const RUNWAYS_RETRY_MS = .*$"), line(r"^const RUNWAY_CACHE_KEY = .*$"),
    function("function runwaysAreHere("), function("function loadCachedRunways("),
    line(r"^let runwaysRetry = .*$"), function("async function loadRunways("),
])

if not shutil.which("node"):
    print("skip behaviour checks (no node)")
else:
    js = r"""
let now = 0; let timers = [];
function setTimeout(fn, ms) { const t = { at: now + ms, fn, ms }; timers.push(t); return t; }
function clearTimeout(t) { timers = timers.filter(x => x !== t); }
const LOCAL_SLOW_TIMEOUT_MS = 20000;
const store = new Map();
const localStorage = { getItem: k => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, String(v)) };
const drain = r => r;
let home = { lat: 35.8776, lon: -78.7875 };
let map = { id: 1 };
let applied = [];
function applyRunwayData(g) { applied.push(g); }
let answer = null, asked = [];
async function fetch(url, opts = {}) {
  asked.push({ url, opts });
  const a = typeof answer === 'function' ? await answer() : answer;
  if (a instanceof Error) throw a;
  return { ok: a.status === 200, status: a.status, json: async () => a.body };
}
const rdu = {
  type: 'FeatureCollection',
  features: [{ type: 'Feature', properties: { aeroway: 'runway', ref: '5L/23R' },
               geometry: { type: 'LineString', coordinates: [[-78.79, 35.86], [-78.77, 35.89]] } }],
  centre: [35.9, -78.8], radiusNm: 22.5, built: '2026-10-26T12:00:00Z',
  source: 'OpenStreetMap via Overpass', licence: 'ODbL 1.0, © OpenStreetMap contributors',
};
""" + src + r"""
const reset = () => { store.clear(); applied = []; asked = []; timers = []; map = { id: 1 }; };
(async () => {
  const out = {};
  out.retryMs = RUNWAYS_RETRY_MS;

  reset(); answer = { status: 404, body: { error: 'not built' } };
  await loadRunways();
  out.notBuilt = applied.length === 0 && !store.size && timers.length === 1 && timers[0].ms === RUNWAYS_RETRY_MS;
  const req = asked[0] || { opts: {} };
  out.request = req.url === '/api/runways' && req.opts.signal instanceof AbortSignal && !req.opts.method && !req.opts.body;
  answer = { status: 200, body: rdu };
  timers[0].fn(); await new Promise(r => setImmediate(r));
  out.retried = asked.length === 2 && applied.length === 1 && timers.length === 0;

  reset(); answer = new DOMException('No answer in time', 'TimeoutError');
  await loadRunways();
  out.timeoutRetries = applied.length === 0 && timers.length === 1;
  await loadRunways();
  out.oneRetryOnly = timers.length === 1;

  reset(); answer = { status: 200, body: rdu };
  await loadRunways();
  out.drawn = applied.length === 1 && applied[0].features.length === 1 && timers.length === 0;
  out.kept = JSON.parse(store.get(RUNWAY_CACHE_KEY) || 'null')?.centre?.[0] === 35.9;

  reset(); answer = { status: 200, body: { ...rdu, features: [] } };
  await loadRunways();
  out.emptyNotKept = applied.length === 0 && !store.size && timers.length === 1;

  reset(); answer = { status: 200, body: { ...rdu, centre: [51.5, -0.1] } };
  await loadRunways();
  out.elsewhereNotDrawn = applied.length === 0 && !store.size && timers.length === 1;

  reset(); answer = () => { map = { id: 2 }; return { status: 200, body: rdu }; };
  await loadRunways();
  out.newMapAsksAgain = applied.length === 0 && store.size === 1;

  reset(); store.set(RUNWAY_CACHE_KEY, JSON.stringify(rdu));
  loadCachedRunways();
  out.cachedDrawn = applied.length === 1;
  reset(); store.set(RUNWAY_CACHE_KEY, JSON.stringify({ ...rdu, centre: [51.5, -0.1] }));
  loadCachedRunways();
  out.cachedElsewhereNot = applied.length === 0;
  reset(); store.set(RUNWAY_CACHE_KEY, JSON.stringify({ type: 'FeatureCollection', features: rdu.features }));
  loadCachedRunways();
  out.oldCopyDrawn = applied.length === 1;
  console.log(JSON.stringify(out));
})();
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stdout[-800:], r.stderr[-1500:])
    check(o.get("request") is True, "the page asks /api/runways with a time limit, a plain GET")
    check(o.get("notBuilt") is True, "not built yet (404): nothing drawn or kept, and asked again later")
    check(isinstance(o.get("retryMs"), int) and 60 * 1000 <= o["retryMs"] <= 15 * 60 * 1000,
          f"a few minutes later ({o.get('retryMs')} ms), not in a tight loop")
    check(o.get("retried") is True, "and drawn once the radar has it")
    check(o.get("timeoutRetries") is True and o.get("oneRetryOnly") is True,
          "a radar that does not answer in time: asked again later, one retry waiting at a time")
    check(o.get("drawn") is True and o.get("kept") is True, "the radar's copy is drawn and kept for the next start")
    check(o.get("emptyNotKept") is True, "an empty copy is neither drawn nor kept")
    check(o.get("elsewhereNotDrawn") is True, "a copy built for somewhere else is not drawn")
    check(o.get("newMapAsksAgain") is True, "an answer for a map since replaced is kept, not drawn on the new one")
    check(o.get("cachedDrawn") is True and o.get("cachedElsewhereNot") is True,
          "the kept copy is drawn at once, unless it was built for somewhere else")
    check(o.get("oldCopyDrawn") is True, "a copy kept before #87, with no centre, is drawn as before")

print("page runway checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
