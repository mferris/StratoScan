#!/usr/bin/env python3
"""The fan's steps in the closed case (2026-09-30, 2026-11-15).

A Raspberry Pi 5 steps its fan up at 50, 60, 67.5 and 75 C, and back down
5 C below each. In the retro case the kiosk sat right on the 67.5 C step, so
the fan kept shifting speed, and the change in pitch is what an owner hears.
The installer moves the third step to 70 C and the top one to 77 C, which
still leaves full speed 3 C before the Pi's 80 C soft limit. The second step
stays at 60 C: a trial at 65 C made the fan change speed more often, not less.

This runs the installer's config.txt step on a stand-in file, and reads the
rest.

Run: python3 tests/test_fan_steps.py
"""
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
inst = (ROOT / "deploy" / "install-setup-server.sh").read_text()
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


helpers = [l for l in inst.splitlines() if l.startswith("has_fan_step() {")]
check(len(helpers) == 1, "the installer reads config.txt's fan steps in one place")
m = re.search(r"^if \[ -f \"\$CFG\" \] && ! has_fan_step fan_temp2; then\n.*?\n^fi\n", inst, re.S | re.M)
check(m is not None, "the installer has a step for fan_temp2 and fan_temp3")
upper = "\n".join(helpers) + "\n" + (m.group(0) if m else "false\n")
check("fan_temp1" not in inst, "the installer leaves the second step at the Pi's own 60 C")


def run(cfg, times=1):
    for _ in range(times):
        subprocess.run(["sh", "-c", f'CFG="{cfg}"\n' + upper], check=True, capture_output=True, timeout=20)
    return cfg.read_text().splitlines()


def value(lines, param):
    got = [l.split("=")[2] for l in lines if l.startswith(f"dtparam={param}=")]
    return got[0] if len(got) == 1 else got


with tempfile.TemporaryDirectory() as t:
    cfg = pathlib.Path(t) / "config.txt"
    # A new unit: Raspberry Pi OS's own file, ending inside a [pi5] section.
    cfg.write_text("dtparam=audio=on\n[pi5]\ndtoverlay=nospi10\n")
    lines = run(cfg, times=2)
    check((value(lines, "fan_temp2"), value(lines, "fan_temp3")) == ("70000", "77000"),
          "a new unit gets 70 and 77 C, each once, however often the installer runs")
    sections = {p: next((l for l in reversed(lines[:lines.index(f"dtparam={p}={v}")]) if l.startswith("[")), None)
                for p, v in (("fan_temp2", "70000"), ("fan_temp3", "77000"))}
    check(set(sections.values()) == {"[all]"}, "both steps are under [all], whatever section the file ended in")
    check(lines[:3] == ["dtparam=audio=on", "[pi5]", "dtoverlay=nospi10"], "and the rest of the file is left alone")

    # A unit set up earlier: it has the steps already.
    before = "dtparam=audio=on\n\n# StratoScan: steadier fan steps in the case (default 67.5C / 75C)\ndtparam=fan_temp2=70000\ndtparam=fan_temp3=77000\n"
    cfg.write_text(before)
    run(cfg)
    check(cfg.read_text() == before, "a unit that already has the steps keeps what it had")

    # An owner's own setting.
    own = "[all]\ndtparam=fan_temp1=58000\ndtparam=fan_temp2=66000\n"
    cfg.write_text(own)
    run(cfg)
    check(cfg.read_text() == own, "a file with its owner's own steps is left as it is")

    # Steps written several to a line, which config.txt allows.
    combined = "[all]\ndtparam=fan_temp0=45000,fan_temp1=58000\n  dtparam=fan_temp2=72000,fan_temp3=78000\n"
    cfg.write_text(combined)
    run(cfg)
    check(cfg.read_text() == combined, "and so is one whose steps share a line, or are indented")

# On a running unit the steps apply at once, and only from their defaults.
check(re.search(r'if \[ "\$\(cat \$TZ0/trip_point_3_temp 2>/dev/null\)" = "67500" \]; then\n\s+echo 70000 > \$TZ0/trip_point_3_temp', inst) is not None,
      "a running unit's third and top steps move now only from the defaults")
temps = {p: int(v) for p, v in re.findall(r"dtparam=(fan_temp[23])=(\d+)", inst)}
check(60000 + 5000 <= temps["fan_temp2"] < temps["fan_temp3"] <= 77000,
      "the steps stay in order, 5 C or more above the second, with full speed by 77 C, before the Pi's 80 C limit")

print("fan step checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
