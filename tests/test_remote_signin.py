#!/usr/bin/env python3
"""The on-screen setup's Tailscale sign-in (security review 2026-10-26).

/onboard/remote/start, the radar screen's own setup, asks no password: it is
for a radar that is not on a tailnet yet. It used to run `tailscale up
--force-reauth` whatever the state, so a radar already connected was signed
out and in afresh. A connected radar is now left where it is ("Already
connected" on screen); moving one to another account is for /setup, signed
in, with an auth key.

Run: python3 tests/test_remote_signin.py
"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


spec = importlib.util.spec_from_file_location("setupd", ROOT / "deploy" / "setupd.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

started = []


class Started(Exception):
    pass


def fake_popen(argv, **k):
    started.append(argv)
    raise Started()


real_popen = d.subprocess.Popen
d.subprocess.Popen = fake_popen
try:
    d.tailscale_status = lambda: {"state": "Running"}
    try:
        r = d.tailscale_login_start("radar")
    except Started:
        r = None
    check(not started and r and r.get("alreadyLoggedIn") and r.get("url") is None,
          "signed in already: no new sign-in")
    d.tailscale_status = lambda: {"state": "NeedsLogin"}
    try:
        d.tailscale_login_start("radar")
    except Started:
        pass
    check(len(started) == 1 and "--force-reauth" in started[0],
          "not signed in: the sign-in starts as before")
finally:
    d.subprocess.Popen = real_popen

page = (ROOT / "index.html").read_text()
start = page.index("if (act === 'remote-start')")
check("if (!r.result.url) deviceMsg = 'Already connected.';" in page[start:start + 1200],
      "the screen says so when no link comes back")

print("remote sign-in checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
