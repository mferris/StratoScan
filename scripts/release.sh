#!/bin/sh
# Cuts a signed release and publishes it to GitHub Releases.
#
# Run this on the maintainer's machine, never on a device and never in CI: it
# needs the private signing key, which is the one secret that must not spread.
#
# What it produces, all attached to a GitHub release:
#
#   flightradar-<version>.tar.gz   the payload: index.html and deploy/
#   manifest.json                  version, serial, per-file sha256, bundle sha256
#   manifest.json.sig             an ssh signature over the manifest
#
# Only the MANIFEST is signed. The manifest names every file by hash, and names
# the bundle by hash, so one signature covers the lot -- and a device can check
# the bundle before unpacking it rather than trusting an archive it has already
# extracted.
#
# Usage: sh scripts/release.sh <version> [--dry-run]
set -eu

KEY="${FLIGHTRADAR_SIGNING_KEY:-$HOME/.ssh/flightradar-signing}"
NAMESPACE=flightradar
REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
VERSION="${1:-}"
DRY=""
[ "${2:-}" = "--dry-run" ] && DRY=1

[ -n "$VERSION" ] || { echo "usage: sh scripts/release.sh <version> [--dry-run]" >&2; exit 1; }
[ -f "$KEY" ] || { echo "no signing key at $KEY" >&2; exit 1; }

cd "$REPO_ROOT"

# The serial is what the device actually compares, not the version string.
# Parsing "2026.09.13.1" to decide whether it is newer than "2026.9.9.2" is a
# trap; a monotonically increasing integer is not. It also blocks a downgrade
# attack: an old release is correctly signed forever, so without this a device
# could be pushed back to a version with a bug that has since been fixed.
SERIAL=$(git rev-list --count HEAD)
OUT="$REPO_ROOT/dist/$VERSION"
rm -rf "$OUT"; mkdir -p "$OUT"
BUNDLE="flightradar-$VERSION.tar.gz"

# The payload. Deliberately explicit: an update must never be able to ship the
# signing key, the enclosure sources, or the git history.
# COPYFILE_DISABLE stops macOS tar from quietly adding an AppleDouble "._name"
# beside every file. They are resource forks, they are not part of the product,
# and they would end up named in a signed manifest -- noticed only because a
# test release listed "._index.html" next to "index.html".
COPYFILE_DISABLE=1 tar -czf "$OUT/$BUNDLE" \
    --exclude='.DS_Store' \
    --exclude='._*' \
    index.html deploy

python3 - "$OUT" "$BUNDLE" "$VERSION" "$SERIAL" <<'PY'
import hashlib, json, os, subprocess, sys, tarfile, time

out, bundle, version, serial = sys.argv[1:5]

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

# Per-file hashes as well as the bundle hash. The bundle hash proves the
# archive arrived intact; the per-file hashes let the device verify what it
# actually wrote, which is the thing that ends up on disk.
files = {}
with tarfile.open(os.path.join(out, bundle)) as tf:
    for m in tf.getmembers():
        if m.isfile():
            files[m.name] = hashlib.sha256(tf.extractfile(m).read()).hexdigest()

manifest = {
    "version": version,
    "serial": int(serial),
    "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "bundle": {"name": bundle, "sha256": sha256(os.path.join(out, bundle))},
    "files": files,
}
with open(os.path.join(out, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=1, sort_keys=True)
    f.write("\n")
print(f"  version {version}  serial {serial}  {len(files)} files")
PY

ssh-keygen -Y sign -f "$KEY" -n "$NAMESPACE" "$OUT/manifest.json" >/dev/null
echo "  signed manifest.json -> manifest.json.sig"

# Verify what was just produced, with the PUBLIC key the devices carry, exactly
# as a device would. Signing and then shipping without checking is how a
# release that no device will accept gets published.
ssh-keygen -Y verify -f "$REPO_ROOT/deploy/allowed_signers" \
    -I flightradar-release -n "$NAMESPACE" \
    -s "$OUT/manifest.json.sig" < "$OUT/manifest.json" >/dev/null \
  && echo "  self-check: a device would accept this" \
  || { echo "  SELF-CHECK FAILED -- not publishing" >&2; exit 1; }

if [ -n "$DRY" ]; then
    echo "  dry run: not publishing. Assets in $OUT"
    exit 0
fi

gh release create "$VERSION" \
    "$OUT/$BUNDLE" "$OUT/manifest.json" "$OUT/manifest.json.sig" \
    --title "$VERSION" --notes "FlightRadar $VERSION (serial $SERIAL)"
echo "  published $VERSION"
