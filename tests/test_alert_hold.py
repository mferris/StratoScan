#!/usr/bin/env python3
"""wake-listener.py's alert hold (2026-10-11): an alert that lights a dark
panel puts it out again after ALERT_HOLD_S, a touch reported by the page
cancels that, a non-alert wake (an update) never starts one, and a panel
already dark is left alone."""
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

src = (root / "deploy" / "wake-listener.py").read_text()
check('path == "/wake/touch"' in src and "_hold_loop" in src.split('if __name__')[1], "the touch route and the hold loop are wired in")
page = (root / "index.html").read_text()
check("fetch('/wake/touch'" in page and "if (!ON_DEVICE) return;" in page, "the page reports touches, on the device only")
print("alert hold checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
