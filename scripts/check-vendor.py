#!/usr/bin/env python3
"""The page's vendored libraries against GitHub's advisory database (#74).

vendor/VERSIONS.json names each file's npm package, version and hash. For
each package this asks GitHub's advisory database which advisories affect
that version, and npm which version is the newest:

  - an advisory whose fix exists (the newest version is outside its range,
    or it names a patched version) refuses the release, unless
    VERSIONS.json accepts it with a reason and an end date that hasn't
    passed;
  - an advisory with no fix anywhere yet is printed, not refused, or
    nothing could ship;
  - a file whose hash doesn't match its record refuses: the record would
    be describing something else.

It fails closed: if GitHub or npm can't be asked, the release is refused.

Run: python3 scripts/check-vendor.py [--commit SHA]
"""
import datetime
import hashlib
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def read(path, commit):
    if commit:
        return subprocess.run(["git", "-C", str(ROOT), "show", f"{commit}:{path}"],
                              capture_output=True, check=True).stdout
    return (ROOT / path).read_bytes()


def vkey(v):
    return tuple(int(x) for x in re.findall(r"\d+", v.split("-")[0])[:3])


def in_range(version, rng):
    """True if `version` satisfies GitHub's range syntax ("<= 6.4.0",
    ">= 5.0.0, < 5.7.1", "= 1.2.3")."""
    v = vkey(version)
    for part in [p.strip() for p in (rng or "").split(",") if p.strip()]:
        m = re.match(r"^(<=|>=|<|>|=)\s*(\S+)$", part)
        if not m:
            return True      # can't read it: assume it applies
        op, w = m.group(1), vkey(m.group(2))
        if not {"<": v < w, "<=": v <= w, ">": v > w, ">=": v >= w, "=": v == w}[op]:
            return False
    return True


def advisories(package, version):
    out = subprocess.run(["gh", "api", f"advisories?ecosystem=npm&affects={package}@{version}&per_page=100"],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(f"GitHub's advisory database didn't answer: {out.stderr.strip()[:200]}")
    return json.loads(out.stdout)


def newest(package):
    out = subprocess.run(["npm", "view", package, "version"], capture_output=True, text=True, timeout=60)
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(f"npm didn't say what the newest {package} is")
    return out.stdout.strip()


def main(argv):
    commit = argv[argv.index("--commit") + 1] if "--commit" in argv else None
    doc = json.loads(read("vendor/VERSIONS.json", commit))
    accepted = doc.get("accepted_advisories", {})
    today = datetime.date.today().isoformat()
    refuse = []
    for name, rec in doc["files"].items():
        got = hashlib.sha256(read(f"vendor/{name}", commit)).hexdigest()
        if got != rec["sha256"]:
            refuse.append(f"vendor/{name} doesn't match its record in VERSIONS.json")
    packages = {(r["package"], r["version"]) for r in doc["files"].values() if r.get("ecosystem") == "npm"}
    for package, version in sorted(packages):
        try:
            found, latest = advisories(package, version), newest(package)
        except Exception as e:
            print(f"  {package}: {e}")
            return 2
        if not found:
            print(f"  {package} {version}: no advisories (newest is {latest})")
        for a in found:
            vulns = [v for v in a.get("vulnerabilities", []) if (v.get("package") or {}).get("name") == package]
            rng = vulns[0].get("vulnerable_version_range") if vulns else ""
            patched = vulns[0].get("first_patched_version") or vulns[0].get("patched_versions") if vulns else None
            fixed = bool(patched) or not in_range(latest, rng)
            ok = accepted.get(a["ghsa_id"])
            line = f"  {package} {version}: {a['ghsa_id']} ({a.get('severity')}) affects {rng or '?'}; " + \
                   (f"fixed in {patched or latest}" if fixed else "no fix published yet")
            if not fixed:
                print(line + " -- noted, not refused")
            elif ok and ok.get("until", "") >= today:
                print(line + f" -- accepted until {ok['until']}: {ok.get('why', '')}")
            else:
                refuse.append(line + (" (its acceptance has ended)" if ok else ""))
    for r in refuse:
        print("  REFUSE:" + r)
    return 1 if refuse else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
