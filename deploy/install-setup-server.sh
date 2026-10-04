#!/bin/sh
# Provisions a StratoScan unit: everything it needs, on top of a stock
# Raspberry Pi OS with desktop (Trixie, arm64). Idempotent; safe to re-run --
# re-running it is how an existing unit picks up system-level changes that a
# signed update deliberately cannot make (unit files, system config).
#
# On a running unit, from the repo root, as the kiosk (desktop) user:
#   sudo sh deploy/install-setup-server.sh
# Inside the factory-image build (nothing is started; first boot re-runs it):
#   STRATOSCAN_CHROOT=1 KIOSK_USER=stratoscan sh deploy/install-setup-server.sh
#
# This used to install only the setup server and grew piece by piece; the
# first unit was partly assembled by hand, so a fresh unit built from it was
# missing the data stores, the public gateway's unit, six lighttpd configs,
# the page itself, readsb and tar1090. It now installs all of it.
set -e
cd "$(dirname "$0")/.."

CHROOT="${STRATOSCAN_CHROOT:-0}"
KIOSK_USER="${KIOSK_USER:-${SUDO_USER:-}}"
live() { [ "$CHROOT" != "1" ]; }
# Enable a system unit; on a running unit also (re)start it now.
enable_unit() {
  if live; then systemctl enable --now "$1" >/dev/null; else systemctl enable "$1" >/dev/null 2>&1 || true; fi
}
restart_unit() { if live; then systemctl restart "$1"; fi; }
lighttpd_conf() {
  install -m 0644 "deploy/$1" /etc/lighttpd/conf-available/
  ln -sf "/etc/lighttpd/conf-available/$1" "/etc/lighttpd/conf-enabled/$1"
}

# Units installed before the rename to StratoScan carry 'flightradar' names
# for their programs, services, data and config. Move them first, so what
# follows installs over the moved data rather than beside a stale copy.
# Nothing happens on a fresh install or a unit already moved.
KIOSK_USER="$KIOSK_USER" sh deploy/migrate-names.sh

# Pinned third-party installs. Changing a version is a deliberate edit here.
READSB_INSTALLER_COMMIT=f933123935631da855a7f8a16c0cb7ad4eedca48   # wiedehopf/adsb-scripts (MIT)
READSB_TAG=v3.16.17                                                 # wiedehopf/readsb (GPL-3.0-or-later)
TAR1090_COMMIT=383a9cb085860277c6c1972a4aca5be7e56bcc66             # wiedehopf/tar1090 (GPL-2.0-or-later)
PIPER_VERSION=1.8.0                                                 # piper-tts (GPL-3.0-or-later)
VOICE=en_US-ljspeech-medium                                         # public-domain dataset
export DEBIAN_FRONTEND=noninteractive

echo "== packages =="
apt-get install -y -q lighttpd git curl ca-certificates python3-venv python3-cryptography \
  python3-qrcode uhubctl unattended-upgrades javascript-common >/dev/null
echo "  ok"

echo "== receiver: readsb $READSB_TAG =="
if ! command -v readsb >/dev/null 2>&1; then
  curl -fsSL "https://raw.githubusercontent.com/wiedehopf/adsb-scripts/$READSB_INSTALLER_COMMIT/readsb-install.sh" \
    -o /tmp/readsb-install.sh
  bash /tmp/readsb-install.sh "tag=$READSB_TAG" no-tar1090 >/tmp/readsb-install.log 2>&1 \
    || { tail -30 /tmp/readsb-install.log; exit 1; }
  rm -f /tmp/readsb-install.sh
  echo "  installed"
else
  echo "  already installed: $(readsb --version 2>&1 | head -1)"
