#!/usr/bin/env python3
"""The two enclosures must be one case design wearing two costumes.

There are two .scad files -- a retro radar and a kitten -- and only their
exteriors are supposed to differ. Everything a Pi, a display, two speakers, a
fan and an antenna actually bolt to has to stay one part, or a spare back
plate printed for one unit will not fit the other and every future fix has to
be made twice (and, in practice, will be made once).

Drift here is silent. Nothing about the two files being wrong looks wrong:
both still render, both still pass their own checks.scad suite, and the
divergence only shows up when a part is in your hand. That happened -- the
kitten's exhaust slots were upgraded to 12mm rounded stadium slots and the
retro was left on the old flat rectangles, for long enough that the retro
still defined exhaust_slot_h = 12 without ever using it.

Run: python3 tests/test_enclosure_core.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / "enclosure"
RETRO = ROOT / "Retro Radar Enclosure" / "flightwall-enclosure.scad"
KITTEN = ROOT / "Kitten Enclosure Two-Tone" / "kitten-enclosure-twotone.scad"

# Everything the hardware touches: the shell's internal furniture, the back,
# and the antenna mount. These must be character-for-character the same.
CORE = {
    # the back plate and everything cut into it
    "back_plate", "back_lip", "usbc_cutout", "usbc_gauge",
    "intake_grille", "fan_grille",
    # what the Pi, fan and speakers bolt to
    "cradle_rails", "cradle_arm", "fan_mount", "speaker_bracket",
    "back_posts", "back_post_holes", "screw_ring_holes",
    # the display clamp
    "retainer",
    # cooling
    "exhaust_slots",
    # the antenna mount, all of it
    "antenna_mount", "antenna_socket_gauge", "ant_axis_frame",
    "ant_barrel_base", "ant_bolt_holes", "ant_cable_bore",
    "ant_insert_bores", "ant_insert_bosses",
}

# The only shared names allowed to differ, and why. Anything NOT listed here
# that differs is a failure -- including a module added later. A new shared
# module that quietly diverges is exactly the thing this test exists to catch.
COSMETIC = {
    "shell":      "same cylinder, posts, rails, fan and vents; rivets/ribs vs ears",
    "front_trim": "same screw ring; the kitten adds a nose and whisker grooves, "
                  "and omits the one screw the nose sits on",
    "stand":      "wholly different: a plinth with paws and a tail vs a plain base",
}


def modules(path):
    """name -> normalised body, for every module and function in a .scad file."""
    src = path.read_text()
    out = {}
    for m in re.finditer(r'^(module|function)\s+([A-Za-z_]\w*)\s*\(', src, re.M):
        kind, name = m.group(1), m.group(2)
        i = src.index('(', m.start())
        depth = 0
        for j in range(i, len(src)):
            if src[j] == '(':
                depth += 1
            elif src[j] == ')':
                depth -= 1
                if depth == 0:
                    break
        rest = src[j + 1:]
        if kind == "function":
            end = rest.index(';') if ';' in rest else len(rest)
            body = rest[:end + 1]
        else:
            k = 0
            while k < len(rest) and rest[k] in ' \t\r\n=':
                k += 1
            if k < len(rest) and rest[k] == '{':
                depth = 0
                for j2 in range(k, len(rest)):
                    if rest[j2] == '{':
                        depth += 1
                    elif rest[j2] == '}':
                        depth -= 1
                        if depth == 0:
                            break
                body = rest[k:j2 + 1]
            else:
                end = rest.index(';') if ';' in rest else len(rest)
                body = rest[:end + 1]
        out[name] = normalise(src[m.start():j + 1] + body)
    return out


def normalise(s):
    """Comments and layout may differ; geometry may not."""
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    s = re.sub(r'//[^\n]*', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def params(path):
    """Top-level `name = value;` assignments, outside any module."""
    src = re.sub(r'/\*.*?\*/', '', path.read_text(), flags=re.S)
    out, depth = {}, 0
    for line in src.split('\n'):
        code = re.sub(r'//.*', '', line)
        if depth == 0:
            for stmt in code.split(';'):
                m = re.match(r'^\s*([A-Za-z_]\w*)\s*=\s*(.+)$', stmt)
                if m and not stmt.lstrip().startswith(("module", "function")):
                    out[m.group(1)] = re.sub(r'\s+', ' ', m.group(2)).strip()
        depth += code.count('{') - code.count('}') + code.count('(') - code.count(')')
        depth = max(depth, 0)
    return out


def main():
    failures, checks = [], 0

    for f in (RETRO, KITTEN):
        if not f.exists():
            print(f"FAIL: missing {f}")
            return 1

    ra, ka = modules(RETRO), modules(KITTEN)
    rp, kp = params(RETRO), params(KITTEN)

    # 1. Shared parameters must agree. Identical module text means nothing if
    #    the numbers it reads differ.
    for name in sorted(set(rp) & set(kp)):
        checks += 1
        if rp[name] != kp[name]:
            failures.append(f"parameter {name}: retro={rp[name]!r} kitten={kp[name]!r}")

    # 2. Every core module must exist in both, and be identical.
    for name in sorted(CORE):
        checks += 1
        if name not in ra or name not in ka:
            where = "retro" if name not in ra else "kitten"
            failures.append(f"core module {name} is missing from the {where} design")
        elif ra[name] != ka[name]:
            failures.append(f"core module {name} differs between the two designs")

    # 3. No shared module may differ unless it is a declared cosmetic.
    for name in sorted(set(ra) & set(ka)):
        if name in CORE:
            continue
        checks += 1
        if ra[name] != ka[name] and name not in COSMETIC:
            failures.append(
                f"shared module {name} differs and is not declared cosmetic -- "
                f"either make it identical or add it to COSMETIC with a reason")

    # 4. A cosmetic exemption that no longer differs is stale: drop it, so the
    #    list stays an accurate account of what actually diverges.
    for name in sorted(COSMETIC):
        checks += 1
        if name in ra and name in ka and ra[name] == ka[name]:
            failures.append(f"{name} is listed as cosmetic but is now identical; "
                            f"remove it from COSMETIC")

    for f in failures:
        print("FAIL:", f)
    print(f"{checks - len(failures)}/{checks} enclosure core checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
