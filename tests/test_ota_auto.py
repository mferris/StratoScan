#!/usr/bin/env python3
"""ota-auto.sh decides whether an unattended update may proceed.

This runs with nobody watching, on a device in someone else's house, and it
is the only thing standing between "a release installs itself overnight" and
"a good release is rolled back and Chromium comes back windowed". The rule it
enforces: apply ONLY once the display has reported a painted frame.

The failure it exists to prevent is not hypothetical. ota.py verifies an
update by restarting the kiosk and watching the paint stamp advance. With the
panel blanked the page's rAF loop stops, no frames are reported, the stamp
never moves, and the release is rolled back for a fault that does not exist --
the same trap shm-guard.sh hit and solved by waking the panel first.

Run: python3 tests/test_ota_auto.py
"""
import http.server
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "deploy" / "ota-auto.sh"


class WakeServer:
    """A stand-in for lighttpd in front of the wake listener (2026-10-30).

    Like lighttpd, it answers 411 Length Required to a POST that carries no
    Content-Length and never passes it on -- the refusal that kept the panel
    dark on a real unit. A POST it accepts "wakes the panel": when the
    display is meant to work, the paint stamp is touched as a painted frame
    would. `answers` is the list of statuses to give accepted POSTs in turn
    (the last one repeats), so a refused first wake can be played.
    """

    def __init__(self, stamp, paints, answers=(204,)):
        self.stamp, self.paints, self.answers = stamp, paints, list(answers)
        self.requests = []   # (path, content-length or None, status)
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = self.headers.get("Content-Length")
                if length is None:
                    status = 411
                else:
                    self.rfile.read(int(length))
                    status = outer.answers.pop(0) if len(outer.answers) > 1 else outer.answers[0]
                    if 200 <= status < 300 and outer.paints:
                        outer.stamp.write_text("x")
                outer.requests.append((self.path, length, status))
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/wake?why=update"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def run_case(name, *, update_available, paint_behaviour, answers=(204,),
             wait_s=6, wake_every_s=15):
    """Run ota-auto.sh against a fake ota.py, a controllable paint stamp and a
    wake endpoint that behaves like lighttpd.

    paint_behaviour: 'advances' | 'never' | 'absent'
    Returns (exit_code, stdout, applied_bool, wake_requests)
    """
    td = pathlib.Path(tempfile.mkdtemp())
    server = None
    try:
        stamp = td / "painted"
        applied = td / "applied.marker"

        if paint_behaviour != "absent":
            stamp.write_text("x")
            os.utime(stamp, (1000, 1000))

        # A fake ota.py: reports availability, records that apply ran.
        fake = td / "ota.py"
        fake.write_text(textwrap.dedent(f"""\
            #!/usr/bin/env python3
            import os, sys, time
            cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
            if cmd == "check":
                print("2026.01.01 serial 2, installed 1 -> "
                      "{'update available' if update_available else 'up to date'}")
                sys.exit(0)
            if cmd == "apply":
                open({str(applied)!r}, "w").write("yes")
                sys.exit(0)
            sys.exit(0)
            """))
        fake.chmod(0o755)

        # The wake endpoint: the real curl talks to it, so the request the
        # script actually sends is what gets judged.
        server = WakeServer(stamp, paint_behaviour == "advances", answers)

        env = dict(os.environ)
        env.update({
            "STRATOSCAN_OTA": str(fake),
            "STRATOSCAN_PAINT_STAMP": str(stamp),
            "STRATOSCAN_PAINT_WAIT_S": str(wait_s),
            "STRATOSCAN_WAKE_EVERY_S": str(wake_every_s),
            "STRATOSCAN_WAKE_URL": server.url,
        })
        env.pop("http_proxy", None)
        env.pop("HTTP_PROXY", None)
        env.pop("ALL_PROXY", None)
        env.pop("all_proxy", None)
        p = subprocess.run(["sh", str(SCRIPT)], env=env,
                           capture_output=True, text=True, timeout=90)
        return p.returncode, p.stdout + p.stderr, applied.exists(), list(server.requests)
    finally:
        if server:
            server.close()
        shutil.rmtree(td, ignore_errors=True)


