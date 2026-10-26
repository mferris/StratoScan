#!/usr/bin/env python3
"""No outside service is asked anything built from the radar's exact position (2026-10-26).

On the panel and in every browser at home the page's `home` is the antenna's
exact position. The lightning alert sent it to SSEC RealEarth to about 11 m,
with sixteen ring points round it, every two minutes; the weather asked
Open-Meteo at 2 dp. Every third-party request is now built from homeArea(),
`home` rounded to 0.05 degrees, as the radar asks Overpass and adsb.lol.

Two parts. A scan of the page's script: no top-level statement that reads
home.lat or home.lon also names a third-party URL, fetches anything but the
radar's own paths, or hands arguments to a function that builds a
third-party URL. Then the page's own probe, weather and tile-check code run
under node with a stand-in fetch, for two homes in the same 0.05-degree
square: they must ask exactly the same things.

Run: python3 tests/test_page_third_party_home.py
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


script = max(re.findall(r"<script>(.*?)</script>", html, re.S), key=len)
code = "\n".join(l for l in script.splitlines() if not l.strip().startswith("//"))

# ---- the scan ----------------------------------------------------------------
# Top-level statements: each begins on a line at column 0 that is not a closer.
chunks = []
for l in code.splitlines():
    if l and not l[0].isspace() and l[0] not in "})]":
        chunks.append([l])
    elif chunks:
        chunks[-1].append(l)
chunks = ["\n".join(c) for c in chunks]

SELF = re.compile(r"https?://(127\.0\.0\.1|localhost|www\.w3\.org)")
consts = {}
for c in chunks:
    m = re.match(r"const (\w+) = (['`])([^'`]*)\2", c)
    if m:
        consts[m.group(1)] = m.group(3)
url_consts = {n for n, v in consts.items() if v.startswith("https://") and not SELF.match(v)}
own_consts = {n for n, v in consts.items() if v.startswith("/")}


def name_of(c):
    m = re.match(r"(?:async )?function (\w+)\(|(?:const|let) (\w+) = (?:async )?(?:function\b|\([^)]*\) =>|\w+ =>)", c)
    return (m.group(1) or m.group(2)) if m else None


def third_party(body):
    lits = [u for u in re.findall(r"https://[^\s'`\"]+", body) if not SELF.match(u)]
    return lits + [n for n in url_consts if re.search(r"\b%s\b" % n, body)]


def foreign_fetches(body):
    out = []
    for arg in re.findall(r"\bfetch\(\s*([^,)]+)", body):
        a = arg.strip()
        if re.match(r"['`]/", a):
            continue
        m = re.match(r"`\$\{(\w+)\}", a) or re.match(r"(\w+)$", a)
        if m and m.group(1) in own_consts:
            continue
        out.append(a)
    return out


builders = {name_of(c) for c in chunks if name_of(c) and third_party(c)}
check({"probeLightningValue", "refreshWeather"} <= builders and "WEB_FONTS_URL" in url_consts,
      "the scan finds the page's third-party URL builders (%d of them)" % len(builders))
readers, bad = [], []
for c in chunks:
    who = name_of(c) or c.splitlines()[0][:50]
    reads = re.search(r"\bhome\.(?:lat|lon)\b", c)
    handed = [b for b in builders if re.search(r"\b%s\([^)]*\bhome\b(?!\.\w)" % b, c)]
    if handed:
        bad.append("%s hands home to %s" % (who, ", ".join(handed)))
    if not reads:
        continue
    readers.append(who)
    calls = [b for b in builders if b != name_of(c) and re.search(r"\b%s\((?!\))" % b, c)]
    found = third_party(c) + calls + foreign_fetches(c)
    if found:
        bad.append("%s reads home and asks %s" % (who, ", ".join(found)))
check(len(readers) >= 8 and "homeArea" in readers, "the scan finds the code that reads the position (%d places)" % len(readers))
check(not bad, "no third-party URL is built from the unrounded home" + ("" if not bad else ": " + "; ".join(bad)))
check(re.search(r"^const HOME_AREA_DEG = 0\.05;", code, re.M) is not None,
      "homeArea() rounds to 0.05 degrees, as the radar asks Overpass and adsb.lol")

# ---- the page's own code, run -----------------------------------------------


def function(head):
    if head not in code:
        return ""
    start = code.index(head)
    return code[start:code.index("\n}\n", start) + 3]


def line(pattern):
    m = re.search(pattern, code, re.M)
    return m.group(0) if m else ""


src = "\n".join([
    line(r"^const REMOTE_TIMEOUT_MS = .*$"), line(r"^const ONLINE_STYLE_TIMEOUT_MS = .*$"),
    function("function timeLimit("), function("function drain("), function("function destinationPoint("),
    line(r"^const HOME_AREA_DEG = .*$"), function("function homeArea("),
    line(r"^const LIGHTNING_LON_MIN = .*$"), line(r"^const LIGHTNING_LAT_MIN = .*$"),
    function("function lightningCovers("),
    line(r"^const LIGHTNING_PROBE_PRODUCT = .*$"), line(r"^const LIGHTNING_ALERT_RADIUS_NM = .*$"),
    line(r"^const LIGHTNING_ALERT_CLEAR_RADIUS_NM = .*$"), line(r"^const LIGHTNING_PROBE_RING_POINTS = .*$"),
    line(r"^let lightningAlerted = .*$"), line(r"^let lightningChecking = .*$"),
    function("async function probeLightningValue("), function("async function checkLightningNearby("),
    line(r"^const US_TIME_ZONES = .*$"), function("function useFahrenheit("),
    line(r"^let weatherAt = .*$"), function("async function refreshWeather("),
    function("async function onlineTilesReachable("),
])

if not shutil.which("node"):
    print("skip behaviour checks (no node)")
else:
    js = r"""