fi
# Options: raw feeds bound to this machine only (nothing on the LAN or the
# internet can connect to them), MLAT results accepted back on 30104, JSON
# positions coarsened. The location is NOT set here -- setup sets it -- and
# the readsb installer's placeholder (a point in west London) is removed, so
# a fresh unit never claims to be somewhere it isn't.
python3 - <<'PY'
import re, shlex
path = "/etc/default/readsb"
want = {
    "NET_OPTIONS": "--net --net-bind-address 127.0.0.1 --net-ri-port 30001 --net-ro-port 30002 "
                   "--net-sbs-port 30003 --net-bi-port 30004,30104 --net-bo-port 30005",
    "JSON_OPTIONS": "--json-location-accuracy 2 --range-outline-hours 24",
}
text = open(path).read()
out = []
for line in text.splitlines():
    m = re.match(r'^(\s*)([A-Z_]+)=(["\'])(.*)\3\s*$', line)
    if m and m.group(2) in want:
        line = f'{m.group(1)}{m.group(2)}="{want.pop(m.group(2))}"'
    elif m and m.group(2) == "DECODER_OPTIONS":
        toks = shlex.split(m.group(4))
        try:
            i, j = toks.index("--lat"), toks.index("--lon")
            if abs(float(toks[i + 1]) - 51.5283) < 1e-4 and abs(float(toks[j + 1]) + 0.38178) < 1e-4:
                toks = [t for k, t in enumerate(toks) if k not in (i, i + 1, j, j + 1)]
        except (ValueError, IndexError):
            pass
        line = f'{m.group(1)}DECODER_OPTIONS="{" ".join(toks)}"'
    out.append(line)
for k, v in want.items():
    out.append(f'{k}="{v}"')
new = "\n".join(out) + "\n"
if new != text:
    open(path, "w").write(new)
    print("  readsb options updated")
else:
    print("  readsb options already correct")
PY
install -m 0644 deploy/blacklist-rtlsdr.conf /etc/modprobe.d/blacklist-rtlsdr.conf

echo "== map history: tar1090 ${TAR1090_COMMIT%${TAR1090_COMMIT#???????}} =="
if [ "$(cat /usr/local/share/tar1090/git/.stratoscan-commit 2>/dev/null)" != "$TAR1090_COMMIT" ]; then
  rm -rf /tmp/tar1090-src
  git clone -q https://github.com/wiedehopf/tar1090.git /tmp/tar1090-src
  git -C /tmp/tar1090-src checkout -q "$TAR1090_COMMIT"
  git_source=/tmp/tar1090-src bash /tmp/tar1090-src/install.sh /run/readsb >/tmp/tar1090-install.log 2>&1 \
    || { tail -30 /tmp/tar1090-install.log; exit 1; }
  echo "$TAR1090_COMMIT" > /usr/local/share/tar1090/git/.stratoscan-commit
  rm -rf /tmp/tar1090-src
  echo "  installed"
else
  echo "  already at the pinned commit"
fi
# tar1090's installer also serves itself on its own port (8504), on every
# interface, with readsb's exact receiver position. Everything reaches
# tar1090 through port 80 (and the public page through the gateway), so this
# second door is closed (2026-10-04).
if [ -e /etc/lighttpd/conf-enabled/95-tar1090-otherport.conf ]; then
  rm -f /etc/lighttpd/conf-enabled/95-tar1090-otherport.conf
  echo "  closed tar1090's extra listener on port 8504"
  if live; then systemctl restart lighttpd; fi
fi

echo "== service accounts =="
if ! getent group scsetup >/dev/null; then groupadd --system scsetup; fi
if ! getent passwd scsetup >/dev/null; then
  useradd --system --gid scsetup --no-create-home --shell /usr/sbin/nologin scsetup
fi

echo "== programs =="
install -d -m 0755 /opt/stratoscan
for f in setupd.py setup-server.py funnel-gateway.py offline-map.py heartbeat.py notable-db.py \
         events.py pairing.py feeding.py ota.py ota-auto.sh net-watchdog.py sighting-store.py approach-store.py \
         network-compare.py photo-proxy.py tts-service.py shm-guard.sh wake-listener.py \
         core-feed.py labels.py; do
  install -m 0755 "deploy/$f" "/opt/stratoscan/$f"
