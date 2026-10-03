#!/usr/bin/env python3
"""
Checks for the public page's visitor counts (roadmap 1.12) in
deploy/funnel-gateway.py: what is counted, what isn't, and that nothing saved
can identify a visitor.

Run: python3 tests/test_visits.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
failures = []
checks = 0


def check(label, condition):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


spec = importlib.util.spec_from_file_location("gw", os.path.join(HERE, "..", "deploy", "funnel-gateway.py"))
gw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gw)

IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
IPAD = "Mozilla/5.0 (iPad; CPU OS 26_0 like Mac OS X) AppleWebKit/605.1.15"
MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_0) AppleWebKit/605.1.15 Safari/605.1.15"
BOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
HOST = "stratoscan-rdu.example.ts.net"

# ---- classification ---------------------------------------------------------------------
check("an iPhone is a phone", gw.device_kind(IPHONE) == "phone")
check("an iPad is a tablet", gw.device_kind(IPAD) == "tablet")
check("a Mac is a computer", gw.device_kind(MAC) == "computer")
check("a crawler is a robot", gw.device_kind(BOT) == "bot" and gw.device_kind("curl/8.4") == "bot")
check("so is a link preview", gw.device_kind("facebookexternalhit/1.1") == "bot")
check("and no description at all", gw.device_kind("") == "bot")
check("a referrer is its site only", gw.referrer_site("https://www.facebook.com/groups/123?ref=abc", HOST) == "facebook.com")
check("not this radar itself", gw.referrer_site(f"https://{HOST}/index.html", HOST) is None)
check("nothing odd gets through as a site", gw.referrer_site("javascript:alert(1)", HOST) is None)
check("the address is the LAST forwarded one, which the client can't choose",
      gw.visitor_address({"X-Forwarded-For": "6.6.6.6, 203.0.113.9"}) == "203.0.113.9")
check("no header, no address", gw.visitor_address({}) is None)

# ---- counting ----------------------------------------------------------------------------
tmp = tempfile.mkdtemp()
clock = [time.mktime((2026, 10, 3, 18, 30, 0, 0, 0, -1))]
v = gw.Visits(directory=tmp, now=lambda: clock[0])


def req(path="/", ua=IPHONE, ip="203.0.113.9", app=False, ref=None, method="GET"):
    h = {"User-Agent": ua, "Host": HOST}
    if ip:
        h["X-Forwarded-For"] = ip
    if app:
        h[gw.APP_HEADER] = "1"
    if ref:
        h["Referer"] = ref
    v.record(method, path, h)


req(ref="https://www.facebook.com/x")
req()                                   # same visitor reloads
req(ip="198.51.100.4", ua=MAC)
req(path="/tar1090/data/aircraft.json")  # the page's own polling
req(ua=BOT)
req(path="/", method="POST")
s = v.summary()["today"]
check("page loads are views", s["views"] == 3)
check("the same visitor twice is one visitor", s["unique"] == 2)
check("the page's polling isn't a view", s["views"] == 3)
check("robots are counted apart", s["bots"] == 1)
summ = v.summary()
check("by device", summ["devices"] == {"phone": 2, "computer": 1})
check("where they came from", summ["referrers"] == [("facebook.com", 1)])
check("by hour of day", summ["hours7"][18] == 3)
check("unique visitors counted on the basis of addresses", summ["basis"] == "visitors")

req(path="/tar1090/data/aircraft.json", app=True)
req(path="/tar1090/data/aircraft.json", app=True)
clock[0] += 61
req(path="/tar1090/data/aircraft.json", app=True)
s = v.summary()["today"]
check("the owner's app is counted apart, in minutes of use", s["app_minutes"] == 2 and s["app_devices"] == 1)
check("and isn't a page view", s["views"] == 3)

# ---- what's saved -------------------------------------------------------------------------
v.save()
raw = open(os.path.join(tmp, "visits.json")).read()
check("nothing saved holds an address", "203.0.113" not in raw and "198.51.100" not in raw)
check("nor a browser description", "iPhone" not in raw and "Macintosh" not in raw)
check("nor a visitor hash", all(h not in raw for h in v._seen))
check("the salt is never saved", v._salt.hex() not in raw)
v2 = gw.Visits(directory=tmp, now=lambda: clock[0])
check("counts survive a restart", v2.summary()["today"]["views"] == 3)

# A new day: a new salt, and yesterday's visitors are strangers again.
salt = v._salt
clock[0] += 24 * 3600
req()
check("each day gets a new salt", v._salt != salt)
check("and the same person is a new visitor tomorrow", v.summary()["today"]["unique"] == 1)

# ---- without forwarded addresses ----------------------------------------------------------
v3 = gw.Visits(directory=tempfile.mkdtemp(), now=lambda: clock[0])
v3.record("GET", "/", {"User-Agent": IPHONE})
v3.record("GET", "/", {"User-Agent": IPHONE})
s3 = v3.summary()
check("with no addresses it counts views, not visitors, and says so",
      s3["today"]["views"] == 2 and s3["today"]["unique"] == 0 and s3["basis"] == "views")

# ---- kept 90 days, and nowhere to keep them -------------------------------------------------
for i in range(100):
    v.days[f"2026-01-{i:03d}"] = gw._new_day()
v.save()
check("90 days are kept", len(json.load(open(os.path.join(tmp, "visits.json")))["days"]) == gw.VISITS_KEEP_DAYS)
v4 = gw.Visits(directory=os.path.join(tmp, "missing"), now=lambda: clock[0])
v4.record("GET", "/", {"User-Agent": IPHONE})
check("with no directory it still counts, in memory", v4.summary()["today"]["views"] == 1 and not v4.summary()["kept"])

print(f"{checks - len(failures)}/{checks} visitor count checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
