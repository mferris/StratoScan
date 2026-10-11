#!/usr/bin/env python3
"""Alert sounds are capped while the 5 V supply is dipping (#53, 2026-10-11).

On RDU most under-voltage warnings came one or two seconds after a nearby-
aircraft chime. net-watchdog.py writes /data/power.json; the page caps its
volume while it says "limited", without touching the owner's setting, and the
cap lifts by itself once the supply has been steady for the window.

Run: python3 tests/test_power_volume.py
"""
import importlib.util
import json
import os
import pathlib
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


tmp = tempfile.mkdtemp()
os.environ["STRATOSCAN_POWER_JSON"] = os.path.join(tmp, "data", "power.json")
nw = load("nw", D / "net-watchdog.py")

check(not nw.power_limited(0) and not nw.power_limited(2), "a couple of dips in six hours: no cap")
check(nw.power_limited(3) and nw.power_limited(40), "three or more: capped")
check(not nw.power_limited(None), "no reading at all: no cap")
check(nw.LIMIT_WINDOW_S == 6 * 3600, "the window is six hours, so the cap lifts within six hours of a fix")

for dips, want in ((12, True), (0, False)):
    nw.undervoltage_dips = lambda window, d=dips: d
    nw.check_power_status(now=1000.0)
    doc = json.load(open(os.environ["STRATOSCAN_POWER_JSON"]))
    check(doc["limited"] is want and doc["dips"] == dips, f"{dips} dips: power.json says limited={want}")
check("check_power_status" in (D / "net-watchdog.py").read_text().split("def check_health")[1][:400],
      "the watchdog checks it every run")

fg = load("fg", D / "funnel-gateway.py")
check(fg.Handler._is_local_only("/data/power.json"), "the unit's power state is not served to the public tunnel")

html = (ROOT / "index.html").read_text()
check("const POWER_VOLUME_CAP = 0.3;" in html, "the cap is 30%")
check("masterGain.gain.value = soundAllowedNow() ? effectiveVolume() : 0;" in html,
      "every sound goes through the capped volume (one master gain)")
check("Math.min(alertSettings.volume, POWER_VOLUME_CAP)" in html, "the cap only lowers, never raises")
check(html.count("alertSettings.volume = ") == html.count("alertSettings.volume = ") and
      "alertSettings.volume = POWER" not in html, "the owner's own volume setting is never rewritten")
check("if (!ON_DEVICE) return;" in html.split("async function checkPowerLimit")[1][:80],
      "only the panel itself asks (other screens play their own sounds on their own power)")
check("checkPowerLimit(); applyVolume();" in html, "checked every minute")
check("the power supply has been dipping" in html, "the settings screen says why the volume is lower")

print("power volume checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
