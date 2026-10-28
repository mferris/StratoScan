#!/usr/bin/env python3
"""Nothing on the radar waits without a time limit (#86, 2026-10-26).

The owner asked that the radar never wait with no limit "for free map or
anything else". The audit of every outside call found the waits a person
notices: the app's poll held by adsb.lol through the core feed's ?network=1
and network-compare's /network; the app's hello held by a probe of nmcli and
tailscale; a Remote access sign-in that read `tailscale up` with no deadline
and held setupd's state lock, so every later change answered "busy"; every
location change, Install button and FlightAware switch held for 30 s by a
systemd-run that waited for its oneshot to finish; the screensaver held by a
wlopm that never answered.

This runs each of those against a stand-in that is slow, and checks the
answer comes inside its limit. Then it reads the radar's code for any outside
call made without one: every urlopen, socket, HTTP connection and subprocess
in deploy/*.py names a timeout (Popen only from the allow-list below, each
saying what bounds it), every transient oneshot is started --no-block with a
start limit, and every curl and wlopm in the scripts has a limit.

Run: python3 tests/test_unit_timeouts.py
"""
import ast
import http.server
import importlib.util
import io
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Slow(http.server.BaseHTTPRequestHandler):
    """Answers after `delay` seconds with `body`."""
    delay, body = 0.0, b"{}"

    def do_GET(self):
        time.sleep(type(self).delay)
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *a):
        pass


def serve(handler):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def timed(fn, *a, **k):
    t0 = time.monotonic()
    out = fn(*a, **k)
    return out, time.monotonic() - t0


tmp = pathlib.Path(tempfile.mkdtemp())

# ---- the core feed never makes the app's poll wait on adsb.lol -------------------
os.environ["STRATOSCAN_CORE_LOOKUPS"] = "0"
cf = load("core_feed", D / "core-feed.py")


class Network(Slow):
    delay, body = 4.0, json.dumps({"ac": [{"hex": "c0ffee", "lat": 35.9, "lon": -78.8}]}).encode()


net_srv, net_url = serve(Network)
cf.NETWORK_URL = net_url + "/network"
feed = cf.Feed(lookups=type("L", (), {"routes": {}, "owners": {}})(), uat=False,
               sightings=type("S", (), {"get": lambda self: {}})(), trails=False)
# The app gives up on a poll after 8 s and the public gateway on the radar
# after 10 s; the radar's own answers come in a couple of seconds.
ac, took = timed(feed._network_raw)
check(took < 2.5 and ac == [],
      "?network=1 with network-compare taking 4 s: the feed answers in %.1f s, with what it has" % took)
ac, took = timed(feed._network_raw)
check(took < 2.5, "and asked again meanwhile, it starts no second refresh and still answers in time")
for _ in range(60):
    if getattr(feed, "_network_worker", None) is None:
        break
    time.sleep(0.1)
ac, took = timed(feed._network_raw)
check([a["hex"] for a in ac] == ["c0ffee"] and took < 0.2, "once the refresh lands, the next answer has it at once")

# The sighting counts, refreshed behind the feed; only the first answer waits, briefly.
class Store(Slow):
    delay, body = 2.0, json.dumps({"abc001": {"total": 4, "nearby": 1}}).encode()     # inside its 3 s limit


store_srv, store_url = serve(Store)
counts = cf.SightingCounts(url=store_url + "/sightings")
got, took = timed(counts.get)
check(took < 1.5 and got == {}, "a sighting store taking 2 s holds the first answer %.1f s at most" % took)
for _ in range(60):
    if not getattr(counts, "busy", False):
        break
    time.sleep(0.1)
check(counts.get() == {"abc001": (4, 1)}, "and its counts are used once they land")
counts.at = time.time() - cf.SIGHTINGS_CACHE_S - 1      # a minute on: due again, but not the first time
got, took = timed(counts.get)
check(took < 0.2 and got == {"abc001": (4, 1)}, "a later refresh never holds an answer: the last counts at once")

