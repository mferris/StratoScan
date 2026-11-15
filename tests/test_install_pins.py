#!/usr/bin/env python3
"""What the installer puts on a new unit is what was chosen, not what
happened to be there that day (security review 2026-11-03).

- SR-32: deploy/allowed_signers, the key every unit takes updates from, is
  installed only if every key in it is the pinned one (or one named by hand
  as ROTATE_SIGNERS for a rotation).
- SR-35: readsb is built only while its tag is still the pinned commit, and
  tar1090's aircraft database is a pinned commit, not that day's master.
- SR-28: a fresh install or image records the release it was built from, so
  the updater's floor is that build's serial; an existing record is kept.
- SR-43: a unit with no SSH host keys makes its own before sshd is asked to
  check its config, and the image never carries any.

The installer's own snippets are taken out of it and run here, against
temporary folders. Nothing is installed.

Run: python3 tests/test_install_pins.py
"""
import base64
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
INST = (ROOT / "deploy" / "install-setup-server.sh").read_text()
BUILD = (ROOT / "image" / "build.sh").read_text()
SIGNERS = (ROOT / "deploy" / "allowed_signers").read_text()
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def pin(name, text=INST):
    m = re.search(rf"^{name}=(\S+)", text, re.M)
    return m.group(1) if m else ""


def heredoc(after):
    """The python the installer runs on the line starting with `after`."""
    body = INST.split(after, 1)[1].split("<<'PY'", 1)[1].split("\n", 1)[1]
    return body.split("\nPY\n", 1)[0]


tmp = pathlib.Path(tempfile.mkdtemp())

# ---- SR-32: the trust root ----------------------------------------------------
FP = pin("SIGNERS_FINGERPRINT")


def fingerprint(blob64):
    return "SHA256:" + base64.b64encode(hashlib.sha256(base64.b64decode(blob64)).digest()).decode().rstrip("=")


keys = [l.split() for l in SIGNERS.splitlines() if l.strip() and not l.startswith("#")]
check(len(keys) >= 1 and {fingerprint(k[2]) for k in keys} == {FP},
      "the installer's pin is the fingerprint of the key deploy/allowed_signers names")
check(pin("SIGNERS_FINGERPRINT", BUILD) == FP, "the image build pins the same key, written out a second time")
check(INST.index('python3 - "$SIGNERS_FINGERPRINT"') < INST.index('echo "== packages =="')
      < INST.index("install -m 0644 deploy/allowed_signers /opt/stratoscan/allowed_signers"),
      "it is checked before anything is installed, long before the file is copied")
signers_check = heredoc('python3 - "$SIGNERS_FINGERPRINT"')


def signers(text, rotate=""):
    d = pathlib.Path(tempfile.mkdtemp(dir=tmp))
    (d / "deploy").mkdir()
    (d / "deploy" / "allowed_signers").write_text(text)
    return subprocess.run([sys.executable, "-", FP, rotate], input=signers_check, cwd=d, capture_output=True, text=True)


def other_key(seed):
    blob = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + hashlib.sha256(seed).digest()
    return base64.b64encode(blob).decode()


OTHER = other_key(b"another key")
r = signers(SIGNERS)
check(r.returncode == 0, "the shipped file passes" + ("" if r.returncode == 0 else ": " + r.stderr.strip()))
r = signers(SIGNERS + f"stratoscan-release ssh-ed25519 {OTHER} someone else\n")
check(r.returncode != 0 and "refusing to install it as the trust root" in r.stderr and fingerprint(OTHER) in r.stderr,
      "a file with one more key is refused, and the key is named by its fingerprint")
r = signers(f"stratoscan-release ssh-ed25519 {OTHER} someone else\n")
check(r.returncode != 0, "so is a file with only another key")
r = signers(SIGNERS + f'stratoscan-release namespaces="stratoscan" ssh-ed25519 {OTHER} with options\n')
check(r.returncode != 0, "options before the key do not hide it")
r = signers(SIGNERS + f"stratoscan-release ssh-ed25519 {OTHER} new key\n", rotate=fingerprint(OTHER))
check(r.returncode == 0, "a rotation passes when the new key's fingerprint is given by hand as ROTATE_SIGNERS")
r = signers(SIGNERS + f"stratoscan-release ssh-ed25519 {OTHER} new key\n", rotate=fingerprint(other_key(b"a third")))
check(r.returncode != 0, "but only for that key")
r = signers("# nothing but comments\n\n")
check(r.returncode != 0 and "no key" in r.stderr, "a file with no key at all is refused: the unit could never update")
r = signers(SIGNERS + "stratoscan-release not-a-key\n")
check(r.returncode != 0, "and so is a line that is not a key")
check('"${ROTATE_SIGNERS:-}"' in INST and "ROTATE_SIGNERS" not in BUILD.replace("no\n# ROTATE_SIGNERS to wave it through", ""),
      "the image build has no way to wave another key through")
check('"$SIGNERS_IN_IMAGE" = "$SIGNERS_FINGERPRINT"' in BUILD and "$MNT/opt/stratoscan/allowed_signers" in BUILD,
      "and it checks the file that ended up in the image")

