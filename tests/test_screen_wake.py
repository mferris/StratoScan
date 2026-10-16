#!/usr/bin/env python3
"""The panel wakes for a person, not for a sound (2026-10-16).

On RDU the dark panel woke itself all night, logged as "on-touch" with
nobody near it. The desktop reports activity for a touch and also whenever
an application keeps the screen awake, and Chromium does for as long as the
page plays a sound: every alert chime turned the desktop "active" two
seconds before its audio stream opened. swayidle cannot tell them apart, so
each chime lit the panel for 20 minutes, and an alert's own chime turned its
two-minute hold into twenty.

Now wake-listener.py notes each real input, and screen-resume.sh lights the
panel and ends an alert's hold only for one. This runs the script with a
stand-in wlopm and the listener's input watcher with a stand-in evdev.

Run: python3 tests/test_screen_wake.py
"""
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


# ---- screen-resume.sh, with a stand-in wlopm and logger ---------------------------
tmp = pathlib.Path(tempfile.mkdtemp())
bin_ = tmp / "bin"; bin_.mkdir()
(bin_ / "wlopm").write_text('#!/bin/sh\nif [ "$1" = "--on" ]; then echo on >> "$XDG_RUNTIME_DIR/calls"; echo on > "$XDG_RUNTIME_DIR/state"; '
                            'else echo "HDMI-A-1 $(cat "$XDG_RUNTIME_DIR/state")"; fi\n')
(bin_ / "logger").write_text('#!/bin/sh\necho "$*" >> "$XDG_RUNTIME_DIR/log"\n')
for f in bin_.iterdir():
    f.chmod(0o755)


def resume(panel, last_input_age=None, alert_flag=True):
    run = tmp / f"run{time.time_ns()}"; run.mkdir()
    (run / "state").write_text(panel + "\n")
    if alert_flag:
        (run / "stratoscan-alert-wake").write_text("")
    if last_input_age is not None:
        li = run / "stratoscan-last-input"; li.write_text("")
        t = time.time() - last_input_age
        os.utime(li, (t, t))
    env = dict(os.environ, XDG_RUNTIME_DIR=str(run), PATH=f"{bin_}:{os.environ['PATH']}")
    subprocess.run(["sh", str(D / "screen-resume.sh")], env=env, check=True, timeout=20)
    calls = (run / "calls").read_text() if (run / "calls").exists() else ""
    log = (run / "log").read_text() if (run / "log").exists() else ""
    return {"woke": "on" in calls, "flag": (run / "stratoscan-alert-wake").exists(), "log": log}


r = resume("off", last_input_age=1)
check(r["woke"] and not r["flag"] and "on-touch" in r["log"], "a touch wakes the dark panel and ends an alert's short hold")
r = resume("off", last_input_age=60)
check(not r["woke"] and r["flag"] and r["log"] == "", "a sound (activity with no input) leaves the panel dark and the alert's hold as it was")
r = resume("on", last_input_age=60)
check(not r["woke"] and r["flag"], "and doesn't turn an alert's two-minute hold into the full twenty minutes")
r = resume("off", last_input_age=None)
check(r["woke"] and not r["flag"], "before any input is on record, activity wakes the panel as it always did")
r = resume("on", last_input_age=1)
check(not r["woke"] and not r["flag"], "a touch on a lit panel only ends the alert's hold")

# ---- wake-listener.py's input watcher, with a stand-in evdev ------------------------
os.environ["XDG_RUNTIME_DIR"] = str(tmp)
spec = importlib.util.spec_from_file_location("wake_listener", D / "wake-listener.py")
wl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wl)
check(wl._is_input(1) and wl._is_input(2) and wl._is_input(3), "keys and buttons, pointer moves and touches are input")
check(not wl._is_input(0) and not wl._is_input(4) and not wl._is_input(5), "syncs, misc and switches (the HDMI jacks) are not")


class Ev:
    def __init__(self, t): self.type = t


class Dev:
    """A device backed by a pipe, so select() really waits on it."""
    def __init__(self, path, events):
        self.path = path
        self.fd, self._w = os.pipe()
        self.events = events
        os.write(self._w, b"x")
    def read(self):
        os.read(self.fd, 1)
        return [Ev(t) for t in self.events]
    def close(self): os.close(self.fd)


class FakeEvdev:
    def __init__(self, devs): self.devs = devs
    def list_devices(self): return list(self.devs)
    def InputDevice(self, path): return self.devs[path]


wl.LAST_INPUT = str(tmp / "last-input-a")
wl._input_watch(FakeEvdev({"/dev/input/event0": Dev("/dev/input/event0", [5, 0])}), rounds=2)
check(not os.path.exists(wl.LAST_INPUT), "an HDMI jack's switch event is not noted")
wl.LAST_INPUT = str(tmp / "last-input-b")
t0 = time.time()
wl._input_watch(FakeEvdev({"/dev/input/event5": Dev("/dev/input/event5", [3, 3, 0])}), rounds=2)
check(os.path.exists(wl.LAST_INPUT) and os.path.getmtime(wl.LAST_INPUT) >= t0 - 1, "a touch is noted, for the screensaver")
check(wl._input_watch(None, rounds=0) is None, "and the watcher runs without python3-evdev (it just notes nothing)")

# ---- wiring ---------------------------------------------------------------------------
unit = (D / "stratoscan-screensaver.service").read_text()
check("resume /opt/stratoscan/screen-resume.sh timeout" in unit and "timeout 1 true resume" in unit,
      "the screensaver's resume is the script, still tied to the 1-second timeout")
check("threading.Thread(target=_input_watch, daemon=True).start()" in (D / "wake-listener.py").read_text(),
      "the wake listener runs the input watcher")
check(" screen-resume.sh " in (D / "install-setup-server.sh").read_text().split('echo "== programs =="')[1].split("done")[0],
      "the installer installs the script")
check('"screen-resume.sh",' in (D / "ota.py").read_text(), "an update may carry it")
check(os.access(D / "screen-resume.sh", os.X_OK), "and it is executable")

print("screen wake checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
