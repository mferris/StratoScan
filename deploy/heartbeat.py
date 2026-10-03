#!/usr/bin/env python3
"""
Opt-in health reports from this unit to the StratoScan relay (relay/).

A gifted unit lives in someone else's house, and until now the only way to
learn it had died was for them to mention it. With the owner's consent, this
sends a small report every REPORT_EVERY_S: software version, uptime,
receiver health, storage wear, clock battery, temperature. Never a location,
hostname, network address or anything about what was seen overhead; the
relay also refuses any report carrying a location field.

Identity: an Ed25519 key generated on this unit at first use, readable by
root only. Its public key IS the unit's id, so no shared or fleet-wide secret
is baked into images. Requests are signed exactly as relay/src/auth.js
verifies them.

  heartbeat.py status   print the report this unit would send (no network)
  heartbeat.py send     send one now if enabled (ignores the schedule)
  maybe_send()          called by net-watchdog.py every run; sends when due

The radar never depends on any of this: a unit that cannot reach the relay,
or has reporting off, works exactly as before.
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

# The maintainer's relay (relay/, deployed on Cloudflare). Reporting still
# does nothing unless the owner turns it on in the setup page.
RELAY_URL = os.environ.get("STRATOSCAN_RELAY_URL", "https://relay.stratoscan.io")
STATE_DIR = os.environ.get("STRATOSCAN_RELAY_STATE", "/var/lib/stratoscan-relay")
KEY_PATH = os.path.join(STATE_DIR, "unit.key")
CONFIG = os.path.join(STATE_DIR, "heartbeat.json")    # {"enabled": bool}
LAST = os.path.join(STATE_DIR, "last-report.json")
IO_SNAPSHOT = os.path.join(STATE_DIR, "io-snapshot.json")   # sectors written at the last report
FLEET = os.path.join(STATE_DIR, "fleet.json")    # {"name", "joined", "health_was"} while in a fleet
SETUP_HELLO = "http://127.0.0.1:8086/setup/api/hello"     # the radar's name
VISITS_URL = "http://127.0.0.1:8087/visits"               # the public page's visit counts
OTA_STATE = "/var/lib/stratoscan-ota"
REPORT_EVERY_S = 6 * 3600
RETRY_AFTER_FAILURE_S = 30 * 60
TIMEOUT_S = 10


def b64url(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


# ---- identity -------------------------------------------------------------

def load_key(create=True):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    try:
        with open(KEY_PATH, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    except FileNotFoundError:
        if not create:
            return None
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(serialization.Encoding.PEM,
                            serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    tmp = KEY_PATH + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, KEY_PATH)
    return key


def unit_id(key):
    from cryptography.hazmat.primitives import serialization
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return b64url(raw)


def sign_headers(key, method, path, body, ts=None):
    ts = int(ts if ts is not None else time.time())
    msg = f"{ts}\n{method.upper()}\n{path}\n{hashlib.sha256(body).hexdigest()}".encode()
    return {"X-FR-Unit": unit_id(key), "X-FR-Time": str(ts), "X-FR-Sig": b64url(key.sign(msg))}


# ---- the report -------------------------------------------------------------

def _read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def _json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _age(path):
    try:
        return int(time.time() - os.path.getmtime(path))
    except OSError:
        return None


def _root_disk():
    """(block device name, e.g. mmcblk0 / nvme0n1, and its partition)."""
    try:
        src = subprocess.run(["findmnt", "-no", "SOURCE", "/"], capture_output=True,
                             text=True, timeout=5).stdout.strip()
    except Exception:
        return None, None
    part = os.path.basename(src)
    disk = part
    for suffix_len in range(1, 4):   # mmcblk0p2 -> mmcblk0, nvme0n1p2 -> nvme0n1
        cand = part[:-suffix_len].rstrip("p") if part[-suffix_len:].isdigit() else None
        if cand and os.path.exists(f"/sys/block/{cand}"):
            disk = cand
            break
    return disk, part


def rtc_health():
    """Clock battery state -- the RTC keeps time across power cuts only if fitted."""
    d = "/sys/class/rtc/rtc0"
    uv = _read(f"{d}/battery_voltage")
    charge = _read(f"{d}/charging_voltage")
    mv = round(int(uv) / 1000) if uv and uv.isdigit() else None
    return {
        "fitted": mv is not None and mv > 1000,     # an empty holder reads a few mV
        "battery_mv": mv,
        "charging": bool(charge and charge.isdigit() and int(charge) > 0),
    }


def collect():
    uptime = float((_read("/proc/uptime", "0") or "0").split()[0])
    installed = _json(os.path.join(OTA_STATE, "installed.json"))
    ota = _json(os.path.join(OTA_STATE, "status.json"))
    stats = _json("/run/readsb/stats.json")
    last1 = stats.get("last1min", {}) if isinstance(stats, dict) else {}
    local = last1.get("local", {}) if isinstance(last1, dict) else {}

    disk, part = _root_disk()
    storage = {"device": disk}
    if disk:
        fields = (_read(f"/sys/block/{disk}/stat", "") or "").split()
        if len(fields) > 6 and uptime > 0:
            sectors = int(fields[6])
            # Rate since the previous report, so a report shows current wear
            # rather than an average dragged by whatever the unit did days
            # ago. Since boot only when there is no usable snapshot (first
            # report, or a reboot reset the counters).
            snap = _json(IO_SNAPSHOT)
            if snap.get("disk") == disk and 0 < snap.get("uptime", 0) < uptime - 600 \
                    and snap.get("sectors", -1) <= sectors:
                span = uptime - snap["uptime"]
                storage["gb_per_day"] = round((sectors - snap["sectors"]) * 512 / 1e9 / (span / 86400), 2)
                storage["rate_window_h"] = round(span / 3600, 1)
            else:
                storage["gb_per_day"] = round(sectors * 512 / 1e9 / (uptime / 86400), 2)
                storage["rate_window_h"] = round(uptime / 3600, 1)
            storage["_snapshot"] = {"disk": disk, "uptime": uptime, "sectors": sectors}
        life = _read(f"/sys/fs/ext4/{part}/lifetime_write_kbytes")
        if life and life.isdigit():
            storage["lifetime_gb"] = round(int(life) / 1e6, 1)
    try:
        st = os.statvfs("/")
        storage["free_pct"] = round(100 * st.f_bavail / st.f_blocks, 1)
    except OSError:
        pass

    temp = _read("/sys/class/thermal/thermal_zone0/temp")
    throttled = None
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=5).stdout
        throttled = out.strip().split("=", 1)[-1] or None
    except Exception:
        pass

    mem = {}
    for line in (_read("/proc/meminfo", "") or "").splitlines():
        k, _, v = line.partition(":")
        if k in ("MemTotal", "MemAvailable", "Shmem"):
            mem[k] = int(v.split()[0]) // 1024

    painted = [p for p in (f"/run/user/{u}/stratoscan-painted" for u in os.listdir("/run/user"))
               if os.path.exists(p)] if os.path.isdir("/run/user") else []

    return {
        "v": 1,
        "version": installed.get("version"),
        "serial": installed.get("serial"),
        "uptime_s": int(uptime),
        "ota": {"state": ota.get("state")},
        "receiver": {
            "age_s": _age("/run/readsb/aircraft.json"),
            "aircraft": stats.get("aircraft_with_pos") if isinstance(stats, dict) else None,
            "messages_per_min": last1.get("messages"),
            "signal_db": local.get("signal"),
            "noise_db": local.get("noise"),
            "restarts": int(_read("/run/stratoscan-net/receiver-restarts", "0") or 0),
        },
        "display": {"painted_age_s": _age(painted[0]) if painted else None},
        "storage": storage,
        "rtc": rtc_health(),
        "thermal": {"temp_c": round(int(temp) / 1000, 1) if temp and temp.isdigit() else None,
                    "throttled": throttled},
        "memory_mb": mem,
        "last_watchdog_reboot_age_s": _age("/var/lib/stratoscan-setup/last-watchdog-reboot"),
        **fleet_extras(),
    }


def _local_json(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return json.loads(r.read())
    except Exception:
        return {}


def fleet_extras():
    """What a fleet's administrator sees beyond health, sent only while this
    radar is in a fleet (roadmap 1.13): its name, and its public page's daily
    visit counts for the last week. Counts only; never a location."""
    if not fleet():
        return {}
    out = {}
    name = _local_json(SETUP_HELLO).get("name")
    if isinstance(name, str) and name:
        out["name"] = name[:32]
    days = _local_json(VISITS_URL).get("days")
    if isinstance(days, list):
        out["visits"] = [{"date": d.get("date"), "views": int(d.get("views") or 0),
                          "unique": int(d.get("unique") or 0)} for d in days[-7:] if isinstance(d, dict)]
    return out


# ---- sending ----------------------------------------------------------------

def enabled():
    return bool(_json(CONFIG).get("enabled"))


def set_enabled(on):
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"enabled": bool(on)}, f)
    os.replace(tmp, CONFIG)
    if on:
        load_key(create=True)


def send(report=None):
    if not RELAY_URL:
        return False, "no relay configured"
    key = load_key(create=True)
    report = report or collect()
    snap = report.get("storage", {}).pop("_snapshot", None)
    body = json.dumps(report, separators=(",", ":")).encode()
    path = "/v1/heartbeat"
    headers = {"Content-Type": "application/json",
               "User-Agent": "StratoScan-unit/1 (+https://github.com/mferris/StratoScan)"}
    headers.update(sign_headers(key, "POST", path, body))
    req = urllib.request.Request(RELAY_URL.rstrip("/") + path, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            ok = 200 <= r.status < 300
        if ok and snap:
            try:
                with open(IO_SNAPSHOT, "w") as f:
                    json.dump(snap, f)
            except OSError:
                pass
        return ok, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, type(e).__name__


# ---- fleets (roadmap 1.13) ----------------------------------------------------

def fleet():
    """The fleet this radar is in, as {"name", ...}, or {} for none."""
    return _json(FLEET)


def _call(method, path, payload=None):
    """A signed request to the relay. Returns (status, reply)."""
    key = load_key(create=True)
    body = b"" if method == "GET" else json.dumps(payload or {}, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json",
               "User-Agent": "StratoScan-unit/1 (+https://github.com/mferris/StratoScan)"}
    headers.update(sign_headers(key, method, path, body))
    req = urllib.request.Request(RELAY_URL.rstrip("/") + path, data=None if method == "GET" else body,
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except Exception as e:
        return 0, {"error": f"Couldn't reach the StratoScan service ({type(e).__name__})."}


def _write_fleet(d):
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    tmp = FLEET + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f)
    os.replace(tmp, FLEET)


def fleet_join(code):
    """Join the fleet whose invite code this is. Joining turns health reports
    on -- they are what the fleet's administrator sees -- and leaving puts
    them back the way they were."""
    if not RELAY_URL:
        raise ValueError("No StratoScan service is configured.")
    status, r = _call("POST", "/v1/unit/fleet", {"code": code})
    if status != 200:
        raise ValueError(r.get("error") or f"The StratoScan service said no (HTTP {status}).")
    name = str((r.get("fleet") or {}).get("name") or "")[:40]
    was = fleet().get("health_was", enabled())
    _write_fleet({"name": name, "joined": int(time.time()), "health_was": bool(was)})
    set_enabled(True)
    ok, detail = send()          # so the administrator sees it straight away
    _record(ok, detail)
    return {"fleet": {"name": name}}


def fleet_leave():
    status, r = _call("POST", "/v1/unit/fleet/leave", {})
    if status not in (200, 404):
        raise ValueError(r.get("error") or f"The StratoScan service said no (HTTP {status}).")
    was = fleet().get("health_was")
    try:
        os.remove(FLEET)
    except FileNotFoundError:
        pass
    if was is not None:
        set_enabled(bool(was))
    return {"fleet": None}


def _record(ok, detail, at=None):
    try:
        os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
        with open(LAST, "w") as f:
            json.dump({"at": int(at if at is not None else time.time()), "ok": ok, "detail": detail}, f)
    except OSError:
        pass


def maybe_send(now=None):
    """Send a report if reporting is on and one is due. Returns a log line or None."""
    now = now or time.time()
    if not RELAY_URL or not enabled():
        return None
    last = _json(LAST)
    wait = REPORT_EVERY_S if last.get("ok") else RETRY_AFTER_FAILURE_S
    if last and now - last.get("at", 0) < wait:
        return None
    ok, detail = send()
    _record(ok, detail, at=now)   # the same clock the due-check used
    return f"health report {'sent' if ok else 'failed'} ({detail})"


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        key = load_key(create=False)
        print(json.dumps({"enabled": enabled(), "relay": RELAY_URL or None,
                          "unit": unit_id(key) if key else None,
                          "last": _json(LAST) or None, "report": collect()}, indent=1, default=str))
        return 0
    if cmd == "send":
        if not enabled():
            print("health reporting is off (opt-in in the setup page)")
            return 1
        ok, detail = send()
        _record(ok, detail)
        print(detail)
        return 0 if ok else 1
    print("usage: heartbeat.py status|send", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
