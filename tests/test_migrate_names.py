#!/usr/bin/env python3
"""deploy/migrate-names.sh: moving a unit from 'flightradar' to 'stratoscan'.

Builds a scratch tree laid out like the first unit (RDU) was on 2026-09-30,
runs the script against it with ROOT set, and checks that the data a unit
cannot lose -- its relay key above all -- moved intact, that nothing of the
old names is left running or configured, and that a second run is a no-op.
systemctl, runuser, usermod and groupmod are replaced by recorders on PATH.
"""
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "deploy", "migrate-names.sh")
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def write(root, rel, text="x"):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


def run(root, bindir):
    env = dict(os.environ, ROOT=root, KIOSK_USER="kioskuser",
               PATH=bindir + os.pathsep + os.environ["PATH"])
    return subprocess.run(["sh", SCRIPT], env=env, capture_output=True, text=True)


with tempfile.TemporaryDirectory() as t:
    root = os.path.join(t, "root")
    bindir = os.path.join(t, "bin")
    log = os.path.join(t, "calls.log")
    os.makedirs(bindir)
    for cmd in ("systemctl", "runuser", "usermod", "groupmod"):
        p = os.path.join(bindir, cmd)
        with open(p, "w") as f:
            f.write(f'#!/bin/sh\necho "{cmd} $*" >> "{log}"\n')
        os.chmod(p, 0o755)

    # --- a unit as RDU was laid out -----------------------------------------
    write(root, "opt/flightradar/ota.py", "program")
    write(root, "var/lib/flightradar-relay/unit.key", "THE-UNIT-KEY")
    write(root, "var/lib/flightradar-ota/state.json", '{"serial": 297}')
    write(root, "var/lib/flightradar-setup/setup.json", '{"admin": "hash"}')
    for name in ("sightings", "approaches", "network"):
        write(root, f"var/lib/private/flightradar-{name}/data.json", name)
        os.symlink(f"private/flightradar-{name}", os.path.join(root, f"var/lib/flightradar-{name}"))
    for u in ("flightradar-events.service", "flightradar-ota-auto.timer"):
        write(root, f"etc/systemd/system/{u}", "[Unit]")
    os.makedirs(os.path.join(root, "etc/systemd/system/multi-user.target.wants"))
    os.symlink("../flightradar-events.service",
               os.path.join(root, "etc/systemd/system/multi-user.target.wants/flightradar-events.service"))
    write(root, "home/kioskuser/.config/systemd/user/flightradar-kiosk.service", "[Unit]")
    os.makedirs(os.path.join(root, "home/kioskuser/.config/systemd/user/default.target.wants"))
    os.symlink("../flightradar-kiosk.service",
               os.path.join(root, "home/kioskuser/.config/systemd/user/default.target.wants/flightradar-kiosk.service"))
    for c in ("etc/lighttpd/conf-available/96-flightradar-wake.conf",
              "etc/lighttpd/conf-enabled/96-flightradar-wake.conf",
              "etc/NetworkManager/dnsmasq-shared.d/flightradar-captive.conf",
              "etc/apt/apt.conf.d/52flightradar-unattended-upgrades",
              "etc/sysctl.d/90-flightradar-sysctl.conf",
              "etc/systemd/journald.conf.d/flightradar.conf",
              "etc/ssh/sshd_config.d/10-radome.conf",
              "usr/local/share/tar1090/git/.flightradar-commit"):
        write(root, c)
    write(root, "etc/lighttpd/conf-enabled/10-something-else.conf", "keep me")

    r = run(root, bindir)
    check(r.returncode == 0, f"first run succeeds (exit {r.returncode}) {r.stderr.strip()[:200]}")
    J = lambda rel: os.path.join(root, rel)
    rd = lambda rel: open(J(rel)).read()

    # the data a unit cannot lose
    check(rd("var/lib/stratoscan-relay/unit.key") == "THE-UNIT-KEY", "relay key moved intact (the unit's identity)")
    check(rd("var/lib/stratoscan-ota/state.json") == '{"serial": 297}', "update state moved intact")
    check(rd("var/lib/stratoscan-setup/setup.json") == '{"admin": "hash"}', "setup data moved intact")
    for name in ("sightings", "approaches", "network"):
        check(rd(f"var/lib/private/stratoscan-{name}/data.json") == name, f"private {name} data moved intact")
        check(not os.path.lexists(J(f"var/lib/flightradar-{name}")), f"old /var/lib link for {name} removed")
    check(not any(n.startswith("flightradar") for n in os.listdir(J("var/lib"))), "nothing named flightradar left in /var/lib")

    # programs, and the safety net
    check(rd("opt/stratoscan/ota.py") == "program", "programs moved to /opt/stratoscan")
    check(os.path.islink(J("opt/flightradar")) and os.readlink(J("opt/flightradar")) == "/opt/stratoscan",
          "/opt/flightradar is a link to /opt/stratoscan")

    # old services and config gone; unrelated config untouched
    check(not [n for n in os.listdir(J("etc/systemd/system")) if n.startswith("flightradar")], "old system units removed")
    check(not os.listdir(J("etc/systemd/system/multi-user.target.wants")), "old enablement links removed")
    ud = J("home/kioskuser/.config/systemd/user")
    check(not [n for n in os.listdir(ud) if n.startswith("flightradar")]
          and not os.listdir(os.path.join(ud, "default.target.wants")), "old kiosk user units removed")
    for c in ("etc/lighttpd/conf-available/96-flightradar-wake.conf", "etc/lighttpd/conf-enabled/96-flightradar-wake.conf",
              "etc/NetworkManager/dnsmasq-shared.d/flightradar-captive.conf", "etc/apt/apt.conf.d/52flightradar-unattended-upgrades",
              "etc/sysctl.d/90-flightradar-sysctl.conf", "etc/systemd/journald.conf.d/flightradar.conf",
              "etc/ssh/sshd_config.d/10-radome.conf"):
        check(not os.path.exists(J(c)), f"removed {c}")
    check(rd("etc/lighttpd/conf-enabled/10-something-else.conf") == "keep me", "unrelated config untouched")
    check(os.path.exists(J("usr/local/share/tar1090/git/.stratoscan-commit")), "tar1090 marker renamed")

    calls = open(log).read()
    check("systemctl disable --now flightradar-events.service" in calls, "old services disabled and stopped")
    check("usermod" not in calls, "accounts untouched in a scratch tree (ROOT set)")

    # the backup
    backups = [n for n in os.listdir(J("var/backups")) if n.startswith("stratoscan-rename-")]
    check(len(backups) == 1, "one backup written")
    if backups:
        names = tarfile.open(J("var/backups/" + backups[0])).getnames()
        check("var/lib/flightradar-relay/unit.key" in names, "backup contains the relay key")
        check("var/lib/private/flightradar-sightings/data.json" in names, "backup contains private data")

    # idempotent
    r2 = run(root, bindir)
    check(r2.returncode == 0 and "nothing to move" in r2.stdout, "second run is a no-op")
    check(rd("var/lib/stratoscan-relay/unit.key") == "THE-UNIT-KEY", "relay key still intact after a second run")

    # refuses to guess
    root2 = os.path.join(t, "root2")
    write(root2, "opt/flightradar/a", "old")
    write(root2, "opt/stratoscan/a", "new")
    r3 = run(root2, bindir)
    check(r3.returncode != 0 and open(os.path.join(root2, "opt/stratoscan/a")).read() == "new",
          "refuses when both /opt dirs exist, and changes nothing")

    # fresh install
    root3 = os.path.join(t, "root3")
    os.makedirs(root3)
    r4 = run(root3, bindir)
    check(r4.returncode == 0 and not os.path.exists(os.path.join(root3, "opt")), "fresh install: nothing done")

total = "failed" if fails else "passed"
print(f"migrate-names checks {total}" + (f" ({fails} failed)" if fails else ""))
sys.exit(1 if fails else 0)
