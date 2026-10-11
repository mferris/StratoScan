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
RETRO = ROOT / "Retro Radar Enclosure" / "retro-enclosure.scad"
KITTEN = ROOT / "Kitten Enclosure Two-Tone" / "kitten-enclosure-twotone.scad"

# Every folder under enclosure/ is one of these. A new case folder fails this
# test until it is added to one or the other -- so a third (or fourth) case
# cannot quietly grow its own copy of the back, the mounts or the shell.
FULL = {"Retro Radar Enclosure": RETRO, "Kitten Enclosure Two-Tone": KITTEN}
# Built by INCLUDING a full design and adding to it: (its .scad, the design it
# includes, its print files and the part that makes each).
VARIANTS = {
    "Retro Radar with Dials": ("retro-dials.scad", RETRO, {
        "shell_dials.stl": "shell_dials", "control_arc.stl": "pod_print",
        "control_arc_text.stl": "pod_text_print", "control_arc_cover.stl": "pod_cover_print",
        "knob.stl": "knob", "jewel_lens.stl": "jewel_print"}),
}
# Print files for the parts every case shares. Each full design's folder ships
# them, and they must be the same shape in every folder (compared by volume
# and extent: two exports of one model differ in triangulation, not shape).
SHARED_PRINTS = ["back_plate", "retainer", "usbc_gauge", "antenna_socket_gauge",
                 "antenna_mount", "antenna_mount_sma", "antenna_mount_twin_8", "antenna_mount_twin_11",
                 "antenna_mount_twin_cover_8", "antenna_mount_twin_cover_11",
                 "antenna_mount_twin_cover_text_8", "antenna_mount_twin_cover_text_11"]
OPENSCAD = "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"

# Everything the hardware touches: the shell's internal furniture, the back,
# and the antenna mount. These must be character-for-character the same.
CORE = {
    # the back plate and everything cut into it
    "back_plate", "back_lip", "usbc_cutout", "usbc_gauge",
    "intake_grille", "fan_grille",
    # what the Pi, fan and speakers bolt to
    "cradle_rails", "cradle_arm", "fan_mount", "speaker_bracket",
    "back_posts", "back_post_holes", "screw_ring_holes",
    # the front screw posts and their heat-set insert holes
    "front_posts", "front_post_holes",
    # the outer shell: the body less the front insert holes
    "shell",
    # the display clamp
    "retainer",
    # Cooling is NOT shared: the retro case vents through nine side slots
    # across the top; the kitten has none and vents through its hollow ears.
    # the antenna mount, all of it -- both variants. They share the flange,
    # the arm, the bolt circle and the counter-tilt, and differ only at the
    # far end: a socket cut for one antenna's base, or an SMA bulkhead that
    # takes any of them.
    "antenna_mount", "antenna_mount_sma", "antenna_socket_gauge",
    "ant_axis_frame", "ant_barrel_base", "ant_bolt_holes", "ant_cable_bore",
    "ant_insert_bores", "ant_insert_bosses",
    # the twin mount (1090 + 978 MHz) and its check helpers
    "antenna_mount_twin", "antenna_mount_twin_cover", "ant_twin_frame", "ant_twin_teardrop", "ant_twin_outline2d", "ant_twin_slab", "ant_twin_cover2d", "ant_twin_bore", "ant_twin_cover_placed", "ant_twin_bore_probe", "ant_twin_jack_probe", "ant_twin_barrel_probe", "ant_twin_channel_probe", "ant_twin_screw_probes",
    "ant_twin_envelopes", "ant_twin_panel_ring", "ant_twin_hole_probe",
}

