#!/bin/sh
# Builds the StratoScan factory image. Run as root on arm64 Linux (GitHub's
# ubuntu-24.04-arm runners), from the repo root:  sudo sh image/build.sh
#
# Output in $OUT (default ./image-out):
#   stratoscan-<version>.img.xz (+ .sha256)   the image to flash
#   MANIFEST.txt                               pinned versions + every package
#   SOURCES.md                                 GPL source offer
#   src/*.tar.gz                               Corresponding Source for readsb,
#                                              tar1090, dump978 and Piper as built
. "$(dirname "$0")/lib.sh"
REPO=$(cd "$HERE/.." && pwd)
VERSION=${VERSION:-$(date -u +%Y.%m.%d)}
OUT=${OUT:-$REPO/image-out}
trap unmount_image EXIT

fetch_base
rm -f "$WORK/base.img.xz"           # disk space on the runner is tight
grow_image 3G
mount_image rw
df -h "$MNT"

echo "== copy the project in (tracked files only)"
rm -rf "$MNT/opt/stratoscan-src"
mkdir -p "$MNT/opt/stratoscan-src"
git -C "$REPO" archive HEAD | tar -x -C "$MNT/opt/stratoscan-src"
COMMIT=$(git -C "$REPO" rev-parse --short HEAD)
# Which release this image starts from (security review 2026-11-03, SR-28):
# the commit's count is a release's serial (scripts/release.sh), and the
# installer records it as the floor under the updates the unit will take.
# The copy above carries no history, so the count goes in beside it. Only
# from a whole history: a shallow checkout's count is not a serial, and then
# nothing is written and the updater's built-in floor applies.
BUILD_SERIAL=""
if [ "$(git -C "$REPO" rev-parse --is-shallow-repository)" = "false" ]; then
  BUILD_SERIAL=$(git -C "$REPO" rev-list --count HEAD)
  echo "$BUILD_SERIAL" > "$MNT/opt/stratoscan-src/.build-serial"
else
  echo "  NOTE: a shallow checkout: this image records no release floor (build from a full clone to set one)"
fi
# The installer's other pins, for the manifest and the checks below.
READSB_TAG=$(sed -n 's/^READSB_TAG=\([^ ]*\).*/\1/p' "$REPO/deploy/install-setup-server.sh")
READSB_COMMIT=$(sed -n 's/^READSB_COMMIT=\([^ ]*\).*/\1/p' "$REPO/deploy/install-setup-server.sh")
TAR1090_DB_COMMIT=$(sed -n 's/^TAR1090_DB_COMMIT=\([^ ]*\).*/\1/p' "$REPO/deploy/install-setup-server.sh")
# The release signing key an image may carry, by fingerprint (SR-32). Written
# out here as well as in the installer, on purpose: an image with another
# key in its trust root takes two edits, not one, and this build has no
# ROTATE_SIGNERS to wave it through.
SIGNERS_FINGERPRINT=SHA256:vB/YWmvqG4/GBjpqYUqIf7/VRora4r7TBoMc33oVHb8
# The 978 MHz decoder's version, as the installer pins it (GPL: its source
# goes with the image, below).
DUMP978_TAG=$(sed -n 's/^DUMP978_TAG=\([^ ]*\).*/\1/p' "$REPO/deploy/install-setup-server.sh")
DUMP978_COMMIT=$(sed -n 's/^DUMP978_COMMIT=\([^ ]*\).*/\1/p' "$REPO/deploy/install-setup-server.sh")

chroot_prepare
# Keep the image's own resolv.conf (a NetworkManager symlink) to put back.
RESOLV_BACKUP="$WORK/resolv.conf.orig"
cp -a "$MNT/etc/resolv.conf" "$RESOLV_BACKUP" 2>/dev/null || true
cp --remove-destination /etc/resolv.conf "$MNT/etc/resolv.conf"

chroot "$MNT" /bin/sh /opt/stratoscan-src/image/customize.sh

