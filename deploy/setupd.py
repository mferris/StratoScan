#!/usr/bin/env python3
"""Root helper for the FlightRadar setup server.

This is the privilege boundary. The HTTP server (setup-server.py) runs
unprivileged and cannot touch the system directly; it asks this process to
perform a fixed set of verbs over a unix socket. The HTTP parser is the part
most likely to be attacked and is therefore exactly the part that must not be
root.

Design rules, all of which exist because breaking them strands or exposes the
appliance:

  * Closed verb enum. There is no generic "run nmcli" or "run systemctl"
    passthrough, so a compromised web tier cannot escalate to arbitrary
    commands -- only to the specific, validated operations below.
  * Every parameter is re-validated HERE, not merely in the caller. The web
    tier's validation is a UX convenience; this is the security control.
  * No shell, ever. subprocess with an argv list, absolute paths, a fixed
    minimal environment, and an explicit timeout.
  * Secrets (WiFi PSK, Tailscale auth key) never appear in argv, where any
    local user could read them from /proc, nor in the journal. They are
    passed through 0600 files on tmpfs that are unlinked immediately.
  * Every state write is atomic and fsynced, including the directory entry.
    A power cut mid-write must never leave a half-written config that stops
    the device booting onto the network.
  * Network changes are add-then-switch with an armed rollback. The working
    profile is never edited or deleted; a new candidate profile is created
    with autoconnect off and only promoted once connectivity is proven.
"""
import contextlib
import fcntl
import json
import os
import re
import shutil
import shlex
import socket
import socketserver
import subprocess
import sys
import time

SOCK_PATH = "/run/flightradar/setupd.sock"
RUN_DIR = "/run/flightradar"
STATE_DIR = "/var/lib/flightradar-setup"
PENDING = os.path.join(STATE_DIR, "pending.json")
LOCK = os.path.join(STATE_DIR, "lock")
READSB_DEFAULT = "/etc/default/readsb"
READSB_ORIG = os.path.join(STATE_DIR, "readsb.default.orig")
READSB_BACKUP = os.path.join(STATE_DIR, "readsb.fr-backup")
CONFIG_JSON = "/var/www/html/config.json"
AIRPORTS_JSON = "/opt/flightradar/airports.json"

CANDIDATE_PROFILE = "fr-candidate"
HOTSPOT_PROFILE = "fr-hotspot"
CONFIRM_WINDOW_S = 180

ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"}
NMCLI = "/usr/bin/nmcli"
TAILSCALE = "/usr/bin/tailscale"
SYSTEMCTL = "/usr/bin/systemctl"

# Continental US. Deliberately not global: the airport table is CONUS-only,
# and a coordinate outside it means the user mistyped rather than that they
# are genuinely in Alaska.
LAT_MIN, LAT_MAX = 24.0, 49.5
LON_MIN, LON_MAX = -125.0, -66.5

