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
import filecmp
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

REPO = os.environ.get("FLIGHTRADAR_OTA_REPO", "mferris/Radome")
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
LIGHTDM_CONFS = ["/etc/lightdm/lightdm.conf"]


def detect_kiosk_user(confs=None):
    """The desktop user the kiosk runs as, without assuming a name.

    The first unit's user was hard-coded here, which a unit built from the
    factory image (user "flightradar") would not have -- every update would
    then have restarted a user that doesn't exist and waited for a paint that
    could never be reported. Order: explicit override, then the display
    manager's autologin user (that IS the kiosk session), then uid 1000.
    """
    override = os.environ.get("FLIGHTRADAR_KIOSK_USER")
    if override:
        return override
    paths = list(confs or LIGHTDM_CONFS)
    d = "/etc/lightdm/lightdm.conf.d"
    if confs is None and os.path.isdir(d):
        paths += sorted(os.path.join(d, n) for n in os.listdir(d) if n.endswith(".conf"))
    user = None
    for path in paths:
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("autologin-user=") and line.split("=", 1)[1].strip():
                        user = line.split("=", 1)[1].strip()   # later files override earlier
        except OSError:
            continue
    if user:
        return user
    try:
        import pwd
        return pwd.getpwuid(1000).pw_name
    except (KeyError, ImportError):
        return "flightradar"


def _default_heartbeat():
    """The kiosk user's runtime directory, resolved from their uid.

    Not /run/flightradar: that belongs to setupd's RuntimeDirectory= and is
    recreated root-owned on every restart of the root helper.
    """
    try:
        import pwd
        uid = pwd.getpwnam(detect_kiosk_user()).pw_uid
        return f"/run/user/{uid}/flightradar-painted"
    except (KeyError, ImportError):
        return "/tmp/flightradar-painted"


HEARTBEAT = os.environ.get("FLIGHTRADAR_PAINT_STAMP", _default_heartbeat())

WEB_ROOT = os.environ.get("FLIGHTRADAR_WEB_ROOT", "/var/www/html")
OPT_ROOT = os.environ.get("FLIGHTRADAR_OPT_ROOT", "/opt/flightradar")
KIOSK_UNIT = "flightradar-kiosk.service"
KIOSK_USER = detect_kiosk_user()

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
    # Builds the on-device fallback map; run by setupd and net-watchdog.
    "offline-map.py",
    # Opt-in health reports to the relay; run by net-watchdog.
    "heartbeat.py",
    # Weekly notable-aircraft list (plane-alert-db); run by net-watchdog.
    "notable-db.py",
    # Spoken alerts; runs in its own Piper virtualenv (installer-only).
    "tts-service.py",
    # Opt-in FlightAware feeding; run by setupd.
    "feeding.py",
    # Unit events for paired phones; its own service (installer-only unit).
    "events.py",
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

# Static web assets -- audio for the sound themes, so far -- get a narrower
# rule than DEPLOY_ALLOWED's per-file list, because they are a different kind
# of thing: browser-sandboxed content with no more privilege than index.html
# already has, not code a service runs as root. Matched by extension rather
# than by name, so adding a fifth sound later is dropping a file in sounds/,
# not also a change here -- the DEPLOY_ALLOWED list is deliberately the
# opposite of this because each entry there IS a decision to make.
#
# WIDENING THIS RULE HAS A ONE-RELEASE LAG, and it is worth understanding once
# rather than re-diagnosing it from a symptom. apply() is a single process
# invocation of the ota.py ALREADY ON DISK -- the copy from the PREVIOUS
# install. If a release both widens dest_for() (or DEPLOY_ALLOWED) AND ships
# files that need the wider rule to be installed, this run's dest_for() is
# still the OLD one: it does not know the new rule exists, silently skips
# those files (dest_for returning None is not an error, just a `continue`),
# and only THEN writes the new ota.py to disk -- too late to change what this
# run decided, because Python already has the old module loaded.
#
# This happened for real the day sounds/ shipped: staged 55 files, wrote 15,
# no error anywhere, state=ok. The four .ogg files were downloaded and hash-
# verified correctly; they were just invisible to the dest_for() that was
# still running. The fix was not a bug fix -- it was a second release, which
# ran with the now-current ota.py and installed them. A release that
# introduces a new install rule and a file that needs it should assume that
# file arrives one release later, or plan to cut a trivial follow-up.
SOUNDS_EXT_ALLOWED = {".ogg", ".mp3", ".wav"}


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
    if name.startswith("sounds/"):
        if os.path.splitext(name)[1].lower() not in SOUNDS_EXT_ALLOWED:
            return None
        # name cannot legitimately contain ".." -- it comes from walking real
        # files when the release was built -- and the tar extraction guard
        # above already refuses any member that does. This is the same
        # "two independent refusals" belt-and-braces as that guard, priced at
        # one join and one prefix check.
        dest = os.path.normpath(os.path.join(WEB_ROOT, name))
        if dest == WEB_ROOT or dest.startswith(WEB_ROOT + os.sep):
            return dest
        return None
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
    req = urllib.request.Request(url, headers={"User-Agent": "Radome-OTA"})
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


