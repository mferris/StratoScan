#!/usr/bin/env python3
"""
Opt-in feeding to FlightAware, for the unit's owner.

Sharing this antenna's data with FlightAware earns the owner a free
FlightAware Enterprise account for as long as it feeds. It is opt-in from
the setup page, because feeding also shares the antenna's exact location
with FlightAware (needed for multilateration, and set in the owner's own
FlightAware account).

PiAware (github.com/flightaware/piaware, BSD-2-Clause) is installed from
FlightAware's own apt repository, whose bootstrap package is pinned by hash
below. It is configured to read the feed readsb already produces (relay on
127.0.0.1:30005) and to hand multilateration results back to readsb on
127.0.0.1:30104, so the radar is untouched:
  - FlightAware's decoder (dump1090-fa) is never installed: it would fight
    readsb for the SDR stick. Hence --no-install-recommends.
  - PiAware's remote auto/manual update features are switched off. A gifted
    unit changes only through this project's signed updates.
  - Its default extra listening ports (30105/30106, on every interface) are
    not opened: results go only to readsb, locally.

Flightradar24's feeder is closed-source and signs up through an interactive
questionnaire meant for a person, so it is not automated here; the setup
page links to FR24's own instructions instead.

  feeding.py status                  JSON state (for setupd)
  feeding.py enable-flightaware      install if needed, configure, start
  feeding.py disable-flightaware     stop and disable
  feeding.py reset                   disable and forget the feeder id (erase)
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

REPO_DEB_URL = ("https://www.flightaware.com/adsb/piaware/files/packages/pool/piaware/"
                "f/flightaware-apt-repository/flightaware-apt-repository_1.3_all.deb")
REPO_DEB_SHA256 = "20bdb73536845d9d95bc4659973e7ed07bc0fbdda7491045b82a66d5361046cc"
FEEDER_ID_FILE = "/var/cache/piaware/feeder_id"
CLAIM_URL = "https://www.flightaware.com/adsb/piaware/claim/"
STATE_DIR = os.environ.get("FLIGHTRADAR_FEEDING_STATE", "/run/flightradar-feeding")
PROGRESS = os.path.join(STATE_DIR, "progress.json")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "DEBIAN_FRONTEND": "noninteractive"}

# name -> value. Everything PiAware needs to relay rather than decode.
PIAWARE_SETTINGS = [
    ("receiver-type", "relay"),
    ("receiver-host", "127.0.0.1"),
    ("receiver-port", "30005"),
    ("allow-mlat", "yes"),
    ("mlat-results", "yes"),
    ("mlat-results-format", "beast,connect,127.0.0.1:30104"),
    ("allow-auto-updates", "no"),
    ("allow-manual-updates", "no"),
]


def run(argv, timeout=600):
    return subprocess.run(argv, env=ENV, timeout=timeout, capture_output=True, text=True)


def progress(step, ok=True, detail=""):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(PROGRESS, "w") as f:
        json.dump({"step": step, "ok": ok, "detail": detail[:300], "at": int(time.time())}, f)


def piaware_installed():
    r = run(["dpkg-query", "-W", "-f=${Status}", "piaware"], timeout=30)
    return r.returncode == 0 and "install ok installed" in r.stdout


def install_piaware():
    progress("downloading FlightAware's repository package")
    with urllib.request.urlopen(urllib.request.Request(
            REPO_DEB_URL, headers={"User-Agent": "Radome/1.0"}), timeout=60) as r:
        data = r.read(1_000_000)
    got = hashlib.sha256(data).hexdigest()
    if got != REPO_DEB_SHA256:
        raise RuntimeError(f"repository package hash mismatch ({got[:12]}…); refusing to install")
    with tempfile.NamedTemporaryFile(suffix=".deb", delete=False) as f:
        f.write(data)
        deb = f.name
    try:
        r = run(["dpkg", "-i", deb], timeout=120)
        if r.returncode:
            raise RuntimeError("could not add FlightAware's repository: " + r.stderr[-200:])
    finally:
        os.unlink(deb)
    progress("updating package lists")
    run(["apt-get", "update", "-q"], timeout=300)
    progress("installing PiAware")
    r = run(["apt-get", "install", "-y", "-q", "--no-install-recommends", "piaware"], timeout=900)
    if r.returncode:
        raise RuntimeError("PiAware did not install: " + r.stderr[-200:])


def configure():
    for name, value in PIAWARE_SETTINGS:
        r = run(["piaware-config", name, value], timeout=30)
        if r.returncode:
            raise RuntimeError(f"piaware-config {name} failed: {r.stderr[-120:]}")


def enable():
    try:
        if not piaware_installed():
            install_piaware()
        progress("configuring PiAware to read this radar's feed")
        configure()
        progress("starting PiAware")
        run(["systemctl", "enable", "--now", "piaware.service"], timeout=60)
        run(["systemctl", "restart", "piaware.service"], timeout=60)
        progress("done")
        return 0
    except Exception as e:
        progress("failed", ok=False, detail=str(e))
        return 1


def disable():
    run(["systemctl", "disable", "--now", "piaware.service"], timeout=60)
    progress("stopped")
    return 0


def reset():
    """For "Erase everything": the feeder id belongs to the previous owner's
    FlightAware account, so the next owner must get a fresh one."""
    disable()
    if piaware_installed():
        run(["piaware-config", "feeder-id", ""], timeout=30)
    try:
        os.unlink(FEEDER_ID_FILE)
    except OSError:
        pass
    try:
        os.unlink(PROGRESS)
    except OSError:
        pass
    return 0


def status():
    installed = piaware_installed()
    active = installed and run(["systemctl", "is-active", "piaware.service"], timeout=15).stdout.strip() == "active"
    feeder = None
    try:
        with open(FEEDER_ID_FILE) as f:
            feeder = f.read().strip() or None
    except OSError:
        pass
    try:
        with open(PROGRESS) as f:
            prog = json.load(f)
    except (OSError, ValueError):
        prog = None
    return {
        "flightaware": {
            "installed": installed,
            "active": active,
            "feederId": feeder,
            "claimUrl": CLAIM_URL + feeder if feeder else None,
            "progress": prog,
        },
    }


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        print(json.dumps(status()))
        return 0
    if cmd == "enable-flightaware":
        return enable()
    if cmd == "disable-flightaware":
        return disable()
    if cmd == "reset":
        return reset()
    print("usage: feeding.py status|enable-flightaware|disable-flightaware|reset", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
