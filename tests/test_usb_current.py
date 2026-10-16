#!/usr/bin/env python3
"""Full USB current without a 5 A USB-C supply (2026-10-16, #53).

The power fix feeds the Pi from a 12 V trigger board and a 5 V regulator, so
the Pi can't ask its supply what it offers, and its firmware then limits the
USB ports to 600 mA in all: too little for the display, which draws through
the Pi's USB, and the receiver's two radios. The installer lifts the limit in
config.txt; with the official 5 A supply plugged straight in, the firmware
sets the same thing itself.

PSU_MAX_CURRENT in the EEPROM would also hide the warning at boot, but writing
the EEPROM flashes the newest bootloader with it, and this project never moves
the bootloader (os-update.py holds rpi-eeprom). On RDU that would have taken it
from May's to September's.

This runs the installer's step on a stand-in config.txt.

Run: python3 tests/test_usb_current.py
"""
import pathlib
import re
import subprocess
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


inst = (D / "install-setup-server.sh").read_text()
m = re.search(r"^if \[ -f \"\$CFG\" \] && ! grep -q '\^usb_max_current_enable=' \"\$CFG\"; then\n.*?\nfi\n", inst, re.S | re.M)
check(m is not None, "the installer has a step for the USB current limit")
step = m.group(0) if m else "false\n"

with tempfile.TemporaryDirectory() as t:
    cfg = pathlib.Path(t) / "config.txt"
    # Ends inside a [pi5] section, as Raspberry Pi OS's own file can.
    cfg.write_text("dtparam=audio=on\n[pi5]\ndtoverlay=nospi10\n")
    for _ in range(2):
        subprocess.run(["sh", "-c", f'CFG="{cfg}"\n' + step], check=True, capture_output=True, timeout=20)
    lines = cfg.read_text().splitlines()
    on = [i for i, l in enumerate(lines) if l == "usb_max_current_enable=1"]
    check(len(on) == 1, "it adds usb_max_current_enable=1, once, however often the installer runs")
    section = next((l for l in reversed(lines[:on[0]]) if l.startswith("[")), None) if on else None
    check(section == "[all]", "under [all], so it holds on every model whatever section the file ended in")
    check(lines[:3] == ["dtparam=audio=on", "[pi5]", "dtoverlay=nospi10"], "and leaves the rest of the file alone")

    cfg.write_text("[all]\nusb_max_current_enable=0\n")
    subprocess.run(["sh", "-c", f'CFG="{cfg}"\n' + step], check=True, capture_output=True, timeout=20)
    check(cfg.read_text() == "[all]\nusb_max_current_enable=0\n", "a file that already says either way is left as its owner set it")

# Nothing on a unit writes the EEPROM: that would move the bootloader.
writers = [p.name for p in D.iterdir() if p.is_file()
           and re.search(r"rpi-eeprom-config[^\n]*--(apply|edit)|rpi-eeprom-update[^\n]*-a\b", p.read_text(errors="ignore"))]
check(not writers, "nothing in deploy/ writes the EEPROM" + (f" ({', '.join(writers)})" if writers else ""))
check('NEVER = ("rpi-eeprom",)' in (D / "os-update.py").read_text(), "and OS updates still never move the bootloader")

print("usb current checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
