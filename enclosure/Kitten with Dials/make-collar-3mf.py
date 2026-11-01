#!/usr/bin/env python3
"""Builds the collar's two-colour 3MFs: the collar on filament 1 and its
inlay (the lettering and the two studs) on filament 2, as one object, and
the same for the collar's lettering test coupon (2026-11-01). It also builds
the head with its inner ears in a second colour, as the kitten's. The builder is
the kitten case's make-cover-3mf.py, as the Retro with Dials' arc uses the
retro case's (same reason: a slicer splits lettering into one part per
letter, so the colour assignment belongs in the file), so the file has the
structure the desktop app loads: name and extruder per part, no process
settings.

The collar prints face down, so the inlay is its first 0.6 mm. The head
prints as the kitten's head does.
Usage: python3 make-collar-3mf.py [project.3mf ...]   (after exporting the
STLs as BINARY: openscad --export-format binstl). With no names it builds
them all.
"""
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cover3mf", HERE.parent / "Kitten Enclosure Two-Tone" / "make-cover-3mf.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# project -> (what it is, [(STL, filament), ...])
PROJECTS = {
    "collar_twotone.3mf":          ("collar", [("collar", 1), ("collar_text", 2)]),
    "test_lettering_collar.3mf":   ("collar lettering coupon",
                                    [("test_lettering_collar", 1), ("test_lettering_collar_text", 2)]),
    # the head with its inner ears in a second colour, as the kitten's
    # kitten-head-twotone.3mf, less the wires' slot (2026-11-01):
    # shell_inner_ears.stl is the kitten's lining, exported here unchanged
    "kitten-head-dials-twotone.3mf": ("kitten head with dials",
                                      [("shell_head_dials", 1), ("shell_inner_ears", 2)]),
}

if __name__ == "__main__":
    import os
    os.chdir(HERE)
    names = sys.argv[1:] or list(PROJECTS)
    for out in names:
        if out not in PROJECTS:
            sys.exit(f"unknown project {out}; known: {', '.join(PROJECTS)}")
        m.build(out, *PROJECTS[out])
