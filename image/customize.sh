#!/bin/sh
# Runs INSIDE the image (chroot). Turns stock Raspberry Pi OS into a
# StratoScan unit that boots straight into the kiosk and the setup hotspot.
# Facts about the base come from image/inspect.sh, not assumptions:
#   - uid 1000 is a placeholder user "pi" (login shell nologin);
#   - lightdm auto-logs-in "rpi-first-boot-wizard", which runs piwiz
#     (/etc/xdg/autostart/piwiz.desktop) with passwordless sudo
#     (/etc/sudoers.d/010_wiz-nopasswd);
#   - SSH is not enabled (and stays that way on a gifted unit).
set -eu
KIOSK_USER=stratoscan

echo "== kiosk user: pi -> $KIOSK_USER (password locked; it only ever auto-logs-in)"
if id pi >/dev/null 2>&1; then
  usermod -l "$KIOSK_USER" -d "/home/$KIOSK_USER" -m -s /bin/bash pi
  groupmod -n "$KIOSK_USER" pi
fi
passwd -l "$KIOSK_USER" >/dev/null

echo "== replace the first-boot wizard with the kiosk session"
rm -f /etc/xdg/autostart/piwiz.desktop /etc/sudoers.d/010_wiz-nopasswd
if id rpi-first-boot-wizard >/dev/null 2>&1; then userdel -r rpi-first-boot-wizard 2>/dev/null || userdel rpi-first-boot-wizard; fi
for f in /etc/lightdm/lightdm.conf /etc/lightdm/lightdm.conf.d/*.conf; do
  [ -f "$f" ] && sed -i -E "s/^autologin-user=.*/autologin-user=$KIOSK_USER/" "$f"
done
grep -rq "^autologin-user=$KIOSK_USER" /etc/lightdm/ || { echo "autologin not set"; exit 1; }
systemctl disable userconfig.service >/dev/null 2>&1 || true

echo "== hostname"
echo stratoscan > /etc/hostname
sed -i -E 's/^127\.0\.1\.1\s.*/127.0.1.1\tstratoscan/' /etc/hosts

echo "== StratoScan itself (installer, chroot mode)"
apt-get update -q >/dev/null
cd /opt/stratoscan-src
STRATOSCAN_CHROOT=1 KIOSK_USER="$KIOSK_USER" sh deploy/install-setup-server.sh

echo "== first boot finishes the job live"
install -m 0644 image/stratoscan-firstboot.service /etc/systemd/system/
systemctl enable stratoscan-firstboot.service >/dev/null

echo "== tidy"
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache
