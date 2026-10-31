#!/usr/bin/env python3
"""Builds the control arc's two-colour 3MFs: the arc on filament 1 and its
lettering on filament 2, as one object, and the same for the arc's lettering
test coupon (2026-10-31). The builder is the retro case's make-cover-3mf.py
(same reason: a slicer splits lettering into one part per letter, so the
colour assignment belongs in the file), so the file has the structure the
desktop app loads: name and extruder per part, no process settings.

The arc prints face down, so the lettering is its first 0.6 mm.
Usage: python3 make-arc-3mf.py [project.3mf ...]   (after exporting the STLs
as BINARY: openscad --export-format binstl). With no names it builds them all.
"""
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cover3mf", HERE.parent / "Retro Radar Enclosure" / "make-cover-3mf.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# project -> (what it is, [(STL, filament), ...])
PROJECTS = {
    "control_arc_twotone.3mf": ("control arc", [("control_arc", 1), ("control_arc_text", 2)]),
    "test_lettering_arc.3mf":  ("control arc lettering coupon",
                                [("test_lettering_arc", 1), ("test_lettering_arc_text", 2)]),
}

if __name__ == "__main__":
    import os
    os.chdir(HERE)
    names = sys.argv[1:] or list(PROJECTS)
    for out in names:
        if out not in PROJECTS:
            sys.exit(f"unknown project {out}; known: {', '.join(PROJECTS)}")
        m.build(out, *PROJECTS[out])
