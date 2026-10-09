#!/bin/sh
# Cuts a signed release and publishes it to GitHub Releases; afterwards,
# widens, pauses or resumes its rollout.
#
# Run this on the maintainer's machine, never on a device and never in CI: it
# needs the private signing key, which is the one secret that must not spread.
#
# What a release is, all attached to one GitHub release:
#
#   stratoscan-<version>.tar.gz   the payload: index.html, deploy/ and sounds/
#   manifest.json                  version, serial, per-file sha256, bundle sha256
#   manifest.stratoscan.sig        an ssh signature over the manifest
#   manifest.json.sig              the same, for updaters from before the rename
#   rollout.json                   how far it may go: a ring 0-3, paused or not
#   rollout.json.sig               an ssh signature over the policy
#
# Only the MANIFEST and the POLICY are signed. The manifest names every file
# by hash, and names the bundle by hash, so one signature covers the lot --
# and a device can check the bundle before unpacking it rather than trusting
# an archive it has already extracted. The policy is signed in its own
# namespace (stratoscan-rollout), so neither can stand in for the other.
#
# A RELEASE IS BUILT FROM A COMMIT, NOT FROM THE WORKING TREE. The bundle is
# the commit's tree (git archive), the serial is that commit's count, and the
# release is tagged on it -- so a release always says exactly which code it
# is. By default the commit is HEAD, which must be clean under the payload
# paths and already on GitHub; --commit REF builds an older commit, which is
# how a hotfix ships without whatever else has landed on main since (the
# 2026-10-08 hotfix went out with three unrelated changes because the script
# took the working tree).
#
# A RELEASE REACHES UNITS IN RINGS (performance audit, 2026-10-09). Ring 0 is
# the maintainer's own radar, 1 family, 2 early adopters, 3 everyone; a unit's
# ring is in /etc/stratoscan/ring (RING= to the installer; none means 3). A
# fresh release starts at ring 0. After the canary has run it for a day,
# `rollout <version> --ring N` lets the next ring in; before that the script
# refuses unless told --force. `--pause` stops the spread, `--resume` lifts
# the pause; a unit that already has the release keeps it, since there is no
# downgrade -- a fix is the next release.
#
# Usage: sh scripts/release.sh <version> [--ring N] [--commit REF] [--dry-run]
#        sh scripts/release.sh rollout <version>                      show the policy
#        sh scripts/release.sh rollout <version> --ring N [--force]   widen, or narrow
#        sh scripts/release.sh rollout <version> --pause | --resume [--ring N]
set -eu

# The key file was ~/.ssh/flightradar-signing before the rename; same key.
DEFAULT_KEY="$HOME/.ssh/stratoscan-signing"
[ -f "$DEFAULT_KEY" ] || DEFAULT_KEY="$HOME/.ssh/flightradar-signing"
KEY="${STRATOSCAN_SIGNING_KEY:-${FLIGHTRADAR_SIGNING_KEY:-$DEFAULT_KEY}}"   # the old variable still works
REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
SIGNERS="$REPO_ROOT/deploy/allowed_signers"

usage() {
    cat >&2 <<'USAGE'
usage: sh scripts/release.sh <version> [--ring N] [--commit REF] [--dry-run]
       sh scripts/release.sh rollout <version> [--ring N] [--pause|--resume] [--force] [--dry-run]
USAGE
    exit 1
}

MODE=release
[ "${1:-}" = "rollout" ] && { MODE=rollout; shift; }
VERSION="${1:-}"
[ -n "$VERSION" ] || usage
shift
RING="" COMMIT=HEAD DRY="" FORCE="" PAUSE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --ring)    RING="${2:-}"; [ -n "$RING" ] || usage; shift 2 ;;
        --commit)  COMMIT="${2:-}"; [ -n "$COMMIT" ] || usage; shift 2 ;;
        --dry-run) DRY=1; shift ;;
        --force)   FORCE=1; shift ;;
        --pause)   PAUSE=pause; shift ;;
        --resume)  PAUSE=resume; shift ;;
        *) usage ;;
    esac
done
case "${RING:-0}" in 0|1|2|3) ;; *) echo "the ring is 0, 1, 2 or 3, not '$RING'" >&2; exit 1 ;; esac
[ -f "$KEY" ] || { echo "no signing key at $KEY" >&2; exit 1; }

cd "$REPO_ROOT"

