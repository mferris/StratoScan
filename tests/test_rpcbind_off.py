#!/usr/bin/env python3
"""rpcbind is off on every radar (2026-10-26, #89).

rpcbind listened on port 111 on every interface of RDU: Raspberry Pi OS
installs it with nfs-common, and nothing on a radar uses NFS. The installer
stops, disables and masks rpcbind.socket and rpcbind.service, and leaves the
packages, since nfs-common depends on rpcbind.

This runs the installer's step against a stand-in systemctl that records what
it is asked and keeps each unit's state: on a radar with rpcbind, one
without, one where systemctl refuses, and inside the image build.

Run: python3 tests/test_rpcbind_off.py
"""
import os
import pathlib
import re
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


inst = (ROOT / "deploy" / "install-setup-server.sh").read_text()
m = re.search(r"^if systemctl list-unit-files [^\n]*rpcbind[^\n]*; then\n.*?\nfi\n", inst, re.S | re.M)
check(m is not None, "the installer has a step that turns rpcbind off")
step = m.group(0) if m else "false\n"
live = re.search(r"^live\(\) \{[^\n]*\}$", inst, re.M).group(0)
check(m is not None and inst.index("sh deploy/trim-os.sh") < m.start() < inst.index("== the kiosk"),
      "among the unused OS services, after trim-os.sh")
check("rpcbind.socket rpcbind.service" in step.split("\n")[0],
      "guarded: it asks systemctl whether rpcbind's units exist first")
check(not re.search(r"apt-get[^\n]*\b(remove|purge|autoremove)\b|dpkg[^\n]*(\s-r\b|\s-P\b|--remove|--purge)", inst),
      "and removes no package (nfs-common depends on rpcbind)")

# The stand-in: each unit's state is a file (enabled or masked), and a running
# one has a .active file. "fail" makes every change refused, as systemctl does
# without permission; "installed" says rpcbind is there at all.
SYSTEMCTL = r"""#!/bin/sh
echo "$*" >> "$STATE/calls"
case "$1" in
  list-unit-files)
    [ -f "$STATE/installed" ] || exit 1
    for a; do
      case "$a" in rpcbind.*) printf '%s %s enabled\n' "$a" "$(cat "$STATE/$a")" ;; esac
    done
    exit 0 ;;
esac
if [ -f "$STATE/fail" ]; then echo "Failed to $1 $2: Access denied" >&2; exit 1; fi
case "$1" in
  stop) rm -f "$STATE/$2.active" ;;
  disable) [ "$(cat "$STATE/$2")" = masked ] || echo disabled > "$STATE/$2" ;;
  mask) echo masked > "$STATE/$2"; echo "Created symlink /etc/systemd/system/$2 -> /dev/null." >&2 ;;
esac
"""
UNITS = ("rpcbind.socket", "rpcbind.service")


def radar(d, installed=True, fail=False):
    state = pathlib.Path(d) / "state"
    state.mkdir()
    if installed:
        (state / "installed").touch()
        for u in UNITS:
            (state / u).write_text("enabled\n")
            (state / f"{u}.active").touch()
    if fail:
        (state / "fail").touch()
    bin_ = pathlib.Path(d) / "bin"
    bin_.mkdir()
    (bin_ / "systemctl").write_text(SYSTEMCTL)
    os.chmod(bin_ / "systemctl", 0o755)
    return state, dict(os.environ, STATE=str(state), PATH=f"{bin_}:{os.environ['PATH']}")


def run(env, chroot="0"):
    # As the installer runs it: under set -e, with its own live().
    return subprocess.run(["sh", "-ec", f"CHROOT={chroot}\n{live}\n{step}"], env=env,
                          capture_output=True, text=True, timeout=20)


def states(state):
    return {u: ((state / u).read_text().strip(), (state / f"{u}.active").exists()) for u in UNITS}


def calls(state):
    p = state / "calls"
    return p.read_text().splitlines() if p.exists() else []


with tempfile.TemporaryDirectory() as d:
    state, env = radar(d)
    first = run(env)
    after = states(state)
    check(first.returncode == 0, "a radar with rpcbind: the step runs cleanly")
    check(after == {u: ("masked", False) for u in UNITS}, "both rpcbind.socket and rpcbind.service end stopped and masked")
    did = calls(state)
    check(all(f"{v} {u}" in did for u in UNITS for v in ("stop", "disable", "mask")),
          "each is stopped, disabled and masked")
    check("stop rpcbind.socket" in did and did.index("stop rpcbind.socket") < did.index("stop rpcbind.service"),
          "the socket is stopped before the service, so it cannot start it again")
    check(first.stdout.count("rpcbind off") == 1 and "Created symlink" not in first.stdout + first.stderr,
          "it says so in one line, and systemctl's own chatter stays out of the install log")
    (state / "calls").unlink(missing_ok=True)
    second = run(env)
    check(second.returncode == 0 and states(state) == after and second.stdout == first.stdout,
          "run again (every re-run of the installer), it changes nothing and still succeeds")
    check(not any(c.split()[0] in ("enable", "start", "unmask") for c in calls(state)),
          "and never turns rpcbind back on")

with tempfile.TemporaryDirectory() as d:
    state, env = radar(d, installed=False)
    r = run(env)
    check(r.returncode == 0 and r.stdout == "" and r.stderr == "",
          "a radar without rpcbind: nothing to do, and nothing said")
    check([c.split()[0] for c in calls(state)] == ["list-unit-files"], "it only asks, and masks nothing that isn't there")

with tempfile.TemporaryDirectory() as d:
    state, env = radar(d, fail=True)
    r = run(env)
    check(r.returncode == 0, "systemctl refusing every change does not fail the install")

with tempfile.TemporaryDirectory() as d:
    state, env = radar(d)
    r = run(env, chroot="1")
    did = calls(state)
    check(r.returncode == 0 and not any(c.startswith("stop ") for c in did)
          and all(f"{v} {u}" in did for u in UNITS for v in ("disable", "mask")),
          "building the factory image: nothing is stopped (nothing runs), but both are disabled and masked")

# The factory image runs this installer (in the build, then live at first
# boot), so the image needs no step of its own.
custom = (ROOT / "image" / "customize.sh").read_text()
first_boot = (ROOT / "image" / "firstboot.sh").read_text()
check("STRATOSCAN_CHROOT=1" in custom and "sh deploy/install-setup-server.sh" in custom
      and "sh deploy/install-setup-server.sh" in first_boot,
      "the factory image gets it from the installer, in the build and again at first boot")

print("rpcbind checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
