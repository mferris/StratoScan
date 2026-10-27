#!/usr/bin/env python3
"""The outside hosts the radar's pages name, and what those hosts are told (2026-10-26).

Every host the kiosk page (index.html) and the setup page (deploy/setup-ui.html)
link to or ask is one listed here, so a new third party is a decision rather
than an accident. The project's rename once rewrote the setup page's
Flightradar24 link to a wrong address, and nothing noticed.

Google Fonts serves the page's two typefaces to the panel and every browser
at home, the stylesheet asked for without a referrer. The public page does
not load them at all: the font files are CORS requests, which carry the
page's origin whatever the referrer policy, and from the public page that
is the radar's public address beside each visitor's IP. The page's own font
code runs under node for a public and a home address to check both.

Neither page names a home network's address but the test fixture and
NetworkManager's own hotspot default.

Run: python3 tests/test_page_hosts.py
"""
import json
import pathlib
import re
import shutil
import subprocess
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

check(not re.search(r"<link[^>]+fonts\.googleapis|@import[^;\n]*fonts\.googleapis", page),
      "no stylesheet link or @import in the markup asks Google Fonts")
code = "\n".join(l for l in page.splitlines() if not l.strip().startswith("//"))
public_line = re.search(r"^const PUBLIC_PAGE = .*$", code, re.M)
fonts = re.search(r"^const WEB_FONTS_URL = .*?\n\}\n", code, re.M | re.S)
check(public_line and fonts and "if (!PUBLIC_PAGE) {" in fonts.group(0),
      "the web fonts are added only when the page is not the public one")
if not shutil.which("node"):
    print("skip behaviour checks (no node)")
elif public_line and fonts:
    # The page's own lines, with a stand-in document that records each
    # property set on the <link>, in order, and what is added to <head>.
    js = r"""
const src = """ + json.dumps(public_line.group(0) + "\n" + fonts.group(0)) + r""";
const out = {};
for (const hostname of ['radar.example.ts.net', 'localhost', '192.168.1.23']) {
  const added = [];
  const document = {
    createElement: () => new Proxy({ sets: [], addEventListener() {} },
      { set(t, k, v) { t.sets.push(k); t[k] = v; return true; } }),
    head: { appendChild: el => added.push({ href: el.href, referrerPolicy: el.referrerPolicy, sets: el.sets }) },
  };
  new Function('location', 'document', 'redrawStaticLayers', src)({ hostname, search: '' }, document, () => {});
  out[hostname] = added;
}
console.log(JSON.stringify(out));
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stdout[-800:], r.stderr[-1500:])
    check(o.get("radar.example.ts.net") == [], "a visitor to the public page asks Google Fonts for nothing")
    for host in ("localhost", "192.168.1.23"):
        links = o.get(host) or []
        ok = (len(links) == 1 and "fonts.googleapis.com" in (links[0].get("href") or "")
              and links[0].get("referrerPolicy") == "no-referrer"
              and links[0]["sets"].index("referrerPolicy") < links[0]["sets"].index("href"))
        check(ok, f"at {host} the stylesheet is still added, its referrer policy set before its address")

PRIVATE = re.compile(r"\b(10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+"
                     r"|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+)\b")
ALLOWED = {"192.168.1.23", "10.42.0.1"}   # the fixture; NetworkManager's shared-network default
for name, text in (("index.html", page), ("deploy/setup-ui.html", setup)):
    found = sorted(set(PRIVATE.findall(text)) - ALLOWED)
    check(not found, f"{name} names no home network's address" + (f" (found {', '.join(found)})" if found else ""))

print("page host checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
