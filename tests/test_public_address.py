#!/usr/bin/env python3
"""The radar notices when its public web address stops working, and repairs it (#82).

On 2026-10-23 Tailscale stopped publishing RDU's public name during a run of
restarts. The radar still had Funnel on and saw nothing wrong, and the owner
found out a day later, away from home, when the app said the radar was out of
reach. Now net-watchdog checks the address every ten minutes: public DNS over
HTTPS, then a harmless path of the public page through Funnel. Once it has
been down half an hour it repairs it the way the setup page's switch does.
That's setupd's funnel_repair: only an address the owner turned on, gateway
guard first. At most once an hour and four times a day. The panel's network
pill and the app at home say so meanwhile.

Run: python3 tests/test_public_address.py
"""
import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---- setupd: repair only what the owner turned on --------------------------------
d = load("setupd", ROOT / "deploy" / "setupd.py")
check("funnel_repair" in d.VERBS, "setupd has a funnel_repair verb")
calls = []
d.tailscale_status = lambda: {"funnel": False}
d.tailscale_funnel = lambda enabled: calls.append(enabled) or {"enabled": enabled}
try:
    d.VERBS["funnel_repair"]({})
    refused = False
except d.Err as e:
    refused = e.code == "funnel_off" if hasattr(e, "code") else True
check(refused and calls == [], "it refuses when the public address is off: it never turns one on")
d.tailscale_status = lambda: {"funnel": True}
d.VERBS["funnel_repair"]({})
check(calls == [True], "and re-applies Funnel the way the setup switch does when it is on")
src = (ROOT / "deploy" / "setupd.py").read_text()
fr = src[src.index("def funnel_repair("):src.index("# ------------------------------------------------------------------- reset")]
check("return tailscale_funnel(True)" in fr, "through tailscale_funnel, whose gateway guard runs first")

# ---- net-watchdog: when to check, when to repair -----------------------------------
w = load("netwatchdog", ROOT / "deploy" / "net-watchdog.py")
tmp = tempfile.mkdtemp()
w.PUBLIC_STATE = os.path.join(tmp, "public-address.json")
said, setupd_calls = [], []
status = {"funnel": True, "magicDnsName": "radar.example.ts.net"}
dns = {"answer": []}          # [] = no such name; ["203.0.113.7"] = resolves; None = no DoH answered
page = {"ok": False}


def fake_setupd(verb, params=None, timeout=120):
    setupd_calls.append(verb)
    if verb == "tailscale_status":
        return {"ok": True, "result": dict(status)}
    if verb == "funnel_repair":
        return {"ok": True, "result": {"enabled": True}}
    return {"ok": False}


w.call_setupd = fake_setupd
w.public_name_lookup = lambda name: dns["answer"]
w.public_page_answers = lambda name, ip: page["ok"]
real_print = print
w.print = lambda *a, **k: said.append(" ".join(str(x) for x in a))
state = lambda: json.load(open(w.PUBLIC_STATE))
repairs = lambda: setupd_calls.count("funnel_repair")

t0 = 1_800_000_000
w.maybe_check_public_address(now=t0)
check(state()["ok"] is False and repairs() == 0, "a missing name is noted at once, but not repaired at once")
check(sum("public web address is down" in s for s in said) == 1, "with one line in the journal")
w.maybe_check_public_address(now=t0 + 60)
check(setupd_calls.count("tailscale_status") == 1, "checks come no more than every ten minutes")
for k in range(1, 3):
    w.maybe_check_public_address(now=t0 + k * 600)
check(repairs() == 0 and sum("is down" in s for s in said) == 1,
      "twenty minutes down: still waiting (Tailscale's DNS is slow), and no more journal lines")
w.maybe_check_public_address(now=t0 + 1800)
check(repairs() == 1 and state()["lastRepair"] == t0 + 1800, "half an hour down: repaired")
for k in range(4, 9):
    w.maybe_check_public_address(now=t0 + k * 600)
check(repairs() == 1, "not again within the hour, while its name comes back")
w.maybe_check_public_address(now=t0 + 1800 + 3600)
check(repairs() == 2, "an hour later, still down: repaired again")
for k in range(1, 12):
    w.maybe_check_public_address(now=t0 + 1800 + 3600 * (1 + k))
check(repairs() == 4, "at most four repairs a day, however long it stays down")
w.maybe_check_public_address(now=t0 + 1800 + 86400 + 3600 * 3)
check(repairs() == 5, "and the count starts over a day on")

dns["answer"] = ["203.0.113.7"]
w.maybe_check_public_address(now=t0 + 200000)
check(state()["ok"] is False and state()["reason"] == "it does not answer through Funnel",
      "a name that resolves is not enough: the page has to answer through Funnel")
