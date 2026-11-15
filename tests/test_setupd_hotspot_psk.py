#!/usr/bin/env python3
"""The setup network's password (2026-11-15).

It was made once, 10 characters, and outlived "Erase everything": whoever
had a unit before could join its setup network whenever that came up. A new
one is now 12 characters, and an erase makes a new one.

The rule every change here has to keep: the password on the radar's screen
and in its setup QR is the one the network is using. Both come from one
file, so the file changes only while the network is down, just before it
is raised again, and a file the network could not be raised with is
replaced rather than leaving a unit nobody can reach.

Two things the first version left (both fixed the same day): the screen's
own look at the password (hotspot_info) could write a new one without the
change lock, between the network's password being read and the network
being raised; and an erase that could not change the password answered
exactly as one that had.

Run: python3 tests/test_setupd_hotspot_psk.py
"""
import fcntl
import importlib.util
import os
import pathlib
import stat
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


spec = importlib.util.spec_from_file_location("setupd", ROOT / "deploy" / "setupd.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

tmp = pathlib.Path(tempfile.mkdtemp())
priv = tmp / "private"
priv.mkdir()
d.PRIVATE_DIR = str(priv)
d.HOTSPOT_PSK = str(priv / "hotspot-psk")
psk_file = priv / "hotspot-psk"
rundir = tmp / "run"
rundir.mkdir()
d.RUN_DIR = str(rundir)
d.LOCK = str(rundir / "setupd.lock")
journal = []
d.print = lambda *a, **k: journal.append(" ".join(map(str, a)))


class FakeNM:
    """Just enough nmcli: a hotspot profile that is up once it is made."""

    def __init__(self):
        self.argvs = []
        self.on_air = None          # the password the network is using
        self.delete_works = True
        self.active_rc = 0          # what nmcli returns when asked what is up
        self.listing = b"uuid-aaa:802-11-wireless\nuuid-hot:802-11-wireless\nuuid-eth:802-3-ethernet\n"

    def __call__(self, argv, **k):
        self.argvs.append(list(argv))
        a = argv[1:]
        out = b""
        if a[:2] == ["connection", "delete"] and a[2] in (d.HOTSPOT_PROFILE, "uuid-hot"):
            if self.delete_works:
                self.on_air = None
        elif a[:3] == ["device", "wifi", "hotspot"]:
            self.on_air = a[a.index("password") + 1]
        elif a == ["-t", "-f", "NAME", "connection", "show", "--active"]:
            out = (d.HOTSPOT_PROFILE + "\n").encode() if self.on_air else b"fr-Home\n"
        elif a == ["-t", "-f", "UUID,TYPE", "connection", "show"]:
            out = self.listing
        if a == ["-t", "-f", "NAME", "connection", "show", "--active"] and self.active_rc:
            return subprocess.CompletedProcess(argv, self.active_rc, b"", b"Error: NetworkManager is not running.")
        return subprocess.CompletedProcess(argv, 0, out, b"")


d.run = nm = FakeNM()
d.hotspot_address = lambda: "10.42.0.1"
info = d.VERBS["hotspot_info"]

# ---- a new unit --------------------------------------------------------------------
first = d.hotspot_psk()
check(len(first) == 12 and set(first) <= set("23456789abcdefghjkmnpqrstuvwxyz"),
      "a new password is 12 characters, none of them easy to misread")
check(stat.S_IMODE(psk_file.stat().st_mode) == 0o600 and psk_file.read_text() == first, "it is saved 0600")
check(d.hotspot_psk() == first and d.hotspot_psk() == first, "and is the same every time it is asked for")
check(len({d.new_hotspot_psk() for _ in range(50)}) == 50, "no two made are alike")

# ---- the screen and the air agree --------------------------------------------------
started = d.hotspot_start()
check(nm.on_air == started["psk"] == d.hotspot_psk() == info({})["psk"],
      "the network comes up with the password the screen and the QR show")
again = d.hotspot_start()
check(again["psk"] == started["psk"] and nm.on_air == started["psk"],
      "raising it again (the watchdog does every five minutes of an outage) keeps the password, so a phone rejoins")
d.hotspot_stop()
check(d.hotspot_psk() == started["psk"], "taking it down keeps the password too")

# ---- a unit that already has one keeps it ------------------------------------------
psk_file.write_text("23456789ab")
check(d.hotspot_psk() == "23456789ab" and psk_file.read_text() == "23456789ab",
      "a unit's existing 10-character password is kept as it is")
psk_file.write_text("23456789ab\n")
check(d.hotspot_psk() == "23456789ab", "with or without a newline after it")

# ---- a file the network could not be raised with -----------------------------------
for label, body in (("an empty", b""), ("a too-short", b"abc"), ("a binary", b"\xff\xfe\x00\x01" * 8),
                    ("a far too long", b"a" * 5000), ("a two-line", b"abcdefgh\nijklmnop\n")):
    psk_file.write_bytes(body)
    got = d.hotspot_psk()
    check(len(got) == 12 and psk_file.read_text() == got, "%s file is replaced with a new password" % label)
    d.hotspot_start()
    check(nm.on_air == got == info({})["psk"], "   and the network comes up with it, as shown")

# ---- the screen's look never writes without the change lock ------------------------
class Held:
    """Another change in progress: the lock held through a descriptor of its own."""

    def __enter__(self):
        self.f = open(d.LOCK, "w")
        fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def __exit__(self, *a):
        self.f.close()


def lock_is_held():
    try:
        with d.state_lock():
            return False
    except d.Err:
        return True


d.hotspot_stop()
saved = psk_file.read_text()
with Held():
    check(info({})["psk"] == saved and psk_file.read_text() == saved,
          "with a password saved, the screen's look reads it even while another change holds the lock")
psk_file.unlink()
with Held():
    got = info({})
    check(got["psk"] is None and not psk_file.exists() and got["ssid"] == "StratoScan-Setup" and "active" in got,
          "with none saved and a change in progress, the screen's look writes nothing and answers with no password yet")
    # the change in progress is the network being raised: it makes the password
    started = d.hotspot_start()
check(info({})["psk"] == started["psk"] == nm.on_air, "and its next look shows the one the network came up with")
d.hotspot_stop()

psk_file.unlink()
made_under_lock = []
real_new = d.new_hotspot_psk
d.new_hotspot_psk = lambda: (made_under_lock.append(lock_is_held()), real_new())[1]
got = info({})
check(made_under_lock == [True] and got["psk"] == psk_file.read_text() and len(got["psk"]) == 12,
      "with none saved and no change in progress, it makes one while holding the lock")
check(not lock_is_held(), "and lets the lock go")
psk_file.write_bytes(b"abc")
with Held():
    check(info({})["psk"] is None and psk_file.read_bytes() == b"abc" and made_under_lock == [True],
          "a saved one the network could not use is not replaced without the lock either")
check(len(info({})["psk"]) == 12 and made_under_lock == [True, True], "only with it")
d.new_hotspot_psk = real_new


def no_lock_dir():
    raise OSError(28, "No space left on device")


psk_file.unlink()
d.atomic_write, real_write = (lambda *a, **k: no_lock_dir()), d.atomic_write
try:
    info({})
    raised = False
except OSError:
    raised = True
d.atomic_write = real_write
check(raised and not lock_is_held(), "a password that can't be saved is an error as before, and the lock is let go")

# setupd makes the password when it starts, before it listens, so the first look has one
class Stop(Exception):
    pass


def no_server(*a):
    raise Stop()


state0 = tmp / "state0"
d.STATE_DIR, d.SOCK_PATH = str(state0), str(rundir / "setupd.sock")
d.Server, real_server = no_server, d.Server
at_listen = []
d.ensure_claim_code = lambda: None
try:
    d.main()
except Stop:
    at_listen.append(psk_file.exists() and len(psk_file.read_text()) == 12)
d.Server = real_server
check(at_listen == [True], "setupd makes the password as it starts, before its socket exists")
first_boot = psk_file.read_text()
try:
    d.Server = no_server
    d.main()
except Stop:
    pass
d.Server = real_server
check(psk_file.read_text() == first_boot, "and a later start keeps it")

src0 = (ROOT / "deploy" / "setupd.py").read_text()
body = src0[src0.index("def hotspot_info("):src0.index("def hotspot_state(")]
check("new_hotspot_psk" not in body and body.count("hotspot_psk()") == 2
      and body.index("psk = saved_hotspot_psk()") < body.index("with state_lock():") < body.index("psk = hotspot_psk()"),
      "hotspot_info reads with the reader that never writes, and reaches the one that may only inside the lock")
check('"hotspot_info": lambda p: hotspot_info()' in src0 and '"hotspot_info"' not in src0[src0.index("MUTATING = {"):src0.index("class Handler(")],
      "it is still a read: it does not hold the lock while it asks NetworkManager what is up")
reader = src0[src0.index("def saved_hotspot_psk("):src0.index("def hotspot_info(")]
check("atomic_write" not in reader and "new_hotspot_psk" not in reader, "the reader has no way to write")

# ---- erasing the unit --------------------------------------------------------------
state = tmp / "state"
state.mkdir()
d.STATE_DIR = str(state)
d.PENDING = str(state / "pending.json")
d.CONFIG_JSON = str(tmp / "config.json")
d.READSB_DEFAULT = str(tmp / "readsb")
d.READSB_ORIG = str(priv / "readsb.default.orig")
d.OFFLINE_MAP_DIR = str(tmp / "offline-map")
d.APPROACH_FILES = (str(tmp / "approaches.json"),)
d.FEEDING = str(tmp / "no-feeding.py")
d._heartbeat = lambda: None
d._pairing = lambda: None
d._events = lambda: None
d.ensure_claim_code = lambda: "CODE1234"
(tmp / "readsb").write_text('DECODER_OPTIONS="--lat 35.8776 --lon -78.7875"\n')


def erase():
    nm.argvs.clear()
    before = d.hotspot_psk()
    return before, d.reset_full()


d.hotspot_start()
before, r = erase()
after = psk_file.read_text()
check(after != before and len(after) == 12, "Erase everything makes a new setup-network password")
check(nm.on_air == after == info({})["psk"], "the network it leaves up uses the new one, and the screen shows the new one")
check(r["reset"] == "full" and r["hotspot"] == "StratoScan-Setup" and r["claimCode"] == "CODE1234",
      "and the erase answers as before")
check(r.get("hotspotPassword") == "new" and "hotspotPasswordKept" not in r and not [l for l in journal if "kept" in l],
      "and says the setup network has a new password")
hot = [i for i, a in enumerate(nm.argvs) if a[1:4] == ["device", "wifi", "hotspot"]]
check(len(hot) == 1 and before not in nm.argvs[hot[0]], "the old password is not the one handed to the new network")

# the old network could not be taken down: nothing changes under it
nm.delete_works = False
journal.clear()
before, r = erase()
check(psk_file.read_text() == before and info({})["psk"] == before,
      "if the setup network is somehow still up, its password is left alone (the screen stays right)")
check(r.get("hotspotPassword") == "kept" and "still up" in r.get("hotspotPasswordKept", ""),
      "and the erase says the old password was kept, and why")
check(len(journal) == 1 and journal[0].startswith("<4>setupd: erase kept") and before not in journal[0],
      "with one journal line at warning priority that does not hold the password")
check(r["reset"] == "full" and r["claimCode"] == "CODE1234", "the rest of its answer is unchanged")
nm.delete_works = True

# nmcli can't say whether it is up: leave it alone, and say so
d.hotspot_start()
real_state = d.hotspot_state


def cannot_tell():
    raise d.Err("timeout", "nmcli")


d.hotspot_state = cannot_tell
journal.clear()
before, r = erase()
check(psk_file.read_text() == before and nm.on_air == before, "if nmcli does not answer in time, the password is left alone")
check(r.get("hotspotPassword") == "kept" and "could not say" in r.get("hotspotPasswordKept", "") and len(journal) == 1,
      "and the erase says so")
d.hotspot_state = real_state

# nmcli answers with an error (NetworkManager is not running): that is not "down"
nm.active_rc = 8
check(d.hotspot_state() is None and d.hotspot_active() is False,
      "an nmcli error is neither up nor down; the screen still treats it as not up, as before")
journal.clear()
before, r = erase()
check(psk_file.read_text() == before and r.get("hotspotPassword") == "kept"
      and "could not say" in r.get("hotspotPasswordKept", "") and len(journal) == 1,
      "if nmcli fails, the erase keeps the password and says so instead of taking the network for down")
nm.active_rc = 0

# the new one can't be saved: the old one stays, on the air and on the screen
real_write = d.atomic_write


def full_card(path, data, mode=0o600):
    if path == d.HOTSPOT_PSK:
        raise OSError(28, "No space left on device")
    return real_write(path, data, mode)


d.atomic_write = full_card
journal.clear()
before, r = erase()
d.atomic_write = real_write
check(psk_file.read_text() == before and nm.on_air == before and info({})["psk"] == before,
      "if the new password can't be saved, the old one stays in force and the unit is still left reachable")
check(r.get("hotspotPassword") == "kept" and "could not be saved" in r.get("hotspotPasswordKept", "") and len(journal) == 1,
      "and the erase says that too")
before, r = erase()
check(r.get("hotspotPassword") == "new" and psk_file.read_text() != before and nm.on_air == psk_file.read_text(),
      "an erase run again once the cause is gone gives the new password")

# ---- nothing else changes it -------------------------------------------------------
src = (ROOT / "deploy" / "setupd.py").read_text()
calls = src.count("new_hotspot_psk()") - src.count("def new_hotspot_psk()")
reset = src[src.index("def reset_full("):src.index("# ------------------------------------------------------------------- verbs")]
check(calls == 2 and reset.count("new_hotspot_psk()") == 1
      and reset.index("up = hotspot_state()") < reset.index("new_hotspot_psk()") < reset.index("hs = hotspot_start()"),
      "a new password is made in two places only: when there is none to use, and in the erase, with the network down and before it is raised")
check('"password", psk]' in src[src.index("def hotspot_start("):src.index("def v_hotspot_psk(")]
      and "psk = hotspot_psk()" in src[src.index("def hotspot_start("):src.index("def v_hotspot_psk(")],
      "the network is always raised with what the file holds")

# ---- the screen asks again after an erase ------------------------------------------
spec = importlib.util.spec_from_file_location("ss_hotspot", ROOT / "deploy" / "setup-server.py")
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)
answers = iter(["old-password", "new-password"])
ss.call_setupd = lambda verb, params=None, timeout=120: (
    {"ok": True, "result": {"ssid": "StratoScan-Setup", "psk": next(answers), "active": True}}
    if verb == "hotspot_info" else {"ok": True, "result": {}})
ss._probe_cache.update(at=float("-inf"), value=None)
one = ss._onboard_probe()[0]["result"]["psk"]
check(ss._onboard_probe()[0]["result"]["psk"] == one == "old-password", "the screen's look at the setup network is cached")
ss.forget_probe()
check(ss._onboard_probe()[0]["result"]["psk"] == "new-password", "forget_probe makes the next look ask setupd again")
check(ss._probe_cache["value"] is not None, "without dropping the last answer the app's hello uses meanwhile")
sv = (ROOT / "deploy" / "setup-server.py").read_text()
check(sv.count('r = call_setupd("reset_full", timeout=180)\n            forget_probe()') == 2,
      "both erases (the setup page's and the screen's) do that as soon as setupd answers")
check('return self._send(200, {"result": r["result"]})' in sv[sv.index("def _reset(self, st):"):sv.index("def _status(self, st):")]
      and "return self._relay(r)" in sv[sv.index('if path == "/onboard/reset":'):sv.index("def _verb(self, verb")],
      "and both hand setupd's whole answer on, so whether the setup password changed reaches whoever asked for the erase")

print("hotspot password checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
