#!/bin/sh
# First boot of a unit flashed from the factory image.
#
# The image build ran the installer in chroot mode: everything installed and
# enabled, nothing started. This finishes it live -- reloads, starts, and the
# public-path refusal check that can only run on a real network stack. Works
# offline: every package, the voice and readsb/tar1090 are already in the
# image; anything that needs the internet (the notable list, the offline map)
# is retried later by net-watchdog. Runs once, then disables itself.
set -e
# The log is root's alone (security review 2026-11-03, SR-55): the
# installer's output went into it under the default umask, readable by every
# user, and with it the claim code. A new log is made under umask 077, and
# chmod closes one left by an earlier attempt. Only the log: the installer
# runs under the usual 022, as it does by hand, or files it makes without a
# mode would be root's alone on factory units only.
LOG=/var/log/stratoscan-firstboot.log
( umask 077; : >>"$LOG" )
chmod 0600 "$LOG"
umask 022
{
  echo "== StratoScan first boot: $(date -Is)"
  # Raspberry Pi OS keeps WiFi blocked until a country is set, which would
  # stop the setup hotspot from ever appearing. Default to US; the owner
  # sets the real one in setup (setupd's set_wifi_country).
  raspi-config nonint do_wifi_country US || rfkill unblock wifi || true
  cd /opt/stratoscan-src
  KIOSK_USER=stratoscan sh deploy/install-setup-server.sh
  touch /var/lib/stratoscan-firstboot.done
  systemctl disable stratoscan-firstboot.service
  echo "== done: $(date -Is)"
} >>"$LOG" 2>&1
