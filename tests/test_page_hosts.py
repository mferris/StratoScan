#!/usr/bin/env python3
"""The outside hosts the radar's pages name, and what those hosts are told (2026-10-26).

Every host the kiosk page (index.html) and the setup page (deploy/setup-ui.html)
link to or ask is one listed here, so a new third party is a decision rather
than an accident. The project's rename once rewrote the setup page's
Flightradar24 link to a wrong address, and nothing noticed.

Google Fonts serves the page's two typefaces to the panel, every browser at
home and every visitor to the public page. It is asked without a referrer,
which from the public page was the radar's public address beside each
visitor's IP.

Neither page names a home network's address but the test fixture and
NetworkManager's own hotspot default.

Run: python3 tests/test_page_hosts.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
page = (ROOT / "index.html").read_text()
setup = (ROOT / "deploy" / "setup-ui.html").read_text()
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


KNOWN = {
    # asked by the page: map, weather, rain, lightning, fonts, photos
    "tiles.openfreemap.org", "api.open-meteo.com", "api.rainviewer.com", "realearth.ssec.wisc.edu",
    "fonts.googleapis.com", "api.planespotters.net",
    # credited and linked to
    "openfreemap.org", "www.openmaptiles.org", "www.openstreetmap.org", "protomaps.com", "www.rainviewer.com",
    "www.flightaware.com", "www.flightradar24.com",
    # not hosts at all: the SVG namespace, and the radar's own loopback listener
    "www.w3.org", "127.0.0.1",
}
for name, text in (("index.html", page), ("deploy/setup-ui.html", setup)):
    hosts = {h.lower() for h in re.findall(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,}|\d+\.\d+\.\d+\.\d+)", text)}
    unknown = sorted(hosts - KNOWN)
    check(hosts and not unknown, f"{name} names only known hosts" + (f" (not: {', '.join(unknown)})" if unknown else ""))

check('href="https://www.flightradar24.com/build-your-own"' in setup and "stratoscan24" not in setup.lower(),
      "the setup page's Flightradar24 link goes to Flightradar24")

code = "\n".join(l for l in page.splitlines() if not l.strip().startswith("//"))
fonts = code.split("const WEB_FONTS_URL", 1)[-1][:900]
check("link.referrerPolicy = 'no-referrer';" in fonts and fonts.index("referrerPolicy") < fonts.index("link.href = WEB_FONTS_URL"),
      "Google Fonts is asked for the stylesheet without a referrer, set before the request starts")
check(not re.search(r"<link[^>]+fonts\.googleapis", page), "and no stylesheet link in the markup asks it with one")

PRIVATE = re.compile(r"\b(10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+"
                     r"|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+)\b")
ALLOWED = {"192.168.1.23", "10.42.0.1"}   # the fixture; NetworkManager's shared-network default
for name, text in (("index.html", page), ("deploy/setup-ui.html", setup)):
    found = sorted(set(PRIVATE.findall(text)) - ALLOWED)
    check(not found, f"{name} names no home network's address" + (f" (found {', '.join(found)})" if found else ""))

print("page host checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
