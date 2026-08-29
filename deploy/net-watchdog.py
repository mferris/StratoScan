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


def hotspot_active():
    p = run([NMCLI, "-t", "-f", "NAME", "connection", "show", "--active"], timeout=15)
    return HOTSPOT_PROFILE in p.stdout.decode("utf-8", "replace")


def have_connectivity():
    """A real connection, not merely an associated radio.

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
    return run(["/bin/ping", "-c", "1", "-W", "3", gw], timeout=10).returncode == 0


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
        if hotspot_active():
            print("net-watchdog: connectivity restored; dropping the hotspot", flush=True)
            call_setupd("hotspot_stop")
        return 0

    if hotspot_active():
        # Alternate: give the real networks another chance rather than
        # camping in AP mode forever after a transient router outage.
        age = time.time() - os.path.getmtime("/run/flightradar/hotspot-since") \
            if os.path.exists("/run/flightradar/hotspot-since") else AP_PERIOD_S + 1
        if age > AP_PERIOD_S:
            print("net-watchdog: retrying known networks", flush=True)
            if retry_known_networks():
                call_setupd("hotspot_stop")
                return 0
            open("/run/flightradar/hotspot-since", "w").close()
            call_setupd("hotspot_start")
        return 0

    print("net-watchdog: no connectivity; raising the setup hotspot", flush=True)
    r = call_setupd("hotspot_start")
    if r.get("ok"):
        open("/run/flightradar/hotspot-since", "w").close()
        print(f"net-watchdog: hotspot up as {r['result'].get('ssid')}", flush=True)
    else:
        print(f"net-watchdog: could not raise hotspot: {r.get('code')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