page["ok"] = True
w.maybe_check_public_address(now=t0 + 200600)
check(state()["ok"] is True and any("works again" in s for s in said), "working again: said once, and the state clears")
n = repairs()
dns["answer"] = None
w.maybe_check_public_address(now=t0 + 201200)
check(state()["ok"] is True and repairs() == n, "no DNS-over-HTTPS service answering says nothing either way")
status["funnel"] = False
dns["answer"] = []
w.maybe_check_public_address(now=t0 + 201800)
check(state()["ok"] is None and repairs() == n, "the public address off: nothing to check, nothing repaired")

# the DNS-over-HTTPS answer read the way Cloudflare's and Google's JSON give it
w2 = load("netwatchdog2", ROOT / "deploy" / "net-watchdog.py")


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def fake_urlopen(answers):
    it = iter(answers)
    def opener(req, timeout=10):
        a = next(it)
        if isinstance(a, Exception):
            raise a
        return FakeResp(json.dumps(a).encode())
    return opener


import urllib.request
real_urlopen = urllib.request.urlopen
urllib.request.urlopen = fake_urlopen([{"Status": 3}])
check(w2.public_name_lookup("radar.example.ts.net") == [], "NXDOMAIN is no such name")
urllib.request.urlopen = fake_urlopen([{"Status": 0, "Answer": [{"type": 5, "data": "x"}, {"type": 1, "data": "203.0.113.7"}]}])
check(w2.public_name_lookup("radar.example.ts.net") == ["203.0.113.7"], "an A record is its address")
urllib.request.urlopen = fake_urlopen([OSError("blocked"), {"Status": 3}])
check(w2.public_name_lookup("radar.example.ts.net") == [], "the second service is asked when the first can't be")
urllib.request.urlopen = fake_urlopen([OSError("x"), OSError("y")])
check(w2.public_name_lookup("radar.example.ts.net") is None, "neither answering is 'don't know', not 'down'")
urllib.request.urlopen = real_urlopen

wd = (ROOT / "deploy" / "net-watchdog.py").read_text()
check('PUBLIC_PATH = "/tar1090/data/receiver.json"' in wd, "the fetch is receiver.json: not a page view, so never counted as a visitor")
check('PUBLIC_STATE = "/run/stratoscan-net/public-address.json"' in wd, "the state is in RAM (no card writes), the watchdog's own directory")
main = wd[wd.index("def main():"):]
check(main.index("maybe_check_public_address()") < main.index("fails = read_failcount() + 1"),
      "it runs only while the radar is online")

# ---- what the panel and the app see ------------------------------------------------
ss = load("setup_server", ROOT / "deploy" / "setup-server.py")
ss.PUBLIC_CHECK_STATE = os.path.join(tmp, "check.json")
check(ss.public_address_check() == {"ok": None}, "no check yet: unknown")
json.dump({"checkedAt": 5, "ok": False, "reason": "its name is not in public DNS", "failingSince": 1,
           "repairs": [3], "lastRepair": 3}, open(ss.PUBLIC_CHECK_STATE, "w"))
pc = ss.public_address_check()
check(pc["ok"] is False and pc["reason"] and pc["since"] == 1 and pc["lastRepair"] == 3 and pc["repairsToday"] == 1,
      "down: why, since when, and the radar's repairs")
srv = (ROOT / "deploy" / "setup-server.py").read_text()
check('"publicAddress": public_address_check(),' in srv[srv.index('"remote": rem,'):][:200],
      "/onboard carries it for the panel")
hello = srv[srv.index('if path == "/setup/api/hello"'):][:2600]
check('"publicAddress": public_address_check(),' in hello, "and the LAN-only hello for the app at home")

page_src = (ROOT / "index.html").read_text()
ns = page_src[page_src.index("function netStatusState()"):page_src.index("function renderNetStatus()")]
check("PUBLIC PAGE DOWN" in ns and "pa.ok === false" in ns, "the panel's pill says PUBLIC PAGE DOWN while it is")
check("netInfo.remote.publicUrl" in ns and "netInfo.remote.funnelUrl" not in ns,
      "and its 'public page live' reads publicUrl, which setupd sends (funnelUrl never came)")

store = (ROOT / "ios" / "StratoScan" / "Pairing" / "PairingStore.swift").read_text()
check("publicAddressDown" in store and "let publicAddress: Public?" in store, "the app reads it from the hello at home")
cv = (ROOT / "ios" / "StratoScan" / "Views" / "ContentView.swift").read_text()
check("PUBLIC ADDRESS DOWN · REPAIRING" in cv and "Endpoint.shared.whereNow == .home" in cv,
      "and says so on the radar view, at home, before the owner needs it away")

privacy = (ROOT / "docs" / "privacy.md").read_text()
check("public web address" in privacy.lower() and "dns over https" in privacy.lower(),
      "the privacy policy says what the check asks and of whom")

print("public address checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
