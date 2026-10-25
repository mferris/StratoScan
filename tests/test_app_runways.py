#!/usr/bin/env python3
"""The app's runway outlines never hold up its first look at the radar (2026-10-25).

Away from home the owner saw "connecting" for over a minute at every launch.
The app fetched runway outlines from OpenStreetMap's public Overpass service
with no timeout of its own, so up to iOS's 60 s default, before it asked the
radar for aircraft at all. Overpass was answering 502 and 406 that morning.

Now the outlines load in the background, from the phone's copy when it has
one, which is kept a month. The request has a 15 s timeout. Its box is centred
on the radar rounded to about 5 km and widened to cover the ring; centred
exactly, it gave Overpass the radar's position.

Run: python3 tests/test_app_runways.py
"""
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


rc = (ROOT / "ios" / "StratoScan" / "Networking" / "RunwayClient.swift").read_text()
fetch = rc[rc.index("static func fetchRunwayGeoJSON("):]
check("req.timeoutInterval = 15" in fetch, "the Overpass request has its own timeout, not iOS's 60 s")
check("rangeBBox(lat: centre.lat, lon: centre.lon, rangeNm: rangeNm + roundingPadNm)" in fetch
      and "let centre = rounded(center)" in fetch,
      "its box is centred on the radar rounded to 0.05°, widened to cover the ring")
m = re.search(r"static let roundingPadNm = ([\d.]+)", rc)
check(m is not None and float(m.group(1)) >= 2.0, "widened by at least the rounding (0.025° is about 1.5 nm)")
check("geojson.write(to: url, options: .atomic)" in fetch, "a fetched set is kept on the phone")
check(re.search(r"static let keepFor: TimeInterval = 30 \* 86400", rc), "and used for a month before Overpass is asked again")

vm = (ROOT / "ios" / "StratoScan" / "ViewModels" / "RadarViewModel.swift").read_text()
check("await loadRunways()" not in vm, "nothing waits for the runways")
lr = vm[vm.index("private func loadRunways()"):]
lr = lr[:lr.index("\n    }\n") + 6]
check("RunwayClient.cachedRunwayGeoJSON" in lr and lr.index("cachedRunwayGeoJSON") < lr.index("Task {"),
      "the phone's copy is shown at once, and Overpass asked behind it")
check("if kept.fresh { return }" in lr, "a fresh copy means no question to Overpass at all")
start = vm[vm.index("    func start() {"):vm.index("    /// Switch between the owner's radar and the demo recording.")]
check("await self.loadHome()" in start and "await self.pollOnce()" in start,
      "start: the radar's position, then straight into the polling")

privacy = (ROOT / "docs" / "privacy.md").read_text()
check("Runway outlines" in privacy and "Overpass" in privacy, "the privacy policy says what Overpass is asked")

print("app runway checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