echo "== checks: the image must be a working unit with no per-unit secrets"
fail=0
# -L too: enablement links point at absolute paths, which resolve against the
# BUILD machine's filesystem from out here, not the image's.
must()    { [ -e "$MNT$1" ] || [ -L "$MNT$1" ] || { echo "  MISSING $1"; fail=1; }; }
mustnot() { [ ! -e "$MNT$1" ] || { echo "  MUST NOT SHIP $1"; fail=1; }; }
for f in /usr/bin/readsb /usr/local/share/tar1090/git/.stratoscan-commit /var/www/html/index.html \
         /opt/stratoscan/ota.py /opt/stratoscan/allowed_signers /opt/stratoscan/tts/venv/bin/python \
         /usr/local/bin/dump978-fa /usr/bin/rtl_sdr /opt/stratoscan/radio-select.py \
         /etc/systemd/system/readsb.service.d/stratoscan-radio.conf \
         /etc/systemd/system/multi-user.target.wants/stratoscan-uat.service \
         /etc/systemd/system/multi-user.target.wants/stratoscan-radio.service \
         /etc/systemd/system/multi-user.target.wants/stratoscan-firstboot.service \
         /etc/systemd/system/multi-user.target.wants/stratoscan-events.service \
         /home/stratoscan/.config/systemd/user/default.target.wants/stratoscan-kiosk.service \
         /usr/bin/tailscale \
         /opt/stratoscan/os-update.py /opt/stratoscan/os-packages.json /usr/bin/dpkg-repack \
         /etc/systemd/system/timers.target.wants/stratoscan-os-update.timer \
         /etc/systemd/system/timers.target.wants/stratoscan-os-restart.timer \
         /etc/systemd/system/multi-user.target.wants/stratoscan-os-confirm.service \
         /var/www/html/vendor/maplibre-gl.mjs /var/www/html/vendor/maplibre-gl-worker.mjs \
         /opt/stratoscan/boot-cover.py /opt/stratoscan/controls.py \
         /etc/systemd/system/stratoscan-controls.service \
         /etc/cloud/cloud-init.disabled /etc/polkit-1/rules.d/05-stratoscan.rules \
         /etc/stratoscan/filter.nft /etc/systemd/system/stratoscan-filter.service \
         /etc/systemd/system/multi-user.target.wants/stratoscan-filter.service \
         /usr/local/share/tar1090/git/.stratoscan-db-commit; do must "$f"; done
for f in /var/lib/stratoscan-relay/unit.key /var/lib/stratoscan-setup/setup.json \
         /var/lib/stratoscan-setup/hotspot-psk /var/lib/tailscale/tailscaled.state \
         /var/lib/stratoscan-setupd/hotspot-psk /var/lib/stratoscan-setupd/readsb.default.orig \
         /var/lib/stratoscan-relay/events.json /var/lib/stratoscan-relay/heartbeat.json \
         /etc/xdg/autostart/piwiz.desktop /etc/sudoers.d/010_wiz-nopasswd \
         /etc/stratoscan/tls/unit.pem \
         /etc/stratoscan/controls.json /var/lib/stratoscan-ota/os-update.json \
         /etc/ssh/ssh_host_ed25519_key /etc/ssh/ssh_host_ecdsa_key /etc/ssh/ssh_host_rsa_key; do mustnot "$f"; done
# Added since the first image (2026-09-28), each checked as it ships:
# quiet boot (no Raspberry Pi splash, text or desktop; #72), the unused OS
# services off, speech held to one core (#53), and no control arc unless
# the unit has one.
grep -q "console=tty3" "$MNT/boot/firmware/cmdline.txt" || { echo "  quiet boot: cmdline.txt not quiet"; fail=1; }
# The base's "resize" makes a new card grow its root filesystem to the whole
# SD card on first boot; quiet boot rewrites the same line and must keep it.
grep -qw "resize" "$MNT/boot/firmware/cmdline.txt" || { echo "  cmdline.txt lost 'resize': a new card would never grow"; fail=1; }
grep -q "boot-cover.py" "$MNT/etc/xdg/labwc/autostart" || { echo "  quiet boot: the start-up cover is not in the session"; fail=1; }
grep -q "^dtoverlay=disable-bt" "$MNT/boot/firmware/config.txt" || { echo "  Bluetooth radio not off"; fail=1; }
for u in bluetooth.service cups.service udisks2.service wayvnc-control.service packagekit.service; do
  [ "$(readlink "$MNT/etc/systemd/system/$u")" = "/dev/null" ] || { echo "  $u is not masked"; fail=1; }
