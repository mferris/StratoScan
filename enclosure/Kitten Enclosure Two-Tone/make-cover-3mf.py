#!/usr/bin/env python3
"""Builds the two-colour 3MF projects: each twin antenna mount cover, and
the back plate (since 2026-10-31), with the part on filament 1 and its
engraved lettering on filament 2, as one object.

Why a project file rather than two STLs: the lettering is many separate
letters, and a slicer splits a multi-lump mesh into one part per lump on
import, so choosing a colour for "the text" would colour one letter. The
assignment belongs in the file (the kitten stand's make-3mf.py, same reason).

The cover and the plate both print outer face down, so the lettering is
their first 0.6 mm (three 0.2 mm layers): one filament change per layer,
nothing after that. Each lettering STL is exported in its part's own frame,
so the two meshes meet face to face as they come.

The meshes keep that frame, so the test can compare them with their STLs
(check 12 in tests/test_enclosure_core.py), and the build item carries a
transform that stands the object on the bed and centres it at BED_CENTRE
(2026-10-31). Without one the plate sat centred on (0, 0), half off the
bed, and 3 mm below it, and Bambu Studio's command line refused to slice it
unless told to arrange it; the GUI moves it either way.

Each object also carries the Bambu Studio settings that face-down lettering
needs (OBJECT_SETTINGS, 2026-10-31), as per-object settings, which the
project opens with. Slicing with Bambu Studio 2.08's command line showed it
honours these three per object, and that the rest of the README's two-colour
settings (first-layer line width and speed, prime tower, plate, Z-hop) are
the print's, the printer's or the filament's, which a project cannot set per
object. With its default classic walls, the cover's old lettering laid down
67 of its 118 mm2 on the first layer; with Arachne, all of it.

Usage: python3 make-cover-3mf.py [project.3mf ...]   (after exporting the
STLs as BINARY: openscad --export-format binstl). With no names it builds
them all; name one to build only that one, since a rebuilt file differs in
its zip timestamps even when nothing in it has changed.
"""
import struct, sys, zipfile
from xml.sax.saxutils import escape

# Where the build item puts the object's middle, mm: the middle of a
# 256 mm Bambu bed. Any slicer can move it from there.
BED_CENTRE = (128.0, 128.0)

# Bambu Studio settings each object carries, as its own per-object settings:
# Arachne walls, which vary a line's width to fill a stroke where classic
# walls leave a narrow one out; no elephant-foot compensation, which pulls
# every first-layer outline in by 0.15 mm and so thins each stroke by
# 0.3 mm; and a bottom surface of straight monotonic lines, the face's look.
OBJECT_SETTINGS = {
    "wall_generator": "arachne",
    "elefant_foot_compensation": "0",
    "bottom_surface_pattern": "monotonicline",
}

# project -> (what it is, [(STL, filament), ...])
PROJECTS = {
    "antenna_mount_twin_cover_8_twotone.3mf":  ("twin antenna mount cover",
        [("antenna_mount_twin_cover_8", 1), ("antenna_mount_twin_cover_text_8", 2)]),
    "antenna_mount_twin_cover_11_twotone.3mf": ("twin antenna mount cover",
        [("antenna_mount_twin_cover_11", 1), ("antenna_mount_twin_cover_text_11", 2)]),
    "back_plate_twotone.3mf":                  ("back plate",
        [("back_plate", 1), ("back_plate_text", 2)]),
    # the lettering test coupons (2026-10-31): a few minutes each
    "test_lettering_plate.3mf":                ("back plate lettering coupon",
        [("test_lettering_plate", 1), ("test_lettering_plate_text", 2)]),
    "test_lettering_cover.3mf":                ("twin antenna cover lettering coupon",
        [("test_lettering_cover", 1), ("test_lettering_cover_text", 2)]),
}


def read_stl(path):
    with open(path, "rb") as f:
        f.seek(80)
        (n,) = struct.unpack("<I", f.read(4))
        idx, verts, tris = {}, [], []
        for _ in range(n):
            v = struct.unpack("<12f", f.read(50)[:48])
            tri = []
            for i in (3, 6, 9):
                key = (round(v[i], 5), round(v[i + 1], 5), round(v[i + 2], 5))
                j = idx.get(key)
                if j is None:
                    j = idx[key] = len(verts)
                    verts.append(key)
                tri.append(j)
            if len(set(tri)) == 3:
                tris.append(tri)
    return verts, tris


def build(out, what, parts, settings=OBJECT_SETTINGS):
    objects, ids, every = [], [], []
    for oid, (name, extruder) in enumerate(parts, start=1):
        verts, tris = read_stl(name + ".stl")
        every += verts
        v = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in verts)
        t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris)
        objects.append(f'<object id="{oid}" type="model"><mesh><vertices>{v}</vertices>'
                       f'<triangles>{t}</triangles></mesh></object>')
        ids.append((oid, name, extruder, len(tris)))
    lo = [min(v[k] for v in every) for k in range(3)]
    hi = [max(v[k] for v in every) for k in range(3)]
    move = (BED_CENTRE[0] - (lo[0] + hi[0]) / 2, BED_CENTRE[1] - (lo[1] + hi[1]) / 2, -lo[2])
    transform = "1 0 0 0 1 0 0 0 1 " + " ".join(f"{round(m, 5):g}" for m in move)
    aid = len(parts) + 1
    objects.append(f'<object id="{aid}" type="model"><components>'
                   + "".join(f'<component objectid="{i}"/>' for i, *_ in ids) + '</components></object>')
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<metadata name="Application">StratoScan {escape(what)}</metadata>'
             f'<resources>{"".join(objects)}</resources><build><item objectid="{aid}" transform="{transform}"/></build></model>')
    cfg = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>'
           f'<object id="{aid}"><metadata key="name" value="{escape(out[:-4])}"/>'
           + "".join(f'<metadata key="{escape(k)}" value="{escape(v)}"/>' for k, v in settings.items())
           + "".join(f'<part id="{i}" subtype="normal_part"><metadata key="name" value="{escape(n)}"/>'
                     f'<metadata key="extruder" value="{e}"/></part>' for i, n, e, _ in ids)
           + '</object></config>')
    ct = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rel0" Target="/3D/3dmodel.model" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", cfg)
    for i, n, e, nt in ids:
        print(f"  {n:34} filament {e}  {nt:6,} tris")
    print(f"  -> {out}")


if __name__ == "__main__":
    names = sys.argv[1:] or list(PROJECTS)
    for out in names:
        if out not in PROJECTS:
            sys.exit(f"unknown project {out}; known: {', '.join(PROJECTS)}")
        build(out, *PROJECTS[out])
