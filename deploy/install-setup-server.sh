#!/bin/sh
# Installs the FlightRadar setup server. Idempotent; safe to re-run.
#
# Run from the repo root on the device:
#   sudo sh deploy/install-setup-server.sh
set -e

echo "== creating the unprivileged service account =="
if ! getent group frsetup >/dev/null; then groupadd --system frsetup; fi
if ! getent passwd frsetup >/dev/null; then
  useradd --system --gid frsetup --no-create-home --shell /usr/sbin/nologin frsetup
fi

echo "== installing files =="
install -d -m 0755 /opt/flightradar
install -m 0755 deploy/setupd.py           /opt/flightradar/setupd.py
install -m 0755 deploy/setup-server.py     /opt/flightradar/setup-server.py
install -m 0644 deploy/setup-ui.html       /opt/flightradar/setup-ui.html
install -m 0644 deploy/airports.json       /opt/flightradar/airports.json
install -m 0644 deploy/funnel-gateway.py   /opt/flightradar/funnel-gateway.py
install -m 0755 deploy/offline-map.py      /opt/flightradar/offline-map.py
install -m 0755 deploy/heartbeat.py        /opt/flightradar/heartbeat.py
install -m 0755 deploy/notable-db.py       /opt/flightradar/notable-db.py

install -m 0644 deploy/flightradar-setupd.service /etc/systemd/system/
install -m 0644 deploy/flightradar-setup.service  /etc/systemd/system/

# The updater. These were installed by hand on the first unit and therefore
# on no others -- the RDU device ran for weeks with no update timer at all,
# which nobody noticed because checking is silent when it is not happening.
# A unit that has been given away cannot be updated by hand, so this is the
# part that must not be left to memory.
install -m 0755 deploy/ota.py       /opt/flightradar/ota.py
install -m 0755 deploy/ota-auto.sh  /opt/flightradar/ota-auto.sh
install -m 0644 deploy/flightradar-ota-check.service /etc/systemd/system/
install -m 0644 deploy/flightradar-ota-check.timer   /etc/systemd/system/
install -m 0644 deploy/flightradar-ota-auto.service  /etc/systemd/system/
install -m 0644 deploy/flightradar-ota-auto.timer    /etc/systemd/system/

# The trust root. Must already be on the device before it ships: fetching the
# key over the same channel as the update would make the signature pointless.
# NOT installable by an update, deliberately -- see deploy/allowed_signers.
install -m 0644 deploy/allowed_signers /opt/flightradar/allowed_signers
install -m 0644 deploy/98-flightradar-setup.conf  /etc/lighttpd/conf-available/
ln -sf /etc/lighttpd/conf-available/98-flightradar-setup.conf \
       /etc/lighttpd/conf-enabled/98-flightradar-setup.conf

echo "== verifying lighttpd config before touching the running server =="
lighttpd -tt -f /etc/lighttpd/lighttpd.conf

echo "== enabling =="
systemctl daemon-reload
systemctl enable --now flightradar-setupd.service
systemctl enable --now flightradar-setup.service
systemctl enable --now flightradar-ota-check.timer
systemctl enable --now flightradar-ota-auto.timer
systemctl restart flightradar-funnel-gateway.service
systemctl reload lighttpd

echo "== verifying /setup is refused on the public tunnel =="
fail=0
for p in /setup /./setup /x/../setup /%73etup /wake /%77ake; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --path-as-is -X POST \
         -H 'Content-Length: 0' "http://127.0.0.1:8085$p")
  [ "$code" = "404" ] || { echo "  FAIL: $p returned $code via the public gateway"; fail=1; }
done
[ "$fail" = "0" ] && echo "  all privileged paths refused publicly"
[ "$fail" = "0" ] || { echo "REFUSING TO FINISH: the public filter is not working"; exit 1; }

echo
echo "Setup page:  http://$(hostname -I | awk '{print $1}')/setup"
echo "Claim code:  shown below (also in /run/flightradar/claim-code)"
cat /run/flightradar/claim-code 2>/dev/null || echo "  (not generated yet)"

