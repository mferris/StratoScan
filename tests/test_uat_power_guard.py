#!/usr/bin/env python3
"""net-watchdog.py's 978 MHz safeguard (2026-10-10): it pauses the 978
decoder when the 5 V supply dips fast, resumes it once the supply has been
quiet, waits longer after each pause, and never touches a decoder its
owner switched off."""
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("netwd", root / "deploy" / "net-watchdog.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


class Unit:
    """Stands in for systemctl and the kernel log."""
    def __init__(self):
        self.enabled, self.active, self.dips, self.calls = "enabled", "active", {}, []

    def run(self, argv, timeout=45):
        self.calls.append(argv)
        out = ""
        if argv[:2] == ["systemctl", "is-enabled"]:
            out = self.enabled
        elif argv[:2] == ["systemctl", "is-active"]:
            out = self.active
        elif argv[:2] == ["systemctl", "stop"]:
            self.active = "inactive"
        elif argv[:2] == ["systemctl", "start"]:
            self.active = "active"
        elif argv[0] == "journalctl":
            window = int(argv[argv.index("--since") + 1].strip("-s"))
            out = "\n".join(["hwmon hwmon3: Undervoltage detected!"] * self.dips.get(window, 0))
        return subprocess.CompletedProcess(argv, 0, out.encode(), b"")


tmp = tempfile.mkdtemp()
m.UAT_PAUSED = os.path.join(tmp, "net", "uat-paused")
u = Unit()
m.run = u.run
T = 1_800_000_000.0
W, Q = m.UAT_PAUSE_WINDOW_S, m.UAT_RESUME_QUIET_S

u.dips = {W: 2}
m.check_uat_power(T)
check(u.active == "active" and not os.path.exists(m.UAT_PAUSED), "a few dips: the decoder keeps running")

u.dips = {W: 5}
m.check_uat_power(T)
check(u.active == "inactive" and os.path.exists(m.UAT_PAUSED), "dips speeding up (5 in 10 min): the decoder is paused")
check(["systemctl", "disable", m.UAT_UNIT] not in u.calls, "paused with stop, never disabled (a reboot starts it again)")

u.dips = {W: 0, Q: 0}
m.check_uat_power(T + 20 * 60)
check(u.active == "inactive", "still inside the first pause's 30 minutes: stays paused, however quiet")
u.dips = {W: 0, Q: 3}
m.check_uat_power(T + 31 * 60)
check(u.active == "inactive", "past 30 minutes but 3 dips in the last half hour: stays paused")
u.dips = {W: 0, Q: 1}
m.check_uat_power(T + 32 * 60)
check(u.active == "active" and not os.path.exists(m.UAT_PAUSED), "quiet for half an hour: running again")

u.dips = {W: 6}
m.check_uat_power(T + 40 * 60)
check(u.active == "inactive", "dips again: paused a second time")
u.dips = {W: 0, Q: 0}
m.check_uat_power(T + 40 * 60 + 45 * 60)
check(u.active == "inactive", "the second pause waits an hour, not thirty minutes")
m.check_uat_power(T + 40 * 60 + 61 * 60)
check(u.active == "active", "and resumes after the hour")
check(min(m.UAT_COOLDOWN_MAX_S, m.UAT_COOLDOWN_S * 2 ** 9) == 6 * 3600, "the wait never exceeds six hours")

u.enabled, u.active, u.dips = "disabled", "inactive", {W: 9}
os.unlink(m.UAT_PAUSED) if os.path.exists(m.UAT_PAUSED) else None
before = len(u.calls)
m.check_uat_power(T + 5 * 3600)
check(not any(c[:2] in (["systemctl", "start"], ["systemctl", "stop"]) for c in u.calls[before:]),
      "a decoder its owner disabled is never started or stopped")

u.enabled, u.active, u.dips = "enabled", "inactive", {W: 9}
m.check_uat_power(T + 6 * 3600)
check(not os.path.exists(m.UAT_PAUSED), "enabled but not running (no 978 radio on this unit): nothing to pause")

# Switched off on the settings screen: the safeguard never starts it.
m.RADIOS_FILE = os.path.join(tmp, "radios.json")
with open(m.RADIOS_FILE, "w") as f:
    f.write('{"978": false}')
u.enabled, u.active, u.dips = "enabled", "inactive", {W: 0, Q: 0}
with open(m.UAT_PAUSED, "w") as f:
    f.write(f"{T} 1")
before = len(u.calls)
m.check_uat_power(T + 10 * 3600)
check(u.active == "inactive" and not any(c[:2] == ["systemctl", "start"] for c in u.calls[before:]),
      "978 switched off on the settings screen: never restarted, even after a pause")
os.unlink(m.RADIOS_FILE)

check("check_uat_power" in (root / "deploy" / "net-watchdog.py").read_text().split("def check_health")[1][:400],
      "the safeguard runs with the watchdog's other health checks")
print("uat power guard checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
