#!/usr/bin/env python3
"""The setup sign-in throttle counts each device, not lighttpd (security
review 2026-11-03, SR-25), and the current-password checks are throttled
too (the review's addendum).

Behind lighttpd every /setup caller is 127.0.0.1, so the per-address
throttle was one bucket for the whole LAN: one device failing on purpose
kept the owner out for up to 15 minutes at a time. Now the key is the last
X-Forwarded-For entry, which lighttpd adds, believed only when the kernel
says the connection is lighttpd's (any other program on the radar could
write the header itself). Change-password and reset check the current
password under the same throttle and failure count as signing in.

Run: python3 tests/test_setup_client_key.py
"""
import http.client
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ss_key", ROOT / "deploy" / "setup-server.py")
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)

fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


tmp = tempfile.mkdtemp()
ss.STATE_DIR = tmp
ss.STATE_FILE = os.path.join(tmp, "setup.json")
with open(ss.STATE_FILE, "w") as f:
    json.dump({"schema": 1, "claimed": True, "password": ss.hash_password("owner-secret-1")}, f)

LIGHTTPD, OTHER = 33, 61234
caller = {"uid": LIGHTTPD}
ss.peer_uid = lambda peer, local, tables=None: caller["uid"]
ss.proxy_uid = lambda: LIGHTTPD
ss.GOOD_FORGET_S = getattr(ss, "GOOD_FORGET_S", 0)
ss.call_setupd = lambda verb, params=None, timeout=120: {"ok": True, "result": {}}

srv = ss.Server(("127.0.0.1", 0), ss.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
PORT = srv.server_address[1]

OWNER, NEIGHBOUR = "192.168.1.23", "192.168.1.50"


def post(path, body, xff=None, uid=LIGHTTPD, token=None):
    caller["uid"] = uid
    h = {"Content-Type": "application/json"}
    if xff:
        h["X-Forwarded-For"] = xff
    if token:
        h["Authorization"] = "Bearer " + token
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
    c.request("POST", path, body=json.dumps(body).encode(), headers=h)
    r = c.getresponse()
    out = json.loads(r.read() or b"{}")
    c.close()
    return r.status, out


def login(pw, xff, uid=LIGHTTPD):
    return post("/setup/api/login", {"password": pw}, xff=xff, uid=uid)[0]


def reset():
    ss._fail.clear()
    getattr(ss, "_good", {}).clear()
    if hasattr(ss, "_good_state"):
        ss._good_state.update(loaded=False, salt=None)
    good = os.path.join(tmp, getattr(ss, "GOOD_FILE", "-"))
    if os.path.exists(good):
        os.unlink(good)
    ss._fail_all.update(count=0, until=0.0, window=ss.time.time(), last=ss.time.time())


# ---- client_key ------------------------------------------------------------------
lo, here = ("127.0.0.1", 50000), ("127.0.0.1", 8086)
if not hasattr(ss, "client_key"):     # before SR-25: every caller was 127.0.0.1
    ss.client_key = lambda peer, local, xff, uid=None: peer[0]
check(ss.client_key(lo, here, OWNER, uid=LIGHTTPD) == OWNER, "through lighttpd: the client's own address")
check(ss.client_key(lo, here, "6.6.6.6, " + OWNER, uid=LIGHTTPD) == OWNER,
      "only the last entry, the one lighttpd added; what the client wrote before it is ignored")
check(ss.client_key(lo, here, OWNER, uid=OTHER) == "local:%d" % OTHER,
      "another program on the radar can't pick its address by writing the header")
check(ss.client_key(lo, here, "not-an-address", uid=LIGHTTPD) == "proxy", "a header that isn't an address is not a key")
check(ss.client_key(("192.168.1.9", 5), here, OWNER) == "192.168.1.9", "a direct caller is its own address")
check(ss.client_key(lo, here, "::ffff:" + OWNER, uid=LIGHTTPD) == OWNER,
      "an IPv4 client reaching lighttpd's IPv6 socket is the same key as its IPv4 address")
check(ss.client_key(lo, here, "2001:db8:1:2::23", uid=LIGHTTPD) == "2001:db8:1:2::23",
      "an IPv6 client is its whole address (a home LAN shares one /64, so a /64 key would be one bucket again)")

# ---- through the real handler ---------------------------------------------------------
reset()
codes = [login("guess-%d" % i, NEIGHBOUR) for i in range(8)]
check(codes[-1] == 429, "a neighbour failing on purpose is slowed down (%s)" % codes)
check(login("owner-secret-1", OWNER) == 200, "while the owner, on another device, signs in")

reset()
codes = [login("guess-%d" % i, "192.168.1.%d" % (100 + i), uid=OTHER) for i in range(8)]
check(codes[-1] == 429, "a local program changing the header every time is still one caller (%s)" % codes)
check(login("owner-secret-1", OWNER) == 200, "and the owner is not held up by it")

# The owner's device, having signed in, gets past the global backstop.
reset()
check(login("owner-secret-1", OWNER) == 200, "the owner signs in once")
for i in range(ss.FAIL_ALL_LIMIT + 5):
    ss.note_failure("10.0.%d.%d" % (i // 200, i % 200))
check(login("guess", "192.168.1.88") == 429, "a crowd of failures slows a newcomer")
check(login("owner-secret-1", OWNER) == 200, "not the owner's own device")
# ...and still not after the setup service restarts (every OTA does).
ss._good.clear()
if hasattr(ss, "_good_state"):
    ss._good_state.update(loaded=False, salt=None)
check(login("owner-secret-1", OWNER) == 200, "nor after a restart, which used to forget the owner's device")

# ---- the current password, re-entered, is throttled ----------------------------------
reset()
tok = ss.new_session()
codes = [post("/setup/api/password", {"currentPassword": "guess-%d" % i, "newPassword": "x" * 12},
              xff=NEIGHBOUR, token=tok)[0] for i in range(8)]
check(codes[-1] == 429, "change-password: guessing the current password is slowed down (%s)" % codes)
check(ss.verify_password("owner-secret-1", ss.load_state()["password"]), "and the password is unchanged")
check(login("owner-secret-1", NEIGHBOUR) == 429, "the same count as signing in, for that device")
reset()
tok = ss.new_session()
codes = [post("/setup/api/reset", {"currentPassword": "guess-%d" % i, "scope": "settings", "confirm": "RESET"},
              xff=NEIGHBOUR, token=tok)[0] for i in range(8)]
check(codes[-1] == 429, "reset: guessing the current password is slowed down (%s)" % codes)
reset()
code, _ = post("/setup/api/password", {"currentPassword": "owner-secret-1", "newPassword": "owner-secret-2"},
               xff=OWNER, token=tok)
check(code == 200 and ss.verify_password("owner-secret-2", ss.load_state()["password"]),
      "with the right password, the change goes through as before")

srv.shutdown()
print("setup client key checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
