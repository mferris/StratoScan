#!/usr/bin/env python3
"""The kiosk page (index.html, also the public page through the gateway)
reads the unit's core feed and nothing else for aircraft, routes and owners
(roadmap 1.9): no visitor's browser contacts adsb.im or adsbdb, and readsb's
aircraft.json is not read by the page. The old path was removed 2026-10-08."""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
page = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
# Comments may still tell the story; code may not do it.
code = "\n".join(l for l in page.splitlines() if not l.lstrip().startswith("//"))

fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


check("'/api/aircraft'" in code, "the page polls the core feed")
for needle in ("adsb.im/api", "api.adsbdb.com", "/tar1090/data/aircraft.json", "core=0",
               "USE_CORE_FEED", "coreActive(", "ROUTE_API_URL", "fetchFrom(", "routeQueue", "queueRouteLookup("):
    check(needle not in code, "no %s in code" % needle)
check(not re.search(r"https?://[a-z0-9.-]*adsb\.im", code), "no adsb.im address in code")
check(not re.search(r"https?://[a-z0-9.-]*adsbdb", code), "no adsbdb address in code")
# Release 2026.10.08.2 captured the pointer on the stage for pan and zoom, and
# every control inside the stage that listens for its own pointerup (the gear,
# the rewind button, the panels) stopped answering on the panel.
check("setPointerCapture(" not in code, "the stage never captures the pointer (the gear's tap must reach the gear)")

print("kiosk core-only checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
