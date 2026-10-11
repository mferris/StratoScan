#!/usr/bin/env python3
"""The control arc (Retro with Dials, roadmap 5.1, #22): deploy/controls.py,
its wake-listener routes, the page's keys, and the wiring table.

No GPIO here: the parts that decide things (settings, the lamp's colour, the
button's press-or-hold, the listener's toggle) are tested directly; the
gpiozero and evdev objects only carry their results to the pins.

Run: python3 tests/test_controls.py
"""
import importlib.util
import json
import os
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
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


os.environ["XDG_RUNTIME_DIR"] = tempfile.mkdtemp()
c = load("controls", D / "controls.py")

# ---- settings ----------------------------------------------------------------
tmp = pathlib.Path(tempfile.mkdtemp())


def cfg(obj):
    p = tmp / "controls.json"
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj))
    return c.load_config(str(p))


check(c.load_config(str(tmp / "absent.json"))["enabled"] is False, "no settings file: off")
check(cfg("not json")["enabled"] is False, "a broken file: off")
check(cfg({"enabled": "yes"})["enabled"] is False, "only a real true turns it on")
on = cfg({"enabled": True})
check(on["enabled"] is True and on["pins"] == c.DEFAULT_PINS, "enabled with the default pins")
check(cfg({"enabled": True, "pins": {"screen": 24}})["pins"]["screen"] == 24, "a pin can be moved")
check(cfg({"enabled": True, "pins": {"screen": 17}})["pins"] == c.DEFAULT_PINS, "two controls on one pin: the defaults")
check(cfg({"enabled": True, "pins": {"screen": 40}})["pins"] == c.DEFAULT_PINS, "a pin that does not exist: the defaults")
check(cfg({"enabled": True, "clockwise": "range_down"})["clockwise"] == "range_down", "the dial's direction can be reversed")
check(cfg({"enabled": True, "brightness": 7})["brightness"] == c.DEFAULTS["brightness"], "a brightness out of 0..1 is ignored")
used = set(c.DEFAULT_PINS.values())
check(not used & {2, 3, 14, 15}, "the default pins leave I2C (light sensor) and the UART (presence sensor) free")

# ---- the status lamp -------------------------------------------------------------
check(c.lamp_colour(0, False, 0, 5) == "green", "hearing, steady power: green")
check(c.lamp_colour(1, False, 0, 5) == "green", "one dip in ten minutes is not yet red")
check(c.lamp_colour(2, False, 0, 5) == "red", "two dips in ten minutes: red")
check(c.lamp_colour(0, True, 0, 5) == "red", "under-voltage right now: red")
check(c.lamp_colour(0, False, 179, 5) == "green", "quiet for under three minutes: still green")
check(c.lamp_colour(0, False, 180, 5) == "amber", "quiet for three minutes: amber")
check(c.lamp_colour(0, False, 0, 600) == "amber", "readsb's statistics stopped: amber")
check(c.lamp_colour(0, False, 0, None) == "amber", "no statistics at all: amber")
check(c.lamp_colour(5, False, 999, None) == "red", "power trouble outranks a deaf receiver")
d = c.Deafness()
check(d.update(500, 100.0) == 0.0, "busy: not quiet")
check(d.update(3, 200.0) == 0.0 and d.update(2, 290.0) == 90.0, "quiet time counts from the first quiet reading")
check(d.update(300, 300.0) == 0.0 and d.update(1, 310.0) == 0.0, "one busy reading starts the count again")
check(c.scaled("amber", 0.5) == (0.5, 0.225, 0.0), "colours scale with the brightness")
st = tmp / "stats.json"
st.write_text(json.dumps({"now": 1000.0, "last1min": {"local": {"accepted": [120, 8]}}}))
check(c.read_receiver(str(st), now=1030.0) == (128, 30.0), "messages a minute and the statistics' age, from readsb")
check(c.read_receiver(str(tmp / "none.json")) == (None, None), "no statistics file: nothing")

# ---- the SCREEN button -------------------------------------------------------------
taps, posts = [], []
b = c.ScreenButton(taps.append, posts.append)
b.pressed(); b.released()
check(posts == ["/wake/button"] and taps == [], "a press toggles the panel")
b.pressed(); b.hold(); b.released()
check(taps == [c.KEYS["screen_mode"]] and posts == ["/wake/button"], "a hold sends the screen-mode key, and the release does nothing more")

