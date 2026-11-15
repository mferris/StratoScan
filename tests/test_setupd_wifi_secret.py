#!/usr/bin/env python3
"""The WiFi password never rides in a command's arguments (2026-11-15).

setupd.py joined a network by handing nmcli the password as an argument,
where any local user could read it from /proc while that nmcli ran. It now
writes the password into the new profile's own keyfile (root's, 0600), has
NetworkManager read that file again, and asks NetworkManager what it holds.
Only when the answer is exactly the password does it go on; otherwise the
profile is made again the old way, so a join can never be lost to this.

A stand-in for nmcli and NetworkManager runs here: it keeps profiles as
keyfiles in a temporary directory, written and read by GLib's key-file
rules as this test understands them (a backslash doubled, a leading space
as backslash-s), and records every command line it is given.

Run: python3 tests/test_setupd_wifi_secret.py
"""
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
d.STATE_DIR = str(tmp / "state")
d.PENDING = str(tmp / "state" / "pending.json")
os.makedirs(d.STATE_DIR)
d.nm_active_wifi_uuid = lambda: None
d.connectivity_ok = lambda: (True, None)
d.time.sleep = lambda s: None
rolled = []
d.wifi_rollback = lambda: rolled.append(True)
journal = []
d.print = lambda *a, **k: journal.append(" ".join(map(str, a)))


def glib_write(v):
    out = v.replace("\\", "\\\\")
    lead = len(out) - len(out.lstrip(" "))
    return "\\s" * lead + out[lead:]


def glib_read(raw):
    """A value as GLib reads it: leading blanks dropped, then the escapes."""
    raw = raw.lstrip(" \t")
    out, i = "", 0
    while i < len(raw):
        if raw[i] == "\\":
            nxt = raw[i + 1:i + 2]
            if nxt not in ("s", "n", "t", "r", "\\"):
                raise ValueError("bad escape")
            out += {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}[nxt]
            i += 2
        else:
            out += raw[i]
            i += 1
    return out


def terse(v):
    return v.replace("\\", "\\\\").replace(":", "\\:")


