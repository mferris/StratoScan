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
#   IDLE_MB  -- restart at a low mark, but ONLY while the panel is blanked.
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

mkdir -p "$STATE"

# Never act on a kiosk that is not running: restarting a stopped or
# failed unit turns an unrelated problem into a restart loop.
if [ "$(systemctl --user is-active flightradar-kiosk.service)" != "active" ]; then
    echo "shm-guard: kiosk not active, nothing to do"; exit 0
fi

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

panel="unknown"
WD=$(basename "$(ls "$XDG_RUNTIME_DIR"/wayland-*[0-9] 2>/dev/null | head -1)" 2>/dev/null || true)
if [ -n "${WD:-}" ]; then
    panel=$(WAYLAND_DISPLAY="$WD" wlopm 2>/dev/null | awk '/HDMI/ {print $2}' || echo unknown)
    [ -n "$panel" ] || panel="unknown"
fi

reason=""
if [ "$mb" -ge "$HIGH_MB" ]; then
    reason="high mark: ${mb}MB >= ${HIGH_MB}MB"
elif [ "$mb" -ge "$IDLE_MB" ] && [ "$panel" = "off" ]; then
    reason="idle mark: ${mb}MB >= ${IDLE_MB}MB and panel is off"
fi

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

echo "shm-guard: restarting kiosk -- ${reason} (shm=${df_mb}MB maps=${map_mb}MB panel=${panel})"
echo "$now" > "$STAMP"
systemctl --user restart flightradar-kiosk.service