done
install -m 0644 deploy/setup-ui.html deploy/airports.json deploy/airlines.json /opt/stratoscan/
# The trust root. Must already be on the device before it ships: fetching the
# key over the same channel as the update would make the signature pointless.
# NOT installable by an update, deliberately -- see deploy/allowed_signers.
install -m 0644 deploy/allowed_signers /opt/stratoscan/allowed_signers

echo "== the radar page =="
# Signed updates keep these current afterwards; this is the first copy.
install -m 0644 index.html /var/www/html/index.html
install -d -m 0755 /var/www/html/vendor
install -m 0644 vendor/* /var/www/html/vendor/
for d in sounds/*/; do
  install -d -m 0755 "/var/www/html/$d"
  for f in "$d"*; do
    case "$f" in *.md) ;; *) install -m 0644 "$f" "/var/www/html/$f" ;; esac
  done
done

echo "== system services and web routing =="
for u in stratoscan-setupd.service stratoscan-setup.service stratoscan-funnel-gateway.service \
         stratoscan-sighting-store.service stratoscan-approach-store.service \
         stratoscan-network.service stratoscan-photo-proxy.service stratoscan-tts.service \
         stratoscan-events.service stratoscan-core.service \
         stratoscan-ota-check.service stratoscan-ota-check.timer \
         stratoscan-ota-auto.service stratoscan-ota-auto.timer \
         stratoscan-netwatchdog.service stratoscan-netwatchdog.timer; do
  install -m 0644 "deploy/$u" /etc/systemd/system/
done
for c in 86-stratoscan-nocache.conf 89-stratoscan-photo-proxy.conf 91-stratoscan-approach-store.conf \
         93-stratoscan-sighting-store.conf 94-stratoscan-core.conf 95-stratoscan-network.conf 96-stratoscan-wake.conf \
         97-stratoscan-tts.conf 98-stratoscan-setup.conf 99-stratoscan-captive.conf; do
  lighttpd_conf "$c"
done
# Captive portal DNS for the setup hotspot (so phones stop using cellular).
install -d -m 0755 /etc/NetworkManager/dnsmasq-shared.d
install -m 0644 deploy/stratoscan-captive-dns.conf /etc/NetworkManager/dnsmasq-shared.d/stratoscan-captive.conf
lighttpd -tt -f /etc/lighttpd/lighttpd.conf

echo "== remote access: Tailscale (used only if the owner signs in from setup) =="
if ! command -v tailscale >/dev/null 2>&1; then
  . /etc/os-release
  curl -fsSL "https://pkgs.tailscale.com/stable/debian/$VERSION_CODENAME.noarmor.gpg" \
    -o /usr/share/keyrings/tailscale-archive-keyring.gpg
  curl -fsSL "https://pkgs.tailscale.com/stable/debian/$VERSION_CODENAME.tailscale-keyring.list" \
    -o /etc/apt/sources.list.d/tailscale.list
  apt-get update -q >/dev/null
  apt-get install -y -q tailscale >/dev/null
  echo "  installed"
else
  echo "  already installed"
fi

# Everything below is image-level: ota.py deliberately cannot install system
# config or unit files, so a unit only ever gets these from this script. That
# makes this the last chance before a unit leaves the house.
echo "== long-life hardening (security updates, panic reboot, logs) =="
# The apt timer is enabled on a stock image but does nothing without
# unattended-upgrades -- the first unit went unpatched for months behind an
# "enabled" timer.
install -m 0644 deploy/20auto-upgrades                   /etc/apt/apt.conf.d/20auto-upgrades
install -m 0644 deploy/52stratoscan-unattended-upgrades /etc/apt/apt.conf.d/52stratoscan-unattended-upgrades
install -m 0644 deploy/90-stratoscan-sysctl.conf        /etc/sysctl.d/90-stratoscan-sysctl.conf
# SSH by key only (see the file for why). Validated before sshd is touched:
# a config sshd rejects must never take remote access down with it.
install -d -m 0755 /etc/ssh/sshd_config.d
install -m 0644 deploy/10-stratoscan-ssh.conf /etc/ssh/sshd_config.d/10-stratoscan.conf
if live && command -v sshd >/dev/null 2>&1; then
  if sshd -t 2>/dev/null; then
    systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true
    echo "  ssh: key-only"
  else
    rm -f /etc/ssh/sshd_config.d/10-stratoscan.conf
    echo "  ssh: config rejected by sshd -t; left unchanged"
  fi
fi
install -d -m 0755 /etc/systemd/journald.conf.d
install -m 0644 deploy/journald-stratoscan.conf /etc/systemd/journald.conf.d/stratoscan.conf
# Applying sysctl in the image build would change the BUILD machine's kernel;
# the image picks the file up at boot.
if live; then sysctl -q -p /etc/sysctl.d/90-stratoscan-sysctl.conf; fi
# Checked cheaply, not with `unattended-upgrade --dry-run`: on a Pi that
# simulates every pending upgrade one at a time and ran past 40 minutes on the
# first unit. `apt-config dump` fails on a syntax error in any apt.conf.d
# file, and the grep proves ours is read.
if dpkg -s unattended-upgrades >/dev/null 2>&1 \
   && apt-config dump 2>/dev/null | grep -q 'Unattended-Upgrade::Package-Blacklist:: "chromium"' \
   && apt-config dump 2>/dev/null | grep -q 'APT::Periodic::Unattended-Upgrade "1"'; then
  echo "  security updates: configured (chromium, kernel and firmware held)"
else
  echo "  FAIL: unattended-upgrades is not installed or its config did not load"; exit 1
fi

# Real-time clock battery. Without one the clock is lost at every power cut
# and stays wrong until NTP answers. The Pi 5 can trickle-charge a
# RECHARGEABLE cell (ML-2020), but charging must never be enabled for an
# ordinary CR2032, which is not rechargeable and can leak or burst. So it is
# never guessed: set RTC_RECHARGEABLE=1 only when an ML-2020 is fitted.
if live; then
  RTC_V=$(cat /sys/class/rtc/rtc0/battery_voltage 2>/dev/null || echo 0)
  echo "  RTC battery: $((RTC_V / 1000)) mV ($([ "$RTC_V" -gt 1000000 ] && echo fitted || echo none fitted))"
fi
if [ "${RTC_RECHARGEABLE:-0}" = "1" ]; then
  CFG=/boot/firmware/config.txt
  if ! grep -q '^dtparam=rtc_bbat_vchg=' "$CFG"; then
    printf '\n# StratoScan: trickle-charge the rechargeable ML-2020 RTC cell\ndtparam=rtc_bbat_vchg=3000000\n' >> "$CFG"
    echo "  RTC charging enabled (takes effect after a reboot)"
  fi
fi

# Fan steps. The Pi 5 defaults step the fan up at 50/60/67.5/75C and back
# down 5C below each. In the retro case the kiosk sits at 65-68C, right on
# the 67.5 step, so the fan kept audibly shifting between ~6000 and ~7700rpm
# (measured on RDU, 2026-09-30). Moving the third step to 70C keeps normal
# running on one steady speed; the top step moves only to 77C, so full speed
# still arrives 3C before the Pi's 80C soft limit -- this case has reached
# 84.5C on busy days, so it goes no further than that.
CFG=/boot/firmware/config.txt
if [ -f "$CFG" ] && ! grep -q '^dtparam=fan_temp2=' "$CFG"; then
  printf '\n# StratoScan: steadier fan steps in the case (default 67.5C / 75C)\ndtparam=fan_temp2=70000\ndtparam=fan_temp3=77000\n' >> "$CFG"
  echo "  fan steps set to 70C / 77C in config.txt"
