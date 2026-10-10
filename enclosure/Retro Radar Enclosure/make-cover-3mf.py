#!/usr/bin/env python3
"""Builds a two-colour 3MF project for each twin antenna mount cover: the
cover on filament 1 and its engraved lettering on filament 2, as one object.

Why a project file rather than two STLs: the lettering is many separate
letters, and a slicer splits a multi-lump mesh into one part per lump on
import, so choosing a colour for "the text" would colour one letter. The
assignment belongs in the file (the kitten stand's make-3mf.py, same reason).

The cover prints outer face down, so the lettering is its first 0.6 mm
(three 0.2 mm layers): one filament change per layer, nothing after that.

Usage: python3 make-cover-3mf.py   (after exporting the four STLs as BINARY:
openscad --export-format binstl)
"""
import struct, zipfile
from xml.sax.saxutils import escape

COVERS = {
    "antenna_mount_twin_cover_8_twotone.3mf":  [("antenna_mount_twin_cover_8", 1), ("antenna_mount_twin_cover_text_8", 2)],
    "antenna_mount_twin_cover_11_twotone.3mf": [("antenna_mount_twin_cover_11", 1), ("antenna_mount_twin_cover_text_11", 2)],
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


def build(out, parts):
    objects, ids = [], []
    for oid, (name, extruder) in enumerate(parts, start=1):
        verts, tris = read_stl(name + ".stl")
        v = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in verts)
        t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris)
        objects.append(f'<object id="{oid}" type="model"><mesh><vertices>{v}</vertices>'
                       f'<triangles>{t}</triangles></mesh></object>')
        ids.append((oid, name, extruder, len(tris)))
    aid = len(parts) + 1
    objects.append(f'<object id="{aid}" type="model"><components>'
                   + "".join(f'<component objectid="{i}"/>' for i, *_ in ids) + '</components></object>')
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             '<metadata name="Application">StratoScan twin antenna mount cover</metadata>'
             f'<resources>{"".join(objects)}</resources><build><item objectid="{aid}"/></build></model>')
    cfg = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>'
           f'<object id="{aid}"><metadata key="name" value="{escape(out[:-4])}"/>'
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
    for out, parts in COVERS.items():
        build(out, parts)
