#!/usr/bin/env python3
"""The network watchdog reads other users' directories carefully (2026-11-15).

net-watchdog.py runs as root, every two minutes, for good. It read
setup.json and pending.json from the web tier's directory, the display
watchdog's count from the desktop user's, and (through offline-map.py)
receiver.json from readsb's -- each by name, following links, with no limit.
A link there to /dev/zero was read until the unit ran out of memory, and the
marker that stops it rebooting too often sat where the web tier could
replace it with a link to a busy file (no reboot ever again) or remove it
(no brake).

Now: a plain file only, never through a link, a bounded size; and the
reboot brake is a file of root's own in a directory only root writes. The
old marker is looked at once, when that file is first made, and believed
only if the watchdog itself could have left it before the last reboot; it
is never part of a later decision, so nothing the web tier keeps touching
at its name can hold a reboot back.

Run: python3 tests/test_net_watchdog_reads.py
"""
import importlib.util
import json
import os
import pathlib
import stat
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / "deploy" / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


w = load("netwd_reads", "net-watchdog.py")
tmp = pathlib.Path(tempfile.mkdtemp())
state, own, elsewhere = tmp / "web-tier", tmp / "own", tmp / "elsewhere"
for p in (state, elsewhere):
    p.mkdir()
w.STATE_DIR = str(state)
w.PENDING = str(state / "pending.json")
w.LAST_REBOOT = str(own / "last-watchdog-reboot")
w.LAST_REBOOT_OLD = str(state / "last-watchdog-reboot")
ZERO = "/dev/zero"          # never ends: reading it by name is the hang and the memory

# ---- read_small ---------------------------------------------------------------------
f = state / "plain"
f.write_text("hello\n")
check(w.read_small(str(f)) == "hello\n", "a plain file is read")
check(w.read_small(str(state / "absent")) is None, "an absent one is None")
secret = elsewhere / "roots-own"
secret.write_text("root's own file\n")
os.symlink(secret, state / "link")
check(w.read_small(str(state / "link")) is None, "a link to another file is not followed")
os.symlink(ZERO, state / "zero")
check(w.read_small(str(state / "zero")) is None, "a link to /dev/zero is not followed")
os.link(secret, state / "second-name")
check(w.read_small(str(state / "second-name")) is None, "a second name for a file elsewhere is not read")
os.mkfifo(state / "fifo")
check(w.read_small(str(state / "fifo")) is None, "a pipe nobody writes is not waited on")
(state / "dir").mkdir()
check(w.read_small(str(state / "dir")) is None, "a directory is not read")
big = state / "big"
big.write_bytes(b"x" * 70000)
check(w.read_small(str(big)) is None and w.read_small(str(big), 70000) == "x" * 70000,
      "a file over the limit is refused whole, not read in part")
(state / "binary").write_bytes(b"\xff\xfe")
check(w.read_small(str(state / "binary")) is None, "bytes that are not text are None")

# ---- is the unit set up? ------------------------------------------------------------
setup = state / "setup.json"
check(w.is_claimed() is False, "no setup.json: not set up")
setup.write_text(json.dumps({"schema": 1, "claimed": True, "password": {"hash": "x" * 200}}))
check(w.is_claimed() is True, "a set-up unit reads as set up")
setup.write_text(json.dumps({"claimed": False}))
check(w.is_claimed() is False, "one not yet set up reads as not")
setup.write_text("{not json")
check(w.is_claimed() is False, "a damaged file reads as not set up, as before")
setup.write_text("[1, 2]")
check(w.is_claimed() is False, "so does one that is not a record")
setup.unlink()
os.symlink(ZERO, setup)
check(w.is_claimed() is False, "a link to /dev/zero at its name returns at once")
setup.unlink()
claimed_elsewhere = elsewhere / "setup.json"
claimed_elsewhere.write_text('{"claimed": true}')
os.symlink(claimed_elsewhere, setup)
check(w.is_claimed() is False, "a link to some other file's answer is not believed")
setup.unlink()