fi
# The trip points are writable at runtime, so apply now rather than waiting
# for a reboot. trip_point_3/4 are fan_temp2/3 (0 is the critical trip).
if live; then
  TZ0=/sys/class/thermal/thermal_zone0
  if [ "$(cat $TZ0/trip_point_3_temp 2>/dev/null)" = "67500" ]; then
    echo 70000 > $TZ0/trip_point_3_temp 2>/dev/null || true
    echo 77000 > $TZ0/trip_point_4_temp 2>/dev/null || true
  fi
  echo "  fan steps now: $(cat $TZ0/trip_point_3_temp 2>/dev/null) / $(cat $TZ0/trip_point_4_temp 2>/dev/null)"
fi

echo "== spoken alerts (Piper text-to-speech, offline) =="
# Piper (GPL-3.0-or-later) runs as its own program in its own virtualenv,
# installed from PyPI rather than shipped in this repository. The voice is
# LJSpeech, trained on a public-domain dataset -- many Piper voices are not
# licensed for redistribution or commercial use, so it is pinned.
TTS=/opt/stratoscan/tts
install -d -m 0755 "$TTS" "$TTS/voices"
[ -x "$TTS/venv/bin/python" ] || python3 -m venv "$TTS/venv"
# Every package pinned by version AND hash (deploy/tts-requirements.txt):
# this runs as root, so a tampered upload of any dependency must fail the
# install rather than run.
"$TTS/venv/bin/pip" install -q --require-hashes -r deploy/tts-requirements.txt
grep -q "^piper-tts==$PIPER_VERSION " deploy/tts-requirements.txt \
  || { echo "  PIPER_VERSION and tts-requirements.txt disagree"; exit 1; }
[ -f "$TTS/voices/$VOICE.onnx" ] || \
  "$TTS/venv/bin/python" -m piper.download_voices "$VOICE" --data-dir "$TTS/voices"
# The voice files, against the checksums recorded when this voice was chosen.
VOICE_SUMS="$(pwd)/deploy/tts-voice.sha256"
if ! (cd "$TTS/voices" && sha256sum -c --quiet "$VOICE_SUMS"); then
  rm -f "$TTS/voices/$VOICE.onnx" "$TTS/voices/$VOICE.onnx.json"
  echo "  voice files do not match deploy/tts-voice.sha256; removed"
  exit 1
fi
chmod -R a+rX "$TTS"