def main():
    failures = []
    checks = 0

    # 1. Nothing to install: must not apply, and must not wake the screen.
    #    A unit that is up to date lighting its own display every evening in
    #    someone's living room is a bug, not a cosmetic issue.
    checks += 1
    rc, out, applied, reqs = run_case("up-to-date", update_available=False,
                                      paint_behaviour="advances")
    if applied:
        failures.append("applied an update when none was available")
    checks += 1
    if "waking the panel" in out or reqs:
        failures.append("woke the display when there was nothing to install")
    checks += 1
    if rc != 0:
        failures.append(f"up-to-date run exited {rc}, expected 0")

    # 2. Update available and the display comes back: must apply.
    checks += 1
    rc, out, applied, _ = run_case("paints", update_available=True,
                                paint_behaviour="advances")
    if not applied:
        failures.append("did NOT apply an available update even though the "
                        "display reported a painted frame")
    checks += 1
    if rc != 0:
        failures.append(f"applying run exited {rc}, expected 0")

    # 3. Update available, panel never paints: must NOT apply. This is the
    #    whole point. Applying here rolls the release back and can leave a
    #    windowed browser on a device nobody is sitting in front of.
    checks += 1
    rc, out, applied, _ = run_case("never-paints", update_available=True,
                                paint_behaviour="never")
    if applied:
        failures.append("APPLIED with no painted frame -- this is the exact "
                        "case that rolls back good releases and leaves "
                        "Chromium windowed")
    checks += 1
    if rc != 0:
        failures.append(f"never-paints run exited {rc}; it must fail soft "
                        "and leave the release staged for next time")
    checks += 1
    if "not applying" not in out:
        failures.append("skipped silently; the journal must say why")

    # 4. No stamp at all (wake service down) is the same refusal, not a crash.
    checks += 1
    rc, out, applied, _ = run_case("no-stamp", update_available=True,
                                paint_behaviour="absent")
    if applied:
        failures.append("applied with no paint stamp at all")
    checks += 1
    if rc != 0:
        failures.append(f"missing-stamp run exited {rc}, expected a soft skip")

    # 5. The wake must reach the listener through lighttpd (2026-10-30, #81).
    #    A bare `curl -X POST` has no Content-Length; lighttpd answers 411 and
    #    the listener never hears it, so the panel stays dark and nothing ever
    #    installs. The wake must carry an (empty) body and be accepted.
    checks += 1
    rc, out, applied, reqs = run_case("wake-body", update_available=True,
                                      paint_behaviour="advances")
    if not reqs:
        failures.append("no wake request reached the endpoint at all")
    elif any(r[1] is None for r in reqs):
        failures.append("the wake POST has no Content-Length; lighttpd "
                        "refuses that with 411 and the panel stays dark")
    checks += 1
    if not applied:
        failures.append("did not apply behind a lighttpd-like endpoint")
    checks += 1
    if reqs and not all(r[0].startswith("/wake?") and "why=update" in r[0] for r in reqs):
        failures.append(f"wake did not name its reason: {[r[0] for r in reqs]}")
    checks += 1
    m = re.search(r'^WAKE_URL="\$\{STRATOSCAN_WAKE_URL:-([^}]*)\}"', SCRIPT.read_text(), re.M)
    if not m or m.group(1) != "http://127.0.0.1/wake?why=update":
        failures.append("the default wake URL is not /wake?why=update, the "
                        "reason ota.py gives")

    # 6. A wake that is refused is logged with its status, not passed over
    #    in silence (curl exits 0 on a 411 or a 503).
    checks += 1
    rc, out, applied, reqs = run_case("wake-refused", update_available=True,
                                      paint_behaviour="advances", answers=(503,))
    if "503" not in out:
        failures.append("a wake answered 503 was not logged with its status")
    checks += 1
    if applied:
        failures.append("applied although every wake was refused")
    checks += 1
    if rc != 0:
        failures.append(f"refused-wake run exited {rc}; it must fail soft")

    # 7. The wake is asked again while waiting: a refused first one (or one
    #    inside the listener's 10 s gap) must not cost the whole run.
    checks += 1
    rc, out, applied, reqs = run_case("wake-retry", update_available=True,
                                      paint_behaviour="advances",
                                      answers=(503, 204), wait_s=12,
                                      wake_every_s=3)
    if not applied:
        failures.append("did not ask for the wake again after a refusal "
                        f"(requests: {[r[2] for r in reqs]})")
    checks += 1
    if len(reqs) < 2:
        failures.append(f"only {len(reqs)} wake request(s); expected a retry")

    # The kiosk user is found, never assumed (2026-10-13): the script once
    # hard-coded the first unit's user, so a unit from the factory image
    # ("stratoscan") never found its paint stamp and never updated itself.
    src = SCRIPT.read_text()
    fn = src[src.index("kiosk_user() {"):]
    fn = fn[:fn.index("\n}\n") + 3]
    with tempfile.TemporaryDirectory() as d:
        a, b = pathlib.Path(d) / "lightdm.conf", pathlib.Path(d) / "50-kiosk.conf"
        a.write_text("[Seat:*]\n#autologin-user=nobody\nautologin-user=pi\n")
        b.write_text("[Seat:*]\nautologin-user=stratoscan\n")
        def who(extra_env, confs):
            env = {k: v for k, v in os.environ.items() if k != "STRATOSCAN_KIOSK_USER"}
            env.update(extra_env)
            env["STRATOSCAN_LIGHTDM_CONFS"] = confs
            return subprocess.run(["sh", "-c", fn + "kiosk_user"], env=env,
                                  capture_output=True, text=True).stdout.strip()
        cases = [
            ({}, f"{a} {b}", "stratoscan", "the display manager's autologin user, later files winning"),
            ({}, str(a), "pi", "a commented-out line doesn't count"),
            ({"STRATOSCAN_KIOSK_USER": "override"}, f"{a} {b}", "override", "an explicit override wins"),
        ]
        for extra, confs, want, what in cases:
            checks += 1
            got = who(extra, confs)
            if got != want:
                failures.append(f"kiosk user: {what}: got {got!r}, want {want!r}")
        checks += 1
        got = who({}, str(pathlib.Path(d) / "missing.conf"))
        if not got:
            failures.append("kiosk user with no autologin: got nothing (uid 1000, else stratoscan, expected)")
    checks += 1
    if "mferris" in src.split("kiosk_user() {")[0] + src.split("KIOSK_USER=$(kiosk_user)")[1]:
        failures.append("ota-auto.sh still names a particular user")

    for f in failures:
        print("FAIL:", f)
    print(f"{checks - len(failures)}/{checks} ota-auto checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
