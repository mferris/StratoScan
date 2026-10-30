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
                 "antenna_mount_twin_cover_text_8", "antenna_mount_twin_cover_text_11",
                 "power_trigger_mount", "power_trigger_stop", "power_regulator_tray"]
OPENSCAD = "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"

# Everything the hardware touches: the shell's internal furniture, the back,
# and the antenna mount. These must be character-for-character the same.
CORE = {
    # the back plate and everything cut into it, the coupon of its USB-C
    # window, and the charger's label engraved above it
    "back_plate", "back_lip", "usbc_cutout", "usbc_window2d", "usbc_gauge",
    "usbc_label2d", "usbc_label_solid",
    "intake_grille", "fan_grille",
    # what the Pi, fan and speakers bolt to
    "cradle_rails", "cradle_arm", "fan_mount", "speaker_bracket",
    "back_posts", "back_post_holes", "screw_ring_holes",
    # the front screw posts and their heat-set insert holes
    "front_posts", "front_post_holes",
    # the shelf's sloped underside (2026-10-29)
    "shelf_slope",
    # the outer shell: the body less the front insert holes
    "shell",
    # the display clamp, and the same keyed ring as it prints (2026-10-29)
    "retainer", "retainer_print",
    # the front stack placed on the shell, for the pictures and checks (2026-10-29)
    "front_stack_placed",
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
    # the power fix (roadmap 5.7): the trigger board with its socket through
    # the USB-C window, held by its mount, the ribs in the mount's roof and
    # the stop behind it, keyed so it goes in only one way, and the
    # regulator's tray
    "power_trigger_mount", "power_trigger_stop", "power_trigger_stop_shape", "power_regulator_tray",
    "pwr_x_teardrop", "pwr_socket2d", "pwr_board_y0", "pwr_pcb_y1", "pwr_board_z1", "pwr_tube_w",
    "pwr_tube_y0", "pwr_tube_y1", "pwr_top_rib_h", "pwr_top_ribs", "pwr_key2d", "pwr_key_slot2d",
    "pwr_stop_hw", "pwr_stop_y0", "pwr_stop_y1", "pwr_stop_z0", "pwr_stop_z1", "pwr_m2_y", "pwr_m2_z",
    "pwr_mount_len", "pwr_m2_reach", "pwr_m2_engaged",
    "power_trigger_mount_placed", "power_trigger_stop_placed", "power_trigger_board_placed",
    "power_plug_probe", "power_m2_probe", "power_m3_probe", "power_insert_probe", "power_wire_probe",
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


def evaluate(defs, name, fallback=None, _seen=None):
    """A parameter's value, worked out: numbers, + - * /, brackets and vectors,
    other parameters by name (from `defs`, then `fallback`). None for
    anything else (a function call, a string, a condition)."""
    _seen = set() if _seen is None else _seen
    src = defs.get(name, (fallback or {}).get(name))
    if src is None or name in _seen:
        return None
    _seen = _seen | {name}
    expr = normalise(src)
    if not re.fullmatch(r"[\w\s.+\-*/()\[\],]+", expr):
        return None
    env = {}
    for ref in set(re.findall(r"[A-Za-z_]\w*", expr)):
        v = evaluate(defs, ref, fallback, _seen) if ref in defs else evaluate(fallback or {}, ref, None, _seen)
        if v is None:
            return None
        env[ref] = v
    try:
        return eval(expr, {"__builtins__": {}}, env)   # only names, numbers and arithmetic reach here
    except Exception:
        return None


def same_value(a, b):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same_value(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 0.01
    return a == b


def stl_triangles(path):
    """An STL's triangles, ASCII or binary, each three (x, y, z) tuples."""
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
                    tris.append(tuple(v)); v = []
    else:
        n = struct.unpack("<I", d[80:84])[0]
        for i in range(n):
            f = struct.unpack("<12f", d[84 + 50 * i:84 + 50 * i + 48])
            tris.append((f[3:6], f[6:9], f[9:12]))
    return tris


def signed_volume(tris):
    """A closed mesh's volume, mm3: positive when its faces are wound to point
    outward, as a slicer reads them, and negative when it is inside out."""
    return sum(a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
               + a[2] * (b[0] * c[1] - b[1] * c[0]) for a, b, c in tris) / 6


def geometry(path):
    """(volume mm3, min corner, max corner) of an STL, ASCII or binary."""
    tris = stl_triangles(path)
    lo, hi = [1e9] * 3, [-1e9] * 3
    for t in tris:
        for pt in t:
            for k in range(3):
                lo[k], hi[k] = min(lo[k], pt[k]), max(hi[k], pt[k])
    return abs(signed_volume(tris)), lo, hi


def same_shape(g1, g2):
    return (abs(g1[0] - g2[0]) <= max(0.5, g1[0] * 1e-5)
            and all(abs(x - y) <= 0.02 for x, y in zip(g1[1] + g1[2], g2[1] + g2[2])))


def in_git(root):
    """The files git tracks (or has staged) under `root`, as paths; None when
    `root` is not in a git checkout, or there is no git."""
    import subprocess
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return {root / p for p in r.stdout.decode().split("\0") if p}


def export(scad, var, part, out):
    import subprocess
    subprocess.run([OPENSCAD, "--backend=manifold", "--export-format", "binstl",
                    "-D", f'{var}="{part}"', "-o", str(out), str(scad)],
                   capture_output=True, timeout=600)
    return out.exists() and out.stat().st_size > 84


def folders_and_prints():
    """Checks 5-8: every case folder registered; variants include, never copy;
    shared print files the same shape everywhere; print files in git and not
    stale."""
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
        # ...and sets none of its base's parameters, apart from `part`, set to
        # "none" to silence the base's own part switch (2026-10-29). OpenSCAD
        # gives a parameter set twice its last value everywhere, inside the
        # base's modules too, so the variant's shared parts would change, and
        # check 8 would only compare them with themselves. The Dials set its
        # own z_trim_face, 4.9 mm in front of the trim.
        checks += 1
        reset = sorted((set(params(f)) & set(params(base))) - {"part"}) if f.exists() else []
        if reset:
            failures.append(f"{name}/{scad} sets {', '.join(reset)}, which {base.name} sets; "
                            f"use the base's value, or change it there")
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

    # 8. print files are in git, and match their design today (that part needs
    #    OpenSCAD, and is skipped without it). In git (2026-10-29): the Retro
    #    with Dials' six STLs and the kitten stand's 3MF sat ignored by
    #    enclosure/.gitignore. Here on disk they passed every check, but no
    #    clone had them, so this test failed in every fresh worktree, and
    #    `git clean -X` would have deleted the only copies.
    jobs = [(RETRO, "part", part, ROOT / fname / f"{part}.stl")
            for part in SHARED_PRINTS for fname in FULL]
    for name, (scad, base, prints) in VARIANTS.items():
        jobs += [(ROOT / name / scad, "dpart", part, ROOT / name / fn) for fn, part in prints.items()]
    tracked = in_git(ROOT)
    if tracked is None:
        print("note: not a git checkout: print files not checked for being in git")
    else:
        for committed in sorted({job[3] for job in jobs}):
            checks += 1
            if committed not in tracked:
                failures.append(f"{committed.relative_to(ROOT)} is not in git: `git add` it, and check "
                                f"that its folder's .gitignore lets it in")
    if os.path.exists(OPENSCAD) and os.environ.get("ENCLOSURE_QUICK") != "1":
        with tempfile.TemporaryDirectory() as t:
            t = pathlib.Path(t)
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


def threemf_meshes(path):
    """name -> triangles, for each object in a 3MF with a mesh of its own (an
    object made only of other objects has none). Named by its model file as
    well as its id: a 3MF can keep its objects in several model files, each
    numbering its own, and two named by id alone would be one, the other
    never checked."""
    import xml.etree.ElementTree as ET
    import zipfile
    out = {}
    with zipfile.ZipFile(path) as z:
        for model in (n for n in z.namelist() if n.endswith(".model")):
            for obj in ET.fromstring(z.read(model)).iter():
                if obj.tag.split("}")[-1] != "object":
                    continue
                verts, tris = [], []
                for el in obj.iter():
                    tag = el.tag.split("}")[-1]
                    if tag == "vertex":
                        verts.append(tuple(float(el.get(k)) for k in "xyz"))
                    elif tag == "triangle":
                        tris.append(tuple(verts[int(el.get(k))] for k in ("v1", "v2", "v3")))
                if tris:
                    out[f"object {obj.get('id')} in {model}"] = tris
    return out


def print_meshes(path):
    """label -> triangles, for each mesh in a print file: an STL is one, a
    3MF one per object."""
    path = pathlib.Path(path)
    if path.suffix == ".3mf":
        return {f"{path.name}, {k}": v for k, v in threemf_meshes(path).items()}
    return {path.name: stl_triangles(path)}


def edge_faults(tris):
    """(bad edges, degenerate triangles) of a mesh, its vertices welded by
    position, as a slicer welds them. An edge is good when exactly two
    triangles use it, one each way round; a bad edge is given as its two ends
    and the number of triangles on it. A degenerate triangle, two of its
    corners at one point, is not counted in the edges: slicers drop it."""
    import collections
    ids, directed, degenerate = {}, collections.Counter(), 0
    for t in tris:
        a, b, c = (ids.setdefault(p, len(ids)) for p in t)
        if a == b or b == c or a == c:
            degenerate += 1
            continue
        for u, v in ((a, b), (b, c), (c, a)):
            directed[(u, v)] += 1
    at = {i: p for p, i in ids.items()}
    bad, seen = [], set()
    for u, v in directed:
        if (v, u) in seen:
            continue
        seen.add((u, v))
        if directed[(u, v)] != 1 or directed[(v, u)] != 1:
            bad.append((at[u], at[v], directed[(u, v)] + directed[(v, u)]))
    return bad, degenerate


def cube_triangles(x0, y0, z0, s=1.0):
    """A cube's twelve triangles, wound outward: a closed mesh, for the controls."""
    p = [(x0 + s * (i & 1), y0 + s * (i >> 1 & 1), z0 + s * (i >> 2 & 1)) for i in range(8)]
    tris = []
    for a, b, c, d in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)):
        tris += [(p[a], p[b], p[c]), (p[a], p[c], p[d])]
    return tris


