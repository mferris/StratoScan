#!/usr/bin/env python3
"""The control arc on the "Retro with Dials" case (roadmap 5.1, #22).

  RANGE dial    an EC11 rotary encoder. Turning it sends F13 or F14 and
                pushing it sends F15, as key presses on a virtual keyboard.
                Chromium hands them to the page, which changes range and goes
                home exactly as its on-screen buttons do. Clockwise is
                range up, that is, zoom out, as on a radar's RANGE knob.
  SCREEN button a press asks the wake listener to turn the panel off, or on
                (/wake/button). Holding it HOLD_S sends F16: the page switches
                between "sleeps when idle" and "always on", which is its
                setting to keep.
  STATUS lamp   an RGB LED behind a jewel lens:
                  red    the 5 V supply is dipping (two under-voltage
                         warnings in ten minutes, or one right now)
                  amber  the receiver has gone deaf (fewer than QUIET_MSGS
                         messages a minute for QUIET_MIN minutes, or
                         readsb's statistics have stopped)
                  green  hearing aircraft
                Dimmed while the screen is off.

Off unless /etc/stratoscan/controls.json says {"enabled": true}: a unit
without the arc has nothing on these pins, and driving outputs on a header
that something else might use is not a default. Pins can be overridden there
too. Wiring: enclosure/Retro Radar with Dials/README.md.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

CONFIG = "/etc/stratoscan/controls.json"
DEFAULT_PINS = {"enc_a": 17, "enc_b": 27, "enc_push": 22, "screen": 23,
                "led_r": 12, "led_g": 13, "led_b": 18}
DEFAULTS = {"enabled": False, "pins": DEFAULT_PINS, "clockwise": "range_up",
            "brightness": 0.35, "brightness_screen_off": 0.06}
# evdev key codes: F13..F16 type nothing and no keyboard layout gives them a
# meaning, so they cannot reach a text field as characters. The page matches
# them by KeyboardEvent.code, which is the same whatever the layout.
KEYS = {"range_up": 183, "range_down": 184, "home": 185, "screen_mode": 186}   # KEY_F13..KEY_F16
WAKE = "http://127.0.0.1:8084"
HOLD_S = 2.0
POLL_S = 10
QUIET_MSGS = 10       # messages a minute below which the receiver counts as deaf
QUIET_MIN = 3         # for this long (the 2026-10-11 noise flood ran at 0-5 a minute)
STALE_S = 120         # readsb's statistics older than this: the receiver has stopped
RED_DIPS = 2          # under-voltage warnings in ten minutes that make the lamp red
COLOURS = {"green": (0.0, 1.0, 0.0), "amber": (1.0, 0.45, 0.0), "red": (1.0, 0.0, 0.0)}
STATS = "/run/readsb/stats.json"


def load_config(path=CONFIG):
    """The settings, with defaults. Bad pins fall back to the defaults whole."""
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        with open(path) as f:
            user = json.load(f)
    except (OSError, ValueError):
        return cfg
    if not isinstance(user, dict):
        return cfg
    cfg["enabled"] = user.get("enabled") is True
    if user.get("clockwise") in ("range_up", "range_down"):
        cfg["clockwise"] = user["clockwise"]
    for k in ("brightness", "brightness_screen_off"):
        v = user.get(k)
        if isinstance(v, (int, float)) and 0 <= v <= 1:
            cfg[k] = float(v)
    pins = dict(DEFAULT_PINS)
    pins.update(user.get("pins") or {})
    ok = (set(pins) == set(DEFAULT_PINS)
          and all(isinstance(p, int) and 2 <= p <= 27 for p in pins.values())
          and len(set(pins.values())) == len(pins))
    cfg["pins"] = pins if ok else dict(DEFAULT_PINS)
    return cfg


def lamp_colour(dips_10m, under_now, quiet_s, stats_age_s):
    if under_now or dips_10m >= RED_DIPS:
        return "red"
    if stats_age_s is None or stats_age_s > STALE_S or quiet_s >= QUIET_MIN * 60:
        return "amber"
    return "green"


class Deafness:
    """How long the receiver has been hearing fewer than QUIET_MSGS a minute."""
    def __init__(self):
        self.quiet_since = None

    def update(self, msgs_per_min, now):
        if msgs_per_min is None or msgs_per_min >= QUIET_MSGS:
            self.quiet_since = None
            return 0.0
        if self.quiet_since is None:
            self.quiet_since = now
        return now - self.quiet_since


def read_receiver(path=STATS, now=None):
    """(messages accepted in the last minute, age of the statistics in s)."""
    now = time.time() if now is None else now
    try:
        with open(path) as f:
            s = json.load(f)
        local = s.get("last1min", {}).get("local", {})
        acc = local.get("accepted", [])
        msgs = sum(acc) if isinstance(acc, list) else int(acc or 0)
        return msgs, now - float(s.get("now", 0))
    except (OSError, ValueError, TypeError):
        return None, None


def read_power():
    """(under-voltage warnings in the last ten minutes, under-voltage now)."""
    dips = 0
    try:
        out = subprocess.run(["journalctl", "-k", "--since", "-600s", "--no-pager", "-o", "cat"],
                             capture_output=True, text=True, timeout=20).stdout
        dips = sum(1 for line in out.splitlines() if "Undervoltage detected" in line)
    except Exception:
        pass
    now = False
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=5).stdout
        now = bool(int(out.strip().split("=")[1], 16) & 0x1)
    except Exception:
        pass
    return dips, now


def wake(path):
    """POST to the wake listener; its JSON answer, or {}."""
    try:
        with urllib.request.urlopen(urllib.request.Request(WAKE + path, method="POST", data=b""),
                                    timeout=5) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except Exception:
        return {}


def scaled(colour, brightness):
    return tuple(round(c * brightness, 3) for c in COLOURS[colour])


class ScreenButton:
    """A press toggles the panel; a hold sends the screen-mode key instead."""
    def __init__(self, tap, post):
        self.tap, self.post, self.held = tap, post, False

    def pressed(self):
        self.held = False

    def hold(self):
        self.held = True
        self.tap(KEYS["screen_mode"])

    def released(self):
        if not self.held:
            self.post("/wake/button")
        self.held = False


def main():
    cfg = load_config()
    if not cfg["enabled"]:
        print("controls: off (no control arc in /etc/stratoscan/controls.json)", flush=True)
        return 0
    from evdev import UInput, ecodes
    from gpiozero import Button, RGBLED, RotaryEncoder

    keyboard = UInput({ecodes.EV_KEY: sorted(KEYS.values())}, name="stratoscan-controls")

    def tap(code):
        keyboard.write(ecodes.EV_KEY, code, 1)
        keyboard.syn()
        keyboard.write(ecodes.EV_KEY, code, 0)
        keyboard.syn()

    p = cfg["pins"]
    cw = KEYS[cfg["clockwise"]]
    ccw = KEYS["range_down" if cfg["clockwise"] == "range_up" else "range_up"]
    dial = RotaryEncoder(p["enc_a"], p["enc_b"], max_steps=0)
    dial.when_rotated_clockwise = lambda: tap(cw)
    dial.when_rotated_counter_clockwise = lambda: tap(ccw)
    push = Button(p["enc_push"], bounce_time=0.03)
    push.when_pressed = lambda: tap(KEYS["home"])
    screen = ScreenButton(tap, wake)
    sb = Button(p["screen"], bounce_time=0.03, hold_time=HOLD_S)
    sb.when_pressed = screen.pressed
    sb.when_held = screen.hold
    sb.when_released = screen.released
    lamp = RGBLED(p["led_r"], p["led_g"], p["led_b"])
    print("controls: on (pins %s)" % json.dumps(p, sort_keys=True), flush=True)

    deaf = Deafness()
    last = None
    while True:
        now = time.time()
        msgs, age = read_receiver(now=now)
        dips, under = read_power()
        colour = lamp_colour(dips, under, deaf.update(msgs, now), age)
        panel = wake("/wake/state").get("panel", "on")
        lamp.color = scaled(colour, cfg["brightness"] if panel != "off" else cfg["brightness_screen_off"])
        if colour != last:
            print(f"status lamp: {colour} ({msgs} msgs/min, {dips} dips in 10 min)", flush=True)
            last = colour
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