echo
echo "== installing the network watchdog (rollback + hotspot fallback) =="
install -m 0755 deploy/net-watchdog.py /opt/flightradar/net-watchdog.py
install -m 0644 deploy/flightradar-netwatchdog.service /etc/systemd/system/
install -m 0644 deploy/flightradar-netwatchdog.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now flightradar-netwatchdog.timer
echo "  watchdog timer: $(systemctl is-active flightradar-netwatchdog.timer)"

echo
echo "== installing the captive portal (so phones stop using cellular) =="
install -m 0644 deploy/99-flightradar-captive.conf /etc/lighttpd/conf-available/
ln -sf /etc/lighttpd/conf-available/99-flightradar-captive.conf \
       /etc/lighttpd/conf-enabled/99-flightradar-captive.conf
install -d -m 0755 /etc/NetworkManager/dnsmasq-shared.d
install -m 0644 deploy/flightradar-captive-dns.conf \
        /etc/NetworkManager/dnsmasq-shared.d/flightradar-captive.conf
lighttpd -tt -f /etc/lighttpd/lighttpd.conf
systemctl reload lighttpd
echo "  captive portal installed"

# Everything below is image-level: ota.py deliberately cannot install system
# config or unit files, so a unit only ever gets these from this script. That
# makes this the last chance before a unit leaves the house.
echo
echo "== long-life hardening (security updates, panic reboot) =="
# The apt timer is enabled on a stock image but does nothing without this
# package -- the RDU unit went unpatched for months behind an "enabled" timer.
# python3-cryptography signs the opt-in health reports (heartbeat.py). It
# ships with Raspberry Pi OS; listed so a minimal image gets it too.
DEBIAN_FRONTEND=noninteractive apt-get install -y -q unattended-upgrades python3-cryptography >/dev/null
install -m 0644 deploy/20auto-upgrades                  /etc/apt/apt.conf.d/20auto-upgrades
install -m 0644 deploy/52flightradar-unattended-upgrades /etc/apt/apt.conf.d/52flightradar-unattended-upgrades
install -m 0644 deploy/90-flightradar-sysctl.conf        /etc/sysctl.d/90-flightradar-sysctl.conf
sysctl -q -p /etc/sysctl.d/90-flightradar-sysctl.conf
# Checked cheaply, not with `unattended-upgrade --dry-run`: on a Pi that
# simulates every pending upgrade one at a time and ran past 40 minutes on the
# RDU unit -- long enough that anyone would Ctrl-C a "hung" installer and
# never reach the kiosk units and offline map below. `apt-config dump` fails
# on a syntax error in any apt.conf.d file, and the grep proves ours is read.
if dpkg -s unattended-upgrades >/dev/null 2>&1 \
   && apt-config dump 2>/dev/null | grep -q 'Unattended-Upgrade::Package-Blacklist:: "chromium"' \
   && apt-config dump 2>/dev/null | grep -q 'APT::Periodic::Unattended-Upgrade "1"'; then
  echo "  security updates: configured (chromium, kernel and firmware held)"
else
  echo "  FAIL: unattended-upgrades is not installed or its config did not load"; exit 1
fi
echo "  kernel.panic=$(cat /proc/sys/kernel/panic)"

# Real-time clock battery. Without one the clock is lost at every power cut
# and stays wrong until NTP answers -- or indefinitely, on a network that
# blocks it. The Pi 5 can trickle-charge a RECHARGEABLE cell (ML-2020), but
# charging must never be enabled for an ordinary CR2032, which is not
# rechargeable and can leak or burst. So it is never guessed: run the
# installer with RTC_RECHARGEABLE=1 only when an ML-2020 is actually fitted.
RTC_V=$(cat /sys/class/rtc/rtc0/battery_voltage 2>/dev/null || echo 0)
echo "  RTC battery: $((RTC_V / 1000)) mV ($([ "$RTC_V" -gt 1000000 ] && echo fitted || echo none fitted))"
if [ "${RTC_RECHARGEABLE:-0}" = "1" ]; then
  CFG=/boot/firmware/config.txt
  if ! grep -q '^dtparam=rtc_bbat_vchg=' "$CFG"; then
    printf '\n# FlightRadar: trickle-charge the rechargeable ML-2020 RTC cell\ndtparam=rtc_bbat_vchg=3000000\n' >> "$CFG"
    echo "  RTC charging enabled (takes effect after a reboot)"
  else
    echo "  RTC charging already enabled"
  fi