# ---- SR-35: readsb and the aircraft database -----------------------------------
for name in ("READSB_COMMIT", "DUMP978_COMMIT", "TAR1090_COMMIT", "TAR1090_DB_COMMIT", "READSB_INSTALLER_COMMIT"):
    check(bool(re.fullmatch(r"[0-9a-f]{40}", pin(name))), f"{name} is a whole commit id")
readsb = INST.split('echo "== receiver: readsb')[1].split('echo "== 978 MHz receiver')[0]
asked, built = readsb.find("git ls-remote"), readsb.find("bash /tmp/readsb-install.sh")
check(0 < asked < readsb.find('[ "$READSB_NOW" = "$READSB_COMMIT" ]') < readsb.find("curl -fsSL") < built
      and "exit 1" in readsb[asked:built],
      "readsb's tag is asked for and compared with the pinned commit before anything is fetched or built")
after = readsb[built:]
check('rev-parse HEAD 2>/dev/null)" != "$READSB_COMMIT"' in after and "rm -f /usr/bin/readsb" in after and "exit 1" in after,
      "what was built is checked again, and taken away if it is not the pin (a second run would call it installed)")
# The tag's answer, as git ls-remote gives it: one line for a plain tag, a
# second (the commit) for an annotated one. The installer's awk takes the last.
awk = re.search(r"\| awk '([^']+)'", readsb).group(1)
for lines, want in (("aaa\trefs/tags/v1\n", "aaa"), ("ttt\trefs/tags/v1\nccc\trefs/tags/v1^{}\n", "ccc"), ("", "")):
    out = subprocess.run(["awk", awk], input=lines, capture_output=True, text=True).stdout.strip()
    check(out == want, f"the tag's commit is read right ({'annotated' if '^' in lines else 'plain' if lines else 'no answer'})")

tar = INST.split('echo "== map history: tar1090')[1].split("# tar1090's installer also serves itself")[0]
steps = [tar.find(s) for s in ('fetch -q --depth 1 https://github.com/wiedehopf/tar1090-db.git "$TAR1090_DB_COMMIT"',
                               'rev-parse HEAD)" = "$TAR1090_DB_COMMIT"', "sed -i 's,", "grep -q 'getGIT",
                               "bash /tmp/tar1090-src/install.sh", 'rev-parse HEAD 2>/dev/null)" = "$TAR1090_DB_COMMIT"',
                               'echo "$TAR1090_COMMIT" > /usr/local/share/tar1090/git/.stratoscan-commit')]
check(all(i > 0 for i in steps) and steps == sorted(steps),
      "the database is fetched at its pinned commit, proved, kept from tar1090's installer, and proved again before the install counts as done")
# The one line of tar1090's installer (at the pinned commit) that takes the
# database from master, and the installer's sed and grep run against it.
UPSTREAM = ('if ! { [[ "$1" == "test" ]] && cd "$gpath/git-db"; }; then\n'
            '    if  [[ "$(cat "$gpath/git-db/version" 2>/dev/null)" != "$DB_VERSION_NEW" ]]; then\n'
            '        getGIT "$db_repo" "master" "$gpath/git-db" || true\n'
            '    fi\nfi\n'
            '        if ! getGIT "$repo" "master" "$gpath/git"; then\n')
expr = re.search(r"sed -i '([^']+)' /tmp/tar1090-src/install\.sh", tar).group(1)
guard = re.search(r"grep -q '([^']+)' /tmp/tar1090-src/install\.sh", tar).group(1)
out = subprocess.run(["sed", expr], input=UPSTREAM, capture_output=True, text=True).stdout
check('getGIT "$db_repo"' not in out and "        true   # StratoScan: the database is pinned\n" in out
      and 'getGIT "$repo" "master" "$gpath/git"' in out and out.count("\n") == UPSTREAM.count("\n"),
      "the sed takes out that one line and nothing else")
check(subprocess.run(["grep", "-q", guard], input=out, text=True).returncode == 1
      and subprocess.run(["grep", "-q", guard], input=UPSTREAM, text=True).returncode == 0
      and subprocess.run(["grep", "-q", guard], input=UPSTREAM.replace('"master"', '"main"'), text=True).returncode == 0,
      "and the guard after it stops the install if the line is still there, or was reworded")
check("READSB_COMMIT" in BUILD and "TAR1090_DB_COMMIT" in BUILD and "readsb is not the pinned commit" in BUILD
      and "the aircraft database is not the pinned commit" in BUILD and 'echo "tar1090-db: ' in BUILD,
      "the image build checks both and records them in MANIFEST.txt")

# ---- SR-28: the release floor ---------------------------------------------------
floor_py = heredoc('python3 - "$BUILD_SERIAL"')
floor_sh = "set -e\n" + INST.split("# floor applies as before.\n", 1)[1].split('python3 - "$BUILD_SERIAL"', 1)[0] + 'printf "%s" "$BUILD_SERIAL"\n'


def record(state, serial):
    return subprocess.run([sys.executable, "-", serial], input=floor_py, capture_output=True, text=True,
                          env=dict(os.environ, STRATOSCAN_OTA_STATE=str(state)))


