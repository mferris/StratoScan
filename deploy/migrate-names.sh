#!/bin/sh
# One-time move of a unit from the project's old 'flightradar' names to
# 'stratoscan' (2026-09-30). Run by install-setup-server.sh before it installs
# anything; does nothing on a fresh install or on a unit already moved.
#
# What must survive, and is MOVED, never re-created:
#   /var/lib/flightradar-relay   the unit's relay key: its identity. Lose it
#                                and the relay sees a new unit, so every phone
#                                would have to pair again.
#   /var/lib/flightradar-ota     the installed update serial and rollback copies
#   /var/lib/flightradar-setup   admin password, hotspot key, setup state
#   /var/lib/private/flightradar-*  sightings, approach heatmap, network
#                                scorecard (DynamicUser services: the data lives
#                                under private/, /var/lib/<name> is only a link
#                                systemd recreates under the new name)
# Everything else (programs, units, config) is installed fresh by the
# installer under the new names straight after this.
#
# A tarball of what it touches goes to /var/backups first. /opt/flightradar is
# left as a link to /opt/stratoscan for one release, as a safety net for
# anything that still names the old path; a later release removes it.
#
# ROOT prefixes every path, so tests/test_migrate_names.py can run this against
# a scratch tree. systemctl, runuser, usermod and groupmod are looked up on
# PATH, so the test substitutes recorders for them.
set -eu
ROOT="${ROOT:-}"
KIOSK_USER="${KIOSK_USER:-}"

OLD="$ROOT/opt/flightradar"
NEW="$ROOT/opt/stratoscan"

if [ ! -d "$OLD" ] || [ -L "$OLD" ]; then
  echo "  names: nothing to move (fresh install, or already moved)"
  exit 0
fi
if [ -e "$NEW" ]; then
  echo "  names: both $OLD and $NEW exist -- refusing to guess which is current" >&2
  exit 1
fi

echo "== moving this unit from 'flightradar' names to 'stratoscan' =="

# 0. Backup of everything below, before any of it changes.
mkdir -p "$ROOT/var/backups"
BACKUP="$ROOT/var/backups/stratoscan-rename-$(date +%Y%m%d-%H%M%S).tar.gz"
( cd "$ROOT/" && tar czf "$BACKUP" $(ls -d opt/flightradar var/lib/flightradar-* \
    var/lib/private/flightradar-* etc/systemd/system/flightradar-* 2>/dev/null) ) \
  && echo "  backup: $BACKUP"

# 1. Stop and remove the old services. The installer installs and starts the
#    new ones; two copies of any of them (the kiosk, the setup helper's socket,
#    the stores' ports) must never run at once.
for path in "$ROOT"/etc/systemd/system/flightradar-*; do
  [ -e "$path" ] || [ -L "$path" ] || continue
  u=${path##*/}
  [ -L "$path" ] || systemctl disable --now "$u" >/dev/null 2>&1 || true
  rm -f "$path"
done
find "$ROOT/etc/systemd/system" -name 'flightradar-*' -type l -exec rm -f {} + 2>/dev/null || true
if [ -n "$KIOSK_USER" ]; then
  KHOME=$(getent passwd "$KIOSK_USER" 2>/dev/null | cut -d: -f6 || true)
  [ -n "$KHOME" ] || KHOME="/home/$KIOSK_USER"
  UDIR="$ROOT$KHOME/.config/systemd/user"
  if [ -d "$UDIR" ]; then
    if [ -z "$ROOT" ]; then
      KUID=$(id -u "$KIOSK_USER")
      for path in "$UDIR"/flightradar-*; do
        [ -e "$path" ] || continue
        runuser -u "$KIOSK_USER" -- env XDG_RUNTIME_DIR="/run/user/$KUID" \
          systemctl --user stop "${path##*/}" >/dev/null 2>&1 || true
      done
    fi
    rm -f "$UDIR"/flightradar-* "$UDIR"/*.wants/flightradar-*
  fi
fi
systemctl daemon-reload >/dev/null 2>&1 || true
echo "  old services stopped and removed"

# 2. Programs.
mv "$OLD" "$NEW"

# 3. State. Private dirs first (the data), then the /var/lib entries: links
#    are dropped (systemd makes new ones), real directories move.
for p in "$ROOT"/var/lib/private/flightradar-*; do
  [ -e "$p" ] || continue
  mv "$p" "$ROOT/var/lib/private/stratoscan-${p##*/flightradar-}"
done
for d in "$ROOT"/var/lib/flightradar-*; do
  if [ -L "$d" ]; then rm -f "$d"
  elif [ -e "$d" ]; then mv "$d" "$ROOT/var/lib/stratoscan-${d##*/flightradar-}"
  fi
done
echo "  data moved: $(ls -d "$ROOT"/var/lib/stratoscan-* "$ROOT"/var/lib/private/stratoscan-* 2>/dev/null | wc -l | tr -d ' ') entries"

# 4. Old config files. The installer writes the new ones next.
rm -f "$ROOT"/etc/lighttpd/conf-enabled/*-flightradar-*.conf \
      "$ROOT"/etc/lighttpd/conf-available/*-flightradar-*.conf \
      "$ROOT"/etc/NetworkManager/dnsmasq-shared.d/flightradar-captive.conf \
      "$ROOT"/etc/apt/apt.conf.d/52flightradar-unattended-upgrades \
      "$ROOT"/etc/sysctl.d/90-flightradar-sysctl.conf \
      "$ROOT"/etc/systemd/journald.conf.d/flightradar.conf \
      "$ROOT"/etc/ssh/sshd_config.d/10-radome.conf

# 5. The setup server's account keeps its uid and gid, so everything it owns
#    stays owned; only the names change.
if [ -z "$ROOT" ] && getent passwd frsetup >/dev/null 2>&1; then
  usermod -l scsetup frsetup
  getent group frsetup >/dev/null 2>&1 && groupmod -n scsetup frsetup
  echo "  account frsetup renamed to scsetup (same uid/gid)"
fi

# 6. The tar1090 install marker, so the installer doesn't reinstall tar1090.
M="$ROOT/usr/local/share/tar1090/git"
[ -f "$M/.flightradar-commit" ] && mv "$M/.flightradar-commit" "$M/.stratoscan-commit"

# 7. Safety net for one release.
ln -s /opt/stratoscan "$OLD"
echo "  $OLD now points at /opt/stratoscan (removed in a later release)"
