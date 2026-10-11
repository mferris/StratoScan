#!/bin/sh
# Boot straight to StratoScan: from power-on to the radar the screen shows
# the StratoScan picture (deploy/boot-splash/splash.png) and nothing else.
#
#   firmware   disable_splash=1 in config.txt: no colour test pattern
#   kernel     console on tty3, no Raspberry Pi logo, no cursor, quiet
#   plymouth   Raspberry Pi OS's own "pix" theme, with our picture and our
#              script (no status text). Both are swapped with dpkg-divert, so an upgrade of
#              rpd-plym-splash -- whose postinst re-selects pix and rebuilds
#              the initramfs -- installs its file beside ours, not over it.
#   desktop    /etc/xdg/labwc/autostart replaced by deploy/labwc-autostart:
#              the picture as the background, no desktop icons, no taskbar.
#              It is a conffile and units upgrade with --force-confold, so
#              upgrades keep this version.
#
# Every step is idempotent and keeps the original beside the file it
# changes (*.stratoscan-orig). Run as root from the repo root:
#   sudo sh deploy/quiet-boot.sh
# QUIET_BOOT_FILES_ONLY=1 with FW=<dir> AUTOSTART=<file> edits only those
# text files (the tests use it).
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
FW="${FW:-/boot/firmware}"
AUTOSTART="${AUTOSTART:-/etc/xdg/labwc/autostart}"
SPLASH_SRC="$HERE/boot-splash/splash.png"
SPLASH=/usr/share/stratoscan/splash.png
PIX=/usr/share/plymouth/themes/pix/splash.png

keep_orig() { [ -f "$1.stratoscan-orig" ] || cp -p "$1" "$1.stratoscan-orig"; }

# kernel command line: one line; add what is missing, move the console off tty1
cmdline() {
  f="$FW/cmdline.txt"
  [ -f "$f" ] || { echo "  no $f; kernel command line left alone"; return 0; }
  line=$(head -n 1 "$f")
  new=$(printf '%s\n' "$line" | sed -E 's/(^| )console=tty1( |$)/\1console=tty3\2/')
  for w in quiet splash plymouth.ignore-serial-consoles logo.nologo loglevel=3 vt.global_cursor_default=0; do
    key=${w%%=*}
    case " $new " in
      *" $w "*|*" $key="*) ;;
      *) new="$new $w" ;;
    esac
  done
  if [ "$new" != "$line" ]; then
    keep_orig "$f"
    printf '%s\n' "$new" > "$f"
    echo "  kernel command line: quiet, no logo, console on tty3 (after a reboot)"
  else
    echo "  kernel command line: already quiet"
  fi
}

# firmware: no rainbow test pattern
firmware() {
  f="$FW/config.txt"
  [ -f "$f" ] || return 0
  if grep -q '^disable_splash=1' "$f"; then
    echo "  firmware splash: already off"
  else
    keep_orig "$f"
    printf '\n[all]\n# StratoScan: no colour splash at power-on\ndisable_splash=1\n' >> "$f"
    echo "  firmware splash: off (after a reboot)"
  fi
}

# desktop session: the picture, no desktop, no taskbar
desktop() {
  [ -f "$AUTOSTART" ] || { echo "  no $AUTOSTART; desktop left alone"; return 0; }
  if cmp -s "$HERE/labwc-autostart" "$AUTOSTART"; then
    echo "  desktop: already the StratoScan picture"
  else
    keep_orig "$AUTOSTART"
    install -m 0644 "$HERE/labwc-autostart" "$AUTOSTART"
    echo "  desktop: replaced by the StratoScan picture (from the next login)"
  fi
}

if [ "${QUIET_BOOT_FILES_ONLY:-0}" = "1" ]; then
  cmdline; firmware; desktop
  exit 0
fi

[ "$(id -u)" = "0" ] || { echo "run as root: sudo sh deploy/quiet-boot.sh"; exit 1; }

# swaybg draws the picture as the background; the GTK layer-shell binding
# lets boot-cover.py hold it above Chromium until the page paints.
for p in swaybg gir1.2-gtklayershell-0.1; do
  dpkg -s "$p" >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get install -y -q "$p" >/dev/null 2>&1
done
install -D -m 0644 "$SPLASH_SRC" "$SPLASH"

# plymouth: our picture, and our script (no status text), in place of
# Raspberry Pi's. Both files are diverted, so a package upgrade installs its
# own copies beside ours.
THEME=$(dirname "$PIX")
if [ -d "$THEME" ]; then
  changed=0
  for f in splash.png pix.script; do
    if ! dpkg-divert --listpackage "$THEME/$f" 2>/dev/null | grep -qx stratoscan; then
      dpkg-divert --package stratoscan --add --rename --divert "$THEME/$f.raspberrypi" "$THEME/$f" >/dev/null
    fi
    if ! cmp -s "$HERE/boot-splash/$f" "$THEME/$f"; then
      install -m 0644 "$HERE/boot-splash/$f" "$THEME/$f"
      changed=1
    fi
  done
  if [ "$changed" = "0" ] && [ "$(plymouth-set-default-theme 2>/dev/null)" = "pix" ]; then
    echo "  boot splash: already StratoScan"
  else
    plymouth-set-default-theme -R pix >/dev/null 2>&1 || plymouth-set-default-theme -R pix
    echo "  boot splash: StratoScan, no status text (initramfs rebuilt)"
  fi
else
  echo "  no plymouth pix theme; boot splash left alone"
fi

cmdline
firmware
desktop
