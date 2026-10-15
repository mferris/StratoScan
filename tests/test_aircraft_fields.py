#!/usr/bin/env python3
"""One aircraft, one description (#77, docs/aircraft-fields.md).

The owner found the app's tags and details and the radar's own "felt like two
different applications". This reads both sides -- index.html and the app's
Swift -- and fails when their tag lines, detail fields, labels or formats
drift apart, and checks that the core feed carries what the app needs to
show them: sighting counts and the notable reason.

Run: python3 tests/test_aircraft_fields.py
"""
import importlib.util
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


html = (ROOT / "index.html").read_text()
radar_swift = (ROOT / "ios/StratoScan/Views/RadarView.swift").read_text()
detail_swift = (ROOT / "ios/StratoScan/Views/AircraftDetailView.swift").read_text()
plane_swift = (ROOT / "ios/StratoScan/Models/PlaneState.swift").read_text()
route_swift = (ROOT / "ios/StratoScan/Networking/RouteLookupClient.swift").read_text()
doc = (ROOT / "docs/aircraft-fields.md").read_text()


def ordered(text, markers):
    """True when every marker is in `text`, in this order."""
    at = -1
    for m in markers:
        i = text.find(m, at + 1)
        if i < 0:
            print(f"     missing or out of order: {m!r}")
            return False
        at = i
    return True


# ---- the tag ---------------------------------------------------------------------
page_tag = re.search(r"node\.innerHTML = '(<div class=\"cs\">.*?)';", html).group(1)
page_lines = re.findall(r'class="([a-z]+)"', page_tag)
check(page_lines == ["cs", "badge", "seen", "type", "alt", "route", "owner"],
      "the radar's tag: callsign, badge, seen, type, altitude · speed, route, owner")
app_tag = radar_swift[radar_swift.index("private func labelContent(for p: PlaneState)"):]
app_tag = app_tag[:app_tag.index("\n    }\n")]
check(ordered(app_tag, ['"SEEN ×', "p.typeLabel", "PlaneState.altLabel(p.alt)) · ", "routeClient.route(for: p)", "p.owner"]),
      "the app's tag: the same lines in the same order")
check("s.total > 1" in app_tag and "counts.total > 1" in html, "both show SEEN only for an aircraft seen more than once")
check('`${formatAltitude(p.alt)} · ${speedTxt}kt`' in html and '"\\(PlaneState.altLabel(p.alt)) · \\(speedTxt)kt"' in app_tag,
      "altitude · speed written alike")

# ---- the details ----------------------------------------------------------------
panel = html[html.index("function showDetailPanel("):]
panel = panel[:panel.index("\nfunction ")]
page_fields = re.findall(r'<div class="dp-label">([^<]+)</div>', panel)
grid = detail_swift[detail_swift.index("private func grid(_ p: PlaneState)"):]
grid = grid[:grid.index("return VStack")]
app_fields = re.findall(r'\("([A-Z][^"]+)",', grid)
want = ["Altitude", "Speed", "Heading", "Vert. rate", "Squawk", "Distance", "Heard on", "Notable", "Sightings", "Within 2 mi"]
check(page_fields == want, f"the radar's details: {', '.join(page_fields)}")
check(app_fields == want, "the app's details: the same fields, labels and order")
doc_fields = re.findall(r"^\| ([A-Z][^|]+?) \|", doc.split("## The details")[1].split("##")[0], re.M)
check([f for f in doc_fields if f in want] == want, "and docs/aircraft-fields.md lists them so")
check(ordered(detail_swift, ["photoView", "header(p)", "grid(p)", "footer(p)"]) and
      ordered(panel, ["dp-photo", "dp-cs", "dp-badge", "dp-type", "dp-route", "dp-grid", "dp-icao"]),
      "photo first, then who and what, the figures, and the ICAO address last, on both")
check("ICAO ${esc(p.hex.toUpperCase())}" in panel and 'Text("ICAO \\(hex.uppercased())")' in detail_swift,
      "both end with the ICAO address")
check("[p.typeLabel || 'Unknown type', p.registration]" in panel and '[p.typeLabel ?? "Unknown type", p.reg]' in detail_swift,
      "type · registration on both")
