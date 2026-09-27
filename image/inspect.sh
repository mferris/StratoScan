#!/bin/sh
# Report how the pinned base image handles its first boot, so the build can
# replace the setup wizard with the kiosk user instead of guessing.
. "$(dirname "$0")/lib.sh"
trap unmount_image EXIT
fetch_base
mount_image ro
echo "== users (uid >= 1000)"
awk -F: '$3 >= 1000 && $3 < 65000 {print $1, $3, $6, $7}' "$MNT/etc/passwd"
echo "== lightdm"
grep -rhE "^(autologin-user|autologin-session|user-session|greeter-session)" \
  "$MNT/etc/lightdm/lightdm.conf" "$MNT/etc/lightdm/lightdm.conf.d/" 2>/dev/null || true
echo "== autostart"
ls "$MNT/etc/xdg/autostart/"
echo "== first-boot related units"
ls "$MNT/etc/systemd/system/" "$MNT/lib/systemd/system/" 2>/dev/null \
  | grep -iE "userconf|firstboot|first-boot|piwiz|wizard|init_resize|regenerate|resize" || true
echo "== sudoers.d"
ls "$MNT/etc/sudoers.d/"
echo "== boot cmdline"
cat "$MNT/boot/firmware/cmdline.txt"
echo "== userconf tooling"
ls "$MNT/usr/lib/userconf-pi/" 2>/dev/null || echo "(none)"
echo "== ssh enabled?"
ls "$MNT/etc/systemd/system/multi-user.target.wants/" | grep -i ssh || echo "(ssh not enabled)"
echo "== os"
grep PRETTY "$MNT/etc/os-release"
echo "== free space"
df -h "$MNT"
