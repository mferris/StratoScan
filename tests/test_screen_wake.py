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
                            'elif [ "$1" = "--off" ]; then echo off >> "$XDG_RUNTIME_DIR/calls"; echo off > "$XDG_RUNTIME_DIR/state"; '
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
    def __init__(self, path, events, caps=None, pending=True):
        self.path = path
        self.fd, self._w = os.pipe()
        self.events = events
        self.caps = caps if caps is not None else sorted(set(events))
        if pending:
            os.write(self._w, b"x")
    def capabilities(self): return {t: [] for t in self.caps}
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

# After a boot, before anyone touches it (RDU, 2026-10-26): the weekly restart
# emptied XDG_RUNTIME_DIR, and with nobody home the airport's take-off chime
# lit the panel for 20 minutes, twice in an hour. A listener that can read the
# touchscreen now says so at once, and a sound is a sound from the start.
wl.LAST_INPUT = str(tmp / "last-input-c")
wl._input_watch(FakeEvdev({"/dev/input/event4": Dev("/dev/input/event4", [], caps=[0, 1, 3], pending=False)}), rounds=1)
check(os.path.exists(wl.LAST_INPUT) and os.path.getmtime(wl.LAST_INPUT) < 86400,
      "with the touchscreen readable, the input file is there from the start, dated long ago")
run = tmp / "boot"; run.mkdir()
(run / "state").write_text("off\n")
(run / "stratoscan-last-input").write_bytes(b"")
os.utime(run / "stratoscan-last-input", (0, 0))
subprocess.run(["sh", str(D / "screen-resume.sh")], timeout=20, check=True,
               env=dict(os.environ, XDG_RUNTIME_DIR=str(run), PATH=f"{bin_}:{os.environ['PATH']}"))
check(not (run / "calls").exists(), "so a quiet chime after a boot leaves the dark panel dark")
wl.LAST_INPUT = str(tmp / "last-input-d")
wl._input_watch(FakeEvdev({"/dev/input/event1": Dev("/dev/input/event1", [], caps=[0, 5], pending=False)}), rounds=1)
check(not os.path.exists(wl.LAST_INPUT), "an HDMI jack alone says nothing: activity still wakes the panel")
wl.LAST_INPUT = str(tmp / "last-input-e")
wl._note_input()
noted = os.path.getmtime(wl.LAST_INPUT)
wl._input_watch(FakeEvdev({"/dev/input/event4": Dev("/dev/input/event4", [], caps=[0, 1, 3], pending=False)}), rounds=1)
check(os.path.getmtime(wl.LAST_INPUT) == noted, "and a touch already noted is never dated back")

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

# ---- the screensaver finds the compositor when the session hadn't said yet --------
# After a boot it can start before the session publishes WAYLAND_DISPLAY:
# swayidle still connects, but wlopm refuses, and the panel never went dark
# (RDU, 2026-10-16). Run the unit's own script, as systemd hands it to sh.
line = next(l for l in unit.splitlines() if l.startswith("ExecStart="))
script = line.split("-c '", 1)[1].rsplit("'", 1)[0].replace("$$", "$").replace("\\\\", "\\")
(bin_ / "swayidle").write_text('#!/bin/sh\necho "${WAYLAND_DISPLAY:-unset}" > "$XDG_RUNTIME_DIR/seen"\n'
                                'printf "%s\\0" "$@" > "$XDG_RUNTIME_DIR/argv"\n')
(bin_ / "swayidle").chmod(0o755)


def screensaver_sees(wayland=None):
    run = tmp / f"ss{time.time_ns()}"; run.mkdir()
    (run / "wayland-0").write_text(""); (run / "wayland-0.lock").write_text("")
    env = dict(os.environ, XDG_RUNTIME_DIR=str(run), PATH=f"{bin_}:{os.environ['PATH']}",
               IDLE_MINUTES="20", ALERT_HOLD_S="120")
    env.pop("WAYLAND_DISPLAY", None)
    if wayland:
        env["WAYLAND_DISPLAY"] = wayland
    subprocess.run(["sh", "-c", script], env=env, check=True, timeout=20)
    return (run / "seen").read_text().strip()


check(screensaver_sees() == "wayland-0", "started before the session said, the screensaver finds the compositor itself")
check(screensaver_sees("wayland-1") == "wayland-1", "and keeps the session's own answer when it has one")

# The alert hold's backstop, exactly as swayidle is handed it (the unit's
# script names the flag by its full path, so it runs in the same directory).
def backstop_cmd(run):
    (run / "wayland-0").write_text("")
    env = dict(os.environ, XDG_RUNTIME_DIR=str(run), PATH=f"{bin_}:{os.environ['PATH']}",
               IDLE_MINUTES="20", ALERT_HOLD_S="120", WAYLAND_DISPLAY="wayland-0")
    subprocess.run(["sh", "-c", script], env=env, check=True, timeout=20)
    argv = (run / "argv").read_text().split("\0")
    i = next(k for k in range(len(argv) - 2) if argv[k] == "timeout" and argv[k + 1] == "120")
    return argv[i + 2]


def backstop(panel, flag):
    run = tmp / f"bt{time.time_ns()}"; run.mkdir()
    cmd = backstop_cmd(run)
    (run / "state").write_text(panel + "\n")
    if flag:
        (run / "stratoscan-alert-wake").write_text("")
    env = dict(os.environ, XDG_RUNTIME_DIR=str(run), PATH=f"{bin_}:{os.environ['PATH']}")
    subprocess.run(["sh", "-c", cmd], env=env, timeout=20)
    calls = (run / "calls").read_text() if (run / "calls").exists() else ""
    log = (run / "log").read_text() if (run / "log").exists() else ""
    return {"off": "off" in calls, "log": log, "flag": (run / "stratoscan-alert-wake").exists()}


r = backstop("on", True)
check(r["off"] and "off-after-alert" in r["log"] and not r["flag"], "the hold's backstop puts a lit panel out, logs it once, and clears its flag")
r = backstop("off", True)
check(not r["off"] and r["log"] == "" and not r["flag"], "on a panel already dark it only clears the flag: no second \"off\" in the log")
r = backstop("on", False)
check(not r["off"] and r["log"] == "", "and with no alert held it does nothing")

print("screen wake checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
