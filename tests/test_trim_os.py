#!/usr/bin/env python3
"""The installer turns off what a radar never uses, and keeps what it does
(2026-10-13). Run against a temporary root: no systemctl is touched.

Run: python3 tests/test_trim_os.py
"""
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
script = (ROOT / "deploy" / "trim-os.sh").read_text()
inst = (ROOT / "deploy" / "install-setup-server.sh").read_text()
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


units = script.split('SYSTEM_UNITS="')[1].split('"')[0].split() + script.split('USER_UNITS="')[1].split('"')[0].split()
for u in ("bluetooth.service", "cups.service", "cups.socket", "wayvnc-control.service", "udisks2.service",
          "upower.service", "nfs-blkmap.service", "rpcbind.socket", "rpcbind.service", "mpris-proxy.service",
          "gvfs-daemon.service"):
    check(u in units, f"turns off {u}")
NEEDED = ("avahi", "pipewire", "wireplumber", "xdg-desktop-portal", "readsb", "tar1090", "lighttpd", "tailscale",
          "NetworkManager", "wpa_supplicant", "ssh", "fail2ban", "timesyncd", "unattended", "cron", "getty",
          "stratoscan", "lightdm", "dbus", "journald", "polkit", "accounts-daemon")
for n in NEEDED:
    check(not any(n in u for u in units), f"keeps {n}")

# a dry run against a temporary root: cloud-init and the Bluetooth overlay
with tempfile.TemporaryDirectory() as d:
    (pathlib.Path(d) / "boot" / "firmware").mkdir(parents=True)
    cfg = pathlib.Path(d) / "boot" / "firmware" / "config.txt"
    cfg.write_text("dtparam=audio=on\n")
    fake = pathlib.Path(d) / "bin"
    fake.mkdir()
    (fake / "systemctl").write_text("#!/bin/sh\nexit 0\n")
    os.chmod(fake / "systemctl", 0o755)
    env = dict(os.environ, STRATOSCAN_ROOT=d, PATH=f"{fake}:{os.environ['PATH']}")
    for _ in range(2):
        r = subprocess.run(["sh", str(ROOT / "deploy" / "trim-os.sh")], env=env, capture_output=True, text=True)
    check(r.returncode == 0, "runs cleanly, twice")
    check((pathlib.Path(d) / "etc" / "cloud" / "cloud-init.disabled").exists(), "cloud-init is disabled")
    check(cfg.read_text().count("dtoverlay=disable-bt") == 1, "the Bluetooth radio is off from the next boot, added once")
    check(cfg.read_text().startswith("dtparam=audio=on"), "the rest of config.txt is untouched")

check('sh deploy/trim-os.sh' in inst and inst.index("trim-os.sh") > inst.index("quiet-boot.sh"),
      "the installer runs it")
check("STRATOSCAN_LIVE=0 sh deploy/trim-os.sh" in inst, "and doesn't try to stop services when building an image")

# rpcbind (port 111, #89): its socket goes before its service, or stopping the
# service leaves the socket to start it again; and nothing is uninstalled,
# since nfs-common depends on it.
check(units.index("rpcbind.socket") < units.index("rpcbind.service"), "rpcbind's socket is turned off before its service")
check(not any(w in script for w in ("apt-get remove", "apt-get purge", "apt remove", "apt purge", "dpkg -r", "dpkg -P")),
      "it removes no packages")

# PackageKit (security review 2026-11-03, SR-12): masked, so the Pi OS package
# tools have no root service to ask. The radar's own updates must not need it:
# os-update.py and the daily security updates run apt and dpkg themselves.
for u in ("packagekit.service", "packagekit-offline-update.service"):
    check(u in script.split('SYSTEM_UNITS="')[1].split('"')[0].split(), f"turns off {u}")
for f in sorted((ROOT / "deploy").iterdir()):
    if f.suffix in (".py", ".sh", ".service", ".timer") and f.name != "trim-os.sh":
        text = f.read_text().lower()
        uses = [w for w in ("pkcon", "pkexec", "org.freedesktop.packagekit", "gui-pkinst", "gui-updater", "rp-prefapps")
                if w in text and f.name != "install-setup-server.sh"]
        check(not uses, f"{f.name} does not rely on PackageKit or the Pi OS package tools")
osu = (ROOT / "deploy" / "os-update.py").read_text()
check('["apt-get", "install"' in osu and '["dpkg", "-i"' in osu and "packagekit" not in osu.lower(),
      "os-update.py installs and puts back the held packages with apt and dpkg alone")
uu = (ROOT / "deploy" / "52stratoscan-unattended-upgrades").read_text() + (ROOT / "deploy" / "20auto-upgrades").read_text()
check("packagekit" not in uu.lower(), "the daily security updates are apt's own, not PackageKit's")
build = (ROOT / "image" / "build.sh").read_text()
check("packagekit.service" in build.split("is not masked")[0].split("for u in ")[-1], "the factory image is checked for the mask")
print("trim os checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
