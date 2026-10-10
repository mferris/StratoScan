#!/usr/bin/env python3
"""Tests for the OTA updater, run against a local release server.

The interesting cases are all REFUSALS. An updater that installs a good build
is easy; one that installs a tampered, downgraded, or hostile build is a way
into every unit that was ever given away. So each test below is a thing that
must NOT happen, and each has a matching positive control so a refusal for the
wrong reason (a broken server, a missing file) cannot pass as a refusal for
the right one.
"""
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OTA = os.path.join(HERE, "..", "deploy", "ota.py")

checks = 0
failures = []


def ok(cond, label):
    global checks
    checks += 1
    if not cond:
        failures.append(label)


class Server(http.server.BaseHTTPRequestHandler):
    root = None

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        name = os.path.basename(path)
        if path.endswith("/releases/latest"):
            body = json.dumps(self.server.release).encode()
        else:
            f = os.path.join(self.root, name)
            if not os.path.isfile(f):
                self.send_error(404)
                return
            body = open(f, "rb").read()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def build_release(tmp, key, serial=2, version="9.9.9", payload=b"<html>new</html>",
                  member="index.html", sigs=("new", "old"), old_key=None,
                  rollout=True, rollout_key=None, rollout_ns="stratoscan-rollout"):
    """Produce a signed release exactly as scripts/release.sh does.

    `rollout`: True for the policy release.sh writes when nothing is said
    (ring 3, everyone), a dict to override its fields, None for a release
    carrying no policy at all.
    """
    src = os.path.join(tmp, "src")
    os.makedirs(src, exist_ok=True)
    p = os.path.join(src, os.path.basename(member))
    with open(p, "wb") as f:
        f.write(payload)
    bundle = os.path.join(tmp, "b.tar.gz")
    with tarfile.open(bundle, "w:gz") as t:
        t.add(p, arcname=member)
    blob = open(bundle, "rb").read()
    files = {}
    with tarfile.open(bundle) as t:
        for m in t.getmembers():
            if m.isfile():
                files[m.name] = {
                    "sha256": hashlib.sha256(t.extractfile(m).read()).hexdigest(),
                    "exec": bool(m.mode & 0o111),
                }
    manifest = {
        "version": version, "serial": serial,
        "bundle": {"name": "b.tar.gz", "sha256": hashlib.sha256(blob).hexdigest()},
        "files": files,
    }
    mpath = os.path.join(tmp, "manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    # Remove any signature left by a previous build. Without this the old .sig
    # survives, the next case verifies a stale signature, and every test after
    # the first fails with "signature rejected" -- a real refusal, for entirely
    # the wrong reason, which is worse than no test at all.
    # As release.sh does since the rename: manifest.stratoscan.sig in the
    # 'stratoscan' namespace ("new") and manifest.json.sig in 'flightradar'
    # ("old", what pre-rename updaters read). A test can publish either alone.
    sig = mpath + ".sig"
    new_sig = os.path.join(tmp, "manifest.stratoscan.sig")
    for f in (sig, new_sig):
        if os.path.exists(f):
            os.unlink(f)
    if "new" in sigs:
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", key, "-n", "stratoscan",
                        mpath], check=True, capture_output=True)
        os.rename(sig, new_sig)
    if "old" in sigs:
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", old_key or key, "-n", "flightradar",
                        mpath], check=True, capture_output=True)
    # The rollout policy, signed in its own namespace like release.sh does.
    rpath = os.path.join(tmp, "rollout.json")
    for f in (rpath, rpath + ".sig"):
        if os.path.exists(f):
            os.unlink(f)
    if rollout is not None:
        policy = {"kind": "rollout", "version": version, "serial": serial, "ring": 3,
                  "paused": False, "released_at": "2026-10-09T00:00:00Z",
                  "at": "2026-10-09T00:00:00Z", "note": "test"}
        if isinstance(rollout, dict):
            policy.update(rollout)
        with open(rpath, "w") as f:
            json.dump(policy, f, indent=1, sort_keys=True)
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", rollout_key or key, "-n", rollout_ns,
                        rpath], check=True, capture_output=True)
    return manifest