# ---- keys: the service sends them, the page reads them -------------------------------
check(c.KEYS == {"range_up": 183, "range_down": 184, "home": 185, "screen_mode": 186}, "the keys are F13-F16 (evdev 183-186)")
html = (ROOT / "index.html").read_text()
block = html[html.index("const CONTROL_KEYS"):html.index("function toggleScreenAlwaysOn")]
check("F13: () => zoomViewAbout(1 / VIEW_STEP" in block, "F13, range up, zooms out")
check("F14: () => zoomViewAbout(VIEW_STEP" in block, "F14, range down, zooms in")
check("F15: goHome" in block and "F16: toggleScreenAlwaysOn" in block, "F15 goes home, F16 switches always-on")
check("CONTROL_KEYS[e.code]" in html, "matched by code, which no keyboard layout changes")
check("alertSettings.screenMode === 'on' ? 'sleep' : 'on'" in html and "saveAlertSettings();" in html,
      "the hold changes the page's own setting, so the page's policy does not undo it")

# ---- the wake listener ---------------------------------------------------------------
wl = load("wl", D / "wake-listener.py")
calls = []
wl.subprocess.run = lambda args, **k: calls.append(args)
panel = {"s": "on"}
wl._panel_state = lambda: panel["s"]
wl._mode = "sleep"
check(wl.screen_button() == "off" and ["wlopm", "--off", "*"] in calls, "the button turns a lit panel off")
calls.clear(); panel["s"] = "off"
check(wl.screen_button() == "on" and ["wlopm", "--on", "*"] in calls
      and any(a[:3] == ["systemctl", "--user", "restart"] for a in calls), "and a dark one on, with a fresh idle time")
calls.clear(); wl._mode = "on"
wl.screen_button()
check(not any(a[:3] == ["systemctl", "--user", "restart"] for a in calls), "in always-on, no screensaver to restart")


def post(path):
    H = wl.Handler
    h = H.__new__(H); h.path = path; out = {"code": None, "body": b""}
    h.send_response = lambda code, *a: out.__setitem__("code", code)
    h.send_header = lambda *a: None; h.end_headers = lambda: None
    h.send_error = lambda code, *a: out.__setitem__("code", code)
    h.wfile = type("W", (), {"write": lambda self, b: out.__setitem__("body", out["body"] + b)})()
    h.do_POST()
    return out


panel["s"] = "on"; wl._mode = "sleep"
r = post("/wake/state")
check(r["code"] == 200 and json.loads(r["body"]) == {"panel": "on", "mode": "sleep"}, "/wake/state reports the panel and mode")
r = post("/wake/button")
check(r["code"] == 200 and json.loads(r["body"])["panel"] == "off", "/wake/button toggles and says what it did")
calls.clear(); wl._mode = "on"; panel["s"] = "off"
post("/wake/touch")
check(["wlopm", "--on", "*"] in calls, "in always-on, a touch wakes a panel the button switched off")
calls.clear(); wl._mode = "sleep"; panel["s"] = "off"
post("/wake/touch")
check(["wlopm", "--on", "*"] not in calls, "in other modes the screensaver does that, as before")

# ---- install, update, and the wiring table --------------------------------------------
unit = (D / "stratoscan-controls.service").read_text()
check("ConditionPathExists=/etc/stratoscan/controls.json" in unit, "the service runs only where the arc is fitted")
check("DevicePolicy=closed" in unit and "DeviceAllow=char-gpiochip rw" in unit and "DeviceAllow=/dev/uinput rw" in unit,
      "it reaches the GPIO chip and uinput and no other device but vcio")
check("IPAddressAllow=localhost" in unit and "IPAddressDeny=any" in unit, "and nothing on the network but the wake listener")
inst = (D / "install-setup-server.sh").read_text()
check("controls.py" in inst and "stratoscan-controls.service" in inst and 'CONTROLS:-0' in inst,
      "the installer installs it, and CONTROLS=1 turns it on")
check("python3-gpiozero python3-lgpio python3-evdev" in inst, "with the libraries it needs")
ota = (D / "ota.py").read_text()
check('"controls.py",' in ota and '"controls.py":        ("system", "stratoscan-controls.service")' in ota,
      "updates may replace it, and restart its service")
readme = (ROOT / "enclosure" / "Retro Radar with Dials" / "README.md").read_text()
table = {m.group(1): int(m.group(2)) for m in re.finditer(r"\| (Encoder A|Encoder B|Encoder push switch|SCREEN button|LED red|LED green|LED blue)[^|]*\| GPIO (\d+) \|", readme)}
want = {"Encoder A": "enc_a", "Encoder B": "enc_b", "Encoder push switch": "enc_push", "SCREEN button": "screen",
        "LED red": "led_r", "LED green": "led_g", "LED blue": "led_b"}
check(len(table) == 7 and all(table[k] == c.DEFAULT_PINS[v] for k, v in want.items()),
      "the README's wiring table and the code's pins agree")

print("controls checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