def read(state):
    return json.loads((state / "installed.json").read_text())


st = tmp / "fresh"
r = record(st, "748")
check(r.returncode == 0 and read(st)["serial"] == 748, "a unit with no record gets one: the serial of the code it was installed from")
check(oct((st / "installed.json").stat().st_mode & 0o777) == "0o644", "readable by the heartbeat, as an update's own record is")
r = record(st, "900")
check(read(st)["serial"] == 748 and "kept" in r.stdout, "an existing record is left alone, even by a newer tree")
(st / "installed.json").write_text(json.dumps({"serial": 950, "version": "2026.12.01.1"}))
record(st, "748")
check(read(st) == {"serial": 950, "version": "2026.12.01.1"}, "and never lowered: an update's record survives a re-run of the installer whole")
for bad in ("", "not json", "[]", '{"serial": "x"}', '{"serial": 0}'):
    st = pathlib.Path(tempfile.mkdtemp(dir=tmp))
    (st / "installed.json").write_text(bad)
    record(st, "748")
    check(read(st)["serial"] == 748, f"a record that says nothing ({bad or 'empty'}) is replaced")
for serial in ("", "junk", "0", "-5"):
    st = pathlib.Path(tempfile.mkdtemp(dir=tmp)) / "s"
    r = record(st, serial)
    check(r.returncode == 0 and not (st / "installed.json").exists() and "built-in floor" in r.stdout,
          f"a tree that cannot say its serial ({serial or 'nothing'}) writes no record")

# The updater reads the record the way it reads its own.
os.environ["STRATOSCAN_OTA_STATE"] = str(tmp / "ota")
import importlib.util
spec = importlib.util.spec_from_file_location("ota", ROOT / "deploy" / "ota.py")
ota = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ota)
record(tmp / "ota", str(ota.FLOOR_SERIAL + 50))
check(ota.installed_serial() == ota.FLOOR_SERIAL + 50 and ota.floor_serial() == ota.FLOOR_SERIAL + 50 and ota.installed_version() == "",
      "ota.py takes it as its floor: nothing at or below the build's serial is an update")
os.remove(tmp / "ota" / "installed.json")
record(tmp / "ota", "5")
check(ota.floor_serial() == ota.FLOOR_SERIAL, "and a low count can never take the floor below the one built into ota.py")


# Where the serial comes from, run as the installer runs it.
def git(d, *a):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *a],
                   cwd=d, check=True, capture_output=True)


def serial_in(d):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["sh", "-c", floor_sh], cwd=d, capture_output=True, text=True, env=env).stdout


repo = tmp / "repo"
repo.mkdir()
git(repo, "init", "-q")
for n in range(3):
    (repo / "f").write_text(str(n))
    git(repo, "add", "f")
    git(repo, "commit", "-q", "-m", f"c{n}")
check(serial_in(repo) == "3", "a checkout with its whole history: the commit count, as scripts/release.sh numbers a release")
git(tmp, "clone", "-q", "--depth", "1", repo.as_uri(), "shallow")
check(serial_in(tmp / "shallow") == "", "a shallow clone's count is not a serial: nothing")
plain = tmp / "plain"
plain.mkdir()
check(serial_in(plain) == "", "a tree with no git: nothing")
(plain / ".build-serial").write_text("748\n")
check(serial_in(plain) == "748", "the image's copy (no history) carries the count the build wrote beside it")
check('rev-list --count HEAD)' in BUILD and '> "$MNT/opt/stratoscan-src/.build-serial"' in BUILD
      and BUILD.index(".build-serial") < BUILD.index("customize.sh"), "the image build writes it before the installer runs")
check("is-shallow-repository" in BUILD and 'if [ -n "$BUILD_SERIAL" ]' in BUILD and "installed.json" in BUILD,
      "only from a whole history, and then the image is checked for the record")
check("installed.json" not in BUILD.split("do mustnot")[0].split("for f in")[-1], "the record is not among what an image must not ship")
rel = (ROOT / "scripts" / "release.sh").read_text()
check('SERIAL=$(git rev-list --count "$SHA")' in rel, "(a release's serial is still its commit's count)")

# ---- SR-43: SSH host keys --------------------------------------------------------
ssh = INST.split("install -m 0644 deploy/10-stratoscan-ssh.conf")[1].split("install -d -m 0755 /etc/systemd/journald.conf.d")[0]
check(0 < ssh.find("ls /etc/ssh/ssh_host_*_key") < ssh.find("ssh-keygen -A") < ssh.find("if sshd -t"),
      "a unit with no host keys makes its own before sshd checks its config (which fails without any)")
check("ssh-keygen -A >/dev/null 2>&1; then" in ssh and "exit 1" not in ssh, "and a failure there does not stop the install")
for k in ("ssh_host_ed25519_key", "ssh_host_ecdsa_key", "ssh_host_rsa_key"):
    check(f"/etc/ssh/{k}" in BUILD.split("do mustnot")[0], f"the factory image must not ship {k}: every unit's would be the same")

print("install pin checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