# What network-compare says about its answer decides how long the feed keeps
# it (review, 2026-10-26): an hour-old list went out as live for a minute.
class Answer(http.server.BaseHTTPRequestHandler):
    """Answers `code` with `body`, or with a body cut off mid-way (`cut`)."""
    code, body, cut = 200, b"{}", False

    def do_GET(self):
        self.send_response(type(self).code)
        self.send_header("Content-Length", str(len(self.body) + (100 if self.cut else 0)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *a):
        pass


ans_srv, ans_url = serve(Answer)
cf.NETWORK_URL = ans_url + "/network"
noted = []
feed._note_trails = lambda ac: noted.append(ac)
plane = {"hex": "c0ffee", "lat": 35.9, "lon": -78.8, "seen_pos": 1.0}


RETRY_S = getattr(cf, "NETWORK_RETRY_S", 5.0)


def refresh(code, doc, cut=False):
    """One refresh against an answer, run here; the list the feed then
    hands out, and how soon it asks again."""
    Answer.code, Answer.cut = code, cut
    Answer.body = doc if isinstance(doc, bytes) else json.dumps(doc).encode()
    noted.clear()
    feed._network_due = 0.0
    marker = threading.Thread(target=lambda: None)          # as _network_raw marks its worker
    marker.start(); marker.join()
    feed._network_worker = marker
    try:
        feed._refresh_network()
    except Exception:
        pass                    # a refresh that dies, as one could before the review
    return [a["hex"] for a in feed._network_raw()], getattr(feed, "_network_due", 0.0) - cf._now()


hexes, due = refresh(200, {"ac": [plane], "fetched": 50.0})
check(hexes == ["c0ffee"] and 8 <= due <= 10.5 and noted,
      "a current answer 50 s old is kept until network-compare's copy is due again (%.0f s), and trailed" % due)
hexes, due = refresh(200, {"ac": [plane], "fetched": 70.0, "pending": 1})
check(hexes == ["c0ffee"] and 0 < due <= RETRY_S + 0.5 and not noted,
      "a pending answer a minute old is shown, asked for again in %.0f s, and not trailed" % due)
hexes, due = refresh(200, {"ac": [plane], "fetched": 3600.0, "stale": True})
check(hexes == [] and 0 < due <= RETRY_S + 0.5 and not noted,
      "an hour-old answer kept through a failure: none of its aircraft shown as live, asked again soon")
hexes, due = refresh(503, {"error": "upstream unavailable", "detail": "still asking", "pending": 1})
check(hexes == [] and 0 < due <= RETRY_S + 0.5,
      "a 503 while network-compare first asks is asked again in %.0f s, not kept a minute" % due)
for what, args in (("an answer cut off mid-body", (200, {"ac": [plane]}, True)),
                   ("an answer of the wrong shape", (200, b"[1, 2]"))):
    hexes, due = refresh(*args)
    check(feed._network_worker is None and hexes == [] and 0 < due <= RETRY_S + 0.5,
          "%s ends the refresh cleanly, so the next one runs" % what)
feed._network_due = 0.0
Answer.code, Answer.body, Answer.cut = 200, json.dumps({"ac": [plane]}).encode(), False
ac, took = timed(feed._network_raw)
check([a["hex"] for a in ac] == ["c0ffee"] and took < 1.5, "and it does: the next answer has the list")
feed._network = (cf._now() - 3600, [plane])
feed._network_due = 0.0
Network.delay = 4.0
cf.NETWORK_URL = net_url + "/network"
ac, took = timed(feed._network_raw)
check(ac == [] and took < 2.5, "the feed's own hour-old list is not handed out while a refresh is slow")
for _ in range(60):
    if feed._network_worker is None:
        break
    time.sleep(0.1)

Answer.code, Answer.body, Answer.cut = 200, json.dumps({"abc002": {"total": 2, "nearby": 0}}).encode(), True
cut = cf.SightingCounts(url=ans_url + "/sightings")
cut.counts = {"abc001": (4, 1)}
cut.at = 1.0
cut.get()
for _ in range(30):
    if not cut.busy:
        break
    time.sleep(0.1)
check(not cut.busy and cut.counts == {"abc001": (4, 1)},
      "a sighting store answer cut off mid-body keeps the last counts and ends the refresh")
Answer.cut = False
cut.at = time.time() - cf.SIGHTINGS_CACHE_S - 1
cut.get()
for _ in range(30):
    if not cut.busy:
        break
    time.sleep(0.1)
check(cut.counts == {"abc002": (2, 0)}, "so the next refresh a minute on still runs")
net_srv.shutdown(); store_srv.shutdown(); ans_srv.shutdown()

# ---- network-compare's /network answers from its cache -------------------------
os.environ["STATE_DIRECTORY"] = str(tmp)
os.environ["STRATOSCAN_NET_RELAY"] = "0"
nc = load("network_compare", D / "network-compare.py")
built = {"started": 0, "n": 0, "delay": 0.0}


def fake_build():
    built["started"] += 1
    time.sleep(built["delay"])
    built["n"] += 1
    return {"ac": [], "mine": built["n"], "network": 0, "stats": {"ready": False}, "source": "adsb.lol", "at": time.time()}


nc.build_payload = fake_build
nc_srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), nc.Handler)
nc_srv.daemon_threads = True
threading.Thread(target=nc_srv.serve_forever, daemon=True).start()
nc_url = f"http://127.0.0.1:{nc_srv.server_address[1]}/network"


