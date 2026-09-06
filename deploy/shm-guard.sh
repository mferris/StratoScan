#!/bin/sh
# Restarts the kiosk BEFORE Chromium's /dev/shm leak reaches the point where
# GPU allocations fail and the panel freezes on a stale frame.
#
# The 04:00 timer bounds the leak once a day. That is not always enough: the
# shortest observed time-to-freeze here was 5.2 hours, inside a single busy
# afternoon. This closes that gap by restarting on the actual measurement
# rather than on the clock.
#
# TWO thresholds, because a restart is only free when nobody is looking:
#
# RELOAD FIRST. Tearing down the document releases about half the accumulated
# shared memory (151MB -> 72MB, measured on this device) without restarting
# Chromium: no black screen, no risk of two instances racing and coming up
# windowed. Only if a reload does not bring it under control is the browser
# restarted. Measured alternatives that did NOT work: --in-process-gpu made it
# marginally worse (+130MB/30min against a +104MB baseline), and a critical
# memory-pressure signal freed nothing at all.
#
#   IDLE_MB  -- act at a low mark, but ONLY while the panel is blanked.
#               Most restarts should happen here, invisibly.
#   HIGH_MB  -- restart regardless of panel state. This is the one that
#               prevents the freeze, and it is worth a two-second black
#               screen to avoid a display stuck until someone notices.
#
# Measured two ways, acting on whichever is larger:
#
#   - /dev/shm usage, the arena that actually runs out;
#   - the sum of shm/memfd mappings across Chromium's renderers.
#
# Both, because they can diverge: /etc/chromium.d/dev-shm adds
# --disable-dev-shm-usage when /dev/shm has under 3.8GB free at launch, so
# after one bad day Chromium switches its backing to /tmp and the df number
# stops tracking the leak while the mappings keep growing.
#
# Runs as a user unit, like the kiosk it restarts.
set -eu

STATE="${STATE_DIRECTORY:-$HOME/.local/state/flightradar-shmguard}"
STAMP="$STATE/last-restart"
HIGH_MB="${SHMGUARD_HIGH_MB:-1500}"
IDLE_MB="${SHMGUARD_IDLE_MB:-900}"
MIN_INTERVAL_S="${SHMGUARD_MIN_INTERVAL_S:-1800}"
# How long to leave the panel on after a restart before blanking it again.
# Chromium has to come up and take the display fullscreen; blank it too soon
# and it lands windowed, which is the whole problem below.
RESTART_SETTLE_S="${SHMGUARD_RESTART_SETTLE_S:-25}"
# The nightly 04:00 restart comes through here too, with FORCE=1. Both
# restart paths must share one rate limit: two Chromium instances started
# within a few seconds of each other lose kiosk mode and leave the browser
# windowed, with tab bar and address bar on the display. Observed, not
# theorised -- it happened while testing this script.
FORCE="${SHMGUARD_FORCE:-0}"
RELOAD_WAIT_S="${SHMGUARD_RELOAD_WAIT_S:-45}"
RELOAD_REQUEST="${XDG_RUNTIME_DIR:-/tmp}/flightradar-reload-request"

mkdir -p "$STATE"

# Never act on a kiosk that is not running: restarting a stopped or
# failed unit turns an unrelated problem into a restart loop.
if [ "$(systemctl --user is-active flightradar-kiosk.service)" != "active" ]; then
    echo "shm-guard: kiosk not active, nothing to do"; exit 0
fi

