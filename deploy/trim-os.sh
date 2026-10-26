#!/bin/sh
# Turns off the parts of Raspberry Pi OS a radar never uses (2026-10-13).
#
# Raspberry Pi OS is a desktop system: it starts printing, Bluetooth, a VNC
# remote-desktop helper, USB automounting, a battery monitor, NFS and
# cloud-init on every boot. A radar uses none of them. Each is small and
# mostly idle (measured on RDU: everything outside Chromium, readsb and the
# StratoScan services under 1% of a core), so this is not where the power
# goes; it is fewer things to start, patch, listen and go wrong, on a device
# in someone else's house.
#
# rpcbind too (2026-10-26, #89): nfs-common brings it, and it listened on
# port 111 on every interface, an open service on the home network for NFS,
# which nothing on a radar mounts. The packages stay (nfs-common depends on
# it); its socket is listed before the service, so stopping the service
# doesn't leave the socket to start it again.
#
# Kept on purpose: avahi (the app finds a radar by its .local name on the
# LAN), pipewire and wireplumber (the speakers are the screen's HDMI audio),
# the desktop portals (Chromium calls them), cron, the consoles (a way in
# with a keyboard when the network is gone), and everything StratoScan.
#
# Idempotent; safe to re-run. Undo a unit with `systemctl unmask NAME` and
# `systemctl enable --now NAME`; cloud-init by removing
# /etc/cloud/cloud-init.disabled; Bluetooth by removing the dtoverlay line.
set -eu

ROOT="${STRATOSCAN_ROOT:-}"
LIVE="${STRATOSCAN_LIVE:-1}"
CONFIG_TXT="$ROOT/boot/firmware/config.txt"

# System units: stopped (on a running unit), disabled, and masked so a
# package update or a D-Bus request cannot start them again.
SYSTEM_UNITS="bluetooth.service cups.service cups.socket cups-browsed.service
wayvnc-control.service wayvnc.service udisks2.service upower.service
nfs-blkmap.service rpcbind.socket rpcbind.service ModemManager.service"
# The kiosk user's session: Bluetooth media control and GNOME's virtual
# filesystems.
USER_UNITS="mpris-proxy.service gvfs-daemon.service"

for u in $SYSTEM_UNITS; do
  if [ -n "$ROOT" ]; then
    systemctl --root="$ROOT" mask "$u" >/dev/null 2>&1 || true
  else
    if [ "$LIVE" = "1" ]; then systemctl stop "$u" >/dev/null 2>&1 || true; fi
    systemctl disable "$u" >/dev/null 2>&1 || true
    systemctl mask "$u" >/dev/null 2>&1 || true
  fi
done
for u in $USER_UNITS; do
  if [ -n "$ROOT" ]; then
    systemctl --root="$ROOT" --global mask "$u" >/dev/null 2>&1 || true
  else
    systemctl --global mask "$u" >/dev/null 2>&1 || true
  fi
done

# cloud-init configured the card once, from Raspberry Pi Imager; after that
# it only adds about 1.5 s to every boot.
install -d -m 0755 "$ROOT/etc/cloud"
: > "$ROOT/etc/cloud/cloud-init.disabled"

# The Bluetooth radio itself, from the next boot.
if [ -f "$CONFIG_TXT" ] && ! grep -q '^dtoverlay=disable-bt' "$CONFIG_TXT"; then
  printf '\n# StratoScan: no Bluetooth (deploy/trim-os.sh)\n[all]\ndtoverlay=disable-bt\n' >> "$CONFIG_TXT"
fi

echo "  unused OS services off: printing, Bluetooth, VNC helper, USB automount, battery monitor, NFS, cloud-init"
