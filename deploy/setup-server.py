#!/usr/bin/env python3
"""Unprivileged HTTP tier for FlightRadar device setup.

Runs as a normal user and holds no privileges of its own. Anything that
touches the system is delegated to setupd.py over a unix socket, which
re-validates every parameter. This process only parses HTTP, checks
authentication, and renders the UI -- deliberately, because the HTTP parser
is the part most exposed to hostile input and therefore the part that must
not be root.

Reachable on the LAN at http://<device>/setup via lighttpd. It is listed in
funnel-gateway.py's LOCAL_ONLY_PATHS, so it is refused for anything arriving
through the public tunnel -- which matters, since it accepts a WiFi password
and a Tailscale auth key.

Claiming: on first boot the device is UNCLAIMED and the first person to
reach it sets the admin password. That is a deliberate trade-off, chosen
because a label-printed secret has a manufacturing lead time. The window is
narrowed by requiring a code shown on the device's own screen, so claiming
needs physical sight of the unit rather than merely being on the network.
"""
import hashlib
import hmac
import http.server
import json
import os
import re
import secrets
import socket
import threading
import time

LISTEN = ("127.0.0.1", 8086)
SOCK_PATH = "/run/flightradar/setupd.sock"
STATE_DIR = "/var/lib/flightradar-setup"
STATE_FILE = os.path.join(STATE_DIR, "setup.json")
CLAIM_FILE = "/run/flightradar/claim-code"
AIRPORTS_JSON = "/opt/flightradar/airports.json"
UI_FILE = "/opt/flightradar/setup-ui.html"

MAX_BODY = 64 * 1024
SESSION_TTL = 8 * 3600
SESSION_IDLE = 30 * 60
MAX_SESSIONS = 8

_sessions = {}          # sha256(token) -> {created, seen}
_lock = threading.Lock()
_fail = {"count": 0, "until": 0.0}


# ------------------------------------------------------------------ state

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        # An unreadable or corrupt state file must read as UNCLAIMED, never
        # as "locked out" -- otherwise a single bad write bricks the owner
        # out of their own device with no way back.
        return {"schema": 1, "claimed": False}


def save_state(st):
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    # 0660, not 0600: the root helper shares this directory by group so both
    # tiers can read it. See share_state_dir() in setupd.py for why.
    os.chmod(tmp, 0o660)
    os.replace(tmp, STATE_FILE)
    dfd = os.open(STATE_DIR, os.O_DIRECTORY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


# hashlib.scrypt needs OpenSSL 1.1+ and is absent from some Python builds.
# Preferred where present, but never depended on: a missing hash function at
# password-creation time would lock the owner out of their own device, which
# is a brick-class failure for the sake of a nicety. The algorithm is
# recorded per-record so existing passwords keep verifying either way.
HAVE_SCRYPT = hasattr(hashlib, "scrypt")


def hash_password(pw, salt=None):
    salt = salt or os.urandom(16)
    if HAVE_SCRYPT:
        h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return {"algo": "scrypt", "n": 2**14, "r": 8, "p": 1,
                "salt": salt.hex(), "hash": h.hex()}
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 600_000, dklen=32)
    return {"algo": "pbkdf2", "iters": 600_000,
            "salt": salt.hex(), "hash": h.hex()}


def verify_password(pw, rec):
    if not rec:
        return False
    try:
        salt = bytes.fromhex(rec["salt"])
        if rec.get("algo") == "scrypt":
            if not HAVE_SCRYPT:
                return False
            h = hashlib.scrypt(pw.encode(), salt=salt, n=rec["n"], r=rec["r"],
                               p=rec["p"], dklen=32)
        elif rec.get("algo") == "pbkdf2":
            h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt,
                                    rec["iters"], dklen=32)
        else:
            return False
    except Exception:
        return False
    return hmac.compare_digest(h.hex(), rec["hash"])


def claim_code():
    """Shown on the device's own screen; never served over HTTP.

    Behind lighttpd's proxy every request appears to come from 127.0.0.1, so
    a 'localhost only' HTTP route would have been readable by the entire LAN.
    The code is read from a file the on-screen console also reads.
    """
    try:
        with open(CLAIM_FILE) as f:
            return f.read().strip()
    except Exception:
        return None


