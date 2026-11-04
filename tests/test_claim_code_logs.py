#!/usr/bin/env python3
"""The claim code stays out of logs (security review 2026-11-03, SR-55).

First boot sent the installer's output to /var/log/stratoscan-firstboot.log
under the default umask, so every user could read it, and the installer
ended by printing the claim code. Now first boot's log is root's alone (a
new one and one left by an earlier attempt), the installer prints the code
only to a terminal, and a re-run fixes an old log's mode.

Both scripts are run here with stand-ins for what they call, in a scratch
directory.

Run: python3 tests/test_claim_code_logs.py
"""
import os
import pathlib
import re
import stat
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIRSTBOOT = (ROOT / "image" / "firstboot.sh").read_text()
INSTALLER = (ROOT / "deploy" / "install-setup-server.sh").read_text()
CODE = "K7Q2XM"
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


def stubs(d):
    b = d / "bin"
    b.mkdir()
    for name in ("raspi-config", "rfkill", "systemctl", "hostname"):
        (b / name).write_text("#!/bin/sh\necho 192.168.1.23\n" if name == "hostname" else "#!/bin/sh\nexit 0\n")
        (b / name).chmod(0o755)
    return b


def mode(p):
    return stat.S_IMODE(os.stat(p).st_mode)


for leftover in (False, True):
    d = pathlib.Path(tempfile.mkdtemp())
    b = stubs(d)
    log = d / "firstboot.log"
    if leftover:
        log.write_text("an earlier attempt\n")
        log.chmod(0o644)
    src = d / "src"
    (src / "deploy").mkdir(parents=True)
    # The installer stand-in prints the code, as the real one did at its end.
    (src / "deploy" / "install-setup-server.sh").write_text(f"echo 'Claim code:'\necho {CODE}\n")
    script = (FIRSTBOOT.replace("/var/log/stratoscan-firstboot.log", str(log))
              .replace("/opt/stratoscan-src", str(src))
              .replace("/var/lib/stratoscan-firstboot.done", str(d / "done")))
    (d / "firstboot.sh").write_text(script)
    env = dict(os.environ, PATH=f"{b}:{os.environ['PATH']}")
    p = subprocess.run(["sh", str(d / "firstboot.sh")], env=env, capture_output=True, text=True,
                       timeout=60, preexec_fn=lambda: os.umask(0o022))
    what = "an earlier attempt's log" if leftover else "a new log"
    check(p.returncode == 0 and log.exists(), f"first boot runs ({what})")
    check(log.exists() and mode(log) & 0o077 == 0,
          f"first boot: {what} is readable by root alone (mode {oct(mode(log)) if log.exists() else '-'})")

# The installer's last lines, run as first boot runs them (output to a file)
# and as a person runs them (at a terminal, which script(1) stands in for).
tail = INSTALLER[INSTALLER.rindex('echo "Setup page:'):]
d = pathlib.Path(tempfile.mkdtemp())
b = stubs(d)
(d / "claim-code").write_text(CODE + "\n")
(d / "tail.sh").write_text(tail.replace("/run/stratoscan/claim-code", str(d / "claim-code")))
env = dict(os.environ, PATH=f"{b}:{os.environ['PATH']}")
out = d / "out.log"
with open(out, "w") as f:
    subprocess.run(["sh", str(d / "tail.sh")], env=env, stdout=f, stderr=subprocess.STDOUT, timeout=30)
check(CODE not in out.read_text(), "the installer doesn't write the claim code into a log")
check("screen" in out.read_text(), "it says where the code is instead")
if sys.platform == "darwin":
    tty = ["script", "-q", "/dev/null", "sh", str(d / "tail.sh")]
else:
    tty = ["script", "-qec", f"sh {d / 'tail.sh'}", "/dev/null"]
try:
    p = subprocess.run(tty, env=env, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
    check(CODE in p.stdout, "a person at a terminal still sees it")
except (OSError, subprocess.SubprocessError):
    print("skip a terminal to try the installer at")

check(re.search(r"chmod 0600 /var/log/stratoscan-firstboot\.log", INSTALLER),
      "a re-run of the installer closes an old first-boot log")

print("claim code log checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
