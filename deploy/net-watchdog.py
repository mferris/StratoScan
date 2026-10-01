#!/usr/bin/env python3
"""Keeps a StratoScan unit reachable no matter what.

Runs every couple of minutes and at boot. It is also the one root process on
a timer that updates can reach, so it carries the last-resort health checks
too -- see check_health() -- which a unit ten years into someone else's house
has no other way to get. Networking jobs:

1. RECONCILE an unconfirmed network change. setupd writes pending.json
   (fsynced) before it touches the radio and deletes it on confirm. If a
   pending record is still here, the change was never confirmed -- the new
   network did not work, or the power was cut mid-change -- so it is rolled
   back unconditionally. Without this, a reboot at the wrong moment leaves
   the device on a network that does not work, with no way in.

2. FALL BACK TO A HOTSPOT. If the device has no usable connection, raise
   'StratoScan-Setup' so someone with a phone can reach the setup page.
   This is the entire first-run story for a recipient: a device fresh out of
   the box has no credentials for their WiFi and they have no SSH.

The hotspot ALTERNATES rather than latching: concurrent AP+STA is unreliable
on this chipset, and a unit that camps in AP mode after a brief router
reboot never rejoins on its own. So it retries the real networks between AP
periods.
"""
import json
import os
import subprocess
import sys
import time

STATE_DIR = "/var/lib/stratoscan-setup"
PENDING = os.path.join(STATE_DIR, "pending.json")
HOTSPOT_PROFILE = "fr-hotspot"
AP_PERIOD_S = 300          # how long to hold the AP up before retrying real networks
# How many consecutive failed checks before touching the radio, for a unit
# that is already set up. At the timer's 120s cadence that is a reconnect at
# ~4 minutes and the AP at ~8. The old code went straight to AP mode on the
# FIRST failed check, and that check was a single ping with a 3s timeout --
# so one lost packet during a mesh roam or an AP reboot was enough to take a
# working radar off the network until someone power-cycled it. Confirmed on
# this receiver: fr-hotspot's NetworkManager timestamp showed the AP being
# raised while the WiFi was healthy (-47dBm, 0/60 packet loss).
#
# An UNCLAIMED unit keeps the old fast path. It has no network to lose, and
# its whole first-run story is the AP coming up promptly for someone holding
# a phone in front of a radar they just unboxed.
REPAIR_AFTER_FAILS = 2     # try reconnecting wlan0
AP_AFTER_FAILS = 4         # only then fall back to the setup hotspot
# Deliberately NOT under /run/stratoscan: that is stratoscan-setupd's
# RuntimeDirectory, so systemd deletes it every time that unit restarts --
# which would silently reset this watchdog's patience counter and, if setupd
# were flapping, mean the escalation below never fired at all. /run is still
# right: a reboot SHOULD start the count over. It just must not be a
# directory whose lifetime belongs to somebody else.
FAILCOUNT = "/run/stratoscan-net/failcount"
HOTSPOT_SINCE = "/run/stratoscan-net/hotspot-since"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"}
NMCLI = "/usr/bin/nmcli"
SYSTEMCTL = "/usr/bin/systemctl"