# ------------------------------------------------------------- setupd link

def call_setupd(verb, params=None, timeout=120):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(SOCK_PATH)
        s.sendall((json.dumps({"verb": verb, "params": params or {}}) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        return json.loads(buf or b'{"ok":false,"code":"no_response"}')
    except FileNotFoundError:
        return {"ok": False, "code": "setupd_unavailable"}
    except socket.timeout:
        return {"ok": False, "code": "timeout"}
    except Exception as e:
        return {"ok": False, "code": "setupd_error", "detail": str(e)[:120]}
    finally:
        s.close()


# ---------------------------------------------------------------- sessions

def new_session():
    tok = secrets.token_urlsafe(32)
    now = time.time()
    with _lock:
        if len(_sessions) >= MAX_SESSIONS:
            oldest = min(_sessions, key=lambda k: _sessions[k]["seen"])
            _sessions.pop(oldest, None)
        _sessions[hashlib.sha256(tok.encode()).hexdigest()] = {"created": now, "seen": now}
    return tok


def valid_session(token):
    if not token:
        return False
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time.time()
    with _lock:
        s = _sessions.get(key)
        if not s:
            return False
        if now - s["created"] > SESSION_TTL or now - s["seen"] > SESSION_IDLE:
            _sessions.pop(key, None)
            return False
        s["seen"] = now
        return True


def drop_sessions():
    with _lock:
        _sessions.clear()


def throttled():
    """Exponential backoff, capped, always self-clearing.

    Never a permanent lockout: the owner forgetting their password must not
    require re-flashing the device.
    """
    return time.time() < _fail["until"]


def note_failure():
    _fail["count"] += 1
    if _fail["count"] >= 5:
        delay = min(900, 2 ** (_fail["count"] - 5))
        _fail["until"] = time.time() + delay


def note_success():
    _fail["count"] = 0
    _fail["until"] = 0.0


# -------------------------------------------------------------------- HTTP

SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def version_string(self):
        return "FlightRadar"

    def log_message(self, fmt, *args):
        # Never log the query string or body: they carry the WiFi password
        # and the Tailscale auth key.
        path = self.path.split("?", 1)[0]
        print(f"setup {self.command} {path}", flush=True)

    # -- helpers ---------------------------------------------------------

    def _send(self, code, obj=None, body=None, ctype="application/json"):
        payload = body if body is not None else json.dumps(obj or {}).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _err(self, code, token, message):
        self._send(code, {"error": {"code": token, "message": message}})

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if n > MAX_BODY:
            return None
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return None

    def _authed(self):
        auth = self.headers.get("Authorization") or ""
        return auth.startswith("Bearer ") and valid_session(auth[7:])

    def _public_blocked(self):
        """The gateway marks anything that came from the public tunnel.

        Belt and braces alongside LOCAL_ONLY_PATHS: if the gateway's filter
        were ever bypassed again, this still refuses the request.
        """
        return self.headers.get("X-FR-Public") is not None

    # -- routing ---------------------------------------------------------

    def do_GET(self):
        self._route()

    def do_POST(self):
        self._route()

    def do_HEAD(self):
        self._route()

    def _route(self):
        if self._public_blocked():
            self._send(404, {})
            return
        path = self.path.split("?", 1)[0].rstrip("/") or "/setup"
        st = load_state()

        if path in ("/setup", "/setup/index.html"):
            return self._serve_ui()
        if path == "/setup/api/hello":
            return self._send(200, {
                "product": "FlightRadar",
                "claimed": bool(st.get("claimed")),
                "steps": st.get("steps", {}),
                "hasScreen": claim_code() is not None,
            })
        if path == "/setup/api/claim" and self.command == "POST":
            return self._claim(st)
        if path == "/setup/api/login" and self.command == "POST":
            return self._login(st)

        # everything below requires a session
        if not self._authed():
            return self._err(401, "unauthenticated", "Sign in to continue.")

        if path == "/setup/api/status":
            return self._status(st)
        if path == "/setup/api/airports":
            return self._airports()
        if path == "/setup/api/wifi/scan":
            return self._proxy_verb("wifi_scan")
        if path == "/setup/api/wifi/connect" and self.command == "POST":
            return self._wifi_connect()
        if path == "/setup/api/wifi/confirm" and self.command == "POST":
            return self._proxy_verb("wifi_confirm")
        if path == "/setup/api/wifi/rollback" and self.command == "POST":
            return self._proxy_verb("wifi_rollback")
        if path == "/setup/api/location" and self.command == "POST":
            return self._location(st)
        if path == "/setup/api/airport" and self.command == "POST":
            return self._airport(st)
        if path == "/setup/api/tailscale/status":
            return self._proxy_verb("tailscale_status")
        if path == "/setup/api/tailscale/up" and self.command == "POST":
            return self._tailscale_up(st)
        if path == "/setup/api/tailscale/funnel" and self.command == "POST":
            b = self._body() or {}
            return self._proxy_verb("tailscale_funnel", {"enabled": bool(b.get("enabled"))})
        if path == "/setup/api/hotspot" and self.command == "POST":
            b = self._body() or {}
            return self._proxy_verb("hotspot_start" if b.get("on") else "hotspot_stop")
        if path == "/setup/api/password" and self.command == "POST":
            return self._change_password(st)
        if path == "/setup/api/reset" and self.command == "POST":
            return self._reset(st)
        if path == "/setup/api/reboot" and self.command == "POST":
            b = self._body() or {}
            if b.get("confirm") != "REBOOT":
                return self._err(400, "confirm_required", "Confirmation missing.")
            return self._proxy_verb("reboot")

        self._send(404, {})

    # -- handlers --------------------------------------------------------

    def _serve_ui(self):
        try:
            with open(UI_FILE, "rb") as f:
                self._send(200, body=f.read(), ctype="text/html; charset=utf-8")
        except FileNotFoundError:
            self._send(500, body=b"setup UI missing", ctype="text/plain")

    def _claim(self, st):
        if st.get("claimed"):
            return self._err(409, "already_claimed",
                             "This device has already been set up.")
        if throttled():
            return self._err(429, "too_many_attempts", "Too many tries. Wait a moment.")
        b = self._body() or {}
        code, pw = b.get("claimCode") or "", b.get("password") or ""
        expected = claim_code()
        if expected is None:
            return self._err(503, "no_claim_code",
                             "The device has not finished starting up.")
        if not hmac.compare_digest(code.strip().upper(), expected.strip().upper()):
            note_failure()
            return self._err(403, "bad_claim_code",
                             "That code does not match the one on the screen.")
        if not (8 <= len(pw) <= 128):
            return self._err(400, "weak_password", "Use at least 8 characters.")
        note_success()
        st.update({"schema": 1, "claimed": True,
                   "password": hash_password(pw),
                   "steps": st.get("steps", {})})
        save_state(st)
        return self._send(200, {"token": new_session(), "expiresIn": SESSION_TTL})

    def _login(self, st):
        if not st.get("claimed"):
            return self._err(409, "not_claimed", "This device has not been set up yet.")
        if throttled():
            return self._err(429, "too_many_attempts", "Too many tries. Wait a moment.")
        b = self._body() or {}
        if not verify_password(b.get("password") or "", st.get("password")):
            note_failure()
            return self._err(401, "bad_password", "That password was not accepted.")
        note_success()
        return self._send(200, {"token": new_session(), "expiresIn": SESSION_TTL})

    def _change_password(self, st):
        b = self._body() or {}
        if not verify_password(b.get("currentPassword") or "", st.get("password")):
            return self._err(401, "bad_password", "Current password was not accepted.")
        new = b.get("newPassword") or ""
        if not (8 <= len(new) <= 128):
            return self._err(400, "weak_password", "Use at least 8 characters.")
        st["password"] = hash_password(new)
        save_state(st)
        drop_sessions()
        return self._send(200, {"changed": True})

    def _proxy_verb(self, verb, params=None):
        r = call_setupd(verb, params)
        if r.get("ok"):
            return self._send(200, {"result": r.get("result")})
        return self._err(400, r.get("code", "failed"),
                         friendly(r.get("code", ""), r.get("detail", "")))

    def _wifi_connect(self):
        b = self._body()
        if b is None:
            return self._err(400, "bad_request", "Could not read that request.")
        return self._proxy_verb("wifi_connect", {
            "ssid": b.get("ssid"), "psk": b.get("psk"), "hidden": bool(b.get("hidden"))})

    def _location(self, st):
        b = self._body() or {}
        r = call_setupd("set_location", {"lat": b.get("lat"), "lon": b.get("lon")})
        if not r.get("ok"):
            return self._err(400, r.get("code", "failed"),
                             friendly(r.get("code", ""), r.get("detail", "")))
        st.setdefault("steps", {})["location"] = True
        st["location"] = r["result"]
        save_state(st)
        return self._send(200, {"result": r["result"],
                                "nearestAirports": nearest_airports(
                                    r["result"]["lat"], r["result"]["lon"])})

    def _airport(self, st):
        b = self._body() or {}
        r = call_setupd("set_airport", {"code": b.get("code"),
                                        "atcMount": b.get("atcMount", "")})
        if not r.get("ok"):
            return self._err(400, r.get("code", "failed"),
                             friendly(r.get("code", ""), r.get("detail", "")))
        st.setdefault("steps", {})["airport"] = True
        st["airport"] = r["result"]
        save_state(st)
        return self._send(200, {"result": r["result"]})

    def _tailscale_up(self, st):
        b = self._body() or {}
        r = call_setupd("tailscale_up", {
            "authKey": b.get("authKey"), "hostname": b.get("hostname"),
            "enableFunnel": bool(b.get("enableFunnel"))}, timeout=150)
        if not r.get("ok"):
            return self._err(400, r.get("code", "failed"),
                             friendly(r.get("code", ""), r.get("detail", "")))
        st.setdefault("steps", {})["remote"] = True
        save_state(st)
        return self._send(200, {"result": r["result"]})

    def _reset(self, st):
        """Both tiers require the current password to be re-entered.

        A live session is not enough: the destructive action should need the
        secret again, not merely an unlocked browser tab left open.
        """
        b = self._body() or {}
        if not verify_password(b.get("currentPassword") or "", st.get("password")):
            return self._err(401, "bad_password", "Password was not accepted.")
        scope = b.get("scope")
        if scope == "settings":
            if b.get("confirm") != "RESET":
                return self._err(400, "confirm_required", "Type RESET to confirm.")
            r = call_setupd("reset_settings", timeout=90)
        elif scope == "full":
            if b.get("confirm") != "ERASE":
                return self._err(400, "confirm_required", "Type ERASE to confirm.")
            r = call_setupd("reset_full", timeout=180)
        else:
            return self._err(400, "bad_scope", "Unknown reset type.")
        if not r.get("ok"):
            return self._err(400, r.get("code", "failed"),
                             friendly(r.get("code", ""), r.get("detail", "")))
        if scope == "full":
            # The state file is gone; drop every session so the device is
            # genuinely unclaimed rather than still driveable by this tab.
            drop_sessions()
        else:
            st.pop("location", None)
            st.pop("airport", None)
            st["steps"] = {k: v for k, v in (st.get("steps") or {}).items()
                           if k in ("password", "wifi", "remote")}
            save_state(st)
        return self._send(200, {"result": r["result"]})

    def _status(self, st):
        ts = call_setupd("tailscale_status")
        pend = call_setupd("pending")
        return self._send(200, {
            "claimed": bool(st.get("claimed")),
            "steps": st.get("steps", {}),
            "location": actual_location() or st.get("location"),
            "airport": actual_airport() or st.get("airport"),
            "remote": ts.get("result") if ts.get("ok") else None,
            "pendingChange": pend.get("result") if pend.get("ok") else None,
        })

    def _airports(self):
        try:
            with open(AIRPORTS_JSON) as f:
                data = json.load(f)
        except Exception:
            return self._err(500, "airports_missing", "Airport list unavailable.")
        q = ""
        if "?" in self.path:
            from urllib.parse import parse_qs, urlparse
            q = (parse_qs(urlparse(self.path).query).get("q") or [""])[0].strip().lower()
        rows = data["airports"]
        if q:
            rows = [a for a in rows
                    if q in a["code"].lower() or q in a["name"].lower()
                    or q in (a.get("city") or "").lower()]
        return self._send(200, {"airports": rows[:60], "total": len(rows)})


def nearest_airports(lat, lon, n=6):
    import math
    try:
        with open(AIRPORTS_JSON) as f:
            rows = json.load(f)["airports"]
    except Exception:
        return []
    out = []
    for a in rows:
        dy = (a["lat"] - lat) * 60.0
        dx = (a["lon"] - lon) * 60.0 * math.cos(math.radians(lat))
        out.append((math.hypot(dx, dy), a))
    out.sort(key=lambda t: t[0])
    return [dict(a, distanceNm=round(d, 1)) for d, a in out[:n]]


FRIENDLY = {
    "wifi_auth_failed": "That WiFi password was not accepted.",
    "wifi_ssid_not_found": "That network was not found. Is it in range?",
    "wifi_no_ip": "Joined the network but it did not provide an address.",
    "wifi_no_gateway": "Joined the network but there is no route out of it.",
    "wifi_gateway_unreachable": "Joined the network but the router did not respond.",
    "lat_out_of_range": "That looks like it is outside the continental United States.",
    "lon_out_of_range": "That looks like it is outside the continental United States.",
    "unknown_airport": "That airport is not in the built-in list.",
    "readsb_did_not_recover": "The receiver did not restart, so the previous location was restored.",
    "funnel_guard_failed": "Refusing to publish: the privacy filter is not working.",
    "bad_authkey": "That does not look like a Tailscale auth key.",
    "busy": "Another change is already in progress.",
    "setupd_unavailable": "The setup service is not running.",
    "ssid_leading_dash": "Network names starting with a dash are not supported.",
    "bad_atc_mount": "That does not look like a LiveATC feed name.",
    "bad_lat": "That latitude is not a number.",
    "bad_lon": "That longitude is not a number.",
    "readsb_unsafe_token": "The receiver's configuration file looks unsafe to edit; not changed.",
    "already_claimed": "This device has already been set up.",
    "timeout": "That took too long and was stopped.",
}


def friendly(code, detail=""):
    return FRIENDLY.get(code) or (detail or "That did not work.")


# ------------------------------------------------- on-screen onboarding tier
#
# The radar's own display is the only channel a recipient has before the
# device is on their network: no SSH, no LAN address, nothing. It has to be
# able to show them the hotspot name, its password, and the claim code.
#
# That information cannot go on the LAN-reachable API. Behind lighttpd's
# proxy every request appears to come from 127.0.0.1, so a "localhost only"
# check on the main port would have been readable by the whole network.
# Instead this is a SEPARATE listener bound to loopback and deliberately NOT
# proxied by lighttpd, so only software running on the device itself -- i.e.
# the kiosk browser -- can read it.
ONBOARD_LISTEN = ("127.0.0.1", 8090)


class OnboardHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def version_string(self):
        return "FlightRadar"

    def log_message(self, *a):
        pass  # this endpoint carries the claim code; never log it

    def do_POST(self):
        """Device-local setup actions, for the radar's own touchscreen.

        Unauthenticated BY DESIGN, and safe only because this listener is
        bound to loopback and is not proxied by lighttpd -- reaching it means
        already running on the device. Physical access is ownership here, the
        same assumption every appliance makes.

        It also has to be unauthenticated to be useful: this is the only
        recovery path for someone who has forgotten the admin password. If it
        demanded that password, a forgotten one would mean a dead unit.
        """
        path = self.path.split("?", 1)[0].rstrip("/")
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except Exception:
            return self._json(400, {"error": {"message": "Bad request."}})

        if path == "/onboard/wifi/scan":
            return self._verb("wifi_scan")
        if path == "/onboard/wifi/connect":
            r = call_setupd("wifi_connect", {"ssid": body.get("ssid"),
                                             "psk": body.get("psk")}, timeout=150)
            if r.get("ok"):
                call_setupd("wifi_confirm")
            return self._relay(r)
        if path == "/onboard/location":
            return self._verb("set_location", {"lat": body.get("lat"),
                                               "lon": body.get("lon")}, timeout=90)
        if path == "/onboard/airport":
            return self._verb("set_airport", {"code": body.get("code"),
                                              "atcMount": body.get("atcMount", "")})
        if path == "/onboard/password":
            # Setting the admin password from the device's own screen. No
            # claim code is required here: being able to reach this listener
            # already means being on the device, which is the same physical
            # proof the code exists to establish. Without this, a unit set up
            # entirely on-screen would stay unclaimed forever and keep
            # showing its first-run instructions.
            pw = body.get("password") or ""
            if not (8 <= len(pw) <= 128):
                return self._json(400, {"error": {"message": "Use at least 8 characters."}})
            st = load_state()
            st.update({"schema": 1, "claimed": True, "password": hash_password(pw)})
            st.setdefault("steps", {})["password"] = True
            save_state(st)
            drop_sessions()
            return self._json(200, {"result": {"claimed": True}})
        if path == "/onboard/hotspot":
            return self._verb("hotspot_start" if body.get("on") else "hotspot_stop",
                              timeout=90)
        if path == "/onboard/remote/start":
            return self._verb("tailscale_login_start",
                              {"hostname": body.get("hostname")}, timeout=60)
        if path == "/onboard/remote/status":
            return self._verb("tailscale_login_status", timeout=30)
        if path == "/onboard/remote/funnel":
            return self._verb("tailscale_funnel",
                              {"enabled": bool(body.get("enabled"))}, timeout=90)
        if path == "/onboard/reboot":
            # Restarting is recoverable in a way reset_full is not, so this
            # needs no typed word -- but it still takes a confirm token, so a
            # stray tap on a touchscreen can never reach it through a bare
            # POST. setupd deliberately exposes no shutdown verb, only this:
            # an appliance that powers itself off needs a physical visit.
            if body.get("confirm") != "REBOOT":
                return self._json(400, {"error": {"message": "Confirmation missing."}})
            return self._verb("reboot", timeout=30)
        if path == "/onboard/reset":
            # Erasing everything from the screen is the give-it-away path AND
            # the forgotten-password path, so it deliberately needs no
            # credential -- only the typed word, checked here as well as in
            # the UI so a stray tap can never reach it.
            if body.get("confirm") != "ERASE":
                return self._json(400, {"error": {"message": "Confirmation missing."}})
            return self._verb("reset_full", timeout=180)
        return self._json(404, {})

    def _verb(self, verb, params=None, timeout=120):
        return self._relay(call_setupd(verb, params, timeout))

    def _relay(self, r):
        if r.get("ok"):
            return self._json(200, {"result": r.get("result")})
        return self._json(400, {"error": {
            "code": r.get("code", "failed"),
            "message": friendly(r.get("code", ""), r.get("detail", ""))}})

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", self._allowed_origin())
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _origin_ok(origin):
        """Loopback origins only.

        The listener is already bound to loopback, so this is a second layer
        rather than the primary control -- it stops some other page loaded in
        the kiosk browser from reading the claim code. Any localhost port is
        accepted because the kiosk is served from :80 while diagnostics and
        forwarded sessions are not.
        """
        if not origin:
            return False
        from urllib.parse import urlparse
        try:
            h = urlparse(origin).hostname
        except Exception:
            return False
        return h in ("localhost", "127.0.0.1", "::1")

    def _allowed_origin(self):
        o = self.headers.get("Origin")
        return o if self._origin_ok(o) else "http://localhost"

    def do_OPTIONS(self):
        self._json(204, {})

    def do_GET(self):
        p = self.path.split("?", 1)[0].rstrip("/")
        if p == "/onboard/airports":
            try:
                with open(AIRPORTS_JSON) as f:
                    rows = json.load(f)["airports"]
            except Exception:
                return self._json(500, {"error": {"message": "Airport list missing."}})
            from urllib.parse import parse_qs, urlparse
            q = (parse_qs(urlparse(self.path).query).get("q") or [""])[0].strip().lower()
            if q:
                rows = [a for a in rows if q in a["code"].lower()
                        or q in a["name"].lower() or q in (a.get("city") or "").lower()]
            return self._json(200, {"airports": rows[:40]})
        if p not in ("/onboard", ""):
            self.send_error(404)
            return
        st = load_state()
        # Cache the setupd round-trips. Each one shells out to nmcli, so an
        # uncached /onboard costs a few hundred ms; without this, every extra
        # viewer of the page multiplies that cost on a device that has no
        # headroom to spare. Short enough that the setup screens still show
        # live values, long enough that polling is nearly free.
        hs, net, rem = _onboard_probe()
        body = json.dumps({
            "claimed": bool(st.get("claimed")),
            "claimCode": None if st.get("claimed") else claim_code(),
            "hotspot": hs.get("result") if hs.get("ok") else None,
            "addresses": lan_addresses(),
            "steps": st.get("steps", {}),
            "location": actual_location() or st.get("location"),
            "airport": actual_airport() or st.get("airport"),
            "network": net,
            "remote": rem,
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # The kiosk page is served from http://localhost/, so reading this
        # port is cross-origin. Only that origin is permitted.
        self.send_header("Access-Control-Allow-Origin", self._allowed_origin())
        self.end_headers()
        self.wfile.write(body)


_PROBE_TTL_S = 20
_probe_cache = {"at": 0.0, "value": None}
_probe_lock = threading.Lock()


def _onboard_probe():
    """(hotspot_info, net_status, tailscale_status), cached for _PROBE_TTL_S.

    All three shell out to nmcli/tailscale. They describe things that change
    on the order of days, so re-running them for every request is pure cost.
    """
    with _probe_lock:
        now = time.monotonic()
        if _probe_cache["value"] is not None and now - _probe_cache["at"] < _PROBE_TTL_S:
            return _probe_cache["value"]
        unwrap = lambda r: r.get("result") if r.get("ok") else None
        value = (call_setupd("hotspot_info"),
                 unwrap(call_setupd("net_status")),
                 unwrap(call_setupd("tailscale_status")))
        _probe_cache.update(at=now, value=value)
        return value


def actual_location():
    """The coordinates readsb is really using, not what our state file recalls.

    The two can disagree: a unit configured before this service existed, or
    one whose state file was reset, still has a perfectly good location in
    /etc/default/readsb. Reporting "Not set" for a working configuration
    would invite the owner to re-enter something that was never wrong.
    """
    try:
        with open("/etc/default/readsb") as f:
            body = f.read()
    except Exception:
        return None
    lat = re.search(r"--lat[= ]([-\d.]+)", body)
    lon = re.search(r"--lon[= ]([-\d.]+)", body)
    if not (lat and lon):
        return None
    try:
        return {"lat": float(lat.group(1)), "lon": float(lon.group(1))}
    except ValueError:
        return None


def actual_airport():
    """Whatever the web app is actually rendering, from its own config."""
    try:
        with open("/var/www/html/config.json") as f:
            return (json.load(f) or {}).get("airport")
    except Exception:
        return None


def lan_addresses():
    """Addresses a phone could actually reach the setup page on."""
    out = []
    try:
        import subprocess
        p = subprocess.run(["/usr/bin/hostname", "-I"], capture_output=True, timeout=5)
        out = [a for a in p.stdout.decode().split()
               if ":" not in a and not a.startswith("127.")]
    except Exception:
        pass
    return out


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    threading.Thread(
        target=lambda: Server(ONBOARD_LISTEN, OnboardHandler).serve_forever(),
        daemon=True,
    ).start()
    Server(LISTEN, Handler).serve_forever()