let home = null;
let AIRPORT = { code: 'RDU', country: 'US' };
let alertSettings = { lightningAlert: true };
const WMO = {};
let asked = [];
async function fetch(url) {
  asked.push(String(url));
  if (String(url).includes('openfreemap')) return { ok: true, json: async () => ({ tiles: ['https://tiles.example.org/{z}/{x}/{y}.pbf'] }) };
  return { ok: true, status: 200, text: async () => 'Data value: <b>0</b>', json: async () => ({}) };
}
function playLightningAlertSound() {}
function showToast() {}
""" + src + r"""
const style = { sources: { base: { type: 'vector', url: 'https://tiles.openfreemap.org/planet' } } };
async function everything(h) {
  home = h; asked = []; lightningAlerted = false; lightningChecking = false;
  await checkLightningNearby();
  await refreshWeather().catch(() => {});
  await onlineTilesReachable(style);
  return asked.slice();
}
(async () => {
  const out = {};
  const rdu = await everything({ lat: 35.8776, lon: -78.7875 });
  const near = await everything({ lat: 35.8901, lon: -78.8122 });   // the same 0.05-degree square
  out.rdu = rdu;
  out.same = JSON.stringify(rdu) === JSON.stringify(near);
  out.probes = rdu.filter(u => u.includes('/api/probe')).length;
  out.london = await everything({ lat: 51.4700, lon: -0.4543 });
  console.log(JSON.stringify(out));
})();
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stdout[-800:], r.stderr[-1500:])
    rdu = o.get("rdu") or []
    check(o.get("probes") == 17, f"the lightning alert still probes the centre and two rings of eight ({o.get('probes')} probes)")
    check(any("realearth.ssec.wisc.edu" in u and "lat=35.9000&lon=-78.8000" in u for u in rdu),
          "the centre probe is the radar's 0.05-degree square, not the antenna")
    check(any("api.open-meteo.com" in u and "latitude=35.90&longitude=-78.80" in u for u in rdu),
          "the weather is asked for the same square")
    check(len(rdu) == 20 and o.get("same") is True,
          "two homes in the same 0.05-degree square ask every outside service exactly the same things")
    exact = re.compile(r"35\.877|35\.878|78\.787|78\.788")
    check(rdu and not any(exact.search(u) for u in rdu), "no request carries the antenna's position at any precision")
    london = o.get("london") or []
    check(london and not any("realearth" in u for u in london),
          "outside GOES-East's view RealEarth is not asked at all")

print("page third-party position checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
