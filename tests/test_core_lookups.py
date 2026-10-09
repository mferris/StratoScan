#!/usr/bin/env python3
"""core-feed.py's route and owner lookups through the relay's shared cache
(performance audit 2026-10-09): asked of the relay when this radar reports
to it, of adsb.im and adsbdb themselves when the relay cannot be reached or
will not serve this unit, and left for later when the relay says the
service is away -- never cached as "no route" from a failure."""
import http.server
import importlib.util
import json
import os
import pathlib
import socket
import sys
import threading
import urllib.error
import urllib.request

root = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


class Stub(http.server.BaseHTTPRequestHandler):
    """The relay and the two public services, on one port."""
    mode = {"routes": 200, "owner": 200}
    hits = []

    def _reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        planes = json.loads(self.rfile.read(n) or b"{}").get("planes", [])
        Stub.hits.append(("POST", self.path, [p["callsign"] for p in planes]))
        if self.path == "/v1/net/routes" and Stub.mode["routes"] != 200:
            return self._reply(Stub.mode["routes"], {"error": "away"})
        routes = [{"callsign": p["callsign"], "plausible": True,
                   "_airports": [{"location": "Raleigh"}, {"location": "Atlanta"}]}
                  for p in planes if p["callsign"] != "NOROUTE"]
        self._reply(200, routes)

    def do_GET(self):
        Stub.hits.append(("GET", self.path, None))
        hexid = self.path.rsplit("/", 1)[-1]
        if self.path.startswith("/v1/net/owner/") and Stub.mode["owner"] != 200:
            return self._reply(Stub.mode["owner"], {"error": "away"})
        if hexid == "000001":
            return self._reply(404, {"response": "unknown aircraft"})
        self._reply(200, {"response": {"aircraft": {"registered_owner": "United States Army",
                                                     "registered_owner_country_name": "United States"}}})

    def log_message(self, *a):
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.server_address[1]
dead = socket.socket(); dead.bind(("127.0.0.1", 0)); dead_port = dead.getsockname()[1]; dead.close()

os.environ.update({
    "STRATOSCAN_CORE_LOOKUPS": "0",
    "STRATOSCAN_ROUTE_API": f"http://127.0.0.1:{port}/api/0/routeset",
    "STRATOSCAN_OWNER_API": f"http://127.0.0.1:{port}/v0/aircraft/{{hex}}",
})
spec = importlib.util.spec_from_file_location("cf", root / "deploy" / "core-feed.py")
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)


class FakeRelay:
    """Stands in for heartbeat.py: on, and really asking the stub (unsigned)."""
    on = True
    base = f"http://127.0.0.1:{port}"

    @staticmethod
    def relay_on():
        return FakeRelay.on

    @staticmethod
    def relay_fetch(method, path, body=None, timeout=5, limit=1 << 20):
        req = urllib.request.Request(FakeRelay.base + path, data=body, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(limit + 1)
        except urllib.error.HTTPError as e:
            return e.code, e.read(65536)


cf.heartbeat = FakeRelay
cf.RELAY = True
L = cf.Lookups()
check(cf.relay_on() is True, "with reports on, lookups go through the relay")

# routes
L.want_route("DAL2164", 35.85, -78.75); L.want_route("NOROUTE", 35.8, -78.7)
L._flush_routes()
check(Stub.hits and Stub.hits[-1][:2] == ("POST", "/v1/net/routes") and Stub.hits[-1][2] == ["DAL2164", "NOROUTE"],
      "the batch goes to the relay, not adsb.im")
check(L.routes.get("DAL2164") == {"text": "Raleigh → Atlanta", "plausible": True} and L.routes.get("NOROUTE") is None
      and "NOROUTE" in L.routes, "routes cached from the relay's answer, including 'no route'")
Stub.hits.clear(); Stub.mode["routes"] = 503
L.want_route("UAL123", 36.0, -79.0)
L._flush_routes()
check([h[1] for h in Stub.hits] == ["/v1/net/routes", "/api/0/routeset"] and L.routes.get("UAL123") is not None,
      "the relay says adsb.im refused it: adsb.im itself, from this address")
Stub.hits.clear(); Stub.mode["routes"] = 403
L.want_route("AAL100", 36.0, -79.0)
L._flush_routes()
check([h[1] for h in Stub.hits] == ["/v1/net/routes", "/api/0/routeset"] and L.routes.get("AAL100") is not None,
      "the relay will not serve this unit: adsb.im itself")
Stub.hits.clear(); Stub.mode["routes"] = 200
FakeRelay.base = f"http://127.0.0.1:{dead_port}"
L.want_route("SWA100", 36.0, -79.0)
L._flush_routes()
check([h[1] for h in Stub.hits] == ["/api/0/routeset"] and L.routes.get("SWA100") is not None,
      "the relay unreachable: adsb.im itself")
FakeRelay.base = f"http://127.0.0.1:{port}"

# owners
Stub.hits.clear()
L.want_owner("ae74e8"); L.want_owner("000001")
L._flush_owners()
paths = sorted(h[1] for h in Stub.hits)
check(paths == ["/v1/net/owner/000001", "/v1/net/owner/ae74e8"], "owners asked of the relay")
check(L.owners.get("ae74e8") == {"name": "United States Army", "country": "United States"}, "an owner from the relay's answer")
check("000001" in L.owners and L.owners["000001"] is None, "404 from the relay: not in the registry, remembered")
Stub.hits.clear(); Stub.mode["owner"] = 503
L.want_owner("a1b2c3")
L._flush_owners()
check([h[1] for h in Stub.hits] == ["/v1/net/owner/a1b2c3", "/v0/aircraft/a1b2c3"] and L.owners.get("a1b2c3") is not None,
      "the relay says adsbdb refused it: adsbdb itself, from this address")
Stub.hits.clear(); Stub.mode["owner"] = 403
L.want_owner("b2c3d4")
L._flush_owners()
check([h[1] for h in Stub.hits] == ["/v1/net/owner/b2c3d4", "/v0/aircraft/b2c3d4"] and L.owners.get("b2c3d4") is not None,
      "the relay will not serve this unit: adsbdb itself")
Stub.hits.clear(); Stub.mode["owner"] = 200
FakeRelay.on = False
L.want_owner("c0ffee")
L._flush_owners()
check([h[1] for h in Stub.hits] == ["/v0/aircraft/c0ffee"], "reports off: adsbdb itself, the relay never asked")
cf.RELAY = False; FakeRelay.on = True
check(cf.relay_on() is False, "STRATOSCAN_NET_RELAY=0 keeps everything direct")
# The services that ask the relay run as dynamic users: without the key's
# group they cannot see the key and quietly fall back to asking the public
# services themselves (found live on RDU, 2026-10-09).
for name in ("stratoscan-network.service", "stratoscan-core.service"):
    svc = open(root / "deploy" / name).read()
    check("DynamicUser=yes" in svc and "SupplementaryGroups=stratoscan-relay" in svc,
          f"{name} may read the unit key, so it can sign for the relay's cache")
srv.shutdown()
print("core lookups checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
