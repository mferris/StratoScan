#!/usr/bin/env python3
"""
Checks for the last-resort health checks in deploy/net-watchdog.py.

These run as root and can reboot a unit in someone else's house, so the rules
that matter are the brakes: nothing acts during boot, a restart comes before a
reboot, and no fault -- however persistent -- can reboot more often than
MIN_REBOOT_INTERVAL_S.

Run: python3 tests/test_health_watchdog.py
"""
import importlib.util
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "deploy", "net-watchdog.py")

failures = []
checks = 0


def check(label, condition):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


spec = importlib.util.spec_from_file_location("netwd", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

with tempfile.TemporaryDirectory() as tmp:
    m.AIRCRAFT_JSON = os.path.join(tmp, "aircraft.json")
    m.RECEIVER_RESTARTS = os.path.join(tmp, "net", "receiver-restarts")
    m.LAST_REBOOT = os.path.join(tmp, "state", "last-watchdog-reboot")
    m.KIOSK_STUCK_GLOB = os.path.join(tmp, "user", "*", "flightradar-kiosk-stuck")
    calls = []
    m.run = lambda argv, timeout=45: calls.append(argv[1:])
    uptime = [10_000.0]
    m._uptime = lambda: uptime[0]

    def stale(seconds):
        open(m.AIRCRAFT_JSON, "w").close()
        t = time.time() - seconds
        os.utime(m.AIRCRAFT_JSON, (t, t))

    # ---- receiver --------------------------------------------------------
    stale(1)
    m.check_receiver()
    check("fresh receiver data is left alone", calls == [])

    stale(600)
    uptime[0] = 60
    m.check_receiver()
    check("nothing acts during the boot grace period", calls == [])
    uptime[0] = 10_000

    m.check_receiver()
    check("stale data restarts readsb first", calls == [["restart", "readsb.service"]])
    check("the restart is counted", m._read_int(m.RECEIVER_RESTARTS) == 1)

    calls.clear()
    stale(1)
    m.check_receiver()
    check("recovered data clears the count", m._read_int(m.RECEIVER_RESTARTS) == 0)
    check("recovery takes no action", calls == [])

    os.remove(m.AIRCRAFT_JSON)
    m.check_receiver()
    check("a missing file counts as stale", calls == [["restart", "readsb.service"]])

    calls.clear()
    m._write_int(m.RECEIVER_RESTARTS, m.RECEIVER_REBOOT_AFTER)
    m.check_receiver()
    check("restarts that never help escalate to a reboot", calls == [["reboot"]])

    calls.clear()
    m.check_receiver()
    check("a second reboot inside the interval is refused", calls == [])

    # ---- kiosk -----------------------------------------------------------
    os.remove(m.LAST_REBOOT)
    stuck_dir = os.path.join(tmp, "user", "1000")
    os.makedirs(stuck_dir)
    stuck = os.path.join(stuck_dir, "flightradar-kiosk-stuck")

    m._write_int(stuck, m.KIOSK_REBOOT_AFTER - 1)
    m.check_kiosk()
    check("a browser restart still being given its chance is left alone", calls == [])

    m._write_int(stuck, m.KIOSK_REBOOT_AFTER)
    m.check_kiosk()
    check("a display frozen through repeated restarts reboots", calls == [["reboot"]])

    calls.clear()
    m.check_kiosk()
    check("the kiosk escalation obeys the same reboot interval", calls == [])

    # ---- isolation -------------------------------------------------------
    def boom():
        raise RuntimeError("simulated")
    orig = m.check_receiver
    m.check_receiver = boom
    try:
        m.check_health()
        check("a failing check does not stop the others", True)
    except Exception:
        check("a failing check does not stop the others", False)
    m.check_receiver = orig

    check("the reboot interval is long enough to never loop",
          m.MIN_REBOOT_INTERVAL_S >= 3600)

print(f"{checks - len(failures)}/{checks} health watchdog checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
