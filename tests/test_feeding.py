#!/usr/bin/env python3
"""
Checks for deploy/feeding.py (opt-in FlightAware feeding).

It runs as root and installs third-party software on a unit in someone
else's house, so what matters is what it must never do: install a second
decoder that fights readsb for the SDR, leave FlightAware able to update the
unit remotely, open network listeners, install a repository package that
doesn't match the pinned hash, or carry a previous owner's feeder id over an
erase. No network or root needed: every command is intercepted.

Run: python3 tests/test_feeding.py
"""
import importlib.util
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
failures, checks = [], 0


def check(label, cond):
    global checks
    checks += 1
    if not cond:
        failures.append(label)


tmp = tempfile.mkdtemp()
os.environ["STRATOSCAN_FEEDING_STATE"] = os.path.join(tmp, "state")
spec = importlib.util.spec_from_file_location("feeding", os.path.join(HERE, "..", "deploy", "feeding.py"))
fd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fd)
fd.FEEDER_ID_FILE = os.path.join(tmp, "feeder_id")

# ---- the settings themselves ------------------------------------------------
settings = dict(fd.PIAWARE_SETTINGS)
check("PiAware relays readsb's feed instead of decoding", settings["receiver-type"] == "relay")
check("it reads readsb locally", settings["receiver-host"] == "127.0.0.1" and settings["receiver-port"] == "30005")
check("FlightAware cannot update the unit automatically", settings["allow-auto-updates"] == "no")
check("or on request", settings["allow-manual-updates"] == "no")
check("MLAT results go only to readsb, locally",
      settings["mlat-results-format"] == "beast,connect,127.0.0.1:30104")
check("no extra listening ports are opened", "listen" not in settings["mlat-results-format"])

# ---- installation -----------------------------------------------------------
calls = []
installed = {"piaware": False}


class R:
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def fake_run(argv, timeout=600):
    calls.append(argv)
    if argv[:2] == ["dpkg-query", "-W"]:
        return R(0 if installed["piaware"] else 1, "install ok installed" if installed["piaware"] else "")
    if argv[:2] == ["apt-get", "install"]:
        installed["piaware"] = True
    if argv[:2] == ["systemctl", "is-active"]:
        return R(0, "active")
    return R()


fd.run = fake_run
good = open(os.path.join(HERE, "..", "tests", "test_feeding.py"), "rb").read()  # any bytes


def serve(data):
    """Make the next download return `data`."""
    ctx = io.BytesIO(data)
    ctx.read = lambda n=-1, d=data: d
    ctx.__enter__ = lambda s=ctx: s
    fd.urllib.request.urlopen = lambda req, timeout=60, c=ctx: c


# A download that doesn't match the pinned hash must not be installed.
serve(b"not the real package")
check("a tampered repository package is refused", fd.enable() == 1)
check("and nothing was installed", not any(c[:2] == ["dpkg", "-i"] for c in calls))
prog = fd.status()["flightaware"]["progress"]
check("the failure is reported to the setup page", prog and prog["ok"] is False and "hash" in prog["detail"])

# The genuine package (by hash): installs, without FlightAware's decoder.
calls.clear()
fd.REPO_DEB_SHA256 = __import__("hashlib").sha256(good).hexdigest()
serve(good)
check("a matching package installs", fd.enable() == 0)
installs = [c for c in calls if c[:2] == ["apt-get", "install"]]
check("PiAware is installed", installs and "piaware" in installs[0])
check("without recommended packages (dump1090-fa)", installs and "--no-install-recommends" in installs[0])
check("dump1090-fa is never named", not any("dump1090-fa" in " ".join(c) for c in calls))
configured = [c[1:] for c in calls if c and c[0] == "piaware-config"]
check("every setting is applied", all([n, v] in configured for n, v in fd.PIAWARE_SETTINGS))
check("and PiAware is started", ["systemctl", "enable", "--now", "piaware.service"] in calls)

# Already installed: no second install.
calls.clear()
fd.enable()
check("an installed PiAware is only reconfigured", not any(c[:2] == ["apt-get", "install"] for c in calls))

# ---- erase --------------------------------------------------------------------
with open(fd.FEEDER_ID_FILE, "w") as f:
    f.write("11111111-2222-3333-4444-555555555555")
check("the claim link is offered once there is a feeder id",
      fd.status()["flightaware"]["claimUrl"].endswith("11111111-2222-3333-4444-555555555555"))
calls.clear()
fd.reset()
check("erase stops feeding", ["systemctl", "disable", "--now", "piaware.service"] in calls)
check("erase forgets the feeder id", not os.path.exists(fd.FEEDER_ID_FILE))
check("and clears it in PiAware's own config", ["piaware-config", "feeder-id", ""] in calls)

print(f"{checks - len(failures)}/{checks} feeding checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