# ---- Last-resort health checks -------------------------------------------
# readsb rewrites this every second whether or not anything is in the sky, so
# a stale file means the receiver is wedged (SDR stick hung, USB glitch), not
# a quiet night. The service can stay "active" through that, so systemd's
# Restart= never fires and the screen says NO RECEIVER forever.
AIRCRAFT_JSON = "/run/readsb/aircraft.json"
RECEIVER_STALE_S = 180
RECEIVER_BOOT_GRACE_S = 300
RECEIVER_RESTARTS = "/run/stratoscan-net/receiver-restarts"
RECEIVER_REBOOT_AFTER = 3          # restarts that did not bring data back
# A radio whose chip has hung (seen on RDU 2026-09-28: the FlyCatcher stopped
# answering USB) needs its power cut. A Pi 5 reboot does NOT cut USB power, so
# rebooting alone left it hung. The Pi 5's four onboard hubs share one VBUS
# switch: it only goes off when every hub's ports are off (uhubctl README).
UHUBCTL = "/usr/sbin/uhubctl"
USB_HUBS = ("1", "2", "3", "4")
USB_CYCLED = "/run/stratoscan-net/usb-power-cycled"
MIN_USB_CYCLE_INTERVAL_S = 30 * 60
USB_OFF_S = 3
USB_SETTLE_S = 6
# When the radio has dropped off USB altogether (RDU 2026-09-30, a loose
# connector: "Cannot enable. Maybe the USB cable is bad?"), restarting readsb
# can't help -- there is nothing for it to open -- and three restarts two
# minutes apart cost about seven minutes of NO SIGNAL before the power cycle
# that does. So a radio that is missing goes straight to the power cycle.
# Only RTL2832U radios (the FlyCatcher, FlightAware's Pro Stick) are
# recognised, and only on a unit where one has been seen since boot: a unit
# with some other receiver keeps the usual order.
USB_DEVICES = "/sys/bus/usb/devices"
RTL_SDR_IDS = {("0bda", "2832"), ("0bda", "2838")}
RTL_SEEN = "/run/stratoscan-net/rtl-sdr-seen"
sleep = time.sleep                 # patched by the tests
# wake-listener.py (the frozen-display watchdog) runs as the desktop user and
# can only restart the browser. It counts restarts that did not bring a
# painted frame back and leaves the count here; past the limit the fault is
# below Chromium (compositor, GPU driver) and only a reboot clears it.
KIOSK_STUCK_GLOB = "/run/user/*/stratoscan-kiosk-stuck"
# The count includes the restart just issued, so 4 means three restarts each
# had their full 15 minutes to bring a frame back and none did.
KIOSK_REBOOT_AFTER = 4
# However broken things are, never reboot more often than this: a fault a
# reboot cannot fix (a missing SDR stick) must degrade to "reboots a few
# times a day", not a loop that makes the unit unusable.
LAST_REBOOT = os.path.join(STATE_DIR, "last-watchdog-reboot")
OFFLINE_MAP = "/opt/stratoscan/offline-map.py"
HEARTBEAT = "/opt/stratoscan/heartbeat.py"
NOTABLE_DB = "/opt/stratoscan/notable-db.py"
MIN_REBOOT_INTERVAL_S = 6 * 3600


def run(argv, timeout=45):
    try:
        return subprocess.run(argv, env=ENV, timeout=timeout,
                              capture_output=True, shell=False)
    except Exception:
        return subprocess.CompletedProcess(argv, 1, b"", b"timeout")


