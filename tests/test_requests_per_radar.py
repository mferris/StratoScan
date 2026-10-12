#!/usr/bin/env python3
"""Fewer questions per radar (roadmap 1.20, #67).

- The ring comparison asks the network at most once a minute (was every
  15 s): the radar's service, the core feed's cache and the page's poll
  agree, and the page carries the network's aircraft forward long enough to
  cover a poll.
- The location poll asks the relay every 10 minutes while no phone shares a
  location (it was every minute regardless).
- Away from home the app reads the radar every 4 s (was every second), and
  carries each blip forward from its last report between reads.

Run: python3 tests/test_requests_per_radar.py
"""
import importlib.util
import io
import os
import pathlib
import re
import sys
import contextlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def num(text, pattern):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


nc = (D / "network-compare.py").read_text()
core = (D / "core-feed.py").read_text()
html = (ROOT / "index.html").read_text()
events = (D / "events.py").read_text()
vm = (ROOT / "ios" / "StratoScan" / "ViewModels" / "RadarViewModel.swift").read_text()
rv = (ROOT / "ios" / "StratoScan" / "Views" / "RadarView.swift").read_text()
ps = (ROOT / "ios" / "StratoScan" / "Models" / "PlaneState.swift").read_text()

upstream = num(nc, r"\nMIN_UPSTREAM_S = (\d+)")
cache = num(core, r"\nNETWORK_CACHE_S = ([\d.]+)")
poll_ms = num(html, r"const NETWORK_POLL_MS = (\d+) \* 1000")
dr = num(html, r"const GHOST_DR_MAX_S = (\d+);")
drop_ms = num(html, r"const GHOST_DROP_MS = (\d+) \* 1000")
check(upstream == 60, "the ring comparison asks the network at most once a minute")
check(cache == upstream, "the core feed keeps an answer as long as the service does")
check(poll_ms == upstream, "the page asks no faster than the answer can change")
check(dr is not None and dr >= upstream + 10, "network aircraft are carried forward past one poll (%s s)" % dr)
check(drop_ms is not None and drop_ms >= 2 * upstream, "and dropped only after two polls without them (%s s)" % drop_ms)
check(86400 / upstream <= 1440, "at most 1,440 ring questions a day with a screen open all day")

# the hourly count, so the rate is measured on a unit
spec = importlib.util.spec_from_file_location("ncm", D / "network-compare.py")
ncm = importlib.util.module_from_spec(spec)
os.environ.setdefault("STRATOSCAN_NETWORK_STATE", "/tmp/stratoscan-test-network")
try:
    spec.loader.exec_module(ncm)
    ncm._ring_asked.update(n=0, since=1000.0)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for t in (1010, 1070, 1130):
            ncm.note_ring_question(t)
        ncm.note_ring_question(4700)
    out = buf.getvalue()
    check("4 ring questions to adsb.lol in the last hour" in out and ncm._ring_asked["n"] == 0,
          "the service logs its ring questions once an hour")
except Exception as e:  # the module needs nothing exotic, but keep the other checks running
    check(False, "network-compare.py loads for the hourly count (%s)" % e)

# the location poll
check(num(events, r"\nLOCATION_POLL_S = (\d+)") == 60 and num(events, r"\nLOCATION_IDLE_POLL_S = (\d+)") == 600,
      "the relay is asked for phone locations every minute only while a phone shares one, else every 10 minutes")

# the app away from home
check(num(vm, r"let awayFetchInterval: TimeInterval = ([\d.]+)") == 4.0, "away from home the app reads the radar every 4 s")
check(num(vm, r"let fetchInterval: TimeInterval = ([\d.]+)") == 1.0, "at home, every second as before")
check("Endpoint.shared.whereNow == .away" in vm and "self.currentFetchInterval" in vm, "chosen by where the phone is")
check("fixAt = now" in ps and "static let drMaxS: Double = 10" in rv and "p.fixAt" in rv,
      "between reads each blip moves on from its last report (up to 10 s)")

print("requests per radar checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