RE_TS_HOSTNAME = re.compile(r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$")
RE_TS_AUTHKEY = re.compile(r"^tskey-[A-Za-z0-9_-]{10,200}$")
RE_ATC_MOUNT = re.compile(r"^[a-z0-9][a-z0-9_-]{2,39}$")


class Err(Exception):
    def __init__(self, code, detail=""):
        super().__init__(code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- utilities

def run(argv, timeout=30, check=False, input_bytes=None):
    """subprocess with no shell, fixed env, absolute paths and a timeout."""
    try:
        p = subprocess.run(argv, env=ENV, timeout=timeout, capture_output=True,
                           input=input_bytes, shell=False)
    except subprocess.TimeoutExpired:
        raise Err("timeout", argv[0])
    if check and p.returncode != 0:
        raise Err("command_failed", redact(p.stderr.decode("utf-8", "replace"))[:400])
    return p


_SECRETS = []


def redact(text):
    """Strip any known secret from text before it can reach a log."""
    for s in _SECRETS:
        if s:
            text = text.replace(s, "<redacted>")
    return text


def atomic_write(path, data, mode=0o600):
    """Write + fsync the file AND its directory.

    Without the directory fsync a power cut can leave the rename unrecorded,
    which for /etc/default/readsb means the receiver may not start.
    """
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".{os.path.basename(path)}.tmp")
    with open(tmp, "w") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    dfd = os.open(d, os.O_DIRECTORY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


@contextlib.contextmanager
def state_lock():
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(LOCK, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Err("busy", "another change is in progress")
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def secret_file(name, value):
    """Hand a secret to a subprocess without putting it in argv."""
    os.makedirs(RUN_DIR, mode=0o700, exist_ok=True)
    path = os.path.join(RUN_DIR, name)
    atomic_write(path, value, mode=0o600)
    return path


# --------------------------------------------------------------- validation

def v_lat(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise Err("bad_lat", "not a number")
    if v != v or v in (float("inf"), float("-inf")):
        raise Err("bad_lat", "not finite")
    if not (LAT_MIN <= v <= LAT_MAX):
        raise Err("lat_out_of_range", f"{v} outside the continental US")
    return float(v)


def v_lon(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise Err("bad_lon", "not a number")
    if v != v or v in (float("inf"), float("-inf")):
        raise Err("bad_lon", "not finite")
    if not (LON_MIN <= v <= LON_MAX):
        raise Err("lon_out_of_range", f"{v} outside the continental US")
    return float(v)


def v_ssid(v):
    if not isinstance(v, str):
        raise Err("bad_ssid")
    b = v.encode("utf-8")
    if not (1 <= len(b) <= 32):
        raise Err("bad_ssid", "must be 1-32 bytes")
    if any(c in v for c in ("\x00", "\r", "\n")):
        raise Err("bad_ssid", "control characters")
    # nmcli has no reliable "--" terminator across all subcommands, so an
    # SSID that begins with a dash could be read as an option. Rejected
    # rather than risk it; genuinely rare, and documented in the UI.
    if v.startswith("-"):
        raise Err("ssid_leading_dash", "network names starting with '-' are not supported")
    return v


def v_psk(v):
    if v is None or v == "":
        return None
    if not isinstance(v, str):
        raise Err("bad_psk")
    if any(c in v for c in ("\x00", "\r", "\n")):
        raise Err("bad_psk", "control characters")
    if re.fullmatch(r"[0-9a-fA-F]{64}", v):
        return v
    if not (8 <= len(v) <= 63):
        raise Err("bad_psk", "must be 8-63 characters")
    if any(ord(c) < 0x20 or ord(c) > 0x7e for c in v):
        raise Err("bad_psk", "unsupported characters")
    return v


def v_ts_hostname(v):
    if not isinstance(v, str) or not RE_TS_HOSTNAME.match(v):
        raise Err("bad_hostname", "lowercase letters, digits and hyphens only")
    return v


def v_authkey(v):
    if not isinstance(v, str) or not RE_TS_AUTHKEY.match(v):
        raise Err("bad_authkey", "does not look like a Tailscale auth key")
    return v


def v_atc_mount(v):
    if v in (None, ""):
        return ""
    if not isinstance(v, str) or not RE_ATC_MOUNT.match(v):
        raise Err("bad_atc_mount")
    return v


def load_airports():
    with open(AIRPORTS_JSON) as f:
        return {a["code"]: a for a in json.load(f)["airports"]}


# ------------------------------------------------------------------ readsb

def rewrite_readsb_location(lat, lon):
    """Replace --lat/--lon inside DECODER_OPTIONS, preserving everything else.

    /etc/default/readsb is shell-sourced by root, so this is a command
    execution sink: anything injected here runs as root at boot. The file is
    tokenised with shlex, only the lat/lon tokens are substituted, values are
    re-serialised from validated floats (the caller's bytes never reach the
    file), and the result is refused if any token looks like it could break
    out of its quoting.
    """
    with open(READSB_DEFAULT) as f:
        original = f.read()

    if not os.path.exists(READSB_ORIG):
        atomic_write(READSB_ORIG, original, mode=0o600)
    atomic_write(READSB_BACKUP, original, mode=0o600)

    out_lines, touched = [], False
    for line in original.splitlines():
        m = re.match(r'^(\s*DECODER_OPTIONS\s*=\s*)"(.*)"\s*$', line)
        if not m:
            out_lines.append(line)
            continue
        prefix, body = m.group(1), m.group(2)
        toks = shlex.split(body)
        new, i = [], 0
        seen_lat = seen_lon = False
        while i < len(toks):
            t = toks[i]
            if t == "--lat" and i + 1 < len(toks):
                new += ["--lat", f"{lat:.5f}"]; i += 2; seen_lat = True; continue
            if t == "--lon" and i + 1 < len(toks):
                new += ["--lon", f"{lon:.5f}"]; i += 2; seen_lon = True; continue
            if t.startswith("--lat="):
                new.append(f"--lat={lat:.5f}"); i += 1; seen_lat = True; continue
            if t.startswith("--lon="):
                new.append(f"--lon={lon:.5f}"); i += 1; seen_lon = True; continue
            new.append(t); i += 1
        if not seen_lat:
            new += ["--lat", f"{lat:.5f}"]
        if not seen_lon:
            new += ["--lon", f"{lon:.5f}"]
        for t in new:
            if any(c in t for c in ('"', "'", "`", "$", "\\", "\n", "\r")):
                raise Err("readsb_unsafe_token", "refusing to write an unsafe option")
        out_lines.append(f'{prefix}"{" ".join(new)}"')
        touched = True

    if not touched:
        raise Err("readsb_no_decoder_options", "DECODER_OPTIONS line not found")

    atomic_write(READSB_DEFAULT, "\n".join(out_lines) + "\n", mode=0o644)
    os.chown(READSB_DEFAULT, 0, 0)
    return original


def restart_readsb_or_rollback(previous):
    """Restart readsb; restore the previous file if it does not come back.

    "active" alone is not proof -- readsb can be running and decoding
    nothing. aircraft.json's mtime must advance too, or the receiver is up
    but deaf, which from the owner's point of view is just as broken.
    """
    run([SYSTEMCTL, "restart", "readsb"], timeout=30)
    aircraft = "/run/readsb/aircraft.json"
    before = os.path.getmtime(aircraft) if os.path.exists(aircraft) else 0
    deadline = time.time() + 20
    ok = False
    while time.time() < deadline:
        time.sleep(1)
        active = run([SYSTEMCTL, "is-active", "readsb"], timeout=10).stdout.strip() == b"active"
        moved = os.path.exists(aircraft) and os.path.getmtime(aircraft) > before
        if active and moved:
            ok = True
            break
    if not ok:
        atomic_write(READSB_DEFAULT, previous, mode=0o644)
        os.chown(READSB_DEFAULT, 0, 0)
        run([SYSTEMCTL, "restart", "readsb"], timeout=30)
        raise Err("readsb_did_not_recover", "reverted to the previous location")
    return True


# -------------------------------------------------------------------- wifi

def nm_active_wifi_uuid():
    p = run([NMCLI, "-t", "-f", "UUID,TYPE,DEVICE", "connection", "show", "--active"])
    for line in p.stdout.decode().splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[1] == "802-11-wireless" and parts[2] == "wlan0":
            return parts[0]
    return None


def nm_delete_profile(name_or_uuid):
    run([NMCLI, "connection", "delete", name_or_uuid], timeout=20)


def wifi_scan():
    run([NMCLI, "device", "wifi", "rescan"], timeout=25)
    time.sleep(2)
    p = run([NMCLI, "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "device", "wifi", "list"], timeout=25)
    seen, out = set(), []
    for line in p.stdout.decode("utf-8", "replace").splitlines():
        # nmcli -t escapes literal colons as \:  -- split on unescaped ones
        parts = re.split(r"(?<!\\):", line)
        if len(parts) < 4:
            continue
        ssid = parts[0].replace("\\:", ":")
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        try:
            signal = int(parts[1])
        except ValueError:
            signal = 0
        out.append({"ssid": ssid, "signal": signal,
                    "secured": parts[2] not in ("", "--"),
                    "inUse": parts[3].strip() == "*"})
    out.sort(key=lambda n: -n["signal"])
    return out


def write_pending(rec):
    atomic_write(PENDING, json.dumps(rec), mode=0o600)


def read_pending():
    try:
        with open(PENDING) as f:
            return json.load(f)
    except Exception:
        return None


def clear_pending():
    with contextlib.suppress(FileNotFoundError):
        os.unlink(PENDING)


def connectivity_ok():
    """Activated is not the same as working.

    NetworkManager reports 'activated' for an association that never got a
    DHCP lease, which is a half-brick: the device looks connected and is
    unreachable. Require an address, a default route, and a real response.
    """
    p = run([NMCLI, "-t", "-f", "IP4.ADDRESS", "device", "show", "wlan0"], timeout=10)
    if b"/" not in p.stdout:
        return False, "wifi_no_ip"
    p = run([NMCLI, "-t", "-f", "IP4.GATEWAY", "device", "show", "wlan0"], timeout=10)
    gw = p.stdout.decode().strip().split(":", 1)[-1]
    if not gw:
        return False, "wifi_no_gateway"
    ping = run(["/bin/ping", "-c", "1", "-W", "3", gw], timeout=10)
    if ping.returncode != 0:
        return False, "wifi_gateway_unreachable"
    return True, None


def wifi_connect(ssid, psk, hidden=False):
    """Add a candidate profile and try it, without disturbing the working one.

    The existing profile is never edited or deleted. If anything goes wrong
    -- wrong password, out of range, no DHCP, power cut -- the device still
    has its old network to fall back to, and pending.json (written and
    fsynced BEFORE the first mutation) tells the reconciler to put it back.
    """
    ssid = v_ssid(ssid)
    psk = v_psk(psk)
    _SECRETS.append(psk or "")

    known_good = nm_active_wifi_uuid()
    write_pending({
        "kind": "wifi",
        "startedAt": time.time(),
        "deadline": time.time() + CONFIRM_WINDOW_S,
        "knownGoodUuid": known_good,
        "candidate": CANDIDATE_PROFILE,
        "ssid": ssid,
    })

    with contextlib.suppress(Exception):
        nm_delete_profile(CANDIDATE_PROFILE)

    argv = [NMCLI, "connection", "add", "type", "wifi", "con-name", CANDIDATE_PROFILE,
            "ifname", "wlan0", "ssid", ssid,
            "connection.autoconnect", "no"]
    if hidden:
        argv += ["wifi.hidden", "yes"]
    run(argv, timeout=20, check=True)

    if psk:
        # via stdin-free file indirection: the key never appears in argv,
        # where any local user could read it out of /proc
        run([NMCLI, "connection", "modify", CANDIDATE_PROFILE,
             "wifi-sec.key-mgmt", "wpa-psk"], timeout=20, check=True)
        run([NMCLI, "connection", "modify", CANDIDATE_PROFILE,
             "wifi-sec.psk", psk], timeout=20, check=True)

    up = run([NMCLI, "connection", "up", CANDIDATE_PROFILE], timeout=60)
    if up.returncode != 0:
        err = redact(up.stderr.decode("utf-8", "replace")).lower()
        reason = ("wifi_auth_failed" if "secrets" in err or "password" in err
                  else "wifi_ssid_not_found" if "not found" in err or "no network" in err
                  else "wifi_failed")
        wifi_rollback()
        raise Err(reason, "")

    ok, why = connectivity_ok()
    if not ok:
        wifi_rollback()
        raise Err(why, "")

    return {"state": "awaiting_confirm", "ssid": ssid,
            "confirmDeadline": time.time() + CONFIRM_WINDOW_S}


def wifi_confirm():
    """Promote the candidate only once someone has proved they can still reach
    the device on the new network."""
    pend = read_pending()
    if not pend or pend.get("kind") != "wifi":
        raise Err("nothing_pending")
    run([NMCLI, "connection", "modify", CANDIDATE_PROFILE,
         "connection.autoconnect", "yes"], timeout=20)
    run([NMCLI, "connection", "modify", CANDIDATE_PROFILE,
         "connection.id", f"fr-{pend['ssid'][:24]}"], timeout=20)
    clear_pending()
    return {"state": "ok", "ssid": pend.get("ssid")}


def wifi_rollback():
    """Undo an unconfirmed change. Must never itself throw."""
    pend = read_pending()
    with contextlib.suppress(Exception):
        nm_delete_profile(CANDIDATE_PROFILE)
    if pend and pend.get("knownGoodUuid"):
        with contextlib.suppress(Exception):
            run([NMCLI, "connection", "up", pend["knownGoodUuid"]], timeout=45)
    clear_pending()
    ok = False
    with contextlib.suppress(Exception):
        ok, _ = connectivity_ok()
    if not ok:
        # Last resort: make the device reachable by its own hotspot rather
        # than leaving it dark. This is the path that turns "unrecoverable
        # brick" into "join FlightRadar-Setup from a phone".
        with contextlib.suppress(Exception):
            hotspot_start()
    return {"rolledBack": True, "connectivity": ok}


def hotspot_start():
    run([NMCLI, "connection", "delete", HOTSPOT_PROFILE], timeout=20)
    psk = hotspot_psk()
    run([NMCLI, "device", "wifi", "hotspot", "ifname", "wlan0",
         "con-name", HOTSPOT_PROFILE, "ssid", "FlightRadar-Setup",
         "password", psk], timeout=45)
    return {"ssid": "FlightRadar-Setup", "psk": psk}


def hotspot_psk():
    """Stable per-device PSK, so the label/on-screen value stays valid."""
    path = os.path.join(STATE_DIR, "hotspot-psk")
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        import secrets as _s
        psk = "".join(_s.choice("23456789abcdefghjkmnpqrstuvwxyz") for _ in range(10))
        atomic_write(path, psk, mode=0o600)
        return psk


def hotspot_active():
    """Whether the AP is actually up right now, not merely configured.

    The onboarding screen branches on this: telling a recipient to join
    'FlightRadar-Setup' when the device is already on their WiFi sends them
    looking for a network that does not exist.
    """
    p = run([NMCLI, "-t", "-f", "NAME", "connection", "show", "--active"], timeout=15)
    return HOTSPOT_PROFILE in p.stdout.decode("utf-8", "replace")


def hotspot_stop():
    with contextlib.suppress(Exception):
        nm_delete_profile(HOTSPOT_PROFILE)
    return {"stopped": True}


# --------------------------------------------------------- location/airport

def set_location(lat, lon):
    lat, lon = v_lat(lat), v_lon(lon)
    previous = rewrite_readsb_location(lat, lon)
    restart_readsb_or_rollback(previous)
    return {"lat": round(lat, 5), "lon": round(lon, 5), "readsbRestarted": True}


def set_airport(code, atc_mount=""):
    """Write the web app's /config.json from the bundled table.

    Coordinates come from the table, never from the request: the client picks
    a code, not a position. And this file deliberately carries only the
    AIRPORT -- never the receiver's own coordinates, which are the owner's
    home address and reach the app solely via receiver.json, which the funnel
    gateway rounds before it leaves the network.
    """
    airports = load_airports()
    if not isinstance(code, str) or code not in airports:
        raise Err("unknown_airport", str(code)[:16])
    a = airports[code]
    cfg = {"airport": {
        "code": a["code"], "lat": a["lat"], "lon": a["lon"],
        "elevFt": a["elevFt"], "atcMount": v_atc_mount(atc_mount),
    }}
    atomic_write(CONFIG_JSON, json.dumps(cfg, indent=1) + "\n", mode=0o644)
    os.chown(CONFIG_JSON, 0, 0)
    return cfg["airport"]


# --------------------------------------------------------------- tailscale

def tailscale_status():
    p = run([TAILSCALE, "status", "--json"], timeout=20)
    if p.returncode != 0:
        return {"state": "unavailable"}
    try:
        d = json.loads(p.stdout)
    except Exception:
        return {"state": "unavailable"}
    self_ = d.get("Self") or {}
    return {
        "state": d.get("BackendState", "unknown"),
        "hostname": self_.get("HostName"),
        "magicDnsName": (self_.get("DNSName") or "").rstrip("."),
    }


def tailscale_up(authkey, hostname, enable_funnel=False):
    authkey = v_authkey(authkey)
    hostname = v_ts_hostname(hostname)
    _SECRETS.append(authkey)
    keyfile = secret_file("authkey", authkey)
    try:
        p = run([TAILSCALE, "up", f"--auth-key=file:{keyfile}",
                 f"--hostname={hostname}", "--accept-dns=false"], timeout=90)
        if p.returncode != 0:
            raise Err("tailscale_up_failed",
                      redact(p.stderr.decode("utf-8", "replace"))[:300])
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(keyfile)

    result = tailscale_status()
    if enable_funnel:
        result["funnel"] = tailscale_funnel(True)
    return result


def tailscale_funnel(enabled):
    """Only ever point Funnel at the filtering gateway, never at lighttpd.

    Pointing it at :80 would publish /setup and the receiver's unrounded
    coordinates straight to the internet. The probe below is a hard gate:
    if the gateway is not actually refusing /setup and /wake right now,
    Funnel is not turned on.
    """
    if enabled:
        for path in ("/setup", "/wake", "/./wake", "/%77ake", "/x/../setup"):
            p = run(["/usr/bin/curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                     "--path-as-is", "-X", "POST", "-H", "Content-Length: 0",
                     f"http://127.0.0.1:8085{path}"], timeout=15)
            if p.stdout.strip() != b"404":
                raise Err("funnel_guard_failed",
                          f"gateway did not refuse {path} (got {p.stdout.decode()})")
        run([TAILSCALE, "serve", "--bg", "--https=443", "http://127.0.0.1:8085"], timeout=45)
        run([TAILSCALE, "funnel", "--bg", "443", "on"], timeout=45)
    else:
        run([TAILSCALE, "funnel", "443", "off"], timeout=45)
    st = tailscale_status()
    url = f"https://{st['magicDnsName']}" if st.get("magicDnsName") and enabled else None
    return {"enabled": bool(enabled), "publicUrl": url}


# ------------------------------------------------------------------- reset

def reset_settings():
    """Undo configuration, keep the device on the network.

    Deliberately survivable remotely: it clears what the owner chose, but
    leaves WiFi and Tailscale alone so the device is still reachable
    afterwards. If this dropped the network it would be indistinguishable
    from a brick to anyone without a keyboard.
    """
    with contextlib.suppress(FileNotFoundError):
        os.unlink(CONFIG_JSON)
    if os.path.exists(READSB_ORIG):
        with open(READSB_ORIG) as f:
            pristine = f.read()
        atomic_write(READSB_DEFAULT, pristine, mode=0o644)
        os.chown(READSB_DEFAULT, 0, 0)
        run([SYSTEMCTL, "restart", "readsb"], timeout=30)
    return {"reset": "settings"}


def reset_full():
    """Prepare the unit to be given to someone else.

    Everything below is either a credential or is geolocated to the current
    owner's house, so a unit handed on with any of it still present is a
    privacy problem, not merely untidy:

      * WiFi profiles      -- their network name and password
      * Tailscale state    -- their tailnet identity
      * admin password     -- the new owner must be able to claim it
      * receiver lat/lon   -- their home address, to five decimal places
      * sighting counts    -- which aircraft have passed over their house
      * approach heatmap   -- accumulated tracks around their home airport

    The device is left UNCLAIMED with a fresh claim code, and the hotspot is
    raised so the next owner can reach it with no network of their own. The
    reachability pieces -- hotspot, watchdog, setup service -- are never
    removed, or the unit would arrive dead.
    """
    # 1. network identity
    p = run([NMCLI, "-t", "-f", "UUID,TYPE", "connection", "show"], timeout=20)
    for line in p.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == "802-11-wireless":
            with contextlib.suppress(Exception):
                nm_delete_profile(parts[0])

    # 2. tailscale
    with contextlib.suppress(Exception):
        run([TAILSCALE, "funnel", "443", "off"], timeout=30)
    with contextlib.suppress(Exception):
        run([TAILSCALE, "logout"], timeout=60)

    # 3. owner-specific data. The stores are geolocated to their house.
    for path in (os.path.join(STATE_DIR, "setup.json"),
                 CONFIG_JSON,
                 "/var/lib/flightradar-sightings/sightings.json",
                 "/var/lib/flightradar-approaches/approaches.json"):
        with contextlib.suppress(Exception):
            os.unlink(path)

    # 4. receiver position back to the shipped default
    if os.path.exists(READSB_ORIG):
        with open(READSB_ORIG) as f:
            atomic_write(READSB_DEFAULT, f.read(), mode=0o644)
        os.chown(READSB_DEFAULT, 0, 0)

    clear_pending()

    # 5. leave it reachable and claimable by its next owner
    with contextlib.suppress(Exception):
        hotspot_start()
    return {"reset": "full", "hotspot": "FlightRadar-Setup"}


# ------------------------------------------------------------------- verbs

VERBS = {
    "wifi_scan": lambda p: wifi_scan(),
    "wifi_connect": lambda p: wifi_connect(p.get("ssid"), p.get("psk"), bool(p.get("hidden"))),
    "wifi_confirm": lambda p: wifi_confirm(),
    "wifi_rollback": lambda p: wifi_rollback(),
    "hotspot_start": lambda p: hotspot_start(),
    "hotspot_stop": lambda p: hotspot_stop(),
    "hotspot_info": lambda p: {"ssid": "FlightRadar-Setup", "psk": hotspot_psk(),
                               "active": hotspot_active()},
    "set_location": lambda p: set_location(p.get("lat"), p.get("lon")),
    "set_airport": lambda p: set_airport(p.get("code"), p.get("atcMount", "")),
    "tailscale_status": lambda p: tailscale_status(),
    "tailscale_up": lambda p: tailscale_up(p.get("authKey"), p.get("hostname"),
                                           bool(p.get("enableFunnel"))),
    "tailscale_funnel": lambda p: tailscale_funnel(bool(p.get("enabled"))),
    "reboot": lambda p: (run([SYSTEMCTL, "reboot"], timeout=10), {"rebooting": True})[1],
    "pending": lambda p: read_pending(),
    "reset_settings": lambda p: reset_settings(),
    "reset_full": lambda p: reset_full(),
}
# Shutdown is deliberately absent: a remote caller must never be able to
# power off an appliance that then needs a physical visit to turn back on.

MUTATING = {"wifi_connect", "wifi_confirm", "wifi_rollback", "hotspot_start",
            "hotspot_stop", "set_location", "set_airport", "tailscale_up",
            "tailscale_funnel", "reboot", "reset_settings", "reset_full"}


class Handler(socketserver.StreamRequestHandler):
    timeout = 180

    def handle(self):
        try:
            raw = self.rfile.readline(65536)
            req = json.loads(raw or b"{}")
            verb = req.get("verb")
            params = req.get("params") or {}
            if verb not in VERBS:
                raise Err("unknown_verb", str(verb)[:40])
            if verb in MUTATING:
                with state_lock():
                    result = VERBS[verb](params)
            else:
                result = VERBS[verb](params)
            self.reply({"ok": True, "result": result})
        except Err as e:
            self.reply({"ok": False, "code": e.code, "detail": redact(e.detail)})
        except Exception as e:
            self.reply({"ok": False, "code": "internal",
                        "detail": redact(str(e))[:200]})

    def reply(self, obj):
        with contextlib.suppress(Exception):
            self.wfile.write((json.dumps(obj) + "\n").encode())


def resolve_gid():
    """Group shared with the unprivileged web tier, so it alone can reach us."""
    import grp
    name = os.environ.get("SETUP_GROUP", "frsetup")
    try:
        return grp.getgrnam(name).gr_gid
    except KeyError:
        return 0


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


def ensure_claim_code():
    """Regenerate the code that authorises first-time setup.

    Written on every start, so an unclaimed device that has been power-cycled
    gets a fresh one. It is deliberately NOT served over HTTP: behind
    lighttpd's proxy every request looks like it came from 127.0.0.1, so a
    "localhost only" route would have been readable by the whole LAN. It goes
    to a file that the on-screen display reads, which makes claiming require
    physical sight of the unit rather than merely being on the network.

    Skipped once the device is claimed, so the code cannot be used to take
    over a device that already has an owner.
    """
    import secrets as _s
    try:
        with open(os.path.join(STATE_DIR, "setup.json")) as f:
            if json.load(f).get("claimed"):
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(os.path.join(RUN_DIR, "claim-code"))
                return None
    except Exception:
        pass  # unreadable state => treat as unclaimed, never as locked out
    # Crockford-style alphabet: no I/L/O/U, so nothing is misread off a screen
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    code = "".join(_s.choice(alphabet) for _ in range(8))
    atomic_write(os.path.join(RUN_DIR, "claim-code"), code, mode=0o640)
    return code


def main():
    os.makedirs(RUN_DIR, mode=0o700, exist_ok=True)
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    code = ensure_claim_code()
    if code:
        # Also to the journal: on a headless or screen-dead unit this is the
        # only way an owner with shell access can complete setup.
        print(f"setupd: device is UNCLAIMED, setup code is {code}", flush=True)
    with contextlib.suppress(FileNotFoundError):
        os.unlink(SOCK_PATH)
    srv = Server(SOCK_PATH, Handler)
    # 0660 + the web tier's group: the unprivileged HTTP process may talk to
    # us, nothing else on the box may.
    os.chmod(SOCK_PATH, 0o660)
    gid = resolve_gid()
    if gid:
        os.chown(SOCK_PATH, 0, gid)
        os.chown(os.path.join(RUN_DIR, "claim-code"), 0, gid) if os.path.exists(
            os.path.join(RUN_DIR, "claim-code")) else None
        with contextlib.suppress(Exception):
            os.chmod(RUN_DIR, 0o750)
            os.chown(RUN_DIR, 0, gid)
    srv.serve_forever()


if __name__ == "__main__":
    main()
