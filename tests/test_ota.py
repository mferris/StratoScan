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
                  member="index.html"):
    """Produce a signed release exactly as scripts/release.sh does."""
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
                files[m.name] = hashlib.sha256(t.extractfile(m).read()).hexdigest()
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
    sig = mpath + ".sig"
    if os.path.exists(sig):
        os.unlink(sig)
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", key, "-n", "flightradar",
                    mpath], check=True, capture_output=True)
    assert os.path.exists(sig), "ssh-keygen produced no signature"
    return manifest


def run(tmp, cmd, state, allowed, env_extra=None):
    env = dict(os.environ)
    env.update({
        "FLIGHTRADAR_OTA_API": f"http://127.0.0.1:{tmp['port']}",
        "FLIGHTRADAR_OTA_REPO": "t/t",
        "FLIGHTRADAR_ALLOWED_SIGNERS": allowed,
        "FLIGHTRADAR_OTA_STATE": state,
    })
    env.update(env_extra or {})
    return subprocess.run([sys.executable, OTA, cmd], env=env,
                          capture_output=True, text=True, timeout=90)


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
        for n in ("manifest.json", "manifest.json.sig", "b.tar.gz"):
            src = os.path.join(tmp, n if n != "b.tar.gz" else "b.tar.gz")
            shutil.copy(src, os.path.join(rel, n))
        httpd.release = {"tag_name": m["version"], "assets": [
            {"name": n, "browser_download_url":
             f"http://127.0.0.1:{port}/{n}"}
            for n in ("manifest.json", "manifest.json.sig", "b.tar.gz")]}
        return m

    # --- positive control: a properly signed release must be accepted -------
    publish(serial=5)
    st = os.path.join(tmp, "s1")
    r = run(ctx, "stage", st, allowed)
    ok(r.returncode == 0, "a correctly signed release must stage")
    ok(os.path.isfile(os.path.join(st, "staging", "index.html")),
       "staging must contain the payload")

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
    ok(ota.dest_for("deploy/ota.py") is not None, "deploy/ota.py must be installable")
    ok(ota.dest_for("deploy/allowed_signers") is None,
       "an update must NOT be able to replace the key that vouches for it")
    ok(ota.dest_for("../../etc/passwd") is None, "traversal must not resolve")
    ok(ota.dest_for("deploy/flightradar-kiosk.service") is None,
       "an update must not drop systemd units")

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
