#!/usr/bin/env python3
"""What keeps the SD card's writes down, so a unit lasts a decade (2026-10-14).

Measured on RDU over 15 minutes with no monitoring logins: 1.85 GB/day, from
the journal (~60 KB of writes per log line, as its indexes are updated all
over its file), Chromium's profile, the sighting store, lighttpd's temporary
files and ext4's own journal. Each measure below took a share of that; none
may quietly come undone.

Run: python3 tests/test_card_writes.py
"""
import contextlib
import importlib.util
import io
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


kiosk = (D / "stratoscan-kiosk.service").read_text()
start = next(l for l in kiosk.splitlines() if l.startswith("ExecStart="))
check("--disk-cache-dir=%t/" in start, "the browser's HTTP cache is in RAM")
check("--disable-gpu-shader-disk-cache" in start, "and it keeps no shader cache on the card")
check("--disable-extensions" in start, "and runs no extensions (Pi OS's ad blocker rewrote its store)")

up = (D / "87-stratoscan-uploads.conf").read_text()
check(re.search(r'^server\.upload-dirs := \( "/run/lighttpd" \)$', up, re.M) is not None,
      "lighttpd's temporary files are in RAM (/run/lighttpd, made by Debian at boot)")
inst = (D / "install-setup-server.sh").read_text()
check("87-stratoscan-uploads.conf" in inst.split("for c in 85-stratoscan-tls.conf")[1].split("done")[0],
      "and the installer enables that")

ss = (D / "sighting-store.py").read_text()
m = re.search(r"^FLUSH_INTERVAL = (\d+)$", ss, re.M)
check(m and int(m.group(1)) >= 1800, "the sighting history is saved at most every 30 minutes")
check('json.dump(store, f, separators=(",", ":"))' in ss, "in compact JSON")

wake = (D / "wake-listener.py").read_text()
check("nothing to do" not in wake, "an alert while the panel is already on is not logged")

spec = importlib.util.spec_from_file_location("setup_server", D / "setup-server.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
H = next(v for v in vars(mod).values() if isinstance(v, type) and "log_request" in v.__dict__)
h = H.__new__(H)
logged = []
for cmd, path, code in (("GET", "/setup/api/hello", 200), ("HEAD", "/setup/", 304),
                        ("GET", "/setup/api/status?k=secret", 403), ("POST", "/setup/api/wifi?psk=secret", 200)):
    h.command, h.path, h.requestline = cmd, path, f"{cmd} {path} HTTP/1.1"
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        h.log_request(code)
    logged.append(out.getvalue())
check(logged[0] == "" and logged[1] == "", "the setup server does not log routine reads (/setup/api/hello: 30 in 15 minutes)")
check(logged[2] == "setup GET /setup/api/status\n" and logged[3] == "setup POST /setup/api/wifi\n",
      "but still logs failures and changes, without their query strings")

osu = (D / "os-update.py").read_text()
promote = osu.split("def promote(")[1].split("\ndef ")[0]
check("prune_kernels(state)" in promote, "a kept kernel removes the older ones (~190 MB each)")
apt = (D / "20auto-upgrades").read_text()
check('APT::Periodic::AutocleanInterval "7";' in apt, "old .debs leave apt's cache weekly")

print("card write checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