done
grep -q "^AllowedCPUs=" "$MNT/etc/systemd/system/stratoscan-tts.service" || { echo "  speech is not held to one core"; fail=1; }
# lighttpd's own unit, Debian's without the wait for the network (#93).
{ grep -q "^ExecStart=" "$MNT/etc/systemd/system/lighttpd.service" && ! grep -q "network-online" "$MNT/etc/systemd/system/lighttpd.service"; } \
  || { echo "  lighttpd waits for the network"; fail=1; }
# The setup certificate is made per unit on first boot (tls-cert.sh), never in
# the image: one baked in would be every unit's, and its key public.
# Every new unit is in rollout ring 3, everyone, until its owner's install
# says otherwise (RING=, MANAGED=1 for a gift unit's ring 1).
[ "$(cat "$MNT/etc/stratoscan/ring" 2>/dev/null)" = "3" ] || { echo "  ring file missing or not 3"; fail=1; }
grep -rq "^autologin-user=stratoscan" "$MNT/etc/lightdm/" || { echo "  autologin is not the kiosk user"; fail=1; }
# The connection filter (SR-10; IPv6 only, IPv4 is not filtered): there,
# enabled (above), and the file the unit loads is the one in this tree.
cmp -s "$REPO/deploy/stratoscan-filter.nft" "$MNT/etc/stratoscan/filter.nft" || { echo "  the connection filter is not this tree's"; fail=1; }
grep -q "^ExecStart=/usr/sbin/nft -f /etc/stratoscan/filter.nft" "$MNT/etc/systemd/system/stratoscan-filter.service" \
  || { echo "  the connection filter's unit does not load it"; fail=1; }
# And nft itself takes it, and the 443 redirect's file with it (2026-11-15).
# No test in the tree runs nft, and a file it refuses would only be found on
# a unit: the filter would stay off there, and the https one fails that
# unit's install. This is the image's own nft, the version a unit runs,
# asked only to check (-c), inside a network namespace of its own (unshare
# -n; the build runs as root), so the build machine's rules are neither read
# nor changed.
for f in filter https; do
  unshare -n chroot "$MNT" /usr/sbin/nft -c -f "/etc/stratoscan/$f.nft" \
    || { echo "  nft does not accept /etc/stratoscan/$f.nft"; fail=1; }