measure() {
df_mb=$(df -m /dev/shm 2>/dev/null | awk 'NR==2 {print $3}' || echo 0)
map_mb=$(python3 - <<'PY' 2>/dev/null || echo 0
import os
tot = 0
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", "replace")
    except OSError:
        continue
    # Chromium rewrites argv into one space-separated string with a single
    # trailing NUL, so splitting on NULs alone finds no --type= at all.
    if "chromium" not in cmd or "--type=renderer" not in cmd.replace(chr(0), " "):
        continue
    try:
        for line in open(f"/proc/{pid}/maps"):
            f = line.split(None, 5)
            if len(f) < 6 or ("/dev/shm" not in f[5] and "memfd:" not in f[5]):
                continue
            a, b = f[0].split("-")
            tot += int(b, 16) - int(a, 16)
    except OSError:
        continue          # process exited mid-read
print(tot // 1048576)
PY
)
[ -n "$df_mb" ] || df_mb=0
[ -n "$map_mb" ] || map_mb=0
mb="$df_mb"; [ "$map_mb" -gt "$mb" ] && mb="$map_mb"
# Explicit success. Under `set -e` the AND-OR list above is the last command
# in this function, so whenever map_mb is NOT the larger of the two the
# function returns non-zero and takes the whole script down with it -- before
# a single threshold is evaluated. It fails silently and looks exactly like
# "nothing needed doing".
return 0
}
measure

panel="unknown"
WD=$(basename "$(ls "$XDG_RUNTIME_DIR"/wayland-*[0-9] 2>/dev/null | head -1)" 2>/dev/null || true)
if [ -n "${WD:-}" ]; then
    panel=$(WAYLAND_DISPLAY="$WD" wlopm 2>/dev/null | awk '/HDMI/ {print $2}' || echo unknown)
    [ -n "$panel" ] || panel="unknown"
fi

reason=""; trigger_mb=0
if [ "$FORCE" = "1" ]; then
    reason="scheduled restart"
elif [ "$mb" -ge "$HIGH_MB" ]; then
    reason="high mark: ${mb}MB >= ${HIGH_MB}MB"; trigger_mb="$HIGH_MB"
elif [ "$mb" -ge "$IDLE_MB" ] && [ "$panel" = "off" ]; then
    reason="idle mark: ${mb}MB >= ${IDLE_MB}MB and panel is off"; trigger_mb="$IDLE_MB"
fi

# Judge the reload against the threshold that actually fired, not against the
# high mark. Deriving it from HIGH_MB made the idle path (900MB) accept
# anything under 1125MB -- a check that passes when the reload does nothing,
# which is no check at all.
RELOAD_OK_MB="${SHMGUARD_RELOAD_OK_MB:-$(( trigger_mb * 3 / 4 ))}"

if [ -z "$reason" ]; then
    echo "shm-guard: ${mb}MB (shm=${df_mb} maps=${map_mb}) panel=${panel} -- below thresholds"
    exit 0
fi

# Rate limit. If something other than the leak is filling shm, a restart will
# not fix it, and a guard that restarts every five minutes forever is worse
# than the freeze it was written to prevent.
now=$(date +%s)
if [ -f "$STAMP" ]; then
    last=$(cat "$STAMP" 2>/dev/null || echo 0)
    case "$last" in ''|*[!0-9]*) last=0 ;; esac
    if [ $(( now - last )) -lt "$MIN_INTERVAL_S" ]; then
        echo "shm-guard: ${reason}, but last restart was $(( (now - last) / 60 ))min ago (min ${MIN_INTERVAL_S}s) -- holding"
        exit 0
    fi
fi

echo "$now" > "$STAMP"

# --- reload first ---
# The page picks this up on its next heartbeat, which it sends every 20s.
if [ "$FORCE" != "1" ]; then
    echo "shm-guard: ${reason} -- asking the page to reload (shm=${df_mb}MB maps=${map_mb}MB panel=${panel})"
    : > "$RELOAD_REQUEST" 2>/dev/null || true
    sleep "$RELOAD_WAIT_S"
    before="$mb"
    measure
    if [ "$mb" -le "$RELOAD_OK_MB" ]; then
        echo "shm-guard: reload brought it ${before}MB -> ${mb}MB, under ${RELOAD_OK_MB}MB -- no restart needed"
        exit 0
    fi
    echo "shm-guard: reload left it at ${mb}MB (was ${before}MB, wanted <= ${RELOAD_OK_MB}MB) -- escalating"
    # Do not leave an unconsumed request behind to reload the fresh page too.
    rm -f "$RELOAD_REQUEST" 2>/dev/null || true
fi

# CHROMIUM MUST NOT BE RESTARTED WHILE THE PANEL IS BLANKED.
#
# It comes up WINDOWED -- tab bar, address bar and the desktop behind it --
# even though --kiosk is on its command line. Reproduced both ways on the
# device: restart with the panel off gives a windowed browser every time,
# restart with it on gives fullscreen every time. Chromium cannot take an
# output that is not on, and it does not retry once the output comes back.
#
# This bit twice before it was understood. The first time it was blamed on
# two restarts landing seconds apart; the real common factor was that the
# panel happened to be off. It matters most for the 04:00 restart, which by
# design runs when the screensaver has blanked the panel -- so it would have
# left the display windowed every single morning.
#
# So: wake the panel, restart, give it time to come up fullscreen, and only
# then put the panel back the way it was found.
echo "shm-guard: restarting kiosk -- ${reason} (shm=${df_mb}MB maps=${map_mb}MB panel=${panel})"
panel_was_off=0
if [ "$panel" = "off" ] && [ -n "${WD:-}" ]; then
    panel_was_off=1
    echo "shm-guard: panel is off -- waking it first, or Chromium restarts windowed"
    WAYLAND_DISPLAY="$WD" wlopm --on HDMI-A-1 >/dev/null 2>&1 || true
    sleep 2
fi

systemctl --user restart flightradar-kiosk.service

if [ "$panel_was_off" = "1" ]; then
    sleep "$RESTART_SETTLE_S"
    WAYLAND_DISPLAY="$WD" wlopm --off HDMI-A-1 >/dev/null 2>&1 || true
    echo "shm-guard: panel blanked again after ${RESTART_SETTLE_S}s"
fi
