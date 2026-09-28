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
LOG=/var/log/flightradar-firstboot.log
{
  echo "== Radome first boot: $(date -Is)"
  # Raspberry Pi OS keeps WiFi blocked until a country is set, which would
  # stop the setup hotspot from ever appearing. Default to US; the owner
  # sets the real one in setup (setupd's set_wifi_country).
  raspi-config nonint do_wifi_country US || rfkill unblock wifi || true
  cd /opt/flightradar-src
  KIOSK_USER=flightradar sh deploy/install-setup-server.sh
  touch /var/lib/flightradar-firstboot.done
  systemctl disable flightradar-firstboot.service
  echo "== done: $(date -Is)"
} >>"$LOG" 2>&1
