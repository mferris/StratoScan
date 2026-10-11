#!/usr/bin/env python3
"""Well-known people's aircraft are named on the owner's own screens and phone,
and never on the public page (2026-10-11: an alert said "Aircraft of a
well-known person" without saying who).

- notable-db.py keeps notable.json name-free: the core feed and the public
  page read it. Names go to a separate notable-people.json.
- funnel-gateway.py refuses notable-people.json to the public tunnel.
- The phone alerts (events.py) and the page read the names; the core feed
  never does.

Run: python3 tests/test_notable_people.py
"""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


tmp = tempfile.mkdtemp()
os.environ["STRATOSCAN_WEB_ROOT"] = tmp
os.environ["STRATOSCAN_NOTABLE_STATE"] = os.path.join(tmp, "state")
nd = load("nd", D / "notable-db.py")

HEADER = "$ICAO,$Registration,$Operator,$Type,$ICAO Type,#CMPG,$Tag 1,$#Tag 2,$#Tag 3,Category,$#Link\n"
CSV = HEADER + "\n".join([
    "A00003,N3,A Famous Person,Gulfstream G650,GLF6,Civ,Celebrity,,,Don't you know who I am?,",
    "A00004,N4,Rich Person LLC,Boeing BBJ,B737,Civ,,,,Oligarch,",
    "A00007,N7,,Cessna Citation,C56X,Civ,,,,Don't you know who I am?,",
    "AE1234,00-1234,USAF,Boeing C-17,C17,Mil,Cargo,,,USAF,",
]) + "\n"

doc = nd.convert(CSV)
check(doc["ac"]["a00003"][2] == "", "notable.json still carries no name for a well-known person")
names = nd.people(CSV)
check(names == {"a00003": "A Famous Person"}, "notable-people.json names only well-known people, and only where a name is given")
check(nd.PEOPLE_OUT.endswith("data/notable-people.json") and nd.PEOPLE_OUT != nd.OUT, "and it is its own file")

# the public tunnel refuses it; the name-free list stays public
fg = load("fg", D / "funnel-gateway.py")
local = fg.Handler._is_local_only
check(local("/data/notable-people.json"), "the public tunnel refuses notable-people.json")
check(local("/DATA//notable-people.json?x=1".split("?")[0]) and local("/data/./notable-people.json"),
      "however the path is written")
check(not local("/data/notable.json"), "but still serves the name-free notable.json")

# the phone alerts read the names; the core feed does not
people_file = pathlib.Path(tmp) / "data" / "notable-people.json"
people_file.parent.mkdir(parents=True, exist_ok=True)
people_file.write_text(json.dumps({"names": names}))
os.environ["STRATOSCAN_NOTABLE_PEOPLE_JSON"] = str(people_file)
sys.path.insert(0, str(D))
labels = load("labels", D / "labels.py")
pp = labels.NotablePeople(str(people_file))
check(pp.get("a00003") == "A Famous Person" and pp.get("ae1234") is None, "NotablePeople reads the names")
ev = load("events", D / "events.py")


class Notable:
    def get(self, h):
        return doc["ac"].get(h)


a = {"hex": "a00003"}
check(ev.notable_reason(a, {}, Notable(), pp) == ("Aircraft of a well-known person", "A Famous Person"),
      "a phone alert names the person")
check(ev.notable_reason(a, {}, Notable()) == ("Aircraft of a well-known person", None),
      "without the names file it says only what kind of aircraft it is")
check(ev.notable_reason({"hex": "ae1234"}, {}, Notable(), pp)[1] == "USAF", "a military operator is still named as before")
core = (D / "core-feed.py").read_text()
check("NotablePeople" not in core and "notable-people" not in core, "the core feed, which is public, never reads the names")

# the page: names on by default, said and shown, never fetched into the public feed
html = (ROOT / "index.html").read_text()
check("notableNames: true" in html, "naming is on by default")
check("fetch('/data/notable-people.json')" in html, "the page loads the names (refused on the public page)")
check("alertSettings.notableNames && notablePeople" in html, "and uses them only while the setting is on")
check("const who = why.operator ? `${why.label}, ${why.operator}` : why.label;" in html
      and "speak(announcementFor(pl, who));" in html, "the spoken alert says who it is")
check("why.operator ? ' \\u00b7 ' + why.operator : ''" in html, "and the banner shows it")
check("key: 'notableNames'" in html, "a setting can turn names off")

print("notable people checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
