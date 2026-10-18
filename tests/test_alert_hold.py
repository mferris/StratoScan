#!/usr/bin/env python3
"""wake-listener.py's alert hold (2026-10-11): an alert that lights a dark
panel puts it out again after ALERT_HOLD_S, a touch reported by the page
cancels that, a non-alert wake (an update) never starts one, and a panel
already dark is left alone.

And its idle rule (2026-10-17): a lit panel goes out IDLE_MINUTES after its
last real input or its last lighting, whichever is later. The screensaver's
own timer counted from the desktop's last "activity", which includes every
sound the page plays, so on a morning of alerts it never ran out."""
import importlib.util
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("wl", root / "deploy" / "wake-listener.py")
wl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wl)
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


calls, panel = [], ["off"]
wl.subprocess.run = lambda argv, **k: (calls.append(argv), panel.__setitem__(0, "on") if argv[:2] == ["wlopm", "--on"] else
                                       panel.__setitem__(0, "off") if argv[:2] == ["wlopm", "--off"] else None)
wl._panel_state = lambda: panel[0]
wl.ALERT_FLAG = "/nonexistent/flag"
real_open = open
wl.open = lambda *a, **k: real_open("/dev/null", "w")      # the flag file is not the test's concern

t0 = 1000.0
wl.time.monotonic = lambda: t0
wl._wake(alert=True)
check(panel[0] == "on" and wl._hold_until == t0 + wl.ALERT_HOLD_S, "an alert lights the panel and starts the hold")
check(not wl._hold_tick(t0 + 60) and panel[0] == "on", "inside the hold the panel stays lit")
check(wl._hold_tick(t0 + wl.ALERT_HOLD_S + 1) and panel[0] == "off", "after the hold the listener puts it out itself")
check(["logger", "-t", "stratoscan-screen", "off-after-alert"] in calls, "and logs it")
check(not wl._hold_tick(t0 + 500), "a hold runs once")

import tempfile as _tf
flag = pathlib.Path(_tf.mkdtemp()) / "alert-wake"
flag.write_text("")
wl.ALERT_FLAG, panel[0] = str(flag), "on"
wl._hold_until = t0 + 1
check(wl._hold_tick(t0 + 2) and not flag.exists(),
      "and clears the alert flag, so the screensaver's backstop doesn't put the dark panel out again")
flag.write_text("")
panel[0] = "off"                # something else put it out first
wl._hold_until = t0 + 1
check(not wl._hold_tick(t0 + 2) and not flag.exists(), "a hold that ends on a dark panel clears its flag too")
wl.ALERT_FLAG = "/nonexistent/flag"

wl._wake(alert=True)
wl._hold_until = 0.0            # what /wake/touch does
check(not wl._hold_tick(t0 + 999) and panel[0] == "on", "a touch during the hold cancels it: the ordinary idle time applies")

panel[0] = "off"
wl._wake(alert=False)
check(wl._hold_until == 0.0, "a wake that is not an alert (an update) starts no hold")

wl._wake(alert=True)
panel[0] = "off"                # someone else put it out already
before = len(calls)
check(not wl._hold_tick(t0 + 9999) and len(calls) == before, "a panel already dark is left alone")

# ---- the idle rule ------------------------------------------------------------
import os
import tempfile
li = pathlib.Path(tempfile.mkdtemp()) / "last-input"
wl.LAST_INPUT = str(li)
IDLE = 1200
wl._mode = "sleep"
panel[0] = "on"
wl._note_lit(5000.0)
check(not wl._idle_tick(5000 + IDLE - 1, IDLE) and panel[0] == "on", "lit and untouched, the panel stays on for IDLE_MINUTES")
check(wl._idle_tick(5000 + IDLE + 1, IDLE) and panel[0] == "off", "then the listener puts it out, whatever sounds the page played")
check(["logger", "-t", "stratoscan-screen", "off-idle"] in calls, "and logs it")

panel[0] = "on"
wl._note_lit(8000.0)
wl._note_input(str(li), now=8900.0)    # (this file stubs open(); test_screen_wake checks the file itself)
check(not wl._idle_tick(8000 + IDLE + 1, IDLE) and panel[0] == "on", "a touch since it was lit gives the full time again")
check(wl._idle_tick(8900 + IDLE + 1, IDLE) and panel[0] == "off", "counted from the touch")
wl._input_at = None

panel[0] = "off"
check(not wl._idle_tick(20000.0, IDLE), "a dark panel is left alone")
panel[0] = "on"                 # the screensaver's touch-to-wake lit it, and said nothing
check(not wl._idle_tick(20030.0, IDLE), "a panel something else lit is noticed at the next look")
check(not wl._idle_tick(20030 + IDLE - 1, IDLE) and wl._idle_tick(20030 + IDLE + 1, IDLE),
      "and its time counts from then")

wl._mode = "on"
panel[0] = "on"
wl._note_lit(30000.0)
check(not wl._idle_tick(30000 + 10 * IDLE, IDLE) and panel[0] == "on", "always on stays on")
wl._mode = "sleep"

wl.time.monotonic = lambda: 40000.0
panel[0] = "on"
wl._note_lit(39000.0)
wl._wake(alert=False)           # an update, about to check its paint
check(not wl._idle_tick(40000 + IDLE - 1, IDLE), "a wake gives a lit panel a fresh idle time")

# The wall clock plays no part: a radar that boots with its clock behind and
# jumps forward when NTP answers keeps its lit panel lit.
wl.time.time = lambda: 9e9
panel[0] = "on"
wl._note_lit(50000.0)
check(not wl._idle_tick(50000.0 + 60) and panel[0] == "on", "a jump of the wall clock doesn't make a lit panel look idle")

check(wl._idle_s() == 1200, "IDLE_MINUTES falls back to 20 when the unit can't be read")
stub = wl.subprocess.run
wl.subprocess.run = lambda argv, **k: type("R", (), {"stdout": "Environment=IDLE_MINUTES=7 ALERT_HOLD_S=120\n"})()
check(wl._idle_s() == 420, "and is read from the screensaver unit, where it is set")
wl.subprocess.run = stub

src = (root / "deploy" / "wake-listener.py").read_text()
check("_idle_tick()" in src.split("def _hold_loop")[1].split("\ndef ")[0], "the hold loop runs the idle rule")
check("_note_input()" in src.split('path == "/wake/touch"')[1].split("send_response")[0],
      "a touch the page reports counts as real input")
check('path == "/wake/touch"' in src and "_hold_loop" in src.split('if __name__')[1], "the touch route and the hold loop are wired in")
page = (root / "index.html").read_text()
check("fetch('/wake/touch'" in page and "if (!ON_DEVICE) return;" in page, "the page reports touches, on the device only")
print("alert hold checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