echo "== the kiosk (desktop user: ${KIOSK_USER:-none}) =="
# These run under the desktop user's systemd, because they need its Wayland
# session. Enabled by linking into the user's .wants directories, which works
# both live and in the image build (no user session is needed to create them).
if [ -n "$KIOSK_USER" ] && [ "$KIOSK_USER" != "root" ]; then
  KHOME=$(getent passwd "$KIOSK_USER" | cut -d: -f6)
  UDIR="$KHOME/.config/systemd/user"
  install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$KHOME/.config" "$UDIR" \
    "$UDIR/default.target.wants" "$UDIR/timers.target.wants"
  for u in stratoscan-kiosk.service stratoscan-kiosk-restart.service \
           stratoscan-kiosk-restart.timer stratoscan-shmguard.service \
           stratoscan-shmguard.timer stratoscan-screensaver.service \
           stratoscan-wake.service; do
    install -m 0644 -o "$KIOSK_USER" -g "$KIOSK_USER" "deploy/$u" "$UDIR/$u"
  done
  for u in stratoscan-kiosk.service stratoscan-screensaver.service stratoscan-wake.service; do
    ln -sfn "../$u" "$UDIR/default.target.wants/$u"
  done
  for u in stratoscan-kiosk-restart.timer stratoscan-shmguard.timer; do
    ln -sfn "../$u" "$UDIR/timers.target.wants/$u"
  done
  chown -h "$KIOSK_USER:$KIOSK_USER" "$UDIR"/*.wants/* 2>/dev/null || true
  if live; then
    KUID=$(id -u "$KIOSK_USER")
    runuser -u "$KIOSK_USER" -- env XDG_RUNTIME_DIR="/run/user/$KUID" \
      systemctl --user daemon-reload 2>/dev/null \
      && echo "  user units installed; they take effect on the next kiosk restart" \
      || echo "  user units installed; they take effect at the next login"
    # Start any that aren't running -- after the rename there are none, since
    # migrate-names.sh stopped the old kiosk. 'start' leaves running ones
    # alone, so an ordinary re-run doesn't blank the display.
    runuser -u "$KIOSK_USER" -- env XDG_RUNTIME_DIR="/run/user/$KUID" \
      systemctl --user start stratoscan-kiosk.service stratoscan-screensaver.service \
        stratoscan-wake.service stratoscan-kiosk-restart.timer stratoscan-shmguard.timer 2>/dev/null \
      && echo "  kiosk services running" || echo "  kiosk services start at the next login"
  else
    echo "  user units installed and enabled"
  fi
else
  echo "  WARNING: no kiosk user (run via sudo from the desktop user's account, or set KIOSK_USER)"
fi

echo "== data (fetched now if online; otherwise net-watchdog retries) =="
python3 /opt/stratoscan/notable-db.py ensure && echo "  notable-aircraft list: ready" \
  || echo "  notable-aircraft list: will be fetched when online"
python3 /opt/stratoscan/offline-map.py ensure \
  && { [ -f /var/www/html/offline-map/meta.json ] && echo "  offline map: ready" \
         || echo "  offline map: built once a location is set"; } \
  || echo "  offline map: will be built when online"

echo "== enabling =="
if live; then systemctl daemon-reload; fi
for u in stratoscan-setupd.service stratoscan-setup.service stratoscan-funnel-gateway.service \
         stratoscan-sighting-store.service stratoscan-approach-store.service \
         stratoscan-network.service stratoscan-photo-proxy.service stratoscan-tts.service \
         stratoscan-events.service stratoscan-core.service \
         stratoscan-ota-check.timer stratoscan-ota-auto.timer stratoscan-netwatchdog.timer \
         lighttpd.service readsb.service; do
  enable_unit "$u"
done
if ! live; then
  echo "  enabled; nothing started (image build). First boot finishes the job."
  exit 0
fi
systemctl reload lighttpd
# A re-run installs new code over running services; enabling alone does not
# restart them, so without this a re-run left the previous code running.
for u in stratoscan-setupd.service stratoscan-setup.service stratoscan-funnel-gateway.service \
         stratoscan-sighting-store.service stratoscan-approach-store.service \
         stratoscan-network.service stratoscan-photo-proxy.service stratoscan-tts.service \
         stratoscan-events.service stratoscan-core.service; do
  restart_unit "$u"
done
systemctl restart systemd-journald

echo "== verifying privileged paths are refused on the public tunnel =="
fail=0
for p in /setup /./setup /x/../setup /%73etup /wake /%77ake /tts; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --path-as-is -X POST \
         -H 'Content-Length: 0' "http://127.0.0.1:8085$p")
  [ "$code" = "404" ] || { echo "  FAIL: $p returned $code via the public gateway"; fail=1; }
done
[ "$fail" = "0" ] && echo "  all privileged paths refused publicly"
[ "$fail" = "0" ] || { echo "REFUSING TO FINISH: the public filter is not working"; exit 1; }

echo
echo "Setup page:  http://$(hostname -I | awk '{print $1}')/setup"
echo "Claim code:  shown below (also in /run/stratoscan/claim-code)"
cat /run/stratoscan/claim-code 2>/dev/null || echo "  (not generated yet)"
