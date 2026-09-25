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
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "deploy" / "ota-auto.sh"


def run_case(name, *, update_available, paint_behaviour):
    """Run ota-auto.sh against a fake ota.py and a controllable paint stamp.

    paint_behaviour: 'advances' | 'never' | 'absent'
    Returns (exit_code, stdout, applied_bool)
    """
    td = pathlib.Path(tempfile.mkdtemp())
    try:
        stamp = td / "painted"
        applied = td / "applied.marker"

        if paint_behaviour != "absent":
            stamp.write_text("x")
            os.utime(stamp, (1000, 1000))

        # A fake ota.py: reports availability, records that apply ran, and --
        # when the display is meant to be working -- advances the stamp the way
        # a real painted frame would.
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

        # The wake endpoint. A real POST /wake powers the panel on and the page
        # starts reporting frames again; here that is a stamp touch.
        wake = td / "wake.sh"
        if paint_behaviour == "advances":
            wake.write_text(f"#!/bin/sh\ntouch {stamp}\n")
        else:
            wake.write_text("#!/bin/sh\nexit 0\n")
        wake.chmod(0o755)

        # curl stand-in, so the script's real call path is exercised.
        bindir = td / "bin"
        bindir.mkdir()
        curl = bindir / "curl"
        curl.write_text(f"#!/bin/sh\nexec {wake}\n")
        curl.chmod(0o755)

        env = dict(os.environ)
        env.update({
            "PATH": f"{bindir}:{env['PATH']}",
            "FLIGHTRADAR_OTA": str(fake),
            "FLIGHTRADAR_PAINT_STAMP": str(stamp),
            "FLIGHTRADAR_PAINT_WAIT_S": "6",
            "FLIGHTRADAR_WAKE_URL": "http://127.0.0.1/wake",
        })
        p = subprocess.run(["sh", str(SCRIPT)], env=env,
                           capture_output=True, text=True, timeout=90)
        return p.returncode, p.stdout + p.stderr, applied.exists()
    finally:
        shutil.rmtree(td, ignore_errors=True)


def main():
    failures = []
    checks = 0

    # 1. Nothing to install: must not apply, and must not wake the screen.
    #    A unit that is up to date lighting its own display every evening in
    #    someone's living room is a bug, not a cosmetic issue.
    checks += 1
    rc, out, applied = run_case("up-to-date", update_available=False,
                                paint_behaviour="advances")
    if applied:
        failures.append("applied an update when none was available")
    checks += 1
    if "waking the panel" in out:
        failures.append("woke the display when there was nothing to install")
    checks += 1
    if rc != 0:
        failures.append(f"up-to-date run exited {rc}, expected 0")

    # 2. Update available and the display comes back: must apply.
    checks += 1
    rc, out, applied = run_case("paints", update_available=True,
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
    rc, out, applied = run_case("never-paints", update_available=True,
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
    rc, out, applied = run_case("no-stamp", update_available=True,
                                paint_behaviour="absent")
    if applied:
        failures.append("applied with no paint stamp at all")
    checks += 1
    if rc != 0:
        failures.append(f"missing-stamp run exited {rc}, expected a soft skip")

    for f in failures:
        print("FAIL:", f)
    print(f"{checks - len(failures)}/{checks} ota-auto checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
