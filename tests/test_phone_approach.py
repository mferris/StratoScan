#!/usr/bin/env python3
"""
Checks for alerts about aircraft approaching a phone (roadmap 2.7) in
deploy/events.py: the unit's box key, decrypting a phone's location, and the
approach rule run against that location.

The phone's side of the encryption is CryptoKit; tests/fixtures/
phone-location.json holds a blob made by the real Swift code
(ios/Shared/LocationBox.swift) for a known unit key, so the two can't drift.

Run: python3 tests/test_phone_approach.py
"""
import base64
import importlib.util
import json
import math
import os
import sys
import tempfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

HERE = os.path.dirname(os.path.abspath(__file__))
failures = []
checks = 0


def check(label, condition):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


tmp = tempfile.mkdtemp()
os.environ["STRATOSCAN_RELAY_STATE"] = os.path.join(tmp, "relay")
os.environ["STRATOSCAN_RELAY_URL"] = "https://relay.example"
os.environ["STRATOSCAN_TAR1090_DB"] = os.path.join(tmp, "db-*")
os.environ["STRATOSCAN_NOTABLE_JSON"] = os.path.join(tmp, "notable.json")
os.environ["STRATOSCAN_EVENTS_RUN"] = os.path.join(tmp, "run")
spec = importlib.util.spec_from_file_location("events", os.path.join(HERE, "..", "deploy", "events.py"))
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
raw = lambda k: k.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def seal(box_pub_raw, phone, fix):
    """The phone's side, in Python: what LocationBox.swift does."""
    eph = X25519PrivateKey.generate()
    eph_pub = raw(eph.public_key())
    shared = eph.exchange(X25519PublicKey.from_public_bytes(box_pub_raw))
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=ev.LOCATION_INFO + eph_pub + box_pub_raw).derive(shared)
    nonce = os.urandom(12)
    sealed = ChaCha20Poly1305(key).encrypt(nonce, json.dumps(fix).encode(), phone.encode())
    return b64(eph_pub + nonce + sealed)


# ---- the box key --------------------------------------------------------------------
ed = Ed25519PrivateKey.generate()
box = ev.box_private(ed)
check("the box key is derived the same way every time", raw(ev.box_private(ed).public_key()) == raw(box.public_key()))
check("and differs between units", raw(ev.box_private(Ed25519PrivateKey.generate()).public_key()) != raw(box.public_key()))
ed_raw = ed.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
check("it is not the identity key's own bytes", ev.box_public_raw(box) != raw(ed.public_key()))

# ---- decrypting --------------------------------------------------------------------
PHONE = b64(os.urandom(32))
OTHER = b64(os.urandom(32))
fix = {"lat": 35.9, "lon": -78.6, "ts": 1_800_000_000}
blob = seal(ev.box_public_raw(box), PHONE, fix)
check("a phone's blob decrypts to its position", ev.decrypt_location(box, blob, PHONE) == (35.9, -78.6, 1_800_000_000))
check("but not as another phone's (the phone id is bound in)", ev.decrypt_location(box, blob, OTHER) is None)
other_box = ev.box_private(Ed25519PrivateKey.generate())
check("nor by another unit", ev.decrypt_location(other_box, blob, PHONE) is None)
bad = bytearray(base64.urlsafe_b64decode(blob + "=" * (-len(blob) % 4)))
bad[-1] ^= 1
check("a tampered blob is refused", ev.decrypt_location(box, b64(bytes(bad)), PHONE) is None)
check("garbage is refused", ev.decrypt_location(box, "not-a-blob", PHONE) is None)
check("an impossible position is refused",
      ev.decrypt_location(box, seal(ev.box_public_raw(box), PHONE, {"lat": 95, "lon": 0, "ts": 1}), PHONE) is None)

# The real Swift code's output (see the docstring); made for this fixed key.
fixture = os.path.join(HERE, "fixtures", "phone-location.json")
if os.path.exists(fixture):
    with open(fixture) as f:
        fx = json.load(f)
    fixed_ed = Ed25519PrivateKey.from_private_bytes(base64.b64decode(fx["unit_ed25519_seed"]))
    got = ev.decrypt_location(ev.box_private(fixed_ed), fx["blob"], fx["phone"])
    check("a blob sealed by the Swift code decrypts here", got == (fx["lat"], fx["lon"], fx["ts"]))
    check("the Swift code derived the same box key", b64(ev.box_public_raw(ev.box_private(fixed_ed))) == fx["box_key"])
else:
    check("the Swift fixture exists (tests/fixtures/phone-location.json)", False)

# ---- the approach rule, against a phone ------------------------------------------------
NOW = 1_800_000_000
# The phone 20 nm north of the antenna; a helicopter 2 nm south of the phone,
# heading north at 90 kt: over the phone in about 80 s.
plat, plon = 36.2, -78.8