# ---- small counters -----------------------------------------------------------------
n = state / "count"
n.write_text("4\n")
check(w._read_int(str(n)) == 4, "a count is read")
n.write_text("")
check(w._read_int(str(n)) == 0, "an empty one is 0")
n.write_text("9" * 500)
check(w._read_int(str(n)) == 0, "one too long to be a count is 0")
n.unlink()
os.symlink(ZERO, n)
check(w._read_int(str(n)) == 0, "a link to /dev/zero is 0, at once")
w._write_int(str(tmp / "net" / "restarts"), 3)
check(w._read_int(str(tmp / "net" / "restarts")) == 3, "the watchdog's own counters still read back")

stuck = tmp / "user" / "1000"
stuck.mkdir(parents=True)
w.KIOSK_STUCK_GLOB = str(tmp / "user" / "*" / "stratoscan-kiosk-stuck")
rebooted = []
w.watchdog_reboot = lambda reason: rebooted.append(reason)
os.symlink(ZERO, stuck / "stratoscan-kiosk-stuck")
w.check_kiosk()
check(rebooted == [], "a link where the frozen-display count goes is no count")
(stuck / "stratoscan-kiosk-stuck").unlink()
(stuck / "stratoscan-kiosk-stuck").write_text(str(w.KIOSK_REBOOT_AFTER))
w.check_kiosk()
check(len(rebooted) == 1, "the real count still leads to the reboot")

# ---- the reboot brake ---------------------------------------------------------------
w = load("netwd_brake", "net-watchdog.py")
check(not w.LAST_REBOOT.startswith(w.STATE_DIR + "/") and w.LAST_REBOOT.startswith("/var/lib/stratoscan-net/"),
      "the brake's marker is not in the web tier's directory")
check(w.LAST_REBOOT_OLD == os.path.join(w.STATE_DIR, "last-watchdog-reboot"), "the old marker's place is unchanged for its readers")
hb = (ROOT / "deploy" / "heartbeat.py").read_text()
check('_age("%s")' % w.LAST_REBOOT_OLD in hb, "which the health report still reads, so it is still kept up")
w.LAST_REBOOT = str(own / "last-watchdog-reboot")
w.LAST_REBOOT_OLD = str(state / "last-watchdog-reboot")
ran = []
w.run = lambda argv, timeout=45: ran.append(argv[1:])
UP = 1800.0                             # this boot was half an hour ago
w._uptime = lambda: UP
new = own / "last-watchdog-reboot"
old = state / "last-watchdog-reboot"
before_boot = time.time() - UP - 600    # ten minutes before this boot
long_ago = time.time() - w.MIN_REBOOT_INTERVAL_S - 60


def reboots():
    ran.clear()
    w.watchdog_reboot("test")
    return ran == [["reboot"]]


def start_over(old_mode=None, old_time=None):
    """No marker of the watchdog's own yet: the one moment the old one counts."""
    for p in (new, old):
        if p.is_symlink() or p.exists():
            p.unlink()
    if old_mode is not None:
        old.write_text("")
        old.chmod(old_mode)
        os.utime(old, (old_time, old_time))


check(reboots(), "with no marker at all, a reboot goes ahead")
check(new.is_file() and old.is_file() and not old.is_symlink(),
      "and both markers are touched: the brake, and the old one for the health report")
check(stat.S_IMODE(old.stat().st_mode) == 0o644, "the old one as the watchdog always made it, 0644")
check(not reboots(), "a second reboot straight after is held")
os.utime(new, (long_ago, long_ago))
os.utime(old, (long_ago, long_ago))
check(reboots(), "six hours on, a reboot goes ahead")

# a unit that rebooted just before this version arrived: the old marker counts, once
start_over(0o644, before_boot)
check(not reboots(), "with no marker of its own yet, the old one (root's, 0644, from before this boot) holds a reboot")
check(new.is_file() and abs(new.stat().st_mtime - before_boot) < 2, "and the watchdog's own marker is made with that time")
start_over(0o600, before_boot)
check(not reboots(), "a stricter mode than 0644 counts the same")
os.utime(new, (long_ago, long_ago))
os.utime(old, None)
check(reboots(), "after that only the watchdog's own marker is the brake: a just-touched old one holds nothing")

