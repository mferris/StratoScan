#!/usr/bin/env python3
"""Builds the control arc's two-colour 3MF: the arc on filament 1 and its
lettering on filament 2, as one object. The builder is the retro case's
make-cover-3mf.py (same reason: a slicer splits lettering into one part per
letter, so the colour assignment belongs in the file).

The arc prints face down, so the lettering is its first 0.6 mm.
Usage: python3 make-arc-3mf.py   (after exporting control_arc.stl and control_arc_text.stl
as BINARY: openscad --export-format binstl)
"""
import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cover3mf", HERE.parent / "Retro Radar Enclosure" / "make-cover-3mf.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

if __name__ == "__main__":
    import os
    os.chdir(HERE)
    m.build("control_arc_twotone.3mf", [("control_arc", 1), ("control_arc_text", 2)])
    print("control_arc_twotone.3mf")
