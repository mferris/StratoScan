#!/usr/bin/env python3
"""Loose ends of the 2026-10-26 security review, across areas.

- The public address tells the services its page uses nothing about the page
  that asked: no referrer, as the setup page already did.
- The public address leaves out the close-pass counts (sightings.nearby and
  the logbook's), so the app must take a missing one as "not shown", not
  fail the whole sightings object or print 0.
- net-watchdog runs as root and keeps one marker in the web tier's own
  directory: it must never write through a link someone left there.

Run: python3 tests/test_security_followups.py
"""
import importlib.util
import os
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
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


# ---- the gateway's referrer policy -------------------------------------------------
gw = (ROOT / "deploy" / "funnel-gateway.py").read_text()
m = re.search(r'"Referrer-Policy":\s*"([^"]+)"', gw)
check(m is not None and m.group(1) == "no-referrer", "the public address sends no referrer")

# ---- the app takes a missing close-pass count as not shown ---------------------------
aircraft = (ROOT / "ios" / "Shared" / "Aircraft.swift").read_text()
detail = (ROOT / "ios" / "StratoScan" / "Views" / "AircraftDetailView.swift").read_text()
logbook = (ROOT / "ios" / "StratoScan" / "Views" / "LogbookView.swift").read_text()
check("struct FeedSightings: Decodable { let total: Int; let nearby: Int? }" in aircraft,
      "a sightings answer without nearby still decodes (the total stays)")
check('if let n = s.nearby { rows.append(("Within 2 mi", "\\(n)")) }' in detail
      and '"\\(s.nearby)"' not in detail, "and the detail view leaves the row out rather than print nil")
check("struct LogToday: Decodable { var total: Int; var nearby: Int? }" in logbook,
      "the logbook's day decodes without nearby")
check('if let n = s.today?.nearby { tile(Self.count(n), "close passes") }' in logbook
      and 'if let n = s.nearby { tile(Self.count(n), "close passes") }' in logbook
      and 'tile(Self.count(s.nearby), "close passes")' not in logbook,
      "and its close-pass tiles show only when the radar sent them, never a made-up 0")

# ---- net-watchdog never writes through a link ----------------------------------------
w = load("netwatchdog_followups", ROOT / "deploy" / "net-watchdog.py")
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    victim = d / "victim"
    victim.write_text("keep me\n")
    marker = d / "web-tier" / "last-watchdog-reboot"
    marker.parent.mkdir()
    os.symlink(victim, marker)
    w.touch_runtime(str(marker))
    check(victim.read_text() == "keep me\n", "a link planted where the marker goes is not written through")
    check(marker.exists() and not marker.is_symlink(), "and the marker is made fresh in its place")
    w.touch_runtime(str(marker))
    check(marker.exists() and not marker.is_symlink(), "and touching it again is fine")
    fresh = d / "new" / "marker"
    w.touch_runtime(str(fresh))
    check(fresh.is_file(), "a missing marker and its directory are still created")

print("security follow-up checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
