#!/usr/bin/env python3
"""The root helper and the web tier's directory (security review 2026-10-26).

setupd.py runs as root. /var/lib/stratoscan-setup belongs to the web tier,
which can put anything at any name in it, and systemd hands everything in it
to the web tier's user whenever that starts. So root keeps its own files in
a directory of its own, and in the shared one it never writes through a
name, never reads through a link, never changes a file's owner or mode by
name, and checks what it reads back.

These run setupd's own code against a temporary directory laid out as the
web tier could leave it. (They run as an ordinary user; the links point at
files of that user's, standing in for root's.)

Run: python3 tests/test_setupd_state_dir.py
"""
import importlib.util
import json
import os
import pathlib
import stat
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


spec = importlib.util.spec_from_file_location("setupd", ROOT / "deploy" / "setupd.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

# ---- where root keeps what -------------------------------------------------------
private = getattr(d, "PRIVATE_DIR", None)
check(private is not None and not private.startswith(d.STATE_DIR + "/") and private != d.STATE_DIR,
      "root's own files have a directory of their own, not the web tier's")
for name in ("READSB_ORIG", "READSB_BACKUP", "HOTSPOT_PSK"):
    path = getattr(d, name, "")
    check(bool(private) and path.startswith(private + "/"), "%s is in it (%s)" % (name, path or "missing"))
check(d.LOCK.startswith(d.RUN_DIR + "/"), "the change lock is under %s, which only root can write" % d.RUN_DIR)
check(d.PENDING.startswith(d.STATE_DIR + "/"), "pending.json stays where net-watchdog looks for it")

tmp = pathlib.Path(tempfile.mkdtemp())
state, priv, run, elsewhere = tmp / "state", tmp / "private", tmp / "run", tmp / "elsewhere"
for p in (state, priv, run, elsewhere):
    p.mkdir()
d.STATE_DIR, d.RUN_DIR = str(state), str(run)
d.PRIVATE_DIR = str(priv)
d.PENDING = str(state / "pending.json")
d.LOCK = str(run / "setupd.lock")
d.READSB_ORIG = str(priv / "readsb.default.orig")
d.READSB_BACKUP = str(priv / "readsb.fr-backup")
d.HOTSPOT_PSK = str(priv / "hotspot-psk")


def victim(name, body="root's own file\n"):
    """A file outside the directory, standing in for one of root's."""
    p = elsewhere / name
    p.write_text(body)
    p.chmod(0o600)
    return p


def untouched(p, body="root's own file\n"):
    return p.read_text() == body and stat.S_IMODE(p.stat().st_mode) == 0o600


# ---- writing: never through a name the web tier chose -----------------------------
v = victim("written")
(state / ".pending.json.tmp").symlink_to(v)        # the old fixed temporary name
d.write_pending({"kind": "wifi", "ssid": "HomeNet", "knownGoodUuid": None})
check(untouched(v), "writing pending.json never writes through a link at a temporary name")
check(json.loads((state / "pending.json").read_text()).get("ssid") == "HomeNet"
      and not (state / "pending.json").is_symlink(), "and pending.json is written, as a file of its own")
check(not [n for n in os.listdir(state) if n.startswith(".pending.json.") and n != ".pending.json.tmp"],
      "leaving no temporary file behind")

# ---- the lock ----------------------------------------------------------------------
v = victim("locked")
d.LOCK = str(state / "lock")                        # where it was, with a link in its place
os.symlink(v, d.LOCK)
try:
    with d.state_lock():
        pass
except d.Err:
    pass
check(untouched(v), "taking the change lock never opens a link for writing (it used to empty its target)")
d.LOCK = str(run / "setupd.lock")
try:
    with d.state_lock():
        took = True
except d.Err:
    took = False
check(took and os.path.isfile(d.LOCK), "and in its own place the lock is taken as before")

# ---- reading pending.json back -----------------------------------------------------
good = {"kind": "wifi", "ssid": "HomeNet", "candidate": "fr-candidate",
        "knownGoodUuid": "6f1b9c2e-3a4d-4e5f-8a9b-0c1d2e3f4a5b"}
(state / "pending.json").unlink()
v = victim("pending-elsewhere", json.dumps(good))
(state / "pending.json").symlink_to(v)
check(d.read_pending() is None, "pending.json is not read through a link")
(state / "pending.json").unlink()
(state / "pending.json").write_text(json.dumps(good))
check(d.read_pending() == good, "a pending change root wrote reads back as written")
(state / "pending.json").write_text(json.dumps(dict(good, knownGoodUuid="--help")))
got = d.read_pending()
check(got is not None and got["knownGoodUuid"] is None,
      "a network id that is not a UUID never reaches nmcli; the change is still pending")
(state / "pending.json").write_text(json.dumps(dict(good, ssid="-x")))
check(d.read_pending() is None, "a network name setupd would never have written is no pending change")

# ---- the ownership pass at start --------------------------------------------------
d.resolve_gid = lambda: os.getgid()
v1, v2 = victim("shared-1"), victim("shared-2")
(state / "setup.json").symlink_to(v1)
(state / "anything").symlink_to(v2)
d.share_state_dir()
check(untouched(v1) and untouched(v2),
      "sharing the directory changes no file through a link (setup.json or any other name)")
(state / "setup.json").unlink()
(state / "setup.json").write_text('{"claimed": true}')
(state / "setup.json").chmod(0o600)
own = state / "kept-private"
own.write_text("x")
own.chmod(0o600)
d.share_state_dir()
check(stat.S_IMODE((state / "setup.json").stat().st_mode) == 0o660, "setup.json itself is shared with the web tier")
check(stat.S_IMODE(own.stat().st_mode) == 0o600, "and nothing else in there is opened up")

# ---- root's files leave the shared directory --------------------------------------
take = getattr(d, "take_private_files", None)
check(take is not None, "setupd carries its own files out of the shared directory at start")
ORIG = 'RECEIVER_OPTIONS="--device 0 --gain -10"\nDECODER_OPTIONS="--max-range 450 --write-json-every 1"\n'
if take:
    (state / "readsb.default.orig").write_text(ORIG)
    (state / "hotspot-psk").write_text("23456789ab")
    (state / "readsb.fr-backup").write_text(ORIG)
    (state / "lock").unlink()
    (state / "lock").write_text("")
    take()
    check((priv / "readsb.default.orig").read_text() == ORIG and (priv / "hotspot-psk").read_text() == "23456789ab",
          "the saved readsb options and the hotspot password are carried over")
    check(all(stat.S_IMODE((priv / n).stat().st_mode) == 0o600 for n in ("readsb.default.orig", "hotspot-psk"))
          and stat.S_IMODE(priv.stat().st_mode) == 0o700, "root's only")
    check(not any((state / n).exists() for n in ("readsb.default.orig", "hotspot-psk", "readsb.fr-backup", "lock")),
          "and gone from the shared directory")
    check(d.hotspot_psk() == "23456789ab", "the hotspot keeps its password (the label stays right)")
    for label, setup in (("a link", lambda p: p.symlink_to(victim("orig-elsewhere", ORIG))),
                         ("unsafe options", lambda p: p.write_text('DECODER_OPTIONS="--lat 1 $(id)"\n'))):
        (priv / "readsb.default.orig").unlink(missing_ok=True)
        setup(state / "readsb.default.orig")
        take()
        check(not (priv / "readsb.default.orig").exists() and not os.path.lexists(state / "readsb.default.orig"),
              "a saved original that is %s is not carried over, and is removed" % label)

# ---- restoring the saved original on a reset ---------------------------------------
calls = []


class Done:
    returncode = 0
    stdout = stderr = b""


d.run = lambda argv, **k: (calls.append(argv), Done())[1]
d.os.chown = lambda *a, **k: None
d.CONFIG_JSON = str(tmp / "config.json")
d.READSB_DEFAULT = str(tmp / "readsb")
current = 'DECODER_OPTIONS="--lat 35.87760 --lon -78.78750 --max-range 450"\n'
for label, saved, want in (("unsafe options", 'DECODER_OPTIONS="--max-range 450"\nX=`id`\n', current),
                           ("a sound original", ORIG, ORIG)):
    pathlib.Path(d.READSB_DEFAULT).write_text(current)
    pathlib.Path(d.READSB_ORIG).write_text(saved)
    d.reset_settings()
    check(pathlib.Path(d.READSB_DEFAULT).read_text() == want,
          "reset_settings with %s %s" % (label, "restores it" if want == saved else "leaves readsb as it is"))
pathlib.Path(d.READSB_ORIG).write_text('DECODER_OPTIONS="--lat 1 $(id)"\n')
check(d.saved_readsb_original() is None if hasattr(d, "saved_readsb_original") else False,
      "a saved original is checked line by line before root writes it back")

print("setupd state checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