# In a dry run a guard only warns, so the bundle can still be inspected
# offline or before a push; for real it refuses.
guard() {
    if [ -n "$DRY" ]; then echo "  WARNING (a real run would refuse): $1" >&2
    else echo "REFUSED: $1" >&2; exit 1; fi
}

# The serial of the latest release on GitHub, 0 when there is none (or it
# cannot be read -- a guard that cannot see refuses nothing, so it is only
# a guard; the devices compare serials for themselves).
latest_release_serial() {
    tag=$(gh release view --json tagName -q .tagName 2>/dev/null || true)
    [ -n "$tag" ] || { echo "0 -"; return; }
    t=$(mktemp -d)
    serial=0
    if gh release download "$tag" --pattern manifest.json --dir "$t" >/dev/null 2>&1; then
        serial=$(python3 -c 'import json,sys; print(int(json.load(open(sys.argv[1])).get("serial", 0)))' "$t/manifest.json")
    fi
    rm -rf "$t"
    echo "$serial $tag"
}

# Writes $1/rollout.json for the release whose manifest.json (and, when it
# has one already, rollout.json) is in $1. Actions: cut (a new release,
# ring $3), set (ring $3), pause, resume, show. Prints what it did, or
# refuses: widening past ring 0 inside the canary's first day needs --force.
write_policy() {   # <dir> <action> <ring> <force 0|1>
    python3 - "$1" "$2" "$3" "$4" <<'PY'
import calendar, json, os, sys, time

d, action, ring, force = sys.argv[1:5]
FMT = "%Y-%m-%dT%H:%M:%SZ"
SOAK_H = 24
RING_NAMES = {0: "the maintainer's own radar", 1: "family", 2: "early adopters", 3: "everyone"}

manifest = json.load(open(os.path.join(d, "manifest.json")))
serial, version = int(manifest["serial"]), manifest["version"]
try:
    cur = json.load(open(os.path.join(d, "rollout.json")))
except OSError:
    cur = {}
if cur and int(cur.get("serial", -1)) != serial:
    cur = {}          # a policy for some other release is no policy
now = time.time()
cur_ring = int(cur["ring"]) if "ring" in cur else None
paused = bool(cur.get("paused"))
released_at = cur.get("released_at") or manifest.get("created") or time.strftime(FMT, time.gmtime(now))
out_h = (now - calendar.timegm(time.strptime(released_at, FMT))) / 3600

def describe(r, p):
    return f"ring {r} ({RING_NAMES[r]}){', PAUSED' if p else ''}"

if action == "show":
    if cur_ring is None:
        print(f"  {version} (serial {serial}) has no rollout policy: it reaches no unit")
    else:
        print(f"  {version} (serial {serial}): {describe(cur_ring, paused)}, "
              f"out for {out_h:.1f} h, policy written {cur.get('at', '?')}"
              + (f" ({cur['note']})" if cur.get("note") else ""))
    sys.exit(0)

if action == "cut":
    new_ring, paused, note = int(ring), False, "cut"
elif action == "pause":
    new_ring, paused, note = (cur_ring if cur_ring is not None else 0), True, "paused"
elif action == "resume":
    new_ring, paused, note = (int(ring) if ring else cur_ring if cur_ring is not None else 0), False, "resumed"
else:
    new_ring, paused, note = int(ring), False, "widened" if cur_ring is None or int(ring) > cur_ring else "narrowed"

widening = new_ring > 0 and (cur_ring is None or new_ring > cur_ring)
if action != "cut" and widening and out_h < SOAK_H and force != "1":
    print(f"  REFUSED: {version} has been out for {out_h:.1f} h; the canary (ring 0) soaks it for "
          f"{SOAK_H} h before it widens. --force to widen anyway.", file=sys.stderr)
    sys.exit(1)
if action == "cut" and new_ring > 0:
    print(f"  note: cut straight to {describe(new_ring, False)}, no canary")

policy = {
    "kind": "rollout", "version": version, "serial": serial,
    "ring": new_ring, "paused": paused,
    "released_at": released_at,
    "at": time.strftime(FMT, time.gmtime(now)),
    "note": note,
}
with open(os.path.join(d, "rollout.json"), "w") as f:
    json.dump(policy, f, indent=1, sort_keys=True)
    f.write("\n")
was = describe(cur_ring, bool(cur.get("paused"))) if cur_ring is not None else "no policy"
print(f"  rollout of {version}: {was} -> {describe(new_ring, paused)}")
PY
}

