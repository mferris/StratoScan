#!/usr/bin/env python3
"""WiFi settings survive a power cut (#80, 2026-10-23).

After two sudden power cuts RDU came back with no WiFi: NetworkManager had
rewritten its netplan-backed profile (/etc/netplan/90-NM-<uuid>.yaml) just
after boot, and the cut a minute later left it 0 bytes. The installer now
moves netplan-backed profiles to NetworkManager keyfiles and clears empty YAML,
and the network watchdog raises the setup hotspot at once when no WiFi network
is saved at all, instead of waiting about eight minutes for one to come back.

Run: python3 tests/test_wifi_profiles.py
"""
import importlib.util
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


inst = (ROOT / "deploy" / "install-setup-server.sh").read_text()
block = inst[inst.index("# WiFi profiles as NetworkManager keyfiles"):inst.index("# The phone app finds the radar")]
check("nmcli connection migrate --plugin keyfile" in block
      and "/run/NetworkManager/system-connections/netplan-*" in block,
      "the installer moves netplan-backed profiles to keyfiles")
check("-name '90-NM-*.yaml' -size 0 -delete" in block, "and removes the empty YAML such a loss leaves")

spec = importlib.util.spec_from_file_location("netwatchdog", ROOT / "deploy" / "net-watchdog.py")
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def counting(stdout, rc=0):
    w.run = lambda argv, timeout=45: subprocess.CompletedProcess(argv, rc, stdout.encode(), b"")
    return w.saved_wifi_networks()


check(counting("fr-hotspot:802-11-wireless\nWired connection 1:802-3-ethernet\nlo:loopback\n") == 0,
      "the setup hotspot and wired profiles are not saved WiFi networks")
check(counting("fr-Home\\:Net:802-11-wireless\nfr-hotspot:802-11-wireless\n") == 1,
      "a saved network counts, a colon in its name included")
check(counting("fr-candidate:802-11-wireless\n") == 0, "an unconfirmed candidate doesn't")
check(counting("", rc=1) is None, "nmcli failing means 'don't know', not 'none'")

events, started = [], []
w.os.makedirs = lambda *a, **k: None
w.check_health = lambda: None
w.have_connectivity = lambda *a, **k: False
w.read_failcount = lambda: 0
w.write_failcount = lambda n: None
w.hotspot_active = lambda: False
w.is_claimed = lambda: True
w.os.path.exists = lambda p: False if p == w.PENDING else True
w.touch_runtime = lambda p: None
w.call_setupd = lambda verb, params=None, timeout=120: (started.append(verb), {"ok": True, "result": {"ssid": "StratoScan-Setup"}})[1]
w.saved_wifi_networks = lambda: 0
w.main()
check(started == ["hotspot_start"], "a set-up radar with no saved WiFi raises the hotspot on the first failed check")
started.clear()
w.saved_wifi_networks = lambda: 1
w.main()
check(started == [], "with a saved network it still waits first (a router reboot is not a reason to go to AP mode)")
started.clear()
w.saved_wifi_networks = lambda: None
w.main()
check(started == [], "and when nmcli can't be asked it is patient too")

print("wifi profile checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