fi

# The kiosk's own units run under the desktop user's systemd, because they
# need its Wayland session. Installed from here so a new unit gets the same
# versions as the repo rather than whatever was copied by hand last time.
KIOSK_USER="${SUDO_USER:-}"
if [ -n "$KIOSK_USER" ] && [ "$KIOSK_USER" != "root" ]; then
  echo
  echo "== installing the kiosk user units for $KIOSK_USER =="
  KHOME=$(getent passwd "$KIOSK_USER" | cut -d: -f6)
  KUID=$(id -u "$KIOSK_USER")
  UDIR="$KHOME/.config/systemd/user"
  install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$UDIR"
  for u in flightradar-kiosk.service flightradar-kiosk-restart.service \
           flightradar-kiosk-restart.timer flightradar-shmguard.service \
           flightradar-shmguard.timer flightradar-screensaver.service \
           flightradar-wake.service; do
    install -m 0644 -o "$KIOSK_USER" -g "$KIOSK_USER" "deploy/$u" "$UDIR/$u"
  done
  install -m 0755 deploy/shm-guard.sh     /opt/flightradar/shm-guard.sh
  install -m 0755 deploy/wake-listener.py /opt/flightradar/wake-listener.py
  runuser -u "$KIOSK_USER" -- env XDG_RUNTIME_DIR="/run/user/$KUID" \
    systemctl --user daemon-reload \
    && echo "  user units installed; they take effect on the next kiosk restart" \
    || echo "  user units copied; log in as $KIOSK_USER and run: systemctl --user daemon-reload"
else
  echo "  (run via sudo from the kiosk user's account to also install its user units)"
fi

echo
echo "== offline fallback map =="
# Built for the receiver's current location if it has one; otherwise setupd
# builds it when the location is set, and net-watchdog retries any failure.
python3 /opt/flightradar/offline-map.py ensure \
  && { [ -f /var/www/html/offline-map/meta.json ] \
         && echo "  built: $(cat /var/www/html/offline-map/meta.json)" \
         || echo "  no location yet; it will be built when one is set"; } \
  || echo "  build failed (no internet?); net-watchdog will retry"

echo
echo "== notable-aircraft list (plane-alert-db, ODbL) =="
python3 /opt/flightradar/notable-db.py ensure \
  && echo "  ready" || echo "  fetch failed (no internet?); net-watchdog will retry"

echo
echo "== spoken alerts (Piper text-to-speech, offline) =="
# Piper (GPL-3.0-or-later) runs as its own program in its own virtualenv, and
# is installed from PyPI here rather than shipped in this repository. The
# voice is LJSpeech, trained on a public-domain dataset -- many Piper voices
# are not licensed for redistribution or commercial use, so it is pinned.
PIPER_VERSION=1.8.0
TTS=/opt/flightradar/tts
VOICE=en_US-ljspeech-medium
install -d -m 0755 "$TTS" "$TTS/voices"
[ -x "$TTS/venv/bin/python" ] || python3 -m venv "$TTS/venv"
"$TTS/venv/bin/pip" install -q "piper-tts==$PIPER_VERSION"
[ -f "$TTS/voices/$VOICE.onnx" ] || \
  "$TTS/venv/bin/python" -m piper.download_voices "$VOICE" --data-dir "$TTS/voices"
chmod -R a+rX "$TTS"
install -m 0755 deploy/tts-service.py /opt/flightradar/tts-service.py
install -m 0644 deploy/flightradar-tts.service /etc/systemd/system/
install -m 0644 deploy/97-flightradar-tts.conf /etc/lighttpd/conf-available/
ln -sf /etc/lighttpd/conf-available/97-flightradar-tts.conf \
       /etc/lighttpd/conf-enabled/97-flightradar-tts.conf
lighttpd -tt -f /etc/lighttpd/lighttpd.conf
systemctl daemon-reload
systemctl enable --now flightradar-tts.service
systemctl reload lighttpd
systemctl restart flightradar-funnel-gateway.service
echo "  tts: $(systemctl is-active flightradar-tts.service)"