class FakeNM:
    """nmcli, as setupd calls it, over keyfiles in a directory."""

    def __init__(self, keydir, mangle=None, load_rc=0, escape_always=False, layout="alias"):
        self.dir = pathlib.Path(keydir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.profiles = {}          # name -> {"props": {}, "path": Path}
        self.argvs = []
        self.mangle = mangle        # what a load does to the password it read
        self.load_rc = load_rc
        self.escape_always = escape_always
        self.layout = layout
        self.ups = 0

    def save(self, name):
        p = self.profiles[name]
        pr = p["props"]
        sec = "[wifi-security]" if self.layout != "long" else "[802-11-wireless-security]"
        text = ("[connection]\nid=%s\nuuid=0f0e0d0c-0b0a-4908-8706-050403020100\ntype=wifi\n"
                "autoconnect=false\ninterface-name=wlan0\n\n[wifi]\n" % name)
        if pr.get("hidden"):
            text += "hidden=true\n"
        text += "mode=infrastructure\nssid=%s\n\n" % pr["ssid"]
        if "key-mgmt" in pr and self.layout != "nosec":
            text += sec + "\nkey-mgmt=%s\n" % pr["key-mgmt"]
            if "psk" in pr:
                text += "psk=%s\n" % glib_write(pr["psk"])
            text += "\n"
        text += "[ipv4]\nmethod=auto\n\n[ipv6]\naddr-gen-mode=default\nmethod=auto\n\n[proxy]\n"
        p["path"].write_text(text)
        p["path"].chmod(0o600)

    def load(self, path):
        if self.load_rc:
            return self.load_rc
        path = pathlib.Path(path)
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            return 1                # NetworkManager refuses a keyfile others can read
        name = psk = None
        section = ""
        for line in path.read_text().split("\n"):
            if line.startswith("["):
                section = line.strip()
            elif "=" in line:
                k, v = line.split("=", 1)
                if section == "[connection]" and k.strip() == "id":
                    name = v
                if section in ("[wifi-security]", "[802-11-wireless-security]") and k.strip() == "psk":
                    psk = glib_read(v)
        if name not in self.profiles:
            return 1
        if psk is not None:
            self.profiles[name]["props"]["psk"] = self.mangle(psk) if self.mangle else psk
        return 0

    def __call__(self, argv, timeout=30, check=False, input_bytes=None):
        self.argvs.append(list(argv))
        a = argv[1:]
        rc, out = 0, ""
        if a[:3] == ["connection", "add", "type"]:
            name = a[a.index("con-name") + 1]
            self.profiles[name] = {"props": {"ssid": a[a.index("ssid") + 1], "hidden": "wifi.hidden" in a},
                                   "path": self.dir / (name + ".nmconnection")}
            self.save(name)
        elif a[:2] == ["connection", "modify"]:
            name = a[2]
            if name not in self.profiles:
                rc = 10
            else:
                for k, v in zip(a[3::2], a[4::2]):
                    self.profiles[name]["props"][k.split(".")[-1]] = v
                self.save(name)
        elif a[:2] == ["connection", "delete"]:
            p = self.profiles.pop(a[2], None)
            if p is None:
                rc = 10
            else:
                p["path"].unlink()
        elif a[:2] == ["connection", "load"]:
            rc = self.load(a[2])
        elif a[:2] == ["connection", "up"]:
            self.ups += 1
            rc = 0 if a[2] in self.profiles else 10
        elif a == ["-t", "-f", "NAME,FILENAME", "connection", "show"]:
            out = "".join("%s:%s\n" % (terse(n), terse(str(p["path"]))) for n, p in self.profiles.items())
        elif a[:4] == ["-s", "-e", "no", "-g"] and a[4] == "802-11-wireless-security.psk":
            p = self.profiles.get(a[-1])
            if p is None:
                rc = 10
            else:
                v = p["props"].get("psk", "")
                out = (terse(v) if self.escape_always else v) + "\n"
        else:
            raise AssertionError("the stand-in was not expecting %r" % (a,))
        if check and rc != 0:
            raise d.Err("command_failed", "")
        return subprocess.CompletedProcess(argv, rc, out.encode(), b"")


N = d.NMCLI
C = d.CANDIDATE_PROFILE


def join(psk, ssid="Home WiFi", hidden=False, **nm):
    keydir = nm.pop("keydir", None) or tempfile.mkdtemp(dir=tmp)
    d.NM_KEYFILE_DIR = nm.pop("claimed_dir", str(keydir))
    fake = FakeNM(keydir, **nm)
    d.run = fake
    d._SECRETS.clear()
    journal.clear()
    result = d.wifi_connect(ssid, psk, hidden)
    return fake, result


def add_argv(ssid, hidden=False):
    return [N, "connection", "add", "type", "wifi", "con-name", C, "ifname", "wlan0", "ssid", ssid,
            "connection.autoconnect", "no"] + (["wifi.hidden", "yes"] if hidden else [])


KEYMGMT = [N, "connection", "modify", C, "wifi-sec.key-mgmt", "wpa-psk"]
OLD_PSK = lambda psk: [N, "connection", "modify", C, "wifi-sec.psk", psk]

# ---- an open network: exactly the commands it always was -------------------------
fake, r = join(None)
check(fake.argvs == [[N, "connection", "delete", C], add_argv("Home WiFi"), [N, "connection", "up", C]],
      "an open network is added and brought up with the same three commands as before")
check(journal == [], "with nothing in the journal: an open network has no password to fall back over")
check(r["state"] == "awaiting_confirm" and r["ssid"] == "Home WiFi", "and waits for its confirmation as before")
fake, r = join("")
check(fake.argvs == [[N, "connection", "delete", C], add_argv("Home WiFi"), [N, "connection", "up", C]],
      "an empty password is an open network too")

# ---- passwords: never an argument, stored character for character ----------------
PASSWORDS = [
    ("eight characters", "abcdefgh"),
    ("63 characters", "A1b2C3d4" * 7 + "E5f6G7h"),
    ("a 64-digit hex key", "0123456789abcdef" * 4),
    ("spaces inside", "correct horse battery"),
    ("a leading space", " leading1"),
    ("several leading spaces", "   three-in"),
    ("a trailing space", "trailing1 "),
    ("only spaces", " " * 8),
    ("a double quote", 'say "cheese" 1'),
    ("single quotes", "it's o'clock"),
    ("a backslash", "back\\slash1"),
    ("a backslash before s and n", "a\\sb\\nc\\td"),
    ("a trailing backslash", "trailing1\\"),
    ("a leading backslash", "\\leading1"),
    ("backslashes only", "\\" * 8),
    ("a colon", "pass:word1"),
    ("an equals sign", "psk=psk=1"),
    ("a hash first", "#notacomment"),
    ("a bracket first", "[wifi-security]"),
    ("a semicolon", "semi;colon;1"),
    ("shell characters", "$(reboot) `id` |&;<>"),
    ("a percent and a tilde", "100%~sure!"),
    ("every printable character", "".join(chr(c) for c in range(0x21, 0x7f))[:63]),
    ("the rest of them", "".join(chr(c) for c in range(0x21, 0x7f))[31:]),
]
for label, psk in PASSWORDS:
    fake, r = join(psk)
    stored = fake.profiles[C]["props"].get("psk")
    inargv = any(psk in arg for argv in fake.argvs for arg in argv)
    check(stored == psk and not inargv and r["state"] == "awaiting_confirm",
          "a password with %s is stored exactly and is in no command line" % label)
    path = fake.profiles[C]["path"]
    check(stat.S_IMODE(path.stat().st_mode) == 0o600 and sorted(os.listdir(path.parent)) == [path.name],
          "   its keyfile is still 0600 and nothing else is left beside it")
    check(journal == [], "   and the journal is given nothing: the keyfile route took")

fake, r = join("correct horse battery")
check(fake.argvs == [[N, "connection", "delete", C], add_argv("Home WiFi"), KEYMGMT,
                     [N, "-t", "-f", "NAME,FILENAME", "connection", "show"],
                     [N, "connection", "load", str(fake.profiles[C]["path"])],
                     [N, "-s", "-e", "no", "-g", "802-11-wireless-security.psk", "connection", "show", C],
                     [N, "connection", "up", C]],
      "the commands are: delete, add, key-mgmt, find the keyfile, load it, read the password back, up")
text = fake.profiles[C]["path"].read_text()
check(text.count("psk=correct horse battery\n") == 1 and text.index("[wifi-security]\npsk=") < text.index("key-mgmt=wpa-psk"),
      "one psk= line was added, under the profile's security section")
without = text.replace("psk=correct horse battery\n", "")
plain = FakeNM(tempfile.mkdtemp(dir=tmp))
plain(add_argv("Home WiFi")), plain(KEYMGMT)
check(without == plain.profiles[C]["path"].read_text(), "and not another byte of NetworkManager's file changed")
check("wpa-psk" in " ".join(KEYMGMT) and fake.profiles[C]["props"]["key-mgmt"] == "wpa-psk",
      "key-mgmt is wpa-psk as before (WPA2, and WPA3 where the router offers both)")

fake, r = join("hidden-net-pass", ssid="Cafe: Corner", hidden=True)
check(fake.argvs[1] == add_argv("Cafe: Corner", hidden=True) and fake.profiles[C]["props"]["psk"] == "hidden-net-pass",
      "a hidden network is added with wifi.hidden yes, as before, and gets its password the same way")

# ---- what was refused before is refused the same, before anything runs -----------
for label, bad, code in (("unicode", "pässwörd1", "bad_psk"), ("seven characters", "sevench", "bad_psk"),
                         ("64 characters that are not hex", "g" * 64, "bad_psk"), ("a newline", "abcd\nefgh", "bad_psk"),
                         ("a leading dash", "-abcdefgh", "psk_leading_dash")):
    d.run = fake = FakeNM(tempfile.mkdtemp(dir=tmp))
    try:
        d.wifi_connect("Home WiFi", bad)
        got = None
    except d.Err as e:
        got = e.code
    check(got == code and fake.argvs == [], "a password with %s is refused as before (%s), and nothing runs" % (label, code))

# ---- when the keyfile route does not take, the old route runs in full ------------
def old_route(fake, psk, why):
    tail = fake.argvs[-5:]
    ok = (tail == [[N, "connection", "delete", C], add_argv("Home WiFi"), KEYMGMT, OLD_PSK(psk), [N, "connection", "up", C]]
          and fake.profiles[C]["props"].get("psk") == psk and fake.ups == 1)
    check(ok, "%s: the profile is made again the old way, holds the password, and is brought up once" % why)
    # A fallback must be visible (2026-11-15): one line, at warning priority
    # ("<4>" is systemd's prefix for it), never holding the password.
    check(len(journal) == 1 and journal[0].startswith("<4>setupd: ") and "keyfile" in journal[0] and psk not in journal[0],
          "   and the journal gets one line at warning priority saying so, without the password")


PSK = "back\\slash: pass"
fake, r = join(PSK, claimed_dir="/etc/NetworkManager/system-connections")
old_route(fake, PSK, "a profile kept somewhere else (netplan's, under /run)")
check(not any(a[1:3] == ["connection", "load"] for a in fake.argvs), "   and no file was written or loaded")

fake, r = join(PSK, load_rc=1)
old_route(fake, PSK, "NetworkManager refusing to load the file")
fake, r = join('"quoted pass"', mangle=lambda v: v.strip('"'))
old_route(fake, '"quoted pass"', "NetworkManager dropping the quotes round a password")
fake, r = join("trailing1 ", mangle=lambda v: v.rstrip())
old_route(fake, "trailing1 ", "NetworkManager dropping a trailing space")
fake, r = join(PSK, mangle=lambda v: v.replace("\\", "\\\\"))
old_route(fake, PSK, "NetworkManager not undoing the doubled backslash")
fake, r = join(PSK, escape_always=True)
old_route(fake, PSK, "nmcli answering in its escaped form")
fake, r = join(PSK, layout="nosec")
old_route(fake, PSK, "a keyfile with no security section")
check(not any(a[1:3] == ["connection", "load"] for a in fake.argvs), "   and the file was left alone")
fake, r = join(PSK, layout="long")
check(fake.profiles[C]["props"]["psk"] == PSK and not any(PSK in arg for argv in fake.argvs for arg in argv),
      "a keyfile that spells the section out in full is handled like the short one")

# the file is put back before the old route starts
keydir = pathlib.Path(tempfile.mkdtemp(dir=tmp))
seen = {}


class Watching(FakeNM):
    def load(self, path):
        seen.setdefault("loads", []).append(pathlib.Path(path).read_text())
        return 1 if len(seen["loads"]) == 1 else 0


d.NM_KEYFILE_DIR = str(keydir)
d.run = fake = Watching(keydir)
journal.clear()
d.wifi_connect("Home WiFi", PSK)
check(len(seen["loads"]) == 2 and "psk=" in seen["loads"][0] and "psk=" not in seen["loads"][1],
      "after a failed load NetworkManager's own file is put back and loaded again")
old_route(fake, PSK, "and then")

# a second profile of the same name, or nmcli failing to list: no guessing
d.NM_KEYFILE_DIR = "/x"
d.run = lambda argv, **k: subprocess.CompletedProcess(argv, 0, b"fr-candidate:/x/a.nmconnection\nfr-candidate:/x/b.nmconnection\n", b"")
check(d.profile_keyfile(C) is None, "two profiles of that name: neither file is touched")
d.run = lambda argv, **k: subprocess.CompletedProcess(argv, 1, b"", b"")
check(d.profile_keyfile(C) is None, "nmcli unable to list profiles: no file is touched")
d.run = lambda argv, **k: subprocess.CompletedProcess(argv, 0, b"fr-other:/x/fr-candidate.nmconnection\nfr-candidate:/x/odd\\:name.nmconnection\n", b"")
check(d.profile_keyfile(C) == "/x/odd:name.nmconnection", "the file is the one nmcli names for that profile, colons unescaped")
d.run = lambda argv, **k: subprocess.CompletedProcess(argv, 0, b"fr-candidate:/x/sub/a.nmconnection\n", b"")
check(d.profile_keyfile(C) is None, "a file anywhere but NetworkManager's own directory is not touched")

# a link where the keyfile should be is not read or written through
keydir = pathlib.Path(tempfile.mkdtemp(dir=tmp))
victim = tmp / "victim"
victim.write_text("[wifi-security]\nkey-mgmt=wpa-psk\n")


class Linked(FakeNM):
    def save(self, name):
        p = self.profiles[name]["path"]
        if not p.is_symlink():
            os.symlink(victim, p)


d.NM_KEYFILE_DIR = str(keydir)
d.run = fake = Linked(keydir)
check(d.wifi_psk_by_keyfile(C, PSK) is False, "no profile: nothing is done")
fake(add_argv("Home WiFi"))
check(d.wifi_psk_by_keyfile(C, PSK) is False and victim.read_text() == "[wifi-security]\nkey-mgmt=wpa-psk\n",
      "a link at the keyfile's name is not followed")

# ---- a failed join still rolls back, and the wrong-password answer is unchanged --
class Refusing(FakeNM):
    def __call__(self, argv, **k):
        if argv[1:3] == ["connection", "up"]:
            self.argvs.append(list(argv))
            return subprocess.CompletedProcess(argv, 4, b"", b"Error: Connection activation failed: Secrets were required, but not provided.")
        return super().__call__(argv, **k)


keydir = tempfile.mkdtemp(dir=tmp)
d.NM_KEYFILE_DIR = keydir
d.run = fake = Refusing(keydir)
rolled.clear()
try:
    d.wifi_connect("Home WiFi", "wrong-password")
    got = None
except d.Err as e:
    got = e.code
check(got == "wifi_auth_failed" and rolled == [True], "a wrong password is still reported as one, and rolled back")

# ---- the source: one place left where the password is an argument ----------------
src = (ROOT / "deploy" / "setupd.py").read_text()
body = src[src.index("def wifi_connect("):src.index("def wifi_confirm(")]
check(body.count('"wifi-sec.psk", psk]') == 1 and body.index("wifi_psk_by_keyfile(") < body.index('"wifi-sec.psk", psk]'),
      "wifi_connect passes the password as an argument in one place only, after the keyfile route has said no")
check(d.keyfile_value("a\\b") == "a\\\\b" and d.keyfile_value("  x ") == "\\s\\sx " and d.keyfile_value('"q" #;=') == '"q" #;=',
      "a keyfile value doubles backslashes, writes leading spaces as \\s, and changes nothing else")
check(all(glib_read(d.keyfile_value(p)) == p for _, p in PASSWORDS), "and reads back as itself for every password above")

print("WiFi secret checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