# systemd-run's --on-active timers default to AccuracySec=1min, so "in 2
# seconds" meant anywhere up to a minute: measured on RDU, restarts asked for
# at 13:09:17 ran at 13:09:38. Service restarts landed after this process had
# already reported success -- and, worse, see kiosk_started_at().
TIMER_ACCURACY = "--timer-property=AccuracySec=100ms"


def kiosk_started_at():
    """Monotonic start time of the kiosk unit, or None if it can't be read."""
    try:
        out = subprocess.run(
            ["/usr/bin/systemctl", "--user", "-M", f"{KIOSK_USER}@", "show",
             "-p", "ActiveEnterTimestampMonotonic", "--value", KIOSK_UNIT],
            capture_output=True, text=True, timeout=15).stdout.strip()
        return int(out) if out.isdigit() and int(out) > 0 else None
    except Exception:
        return None


def restart_kiosk():
    # Out of this process's control group, so a restart cannot kill the updater
    # mid-way and leave the device half-written with nothing watching it.
    subprocess.run(
        ["systemd-run", "--quiet", "--collect",
         "--unit", f"flightradar-ota-restart-{os.getpid()}",
         "--on-active=2s", TIMER_ACCURACY,
         "/usr/bin/systemctl", "--user", "-M", f"{KIOSK_USER}@",
         "restart", KIOSK_UNIT],
        check=False, timeout=30)


# Long-running services load their code once at start, so writing a new file
# changes nothing until the service restarts -- and this used to restart only
# the kiosk. Found the hard way: a security fix to funnel-gateway.py was
# "installed" and reported OK while the old, leaking gateway kept running for
# hours. Timer-driven oneshots (net-watchdog.py, shm-guard.sh, ota-auto.sh)
# and this file itself pick up a new version on their next run and need
# nothing here.
SERVICE_FOR = {
    "sighting-store.py":  ("system", "flightradar-sighting-store.service"),
    "approach-store.py":  ("system", "flightradar-approach-store.service"),
    "network-compare.py": ("system", "flightradar-network.service"),
    "photo-proxy.py":     ("system", "flightradar-photo-proxy.service"),
    "funnel-gateway.py":  ("system", "flightradar-funnel-gateway.service"),
    "setup-server.py":    ("system", "flightradar-setup.service"),
    "setup-ui.html":      ("system", "flightradar-setup.service"),
    "setupd.py":          ("system", "flightradar-setupd.service"),
    "wake-listener.py":   ("user",   "flightradar-wake.service"),
    "tts-service.py":     ("system", "flightradar-tts.service"),
    "events.py":          ("system", "flightradar-events.service"),
}
# Where the installer puts system units. An update can deliver a program
# before the installer has put its service on that unit; restarting a unit
# that does not exist only fails the restart command it shares with the
# others, so it is left out and logged instead.
SYSTEM_UNIT_DIR = os.environ.get("FLIGHTRADAR_SYSTEM_UNIT_DIR", "/etc/systemd/system")