def run(tmp, cmd, state, allowed, env_extra=None, ring=None, flags=()):
    env = dict(os.environ)
    env.update({
        "STRATOSCAN_OTA_API": f"http://127.0.0.1:{tmp['port']}",
        "STRATOSCAN_OTA_REPO": "t/t",
        "STRATOSCAN_ALLOWED_SIGNERS": allowed,
        "STRATOSCAN_OTA_STATE": state,
        # A ring file that does not exist, unless the case puts the unit in
        # one: the default is what a unit nobody placed gets.
        "STRATOSCAN_RING_FILE": os.path.join(state, "ring"),
    })
    env.update(env_extra or {})
    if ring is not None:
        os.makedirs(state, exist_ok=True)
        with open(os.path.join(state, "ring"), "w") as f:
            f.write(f"{ring}\n")
    return subprocess.run([sys.executable, OTA, cmd, *flags], env=env,
                          capture_output=True, text=True, timeout=90)


def status_of(state):
    try:
        with open(os.path.join(state, "status.json")) as f:
            return json.load(f)
    except OSError:
        return {}


def main():
    tmp = tempfile.mkdtemp()
    keydir = os.path.join(tmp, "k")
    os.makedirs(keydir)
    good = os.path.join(keydir, "good")
    evil = os.path.join(keydir, "evil")
    for k in (good, evil):
        subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", k],
                       check=True, capture_output=True)
    allowed = os.path.join(keydir, "allowed_signers")
    with open(allowed, "w") as f:
        f.write("stratoscan-release " + open(good + ".pub").read())
        f.write("flightradar-release " + open(good + ".pub").read())
    # A unit whose allowed_signers predates the rename: the key under its old
    # name only. It must still accept releases signed in the new namespace.
    allowed_old = os.path.join(keydir, "allowed_signers_old")
    with open(allowed_old, "w") as f:
        f.write("flightradar-release " + open(good + ".pub").read())

    rel = os.path.join(tmp, "rel")
    os.makedirs(rel)
    Server.root = rel
    httpd = http.server.HTTPServer(("127.0.0.1", 0), Server)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    ctx = {"port": port}

    def publish(**kw):
        for f in os.listdir(rel):
            os.unlink(os.path.join(rel, f))
        m = build_release(tmp, kw.pop("key", good), **kw)
        names = [n for n in ("manifest.json", "manifest.stratoscan.sig", "manifest.json.sig", "b.tar.gz",
                             "rollout.json", "rollout.json.sig")
                 if os.path.exists(os.path.join(tmp, n))]
        for n in names:
            shutil.copy(os.path.join(tmp, n), os.path.join(rel, n))
        httpd.release = {"tag_name": m["version"], "assets": [
            {"name": n, "browser_download_url":
             f"http://127.0.0.1:{port}/{n}"}
            for n in names]}
        return m

    # --- positive control: a properly signed release must be accepted -------
    publish(serial=5)
    st = os.path.join(tmp, "s1")
    r = run(ctx, "stage", st, allowed)
    ok(r.returncode == 0, "a correctly signed release must stage")
    ok(os.path.isfile(os.path.join(st, "staging", "index.html")),
       "staging must contain the payload")

    # --- the signing rename (2026-09-30): every combination a unit may meet --
    publish(serial=5, sigs=("old",))
    r = run(ctx, "stage", os.path.join(tmp, "sr1"), allowed)
    ok(r.returncode == 0, "a pre-rename release (old signature only) must still stage")
    publish(serial=5, sigs=("new",))
    r = run(ctx, "stage", os.path.join(tmp, "sr2"), allowed)
    ok(r.returncode == 0, "a release with only the new signature must stage")
    publish(serial=5, sigs=("new",))
    r = run(ctx, "stage", os.path.join(tmp, "sr3"), allowed_old)
    ok(r.returncode == 0, "a unit whose allowed_signers names the key only by its old name must accept the new signature")
    publish(serial=5, sigs=("new", "old"), key=evil)   # new sig by the wrong key, old by the right one
    r = run(ctx, "stage", os.path.join(tmp, "sr4"), allowed)
    ok(r.returncode != 0, "both signatures by the wrong key must be refused")
    publish(serial=5, sigs=("new", "old"), key=evil, old_key=good, rollout_key=good)
    r = run(ctx, "stage", os.path.join(tmp, "sr5"), allowed)
    ok(r.returncode == 0, "a bad new signature falls back to a valid old one (same trusted key signed it)")

    # --- signed by the WRONG key -------------------------------------------
    publish(serial=6, key=evil)
    r = run(ctx, "stage", os.path.join(tmp, "s2"), allowed)
    ok(r.returncode != 0 and "signature" in (r.stdout + r.stderr).lower(),
       "a release signed by an unknown key must be refused")

    # --- tampered payload, signature left intact ---------------------------
    publish(serial=7)
    with open(os.path.join(rel, "b.tar.gz"), "ab") as f:
        f.write(b"x")
    r = run(ctx, "stage", os.path.join(tmp, "s3"), allowed)
    ok(r.returncode != 0 and "hash" in (r.stdout + r.stderr).lower(),
       "a bundle that does not match the signed manifest must be refused")

    # --- tampered manifest -------------------------------------------------
    publish(serial=8)
    m = json.load(open(os.path.join(rel, "manifest.json")))
    m["serial"] = 99
    with open(os.path.join(rel, "manifest.json"), "w") as f:
        json.dump(m, f)
    r = run(ctx, "stage", os.path.join(tmp, "s4"), allowed)
    ok(r.returncode != 0, "an edited manifest must fail its signature")

    # --- downgrade ---------------------------------------------------------
    st5 = os.path.join(tmp, "s5")
    os.makedirs(st5, exist_ok=True)
    with open(os.path.join(st5, "installed.json"), "w") as f:
        json.dump({"serial": 50, "version": "current"}, f)
    publish(serial=10)
    r = run(ctx, "stage", st5, allowed)
    ok(not os.path.isfile(os.path.join(st5, "staging", "index.html")),
       "an older serial must not be staged over a newer install")
    ok("up to date" in (r.stdout + r.stderr).lower(),
       "a downgrade must be reported as up to date, not as an error")

    # --- staged rollout (performance audit 2026-10-09) ----------------------
    # The policy on the release says how far it may go; the unit's ring file
    # says where the unit stands. Everything unexpected holds.
    def staged(state):
        return os.path.isfile(os.path.join(state, "staging", "index.html"))

    publish(serial=20, rollout={"ring": 0})
    st = os.path.join(tmp, "r1")
    r = run(ctx, "apply", st, allowed)                      # no ring file: ring 3
    ok(r.returncode == 0 and not staged(st), "a ring-0 release must not reach a unit in ring 3")
    ok("held" in r.stdout and "update available" not in r.stdout,
       "a held release must say so and never say 'update available' (ota-auto.sh acts on those words)")
    s1 = status_of(st)
    ok(s1.get("update_available") is False and s1.get("rollout", {}).get("unit_ring") == 3
       and s1["rollout"].get("ring") == 0 and "ring 0" in (s1["rollout"].get("held") or ""),
       "status must carry the rings and why the release is held")
    st = os.path.join(tmp, "r2")
    r = run(ctx, "stage", st, allowed, ring=0)
    ok(r.returncode == 0 and staged(st), "the maintainer's unit (ring 0) takes a ring-0 release")
    ok("update available (rollout at ring 0, this unit in ring 0)" in r.stdout,
       "the journal line says which rings decided it")
    st = os.path.join(tmp, "r3")
    r = run(ctx, "stage", st, allowed, ring=1)
    ok(r.returncode == 0 and not staged(st), "a ring-1 unit waits while the rollout is at ring 0")
    publish(serial=20, rollout={"ring": 1})
    st = os.path.join(tmp, "r4")
    r = run(ctx, "stage", st, allowed, ring=1)
    ok(r.returncode == 0 and staged(st), "widening the policy to ring 1 lets a ring-1 unit in")
    st = os.path.join(tmp, "r5")
    r = run(ctx, "stage", st, allowed, ring=2)
    ok(not staged(st), "ring 2 still waits at ring 1")
    publish(serial=20, rollout={"ring": 3})
    st = os.path.join(tmp, "r6")
    r = run(ctx, "stage", st, allowed)
    ok(r.returncode == 0 and staged(st), "ring 3 (everyone) reaches a unit with no ring file")
    publish(serial=20, rollout={"ring": 3, "paused": True})
    st = os.path.join(tmp, "r7")
    r = run(ctx, "stage", st, allowed, ring=0)
    ok(r.returncode == 0 and not staged(st) and "paused" in r.stdout,
       "a paused rollout holds even the maintainer's unit")
    publish(serial=20, rollout=None)
    st = os.path.join(tmp, "r8")
    r = run(ctx, "stage", st, allowed, ring=0)
    ok(r.returncode == 0 and not staged(st) and "no rollout policy" in r.stdout,
       "a release with no policy goes nowhere (a hand-made release cannot reach everyone by accident)")
    publish(serial=20, rollout={"serial": 19, "ring": 3})
    st = os.path.join(tmp, "r9")
    r = run(ctx, "stage", st, allowed, ring=0)
    ok(not staged(st) and "serial 19" in r.stdout, "a policy left over from another release does not apply")
    publish(serial=20, rollout={"ring": 3}, rollout_key=evil)
    st = os.path.join(tmp, "r10")
    r = run(ctx, "stage", st, allowed, ring=0)
    ok(r.returncode != 0 and "signature" in (r.stdout + r.stderr).lower(),
       "a policy signed by the wrong key is a refusal, not 'no policy'")
    publish(serial=20, rollout={"ring": 3}, rollout_ns="stratoscan")
    st = os.path.join(tmp, "r11")
    r = run(ctx, "stage", st, allowed, ring=0)
    ok(r.returncode != 0, "a signature made for a manifest must not vouch for a policy (namespaces)")
    publish(serial=20, rollout={"ring": 0})
    st = os.path.join(tmp, "r12")
    r = run(ctx, "stage", st, allowed, ring=3, flags=("--ignore-rollout",))
    ok(r.returncode == 0 and staged(st) and status_of(st).get("rollout", {}).get("held") is None,
       "--ignore-rollout takes a held release on request")
    st = os.path.join(tmp, "r13")
    r = run(ctx, "stage", st, allowed, ring=3, flags=("--no-such-flag",))
    ok(r.returncode == 2 and not staged(st), "an unknown option is refused, not ignored")
    # A unit whose ring file holds nonsense is the general public, not ring 0.
    st = os.path.join(tmp, "r14")
    r = run(ctx, "stage", st, allowed, ring="zero")
    ok(not staged(st), "an unreadable ring file means ring 3")
    # Up to date is up to date whatever the policy says: nothing is gated
    # that would not have installed anyway, and no policy is fetched.
    st = os.path.join(tmp, "r15")
    os.makedirs(st, exist_ok=True)
    with open(os.path.join(st, "installed.json"), "w") as f:
        json.dump({"serial": 20, "version": "9.9.9"}, f)
    publish(serial=20, rollout=None)
    r = run(ctx, "check", st, allowed, ring=0)
    ok(r.returncode == 0 and "up to date" in r.stdout and status_of(st).get("rollout", {}).get("unit_ring") == 0,
       "a unit already on the release reports up to date, and its ring")

    # --- path traversal in the archive -------------------------------------
    publish(serial=11, member="../../../../etc/evil.conf")
    r = run(ctx, "stage", os.path.join(tmp, "s6"), allowed)
    ok(r.returncode != 0 and "unsafe path" in (r.stdout + r.stderr).lower(),
       "a bundle member escaping the staging directory must be refused")

    # --- a file the installer is not allowed to place ----------------------
    sys.path.insert(0, os.path.join(HERE, "..", "deploy"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("ota", OTA)
    ota = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ota)
    ok(ota.dest_for("index.html") is not None, "index.html must be installable")
    ok(ota.rollout_decision({"kind": "rollout", "serial": 7, "ring": 2}, 7, 2) == (True, None),
       "a unit on the policy's ring is in")
    ok(ota.rollout_decision({"kind": "rollout", "serial": 7, "ring": "2"}, 7, 3)[0] is False,
       "a unit past the policy's ring is out")
    ok(ota.rollout_decision({"kind": "rollout", "serial": 7, "ring": "two"}, 7, 0)[0] is False,
       "a malformed ring holds rather than admits")
    ok(ota.rollout_decision({"kind": "rollout", "serial": 7, "ring": 3, "paused": 1}, 7, 0)[0] is False,
       "any true-ish pause pauses")
    ok(ota.dest_for("deploy/ota.py") is not None, "deploy/ota.py must be installable")
    ok(ota.dest_for("deploy/allowed_signers") is None,
       "an update must NOT be able to replace the key that vouches for it")
    ok(ota.dest_for("../../etc/passwd") is None, "traversal must not resolve")
    ok(ota.dest_for("deploy/stratoscan-kiosk.service") is None,
       "an update must not drop systemd units")
    ok(ota.dest_for("deploy/setupd.py") is not None,
       "the root helper must be fixable by an update")
    ok(ota.dest_for("sounds/kitten/nearby.ogg") is not None,
       "a sound theme's audio must be installable")
    ok(ota.dest_for("sounds/kitten/CREDITS.md") is None,
       "only audio extensions under sounds/ may be installed")
    ok(ota.dest_for("sounds/../../../etc/cron.d/evil.ogg") is None,
       "an .ogg extension must not excuse a traversal out of WEB_ROOT")

    # --- a changed service must actually be restarted -----------------------
    # A funnel-gateway.py security fix once sat installed-but-not-running for
    # hours because only the kiosk was restarted after an update.
    gw = ota.dest_for("deploy/funnel-gateway.py")
    ok(("system", "stratoscan-funnel-gateway.service") in ota.services_to_restart([gw]),
       "a changed gateway must be restarted, or its fix never runs")
    ok(ota.services_to_restart([ota.dest_for("deploy/wake-listener.py")])
       == [("user", "stratoscan-wake.service")],
       "wake-listener runs under the kiosk user's systemd")
    both = ota.services_to_restart([ota.dest_for("deploy/setup-server.py"),
                                    ota.dest_for("deploy/setup-ui.html")])
    ok(both == [("system", "stratoscan-setup.service")],
       "two files of one service restart it once")
    ok(ota.services_to_restart([ota.dest_for("index.html"),
                                ota.dest_for("deploy/ota-auto.sh")]) == [],
       "page assets and timer oneshots need no service restart")
    ok(ota.services_to_restart([ota.dest_for("deploy/net-watchdog.py")])
       == [("system", "stratoscan-netwatchdog.service")],
       "the watchdog is long-running since 2026-10-08, so its update restarts it")
    ok(ota.services_to_restart(["/etc/evil/funnel-gateway.py"]) == [],
       "only files in OPT_ROOT map to services")
    for name in ("sighting-store.py", "approach-store.py", "network-compare.py",
                 "photo-proxy.py", "funnel-gateway.py", "setup-server.py",
                 "setupd.py", "wake-listener.py", "tts-service.py", "events.py"):
        ok(name in ota.DEPLOY_ALLOWED and name in ota.SERVICE_FOR,
           f"{name} is updatable, so it must also be restarted when it changes")

    # An update can deliver a program before the installer has put its
    # service on that unit; that service is skipped, not restarted.
    units_dir = tempfile.mkdtemp()
    open(os.path.join(units_dir, "stratoscan-setup.service"), "w").close()
    ran = []
    real_run, real_dir = ota.subprocess.run, ota.SYSTEM_UNIT_DIR
    ota.subprocess.run = lambda argv, **k: ran.append(argv)
    ota.SYSTEM_UNIT_DIR = units_dir
    try:
        ota.restart_services([("system", "stratoscan-setup.service"),
                              ("system", "stratoscan-events.service")])
    finally:
        ota.subprocess.run, ota.SYSTEM_UNIT_DIR = real_run, real_dir
    restarted = [a for argv in ran for a in argv if a.endswith(".service")]
    ok(restarted == ["stratoscan-setup.service"],
       "an installed service is restarted and a not-yet-installed one is skipped")

    # --- an update wakes the panel before its paint check (2026-10-10) -------
    # A dark panel paints nothing, so an update applied to one was rolled back.
    stamp = os.path.join(tmp, "painted")
    open(stamp, "w").close()
    os.utime(stamp, (1, 1))
    woke = []

    class Wake(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            woke.append(self.path)
            os.utime(stamp, None)          # the page paints once the panel is lit
            self.send_response(204); self.end_headers()
        def log_message(self, *a):
            pass
    wsrv = http.server.HTTPServer(("127.0.0.1", 0), Wake)
    threading.Thread(target=wsrv.serve_forever, daemon=True).start()
    real = (ota.WAKE_URL, ota.HEARTBEAT)
    ota.WAKE_URL = f"http://127.0.0.1:{wsrv.server_address[1]}/wake?why=update"
    ota.HEARTBEAT = stamp
    try:
        ok(ota.wake_display() is True and woke == ["/wake?why=update"],
           "apply asks for the panel to wake (as a non-alert wake) and waits for a fresh frame")
        ota.WAKE_URL = "http://127.0.0.1:9/wake"
        ota.WAKE_WAIT_S = 1
        ok(ota.wake_display() is False, "no wake endpoint: it says so and goes ahead")
    finally:
        ota.WAKE_URL, ota.HEARTBEAT = real
        wsrv.shutdown()
    ok("    wake_display()\n    before = paint_stamp()" in open(OTA).read(), "apply wakes the panel before the paint check")

    # --- the kiosk user is found, never assumed ------------------------------
    d = tempfile.mkdtemp()
    conf = os.path.join(d, "lightdm.conf")
    with open(conf, "w") as f:
        f.write("[Seat:*]\n#autologin-user=\nautologin-user=stratoscan\nautologin-session=rpd-labwc\n")
    saved = os.environ.pop("STRATOSCAN_KIOSK_USER", None)
    ok(ota.detect_kiosk_user([conf]) == "stratoscan",
       "the autologin user is the kiosk user (a factory-image unit is not 'mferris')")
    override = os.path.join(d, "override.conf")
    with open(override, "w") as f:
        f.write("[Seat:*]\nautologin-user=someoneelse\n")
    ok(ota.detect_kiosk_user([conf, override]) == "someoneelse", "a later config overrides an earlier one")
    os.environ["STRATOSCAN_KIOSK_USER"] = "explicit"
    ok(ota.detect_kiosk_user([conf]) == "explicit", "an explicit override wins")
    if saved is None:
        del os.environ["STRATOSCAN_KIOSK_USER"]
    else:
        os.environ["STRATOSCAN_KIOSK_USER"] = saved
    shutil.rmtree(d, ignore_errors=True)

    httpd.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print(f"{len(failures)} of {checks} OTA checks FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"{checks}/{checks} OTA checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