# The only shared names allowed to differ, and why. Anything NOT listed here
# that differs is a failure -- including a module added later. A new shared
# module that quietly diverges is exactly the thing this test exists to catch.
COSMETIC = {
    "shell_body": "same cylinder, posts, rails and fan; rivets, ribs and side slots vs ears",
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


def geometry(path):
    """(volume mm3, min corner, max corner) of an STL, ASCII or binary."""
    import struct
    d = pathlib.Path(path).read_bytes()
    tris = []
    if d[:5] == b"solid" and b"facet" in d[:400]:
        v = []
        for line in d.decode(errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("vertex"):
                v.append(tuple(float(x) for x in line.split()[1:4]))
                if len(v) == 3:
                    tris.append(v); v = []
    else:
        n = struct.unpack("<I", d[80:84])[0]
        for i in range(n):
            f = struct.unpack("<12f", d[84 + 50 * i:84 + 50 * i + 48])
            tris.append((f[3:6], f[6:9], f[9:12]))
    vol, lo, hi = 0.0, [1e9] * 3, [-1e9] * 3
    for a, b, c in tris:
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
        for pt in (a, b, c):
            for k in range(3):
                lo[k], hi[k] = min(lo[k], pt[k]), max(hi[k], pt[k])
    return abs(vol), lo, hi


def same_shape(g1, g2):
    return (abs(g1[0] - g2[0]) <= max(0.5, g1[0] * 1e-5)
            and all(abs(x - y) <= 0.02 for x, y in zip(g1[1] + g1[2], g2[1] + g2[2])))


def export(scad, var, part, out):
    import subprocess
    subprocess.run([OPENSCAD, "--backend=manifold", "--export-format", "binstl",
                    "-D", f'{var}="{part}"', "-o", str(out), str(scad)],
                   capture_output=True, timeout=600)
    return out.exists() and out.stat().st_size > 84


def folders_and_prints():
    """Checks 5-8: every case folder registered; variants include, never copy;
    shared print files the same shape everywhere; print files not stale."""
    import os
    import tempfile
    failures, checks = [], 0

    # 5. every folder is registered
    for d in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        checks += 1
        if d.name not in FULL and d.name not in VARIANTS:
            failures.append(f"enclosure/{d.name} is a new case: register it in FULL (a design of its own, "
                            f"compared module by module) or VARIANTS (one that includes another)")

    # 6. a variant includes its base and redefines none of the shared parts
    for name, (scad, base, prints) in VARIANTS.items():
        f = ROOT / name / scad
        checks += 1
        src = f.read_text() if f.exists() else ""
        inc = f"include <../{base.parent.name}/{base.name}>"
        if inc not in src:
            failures.append(f"{name}/{scad} must `{inc}` -- a copy of the base design would drift")
        mine = set(modules(f)) if f.exists() else set()
        checks += 1
        clash = sorted(mine & (CORE | set(COSMETIC) | set(modules(base))))
        if clash:
            failures.append(f"{name}/{scad} redefines {', '.join(clash)} from {base.name}; "
                            f"change the base design instead, so every case gets it")
        checks += 1
        copies = sorted(p.name for p in (ROOT / name).glob("*.stl") if p.stem in SHARED_PRINTS)
        if copies:
            failures.append(f"{name} ships its own {', '.join(copies)}; the base design's folder holds those")

    # 7. shared print files: present in every full design's folder, same shape
    for part in SHARED_PRINTS:
        shapes = {}
        for fname in FULL:
            checks += 1
            p = ROOT / fname / f"{part}.stl"
            if not p.exists():
                failures.append(f"{fname} is missing {part}.stl")
                continue
            shapes[fname] = geometry(p)
        if len(shapes) > 1:
            checks += 1
            first = next(iter(shapes.values()))
            if not all(same_shape(first, g) for g in shapes.values()):
                failures.append(f"{part}.stl is not the same shape in every case folder: "
                                f"re-export it from each design (and check the designs agree)")

    # 8. print files match their design today (needs OpenSCAD; skipped without it)
    if os.path.exists(OPENSCAD) and os.environ.get("ENCLOSURE_QUICK") != "1":
        with tempfile.TemporaryDirectory() as t:
            t = pathlib.Path(t)
            jobs = [(RETRO, "part", part, ROOT / fname / f"{part}.stl")
                    for part in SHARED_PRINTS for fname in FULL]
            for name, (scad, base, prints) in VARIANTS.items():
                jobs += [(ROOT / name / scad, "dpart", part, ROOT / name / fn) for fn, part in prints.items()]
            made = {}
            for scad, var, part, committed in jobs:
                checks += 1
                key = (str(scad), part)
                if key not in made:
                    out = t / f"{len(made)}.stl"
                    made[key] = geometry(out) if export(scad, var, part, out) else None
                if made[key] is None:
                    failures.append(f"could not export {part} from {scad.name}")
                elif not committed.exists():
                    failures.append(f"{committed.relative_to(ROOT)} is missing")
                elif not same_shape(made[key], geometry(committed)):
                    failures.append(f"{committed.relative_to(ROOT)} is stale: the design has changed since it "
                                    f"was exported. Re-export it (and the same part in every other case folder)")
    else:
        print("note: OpenSCAD not found (or ENCLOSURE_QUICK=1): print files not compared with their designs")
    return failures, checks


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

    more, n = folders_and_prints()
    failures += more
    checks += n

    for f in failures:
        print("FAIL:", f)
    print(f"{checks - len(failures)}/{checks} enclosure core checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
