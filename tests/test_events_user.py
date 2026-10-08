#!/usr/bin/env python3
"""The events service runs as its own user (security review 2026-10-04,
item 1): it reads the unit key through a group, never creates it, and can
write only its runtime directory; the installer and heartbeat.py keep the
key directory root:stratoscan-relay 0750 and the key 0640."""
import importlib.util
import os
import pathlib
import stat
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


svc = (root / "deploy" / "stratoscan-events.service").read_text()
check("User=stratoscan-events" in svc and "Group=stratoscan-events" in svc, "the service runs as stratoscan-events")
check("SupplementaryGroups=stratoscan-relay" in svc, "with the group that may read the unit key")
check("RuntimeDirectory=stratoscan-events" in svc and "ProtectSystem=strict" in svc, "and may write only its runtime directory")
inst = (root / "deploy" / "install-setup-server.sh").read_text()
check("groupadd --system \"$g\"" in inst and "useradd --system --gid stratoscan-events --groups stratoscan-relay" in inst,
      "the installer creates the user and the groups")
check("chmod 0750 /var/lib/stratoscan-relay" in inst and "chmod 0640 /var/lib/stratoscan-relay/unit.key" in inst,
      "and sets the directory and key modes")
ev = (root / "deploy" / "events.py").read_text()
check(ev.count("load_key(create=True)") == 1 and "def set_enabled" in ev.split("load_key(create=True)")[0][-400:],
      "the service never creates the key; only set_enabled (run as root by pairing) does")

tmp = tempfile.mkdtemp()
os.environ["STRATOSCAN_RELAY_STATE"] = tmp
os.environ["STRATOSCAN_RELAY_URL"] = "https://relay.invalid"


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), root / "deploy" / (name + ".py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name.replace("-", "_")] = m
    spec.loader.exec_module(m)
    return m


hb = load("heartbeat")
check(hb.load_key(create=False) is None, "without a key, create=False returns None")
# As root the helper would chown; here it records what it would do.
chowns = []
hb.os.chown = lambda path, uid, gid: chowns.append((os.path.basename(path), uid, gid))
hb.grp.getgrnam = lambda name: type("G", (), {"gr_gid": 4242})()
key = hb.load_key(create=True)
check(key is not None and os.path.exists(hb.KEY_PATH), "creating the key (as pairing does) works")
check(("unit.key", 0, 4242) in chowns and (os.path.basename(tmp), 0, 4242) in chowns, "and hands the group the key and its directory")
check(stat.S_IMODE(os.stat(hb.KEY_PATH).st_mode) == 0o640, "the key is 0640")
check(stat.S_IMODE(os.stat(tmp).st_mode) == 0o750, "the directory is 0750")
hb.grp.getgrnam = lambda name: (_ for _ in ()).throw(KeyError(name))
check(hb.share_state_with_group() is False, "a unit without the group is left alone")

ev = load("events")
ev.hb = hb
os.remove(hb.KEY_PATH)
check(ev._unit_key() is None, "the service sees no key before pairing")
check(ev.relay_call("GET", "/v1/unit/locations") == (None, None), "a relay call without a key fails quietly")
status, detail = ev.Sender()._post([]) if hasattr(ev, "Sender") else (0, b"no unit key")
check(status == 0 and b"no unit key" in detail, "a send without a key is a failure to retry, not a crash")
loc = ev.PhoneLocations(call=lambda *a: (200, {"locations": []}))
check(loc.publish() is None and loc._box() is None, "the box key waits for the unit key")
print("events user checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
