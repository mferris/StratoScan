# Shared by image/inspect.sh and image/build.sh. Runs as root on an arm64
# Linux machine (GitHub's ubuntu-24.04-arm runners), so the image's own
# binaries run natively in a chroot -- no emulation.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/base.env"
WORK=${WORK:-/tmp/frimage}
IMG="$WORK/base.img"
MNT="$WORK/root"
LOOP=""

fetch_base() {
  mkdir -p "$WORK"
  if [ ! -f "$WORK/base.img.xz" ]; then
    curl -fsSL --retry 3 -o "$WORK/base.img.xz" "$BASE_URL"
  fi
  echo "$BASE_SHA256  $WORK/base.img.xz" | sha256sum -c - >/dev/null \
    || { echo "base image checksum mismatch; refusing to build"; exit 1; }
  echo "base image verified: $(basename "$BASE_URL")"
  rm -f "$IMG"
  xz -dkc "$WORK/base.img.xz" > "$IMG"
}

# grow_image BYTES: make room for what the build adds (readsb, the voice,
# Tailscale...). The root partition is the last one; grow it to the end.
grow_image() {
  truncate -s "+$1" "$IMG"
  parted -s "$IMG" resizepart 2 100%
}

mount_image() {
  LOOP=$(losetup --find --show --partscan "$IMG")
  if [ "${1:-rw}" = "rw" ]; then
    e2fsck -pf "${LOOP}p2" >/dev/null || true
    resize2fs "${LOOP}p2" >/dev/null
  fi
  mkdir -p "$MNT"
  mount "${LOOP}p2" "$MNT"
  mount "${LOOP}p1" "$MNT/boot/firmware"
}

chroot_prepare() {
  for d in dev dev/pts proc sys run; do mount --bind "/$d" "$MNT/$d"; done
  # Services must not start inside the build: this makes every invoke-rc.d /
  # package postinst "start" a no-op.
  printf '#!/bin/sh\nexit 101\n' > "$MNT/usr/sbin/policy-rc.d"
  chmod 0755 "$MNT/usr/sbin/policy-rc.d"
}

unmount_image() {
  rm -f "$MNT/usr/sbin/policy-rc.d" 2>/dev/null || true
  for d in run sys proc dev/pts dev; do umount "$MNT/$d" 2>/dev/null || true; done
  umount "$MNT/boot/firmware" 2>/dev/null || true
  umount "$MNT" 2>/dev/null || true
  [ -n "$LOOP" ] && losetup -d "$LOOP" 2>/dev/null || true
}