def write_control(path, *meshes):
    """Write control meshes as one binary STL, or as a 3MF: one mesh as object
    1 of its 3dmodel.model, or several, each object 1 of a model file of its
    own, put together by an object in the 3dmodel.model."""
    import struct
    import zipfile
    path = pathlib.Path(path)
    if path.suffix == ".stl":
        tris = [t for m in meshes for t in m]
        d = bytearray(80) + struct.pack("<I", len(tris))
        for t in tris:
            d += struct.pack("<12fH", 0, 0, 0, *t[0], *t[1], *t[2], 0)
        path.write_bytes(bytes(d))
        return

    def model(resources, build):
        return ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" '
                'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
                'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
                f'requiredextensions="p"><resources>{resources}</resources><build>{build}</build></model>')

    def mesh_object(tris):
        ids = {}
        tri_ids = [[ids.setdefault(p, len(ids)) for p in t] for t in tris]
        verts = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in ids)
        faces = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tri_ids)
        return (f'<object id="1" type="model"><mesh><vertices>{verts}</vertices>'
                f'<triangles>{faces}</triangles></mesh></object>')

    with zipfile.ZipFile(path, "w") as z:
        if len(meshes) == 1:
            z.writestr("3D/3dmodel.model", model(mesh_object(meshes[0]), '<item objectid="1"/>'))
            return
        parts = [f"3D/Objects/object_{i + 1}.model" for i in range(len(meshes))]
        for part, tris in zip(parts, meshes):
            z.writestr(part, model(mesh_object(tris), ""))
        top = len(meshes) + 1
        comps = "".join(f'<component p:path="/{part}" objectid="1"/>' for part in parts)
        z.writestr("3D/3dmodel.model", model(f'<object id="{top}" type="model"><components>{comps}'
                                             f'</components></object>', f'<item objectid="{top}"/>'))


