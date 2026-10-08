#!/usr/bin/env python3
"""The panel's touch screen delivers real touch events to the page (2026-10-08):
Raspberry Pi OS's autotouch maps a touch screen with mouseEmulation="yes",
which makes labwc turn every touch into mouse events, one pointer, so a pinch
on the panel did nothing. The installer writes the labwc setting; this runs
its shell on a copy of the three cases."""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
inst = open(os.path.join(ROOT, "deploy", "install-setup-server.sh"), encoding="utf-8").read()
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


# Lift the block out of the installer and run it against a temporary home.
m = re.search(r'  RC="\$KHOME/.config/labwc/rc.xml"\n(.*?)  if live; then pkill', inst, re.S)
check(bool(m), "the installer has the labwc touch block")
block = 'RC="$KHOME/.config/labwc/rc.xml"\n' + (m.group(1) if m else "")
block = block.replace('install -d -o "$KIOSK_USER" -g "$KIOSK_USER"', "install -d").replace('chown "$KIOSK_USER:$KIOSK_USER" "$RC"', "true")


def run(initial):
    home = tempfile.mkdtemp()
    rc = os.path.join(home, ".config", "labwc", "rc.xml")
    if initial is not None:
        os.makedirs(os.path.dirname(rc))
        open(rc, "w").write(initial)
    r = subprocess.run(["sh", "-c", block], env={**os.environ, "KHOME": home, "KIOSK_USER": "x"}, capture_output=True, text=True)
    return r, (open(rc).read() if os.path.exists(rc) else "")


auto = ('<?xml version="1.0"?>\n<openbox_config xmlns="http://openbox.org/3.4/rc">\n'
        '\t<touch deviceName="Waveshare  Waveshare -079-HD (USB 1-1)" mapToOutput="HDMI-A-1" mouseEmulation="yes"/>\n</openbox_config>\n')
r, out = run(auto)
check(r.returncode == 0 and 'mouseEmulation="no"' in out and 'mouseEmulation="yes"' not in out, "autotouch's line is flipped to real touch")
check('mapToOutput="HDMI-A-1"' in out, "and its output mapping is kept")
r, out = run(None)
check(r.returncode == 0 and '<touch mouseEmulation="no"/>' in out and out.startswith("<?xml"), "no config: a fresh one with real touch for every touch device")
custom = '<?xml version="1.0"?>\n<openbox_config xmlns="http://openbox.org/3.4/rc">\n\t<theme><name>x</name></theme>\n</openbox_config>\n'
r, out = run(custom)
check(r.returncode == 0 and "<theme>" in out and '<touch mouseEmulation="no"/>' in out, "an owner's own config keeps its contents and gains the line")
r, out2 = run(out)
check(out2 == out, "running again changes nothing")
print("kiosk touch checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