# Signs $1/rollout.json in its own namespace and checks it as a device would.
sign_policy() {
    ssh-keygen -Y sign -f "$KEY" -n stratoscan-rollout "$1/rollout.json" >/dev/null
    ssh-keygen -Y verify -f "$SIGNERS" -I stratoscan-release -n stratoscan-rollout \
        -s "$1/rollout.json.sig" < "$1/rollout.json" >/dev/null \
      || { echo "  SELF-CHECK FAILED on the rollout policy -- not publishing" >&2; exit 1; }
}

# ---- rollout: change how far an existing release goes ---------------------
if [ "$MODE" = rollout ]; then
    [ "$COMMIT" = HEAD ] || usage
    ACTION=show
    [ -n "$RING" ] && ACTION=set
    [ "$PAUSE" = pause ] && ACTION=pause
    [ "$PAUSE" = resume ] && ACTION=resume
    T=$(mktemp -d)
    gh release download "$VERSION" --pattern manifest.json --pattern rollout.json --dir "$T" >/dev/null 2>&1 \
        || { echo "no release $VERSION on GitHub, or it has no manifest" >&2; exit 1; }
    [ -f "$T/manifest.json" ] || { echo "release $VERSION has no manifest.json" >&2; exit 1; }
    LATEST=$(gh release view --json tagName -q .tagName 2>/dev/null || true)
    [ "$LATEST" = "$VERSION" ] || echo "  note: the latest release is $LATEST, not $VERSION; units read only the latest, so this policy decides nothing until $VERSION is"
    write_policy "$T" "$ACTION" "$RING" "${FORCE:-0}"
    [ "$ACTION" = show ] && exit 0
    sign_policy "$T"
    if [ -n "$DRY" ]; then echo "  dry run: not publishing. Policy in $T"; exit 0; fi
    gh release upload "$VERSION" "$T/rollout.json" "$T/rollout.json.sig" --clobber >/dev/null
    rm -rf "$T"
    echo "  published; units see it at their next check (nightly, or from the settings screen)"
    exit 0
fi

# ---- release: build, sign, publish ----------------------------------------
RING="${RING:-0}"
SHA=$(git rev-parse --verify --quiet "${COMMIT}^{commit}") || { echo "no such commit: $COMMIT" >&2; exit 1; }
SHORT=$(git rev-parse --short "$SHA")

# Built from the commit, so anything uncommitted under the payload paths
# would silently not ship -- which is a surprise either way round.
if [ "$COMMIT" = HEAD ]; then
    if ! git diff --quiet HEAD -- index.html deploy sounds \
       || [ -n "$(git ls-files --others --exclude-standard -- index.html deploy sounds)" ]; then
        guard "uncommitted changes under index.html, deploy/ or sounds/ would not ship (a release is built from the commit, not the working tree): commit them, or name a commit with --commit"
    fi
fi
# The release is tagged on the commit, and GitHub refuses a commit it has
# never seen ("Release.target_commitish is invalid", 2026-10-08).
git fetch -q origin 2>/dev/null || guard "could not reach origin to confirm $SHORT is pushed"
[ -n "$(git branch -r --contains "$SHA" 2>/dev/null)" ] || guard "commit $SHORT is not on GitHub: push it first"

# The serial is what the device actually compares, not the version string.
# Parsing "2026.09.13.1" to decide whether it is newer than "2026.9.9.2" is a
# trap; a monotonically increasing integer is not. It also blocks a downgrade
# attack: an old release is correctly signed forever, so without this a device
# could be pushed back to a version with a bug that has since been fixed.
SERIAL=$(git rev-list --count "$SHA")
set -- $(latest_release_serial)
LATEST_SERIAL=$1; LATEST_TAG=$2
if [ "$SERIAL" -le "$LATEST_SERIAL" ]; then
    guard "serial $SERIAL is not above the latest release's ($LATEST_TAG, serial $LATEST_SERIAL): every unit would refuse it as not newer. A release needs a commit the last one did not have"
fi

OUT="$REPO_ROOT/dist/$VERSION"
rm -rf "$OUT"; mkdir -p "$OUT/tree"
BUNDLE="stratoscan-$VERSION.tar.gz"

