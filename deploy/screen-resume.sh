#!/bin/sh
# What the screensaver does when the desktop says someone is back
# (stratoscan-screensaver.service, swayidle's `resume`): light the panel and
# end an alert's short hold -- but only for a person.
#
# The desktop also reports activity when an application asks to keep the
# screen awake, and Chromium asks for as long as the page plays a sound
# (2026-10-16, found on RDU: every alert chime turned the desktop "active"
# two seconds before its audio stream opened, with no touch at all). So each
# chime woke the dark panel for the full IDLE_MINUTES, all night, and an
# alert's own chime turned its two-minute hold into twenty minutes.
#
# wake-listener.py records each real input (a touch, a key, a button, the
# dials) in $XDG_RUNTIME_DIR/stratoscan-last-input. Activity with no input in
# the last few seconds is a sound, and changes nothing. The listener makes
# the file, dated 1970, as soon as it can read a touchscreen or keys, so this
# holds from boot, before anyone has touched anything (2026-10-26). Until that
# file exists (a listener that cannot read the input devices, or one not yet
# started), any activity wakes the panel, as it always did: a finger must
# never fail to wake the screen.
F="$XDG_RUNTIME_DIR/stratoscan-alert-wake"
L="$XDG_RUNTIME_DIR/stratoscan-last-input"
RECENT_S=5

if [ -e "$L" ]; then
    sleep 0.3                           # the listener notes the touch a moment after the desktop sees it
    now=$(date +%s)
    at=$(stat -c %Y "$L" 2>/dev/null || stat -f %m "$L" 2>/dev/null || echo 0)
    if [ $(( now - at )) -gt "$RECENT_S" ]; then
        exit 0                          # a sound, not a person
    fi
fi
rm -f "$F"
# Each wlopm call is limited: a compositor that stops answering held this,
# and swayidle with it, so the panel neither blanked nor woke (#86, 2026-10-26).
if timeout 5 wlopm | grep -q " off"; then
    timeout 5 wlopm --on '*'
    logger -t stratoscan-screen on-touch
fi
