#!/usr/bin/env python3
"""The setup server's sign-in throttle is per address (security review
2026-10-04, item 2): a device failing on purpose slows itself down, not the
owner on another device; a global backstop still slows everyone once a crowd
of addresses fails together; and nothing locks for good."""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ss", root / "deploy" / "setup-server.py")
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)

fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


ss.STATE_DIR = tempfile.mkdtemp()
clock = [1_000_000.0]
ss.time.time = lambda: clock[0]
ss._fail.clear()
ss._fail_all.update(count=0, until=0.0, window=clock[0], last=clock[0])

ATTACKER, OWNER = "192.168.1.50", "192.168.1.23"
for _ in range(8):
    ss.note_failure(ATTACKER)
check(ss.throttled(ATTACKER), "eight failures throttle that address")
check(not ss.throttled(OWNER), "another address is not throttled by them")
ss.note_success(OWNER)
check(not ss.throttled(OWNER), "the owner signs in while the attacker waits")

clock[0] += 20 * 60
check(not ss.throttled(ATTACKER), "the attacker's wait ends on its own (20 min later)")
check(ATTACKER not in ss._fail, "and a quiet address is forgotten")

# The backstop: many addresses failing together slow every newcomer, briefly,
# but never an address that has signed in before: a neighbour with a crowd of
# addresses must not keep the owner out (security review 2026-11-03, SR-25).
NEWCOMER = "192.168.1.77"
for i in range(ss.FAIL_ALL_LIMIT):
    ss.note_failure("10.0.0.%d" % (i % 200))
check(ss.throttled(NEWCOMER), "%d failures across addresses slow an address never seen to sign in" % ss.FAIL_ALL_LIMIT)
check(not ss.throttled(OWNER), "but not the owner's device, which has signed in before")
clock[0] += ss.FAIL_ALL_DELAY_S + 1
check(not ss.throttled(NEWCOMER), "for %d s only" % ss.FAIL_ALL_DELAY_S)
clock[0] += ss.GOOD_FORGET_S + 1
for i in range(ss.FAIL_ALL_LIMIT):
    ss.note_failure("10.0.1.%d" % (i % 200))
check(ss.throttled(OWNER), "a sign-in is remembered for %d days, not for ever" % (ss.GOOD_FORGET_S // 86400))
clock[0] += ss.FAIL_ALL_DELAY_S + 1

# Never permanent: even a thousand failures from one address cap at 15 min.
for _ in range(1000):
    ss.note_failure(ATTACKER)
check(ss._fail[ATTACKER]["until"] - clock[0] <= 900, "one address waits at most 15 min")

# ---- a crowd guesses no faster than one address (2026-11-03 review) ----------------
# One device can take any number of IPv6 addresses. Each gets a few free
# tries, but past the limit the backstop backs off like one address does,
# and a steady trickle keeps it up rather than starting a fresh window.
def fresh():
    ss._fail.clear()
    ss._good.clear()
    if hasattr(ss, "_good_state"):
        ss._good_state.update(loaded=False, salt=None)
    good = os.path.join(ss.STATE_DIR, getattr(ss, "GOOD_FILE", "-"))
    if os.path.exists(good):
        os.unlink(good)
    ss._fail_all.update(count=0, until=0.0, window=clock[0], last=clock[0])


fresh()
n = 0
for i in range(ss.FAIL_ALL_LIMIT):
    ss.note_failure("2001:db8:1:2::%x" % i)
    n += 1
day_end = clock[0] + 86400
k = 0
while clock[0] < day_end:
    addr = "2001:db8:1:2::1:%x" % k
    k += 1
    if ss.throttled(addr):
        clock[0] += 1
        continue
    ss.note_failure(addr)
    n += 1
check(n <= ss.FAIL_ALL_LIMIT + 200,
      "a fresh address for every guess gets at most ~%d guesses a day, not thousands (%d)"
      % (ss.FAIL_ALL_LIMIT + 200, n))
check(ss._fail_all["until"] - clock[0] <= 900, "and the backstop, too, waits at most 15 min")
clock[0] += 16 * 60
check(not ss.throttled("2001:db8:1:2::ffff"), "and it clears on its own once the guessing stops")

# ---- the owner's exemption survives a restart -------------------------------------
fresh()
ss.note_success(OWNER)
path = os.path.join(ss.STATE_DIR, getattr(ss, "GOOD_FILE", "throttle-good.json"))
check(os.path.exists(path), "a sign-in is written down")
raw = open(path).read() if os.path.exists(path) else ""
check(OWNER not in raw and "192.168" not in raw, "as a keyed hash, not the address")
check(not os.path.exists(path) or os.stat(path).st_mode & 0o077 == 0, "readable by the setup service alone")
# A restart: memory empty, the file still there.
ss._good.clear()
if hasattr(ss, "_good_state"):
    ss._good_state.update(loaded=False, salt=None)
for i in range(ss.FAIL_ALL_LIMIT + 5):
    ss.note_failure("10.0.2.%d" % (i % 200))
check(not ss.throttled(OWNER), "after a restart, the owner's device is still not held up by a crowd")
check(ss.throttled("192.168.1.78"), "while a newcomer is")
writes = []
real_save = getattr(ss, "_save_good", None)
if real_save:
    ss._save_good = lambda now: (writes.append(now), real_save(now))
for _ in range(20):
    ss.note_success(OWNER)
check(len(writes) == 0, "signing in again the same day doesn't rewrite the file (card writes)")
if real_save:
    ss._save_good = real_save
if hasattr(ss, "forget_good"):
    ss.forget_good()
check(not os.path.exists(path) and not ss._good, "forget_good (after an erase) drops the list")

# ---- the screen's key: its own backoff, never the LAN's ----------------------------
fresh()
for i in range(ss.FAIL_ALL_LIMIT + 5):
    ss.note_failure("10.0.3.%d" % (i % 200))
try:
    check(not ss.throttled("panel", backstop=False), "the screen is not held up by the LAN's failures")
    for _ in range(6):
        ss.note_failure("panel", backstop=False)
    check(ss.throttled("panel", backstop=False), "only by its own")
except TypeError:
    check(False, "throttled() can leave the backstop out")

print("setup throttle checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
