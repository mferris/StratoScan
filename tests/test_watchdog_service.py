#!/usr/bin/env python3
"""The network watchdog is one long-running service with its own cadence
(security review 2026-10-04, item 4), not a systemd timer that logged three
lines every two minutes: the timer is gone, the installer removes it from
older units, and an update restarts the service so new code runs."""
import os
import re
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
D = os.path.join(ROOT, "deploy")
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


svc = open(os.path.join(D, "stratoscan-netwatchdog.service"), encoding="utf-8").read()
check("Type=simple" in svc and "--loop" in svc and "Restart=always" in svc, "the service runs net-watchdog.py --loop for good")
check("WantedBy=multi-user.target" in svc, "and is enabled at boot")
check(not os.path.exists(os.path.join(D, "stratoscan-netwatchdog.timer")), "no timer file ships")
inst = open(os.path.join(D, "install-setup-server.sh"), encoding="utf-8").read()
check("disable --now stratoscan-netwatchdog.timer" in inst and "rm -f /etc/systemd/system/stratoscan-netwatchdog.timer" in inst,
      "the installer removes the timer from an older unit")
check("stratoscan-netwatchdog.service" in inst.split("== enabling ==")[1], "and enables the service")
ota = open(os.path.join(D, "ota.py"), encoding="utf-8").read()
check(re.search(r'"net-watchdog\.py":\s*\("system", "stratoscan-netwatchdog\.service"\)', ota), "an update restarts the service")
src = open(os.path.join(D, "net-watchdog.py"), encoding="utf-8").read()
check("def loop():" in src and 'loop() if "--loop" in sys.argv[1:] else main()' in src, "net-watchdog.py has the loop, and the one-shot form for the tests")
check("LOOP_S = 120" in src and "BOOT_DELAY_S = 45" in src, "the old timer's cadence is kept")
# A run must still be a plain one-shot without the flag (the existing tests rely on it).
r = subprocess.run([sys.executable, "-c", "import ast,sys; ast.parse(open(sys.argv[1]).read())", os.path.join(D, "net-watchdog.py")])
check(r.returncode == 0, "net-watchdog.py parses")
print("watchdog service checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
