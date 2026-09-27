#!/usr/bin/env python3
"""
Checks for deploy/heartbeat.py (opt-in health reports).

What matters: nothing is ever sent unless the owner turned it on; a report
never carries a location; failures back off; and the private key is readable
by its owner only. Signing checks need the `cryptography` package (present on
Raspberry Pi OS); they are skipped, and reported as skipped, where it is not.
The relay side of signing is covered by relay/test (npm test), including a
fixture signed by this module on a real unit.

Run: python3 tests/test_heartbeat.py
"""
import importlib.util
import json
import os
import stat
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
failures, checks, skipped = [], 0, 0


def check(label, cond):
    global checks
    checks += 1
    if not cond:
        failures.append(label)


tmp = tempfile.mkdtemp()
os.environ["FLIGHTRADAR_RELAY_STATE"] = os.path.join(tmp, "relay")
os.environ["FLIGHTRADAR_RELAY_URL"] = "https://relay.example"
spec = importlib.util.spec_from_file_location("hb", os.path.join(HERE, "..", "deploy", "heartbeat.py"))
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)

# ---- the report never carries a location ---------------------------------
report = hb.collect()
text = json.dumps(report).lower()
for word in ('"lat"', '"lon"', "latitude", "longitude", "hostname", '"ip"', "ssid"):
    check(f"the report has no {word} field", word not in text)
check("the report is versioned", report.get("v") == 1)

# ---- opt-in: nothing is sent unless enabled --------------------------------
sent = []
hb.send = lambda report=None: (sent.append(1), (True, "HTTP 200"))[1]
check("off by default", hb.enabled() is False)
check("a disabled unit sends nothing", hb.maybe_send(now=1_000_000) is None and not sent)

try:
    import cryptography  # noqa: F401
    have_crypto = True
except ImportError:
    have_crypto = False

if have_crypto:
    hb.set_enabled(True)
    check("enabling persists", hb.enabled() is True)
    mode = stat.S_IMODE(os.stat(hb.KEY_PATH).st_mode)
    check("the private key is readable by its owner only", mode == 0o600)
    check("the key directory is private", stat.S_IMODE(os.stat(hb.STATE_DIR).st_mode) == 0o700)

    # ---- scheduling and back-off -----------------------------------------
    t0 = 2_000_000_000
    check("the first report goes out", hb.maybe_send(now=t0) is not None and len(sent) == 1)
    check("not again before it is due", hb.maybe_send(now=t0 + 3600) is None and len(sent) == 1)
    with open(hb.LAST, "w") as f:
        json.dump({"at": t0, "ok": True}, f)
    check("again once due", hb.maybe_send(now=t0 + hb.REPORT_EVERY_S + 1) is not None and len(sent) == 2)

    hb.send = lambda report=None: (sent.append(1), (False, "URLError"))[1]
    with open(hb.LAST, "w") as f:
        json.dump({"at": t0, "ok": True}, f)
    hb.maybe_send(now=t0 + hb.REPORT_EVERY_S + 1)
    n = len(sent)
    check("a failure is retried after a short back-off, not immediately",
          hb.maybe_send(now=t0 + hb.REPORT_EVERY_S + 60) is None and len(sent) == n)
    check("and is retried once the back-off passes",
          hb.maybe_send(now=t0 + hb.REPORT_EVERY_S + hb.RETRY_AFTER_FAILURE_S + 2) is not None)

    # ---- signing: the canonical message the relay verifies ---------------
    import hashlib
    key = hb.load_key(create=False)
    body = b'{"v":1}'
    h = hb.sign_headers(key, "post", "/v1/heartbeat", body, ts=1_800_000_000)
    msg = f"1800000000\nPOST\n/v1/heartbeat\n{hashlib.sha256(body).hexdigest()}".encode()
    import base64
    sig = base64.urlsafe_b64decode(h["X-FR-Sig"] + "==")
    try:
        key.public_key().verify(sig, msg)
        ok = True
    except Exception:
        ok = False
    check("the signature covers time, method, path and body hash", ok)
    check("the unit id is the raw public key, base64url", len(h["X-FR-Unit"]) == 43)
    check("the same key is reused, not regenerated", hb.unit_id(hb.load_key()) == h["X-FR-Unit"])

    hb.set_enabled(False)
    check("turning it off stops reports", hb.maybe_send(now=t0 + 10 * hb.REPORT_EVERY_S) is None)
else:
    skipped = 12

# ---- no relay configured: silently nothing -----------------------------------
hb.RELAY_URL = ""
check("with no relay configured nothing is attempted", hb.maybe_send(now=3_000_000_000) is None)

print(f"{checks - len(failures)}/{checks} heartbeat checks passed"
      + (f" ({skipped} signing checks skipped: no cryptography package here)" if skipped else ""))
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
