#!/usr/bin/env python3
"""
Checks for the radar's name (roadmap 2.17) in deploy/setup-server.py: what is
accepted, the suggestion from the home airport, and that it reaches the
pairing link (so a phone shows "Raleigh", not "Radar 1") while staying out of
anything public.

Run: python3 tests/test_radar_name.py
"""
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


spec = importlib.util.spec_from_file_location("setup_server", os.path.join(HERE, "..", "deploy", "setup-server.py"))
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)

tmp = tempfile.mkdtemp()
ss.STATE_DIR = tmp
ss.STATE_FILE = os.path.join(tmp, "setup.json")
ss.AIRPORTS_JSON = os.path.join(HERE, "..", "deploy", "airports.json")
airport = {"code": None}
ss.actual_airport = lambda: {"code": airport["code"]} if airport["code"] else None
ss.public_url = lambda: None
ss.lan_addresses = lambda: ["<radar>"]
ss.qr_svg = lambda text: None

# ---- what a name may be ---------------------------------------------------------------
check("an ordinary name is kept", ss.clean_name("Mom's radar") == "Mom's radar")
check("spaces are tidied", ss.clean_name("  Lake   house ") == "Lake house")
check("accents and emoji are fine", ss.clean_name("Zürich ✈") == "Zürich ✈")
check("empty is not a name", ss.clean_name("   ") is None)
check("too long is refused", ss.clean_name("x" * 33) is None and ss.clean_name("x" * 32) == "x" * 32)
check("control characters are refused", ss.clean_name("a\u0000b") is None and ss.clean_name("a‮b") is None)
check("only strings", ss.clean_name(42) is None and ss.clean_name(None) is None)

# ---- the suggestion -------------------------------------------------------------------
check("with no airport it is StratoScan", ss.radar_name() == "StratoScan")
airport["code"] = "RDU"
check("RDU suggests Raleigh (the first of Raleigh/Durham)", ss.radar_name() == "Raleigh")
airport["code"] = "ZZZ"
check("an airport not in the list suggests its code", ss.radar_name() == "ZZZ")
airport["code"] = "RDU"

# ---- setting it -------------------------------------------------------------------------
r = ss.set_name("Lake house")
check("setting a name keeps it", r == {"name": "Lake house", "own": True} and ss.radar_name() == "Lake house")
check("a bad name changes nothing", ss.set_name("\u0007") is None and ss.radar_name() == "Lake house")
r = ss.set_name("")
check("an empty name goes back to the suggestion", r == {"name": "Raleigh", "own": False})
with open(ss.STATE_FILE) as f:
    check("and leaves nothing behind in the state file", "name" not in json.load(f))

# ---- the pairing link -------------------------------------------------------------------
ss.set_name("Mom's radar")
offer = ss.dress_offer({"link": "stratoscan://pair?u=" + "A" * 43 + "&s=" + "b" * 22, "expires": 0})
q = parse_qs(urlparse(offer["link"]).query)
check("the pairing link carries the name", q.get("n") == ["Mom's radar"])
check("encoded, so it can't add parameters of its own", "&n=Mom%27s%20radar" in offer["link"])
ss.set_name("a&s=evil")
q = parse_qs(urlparse(ss.dress_offer({"link": "stratoscan://pair?u=x&s=real"})["link"]).query)
check("a name with & and = stays one parameter", q.get("s") == ["real"] and q.get("n") == ["a&s=evil"])

# ---- never public -------------------------------------------------------------------------
gspec = importlib.util.spec_from_file_location("gateway", os.path.join(HERE, "..", "deploy", "funnel-gateway.py"))
gw = importlib.util.module_from_spec(gspec)
gspec.loader.exec_module(gw)
check("hello (which carries the name) is refused on the public address",
      gw._matches("/setup/api/hello", gw.LOCAL_ONLY_PATHS))

print(f"{checks - len(failures)}/{checks} radar name checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