def services_to_restart(dests):
    """The (scope, unit) pairs whose code is among `dests`, deduplicated."""
    units = []
    for dest in dests:
        if os.path.dirname(dest) != OPT_ROOT:
            continue
        pair = SERVICE_FOR.get(os.path.basename(dest))
        if pair and pair not in units:
            units.append(pair)
    return units


def restart_services(units):
    """Restart services from a transient unit, like restart_kiosk.

    Never inline: this process may be verifying the update, and a restart must
    not be able to take it down with it. ota.py always runs in its own unit
    (setupd starts it via systemd-run; ota-auto has its own service), so even
    restarting setupd here cannot reach it.
    """
    missing = [u for scope, u in units
               if scope == "system" and not os.path.exists(os.path.join(SYSTEM_UNIT_DIR, u))]
    if missing:
        log("not installed yet, not restarting: " + ", ".join(missing))
    units = [(scope, u) for scope, u in units if (scope, u) not in [("system", m) for m in missing]]
    system = [u for scope, u in units if scope == "system"]
    user = [u for scope, u in units if scope == "user"]
    if system:
        subprocess.run(
            ["systemd-run", "--quiet", "--collect",
             "--unit", f"flightradar-ota-services-{os.getpid()}",
             "--on-active=1s", TIMER_ACCURACY, "/usr/bin/systemctl", "restart", *system],
            check=False, timeout=30)
    if user:
        subprocess.run(
            ["systemd-run", "--quiet", "--collect",
             "--unit", f"flightradar-ota-userservices-{os.getpid()}",
             "--on-active=1s", TIMER_ACCURACY, "/usr/bin/systemctl", "--user", "-M",
             f"{KIOSK_USER}@", "restart", *user],
            check=False, timeout=30)
    if units:
        log("restarting " + ", ".join(u for _, u in units))


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
    # Every allowlisted file is rewritten on every release, so "in the plan"
    # is not "changed" -- compare contents, or every update would bounce every
    # service, the setup page and remote access included.
    changed = [dest for src, dest, _ in plan
               if not os.path.exists(dest) or not filecmp.cmp(src, dest, shallow=False)]
    for src, dest, want_exec in plan:
        # Every existing DEST directory (WEB_ROOT, OPT_ROOT) is already there
        # on a device that has run any prior release. This only matters for a
        # NEW subdirectory shipping for the first time -- sounds/kitten/ did
        # not exist before this file was added -- and copy2 does not create
        # parents, it raises FileNotFoundError.
        os.makedirs(os.path.dirname(dest), exist_ok=True)
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
    services = services_to_restart(changed)
    kiosk_was = kiosk_started_at()
    restart_services(services)
    restart_kiosk()

    # Only a frame painted by the NEW page proves anything. The old page keeps
    # heartbeating every 20 s until the restart actually lands, and comparing
    # against the pre-install stamp accepted one of those: .14 was reported
    # "installed and painting" before the kiosk had even restarted, so a build
    # that could not paint would have been approved by the page it replaced.
    # So wait for the kiosk unit's start time to move, and only count
    # heartbeats after that.
    restarted = False
    settle_until = time.time() + RESTART_SETTLE_S + 60
    while time.time() < settle_until:
        now_started = kiosk_started_at()
        if kiosk_was is None or now_started is None:
            time.sleep(RESTART_SETTLE_S)      # can't observe it; allow for the delay
            restarted = True
            break
        if now_started != kiosk_was:
            restarted = True
            break
        time.sleep(1)
    if not restarted:
        # The old page would keep "passing" the paint check below; a new build
        # that was never shown has not been verified, so it does not stay.
        log("the kiosk did not restart after the update")
    baseline = time.time()

    deadline = baseline + RESTART_SETTLE_S + PAINT_TIMEOUT_S if restarted else 0
    while time.time() < deadline:
        if paint_stamp() > baseline:
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
    # The services restarted onto the new code must go back to the old too,
    # or a rollback would leave them running the build it just rejected.
    restart_services(services)
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