def heli(**kw):
    a = {"hex": "a11111", "flight": "N407XX", "lat": plat - 2 / 60, "lon": plon, "gs": 90, "track": 0,
         "alt_baro": 900, "category": "A7", "seen": 1, "r_dst": 18.0, "r_dir": 0}
    a.update(kw)
    return a


d = ev.Detector()
d.set_points({PHONE: (plat, plon, NOW - 60)}, NOW)
out = d.scan({"aircraft": [heli()]}, now=NOW)
mine = [e for e in out if e.get("phone") == PHONE]
check("an aircraft about to pass over the phone is an approach to that phone",
      len(mine) == 1 and mine[0]["kind"] == "approach" and mine[0]["label"] == "Helicopter")
check("the pass is about 80 s away", mine and 70 <= mine[0]["eta_s"] <= 90)
check("with no distance or direction, which would say where the phone is",
      mine and "dist_nm" not in mine[0] and "dir" not in mine[0])
check("no plain position goes anywhere", mine and not ({"lat", "lon"} & set(mine[0])))
check("and the radar itself, 18 nm off, gets no approach of its own",
      not [e for e in out if e["kind"] == "approach" and "phone" not in e])

again = d.scan({"aircraft": [heli()]}, now=NOW + 5)
check("one alert per aircraft per phone", not [e for e in again if e.get("phone") == PHONE and e["kind"] == "approach"])

later = d.scan({"aircraft": []}, now=NOW + 80 + ev.APPROACH_END_AFTER_S + 1)
check("after the pass, its end goes to the same phone",
      [e for e in later if e["kind"] == "approach_end" and e.get("phone") == PHONE and e["hex"] == "a11111"])

d2 = ev.Detector()
d2.set_points({PHONE: (plat, plon, NOW - ev.LOCATION_MAX_AGE_S - 1)}, NOW)
check("a stale position is ignored", d2.points == {})

d3 = ev.Detector()
d3.set_points({PHONE: (plat, plon, NOW)}, NOW)
far = heli(lat=plat - 2 / 60, lon=plon + 0.2)      # passing 10 nm east of the phone
check("an aircraft passing well clear is not an approach",
      not [e for e in d3.scan({"aircraft": [far]}, now=NOW) if e.get("phone")])
airliner = heli(hex="a90001", category="A3", alt_baro=30000)
check("high traffic passing over is not worth an alert",
      not [e for e in ev.Detector().scan({"aircraft": [airliner]}, now=NOW) if e.get("phone")])

# ---- talking to the relay ----------------------------------------------------------------
os.makedirs(ev.hb.STATE_DIR, exist_ok=True)
unit_key = ev.hb.load_key(create=True)
unit_box = ev.box_private(unit_key)
calls = []


def relay(method, path, payload=None):
    calls.append((method, path, payload))
    if path == "/v1/unit/boxkey":
        return 200, {"ok": True}
    return 200, {"locations": [{"phone": PHONE, "blob": seal(ev.box_public_raw(unit_box), PHONE, {"lat": plat, "lon": plon, "ts": NOW}), "updated": NOW},
                               {"phone": OTHER, "blob": "rubbish", "updated": NOW}]}


locs = ev.PhoneLocations(call=relay)
d4 = ev.Detector()
said = locs.tick(d4, now=NOW)
pub = [c for c in calls if c[1] == "/v1/unit/boxkey"]
check("the box key is published first", calls and calls[0][1] == "/v1/unit/boxkey")
ed_pub = unit_key.public_key()
sig = base64.urlsafe_b64decode(pub[0][2]["sig"] + "==")
try:
    ed_pub.verify(sig, (ev.BOX_KEY_CONTEXT + pub[0][2]["key"]).encode())
    signed_ok = True
except Exception:
    signed_ok = False
check("signed by the unit's identity key", signed_ok)
check("good blobs become points; bad ones are dropped", set(d4.points) == {PHONE})
check("the log says how many phones, never where", said and "1 phone" in said and "36." not in said)
calls.clear()
locs.tick(d4, now=NOW + 10)
check("not polled again before its interval", calls == [])
locs.tick(d4, now=NOW + ev.LOCATION_POLL_S + 1)
check("then polled, without republishing the key", [c[1] for c in calls] == ["/v1/unit/locations"])

old = ev.PhoneLocations(call=lambda *a: (404, None))
d5 = ev.Detector()
check("an older relay without these endpoints is quietly left alone",
      old.tick(d5, now=NOW) is None and old.next_poll >= NOW + 3600 and d5.points == {})

print(f"{checks - len(failures)}/{checks} phone approach checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
