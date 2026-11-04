#!/usr/bin/env python3
"""Who may use the on-screen setup listener, 127.0.0.1:8090 (security review
2026-11-03, SR-11, with SR-49).

It used to answer anything on the radar that could reach loopback, with no
credential: a new admin password, a factory reset, another WiFi network, a
tailnet join. Now:
  - only the kiosk's user, by the kernel's word (/proc/net/tcp), and only by
    the radar's own names;
  - a change only from the kiosk page's own origin;
  - on a radar not yet set up, every change carries the screen's code;
  - on one that is, a new password, another WiFi network, a tailnet and the
    public page need the admin password (or a /setup session), throttled;
  - erasing stays open to the screen (the lost-password path), and the
    panel's everyday settings still need nothing.

Run: python3 tests/test_onboard_access.py
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
spec = importlib.util.spec_from_file_location("ss_onboard", ROOT / "deploy" / "setup-server.py")
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
ss.CLAIM_FILE = os.path.join(tmp, "claim-code")
with open(ss.CLAIM_FILE, "w") as f:
    f.write("K7Q2XM\n")

KIOSK, OTHER = 1000, 61234          # the kiosk's uid; a DynamicUser service's
caller = {"uid": KIOSK}
ss.peer_uid = lambda peer, local, tables=None: caller["uid"]
ss.kiosk_uid = lambda: KIOSK

verbs = []


def fake_setupd(verb, params=None, timeout=120):
    verbs.append(verb)
    return {"ok": True, "result": {"verb": verb}}


ss.call_setupd = fake_setupd
ss._onboard_probe = lambda: ({"ok": False}, None, None)
ss.lan_addresses = lambda: []
ss.public_address_check = lambda: {"ok": None}
ss.boot_info = lambda: {}
ss.actual_location = lambda: None
ss.actual_airport = lambda: None


def reset_throttle():
    ss._fail.clear()
    getattr(ss, "_good", {}).clear()
    ss._fail_all.update(count=0, until=0.0, window=ss.time.time())


def set_state(st):
    with open(ss.STATE_FILE, "w") as f:
        json.dump(st, f)


srv = ss.Server(("127.0.0.1", 0), ss.OnboardHandler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
PORT = srv.server_address[1]


def ask(method, path, body=None, uid=KIOSK, host="127.0.0.1:8090",
        origin="http://localhost", claim=None, extra=None):
    caller["uid"] = uid
    h = {"Host": host, "Content-Type": "application/json"}
    if origin:
        h["Origin"] = origin
    if claim:
        h["X-StratoScan-Claim"] = claim
    h.update(extra or {})
    data = json.dumps(body).encode() if body is not None else None
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    raw = r.read()
    c.close()
    try:
        return r.status, json.loads(raw or b"{}"), r
    except ValueError:
        return r.status, {}, r


def claimed():
    return bool(ss.load_state().get("claimed"))


# ---- the kernel's word: only the kiosk's user --------------------------------
set_state({"schema": 1, "claimed": False})
reset_throttle()
code, body, _ = ask("GET", "/onboard", uid=OTHER, origin=None)
check(code == 403 and "claimCode" not in body,
      "another program on the radar (the gateway, say) can't read the claim code")
code, body, _ = ask("GET", "/onboard", origin=None)
check(code == 200 and body.get("claimCode") == "K7Q2XM", "the kiosk still reads it")
verbs.clear()
code, _, _ = ask("POST", "/onboard/password", {"password": "hunter2hunter2"}, uid=OTHER, claim="K7Q2XM")
check(code == 403 and not claimed(), "another program can't set the password, even with the code")
code, _, _ = ask("POST", "/onboard/reset", {"confirm": "ERASE"}, uid=OTHER, claim="K7Q2XM")
check(code == 403 and "reset_full" not in verbs, "or erase the radar")
code, _, _ = ask("POST", "/onboard/remote/start", {"hostname": "x"}, uid=None, claim="K7Q2XM")
check(code == 403 and not verbs, "a caller the kernel can't name is refused, not guessed")
code, _, _ = ask("OPTIONS", "/onboard/password", uid=OTHER)
check(code == 403, "nor answered a preflight")

# ---- the radar's own names and the page's own origin --------------------------
code, _, _ = ask("GET", "/onboard", host="attacker.example:8090", origin=None)
check(code == 403, "a request by another site's name (DNS rebinding) is refused")
code, _, _ = ask("GET", "/onboard", host="localhost:8090", origin=None)
check(code == 200, "localhost:8090 is the radar's own name")
code, _, _ = ask("POST", "/onboard/name", {"name": "Den"}, origin="http://localhost:8504", claim="K7Q2XM")
check(code == 403, "a change from another loopback page (tar1090's port) is refused")
code, _, _ = ask("POST", "/onboard/name", {"name": "Den"}, origin=None, claim="K7Q2XM")
check(code == 403, "and one with no origin at all")
check(not ss.OnboardHandler._origin_ok("http://127.0.0.1:8085")
      and ss.OnboardHandler._origin_ok("http://localhost"),
      "only the kiosk page's origin is echoed back to the browser (SR-49)")
code, _, r = ask("OPTIONS", "/onboard/password")
check(code == 204 and "X-StratoScan-Claim" in (r.getheader("Access-Control-Allow-Headers") or ""),
      "the kiosk's preflight allows the code's header")

# ---- not yet set up: the screen's code on every change ----------------------------
verbs.clear()
code, body, _ = ask("POST", "/onboard/password", {"password": "hunter2hunter2"})
check(code == 403 and body["error"]["code"] == "claim_required" and not claimed(),
      "unclaimed: setting the password without the screen's code is refused")
code, _, _ = ask("POST", "/onboard/password", {"password": "hunter2hunter2"}, claim="WRONG1")
check(code == 403 and not claimed(), "and with a wrong code")
code, _, _ = ask("POST", "/onboard/wifi/connect", {"ssid": "x", "psk": "y"})
check(code == 403 and "wifi_connect" not in verbs, "unclaimed: joining a network needs the code too")
code, _, _ = ask("POST", "/onboard/wifi/scan", {})
check(code == 200 and "wifi_scan" in verbs, "a scan changes nothing and needs no code")
reset_throttle()
code, _, _ = ask("POST", "/onboard/password", {"password": "hunter2hunter2"}, claim="k7q2xm")
check(code == 200 and claimed(), "with the code (any case), the screen claims the radar")

# ---- set up: the changes that hand the radar over need its password ----------------
reset_throttle()
verbs.clear()
for path, b, verb in (("/onboard/wifi/connect", {"ssid": "x", "psk": "y"}, "wifi_connect"),
                      ("/onboard/remote/start", {"hostname": "x"}, "tailscale_login_start"),
                      ("/onboard/remote/funnel", {"enabled": True}, "tailscale_funnel")):
    code, body, _ = ask("POST", path, b)
    check(code == 401 and body["error"]["code"] == "admin_required" and verb not in verbs,
          f"claimed: {path} without the admin password is refused")
    code, _, _ = ask("POST", path, dict(b, adminPassword="hunter2hunter2"))
    check(code == 200 and verb in verbs, f"claimed: {path} with it goes ahead")
before = ss.load_state()["password"]
code, _, _ = ask("POST", "/onboard/password", {"password": "newpassword1"})
check(code == 401 and ss.load_state()["password"] == before,
      "claimed: a new password without the current one is refused")
code, _, _ = ask("POST", "/onboard/password", {"password": "newpassword1", "adminPassword": "nope-nope"})
check(code == 401 and ss.load_state()["password"] == before, "and with a wrong one")
code, _, _ = ask("POST", "/onboard/password", {"password": "newpassword1", "adminPassword": "hunter2hunter2"})
check(code == 200 and ss.verify_password("newpassword1", ss.load_state()["password"]),
      "with the current password, the screen changes it")
tok = ss.new_session()
code, _, _ = ask("POST", "/onboard/remote/funnel", {"enabled": False}, extra={"Authorization": "Bearer " + tok})
check(code == 200, "a /setup session will do instead of the password")

# The panel's everyday settings still need nothing, and erasing stays open.
verbs.clear()
code, _, _ = ask("POST", "/onboard/name", {"name": "Den"})
check(code == 200, "claimed: the panel names the radar with no password")
code, _, _ = ask("POST", "/onboard/radios", {"1090": True})
check(code == 200 and "set_radios" in verbs, "and switches its radios")
code, _, _ = ask("POST", "/onboard/reset", {"confirm": "ERASE"})
check(code == 200 and "reset_full" in verbs, "claimed: Erase everything still works without the password (the way back)")

# Guessing the password at the panel is throttled like a sign-in.
reset_throttle()
codes = [ask("POST", "/onboard/remote/start", {"hostname": "x", "adminPassword": "guess%d" % i})[0]
         for i in range(8)]
check(codes[-1] == 429, "repeated wrong passwords at the panel are slowed down (%s)" % codes)
reset_throttle()

# ---- peer_uid reads the kernel's table ----------------------------------------------
tbl = os.path.join(tmp, "tcp")
tbl6 = os.path.join(tmp, "tcp6")
with open(tbl, "w") as f:
    f.write("  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
            "   0: 0100007F:1F9A 00000000:0000 0A 00000000:00000000 00:00000000 00000000   997        0 1 1\n"
            "   1: 0100007F:1F9A 0100007F:D431 01 00000000:00000000 00:00000000 00000000   997        0 2 1\n"
            "   2: 0100007F:D431 0100007F:1F9A 01 00000000:00000000 00:00000000 00000000  1000        0 3 1\n")
with open(tbl6, "w") as f:
    f.write("  sl  local_address                         remote_address                        st\n"
            "   0: 0000000000000000FFFF00000100007F:D432 0000000000000000FFFF00000100007F:1F9A 01"
            " 00000000:00000000 00:00000000 00000000   33        0 4 1\n")
spec2 = importlib.util.spec_from_file_location("ss_peer", ROOT / "deploy" / "setup-server.py")
real = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(real)
for fn in ("peer_uid", "detect_kiosk_user"):
    if not hasattr(real, fn):     # before SR-11
        setattr(real, fn, lambda *a, **k: "missing")
if sys.byteorder == "little":
    check(real.peer_uid(("127.0.0.1", 0xD431), ("127.0.0.1", 8090), (tbl, tbl6)) == 1000,
          "peer_uid: the client's end of the connection names its user (not the server's own row)")
    check(real.peer_uid(("127.0.0.1", 0xD432), ("127.0.0.1", 8090), (tbl, tbl6)) == 33,
          "peer_uid: a dual-stack client's end is found in tcp6")
check(real.peer_uid(("127.0.0.1", 0xD433), ("127.0.0.1", 8090), (tbl, tbl6)) is None,
      "peer_uid: a connection not in the table is None")
check(real.peer_uid(("127.0.0.1", 1), ("127.0.0.1", 8090), ("/nonexistent",)) is None,
      "peer_uid: no table, no answer")
conf = os.path.join(tmp, "lightdm.conf")
with open(conf, "w") as f:
    f.write("[Seat:*]\n#autologin-user=\nautologin-user=<user>\n")
os.environ.pop("STRATOSCAN_KIOSK_USER", None)
check(real.detect_kiosk_user([conf]) == "<user>", "the kiosk's user is the display manager's autologin user")

srv.shutdown()
print("onboard access checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
