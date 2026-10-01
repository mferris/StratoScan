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
    m.KIOSK_STUCK_GLOB = os.path.join(tmp, "user", "*", "stratoscan-kiosk-stuck")
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

    # uhubctl present: a hung radio gets its power cut before any reboot.
    m.UHUBCTL = os.path.join(tmp, "uhubctl")
    open(m.UHUBCTL, "w").close()
    m.USB_CYCLED = os.path.join(tmp, "net", "usb-power-cycled")
    slept = []
    m.sleep = slept.append
    calls.clear()
    m._write_int(m.RECEIVER_RESTARTS, m.RECEIVER_REBOOT_AFTER)
    m.check_receiver()
    offs = [c for c in calls if c[-1] == "off"]
    ons = [c for c in calls if c[-1] == "on"]
    check("repeated failures power-cycle USB before rebooting",
          ["reboot"] not in calls and len(offs) == 4 and len(ons) == 4)
    first_on = next(i for i, c in enumerate(calls) if c[-1] == "on")
    check("every hub goes off before any comes back on (the Pi 5's VBUS is shared)",
          all(i < first_on for i, c in enumerate(calls) if c[-1] == "off"))
    check("the radio gets time off and time to come back", sum(slept) >= m.USB_OFF_S + m.USB_SETTLE_S)
    check("then readsb gets one more start", calls[-1] == ["restart", "readsb.service"])

    calls.clear()
    m.check_receiver()
    check("a second cycle inside the interval is refused; the reboot follows", calls == [["reboot"]])
    os.remove(m.LAST_REBOOT)
    os.remove(m.UHUBCTL)
    os.remove(m.USB_CYCLED)

    calls.clear()
    m._write_int(m.RECEIVER_RESTARTS, m.RECEIVER_REBOOT_AFTER)
    m.check_receiver()
    check("without uhubctl, restarts that never help escalate to a reboot", calls == [["reboot"]])

    calls.clear()
    m.check_receiver()
    check("a second reboot inside the interval is refused", calls == [])

    # ---- a radio gone from USB goes straight to the power cycle ---------
    usb = os.path.join(tmp, "usb")
    m.USB_DEVICES = usb
    m.RTL_SEEN = os.path.join(tmp, "net", "rtl-sdr-seen")
    m.UHUBCTL = os.path.join(tmp, "uhubctl")
    open(m.UHUBCTL, "w").close()

    def radio(present):
        dev = os.path.join(usb, "1-2")
        if present:
            os.makedirs(dev, exist_ok=True)
            open(os.path.join(dev, "idVendor"), "w").write("0bda\n")
            open(os.path.join(dev, "idProduct"), "w").write("2838\n")
        elif os.path.isdir(dev):
            for f in os.listdir(dev):
                os.remove(os.path.join(dev, f))
            os.rmdir(dev)
    os.makedirs(usb, exist_ok=True)

    # never seen an RTL radio this boot: the usual order, restart first
    m._write_int(m.RECEIVER_RESTARTS, 0)
    calls.clear()
    m.check_receiver()
    check("an unknown receiver keeps the usual order (restart first)", calls == [["restart", "readsb.service"]])

    # seen while all is well: remembered, even though nothing needed doing
    radio(True)
    stale(1)
    calls.clear()
    m.check_receiver()
    check("a healthy run takes no action", calls == [])
    check("the radio is remembered on a healthy run", os.path.exists(m.RTL_SEEN))

    # still there: data stale for another reason, restart first
    stale(600)
    m._write_int(m.RECEIVER_RESTARTS, 0)
    calls.clear()
    m.check_receiver()
    check("a radio still on USB is restarted, not power-cycled", calls == [["restart", "readsb.service"]])

    # gone: power cycle at once, counted
    radio(False)
    m._write_int(m.RECEIVER_RESTARTS, 0)
    calls.clear()
    m.check_receiver()
    check("a radio gone from USB is power-cycled at once",
          len([c for c in calls if c[-1] == "off"]) == 4 and calls[-1] == ["restart", "readsb.service"])
    check("the fast cycle counts toward the reboot", m._read_int(m.RECEIVER_RESTARTS) == 1)

    # still gone inside the interval: no second cycle; the usual restarts
    calls.clear()
    m.check_receiver()
    check("no second cycle inside the interval; back to restarts", calls == [["restart", "readsb.service"]])
    os.remove(m.UHUBCTL)
    os.remove(m.USB_CYCLED)
    m._write_int(m.RECEIVER_RESTARTS, 0)
    calls.clear()

    # ---- kiosk -----------------------------------------------------------
    os.remove(m.LAST_REBOOT)
    stuck_dir = os.path.join(tmp, "user", "1000")
    os.makedirs(stuck_dir)
    stuck = os.path.join(stuck_dir, "stratoscan-kiosk-stuck")

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
