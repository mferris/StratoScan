#!/usr/bin/env python3
"""The speakers start at 70% (2026-10-17).

WirePlumber starts a new output at 40% (0.4 cubed, 0.064, on its linear
scale), and on RDU that made the alerts and spoken announcements much too
quiet next to the speakers' own full-scale test. The installer puts a
WirePlumber setting in place so a new unit's output starts at 70% instead,
without touching a volume an owner has already set.

Checked on RDU's WirePlumber 0.5.8: `pw-config -n wireplumber.conf merge
wireplumber.settings` merges this file's value. WirePlumber itself can't run
here, so this checks the file and the installer.

Run: python3 tests/test_audio_volume.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


conf = (D / "50-stratoscan-volume.conf").read_text()
code = "\n".join(l.split("#", 1)[0] for l in conf.splitlines())
m = re.search(r"wireplumber\.settings\s*=\s*\{([^}]*)\}", code)
check(m is not None, "the file is a wireplumber.settings section")
v = re.search(r"device\.routes\.default-sink-volume\s*=\s*([0-9.]+)", m.group(1) if m else "")
check(v is not None, "it sets the default volume for a new output")
check(v is not None and abs(float(v.group(1)) - 0.7 ** 3) < 0.0005,
      "to 0.343, which is 70% on the cubic scale wpctl and the sliders show")
inst = (D / "install-setup-server.sh").read_text()
check("install -m 0644 deploy/50-stratoscan-volume.conf /etc/wireplumber/wireplumber.conf.d/50-stratoscan-volume.conf" in inst,
      "the installer puts it where WirePlumber reads system settings")
check("set-volume" not in inst, "and leaves a volume already set on the unit alone")

print("audio volume checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