def get_network():
    try:
        with urllib.request.urlopen(nc_url, timeout=20) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


(code, d), took = timed(get_network)
check(code == 200 and d["mine"] == 1, "the first /network question is answered when adsb.lol is quick")
nc._cache["at"] -= nc.MIN_UPSTREAM_S + 1          # a minute later
built["delay"] = 5.0
(code, d), took = timed(get_network)
check(code == 200 and d["mine"] == 1 and took < 3.7,
      "adsb.lol taking 5 s: /network answers in %.1f s with the last comparison" % took)
(code, d), took = timed(get_network)
check(code == 200 and took < 3.7 and built["started"] == 2, "asked again meanwhile: one refresh, not two")
for _ in range(80):
    if nc._cache.get("worker") is None:
        break
    time.sleep(0.1)
(code, d), took = timed(get_network)
check(code == 200 and d["mine"] == 2 and took < 0.5, "and the next question after it lands has the fresh one")


def landed():
    for _ in range(80):
        if nc._cache.get("worker") is None:
            return
        time.sleep(0.1)


# Nothing asked for an hour, then adsb.lol slow (review, 2026-10-26): last
# night's comparison is not handed out as the current one.
nc._cache["at"] -= 3600
(code, d), took = timed(get_network)
check(code == 503 and d.get("detail") == "still asking" and d.get("pending") == 1 and took < 3.7,
      "with the last comparison an hour old and adsb.lol slow, /network says it is still asking (%.1f s)" % took)
landed()
(code, d), took = timed(get_network)
check(code == 200 and d["mine"] == 3 and "pending" not in d and not d.get("stale"),
      "and once it lands, the fresh one, not pending")
nc._cache["at"] -= nc.MIN_UPSTREAM_S + 10
(code, d), took = timed(get_network)
check(code == 200 and d["mine"] == 3 and d.get("pending") == 1 and d["fetched"] >= nc.MIN_UPSTREAM_S
      and not d.get("stale") and took < 3.7,
      "a comparison a minute old goes out while the next is on its way, marked pending, %.0f s old" % d.get("fetched", 0))
landed()
nc_srv.shutdown()

# ---- setupd: a sign-in that prints nothing, and the transient units ------------
sd = load("setupd", D / "setupd.py")
fake = tmp / "tailscale"
fake.write_text("#!/bin/sh\n[ -f \"$0.url\" ] && { echo 'To authenticate, visit:'; echo; "
                "printf '\\thttps://login.tailscale.com/a/abc123\\n'; }\nexec sleep 8\n")
fake.chmod(0o755)
sd.TAILSCALE = str(fake)
sd.LOGIN_URL_WAIT_S = 1
sd.tailscale_status = lambda: {"state": "NeedsLogin"}
t0 = time.monotonic()
try:
    sd.tailscale_login_start("radar")
    check(False, "a tailscale up that prints no login URL is an error")
except sd.Err as e:
    check(e.code == "tailscale_no_url", "a tailscale up that prints no login URL is an error")
