#!/usr/bin/env python3
"""
Pairing a phone with this unit (roadmap 2.3). Runs as root, inside setupd,
because it signs with the unit key (heartbeat.py owns it).

  1. The owner taps "Pair a phone" on the radar's own screen. start() makes a
     one-time secret, tells the relay only its SHA-256, and returns a link the
     screen shows as a QR code:  radome://pair?u=<unit id>&s=<secret>
  2. The phone scans it (the Camera app opens the Radome app), and presents
     the secret to the relay with its own signed request. The relay links the
     two and spends the code; it expires anyway after 10 minutes.
  3. status() sees the new phone and turns this unit's events on
     (events.py). With no phones left, events go off again: a unit never
     sends events nobody will receive.

The secret only ever exists here (in /run, never on storage), in the QR code
on this unit's own screen, and in the phone that scanned it. The screen's
channel to this code is loopback-only and not reachable from the network
(setup-server.py's onboarding listener); the setup page, behind the owner's
password, can ask for a link too.

  pairing.py status       phones paired with this unit, and any open code
  pairing.py start        open a code (prints the link)
  pairing.py cancel       withdraw it
  pairing.py remove ID    unpair one phone
  pairing.py remove-all   unpair every phone
"""
import hashlib
import importlib.util
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.environ.get("FLIGHTRADAR_PAIRING_RUN", "/run/flightradar")
OFFER = os.path.join(RUN_DIR, "pairing-offer.json")
TIMEOUT_S = 10
LINK = "radome://pair"
RE_ID = re.compile(r"^[A-Za-z0-9_-]{43}$")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hb = _load("heartbeat")


class RelayError(Exception):
    pass


def _call(method, path, payload=None):
    """A request signed with the unit key. Returns the decoded JSON reply."""
    if not hb.RELAY_URL:
        raise RelayError("No Radome service is configured on this radar.")
    key = hb.load_key(create=True)
    body = b"" if method == "GET" else json.dumps(payload or {}, separators=(",", ":")).encode()
    headers = {"User-Agent": "Radome-unit/1 (+https://github.com/mferris/Radome)"}
    if method != "GET":
        headers["Content-Type"] = "application/json"
    headers.update(hb.sign_headers(key, method, path, body))
    req = urllib.request.Request(hb.RELAY_URL.rstrip("/") + path, data=body if method != "GET" else None,
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read(65536) or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read(4096)).get("error")
        except Exception:
            msg = None
        raise RelayError(msg or f"HTTP {e.code}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise RelayError("Could not reach the Radome service. Is this radar online?")


def _events():
    try:
        return _load("events")
    except Exception:
        return None


def _sync_events(phones):
    """Events on exactly while a phone is paired."""
    ev = _events()
    if ev is not None and ev.enabled() != (phones > 0):
        ev.set_enabled(phones > 0)


def _read_offer():
    try:
        with open(OFFER) as f:
            o = json.load(f)
        return o if o.get("expires", 0) > time.time() else None
    except (OSError, ValueError):
        return None


def _write_offer(offer):
    os.makedirs(RUN_DIR, exist_ok=True)
    tmp = OFFER + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(offer, f)
    os.replace(tmp, OFFER)


def _drop_offer():
    try:
        os.remove(OFFER)
    except OSError:
        pass


def link_for(unit, secret):
    return f"{LINK}?u={unit}&s={secret}"


def start():
    unit = hb.unit_id(hb.load_key(create=True))
    secret = secrets.token_urlsafe(16)          # 128 bits
    r = _call("POST", "/v1/unit/pairing", {"secret_hash": hashlib.sha256(secret.encode()).hexdigest()})
    offer = {"link": link_for(unit, secret), "expires": int(r.get("expires") or time.time() + 600)}
    _write_offer(offer)
    return offer


def cancel():
    _drop_offer()
    _call("POST", "/v1/unit/pairing/cancel", {})
    return {"cancelled": True}


def status():
    key = hb.load_key(create=False)
    if key is None:
        return {"unit": None, "phones": [], "offer": None}
    r = _call("GET", "/v1/unit/phones")
    phones = [{"id": p.get("phone"), "name": p.get("name"), "created": p.get("created")}
              for p in r.get("phones") or [] if isinstance(p, dict)]
    local = _read_offer()
    # The relay is the authority on whether the code is still open: once a
    # phone has used it, it is gone there and the screen should stop showing it.
    if local and not r.get("offer"):
        _drop_offer()
        local = None
    _sync_events(len(phones))
    return {"unit": hb.unit_id(key)[:10], "phones": phones, "offer": local}


def remove(phone):
    if not isinstance(phone, str) or not RE_ID.match(phone):
        raise ValueError("not a phone id")
    r = _call("POST", "/v1/unit/unpair", {"phone": phone})
    _sync_events(int(r.get("phones") or 0))
    return {"phones": int(r.get("phones") or 0)}


def remove_all():
    _drop_offer()
    try:
        _call("POST", "/v1/unit/unpair", {"all": True})
    finally:
        _sync_events(0)
    return {"phones": 0}


def forget_everything():
    """For a factory reset: unpair every phone, then retire this unit's identity.

    The relay call can fail (no network at reset time), so the key is replaced
    too: whatever the relay still holds belongs to an id this unit no longer
    uses, and nothing it sends from now on can reach the previous owner's phones.
    """
    try:
        remove_all()
    except Exception:
        pass
    try:
        os.remove(hb.KEY_PATH)
    except OSError:
        pass


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    try:
        if cmd == "status":
            out = status()
        elif cmd == "start":
            out = start()
        elif cmd == "cancel":
            out = cancel()
        elif cmd == "remove" and len(argv) > 2:
            out = remove(argv[2])
        elif cmd == "remove-all":
            out = remove_all()
        else:
            print("usage: pairing.py status|start|cancel|remove ID|remove-all", file=sys.stderr)
            return 2
    except (RelayError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
