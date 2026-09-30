#!/usr/bin/env python3
"""deploy/core-feed.py: the labelled feed every screen reads (roadmap 1.8).

Runs the real service on a spare port against fixture files and a fake
network-compare, with the third-party lookups switched off, and checks what
it serves: labels by the page's rules, nothing that could locate the
receiver, correct counts, the network merged only when asked (and cached),
and no way to write.
"""
import http.server
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(HERE, "..", "deploy", "core-feed.py")
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


HOME = (35.7801, -78.6389)          # a receiver position that must never appear in the output
AIRCRAFT = {"now": 0, "aircraft": [
    {"hex": "ae74e8", "flight": "ZEUS41  ", "lat": 35.80, "lon": -78.70, "alt_baro": 800, "gs": 97,
     "track": 315, "r_dst": 3.4, "r_dir": 290.1, "seen": 1, "seen_pos": 1, "category": "A7"},
    {"hex": "000001", "flight": "ZEUS44  ", "lat": 35.75, "lon": -78.60, "alt_baro": 900, "seen": 1},
    {"hex": "a1b2c3", "flight": "DAL2164 ", "lat": 35.85, "lon": -78.75, "alt_baro": 1175, "gs": 132,
     "baro_rate": -704, "squawk": "4611", "r_dst": 6.0, "r_dir": 300.0, "seen": 0.2},
    {"hex": "a3d4e5", "flight": "N30521  ", "lat": 36.30, "lon": -78.00, "alt_baro": 7400, "seen": 2},   # ~40 nm: outside the ring
    {"hex": "a3711a", "lat": 35.79, "lon": -78.65, "alt_baro": "ground", "seen": 3},
    {"hex": "a00001", "flight": "00000000", "lat": 35.70, "lon": -78.55, "alt_baro": 2000, "seen": 1},
    {"hex": "a99999", "flight": "UAL1", "lat": 35.78, "lon": -78.64, "alt_baro": 3000, "seen": 90},       # stale
]}
NETWORK = {"ac": [
    {"hex": "a1b2c3", "flight": "DAL2164", "lat": 35.85, "lon": -78.75, "alt": 1100},    # heard: must not repeat
    {"hex": "c0ffee", "flight": "JBU2084", "lat": 35.70, "lon": -78.70, "alt": 3775, "gs": 235,
     "track": 60, "seen_pos": 4, "type": "BCS3", "reg": "N3008J"},
]}


class NetworkServer(http.server.BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self):
        NetworkServer.hits += 1
        raw = json.dumps(NETWORK).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


def get(port, path, method="GET"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


with tempfile.TemporaryDirectory() as t:
    for name, data in (("aircraft.json", AIRCRAFT), ("receiver.json", {"lat": HOME[0], "lon": HOME[1]})):
        with open(os.path.join(t, name), "w") as f:
            json.dump(data, f)
    net = http.server.ThreadingHTTPServer(("127.0.0.1", 0), NetworkServer)
    threading.Thread(target=net.serve_forever, daemon=True).start()
    port = free_port()
    env = dict(os.environ,
               STRATOSCAN_CORE_PORT=str(port), STRATOSCAN_CORE_LOOKUPS="0",
               STRATOSCAN_AIRCRAFT_JSON=os.path.join(t, "aircraft.json"),
               STRATOSCAN_RECEIVER_JSON=os.path.join(t, "receiver.json"),
               STRATOSCAN_NETWORK_URL=f"http://127.0.0.1:{net.server_address[1]}/network",
               STRATOSCAN_TAR1090_DB=os.path.join(t, "no-db-*"),
               STRATOSCAN_NOTABLE_JSON=os.path.join(t, "no-notable.json"))
    proc = subprocess.Popen([sys.executable, CORE], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)

        code, raw = get(port, "/api/aircraft")
        check(code == 200, f"GET /api/aircraft -> {code}")
        feed = json.loads(raw)
        by = {a["hex"]: a for a in feed["aircraft"]}
        kind = lambda h: by[h]["operator"]["kind"]

        # labels, by the page's rules
        check(kind("ae74e8") == "military" and by["ae74e8"]["operator"]["label"] == "US military",
              "ZEUS41 (ae74e8, US military block) is military")
        check(kind("000001") == "private", "ZEUS44 on a placeholder address (000001) is not military")
        check(kind("a1b2c3") == "airline" and by["a1b2c3"]["operator"]["label"] == "Delta Air Lines", "DAL2164 is Delta")
        check(kind("a3d4e5") == "private", "N30521 is private")
        check(kind("a3711a") == "unknown", "no callsign yet is unknown (Identifying...)")
        check(kind("a00001") == "unknown", "an all-digit placeholder callsign is not a callsign")
        check("a99999" not in by, "an aircraft not heard for over a minute is left out")
        check(by["a3711a"]["alt"] == "ground", "on the ground reads as ground")
        check(by["a1b2c3"]["vrate"] == -704 and by["a1b2c3"]["squawk"] == "4611", "vertical rate and squawk carried")
        check(all(a["source"] == "antenna" for a in feed["aircraft"]), "without ?network=1, only the antenna's aircraft")

        # nothing that could locate the receiver
        text = raw.decode()
        check("r_dst" not in text and "r_dir" not in text, "no antenna-relative fields (r_dst, r_dir)")
        check(str(HOME[0]) not in text and str(HOME[1]) not in text, "the receiver's position appears nowhere")

        # counts: the 20 nm ring, as the kiosk counts
        check(feed["counts"]["heard"] == 5, f"heard in the 20 nm ring = 5 (got {feed['counts']['heard']})")
        check(feed["counts"]["notHeard"] is None, "no network count unless the network was asked for")
        check(NetworkServer.hits == 0, "the network is not contacted unless a client asks")

        # the network, merged when asked
        code, raw = get(port, "/api/aircraft?network=1")
        feed = json.loads(raw)
        net_ac = [a for a in feed["aircraft"] if a["source"] == "network"]
        check([a["hex"] for a in net_ac] == ["c0ffee"], "network aircraft merged; one the antenna heard is not repeated")
        check(net_ac and net_ac[0]["operator"]["label"] == "JetBlue Airways", "network aircraft labelled the same way")
        check(net_ac and net_ac[0]["reg"] == "N3008J" and net_ac[0]["type"]["code"] == "BCS3", "network registration and type kept")
        check(feed["counts"]["notHeard"] == 1, "not-heard count")
        get(port, "/api/aircraft?network=1")
        check(NetworkServer.hits == 1, f"network fetched once and cached (hits {NetworkServer.hits})")

        # read-only, and nothing else served
        check(get(port, "/api/aircraft", "POST")[0] == 405, "POST refused")
        check(get(port, "/api/other")[0] == 404, "other paths 404")
    finally:
        proc.terminate()
        proc.wait(5)
        net.shutdown()

print(f"core feed checks {'failed' if fails else 'passed'}" + (f" ({fails} failed)" if fails else ""))
sys.exit(1 if fails else 0)
