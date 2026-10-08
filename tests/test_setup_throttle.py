#!/usr/bin/env python3
"""The setup server's sign-in throttle is per address (security review
2026-10-04, item 2): a device failing on purpose slows itself down, not the
owner on another device; a global backstop still slows everyone once a crowd
of addresses fails together; and nothing locks for good."""
import importlib.util
import pathlib
import sys

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


clock = [1_000_000.0]
ss.time.time = lambda: clock[0]
ss._fail.clear()
ss._fail_all.update(count=0, until=0.0, window=clock[0])

ATTACKER, OWNER = "192.168.4.50", "192.168.4.20"
for _ in range(8):
    ss.note_failure(ATTACKER)
check(ss.throttled(ATTACKER), "eight failures throttle that address")
check(not ss.throttled(OWNER), "another address is not throttled by them")
ss.note_success(OWNER)
check(not ss.throttled(OWNER), "the owner signs in while the attacker waits")

clock[0] += 20 * 60
check(not ss.throttled(ATTACKER), "the attacker's wait ends on its own (20 min later)")
check(ATTACKER not in ss._fail, "and a quiet address is forgotten")

# The backstop: many addresses failing together slow everyone, briefly.
for i in range(ss.FAIL_ALL_LIMIT):
    ss.note_failure("10.0.0.%d" % (i % 200))
check(ss.throttled(OWNER), "%d failures across addresses throttle everyone" % ss.FAIL_ALL_LIMIT)
clock[0] += ss.FAIL_ALL_DELAY_S + 1
check(not ss.throttled(OWNER), "for %d s only" % ss.FAIL_ALL_DELAY_S)

# Never permanent: even a thousand failures from one address cap at 15 min.
for _ in range(1000):
    ss.note_failure(ATTACKER)
check(ss._fail[ATTACKER]["until"] - clock[0] <= 900, "one address waits at most 15 min")

print("setup throttle checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