done
# The trust root (SR-32): every key in the image's allowed_signers is the
# pinned one, by the fingerprint `ssh-keygen -lf` prints.
python3 - "$MNT/opt/stratoscan/allowed_signers" > "$WORK/signers.fingerprints" <<'PY' || echo unreadable > "$WORK/signers.fingerprints"
import base64, hashlib, sys
fps = set()
for line in open(sys.argv[1]):
    parts = line.split()
    if not parts or parts[0].startswith("#"):
        continue
    at = next((i for i, t in enumerate(parts) if t.startswith(("ssh-", "ecdsa-", "sk-"))), None)
    try:
        blob = base64.b64decode(parts[at + 1], validate=True)
    except (TypeError, IndexError, ValueError):
        fps.add("not-a-key")
        continue
    fps.add("SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("="))
print(" ".join(sorted(fps)))
PY
SIGNERS_IN_IMAGE=$(cat "$WORK/signers.fingerprints")
[ "$SIGNERS_IN_IMAGE" = "$SIGNERS_FINGERPRINT" ] \
  || { echo "  the image's trust root is not the pinned signing key alone"; fail=1; }
# The upstream pins (SR-35): what was built is the commit the installer names.
[ -n "$READSB_COMMIT" ] && [ "$(git -C "$MNT/usr/local/share/adsb-wiki/readsb-install/git" rev-parse HEAD 2>/dev/null)" = "$READSB_COMMIT" ] \
  || { echo "  readsb is not the pinned commit"; fail=1; }
[ -n "$TAR1090_DB_COMMIT" ] && [ "$(git -C "$MNT/usr/local/share/tar1090/git-db" rev-parse HEAD 2>/dev/null)" = "$TAR1090_DB_COMMIT" ] \
  || { echo "  the aircraft database is not the pinned commit"; fail=1; }
# The release floor (SR-28): when this build could count its commits, the
# image's record says so.
if [ -n "$BUILD_SERIAL" ]; then
  grep -q "\"serial\": $BUILD_SERIAL[,}]" "$MNT/var/lib/stratoscan-ota/installed.json" 2>/dev/null \
    || { echo "  the release floor (serial $BUILD_SERIAL) is not recorded"; fail=1; }
fi
[ "$fail" = 0 ] || { echo "IMAGE CHECKS FAILED"; exit 1; }
echo "  all checks passed"

echo "== manifest and Corresponding Source"
mkdir -p "$OUT/src"
READSB_GIT=$MNT/usr/local/share/adsb-wiki/readsb-install/git
TAR_GIT=$MNT/usr/local/share/tar1090/git
{
  echo "StratoScan factory image $VERSION (project commit $COMMIT, release floor ${BUILD_SERIAL:-not recorded})"
  echo "Base: $(basename "$BASE_URL")  sha256 $BASE_SHA256"
  echo "readsb: $(git -C "$READSB_GIT" describe --tags --always 2>/dev/null || echo '?') ($(git -C "$READSB_GIT" rev-parse HEAD 2>/dev/null || echo '?'); pinned $READSB_TAG $READSB_COMMIT)"
  echo "tar1090: $(cat "$TAR_GIT/.stratoscan-commit")"
  echo "tar1090-db: $(cat "$TAR_GIT/.stratoscan-db-commit")"
  echo "release signing key: $SIGNERS_FINGERPRINT"
  echo "dump978: $DUMP978_TAG ($DUMP978_COMMIT)"
  echo "piper-tts: $(chroot "$MNT" /opt/stratoscan/tts/venv/bin/pip show piper-tts | awk '/^Version/{print $2}')"
  echo
  echo "Installed packages:"
  chroot "$MNT" dpkg-query -W -f '${Package} ${Version}\n'
} > "$OUT/MANIFEST.txt"
( cd "$READSB_GIT" && git archive --prefix=readsb/ -o "$OUT/src/readsb-source.tar.gz" HEAD ) \
  || tar -C "$(dirname "$READSB_GIT")" -czf "$OUT/src/readsb-source.tar.gz" git
tar -C "$TAR_GIT/.." --exclude=.git -czf "$OUT/src/tar1090-source.tar.gz" git
PIPER_V=$(chroot "$MNT" /opt/stratoscan/tts/venv/bin/pip show piper-tts | awk '/^Version/{print $2}')
PIPER_SDIST=$(curl -fsSL "https://pypi.org/pypi/piper-tts/$PIPER_V/json" \
  | python3 -c "import json,sys; print(next(u['url'] for u in json.load(sys.stdin)['urls'] if u['packagetype']=='sdist'))")
curl -fsSL -o "$OUT/src/$(basename "$PIPER_SDIST")" "$PIPER_SDIST"
# By commit, so the source offered is exactly what was built (a tag can move).
curl -fsSL -o "$OUT/src/dump978-source.tar.gz" "https://github.com/flightaware/dump978/archive/$DUMP978_COMMIT.tar.gz"
cp "$HERE/SOURCES.md" "$OUT/SOURCES.md"

echo "== restore and seal"
rm -f "$MNT/etc/resolv.conf"
[ -e "$RESOLV_BACKUP" ] || [ -L "$RESOLV_BACKUP" ] && cp -a "$RESOLV_BACKUP" "$MNT/etc/resolv.conf"
# The first boot of every unit must generate its own machine id.
: > "$MNT/etc/machine-id"
unmount_image
trap - EXIT

echo "== compress"
command -v zerofree >/dev/null && { LOOP=$(losetup --find --show --partscan "$IMG"); zerofree "${LOOP}p2" || true; losetup -d "$LOOP"; }
NAME="stratoscan-$VERSION.img"
mv "$IMG" "$OUT/$NAME"
xz -T0 -6 "$OUT/$NAME"
( cd "$OUT" && sha256sum "$NAME.xz" > "$NAME.xz.sha256" )
ls -la "$OUT" "$OUT/src"