took = time.monotonic() - t0
check(took < 3, "given up after its deadline (%.1f s), not when tailscale chooses to finish" % took)
check(sd._login_proc["p"] is None, "and the process stopped, so the next try starts afresh")
pathlib.Path(str(fake) + ".url").write_text("")
r = sd.tailscale_login_start("radar")
first = sd._login_proc["p"]
check(r["url"] == "https://login.tailscale.com/a/abc123" and first.poll() is None,
      "a login URL is handed out and its process left waiting for the owner")
check(sd.tailscale_login_start("radar")["url"] == r["url"] and sd._login_proc["p"] is first,
      "asked again soon, the same URL from the same login")
sd._login_proc["started"] -= getattr(sd, "LOGIN_REUSE_S", 600) + 1
sd.tailscale_login_start("radar")
check(sd._login_proc["p"] is not first and first.poll() is not None,
      "asked again much later, the old login is stopped and a fresh one started")
getattr(sd, "_stop_login", lambda: None)()

calls = []


class Done:
    returncode = 0
    stdout = b"inactive"
    stderr = b""


real_run, real_exists = sd.run, sd.os.path.exists
sd.run = lambda argv, **k: (calls.append(argv), Done())[1]
sd.os.path.exists = lambda p: p in (sd.OFFLINE_MAP, sd.FEEDING) or real_exists(p)
sd.ota_status = lambda: {"state": "checked"}
sd.start_offline_map_build(35.8776, -78.7875)
sd.set_feeding(True)
sd.ota_apply()
sd.run, sd.os.path.exists = real_run, real_exists
runs = [c for c in calls if c[0] == "systemd-run"]
check(len(runs) == 3, "the offline map, FlightAware and an update each start a transient unit")
for c in runs:
    unit = c[c.index("--unit") + 1]
    check("--no-block" in c and any(a.startswith("--property=TimeoutStartSec=") for a in c),
          "%s: systemd-run returns at once (--no-block), and the oneshot has a start limit" % unit)
check(any(c[:3] == ["/usr/bin/systemctl", "is-active", "stratoscan-ota-apply"] for c in calls),
      "an update already being installed is refused by its unit, not by waiting for it")

calls.clear()
sd.run = lambda argv, **k: (calls.append(argv), Done())[1]
sd.hotspot_active = lambda: False
sd.net_status()
sd.run = real_run
wifi = next(c for c in calls if "ACTIVE,SSID" in c)
check(wifi[-3:] == ["list", "--rescan", "no"], "the status probe reads NetworkManager's list, never waits for a WiFi scan")

# ---- setup-server: the app's hello never waits for a probe ---------------------
os.environ["STRATOSCAN_TLS_CERT"] = str(tmp / "no-cert")
ss = load("setup_server", D / "setup-server.py")
ss.STATE_FILE = str(tmp / "setup.json")
ss.CLAIM_FILE = str(tmp / "claim-code")
ss.PUBLIC_CHECK_STATE = str(tmp / "public-address.json")


def slow_setupd(verb, params=None, timeout=120):
    if verb in ("hotspot_info", "net_status", "tailscale_status"):
        time.sleep(3)
        if verb == "tailscale_status":
            return {"ok": True, "result": {"funnel": True, "publicUrl": "https://radar.example.com"}}
    return {"ok": True, "result": {"unit": "u"}}


