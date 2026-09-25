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

WAKE_URL="${FLIGHTRADAR_WAKE_URL:-http://127.0.0.1/wake}"
KIOSK_USER="${FLIGHTRADAR_KIOSK_USER:-mferris}"
OTA="${FLIGHTRADAR_OTA:-/opt/flightradar/ota.py}"
PAINT_WAIT_S="${FLIGHTRADAR_PAINT_WAIT_S:-60}"

uid=$(id -u "$KIOSK_USER" 2>/dev/null || echo "")
STAMP="${FLIGHTRADAR_PAINT_STAMP:-/run/user/${uid}/flightradar-painted}"

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
