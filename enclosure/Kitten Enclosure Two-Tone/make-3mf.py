#!/usr/bin/env python3
"""Builds a single 3MF project with the six stand bodies as one object, each
already assigned a filament.

Why this exists rather than "load the six STLs and pick a colour for each":
three of the bodies are physically several disconnected lumps -- two paws, two
clumps of toes, and eight separate claws -- because that is what the shapes
are. Slicers split a multi-lump mesh into separate parts on import, so
clicking one and choosing a filament colours ONE CLAW, and the other seven
stay as they were. That is not a mistake anyone can be expected to work
around; the assignment belongs in the file.

Filament slots (change them in the slicer if you want other colours):
  1  stand_body, stand_toes, stand_tail        the black
  2  stand_paws, stand_tail_tip                the white
  3  stand_claws                               left on its own slot so the
                                               claws can be a third colour
"""
import struct, sys, zipfile
from xml.sax.saxutils import escape

PARTS = [
    ("stand_body",     1),
    ("stand_toes",     1),
    ("stand_tail",     1),
    ("stand_paws",     2),
    ("stand_tail_tip", 2),
    ("stand_claws",    3),
]


def read_stl(path):
    """Binary STL -> (vertices, triangles) with vertices de-duplicated."""
    with open(path, "rb") as f:
        f.seek(80)
        (n,) = struct.unpack("<I", f.read(4))
        idx, verts, tris = {}, [], []
        for _ in range(n):
            d = f.read(50)
            v = struct.unpack("<12f", d[:48])
            tri = []
            for i in (3, 6, 9):
                key = (round(v[i], 5), round(v[i+1], 5), round(v[i+2], 5))
                j = idx.get(key)
                if j is None:
                    j = len(verts)
                    idx[key] = j
                    verts.append(key)
                tri.append(j)
            # A degenerate triangle (two indices equal after welding) is not
            # geometry and some slicers reject the whole mesh over one.
            if tri[0] != tri[1] and tri[1] != tri[2] and tri[0] != tri[2]:
                tris.append(tri)
    return verts, tris


def main():
    objects, settings, oid = [], [], 1
    part_ids = []
    for name, extruder in PARTS:
        verts, tris = read_stl(name + ".stl")
        v = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in verts)
        t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris)
        objects.append(
            f'<object id="{oid}" type="model"><mesh><vertices>{v}</vertices>'
            f'<triangles>{t}</triangles></mesh></object>')
        part_ids.append((oid, name, extruder, len(verts), len(tris)))
        oid += 1

    # One assembly object holding every part, so the slicer shows a single
    # object with six sub-parts rather than six loose objects to align.
    comps = "".join(f'<component objectid="{i}"/>' for i, _, _, _, _ in part_ids)
    assembly_id = oid
    objects.append(f'<object id="{assembly_id}" type="model">'
                   f'<components>{comps}</components></object>')

    model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        '<metadata name="Application">FlightRadar kitten stand</metadata>'
        f'<resources>{"".join(objects)}</resources>'
        f'<build><item objectid="{assembly_id}"/></build></model>')

    parts_xml = "".join(
        f'<part id="{i}" subtype="normal_part">'
        f'<metadata key="name" value="{escape(n)}"/>'
        f'<metadata key="extruder" value="{e}"/></part>'
        for i, n, e, _, _ in part_ids)
    cfg = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>'
           f'<object id="{assembly_id}">'
           '<metadata key="name" value="Kitten stand (two-tone)"/>'
           f'{parts_xml}</object></config>')

    ct = ('<?xml version="1.0" encoding="UTF-8"?>\n'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rel0" Target="/3D/3dmodel.model" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')

    out = "kitten-stand-twotone.3mf"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", cfg)
    for i, n, e, nv, nt in part_ids:
        print(f"  part {i}: {n:16} filament {e}   {nv:7,} verts  {nt:7,} tris")
    print(f"  -> {out}")


if __name__ == "__main__":
    main()
