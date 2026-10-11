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
check("if (alertSettings.quietScreen === 'dark') return false;" in page, "dark and silent is silent, emergencies included")
check("if (alertSettings.quietSounds) return true;" in page, "sounds can be left on for quiet hours")
check("if (screenModeNow() === 'dark') return;" in page, "a dark-and-silent screen is not woken by alerts")
check("fetch('/wake/mode?m='" in page and "applyScreenPolicy(); }, 60 * 1000)" in page,
      "the page sends the mode to the listener, and re-checks it every minute")
for label in ("Sleeps when idle", "Always on", "As the rest of the day", "Dark — alerts light it", "Dark and silent", "Sounds during quiet hours"):
    check(label in page, f"the settings offer '{label}'")
print("screen mode checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
