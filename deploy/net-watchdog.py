#!/usr/bin/env python3
"""Keeps a FlightRadar unit reachable no matter what.

Runs every couple of minutes and at boot. Two jobs:

1. RECONCILE an unconfirmed network change. setupd writes pending.json
   (fsynced) before it touches the radio and deletes it on confirm. If a
   pending record is still here, the change was never confirmed -- the new
   network did not work, or the power was cut mid-change -- so it is rolled
   back unconditionally. Without this, a reboot at the wrong moment leaves
   the device on a network that does not work, with no way in.

2. FALL BACK TO A HOTSPOT. If the device has no usable connection, raise
   'FlightRadar-Setup' so someone with a phone can reach the setup page.
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

STATE_DIR = "/var/lib/flightradar-setup"
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
# Deliberately NOT under /run/flightradar: that is flightradar-setupd's
# RuntimeDirectory, so systemd deletes it every time that unit restarts --
# which would silently reset this watchdog's patience counter and, if setupd
# were flapping, mean the escalation below never fired at all. /run is still
# right: a reboot SHOULD start the count over. It just must not be a
# directory whose lifetime belongs to somebody else.
FAILCOUNT = "/run/flightradar-net/failcount"
HOTSPOT_SINCE = "/run/flightradar-net/hotspot-since"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"}
NMCLI = "/usr/bin/nmcli"


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
        s.connect("/run/flightradar/setupd.sock")
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
    fail counter after os.makedirs("/run/flightradar") and swallowed any
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


def main():
    os.makedirs(STATE_DIR, exist_ok=True)

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
