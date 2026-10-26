#!/usr/bin/env python3
"""The public page leaves out what is measured from the antenna's exact position (2026-10-26).

The radar counts the passes that come within 2 miles of the antenna and keeps
the closest and farthest contacts, each measured from its exact position. Over
the public address those answers no longer carry them (the gateway's part),
and the page leaves out their rows there: the "Within 2 mi" field in both
detail panels, "Came within 2 miles" on the Overview and the year in review,
the Close encounters screen, and the closest and farthest records. The
radar's own screen and every browser at home keep them all.

The Statistics screens run under node with the page's own renderers, once
as each kind of viewer; the panels are checked in the page's source.

Run: python3 tests/test_page_public_rows.py
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


def function(head):
    if head not in code:
        return ""
    start = code.index(head)
    return code[start:code.index("\n}\n", start) + 3]


def block(head, close):
    if head not in code:
        return ""
    start = code.index(head)
    return code[start:code.index(close, start) + len(close)]


def line(pattern):
    m = re.search(pattern, code, re.M)
    return m.group(0) if m else ""


# ---- the panels ---------------------------------------------------------------
fields = re.findall(r"(.{0,40})<div class=\"dp-field\"><div class=\"dp-label\">Within 2 ?mi</div>", code)
check(len(fields) == 2, "both detail panels have a 'Within 2 mi' field (%d found)" % len(fields))
check(fields and all(f.endswith("${PUBLIC_PAGE ? '' : `") for f in fields),
      "and the public page leaves it out of both")
check(code.count('<div class="dp-value">${esc(String(counts.') == 4 and '<div class="dp-value">${counts.' not in code,
      "the panels' counts are escaped like every other value from the radar")

# ---- the Statistics screens, as each viewer -------------------------------------
src = "\n".join([
    line(r"^const PUBLIC_PAGE = .*$"), function("function esc("), line(r"^const ALERT_RADIUS_MI = .*$"),
    block("const OP_LABELS = {", "\n};"), block("const KIND_LABELS = {", "\n};"),
    block("const STATS_SCREENS = [", "\n];"),
    function("function sharePct("), function("function statNum("), function("function statRow("),
    function("function statBars("), function("function statsDateLine("),
    line(r"^const MONTHS_SHORT = .*$"), line(r"^function hourLabel\(.*$"),
    function("function renderYearInReview("), function("function renderStatsScreen("),
    line(r"^const DOW_LABELS = .*$"), function("function weekChart("), function("function fmtHour("),
    function("function renderStatistics("),
])

st = {
    "since": 1760000000, "heard": 1200, "visits": 3400, "nearby": 170, "networkOnly": 50,
    "byOp": {k: {"ac": 10, "visits": 30, "nearby": 4} for k in ("com", "pri", "mil", "unk")},
    "byKind": {k: {"ac": 10, "visits": 30, "nearby": 4} for k in ("heavy", "jet", "prop", "heli", "lta", "unknown")},
    "records": {"far": {"v": 187.3, "hex": "a1b2c3", "cs": "DAL140", "at": 1761000000},
                "near": {"v": 0.3, "hex": "a4d5e6", "cs": "N123AB", "at": 1761100000},
                "high": {"v": 45000, "hex": "a7b8c9", "cs": "UAL1", "at": 1761200000},
                "fast": {"v": 612, "hex": "a7b8c9", "cs": "UAL1", "at": 1761200000}},
    "hours": [i % 7 for i in range(24)], "dows": [3, 4, 5, 6, 7, 8, 9], "top": [],
}
year = {"ready": True, "year": 2026, "countingSince": 1760000000, "visits": 3400, "aircraft": 1200,
        "newAircraft": 300, "nearby": 170, "busiestMonth": 9, "months": [100] * 12, "busiestHour": 17,
        "top": [], "kinds": {"jet": 2000}, "records": st["records"]}
# What the public answers carry once the gateway has had them.
public_st = {k: v for k, v in st.items() if k != "nearby"}
public_st["records"] = {k: v for k, v in st["records"].items() if k not in ("far", "near")}
public_year = {k: v for k, v in year.items() if k != "nearby"}
public_year["records"] = public_st["records"]

LAN = ("localhost", "192.168.1.23", "stratoscan.local")
PUBLIC = ("radar.example.ts.net",)


def screens(host, stats, yr):
    js = r"""
const location = { hostname: %s };
const IS_KIOSK = false;
let flightStats = null, statsView = null;
const scorecardSubtitle = () => '', renderScorecard = () => '', renderVisitors = () => '';
""" % json.dumps(host) + src + r"""
let yearStats = %s;
const st = %s;
flightStats = st;
const out = { menu: renderStatistics(), year: renderStatsScreen('year', st) };
for (const s of STATS_SCREENS) if (s.key !== 'year') out[s.key] = renderStatsScreen(s.key, st);
console.log(JSON.stringify(out));
""" % (json.dumps(yr), json.dumps(stats))
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        print(r.stdout[-800:], r.stderr[-1500:])
        return {}


def text(o):
    return re.sub(r"\s+", " ", " ".join(o.values()))


if not shutil.which("node"):
    print("skip behaviour checks (no node)")
else:
    for host in LAN:
        o = screens(host, st, year)
        t = text(o)
        check("Close encounters" in o.get("menu", "") and "nearby" in o
              and "Came within 2 miles" in o.get("overview", "") and "Came within 2 miles" in o.get("year", ""),
              f"at {host}: the 2-mile counts are shown")
        check("Farthest contact" in t and "Closest approach" in t and "187.3 nm" in t and "0.3 nm" in t
              and "Farthest heard" in o.get("year", "") and "Closest" in o.get("year", ""),
              f"at {host}: and the closest and farthest records")
    for host in PUBLIC:
        for label, stats, yr in (("as the radar answers today", st, year),
                                 ("as the gateway answers", public_st, public_year)):
            o = screens(host, stats, yr)
            t = text(o)
            check(bool(o) and "Close encounters" not in o.get("menu", "") and "nearby" not in o
                  and "within 2 miles" not in t.lower() and "came close" not in t,
                  f"on the public page ({label}): no 2-mile counts, and no Close encounters screen")
            check(bool(o) and "Farthest" not in t and "Closest" not in t and "closest" not in o.get("menu", "")
                  and "187.3" not in t and "0.3 nm" not in t,
                  f"on the public page ({label}): no closest or farthest records")
            check(bool(o) and "Highest" in t and "45,000 ft" in t and "Fastest" in t
                  and "undefined" not in t and "NaN" not in t,
                  f"on the public page ({label}): the rest of the screens as before")

print("page public rows checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
