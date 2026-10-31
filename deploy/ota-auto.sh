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
#
# THE WAKE CARRIES AN EMPTY BODY (2026-10-30, #81). lighttpd answers a POST
# with no Content-Length with 411 Length Required and never passes it on, so
# the bare `curl -X POST` this used to send never reached the wake listener:
# the panel stayed dark, nothing painted, and no unattended update could
# install unless the page happened to be painting already. curl still exits 0
# on a 411, so the failure was silent. Now the POST has an empty body
# (Content-Length: 0), any answer that is not 2xx is logged with its status,
# and the wake is sent again every WAKE_EVERY_S while waiting, in case one is
# refused or lands inside the listener's 10 s gap after another wake. "why"
# is "update", the reason ota.py gives, so the journal says who asked.
set -eu

WAKE_URL="${STRATOSCAN_WAKE_URL:-http://127.0.0.1/wake?why=update}"
WAKE_EVERY_S="${STRATOSCAN_WAKE_EVERY_S:-15}"
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

# Ask for the panel to be woken. The empty body (-d '') is what makes curl send
# Content-Length: 0; without it lighttpd refuses the request (see the top).
wake() {
    code=$(curl -s -m 10 -o /dev/null -w '%{http_code}' -d '' "$WAKE_URL" 2>/dev/null) || true
    case "$code" in
        2??) return 0 ;;
    esac
    log "wake request answered HTTP ${code:-000} (not 2xx); will ask again"
}

# Nothing to do at all? Ask first, so a unit that is up to date never wakes its
# own screen in the middle of someone's evening.
if ! "$OTA" check 2>&1 | grep -q "update available"; then
    log "up to date; not touching the display"
    exit 0
fi

before=$(stamp_mtime)
log "update available; waking the panel (stamp was $before)"
wake

# Wait for the stamp to MOVE. Panel-on is not the same as page-painting, and it
# is the painting that the rollback check measures.
# The wake is repeated while waiting: a refused one, or one swallowed by the
# listener's rate limit, would otherwise cost the whole run.
waited=0
since_wake=0
while [ "$waited" -lt "$PAINT_WAIT_S" ]; do
    now=$(stamp_mtime)
    if [ "$now" != "0" ] && [ "$now" != "$before" ]; then
        log "display is painting after ${waited}s; applying"
        exec "$OTA" apply
    fi
    if [ "$since_wake" -ge "$WAKE_EVERY_S" ]; then
        wake
        since_wake=0
    fi
    sleep 3
    waited=$((waited + 3))
    since_wake=$((since_wake + 3))
done

log "display never reported a frame in ${PAINT_WAIT_S}s -- not applying."
log "the release stays staged; the next run will try again."
exit 0