# the reviewer's scenario: STATE_DIR is group-writable and not sticky, so the web
# tier renames a file of root's that its group can write to the old marker's
# name and touches it every few hours
for label, at in (("before the watchdog has a marker of its own", None), ("once it has one", long_ago)):
    start_over()
    if at is not None:
        new.write_text("")
        os.utime(new, (at, at))
    theirs = state / "pending.json"
    theirs.write_text("{}")
    theirs.chmod(0o660)
    os.rename(theirs, old)
    held = []
    for hours in (0, 3, 6, 9):          # touched again and again; a fault wants a reboot each time
        os.utime(old, None)
        went = reboots()
        held.append(not went)
        if went:                        # the reboot happened; six hours pass before the next fault
            os.utime(new, (long_ago, long_ago))
            os.remove(old)
            theirs.write_text("{}")
            theirs.chmod(0o660)
            os.rename(theirs, old)
    check(held == [False] * 4,
          "a group-writable file of root's renamed to the old marker's name and kept touched never holds a reboot (%s)" % label)

# each thing that makes the old marker not the watchdog's own leaving
for label, mode, at in (("group-writable", 0o664, before_boot), ("other-writable", 0o646, before_boot),
                        ("executable", 0o744, before_boot), ("setuid", 0o4644, before_boot),
                        ("touched since this boot", 0o644, time.time() - 60),
                        ("dated in the future", 0o644, time.time() + 3600),
                        ("dated at the epoch", 0o644, 0)):
    start_over(mode, at)
    check(w._old_marker_time() == 0 and reboots(), "an old marker that is %s is not believed" % label)
start_over(0o644, before_boot)
real_euid = os.geteuid
os.geteuid = lambda: real_euid() + 1
try:
    check(w._old_marker_time() == 0, "nor one that is not root's own")
finally:
    os.geteuid = real_euid
start_over(0o644, before_boot)
os.link(old, elsewhere / "second-name-for-marker")
check(w._old_marker_time() == 0 and reboots(), "nor one with a second name")
start_over(0o644, before_boot)


def no_uptime():
    raise OSError("no /proc/uptime")


w._uptime = no_uptime
check(w._old_marker_time() == 0 and reboots(), "nor any, when this boot's time can't be read")
w._uptime = lambda: UP

# the web tier removes the old marker: the brake holds
check(not reboots(), "straight after that reboot, another is held")
old.unlink()
check(not reboots(), "and removing the old marker does not take the brake off")

# the web tier leaves a link to a busy file: recovery is not disarmed
busy = elsewhere / "busy"
busy.write_text("touched all the time\n")
for label, at in (("before the watchdog has a marker of its own", None), ("once it has one", long_ago)):
    start_over()
    if at is not None:
        new.write_text("")
        os.utime(new, (at, at))
    os.symlink(busy, old)
    check(reboots(), "a link at the old marker's name to a just-touched file does not hold a reboot back (%s)" % label)
    check(busy.read_text() == "touched all the time\n" and old.is_file() and not old.is_symlink(),
          "   and the link is replaced, not written through")

# a second name for a busy file elsewhere
os.utime(new, (long_ago, long_ago))
old.unlink()
os.link(busy, old)
check(reboots(), "nor does a second name for one")
check(busy.read_text() == "touched all the time\n" and os.stat(old).st_nlink == 1,
      "and that file is not emptied through its second name")

# the old place can't be written: the reboot still happens
w.LAST_REBOOT_OLD = str(elsewhere / "busy" / "under-a-file")
os.utime(new, (long_ago, long_ago))
check(reboots(), "the old marker being unwritable does not stop a reboot")

# the brake itself can't be written: no reboot, as before (never a loop)
w.LAST_REBOOT = str(elsewhere / "busy" / "under-a-file")
w.LAST_REBOOT_OLD = str(state / "gone")
try:
    went = reboots()
except OSError:
    went = False
check(not went, "if the brake can't be recorded there is no reboot, as before")