# The payload, from the commit's tree. Deliberately explicit: an update must
# never be able to ship the signing key, the enclosure sources, or the git
# history. git archive carries only tracked files, so .DS_Store and macOS
# "._name" resource forks never get in; the excludes stay as a second refusal
# (a test release once listed "._index.html" in a signed manifest).
git archive --format=tar "$SHA" index.html deploy sounds > "$OUT/tree.tar"
tar -xf "$OUT/tree.tar" -C "$OUT/tree"
(cd "$OUT/tree" && COPYFILE_DISABLE=1 tar -czf "$OUT/$BUNDLE" \
    --exclude='.DS_Store' \
    --exclude='._*' \
    --exclude='CREDITS.md' \
    index.html deploy sounds)
rm -rf "$OUT/tree" "$OUT/tree.tar"

python3 - "$OUT" "$BUNDLE" "$VERSION" "$SERIAL" "$SHA" <<'PY'
import hashlib, json, os, subprocess, sys, tarfile, time

out, bundle, version, serial, sha = sys.argv[1:6]

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

# Per-file hashes as well as the bundle hash. The bundle hash proves the
# archive arrived intact; the per-file hashes let the device verify what it
# actually wrote, which is the thing that ends up on disk.
# Hash AND mode. The mode matters and it was missed the first time: a file
# installed 644 that needs to be 755 is not a cosmetic difference, it is a
# script that will not run. The update that found this installed a new ota.py
# without its executable bit and broke its own updater.
#
# Only the executable bit is carried, not the whole mode: a manifest that can
# set arbitrary permissions on root-owned files is a much larger thing to
# sign off on than one that can say "this is a program".
files = {}
with tarfile.open(os.path.join(out, bundle)) as tf:
    for m in tf.getmembers():
        if m.isfile():
            files[m.name] = {
                "sha256": hashlib.sha256(tf.extractfile(m).read()).hexdigest(),
                "exec": bool(m.mode & 0o111),
            }

manifest = {
    "version": version,
    "serial": int(serial),
    "commit": sha,
    "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "bundle": {"name": bundle, "sha256": sha256(os.path.join(out, bundle))},
    "files": files,
}
with open(os.path.join(out, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=1, sort_keys=True)
    f.write("\n")
print(f"  version {version}  serial {serial}  commit {sha[:10]}  {len(files)} files")
PY

# Two signatures while units move over (2026-09-30): the 'stratoscan' one that
# current updaters prefer, and the 'flightradar' one that updaters from before
# the rename can read (they only look for manifest.json.sig). Same key.
ssh-keygen -Y sign -f "$KEY" -n stratoscan "$OUT/manifest.json" >/dev/null
mv "$OUT/manifest.json.sig" "$OUT/manifest.stratoscan.sig"
ssh-keygen -Y sign -f "$KEY" -n flightradar "$OUT/manifest.json" >/dev/null
echo "  signed manifest.json -> manifest.stratoscan.sig, manifest.json.sig"

# Verify what was just produced, with the PUBLIC key the devices carry, exactly
# as a device would -- each signature as the updater that reads it would.
# Signing and then shipping without checking is how a release that no device
# will accept gets published.
check_sig() {  # <signature file> <namespace> <signer name>
    ssh-keygen -Y verify -f "$SIGNERS" -I "$3" -n "$2" \
        -s "$1" < "$OUT/manifest.json" >/dev/null
}
check_sig "$OUT/manifest.stratoscan.sig" stratoscan stratoscan-release \
  && check_sig "$OUT/manifest.json.sig" flightradar flightradar-release \
  && echo "  self-check: both current and pre-rename updaters would accept this" \
  || { echo "  SELF-CHECK FAILED -- not publishing" >&2; exit 1; }

write_policy "$OUT" cut "$RING" 0
sign_policy "$OUT"

if [ -n "$DRY" ]; then
    echo "  dry run: not publishing. Assets in $OUT"
    exit 0
fi

# Tag the commit this was built from, not whatever main points at on GitHub:
# a release cut from an earlier commit would otherwise be tagged with code it
# doesn't contain.
gh release create "$VERSION" --target "$SHA" \
    "$OUT/$BUNDLE" "$OUT/manifest.json" "$OUT/manifest.stratoscan.sig" "$OUT/manifest.json.sig" \
    "$OUT/rollout.json" "$OUT/rollout.json.sig" \
    --title "$VERSION" --notes "StratoScan $VERSION (serial $SERIAL, commit $SHORT, rollout ring $RING)"
echo "  published $VERSION at ring $RING"
[ "$RING" = 0 ] && echo "  after a day on the canary: sh scripts/release.sh rollout $VERSION --ring 1  (then 2, 3)"
exit 0