check("Registered to ${info.owner}" in html and 'Text("Registered to \\(o.name)' in detail_swift, "the owner worded alike")

# ---- formats ---------------------------------------------------------------------
check(all(x in html for x in ("'On ground'", "return '—'", "} ft`")) and
      all(x in plane_swift for x in ('"On ground"', 'return "—"', ' ft"')),
      "altitude: 33,000 ft / On ground / — on both (the app no longer says FL330 or GND)")
check("'Level'" in html and "'↑ '" in html and "'↓ '" in html and "' ft/min'" in html and
      all(x in detail_swift for x in ('"Level"', '"↑ "', '"↓ "', ' ft/min"')), "vertical rate alike")
check("${p.range.toFixed(1)} nm · ${Math.round(p.bearing)}°" in panel and '"%.1f nm · %d°"' in grid, "distance: 12.3 nm · 245° on both")
for band in ("'1090 MHz'", "'978 MHz (UAT)'", "'978 MHz, re-sent on 1090'"):
    check(band in panel and band.replace("'", '"') in grid, f"heard on {band}")
check("p.realHdg != null ? Math.round(p.realHdg) + '°' : '—'" in panel and 'p.realHdg.map' in grid,
      "a heading only when one is reported, on both")
check("(unconfirmed)" in html and "(unconfirmed)" in route_swift and 'joined(separator: " → ")' in route_swift,
      "a route worded alike: every stop, and (unconfirmed) when it doesn't fit")
check("No photo available" in html and "No photo available" in detail_swift, "the same stand-in when there is no photo")

# ---- the core feed carries what the app shows ------------------------------------------
os.environ["STRATOSCAN_CORE_LOOKUPS"] = "0"
sys.path.insert(0, str(ROOT / "deploy"))
spec = importlib.util.spec_from_file_location("core_feed", ROOT / "deploy" / "core-feed.py")
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)


class Counts:
    def __init__(self, d): self.d = d
    def get(self): return self.d


class NoUat:
    def heard(self, hex_): return False


big = {f"{i:06x}": (3, 0) for i in range(2500)}            # a radar that has seen plenty
big.update({"a1b2c3": (14, 3), "abc001": (1, 0)})
feed = cf.Feed(uat=NoUat(), sightings=Counts(big))
feed.notable = {"a77777": ["Don't you know who I am?", None, "A Company"]}
lab = lambda a, src="antenna": feed.label(a, src, big if src == "antenna" else None)
r = lab({"hex": "a1b2c3", "flight": "DAL2164", "type": "adsb_icao", "squawk": "4611", "baro_rate": -704})
check(r["sightings"] == {"total": 14, "nearby": 3}, "an aircraft's sighting counts are in the feed")
check(r["type"]["code"] is None, "readsb's message type is never taken for the aircraft's type (adsb_icao was shown)")
check(r["squawk"] == "4611" and r["vrate"] == -704, "squawk and vertical rate are in the feed")
check(r["rare"] is None, "an ordinary aircraft seen before is not notable")
check(lab({"hex": "abc001"})["rare"] == {"kind": "first", "label": "Never seen here before", "operator": None},
      "first time here, once the radar has seen 2,000 aircraft")
small = cf.Feed(uat=NoUat(), sightings=Counts({"abc001": (1, 0)}))
check(small.label({"hex": "abc001"}, "antenna", {"abc001": (1, 0)})["rare"] is None,
      "but not on a radar that has seen few (nearly everything would be)")
check(lab({"hex": "ae1234"})["rare"]["kind"] == "military", "a military operator")
check(lab({"hex": "a77777"})["rare"] == {"kind": "notable", "label": "Aircraft of a well-known person", "operator": "A Company"},
      "a listed aircraft, with plane-alert-db's operator but never a person's name")
net = lab({"hex": "a55555", "type": "B738", "r": "N1"}, "network")
check("sightings" not in net and net["type"]["code"] == "B738",
      "a network aircraft: no counts (this radar didn't hear it), and its type is the network's")
check("people" not in cf.Feed.label.__code__.co_varnames, "the feed never reads the names (it is public)")

print("aircraft field checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
