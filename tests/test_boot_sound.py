#!/usr/bin/env python3
"""A take-off sound when the radar is plugged in, never after a restart (#81).

The owner's ask (2026-10-23). The unit reports whether this boot was a
power-on: the bootloader's copy of the Pi's reset flags (PM_RSTS) has HADPOR,
bit 12, set when the power came on, and other bits after a reboot or a
watchdog reset (RDU read 0x1000 after a replug). The panel plays the sound
once per boot, in the first five minutes, through the usual volume, mute and
quiet hours, and only while its setting is on.

Run: python3 tests/test_boot_sound.py
"""
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


spec = importlib.util.spec_from_file_location("setup_server", ROOT / "deploy" / "setup-server.py")
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)
tmp = pathlib.Path(tempfile.mkdtemp())
for label, raw, want in (("power-on (0x1000, RDU after a replug)", b"\x00\x00\x10\x00", True),
                         ("a watchdog or software reset", b"\x00\x00\x00\x20", False),
                         ("power-on with other bits too", b"\x00\x00\x10\x05", True)):
    (tmp / "rsts").write_bytes(raw)
    ss.RSTS_PATH = str(tmp / "rsts")
    check(ss.boot_info()["powerOn"] is want, f"boot_info reads {label} as powerOn={want}")
ss.RSTS_PATH = str(tmp / "missing")
info = ss.boot_info()
check(info["powerOn"] is False and isinstance(info["uptimeS"], int) or info["uptimeS"] is None,
      "no reset flags (not a Pi): never a power-on")
shutil.rmtree(tmp, ignore_errors=True)
srv = (ROOT / "deploy" / "setup-server.py").read_text()
check('"boot": boot_info(),' in srv, "the panel's /onboard status carries it")

html = (ROOT / "index.html").read_text()
start = html.index("// ---- Take-off sound at power-on (#81)")
block = html[start:html.index("function playAlertSound() {", start)]
check("bootSound: true" in html.split("const DEFAULT_ALERT_SETTINGS")[1][:900], "the setting is on by default")
check("key: 'bootSound'" in html, "and has a row in Settings")
if not shutil.which("node"):
    print("skip page checks (no node)")
else:
    js = r"""
const store = {};
const localStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
let ON_DEVICE = true, netInfo = null, allowed = true, played = 0;
const alertSettings = { bootSound: true };
function soundAllowedNow() { return allowed; }
""" + block.replace("function playTakeoffSound() {", "function playTakeoffSound() { played++; return;") + r"""
const out = {};
const boot = (id, powerOn, uptimeS) => { netInfo = { boot: { id, powerOn, uptimeS } }; maybePlayBootSound(); return played; };
out.powerOn = boot('a', true, 40);
out.again = boot('a', true, 220);                 // a page reload in the same boot
out.reboot = boot('b', false, 30);
out.late = boot('c', true, 900);
alertSettings.bootSound = false; out.off = boot('d', true, 30); alertSettings.bootSound = true;
allowed = false; out.quiet = boot('e', true, 30); allowed = true; out.quietLater = boot('e', true, 200);
ON_DEVICE = false; out.remote = boot('f', true, 30);
console.log(JSON.stringify(out));
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stderr[-1500:])
    check(o.get("powerOn") == 1, "after a power-on the take-off sound plays")
    check(o.get("again") == 1, "once: reloading the page in the same boot doesn't play it again")
    check(o.get("reboot") == 1, "a reboot or watchdog reset plays nothing")
    check(o.get("late") == 1, "nor a power-on more than five minutes ago")
    check(o.get("off") == 1, "nor anything with the setting off")
    check(o.get("quiet") == 1 and o.get("quietLater") == 1,
          "inside quiet hours (or muted) it stays silent, and doesn't play later in that boot")
    check(o.get("remote") == 1, "and only the panel plays it, not a phone or laptop viewing the page")

print("boot sound checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