ss.call_setupd = slow_setupd
srv = ss.Server(("127.0.0.1", 0), ss.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
hello_url = f"http://127.0.0.1:{srv.server_address[1]}/setup/api/hello"


def hello():
    with urllib.request.urlopen(hello_url, timeout=30) as r:
        return json.load(r)


h, took = timed(hello)
check(took < 1.5 and h["product"] == "StratoScan",
      "with setupd's probe taking 9 s, the hello answers in %.1f s (the app gives up at 2-3 s)" % took)
for _ in range(150):
    if ss._probe_cache["value"] is not None:
        break
    time.sleep(0.1)
h, took = timed(hello)
check(took < 1.5 and h["publicUrl"] == "https://radar.example.com", "and once the probe lands, the hello carries its public address")
srv.shutdown()

# ---- alerts and photos ------------------------------------------------------------
ev = (D / "events.py").read_text()
tick = ev.split("    def tick(self):")[1].split("\ndef ")[0]
check(tick.index("self.sender.flush()") < tick.index("self.locations.tick("),
      "events.py sends alerts before it asks the relay for phones' locations, never behind it")

pp = load("photo_proxy", D / "photo-proxy.py")


def refused(req, timeout=None):
    raise OSError("planespotters not answering")


pp.urllib.request.urlopen = refused
h = pp.Handler.__new__(pp.Handler)
h.path, h.wfile = "/photo/a1b2c3", io.BytesIO()
h.send_response = h.send_header = lambda *a: None
h.end_headers = lambda: None
h.do_GET()
entry = pp.cache.get("a1b2c3") or (0, None)
ttl = entry[1] if isinstance(entry[1], (int, float)) else pp.CACHE_TTL     # (time, body) before #86: a day
check(ttl <= 60 and json.loads(h.wfile.getvalue()) == {"found": False},
      "a photo lookup that failed is remembered a minute, not as 'no photo' for a day")

# ---- the scripts: every wlopm and curl has a limit -------------------------------
bin_ = tmp / "bin"
bin_.mkdir()
(bin_ / "wlopm").write_text("#!/bin/sh\nexec sleep 30\n")
(bin_ / "logger").write_text("#!/bin/sh\n:\n")
(bin_ / "wlopm").chmod(0o755); (bin_ / "logger").chmod(0o755)
if subprocess.run(["sh", "-c", "command -v timeout"], capture_output=True).returncode != 0:
    # coreutils' timeout(1) is on every unit; a stand-in where it is missing (a Mac)
    (bin_ / "timeout").write_text('#!/usr/bin/env python3\nimport subprocess, sys\n'
                                  'try:\n    sys.exit(subprocess.run(sys.argv[2:], timeout=float(sys.argv[1])).returncode)\n'
                                  'except subprocess.TimeoutExpired:\n    sys.exit(124)\n')
    (bin_ / "timeout").chmod(0o755)
run_dir = tmp / "run"
run_dir.mkdir()
env = dict(os.environ, XDG_RUNTIME_DIR=str(run_dir), PATH=f"{bin_}:{os.environ['PATH']}")
t0 = time.monotonic()
subprocess.run(["sh", str(D / "screen-resume.sh")], env=env, timeout=60)
took = time.monotonic() - t0
check(took < 15, "screen-resume.sh with a wlopm that never answers is done in %.0f s" % took)

saver = next(l for l in (D / "stratoscan-screensaver.service").read_text().splitlines() if l.startswith("ExecStart="))
check(saver.count("wlopm") == saver.count("timeout 5 wlopm") == 4, "and the screensaver's own wlopm calls are limited too")

# A command where a command can start: the line's start, or after $( ; | && ||.
AT_COMMAND = r"(?:^\s*|\$\(\s*|[;|&]\s*|\btimeout \d+ )"
unlimited = []
for script in sorted(D.glob("*.sh")):
    joined = re.sub(r"\\\n\s*", " ", script.read_text())        # a command continued over lines, whole
    for line in joined.splitlines():
        code = "" if line.lstrip().startswith("#") else line.split(" #", 1)[0]
        if re.search(AT_COMMAND + r"curl\s", code) and not re.search(r"\s(-m\s*\d|--max-time)", code):
            unlimited.append(f"{script.name}: {code.strip()[:70]}")
        if re.search(AT_COMMAND + r"wget\s", code) and not re.search(r"\s(-T\s*\d|--timeout)", code):
            unlimited.append(f"{script.name}: {code.strip()[:70]}")
        if re.search(r"(?:^|[\s;|&(])wlopm(?:\s|$)", code) and not re.search(r"\btimeout \d+ wlopm", code):
            unlimited.append(f"{script.name}: {code.strip()[:70]}")
check(not unlimited, "every curl, wget and wlopm in deploy/*.sh has a time limit" + "".join("\n       " + u for u in unlimited))
inst = (D / "install-setup-server.sh").read_text()
for needle, what in (("notable-db.py ensure", "notable-aircraft list"), ("offline-map.py ensure", "offline map"),
                     ("git clone -q --depth 1", "dump978 clone"), ("github.com/wiedehopf/tar1090", "tar1090 clone"),
                     ('pip" install', "voice packages"), ("piper.download_voices", "voice download")):
    line = next((l for l in inst.splitlines() if needle in l and not l.lstrip().startswith("#")), "")
    check(re.search(r"\btimeout \d+ ", line) is not None, "the installer's %s has a time limit" % what)
for unit, limit in (("stratoscan-ota-auto.service", "30min"), ("stratoscan-ota-check.service", "5min")):
    check(f"TimeoutStartSec={limit}" in (D / unit).read_text(), f"{unit}, a oneshot, has a start limit")

# ---- the kiosk waits for its page, with a limit (#93, 2026-10-28) ----------------
# After a boot with no WiFi, lighttpd came up a minute after the kiosk, and the
# panel showed "This site can't be reached" until the paint watchdog restarted
# the kiosk. Now the browser waits for http://localhost/ to answer, but never
# past a limit: a broken lighttpd must still end in a browser on the panel.
kiosk = (D / "stratoscan-kiosk.service").read_text()
pres = [l[len("ExecStartPre="):] for l in kiosk.splitlines() if l.startswith("ExecStartPre=")]
wayland = next((p for p in pres if "wayland-" in p), "")
page = next((p for p in pres if "http://localhost/" in p), "")
page_sh = re.fullmatch(r"/bin/sh -c '([^']*)'", page)
bound = re.search(r"^timeout (\d+) sh -c \"until curl -so /dev/null -m (\d+) http://localhost/; do sleep 1; done\" \|\| echo ",
                  page_sh.group(1) if page_sh else "")
check(bound is not None and int(bound.group(1)) <= 120 and int(bound.group(2)) <= 5,
      "the kiosk waits for http://localhost/ at most 120 s, each try limited, then starts the browser anyway")
check(bool(wayland) and bool(page) and pres.index(wayland) < pres.index(page) and kiosk.index(page) < kiosk.index("\nExecStart="),
      "after the wait for Wayland, before the browser")
if bound:
    limit_s = int(bound.group(1))
    hold = re.search(r"-lt (\d+) \]", wayland)               # one look a second
    start_limit = re.search(r"^TimeoutStartSec=(\d+)min$", kiosk, re.M)
    check(hold is not None and start_limit is not None
          and int(start_limit.group(1)) * 60 >= int(hold.group(1)) + limit_s + 30,
          "systemd lets both waits run out: a start cut short would begin again from the top, never reaching the browser")
    # The paint watchdog counts from its own start at login, not the kiosk's.
    wl_src = (D / "wake-listener.py").read_text()
    wl_const = lambda name: eval(re.search(rf"^{name} = ([0-9 *]+)", wl_src, re.M).group(1), {"__builtins__": {}})
    check(limit_s < wl_const("FROZEN_AFTER_S"),
          "the wait is over before the paint watchdog can first restart the kiosk (%d s in)" % wl_const("FROZEN_AFTER_S"))
    check(limit_s < wl_const("MIN_RESTART_INTERVAL_S"),
          "and a restart that lands in a wait has the browser up before the watchdog may restart it again")

    # The wait itself, run with a shorter limit against stand-ins for lighttpd.
    class Answers(Slow):
        delay, body = 0.0, b"<!doctype html>"

    class Hangs(Slow):
        delay = 30.0

    def wait_for(url):
        script = page_sh.group(1).replace("http://localhost/", url + "/").replace(f"timeout {limit_s} ", "timeout 3 ", 1)
        t0 = time.monotonic()
        r = subprocess.run(["sh", "-c", script], env=env, capture_output=True, text=True, timeout=30)
        return r, time.monotonic() - t0

    up, up_url = serve(Answers)
    r, took = wait_for(up_url)
    check(r.returncode == 0 and took < 2 and r.stdout == "", "lighttpd answering: the browser starts at once (%.1f s)" % took)
    s = socket.socket(); s.bind(("127.0.0.1", 0)); closed_url = "http://127.0.0.1:%d" % s.getsockname()[1]; s.close()
    r, took = wait_for(closed_url)
    check(r.returncode == 0 and 2.5 < took < 6 and "starting the browser anyway" in r.stdout,
          "lighttpd not there: the start goes on at the limit, and says why (%.1f s of 3)" % took)
    hung, hung_url = serve(Hangs)
    r, took = wait_for(hung_url)
    check(r.returncode == 0 and took < 6 and "starting the browser anyway" in r.stdout,
          "lighttpd taking connections but not answering: the same (%.1f s of 3)" % took)

# ---- the code: every outside call in deploy/*.py names a timeout ------------------
# Popen has no timeout of its own. Each one is listed here with what bounds it.
POPEN_ALLOWED = {
    # read against a deadline by _read_login_url, and stopped by _stop_login
    # (terminate, then kill) when no URL comes, or when a newer login starts
    ("setupd.py", "tailscale_login_start"),
}
# Where a call's timeout is, if passed by position.
TIMEOUT_POS = {"urlopen": 2, "create_connection": 1, "HTTPConnection": 2, "HTTPSConnection": 2,
               "communicate": 1}
SUBPROCESS = {"run", "call", "check_call", "check_output"}
PROCESS = re.compile(r"(p|proc|.*_proc\b.*)")       # what a process is called, for its .wait()
missing, popens, oneshots, no_settimeout, bad_defaults = [], set(), [], [], []


class Scan(ast.NodeVisitor):
    def __init__(self, name):
        self.name, self.func = name, "<module>"

    def visit_FunctionDef(self, node):
        outer, self.func = self.func, node.name
        args = node.args.args + node.args.kwonlyargs
        defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + list(node.args.defaults) + list(node.args.kw_defaults)
        for a, dflt in zip(args, defaults):
            if a.arg == "timeout" and isinstance(dflt, ast.Constant) and dflt.value is None:
                bad_defaults.append(f"{self.name}:{node.lineno} {node.name}(timeout=None)")
        src = ast.unparse(node)
        if "socket.socket(" in src and ".settimeout(" not in src:
            no_settimeout.append(f"{self.name}:{node.lineno} {node.name}")
        self.generic_visit(node)
        self.func = outer

    def visit_Call(self, node):
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
        base = ast.unparse(fn)
        kws = {k.arg for k in node.keywords}
        where = f"{self.name}:{node.lineno} {ast.unparse(node)[:90]}"
        if name == "Popen":
            popens.add((self.name, self.func))
        elif name in TIMEOUT_POS:
            if "timeout" not in kws and len(node.args) <= TIMEOUT_POS[name]:
                missing.append(where)
        elif name == "wait" and isinstance(fn, ast.Attribute) and PROCESS.fullmatch(ast.unparse(fn.value)):
            if "timeout" not in kws and not node.args:
                missing.append(where)
        elif base in {f"subprocess.{s}" for s in SUBPROCESS} or (name == "open" and "opener" in base):
            if "timeout" not in kws:
                missing.append(where)
        if isinstance(node.args[0] if node.args else None, ast.List):
            argv = [a.value for a in node.args[0].elts if isinstance(a, ast.Constant)]
            if argv[:1] == ["systemd-run"] and "--property=Type=oneshot" in argv:
                ok = "--no-block" in argv and any(
                    "TimeoutStartSec" in ast.unparse(a) for a in node.args[0].elts)
                oneshots.append((where, ok))
        self.generic_visit(node)


for f in sorted(D.glob("*.py")):
    Scan(f.name).visit(ast.parse(f.read_text()))
check(not missing, "every urlopen, socket connection, HTTP connection and subprocess in deploy/*.py names a timeout"
      + "".join("\n       " + m for m in missing))
check(popens <= POPEN_ALLOWED, "Popen only where the allow-list says what bounds it"
      + "".join("\n       %s %s" % p for p in sorted(popens - POPEN_ALLOWED)))
check(not no_settimeout, "every function that opens a socket sets its timeout" + "".join("\n       " + m for m in no_settimeout))
check(not bad_defaults, "no wrapper's timeout defaults to none at all" + "".join("\n       " + m for m in bad_defaults))
check(len(oneshots) >= 5 and all(ok for _, ok in oneshots),
      "every transient oneshot is started --no-block, with a start limit (%d found)" % len(oneshots)
      + "".join("\n       " + w for w, ok in oneshots if not ok))

print("unit time limit checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
