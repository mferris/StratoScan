#!/usr/bin/env python3
"""The screen's modes (2026-10-11): sleeps when idle (the default), always
on, and in quiet hours either as the rest of the day, dark with alerts
lighting it, or dark and silent. The wake listener acts on the mode the
page sends; the page works the mode out and decides sounds."""
import importlib.util
import pathlib
import re
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


state = {"panel": "on", "saver": "active"}
calls = []


class R:
    def __init__(self, out=""):
        self.stdout = out


def fake_run(argv, **k):
    calls.append(argv)
    if argv[:2] == ["wlopm", "--on"]:
        state["panel"] = "on"
    elif argv[:2] == ["wlopm", "--off"]:
        state["panel"] = "off"
    elif argv[:3] == ["systemctl", "--user", "stop"]:
        state["saver"] = "inactive"
    elif argv[:3] == ["systemctl", "--user", "start"] or argv[:3] == ["systemctl", "--user", "restart"]:
        state["saver"] = "active"
    elif argv[:3] == ["systemctl", "--user", "is-active"]:
        return R(state["saver"])
    return R()


wl.subprocess.run = fake_run
wl._panel_state = lambda: state["panel"]
wl.ALERT_FLAG = "/dev/null"

check(wl._mode == "sleep", "the listener starts in the default mode, sleeps when idle")
wl.set_mode("on")
check(state["saver"] == "inactive" and state["panel"] == "on", "always on: the screensaver stops and the panel is lit")
state["panel"] = "on"
wl._wake(alert=True)
check(wl._hold_until == 0.0 and state["saver"] == "inactive", "an alert while always on starts no hold and does not restart the screensaver")
wl.set_mode("sleep")
check(state["saver"] == "active", "back to sleeping when idle: the screensaver runs again")
wl.set_mode("alerts")
check(state["panel"] == "off" and ["logger", "-t", "stratoscan-screen", "off-quiet"] in calls,
      "quiet hours, alerts light it: dark from the start")
wl._wake(alert=True)
check(state["panel"] == "on" and wl._hold_until > 0, "and an alert lights it with the two-minute hold")
state["panel"] = "on"
wl.set_mode("alerts")
check(state["panel"] == "on", "re-sending the same mode does not put out a panel someone is using")
wl.set_mode("dark")
check(state["panel"] == "off" and state["saver"] == "active", "dark and silent: dark, the screensaver still runs so a touch wakes it")
try:
    wl.set_mode("disco")
    check(False, "an unknown mode is refused")
except ValueError:
    check(True, "an unknown mode is refused")

page = (root / "index.html").read_text()
defaults = re.search(r"const DEFAULT_ALERT_SETTINGS = \{(.*?)\};", page).group(1)
check("screenMode: 'sleep'" in defaults and "quietScreen: 'same'" in defaults and "quietSounds: false" in defaults,
      "the defaults are the behaviour before: sleeps when idle, quiet hours change only the sound")
check("if (alertSettings.quietScreen === 'dark') return Date.now() < quietEmergencyUntil;" in page
      and "if (alertSettings.quietScreen === 'dark') return !!alertSettings.quietDarkEmergencies;" in page,
      "dark and silent is silent unless emergencies are let through")
check("quietDarkEmergencies: false" in defaults, "by default even emergencies stay dark and silent")
check("!(why === 'emergency' && alertSettings.quietDarkEmergencies)" in page, "a let-through emergency lights a dark-and-silent screen")
check("if (emergencyThroughQuiet()) allowThroughQuiet" in page, "and sounds")
check("if (alertSettings.quietSounds) return true;" in page, "sounds can be left on for quiet hours")
check("if (screenModeNow() === 'dark' &&" in page, "a dark-and-silent screen is not woken by ordinary alerts")
check("fetch('/wake/mode?m='" in page and "applyScreenPolicy(); }, 60 * 1000)" in page,
      "the page sends the mode to the listener, and re-checks it every minute")
for label in ("Sleeps when idle", "Always on", "As the rest of the day", "Dark — alerts light it", "Dark and silent", "Sounds during quiet hours"):
    check(label in page, f"the settings offer '{label}'")

# ---- found on RDU 2026-10-11: the screen would not wake ------------------------
# 1. After a fresh boot the listener started before the session published
#    WAYLAND_DISPLAY, so every wlopm call failed. It now finds the socket.
import os
import tempfile as _tf
_rd = _tf.mkdtemp()
open(os.path.join(_rd, "wayland-0"), "w").close()
open(os.path.join(_rd, "wayland-0.lock"), "w").close()
_saved = {k: os.environ.get(k) for k in ("WAYLAND_DISPLAY", "XDG_RUNTIME_DIR")}
os.environ.pop("WAYLAND_DISPLAY", None)
os.environ["XDG_RUNTIME_DIR"] = _rd
wl._ensure_wayland()
check(os.environ.get("WAYLAND_DISPLAY") == "wayland-0", "with no WAYLAND_DISPLAY, the listener finds the compositor's socket (not its lock)")
os.environ["WAYLAND_DISPLAY"] = "wayland-7"
wl._ensure_wayland()
check(os.environ["WAYLAND_DISPLAY"] == "wayland-7", "and leaves one that is set alone")
for k, v in _saved.items():
    if v is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = v
_src = (root / "deploy" / "wake-listener.py").read_text()
check(_src.count("_ensure_wayland()") >= 4, "every path that runs wlopm looks first (requests, panel state, hold, watchdog)")
# 2. swayidle ties a resume to the timeout just before it. The wake-on-touch
#    followed the 20-minute idle timeout, so a panel put out by the alert hold
#    or quiet hours did not wake on a touch. It must follow `timeout 1 true`.
_unit = (root / "deploy" / "stratoscan-screensaver.service").read_text()
_exec = [l for l in _unit.splitlines() if l.startswith("ExecStart=")][0]
check("timeout 1 true resume " in _exec, "the wake-on-touch follows the 1-second timeout, so any touch after a pause wakes the panel")
check(_exec.count(" resume ") == 1, "and there is only one")

print("screen mode checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
