#!/usr/bin/env python3
"""The page's vendored libraries can be updated, are recorded, and are
checked before release (#74, 2026-10-13).

Before this, a release carried index.html, deploy/ and sounds/ only, so a
radar kept whatever vendor/ its installer put there for good.

Run: python3 tests/test_vendor.py
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


# what each vendored file is
doc = json.loads((ROOT / "vendor" / "VERSIONS.json").read_text())
on_disk = sorted(p.name for p in (ROOT / "vendor").iterdir() if p.name not in ("VERSIONS.json",) and not p.name.startswith("."))
check(sorted(doc["files"]) == on_disk, "every file in vendor/ has a record, and every record a file")
for name, rec in doc["files"].items():
    data = (ROOT / "vendor" / name).read_bytes()
    check(hashlib.sha256(data).hexdigest() == rec["sha256"], f"{name} matches its recorded hash")
    check(rec.get("ecosystem") == "npm" and rec.get("package") and re.fullmatch(r"\d+\.\d+\.\d+", rec.get("version", "")),
          f"{name} names its npm package and version")
for name in ("maplibre-gl.mjs", "maplibre-gl-worker.mjs"):
    head = (ROOT / "vendor" / name).read_text(errors="replace")[:400]
    ver = doc["files"][name]["version"]
    check(f"v{ver}/LICENSE" in head and "@license 3-Clause BSD" in head,
          f"{name} really is MapLibre {ver}, with its licence header intact")
    check("sourceMappingURL" not in (ROOT / "vendor" / name).read_text(errors="replace")[-300:],
          f"{name} asks for no source map (not shipped, so it would only be a 404)")
for gid, acc in doc.get("accepted_advisories", {}).items():
    check(re.fullmatch(r"\d{4}-\d{2}-\d{2}", acc.get("until", "")) is not None and len(acc.get("why", "")) > 40,
          f"accepting {gid} has a reason and an end date")

# the updater installs them, and nothing else under vendor/
os.environ["STRATOSCAN_WEB_ROOT"] = "/var/www/html"
spec = importlib.util.spec_from_file_location("ota", ROOT / "deploy" / "ota.py")
ota = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ota)
check(ota.dest_for("vendor/maplibre-gl.js") == "/var/www/html/vendor/maplibre-gl.js", "a release installs vendor/*.js")
check(ota.dest_for("vendor/maplibre-gl.css") == "/var/www/html/vendor/maplibre-gl.css", "and vendor/*.css")
check(ota.dest_for("vendor/maplibre-gl-worker.mjs") == "/var/www/html/vendor/maplibre-gl-worker.mjs",
      "and vendor/*.mjs (MapLibre 6 ships only ES modules)")
for bad in ("vendor/VERSIONS.json", "vendor/x.sh", "vendor/sub/x.js", "vendor/../x.js", "vendor/", "vendor/.hidden.js",
            "vendor/x.html"):
    check(ota.dest_for(bad) is None, f"but not {bad}")

# releases carry them, and refuse an advisory with a fix available
rel = (ROOT / "scripts" / "release.sh").read_text()
check('index.html deploy sounds vendor > "$OUT/tree.tar"' in rel and "index.html deploy sounds vendor)" in rel,
      "release.sh puts vendor/ in the bundle")
check('scripts/check-vendor.py" --commit "$SHA"' in rel and "|| guard" in rel.split("check-vendor.py")[1][:200],
      "and runs the advisory check as a guard")

spec = importlib.util.spec_from_file_location("cv", ROOT / "scripts" / "check-vendor.py")
cv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv)
check(cv.in_range("5.24.0", "<= 6.4.0") and not cv.in_range("6.14.0", "<= 6.4.0"), "ranges: <= reads right")
check(cv.in_range("5.6.0", ">= 5.0.0, < 5.7.1") and not cv.in_range("5.7.1", ">= 5.0.0, < 5.7.1"), "ranges: a pair reads right")
check(cv.in_range("1.0.0", "weird"), "an unreadable range is assumed to apply")

# MapLibre 6: loaded as an ES module, its worker beside it (2026-10-13)
html = (ROOT / "index.html").read_text()
check("import('./vendor/maplibre-gl.mjs')" in html and 'src="vendor/maplibre-gl.js"' not in html,
      "the page loads MapLibre 6 with import(), not the old classic script")
check("await loadMapLibre();" in html.split("async function initMap()")[1][:600],
      "and waits for it before building the first map")
check((ROOT / "vendor" / "maplibre-gl-worker.mjs").exists(), "its worker ships beside it")
check(not (ROOT / "vendor" / "maplibre-gl.js").exists(), "the 5.x file is gone")

# no HTML reaches MapLibre (its DOM.sanitize had GHSA-jrc7-96c5-q579 to 6.4.0)
check("attributionControl: false" in html, "MapLibre's credits control is off (it sanitises provider HTML)")
check("maplibregl.Popup" not in html and "setHTML(" not in html, "the page has no MapLibre popups or HTML")
check("function renderMapCredits()" in html and "innerHTML" not in html.split("function renderMapCredits()")[1].split("\n}\n")[0],
      "the page draws the credits itself, without innerHTML")
for src in ("openmaptiles", "offline", "storms", "lightning"):
    check(f"  {src}: [[" in html.split("const MAP_CREDITS = {")[1][:900], f"the {src} source keeps its credit")

print("vendor checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
