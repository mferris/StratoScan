#!/usr/bin/env python3
"""deploy/labels.py stays identical to the copies that still exist elsewhere.

labels.py is the one copy of what says what an aircraft is. Until the kiosk
page (roadmap 1.9) and the iPhone app (2.8) read the core feed instead of
labelling for themselves, their own tables must match it exactly, or the
screens and the alerts disagree -- which is how the military badge came to
be fixed twice in one day.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "deploy"))
import labels  # noqa: E402

fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


page = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
swift = open(os.path.join(ROOT, "ios", "StratoScan", "Models", "AirlineTable.swift"), encoding="utf-8").read()

# airlines: airlines.json <-> index.html's AIRLINES
block = re.search(r"const AIRLINES = \{(.*?)\n\};", page, re.S).group(1)
page_airlines = {m.group(1): {"name": m.group(2), "iata": m.group(3), "color": m.group(4)}
                 for m in re.finditer(r"(\w{3}): \{ name: '([^']*)',\s*iata: '([^']*)',\s*color: '(#[0-9a-fA-F]{6})' \}", block)}
check(len(page_airlines) > 20, f"found the page's airline table ({len(page_airlines)} airlines)")
check(labels.AIRLINES == page_airlines, "airlines.json matches the page's AIRLINES exactly")

# military blocks: labels <-> index.html <-> the iPhone app
ranges = lambda text, q: [(int(a, 16), int(b, 16), w) for a, b, w in
                          re.findall(r"(0x[0-9a-f]+), (0x[0-9a-f]+), " + q + r"([^" + q[-1] + r"]+)" + q, text)]
page_mil = ranges(re.search(r"const MILITARY_HEX_RANGES = \[(.*?)\n\];", page, re.S).group(1), "'")
swift_mil = ranges(re.search(r"militaryHexRanges:.*?\[(.*?)\n    \]", swift, re.S).group(1), '"')
check(len(page_mil) >= 13, f"found the page's military blocks ({len(page_mil)})")
check(list(labels.MILITARY_HEX_RANGES) == page_mil, "military blocks match the page's")
check(list(labels.MILITARY_HEX_RANGES) == swift_mil, "military blocks match the iPhone app's")

# the operator rules, on the cases that have gone wrong before
cases = [("ae74e8", "ZEUS41", "military"), ("000001", "ZEUS44", "private"), ("a1b2c3", "DAL2164", "airline"),
         ("a3d4e5", "N30521", "private"), ("a3711a", "", "unknown"), ("a00001", "00000000", "unknown"),
         ("adf7c8", "RCH123", "military"), ("a00002", "XYZ123", "private")]
for hex_, cs, want in cases:
    got = labels.operator(hex_, cs)["kind"]
    check(got == want, f"operator({hex_}, {cs!r}) is {want} (got {got})")
check(labels.operator("ae74e8", "DAL1")["kind"] == "military", "a military block outranks an airline-looking callsign")

print(f"labels checks {'failed' if fails else 'passed'}" + (f" ({fails} failed)" if fails else ""))
sys.exit(1 if fails else 0)
