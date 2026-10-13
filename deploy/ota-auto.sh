#!/bin/sh
# Unattended update: wake the panel, wait for proof it is painting, then apply.
#
# WHY THE WAKE. ota.py verifies an update by restarting the kiosk and watching
# the paint stamp advance; if it does not advance inside PAINT_TIMEOUT_S the
# release is rolled back. That check is correct and it is the reason a bad
# release cannot brick a unit in someone else's house -- but it only answers
# truthfully while the panel is on. With the panel blanked the page's
# requestAnimationFrame loop stops, no frames are reported, the stamp never
# moves, and a perfectly good release is rolled back for a fault that does not
# exist. shm-guard.sh hit exactly this and solved it the same way: wake first.
#
# Worse than the false rollback: Chromium restarted against a blanked panel
# comes up WINDOWED -- tab bar, address bar, desktop behind it -- which on a
# gifted unit is indistinguishable from the thing being broken.
#
# So this does not simply run `ota.py apply` on a timer. It wakes the panel
# through the same /wake endpoint the touchscreen uses, waits for the stamp to
# actually move (proof the page is rendering, not merely that the panel is
# powered), and only then applies. Nothing re-blanks the panel afterwards on
# purpose: the screensaver already does that on idle, and duplicating it here
# would be a second thing to get wrong.
#
# If the page never starts painting, this exits without applying. That is the
# safe outcome -- the release stays staged and the next run tries again.
set -eu

WAKE_URL="${STRATOSCAN_WAKE_URL:-http://127.0.0.1/wake}"
# The desktop user the kiosk runs as, found the way ota.py's
# detect_kiosk_user finds it: an explicit override, then the display
# manager's autologin user (that IS the kiosk session; later files win),
# then uid 1000. This was hard-coded to the first unit's user, which a unit
# built from the factory image ("stratoscan") doesn't have: its paint stamp
# was then never found, and it would never have applied an update by itself
# (found 2026-10-13, reviewing the image for #5).
kiosk_user() {
    [ -n "${STRATOSCAN_KIOSK_USER:-}" ] && { echo "$STRATOSCAN_KIOSK_USER"; return; }
    u=$(cat ${STRATOSCAN_LIGHTDM_CONFS:-/etc/lightdm/lightdm.conf /etc/lightdm/lightdm.conf.d/*.conf} 2>/dev/null \
        | sed -n 's/^[[:space:]]*autologin-user=[[:space:]]*\([^[:space:]]\{1,\}\).*/\1/p' | tail -n 1)
    [ -n "$u" ] && { echo "$u"; return; }
    u=$(getent passwd 1000 2>/dev/null | cut -d: -f1)
    echo "${u:-stratoscan}"
}
KIOSK_USER=$(kiosk_user)
OTA="${STRATOSCAN_OTA:-/opt/stratoscan/ota.py}"
PAINT_WAIT_S="${STRATOSCAN_PAINT_WAIT_S:-60}"

uid=$(id -u "$KIOSK_USER" 2>/dev/null || echo "")
STAMP="${STRATOSCAN_PAINT_STAMP:-/run/user/${uid}/stratoscan-painted}"

stamp_mtime() {
    # 0 when the file is absent, which is also what ota.py treats as "cannot
    # answer". Keeping the two in agreement matters: this script deciding the
    # display is fine while ota.py refuses would be a confusing pair of logs.
    [ -f "$STAMP" ] || { echo 0; return; }
    stat -c %Y "$STAMP" 2>/dev/null || stat -f %m "$STAMP" 2>/dev/null || echo 0
}

log() { echo "ota-auto: $*"; }

# Nothing to do at all? Ask first, so a unit that is up to date never wakes its
# own screen in the middle of someone's evening.
if ! "$OTA" check 2>&1 | grep -q "update available"; then
    log "up to date; not touching the display"
    exit 0
fi

before=$(stamp_mtime)
log "update available; waking the panel (stamp was $before)"
curl -s -m 10 -X POST "$WAKE_URL" >/dev/null 2>&1 || log "wake request failed; continuing anyway"

# Wait for the stamp to MOVE. Panel-on is not the same as page-painting, and it
# is the painting that the rollback check measures.
waited=0
while [ "$waited" -lt "$PAINT_WAIT_S" ]; do
    now=$(stamp_mtime)
    if [ "$now" != "0" ] && [ "$now" != "$before" ]; then
        log "display is painting after ${waited}s; applying"
        exec "$OTA" apply
    fi
    sleep 3
    waited=$((waited + 3))
done

log "display never reported a frame in ${PAINT_WAIT_S}s -- not applying."
log "the release stays staged; the next run will try again."
exit 0