def print_files_manifold():
    """Check 10: every print file is a closed mesh with no edge a slicer has to
    repair, and not inside out."""
    import tempfile
    failures, checks = [], 0

    # 10. Every print file (an STL, and every object in a 3MF) in every case
    #     folder is edge-manifold: once its vertices are welded by position,
    #     as a slicer welds them, every edge is used by exactly two
    #     triangles, one each way round (2026-10-29). Bambu Studio opened
    #     shell_dials.stl with "3 non-manifold edges" and "reversed faces
    #     detected". Where two solids of a part only touch, along a line or
    #     a face, instead of overlapping, OpenSCAD's mesh keeps the two
    #     surfaces there as separate sheets with no gap between them, and
    #     welded, four triangles share an edge, two of them the same way
    #     round. Every one of those files passed OpenSCAD's own "manifold"
    #     line, and only a slicer opening the file says otherwise, so
    #     nothing here saw it.
    #
    #     Its volume must also come out above 0 (2026-10-29). A mesh turned
    #     inside out, every face wound the wrong way round, has every edge
    #     used once each way, so it passes the edge check, and a slicer has
    #     to flip it. This is the whole mesh's volume, not each piece's: a
    #     hollow inside a part is a piece whose faces point inward, and is
    #     right. So one piece turned inside out, beside others the right way
    #     out, is not caught here.
    #
    #     A 3MF's meshes are named by model file as well as id (2026-10-29):
    #     a 3MF can keep its objects in several model files, each numbering
    #     its own, and by id alone a second object 1 hid the first from this
    #     check.
    #
    #     The controls go through the same reader and checks, each as an STL
    #     and as a 3MF. They must fail: two cubes that share one edge; a cube
    #     with one face turned over; a cube turned inside out; and two
    #     meshes, the first of them two cubes sharing an edge, which the 3MF
    #     keeps in two model files, both as object 1. They must pass: a plain
    #     cube, and a cube with a hollow in it.
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t)
        clean = cube_triangles(0, 0, 0)
        pinch = clean + cube_triangles(1, 1, 0)
        inside_out = [tri[::-1] for tri in clean]
        hollow = cube_triangles(0, 0, 0, 3) + [tri[::-1] for tri in cube_triangles(1, 1, 1)]
        controls = [("two cubes sharing an edge", [pinch], False),
                    ("a cube with a face turned over", [[clean[0][::-1]] + clean[1:]], False),
                    ("a cube turned inside out", [inside_out], False),
                    ("two meshes, a pinch in the first", [pinch, cube_triangles(5, 0, 0)], False),
                    ("a plain cube", [clean], True),
                    ("a cube with a hollow in it", [hollow], True)]
        for name, parts, good in controls:
            for ext in (".stl", ".3mf"):
                checks += 1
                f = t / f"control{ext}"
                write_control(f, *parts)
                meshes = print_meshes(f)
                ok = bool(meshes) and all(not edge_faults(m)[0] and signed_volume(m) > 0
                                          for m in meshes.values())
                if ok != good:
                    failures.append(f"the manifold check's control, {name} as {ext}, came out "
                                    f"{'clean' if ok else 'bad'}: the check itself is broken")

    tracked = in_git(ROOT)
    folders = set(FULL) | set(VARIANTS)
    if tracked is None:
        print("note: not a git checkout: every print file on disk checked for edges, not only tracked ones")
        files = [p for d in folders for p in (ROOT / d).rglob("*") if p.suffix in (".stl", ".3mf")]
    else:
        files = [p for p in tracked if p.suffix in (".stl", ".3mf") and p.relative_to(ROOT).parts[0] in folders]
    for f in sorted(files):
        rel = f.relative_to(ROOT)
        meshes = print_meshes(f) if f.exists() else {}
        if not meshes:
            checks += 1
            failures.append(f"{rel}: no mesh could be read from it")
            continue
        for label, tris in meshes.items():
            checks += 1
            bad, degenerate = edge_faults(tris)
            where = f"{rel.parent}/{label}"
            if bad:
                (p, q, n) = bad[0]
                failures.append(f"{where}: {len(bad)} edges a slicer reports as non-manifold or reversed, "
                                f"not used by two triangles one each way round, e.g. "
                                f"({p[0]:.3f}, {p[1]:.3f}, {p[2]:.3f}) to ({q[0]:.3f}, {q[1]:.3f}, {q[2]:.3f}), "
                                f"used {n} times. Two solids there meet in a line or a face: make them overlap "
                                f"a little, or stand clear, and re-export it")
            checks += 1
            vol = signed_volume(tris)
            if vol <= 0:
                failures.append(f"{where}: inside out: its faces point inward, so its volume comes out "
                                f"{vol:.3f} mm3, and a slicer has to turn it the right way out. Fix the "
                                f"winding in whatever wrote it, and re-export it")
            if degenerate:
                print(f"note: {where}: {degenerate} degenerate triangles (zero area; slicers drop them)")
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

    # 9. A checks.scad that `use`s its design can't see the design's values,
    #    so it restates the ones it probes with -- and a restated value that
    #    has gone stale checks the wrong place. The kitten's copy kept the
    #    USB-C window at its old spot for three days after it moved, and its
    #    usbc_open probe failed for a fault that wasn't there (2026-10-13).
    #    Every value a check file restates must equal its design's.
    for design in FULL.values():
        chk = design.parent / "checks.scad"
        if not chk.exists():
            continue
        dp, cp = params(design), params(chk)
        for name in sorted(set(cp) & set(dp)):
            want, got = evaluate(dp, name), evaluate(cp, name, fallback=dp)
            if want is None or got is None:
                continue          # not plain arithmetic: nothing to compare numerically
            checks += 1
            if not same_value(want, got):
                failures.append(f"{design.parent.name}/checks.scad restates {name}={cp[name]!r} ({got}), "
                                f"but the design has {dp[name]!r} ({want}): update the copy")

    more, n = folders_and_prints()
    failures += more
    checks += n

    more, n = print_files_manifold()
    failures += more
    checks += n

    for f in failures:
        print("FAIL:", f)
    print(f"{checks - len(failures)}/{checks} enclosure core checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