# ---- an unconfirmed change ----------------------------------------------------------
w = load("netwd_pending", "net-watchdog.py")
w.STATE_DIR = str(state)
w.PENDING = str(state / "pending.json")
verbs, lines = [], []
w.check_health = lambda: None
w.have_connectivity = lambda *a, **k: True
w.write_failcount = lambda n: None
w.maybe_build_offline_map = w.maybe_refresh_notable_db = lambda: None
w.maybe_send_health_report = w.maybe_check_public_address = lambda: None
w.hotspot_active = lambda: False
w.call_setupd = lambda verb, params=None, timeout=120: (verbs.append(verb), {"ok": True, "result": {}})[1]
w.print = lambda *a, **k: lines.append(" ".join(map(str, a)))
pend = state / "pending.json"


def run_once():
    verbs.clear()
    lines.clear()
    started = time.time()
    w.main()
    return time.time() - started


run_once()
check(verbs == [], "no pending record: nothing is rolled back")
pend.write_text(json.dumps({"kind": "wifi", "ssid": "Home WiFi"}))
run_once()
check(verbs == ["wifi_rollback"] and "'Home WiFi'" in lines[0], "an unconfirmed change is rolled back, and named in the journal")
pend.write_text("{half a rec")
run_once()
check(verbs == ["wifi_rollback"] and "'?'" in lines[0], "a damaged record is rolled back all the same")
pend.unlink()
os.symlink(ZERO, pend)
took = run_once()
check(verbs == ["wifi_rollback"] and took < 5, "a link to /dev/zero there is rolled back without being read")
pend.unlink()
os.symlink(state / "nowhere", pend)
run_once()
check(verbs == ["wifi_rollback"], "so is a link to nothing (setupd removes whatever is at the name)")
pend.unlink()
pend.write_text(json.dumps({"ssid": "x" * 5000}))
run_once()
check(verbs == ["wifi_rollback"] and len(lines[0]) < 200, "a long name in the record can't flood the journal")
pend.unlink()

# ---- offline-map's look at readsb's directory ---------------------------------------
om = load("offline_map_reads", "offline-map.py")
recv = tmp / "receiver.json"
om.RECEIVER_JSON = str(recv)
recv.write_text(json.dumps({"lat": 35.8776, "lon": -78.7875, "version": "readsb"}))
check(om.receiver_location() == (35.8776, -78.7875), "the receiver's position is read from a plain file")
recv.unlink()
for label, target in (("/dev/zero", ZERO), ("another file", None)):
    if target is None:
        other = elsewhere / "receiver.json"
        other.write_text(json.dumps({"lat": 35.8776, "lon": -78.7875}))
        target = other
    os.symlink(target, recv)
    try:
        om.receiver_location()
        raised = False
    except OSError:
        raised = True
    check(raised, "a link to %s at its name is not followed" % label)
    started = time.time()
    check(om.needs_build() is None and om.needs_runways() is None and time.time() - started < 5,
          "   and the map check reads that as no location yet, at once")
    recv.unlink()
recv.write_text('{"lat": 35.8776, "lon": -78.7875, "pad": "' + "x" * 70000 + '"}')
check(om.needs_build() is None, "a receiver.json far larger than readsb writes is not taken in")
recv.unlink()
os.mkfifo(recv)
check(om.needs_build() is None, "a pipe there is not waited on")

# ---- the source: no bare open() left on those names ---------------------------------
src = (ROOT / "deploy" / "net-watchdog.py").read_text()
check("open(PENDING)" not in src and 'open(os.path.join(STATE_DIR, "setup.json"))' not in src
      and "os.path.getmtime(LAST_REBOOT)" not in src,
      "net-watchdog no longer opens setup.json or pending.json by name, or stats the marker through a link")
body = src[src.index("def watchdog_reboot("):src.index("def power_cycle_usb(")]
check(src.count("_old_marker_time()") == 2 and "LAST_REBOOT_OLD" not in body.split("print(f\"health: rebooting")[0],
      "the old marker is looked at in one place, where the watchdog's own is first made, and never in the decision")

print("watchdog read checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
