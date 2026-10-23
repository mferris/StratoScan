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

fs = inst.split("ROOT_LINE=")[1].split("\nfi\n")[0]
check(",lazytime,commit=60" in fs and "mount -o remount,lazytime,commit=60 /" in fs,
      "the installer mounts the root filesystem lazytime,commit=60 (ext4's journal batched)")
check("findmnt --verify" in fs and "^(Success|0 parse errors)" in fs
      and "fstab.stratoscan-orig" in fs and "commit=" in fs.split("then")[0],
      "keeping the original fstab, leaving one with commit= alone, and undoing a result findmnt cannot parse")

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

guard = (D / "shm-guard.sh").read_text()
unit = (D / "stratoscan-shmguard.service").read_text()
check("LogLevelMax=notice" in unit,
      "the five-minute shared-memory guard's start and finish lines stay out of the journal")
says = re.findall(r'echo "([^"]*)shm-guard:', guard)
check(says and all(p == "<5>" for p in says), "while every line it logs goes out at notice, so it is kept")
check('"$STATE/last-log"' in guard.split("below thresholds")[0][-600:],
      "and its all's-well line is written once an hour, not every five minutes")

core = (D / "core-feed.py").read_text()
m = re.search(r"^UAT_IDLE_S = (\d+)$", core, re.M)
check(m and int(m.group(1)) >= 3600 and "s.settimeout(UAT_IDLE_S)" in core,
      "the core feed stays connected to a quiet 978 decoder (each reconnect logged two lines)")

osu = (D / "os-update.py").read_text()
promote = osu.split("def promote(")[1].split("\ndef ")[0]
check("prune_kernels(state)" in promote, "a kept kernel removes the older ones (~190 MB each)")
apt = (D / "20auto-upgrades").read_text()
check('APT::Periodic::AutocleanInterval "7";' in apt, "old .debs leave apt's cache weekly")

# ---- round three (#78, 2026-10-23): over half of RDU's journal lines were chatter
check("--log-level=3" in start,
      "the browser logs only fatal messages (~340 'CompositorAnimationObserver' error lines a day)")
saver = (D / "stratoscan-screensaver.service").read_text()
check(re.search(r"^LogLevelMax=notice$", saver, re.M) and re.search(r"^SyslogLevel=warning$", saver, re.M),
      "the screensaver's restarts on alert wakes stay out of the journal (four manager lines each), "
      "while its own output is raised to warning so it still gets through")
ts = (D / "tailscaled-quiet.conf").read_text()
check(re.search(r"^LogFilterPatterns=~\^magicsock:$", ts, re.M) is not None,
      "tailscaled's 'magicsock:' chatter is filtered out (system unit; LogFilterPatterns)")
check("deploy/tailscaled-quiet.conf /etc/systemd/system/tailscaled.service.d/stratoscan-quiet.conf" in inst,
      "and the installer puts that drop-in in place")
ev = (D / "events.py").read_text()
check("print(f\"events: {e['kind']}" not in ev
      and "sent = collections.Counter(f\"{e['kind']} {e.get('flight') or e['hex']}\" for e in batch)" in ev,
      "phone alerts log one line per send, naming each aircraft, not a line per alert as well")

print("card write checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
