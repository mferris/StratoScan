#!/usr/bin/env python3
"""
Checks for setting up a new radar from the app (roadmap 2.18) on the radar's
side: the first-run QR link, joining the home WiFi from the setup network,
and offering a pairing code whose secret only the phone holds.

Run: python3 tests/test_app_setup.py
"""
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
failures = []
checks = 0


def check(label, condition):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "..", "deploy", file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ss = load("setup_server", "setup-server.py")
tmp = tempfile.mkdtemp()
ss.STATE_DIR = tmp
ss.STATE_FILE = os.path.join(tmp, "setup.json")

# ---- the first-run QR link -------------------------------------------------------------
HS = {"active": True, "ssid": "StratoScan-Setup", "psk": "pw&k=x 1", "address": "10.42.0.1"}
link = ss.setup_link("ABC-123", HS)
q = parse_qs(urlparse(link).query)
check("a setup link is a stratoscan://setup link", link.startswith("stratoscan://setup?"))
check("it carries the claim code and the setup network",
      q.get("c") == ["ABC-123"] and q.get("w") == ["StratoScan-Setup"] and q.get("a") == ["10.42.0.1"])
check("the network password survives & = and spaces as one value", q.get("k") == ["pw&k=x 1"])
check("on the setup network it gives no LAN address", "h" not in q)
ss.lan_addresses = lambda: ["100.98.1.2", "192.168.1.23"]
q = parse_qs(urlparse(ss.setup_link("ABC-123", {"active": False})).query)
check("already on a network, it gives the home address (not Tailscale's)", q.get("h") == ["192.168.1.23"] and "w" not in q)
ss.lan_addresses = lambda: []
check("with neither, there is no link to show", ss.setup_link("ABC-123", {"active": False}) is None)
check("with no claim code (already claimed), no link", ss.setup_link(None, HS) is None)

# ---- joining the home WiFi from the setup network ----------------------------------------
calls = []
answers = {}


def fake_setupd(verb, params=None, timeout=None):
    calls.append((verb, params))
    a = answers.get(verb, {"ok": True, "result": {}})
    return a.pop(0) if isinstance(a, list) else a


ss.call_setupd = fake_setupd
H = hashlib.sha256(b"a phone's secret").hexdigest()
ss.save_state({"schema": 1, "claimed": True})
ss.join_in_background("Home", "hunter22", H, delay=0, sleep=lambda s: None)
verbs = [v for v, _ in calls]
check("it joins, confirms, then offers the phone's code, in that order",
      verbs == ["wifi_connect", "wifi_confirm", "pair_offer_hash"])
check("the WiFi password goes to setupd as given", calls[0][1] == {"ssid": "Home", "psk": "hunter22"})
check("the offer carries only the hash", calls[2][1] == {"hash": H})
st = ss.load_state()
check("and records the join as done", st["join"]["state"] == "ok" and st["steps"].get("wifi") is True)

calls.clear()
answers["wifi_connect"] = {"ok": False, "code": "wifi_auth_failed"}
ss.join_in_background("Home", "wrong", H, delay=0, sleep=lambda s: None)
check("a failed join is not confirmed, and offers nothing", [v for v, _ in calls] == ["wifi_connect"])
st = ss.load_state()
check("and says why, for the phone to read after rejoining the setup network",
      st["join"] == {**st["join"], "state": "failed", "code": "wifi_auth_failed"})
answers.pop("wifi_connect")

calls.clear()
answers["pair_offer_hash"] = [{"ok": False, "code": "relay"}, {"ok": False, "code": "relay"}, {"ok": True}]
ss.join_in_background("Home", "hunter22", H, delay=0, sleep=lambda s: None)
check("the offer is retried while the relay is unreachable, then stops",
      [v for v, _ in calls].count("pair_offer_hash") == 3)
answers.pop("pair_offer_hash", None)

calls.clear()
answers["pair_offer_hash"] = {"ok": False, "code": "relay"}
ss.join_in_background("Home", "hunter22", H, delay=0, sleep=lambda s: None)
check("but not forever", [v for v, _ in calls].count("pair_offer_hash") == ss.JOIN_OFFER_TRIES)
answers.pop("pair_offer_hash")

calls.clear()
ss.join_in_background("Home", "hunter22", None, delay=0, sleep=lambda s: None)
check("with no code to offer, it only joins", [v for v, _ in calls] == ["wifi_connect", "wifi_confirm"])

# ---- the hash, at each layer ---------------------------------------------------------------
check("the server only takes a hex SHA-256", bool(ss.RE_SECRET_HASH.match(H)) and not ss.RE_SECRET_HASH.match(H.upper())
      and not ss.RE_SECRET_HASH.match(H[:-1]) and not ss.RE_SECRET_HASH.match("a phone's secret"))
os.environ["STRATOSCAN_PAIRING_RUN"] = tmp
pr = load("pairing", "pairing.py")
sent = []
pr._call = lambda method, path, body=None: (sent.append((method, path, body)) or {"ok": True, "expires": 123})
r = pr.offer_hash(H)
check("pairing.py offers the hash to the relay, and nothing else",
      sent == [("POST", "/v1/unit/pairing", {"secret_hash": H})] and r["offered"] is True)
try:
    pr.offer_hash("not a hash")
    refused = False
except ValueError:
    refused = True
check("and refuses anything that isn't one", refused)
check("no secret is written on the radar", not os.path.exists(os.path.join(tmp, "pairing-offer.json")))

# ---- no read route swallows a save to the same path ---------------------------------------
# /setup/api/locale and /setup/api/ota each had an any-method route ahead of
# their POST route, so the setup page's Save and Install buttons only ever read.
import re
src = open(os.path.join(HERE, "..", "deploy", "setup-server.py")).read()
any_method = set(re.findall(r'if path == "(/setup/api/[^"]+)":', src))
posted = set(re.findall(r'if path == "(/setup/api/[^"]+)" and self.command == "POST"', src))
check("no path has both an any-method route and a POST route", not (any_method & posted))

print(f"{checks - len(failures)}/{checks} app setup checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
