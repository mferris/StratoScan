#!/bin/sh
# Builds the StratoScan factory image. Run as root on arm64 Linux (GitHub's
# ubuntu-24.04-arm runners), from the repo root:  sudo sh image/build.sh
#
# Output in $OUT (default ./image-out):
#   stratoscan-<version>.img.xz (+ .sha256)   the image to flash
#   MANIFEST.txt                               pinned versions + every package
#   SOURCES.md                                 GPL source offer
#   src/*.tar.gz                               Corresponding Source for readsb,
#                                              tar1090 and Piper as built
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
         /usr/bin/tailscale; do must "$f"; done
for f in /var/lib/stratoscan-relay/unit.key /var/lib/stratoscan-setup/setup.json \
         /var/lib/stratoscan-setup/hotspot-psk /var/lib/tailscale/tailscaled.state \
         /var/lib/stratoscan-relay/events.json /var/lib/stratoscan-relay/heartbeat.json \
         /etc/xdg/autostart/piwiz.desktop /etc/sudoers.d/010_wiz-nopasswd \
         /etc/stratoscan/tls/unit.pem; do mustnot "$f"; done
# The setup certificate is made per unit on first boot (tls-cert.sh), never in
# the image: one baked in would be every unit's, and its key public.
# Every new unit is in rollout ring 3, everyone, until its owner's install
# says otherwise (RING=, MANAGED=1 for a gift unit's ring 1).
[ "$(cat "$MNT/etc/stratoscan/ring" 2>/dev/null)" = "3" ] || { echo "  ring file missing or not 3"; fail=1; }
grep -rq "^autologin-user=stratoscan" "$MNT/etc/lightdm/" || { echo "  autologin is not the kiosk user"; fail=1; }
[ "$fail" = 0 ] || { echo "IMAGE CHECKS FAILED"; exit 1; }
echo "  all checks passed"

echo "== manifest and Corresponding Source"
mkdir -p "$OUT/src"
READSB_GIT=$MNT/usr/local/share/adsb-wiki/readsb-install/git
TAR_GIT=$MNT/usr/local/share/tar1090/git
{
  echo "StratoScan factory image $VERSION (project commit $COMMIT)"
  echo "Base: $(basename "$BASE_URL")  sha256 $BASE_SHA256"
  echo "readsb: $(git -C "$READSB_GIT" describe --tags --always 2>/dev/null || echo '?') ($(git -C "$READSB_GIT" rev-parse HEAD 2>/dev/null || echo '?'))"
  echo "tar1090: $(cat "$TAR_GIT/.stratoscan-commit")"
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
