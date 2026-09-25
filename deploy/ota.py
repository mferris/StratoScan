#!/usr/bin/env python3
"""Over-the-air updates: check, verify, apply, and roll back on its own.

The reason this is safe enough to put on a device in somebody else's house is
not the download. It is three things that happen around it:

  1. NOTHING IS TRUSTED WITHOUT A SIGNATURE. The manifest must carry an ssh
     signature from the key in /opt/flightradar/allowed_signers, which was put
     there before the unit shipped. GitHub is delivery, not trust: a
     compromised account could publish a release but could not sign one.

  2. THE SERIAL MUST INCREASE. An old release stays correctly signed forever,
     so without this a device could be walked backwards onto a version whose
     bugs are already fixed.

  3. A BAD UPDATE UNDOES ITSELF. After applying, the display has to paint a
     frame within PAINT_TIMEOUT_S or the previous files go back and the kiosk
     restarts again. The heartbeat that proves this already exists -- it is
     what the frozen-display watchdog uses -- so an update that blanks the
     screen is caught by the thing already watching the screen, with nobody
     in the room.

Usage:  ota.py check         look for a newer release, verify it, stage nothing
        ota.py stage         download and verify into the staging directory
        ota.py apply         install what is staged, verify paint, roll back
        ota.py status        print what is installed and what is available
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

REPO = os.environ.get("FLIGHTRADAR_OTA_REPO", "mferris/FlightRadar")
# Overridable so the whole path -- fetch, verify, stage, reject -- can be
# exercised against a local server in tests. The default is the real thing;
# nothing about the trust model depends on this being GitHub.
API_BASE = os.environ.get("FLIGHTRADAR_OTA_API", "https://api.github.com")
NAMESPACE = "flightradar"
ALLOWED_SIGNERS = os.environ.get(
    "FLIGHTRADAR_ALLOWED_SIGNERS", "/opt/flightradar/allowed_signers")
SIGNER_ID = "flightradar-release"
STATE_DIR = os.environ.get("FLIGHTRADAR_OTA_STATE", "/var/lib/flightradar-ota")
INSTALLED = os.path.join(STATE_DIR, "installed.json")
STATUS = os.path.join(STATE_DIR, "status.json")
STAGING = os.path.join(STATE_DIR, "staging")
ROLLBACK = os.path.join(STATE_DIR, "rollback")
LOCK = os.path.join(STATE_DIR, "ota.lock")
def _default_heartbeat():
    """The kiosk user's runtime directory, resolved from their uid.

    Not /run/flightradar: that belongs to setupd's RuntimeDirectory= and is
    recreated root-owned on every restart of the root helper.
    """
    try:
        import pwd
        uid = pwd.getpwnam(os.environ.get("FLIGHTRADAR_KIOSK_USER", "mferris")).pw_uid
        return f"/run/user/{uid}/flightradar-painted"
    except (KeyError, ImportError):
        return "/tmp/flightradar-painted"


HEARTBEAT = os.environ.get("FLIGHTRADAR_PAINT_STAMP", _default_heartbeat())

WEB_ROOT = os.environ.get("FLIGHTRADAR_WEB_ROOT", "/var/www/html")
OPT_ROOT = os.environ.get("FLIGHTRADAR_OPT_ROOT", "/opt/flightradar")
KIOSK_UNIT = "flightradar-kiosk.service"
KIOSK_USER = os.environ.get("FLIGHTRADAR_KIOSK_USER", "mferris")

HTTP_TIMEOUT_S = 30
MAX_BUNDLE_BYTES = 32 * 1024 * 1024
PAINT_TIMEOUT_S = 90
RESTART_SETTLE_S = 8

# Where each file in the bundle is installed. A path not listed here is NOT
# written -- an update cannot invent a destination, drop a file into a systemd
# unit directory, or overwrite the allowed_signers that vouch for it.
DESTS = {
    "index.html": os.path.join(WEB_ROOT, "index.html"),
}
DEPLOY_ALLOWED = {
    "wake-listener.py", "sighting-store.py", "approach-store.py",
    "network-compare.py", "photo-proxy.py", "funnel-gateway.py",
    "setup-server.py", "setup-ui.html", "shm-guard.sh", "ota.py",
    "airports.json", "net-watchdog.py",
    # ota-auto.sh decides whether an unattended update may proceed, running as
    # root on a timer on a device in someone else's house. Omitting it would
    # ship it in the bundle and then refuse to install it -- which is the same
    # trap setupd.py was in below, and worse here: the one file whose bugs
    # nobody can reach around is the one that installs the fixes.
    "ota-auto.sh",
    # setupd.py is the root helper, and leaving it out looked like caution but
    # bought nothing: ota.py is on this list and also runs as root, so anyone
    # who can sign a release can already run code as root. All excluding it
    # achieved was making a bug in the privileged helper unfixable on a unit
    # that has been given away. The signature is the protection here, not the
    # file list.
    "setupd.py",
}
# Deliberately NOT installable, for reasons that are not symmetrical:
#
#   allowed_signers      the root of trust. An update must never be able to
#                        replace the key that vouches for it, or one bad
#                        release owns the device permanently, with no way back.
#   *.service, *.timer   systemd units need a daemon-reload and possibly an
#                        enable to take effect, and ota.py does neither -- so
#                        writing them would look like it worked and change
#                        nothing until the next reboot. Better to refuse than
#                        to half-apply.
#
# This list is itself shippable: ota.py can update ota.py, so widening it later
# is a normal release, not a one-way door.


class Fail(Exception):
    pass


def log(msg):
    print(f"ota: {msg}", flush=True)


def dest_for(name):
    """Install path for a bundle member, or None if it must not be written."""
    if name in DESTS:
        return DESTS[name]
    if name.startswith("deploy/"):
        base = name[len("deploy/"):]
        if base in DEPLOY_ALLOWED:
            return os.path.join(OPT_ROOT, base)
    return None


def write_status(**kw):
    os.makedirs(STATE_DIR, exist_ok=True)
    kw["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # Stamped here rather than at each call site. There are eight of them and
    # "what is this device running" has to be answerable in every state --
    # including error and rolled_back, which are exactly when someone asks.
    # setdefault, so a caller that knows better still wins.
    kw.setdefault("installed_version", installed_version())
    kw.setdefault("installed_serial", installed_serial())
    tmp = STATUS + ".tmp"
    with open(tmp, "w") as f:
        json.dump(kw, f, indent=1)
    os.replace(tmp, STATUS)


def installed_serial():
    try:
        with open(INSTALLED) as f:
            return int(json.load(f).get("serial", 0))
    except (OSError, ValueError, TypeError):
        return 0


def installed_version():
    """The version string this device is actually running.

    Recorded at install time and, until now, never reported: status carried
    installed_serial, an integer nobody can read off a screen and say out
    loud. "What version are you on" is the first question of any support call
    about a unit in someone else's house, and the answer has to be on the
    device's own settings screen, not in a file only ssh can reach.
    """
    try:
        with open(INSTALLED) as f:
            return str(json.load(f).get("version") or "")
    except (OSError, ValueError, TypeError):
        return ""


def fetch(url, limit=MAX_BUNDLE_BYTES):
    req = urllib.request.Request(url, headers={"User-Agent": "FlightRadar-OTA"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise Fail(f"{url} larger than {limit} bytes")
    return data


def latest_release():
    data = json.loads(fetch(
        f"{API_BASE}/repos/{REPO}/releases/latest", 1 << 20))
    assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
    for need in ("manifest.json", "manifest.json.sig"):
        if need not in assets:
            raise Fail(f"release {data.get('tag_name')} has no {need}")
    return data.get("tag_name", "?"), assets


def verify_manifest(raw_manifest, raw_sig):
    """ssh-keygen -Y verify, or refuse. Nothing downstream runs without this."""
    with tempfile.TemporaryDirectory() as td:
        sig = os.path.join(td, "m.sig")
        with open(sig, "wb") as f:
            f.write(raw_sig)
        p = subprocess.run(
            ["ssh-keygen", "-Y", "verify", "-f", ALLOWED_SIGNERS,
             "-I", SIGNER_ID, "-n", NAMESPACE, "-s", sig],
            input=raw_manifest, capture_output=True, timeout=30)
    if p.returncode != 0:
        raise Fail("signature rejected: "
                   + (p.stderr or b"").decode("utf-8", "replace").strip())
    return json.loads(raw_manifest.decode("utf-8"))


def check():
    tag, assets = latest_release()
    manifest = verify_manifest(fetch(assets["manifest.json"], 1 << 20),
                               fetch(assets["manifest.json.sig"], 1 << 16))
    have, want = installed_serial(), int(manifest["serial"])
    newer = want > have
    write_status(state="checked", tag=tag, version=manifest["version"],
                 serial=want, installed_serial=have, update_available=newer)
    log(f"{tag} serial {want}, installed {have} -> "
        + ("update available" if newer else "up to date"))
    return manifest, assets, newer


def stage():
    manifest, assets, newer = check()
    if not newer:
        return None
    name = manifest["bundle"]["name"]
    if name not in assets:
        raise Fail(f"manifest names {name} but the release has no such asset")
    blob = fetch(assets[name])
    got = hashlib.sha256(blob).hexdigest()
    if got != manifest["bundle"]["sha256"]:
        raise Fail("bundle hash does not match the signed manifest")

    shutil.rmtree(STAGING, ignore_errors=True)
    os.makedirs(STAGING, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tf:
        tf.write(blob)
        arc = tf.name
    try:
        with tarfile.open(arc) as t:
            for m in t.getmembers():
                # Path traversal: a member named ../../etc/passwd would escape
                # the staging directory on extract.
                if m.name.startswith("/") or ".." in m.name.split("/"):
                    raise Fail(f"unsafe path in bundle: {m.name}")
                if not (m.isfile() or m.isdir()):
                    raise Fail(f"bundle contains a non-regular file: {m.name}")
            # Python's "data" filter rejects absolute paths, traversal,
            # links and special files on its own. The explicit checks above
            # stay -- this runs as root, and two independent refusals are
            # worth more than one -- but the filter also silences a
            # DeprecationWarning that becomes the default in 3.14. Passed
            # conditionally because it does not exist before 3.12.
            try:
                t.extractall(STAGING, filter="data")
            except TypeError:
                t.extractall(STAGING)
    finally:
        os.unlink(arc)

    # Every file, against the signed manifest. The bundle hash proved the
    # archive; this proves what came out of it.
    for name, entry in manifest["files"].items():
        # Accept both shapes: early manifests carried a bare hash string,
        # current ones carry {"sha256": ..., "exec": ...}.
        want_hash = entry["sha256"] if isinstance(entry, dict) else entry
        path = os.path.join(STAGING, name)
        if not os.path.isfile(path):
            raise Fail(f"manifest lists {name}, bundle does not contain it")
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != want_hash:
            raise Fail(f"{name} does not match the signed manifest")

    with open(os.path.join(STAGING, ".manifest.json"), "w") as f:
        json.dump(manifest, f)
    write_status(state="staged", version=manifest["version"],
                 serial=manifest["serial"])
    log(f"staged {manifest['version']} ({len(manifest['files'])} files verified)")
    return manifest


def paint_stamp():
    try:
        return os.stat(HEARTBEAT).st_mtime
    except OSError:
        return 0.0


def restart_kiosk():
    # Out of this process's control group, so a restart cannot kill the updater
    # mid-way and leave the device half-written with nothing watching it.
    subprocess.run(
        ["systemd-run", "--quiet", "--collect",
         "--unit", f"flightradar-ota-restart-{os.getpid()}",
         "--on-active=2s",
         "/usr/bin/systemctl", "--user", "-M", f"{KIOSK_USER}@",
         "restart", KIOSK_UNIT],
        check=False, timeout=30)


def apply():
    manifest_path = os.path.join(STAGING, ".manifest.json")
    if not os.path.isfile(manifest_path):
        raise Fail("nothing staged")
    with open(manifest_path) as f:
        manifest = json.load(f)
    if int(manifest["serial"]) <= installed_serial():
        raise Fail("staged release is not newer than what is installed")

    plan = []
    for name, entry in manifest["files"].items():
        dest = dest_for(name)
        if dest is None:
            continue
        want_exec = bool(entry.get("exec")) if isinstance(entry, dict) else None
        plan.append((os.path.join(STAGING, name), dest, want_exec))
    if not plan:
        raise Fail("staged release installs nothing")

    shutil.rmtree(ROLLBACK, ignore_errors=True)
    os.makedirs(ROLLBACK, exist_ok=True)
    saved = []
    for _, dest, _ in plan:
        if os.path.exists(dest):
            keep = os.path.join(ROLLBACK, dest.lstrip("/").replace("/", "_"))
            shutil.copy2(dest, keep)
            saved.append((keep, dest))
    with open(os.path.join(ROLLBACK, "prev.json"), "w") as f:
        json.dump({"serial": installed_serial(), "files": saved}, f)

    before = paint_stamp()
    if before == 0.0:
        # No stamp at all means the paint check cannot answer, and a check that
        # cannot answer would roll back every update including the good ones.
        # That is exactly what happened once: the stamp lived in a directory
        # another service owned, systemd recreated it root-owned, and a
        # perfectly good release was undone because nothing could write the
        # file. Refuse to start rather than install something that is
        # guaranteed to be reverted.
        raise Fail(f"no paint heartbeat at {HEARTBEAT} -- the display check "
                   f"cannot run, so an update would be rolled back whatever "
                   f"happened. Is flightradar-wake.service running?")
    for src, dest, want_exec in plan:
        tmp = dest + ".ota-tmp"
        shutil.copy2(src, tmp)
        # The signed manifest decides whether this is a program. Falling back
        # to whatever mode survived the tar is how a 755 script became 644.
        if want_exec is None:
            want_exec = os.access(dest, os.X_OK) if os.path.exists(dest) else False
        os.chmod(tmp, 0o755 if want_exec else 0o644)
        os.replace(tmp, dest)
    log(f"wrote {len(plan)} files, restarting to verify")
    write_status(state="applying", version=manifest["version"],
                 serial=manifest["serial"])
    restart_kiosk()

    deadline = time.time() + RESTART_SETTLE_S + PAINT_TIMEOUT_S
    while time.time() < deadline:
        if paint_stamp() > before:
            with open(INSTALLED, "w") as f:
                json.dump({"serial": int(manifest["serial"]),
                           "version": manifest["version"]}, f)
            write_status(state="ok", version=manifest["version"],
                         serial=manifest["serial"])
            log(f"{manifest['version']} installed and painting")
            return True
        time.sleep(2)

    log("no frame painted after the update -- rolling back")
    for keep, dest in saved:
        shutil.copy2(keep, dest)
    restart_kiosk()
    write_status(state="rolled_back", version=manifest["version"],
                 serial=manifest["serial"],
                 message="the display did not paint after the update")
    return False


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        if cmd == "status":
            try:
                with open(STATUS) as f:
                    print(f.read())
            except OSError:
                print(json.dumps({"state": "unknown",
                                  "installed_version": installed_version(),
                                  "installed_serial": installed_serial()}))
            return 0
        if cmd == "check":
            check(); return 0
        if cmd == "stage":
            stage(); return 0
        if cmd == "apply":
            if stage() is None:
                log("already up to date"); return 0
            return 0 if apply() else 1
        log(f"unknown command {cmd}")
        return 2
    except Fail as e:
        log(f"REFUSED: {e}")
        write_status(state="error", message=str(e))
        return 1
    except Exception as e:
        log(f"failed: {type(e).__name__}: {e}")
        write_status(state="error", message=f"{type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