def call_setupd(verb, params=None, timeout=120):
    import socket
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect("/run/stratoscan/setupd.sock")
        s.sendall((json.dumps({"verb": verb, "params": params or {}}) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            c = s.recv(65536)
            if not c:
                break
            buf += c
        return json.loads(buf or b'{"ok":false}')
    except Exception as e:
        return {"ok": False, "code": "unreachable", "detail": str(e)[:80]}
    finally:
        s.close()


def is_claimed():
    """Has anyone finished setting this unit up?

    Read directly rather than asked of the web tier: this runs at boot, when
    that service may not be listening yet.
    """
    try:
        with open(os.path.join(STATE_DIR, "setup.json")) as f:
            return bool(json.load(f).get("claimed"))
    except Exception:
        return False    # unreadable or absent => treat as not yet set up


def hotspot_active():
    p = run([NMCLI, "-t", "-f", "NAME", "connection", "show", "--active"], timeout=15)
    return HOTSPOT_PROFILE in p.stdout.decode("utf-8", "replace")


def probe_once():
    """One look at whether this device has a working connection.

    NetworkManager reports 'activated' for an association with no DHCP lease,
    which looks connected and is unreachable -- so require an address and a
    reachable gateway before believing it.
    """
    p = run([NMCLI, "-t", "-f", "IP4.ADDRESS", "device", "show", "wlan0"], timeout=15)
    if b"/" not in p.stdout:
        # wifi may legitimately be down if the unit is on ethernet
        e = run([NMCLI, "-t", "-f", "IP4.ADDRESS", "device", "show", "eth0"], timeout=15)
        if b"/" not in e.stdout:
            return False
    g = run([NMCLI, "-t", "-f", "IP4.GATEWAY", "device", "show", "wlan0"], timeout=15)
    gw = g.stdout.decode().strip().split(":", 1)[-1]
    if not gw:
        g = run([NMCLI, "-t", "-f", "IP4.GATEWAY", "device", "show", "eth0"], timeout=15)
        gw = g.stdout.decode().strip().split(":", 1)[-1]
    if not gw:
        return False
    if run(["/bin/ping", "-c", "2", "-W", "3", gw], timeout=12).returncode == 0:
        return True
    # Second opinion before calling it down: NetworkManager runs its own
    # connectivity check, and a gateway that ignores ping (or is mid-roam)
    # is not the same thing as no network.
    c = run([NMCLI, "-t", "-f", "CONNECTIVITY", "general"], timeout=15)
    return c.stdout.decode("utf-8", "replace").strip() in ("full", "limited", "portal")


def have_connectivity(attempts=3, gap=4):
    """probe_once, retried -- a dropped packet is not an outage.

    WiFi loses frames for entirely ordinary reasons: a mesh steering the
    client to another AP, a channel scan, the router rebooting. Every one of
    those recovers on its own within seconds. Deciding from a single probe
    that the network is gone is what made this watchdog the cause of the
    outages it exists to prevent.
    """
    for i in range(attempts):
        if probe_once():
            return True
        if i < attempts - 1:
            time.sleep(gap)
    return False


def read_failcount():
    try:
        with open(FAILCOUNT) as f:
            return int(f.read().strip() or 0)
    except Exception:
        return 0        # absent (fresh boot) or unreadable => no failures yet


def touch_runtime(path):
    """Write a marker under /run, creating the directory if it is not there.

    Derived from the path rather than hardcoded: an earlier version wrote the
    fail counter after os.makedirs("/run/stratoscan") and swallowed any
    error, so on a system where that directory was missing the counter never
    incremented -- and a claimed unit that had genuinely lost its network
    would have sat at "1 failed check" forever and never fallen back to the
    hotspot. Silent, and only visible in the case you least want it.
    """
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    open(path, "w").close()
    return path


def write_failcount(n):
    try:
        d = os.path.dirname(FAILCOUNT)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(FAILCOUNT, "w") as f:
            f.write(str(n))
    except Exception as e:
        print(f"net-watchdog: could not record fail count: {e}", flush=True)


def retry_known_networks():
    """Bring the hotspot down and let NetworkManager try the real profiles."""
    run([NMCLI, "connection", "down", HOTSPOT_PROFILE], timeout=30)
    run([NMCLI, "device", "disconnect", "wlan0"], timeout=30)
    time.sleep(2)
    run([NMCLI, "device", "connect", "wlan0"], timeout=60)
    time.sleep(12)
    return have_connectivity()


def _uptime():
    with open("/proc/uptime") as f:
        return float(f.read().split()[0])


def _read_int(path):
    try:
        with open(path) as f:
            return int(f.read().strip() or 0)
    except Exception:
        return 0


def _write_int(path, n):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(str(n))


def watchdog_reboot(reason):
    try:
        last = os.path.getmtime(LAST_REBOOT)
    except OSError:
        last = 0
    if time.time() - last < MIN_REBOOT_INTERVAL_S:
        print(f"health: would reboot ({reason}) but rebooted recently; holding",
              flush=True)
        return
    print(f"health: rebooting -- {reason}", flush=True)
    touch_runtime(LAST_REBOOT)
    run([SYSTEMCTL, "reboot"], timeout=30)


def power_cycle_usb():
    """Cut power to every USB port for a few seconds. True if it was done.

    Everything on USB drops briefly (the radio, and a USB touchscreen or
    keyboard if there is one), which is why this comes after readsb restarts
    and is rate-limited. It is still far lighter than a reboot, and unlike a
    reboot it actually resets a hung radio.
    """
    if not os.path.exists(UHUBCTL):
        return False
    try:
        if time.time() - os.path.getmtime(USB_CYCLED) < MIN_USB_CYCLE_INTERVAL_S:
            return False
    except OSError:
        pass
    touch_runtime(USB_CYCLED)
    for hub in USB_HUBS:
        run([UHUBCTL, "-l", hub, "-a", "off"], timeout=20)
    sleep(USB_OFF_S)
    for hub in USB_HUBS:
        run([UHUBCTL, "-l", hub, "-a", "on"], timeout=20)
    sleep(USB_SETTLE_S)            # let the radio enumerate before readsb opens it
    return True


def rtl_sdr_present():
    """True if an RTL2832U radio is on USB now."""
    try:
        for dev in os.listdir(USB_DEVICES):
            try:
                with open(os.path.join(USB_DEVICES, dev, "idVendor")) as f:
                    vendor = f.read().strip()
                with open(os.path.join(USB_DEVICES, dev, "idProduct")) as f:
                    product = f.read().strip()
            except OSError:
                continue
            if (vendor, product) in RTL_SDR_IDS:
                return True
    except OSError:
        pass
    return False


def radio_missing():
    """True only when an RTL radio was here earlier this boot and is gone now."""
    if rtl_sdr_present():
        touch_runtime(RTL_SEEN)
        return False
    return os.path.exists(RTL_SEEN)


def check_receiver():
    if _uptime() < RECEIVER_BOOT_GRACE_S:
        return
    try:
        age = time.time() - os.path.getmtime(AIRCRAFT_JSON)
    except OSError:
        age = float("inf")
    if age < RECEIVER_STALE_S:
        if _read_int(RECEIVER_RESTARTS):
            print("health: receiver data flowing again", flush=True)
            _write_int(RECEIVER_RESTARTS, 0)
        return
    what = "missing" if age == float("inf") else f"stale for {int(age)}s"
    restarts = _read_int(RECEIVER_RESTARTS)
    if radio_missing() and power_cycle_usb():
        # Counted like a restart, so a cycle that doesn't bring it back still
        # escalates (the next cycle is rate-limited; the reboot follows).
        _write_int(RECEIVER_RESTARTS, restarts + 1)
        print(f"health: receiver data {what} and the radio is gone from USB; "
              "power-cycled USB", flush=True)
        run([SYSTEMCTL, "restart", "readsb.service"], timeout=60)
        return
    if restarts >= RECEIVER_REBOOT_AFTER:
        if power_cycle_usb():
            # One more readsb start on a freshly powered radio; if data is
            # still missing next time, the cycle is rate-limited and the
            # reboot below follows.
            print(f"health: receiver data {what} after {restarts} readsb restarts; "
                  "power-cycled USB", flush=True)
            run([SYSTEMCTL, "restart", "readsb.service"], timeout=60)
            return
        watchdog_reboot(f"receiver data {what} after {restarts} readsb restarts")
        return
    print(f"health: receiver data {what}; restarting readsb", flush=True)
    _write_int(RECEIVER_RESTARTS, restarts + 1)
    run([SYSTEMCTL, "restart", "readsb.service"], timeout=60)


def check_kiosk():
    import glob
    for path in glob.glob(KIOSK_STUCK_GLOB):
        stuck = _read_int(path)
        if stuck >= KIOSK_REBOOT_AFTER:
            watchdog_reboot(f"display frozen through {stuck} browser restarts")
            return


def check_health():
    # Independent of each other and of the networking below: a bug or an
    # odd state in one must never stop the unit staying reachable.
    for check in (check_receiver, check_kiosk):
        try:
            check()
        except Exception as e:
            print(f"health: {check.__name__} failed ({type(e).__name__}: {e})",
                  flush=True)


def maybe_build_offline_map():
    """Start an offline-map build if the stored one is wrong or missing.

    setupd starts one whenever the location changes, but that can fail -- a
    unit set up from the hotspot has no internet yet -- and a unit that was
    located before this feature existed has none at all. The decision is
    offline-map.py's own needs_build(), so the two can never disagree; it is
    cheap (two small files) and backs off for hours after a failed build.
    The build itself runs in its own transient unit so this watchdog is never
    held up by a download, and systemd refuses a second one while it runs.
    """
    if not os.path.exists(OFFLINE_MAP):
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("offline_map", OFFLINE_MAP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if mod.needs_build() is None:
        return
    print("health: offline map missing or out of date; building", flush=True)
    run(["systemd-run", "--quiet", "--collect", "--unit", "stratoscan-offline-map",
         "--property=Type=oneshot", "--property=Nice=10",
         "/usr/bin/python3", OFFLINE_MAP, "ensure"], timeout=30)


def maybe_refresh_notable_db():
    """Weekly refresh of the notable-aircraft list, in its own transient unit.

    notable-db.py decides whether it is due (and backs off after a failure);
    the download never holds up this watchdog.
    """
    if not os.path.exists(NOTABLE_DB):
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("notable_db", NOTABLE_DB)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not mod.needs_refresh():
        return
    run(["systemd-run", "--quiet", "--collect", "--unit", "stratoscan-notable-db",
         "--property=Type=oneshot", "--property=Nice=10",
         "/usr/bin/python3", NOTABLE_DB, "ensure"], timeout=30)


def maybe_send_health_report():
    """Opt-in health report to the maintainer's relay, when one is due.

    heartbeat.py decides (enabled? relay configured? due?) and does nothing
    otherwise. A 10 s cap on the request keeps a slow relay from ever holding
    up this watchdog's real job.
    """
    if not os.path.exists(HEARTBEAT):
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("heartbeat", HEARTBEAT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    line = mod.maybe_send()
    if line:
        print(f"health: {line}", flush=True)


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    check_health()

    # 1. roll back anything left unconfirmed
    if os.path.exists(PENDING):
        try:
            with open(PENDING) as f:
                pend = json.load(f)
        except Exception:
            pend = {"ssid": "?"}
        print(f"net-watchdog: unconfirmed change to {pend.get('ssid')!r}; rolling back",
              flush=True)
        call_setupd("wifi_rollback")

    # 2. keep the device reachable
    if have_connectivity():
        write_failcount(0)
        try:
            maybe_build_offline_map()
        except Exception as e:
            print(f"health: offline map check failed ({type(e).__name__}: {e})",
                  flush=True)
        try:
            maybe_refresh_notable_db()
        except Exception as e:
            print(f"health: notable list check failed ({type(e).__name__}: {e})",
                  flush=True)
        try:
            maybe_send_health_report()
        except Exception as e:
            print(f"health: health report failed ({type(e).__name__}: {e})",
                  flush=True)
        # An UNCLAIMED unit keeps its setup network up even when it has
        # connectivity by some other route. Plugging in an ethernet cable
        # otherwise tore the hotspot down mid-setup, stranding whoever was
        # part-way through configuring it from a phone. Once the unit is
        # claimed, setup is finished and the AP is just an open door.
        if hotspot_active() and is_claimed():
            print("net-watchdog: setup complete and online; dropping the hotspot",
                  flush=True)
            call_setupd("hotspot_stop")
        return 0

    fails = read_failcount() + 1
    write_failcount(fails)
    print(f"net-watchdog: no connectivity (consecutive failed checks: {fails})",
          flush=True)

    if hotspot_active():
        # Alternate: give the real networks another chance rather than
        # camping in AP mode forever after a transient router outage.
        age = time.time() - os.path.getmtime(HOTSPOT_SINCE) \
            if os.path.exists(HOTSPOT_SINCE) else AP_PERIOD_S + 1
        if age > AP_PERIOD_S:
            print("net-watchdog: retrying known networks", flush=True)
            if retry_known_networks():
                call_setupd("hotspot_stop")
                return 0
            touch_runtime(HOTSPOT_SINCE)
            call_setupd("hotspot_start")
        return 0

    # A unit nobody has set up yet has no connection to lose, so it keeps the
    # original behaviour: raise the AP at once, because someone is very
    # probably standing in front of it with a phone waiting for exactly that.
    # A CLAIMED unit is the opposite case -- it had a working network a moment
    # ago, and going to AP mode takes it off that network and hides it from
    # its owner. Give the connection a chance to come back, then try to repair
    # it, and only fall back to the AP once the outage has clearly persisted.
    if is_claimed():
        if fails < REPAIR_AFTER_FAILS:
            print("net-watchdog: waiting to see if this recovers on its own",
                  flush=True)
            return 0
        if fails < AP_AFTER_FAILS:
            print("net-watchdog: reconnecting wlan0", flush=True)
            if retry_known_networks():
                print("net-watchdog: reconnected", flush=True)
                write_failcount(0)
                return 0
            return 0

    print("net-watchdog: no connectivity; raising the setup hotspot", flush=True)
    r = call_setupd("hotspot_start")
    if r.get("ok"):
        touch_runtime(HOTSPOT_SINCE)
        print(f"net-watchdog: hotspot up as {r['result'].get('ssid')}", flush=True)
    else:
        print(f"net-watchdog: could not raise hotspot: {r.get('code')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
