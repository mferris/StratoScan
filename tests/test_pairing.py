#!/usr/bin/env python3
"""
Checks for deploy/pairing.py (pairing a phone with this unit).

What matters:
- the relay only ever sees the secret's hash; the secret stays in /run and
  in the QR code;
- a spent or withdrawn code stops showing;
- events are on exactly while a phone is paired;
- a factory reset leaves nothing that can reach the previous owner's
  phones, even when the relay can't be reached.

The relay's side is relay/test (npm test). Signing needs the `cryptography`
package (present on Raspberry Pi OS); key-dependent checks are skipped
without it.

Run: python3 tests/test_pairing.py
"""
import hashlib
import importlib.util
import json
import os
import stat
import sys
import tempfile
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
failures, checks, skipped = [], 0, 0


def check(label, cond):
    global checks
    checks += 1
    if not cond:
        failures.append(label)


tmp = tempfile.mkdtemp()
os.environ["STRATOSCAN_RELAY_STATE"] = os.path.join(tmp, "relay")
os.environ["STRATOSCAN_RELAY_URL"] = "https://relay.example"
os.environ["STRATOSCAN_PAIRING_RUN"] = os.path.join(tmp, "run")
os.environ["STRATOSCAN_EVENTS_RUN"] = os.path.join(tmp, "events-run")
spec = importlib.util.spec_from_file_location("pairing", os.path.join(HERE, "..", "deploy", "pairing.py"))
pairing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pairing)

try:
    import cryptography  # noqa: F401
    have_crypto = True
except ImportError:
    have_crypto = False


class FakeRelay:
    def __init__(self):
        self.calls, self.offer_hash, self.phones, self.down = [], None, [], False

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if self.down:
            raise pairing.RelayError("Could not reach the StratoScan service. Is this radar online?")
        if path == "/v1/unit/pairing":
            self.offer_hash = payload["secret_hash"]
            return {"ok": True, "expires": 2_000_000_600}
        if path == "/v1/unit/pairing/cancel":
            self.offer_hash = None
            return {"ok": True}
        if path == "/v1/unit/phones":
            return {"phones": [{"phone": p, "name": "iPhone", "created": 1} for p in self.phones],
                    "offer": {"expires": 2_000_000_600} if self.offer_hash else None}
        if path == "/v1/unit/unpair":
            if payload.get("all"):
                self.phones = []
            else:
                self.phones = [p for p in self.phones if p != payload.get("phone")]
            return {"ok": True, "phones": len(self.phones)}
        raise AssertionError(path)


relay = FakeRelay()
pairing._call = relay

# events.py stand-in: pairing turns it on and off.
ev_state = {"on": False}


class FakeEvents:
    @staticmethod
    def enabled(): return ev_state["on"]

    @staticmethod
    def set_enabled(v): ev_state["on"] = bool(v)


pairing._events = lambda: FakeEvents

PHONE = "P" * 43

if have_crypto:
    real_time = pairing.time.time
    pairing.time.time = lambda: 2_000_000_000
    offer = pairing.start()
    q = parse_qs(urlparse(offer["link"]).query)
    check("the link is a radome:// pairing link", offer["link"].startswith("radome://pair?"))
    unit = pairing.hb.unit_id(pairing.hb.load_key(create=False))
    check("it names this unit", q.get("u") == [unit])
    secret = q["s"][0]
    check("the secret has 128 bits", len(secret) >= 22)
    check("the relay got the secret's hash, never the secret",
          relay.offer_hash == hashlib.sha256(secret.encode()).hexdigest()
          and secret not in json.dumps(relay.calls))
    mode = stat.S_IMODE(os.stat(pairing.OFFER).st_mode)
    check("the open code is readable by root only", mode == 0o600)
    check("the open code is kept in /run, not on storage", pairing.OFFER.startswith(os.environ["STRATOSCAN_PAIRING_RUN"]))

    st = pairing.status()
    check("an open code shows while the relay still holds it", st["offer"] and st["offer"]["link"] == offer["link"])
    check("no phone yet: events stay off", ev_state["on"] is False and st["phones"] == [])

    # A phone uses the code: the relay spends it and lists the phone.
    relay.offer_hash = None
    relay.phones = [PHONE]
    st = pairing.status()
    check("a spent code stops showing", st["offer"] is None and not os.path.exists(pairing.OFFER))
    check("the new phone is listed", [p["id"] for p in st["phones"]] == [PHONE])
    check("pairing a phone turns events on", ev_state["on"] is True)

    for bad in ("", "x" * 42, "../" + "x" * 40, None, 7):
        try:
            pairing.remove(bad)
            check(f"remove refuses {bad!r}", False)
        except ValueError:
            pass
    check("a malformed phone id never reaches the relay",
          not any(c[1] == "/v1/unit/unpair" for c in relay.calls))
    pairing.remove(PHONE)
    check("removing the last phone turns events off", ev_state["on"] is False)

    pairing.start()
    pairing.cancel()
    check("a withdrawn code is gone locally and at the relay",
          not os.path.exists(pairing.OFFER) and relay.offer_hash is None)

    # Factory reset with the relay unreachable.
    relay.phones = [PHONE]
    ev_state["on"] = True
    pairing.start()
    relay.down = True
    pairing.forget_everything()
    check("a reset retires the unit key even when the relay is down",
          not os.path.exists(pairing.hb.KEY_PATH))
    check("and turns events off", ev_state["on"] is False)
    check("and drops any open code", not os.path.exists(pairing.OFFER))
    relay.down = False
    new_unit = pairing.hb.unit_id(pairing.hb.load_key(create=True))
    check("the unit comes back as a new identity", new_unit != unit)
    pairing.time.time = real_time
else:
    skipped += 18

relay.down = True
try:
    pairing.cancel()
    check("a relay failure is reported, not swallowed", False)
except pairing.RelayError as e:
    check("a relay failure says what to check", "online" in str(e))

if failures:
    print(f"{len(failures)} of {checks} pairing checks FAILED:")
    for f in failures:
        print("  -", f)
    sys.exit(1)
extra = f" ({skipped} key checks skipped: no cryptography package here)" if skipped else ""
print(f"{checks}/{checks} pairing checks passed{extra}")
