#!/bin/sh
# Keeps the kiosk healthy without anyone watching it. Three jobs, in order of
# how badly they fail if left alone:
#
#   1. Repair a WINDOWED browser. Chromium restarted while the panel is
#      blanked comes up with a tab bar, an address bar and the desktop behind
#      it, even with --kiosk on its command line -- it cannot take an output
#      that is off and never retries. This is checked every run and repaired,
#      because it is the failure a recipient would just live with.
#   2. Bound Chromium's shared-memory leak (~200 MB/h of rendering on this
#      hardware) before /dev/shm fills and the display freezes on a stale
#      frame. Reload first, restart only if that is not enough.
#   3. Do the nightly reset, when called with SHMGUARD_FORCE=1.
#
# Runs as a user unit, like the kiosk it manages.
set -eu

STATE="${STATE_DIRECTORY:-$HOME/.local/state/flightradar-shmguard}"
RELOAD_STAMP="$STATE/last-reload"
RESTART_STAMP="$STATE/last-restart"

# A reload frees memory only while there is not much of it: measured, it
# recovered 52% at 151MB and 36% at 124MB, but 0% at 1010MB and 0% at 1404MB.
# So reload EARLY, where it still works, rather than as a last resort. These
# were 900/1500 and reloads were consistently useless by the time they fired.
RELOAD_IDLE_MB="${SHMGUARD_RELOAD_IDLE_MB:-300}"   # panel blanked: invisible, so act early
RELOAD_ON_MB="${SHMGUARD_RELOAD_ON_MB:-700}"       # panel on: still cheaper than a restart
RESTART_MB="${SHMGUARD_RESTART_MB:-1400}"          # last resort; failures start ~2100MB
RELOAD_MIN_S="${SHMGUARD_RELOAD_MIN_S:-600}"
RESTART_MIN_S="${SHMGUARD_RESTART_MIN_S:-1800}"
RESTART_SETTLE_S="${SHMGUARD_RESTART_SETTLE_S:-25}"
# Mean brightness of the top-left corner. Measured on this panel: 0.0
# fullscreen, 231.7 windowed. Anything near the middle means something
# unexpected is on screen, so treat it as broken and repair it.
FULLSCREEN_MAX="${SHMGUARD_FULLSCREEN_MAX:-60}"
FORCE="${SHMGUARD_FORCE:-0}"
RELOAD_REQUEST="${XDG_RUNTIME_DIR:-/tmp}/flightradar-reload-request"

mkdir -p "$STATE"

# Never act on a kiosk that is not running: restarting a stopped or failed
# unit turns an unrelated problem into a restart loop.
if [ "$(systemctl --user is-active flightradar-kiosk.service)" != "active" ]; then
    echo "shm-guard: kiosk not active, nothing to do"; exit 0
fi

WD=$(basename "$(ls "$XDG_RUNTIME_DIR"/wayland-*[0-9] 2>/dev/null | head -1)" 2>/dev/null || true)
panel="unknown"
if [ -n "${WD:-}" ]; then
    panel=$(WAYLAND_DISPLAY="$WD" wlopm 2>/dev/null | awk '/HDMI/ {print $2}' || echo unknown)
    [ -n "$panel" ] || panel="unknown"
fi

measure() {
    df_mb=$(df -m /dev/shm 2>/dev/null | awk 'NR==2 {print $3}' || echo 0)
    # Both /dev/shm usage AND the renderers' mappings, acting on whichever is
    # larger. They diverge: /etc/chromium.d/dev-shm adds --disable-dev-shm-usage
    # when /dev/shm has under 3.8GB free at launch, so after one bad day
    # Chromium moves its backing to /tmp and the df number stops tracking.
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
        continue
print(tot // 1048576)
PY
)
    [ -n "$df_mb" ] || df_mb=0
    [ -n "$map_mb" ] || map_mb=0
    mb="$df_mb"; [ "$map_mb" -gt "$mb" ] && mb="$map_mb"
    # Explicit success: under `set -e` the AND-OR list above is the last
    # command in this function, so whenever map_mb is not the larger one the
    # function returns non-zero and takes the whole script down with it,
    # silently, before a single threshold is evaluated.
    return 0
}

# Mean brightness of the top-left corner of the actual screen. -1 if it
# cannot be read, which is treated as "do not judge".
screen_topleft() {
    [ -n "${WD:-}" ] || { echo "-1"; return 0; }
    WAYLAND_DISPLAY="$WD" grim -t ppm - 2>/dev/null | python3 -c '
import sys
d = sys.stdin.buffer.read()
if not d.startswith(b"P6"):
    print("-1"); raise SystemExit
parts = []; i = 2
while len(parts) < 3:
    while i < len(d) and d[i:i+1].isspace(): i += 1
    if d[i:i+1] == b"#":
        while d[i:i+1] not in (b"\n", b""): i += 1
        continue
    j = i
    while j < len(d) and not d[j:j+1].isspace(): j += 1
    parts.append(int(d[i:j])); i = j
i += 1
w, h, _ = parts; px = d[i:]
tot = n = 0
for y in range(36):
    base = y * w * 3
    for x in range(0, 140, 3):
        o = base + x * 3
        if o + 2 < len(px):
            tot += px[o] + px[o+1] + px[o+2]; n += 3
print(int(tot / n) if n else -1)
' 2>/dev/null || echo "-1"
}

rate_ok() {   # stamp  min_seconds
    [ -f "$1" ] || return 0
    last=$(cat "$1" 2>/dev/null || echo 0)
    case "$last" in ''|*[!0-9]*) last=0 ;; esac
    [ $(( $(date +%s) - last )) -ge "$2" ]
}

restart_kiosk() {   # reason
    echo "shm-guard: restarting kiosk -- $1"
    date +%s > "$RESTART_STAMP"
    # CHROMIUM MUST NOT BE RESTARTED WHILE THE PANEL IS BLANKED -- it comes up
    # windowed. Reproduced both ways on the device. This matters most for the
    # 04:00 restart, which by design runs with the panel blanked.
    was_off=0
    if [ "$panel" = "off" ] && [ -n "${WD:-}" ]; then
        was_off=1
        echo "shm-guard: panel is off -- waking it first, or Chromium restarts windowed"
        WAYLAND_DISPLAY="$WD" wlopm --on HDMI-A-1 >/dev/null 2>&1 || true
        sleep 2
    fi
    systemctl --user restart flightradar-kiosk.service
    if [ "$was_off" = "1" ]; then
        sleep "$RESTART_SETTLE_S"
        WAYLAND_DISPLAY="$WD" wlopm --off HDMI-A-1 >/dev/null 2>&1 || true
        echo "shm-guard: panel blanked again after ${RESTART_SETTLE_S}s"
    fi
}

# ---- 1. is the browser actually fullscreen? --------------------------------
# Only meaningful with the panel on; a blanked panel reads black, which is
# indistinguishable from a healthy kiosk and would never false-alarm anyway.
if [ "$panel" = "on" ]; then
    tl=$(screen_topleft)
    case "$tl" in ''|*[!0-9-]*) tl=-1 ;; esac
    if [ "$tl" -ge 0 ] && [ "$tl" -ge "$FULLSCREEN_MAX" ]; then
        if rate_ok "$RESTART_STAMP" "$RESTART_MIN_S"; then
            restart_kiosk "browser is NOT fullscreen (corner brightness ${tl}, fullscreen reads ~0)"
            exit 0
        fi
        echo "shm-guard: browser not fullscreen (${tl}) but a restart is rate-limited -- holding"
        exit 0
    fi
fi

measure

# ---- 2/3. the leak ---------------------------------------------------------
if [ "$FORCE" = "1" ]; then
    restart_kiosk "scheduled nightly reset (shm=${df_mb}MB maps=${map_mb}MB panel=${panel})"
    exit 0
fi

if [ "$mb" -ge "$RESTART_MB" ]; then
    if rate_ok "$RESTART_STAMP" "$RESTART_MIN_S"; then
        restart_kiosk "${mb}MB >= ${RESTART_MB}MB (panel=${panel})"
    else
        echo "shm-guard: ${mb}MB over the restart mark but rate-limited -- holding"
    fi
    exit 0
fi

want_reload=0
if   [ "$panel" = "off" ] && [ "$mb" -ge "$RELOAD_IDLE_MB" ]; then want_reload=1; why="idle mark ${mb}MB >= ${RELOAD_IDLE_MB}MB"
elif [ "$mb" -ge "$RELOAD_ON_MB" ];                          then want_reload=1; why="${mb}MB >= ${RELOAD_ON_MB}MB"
fi

if [ "$want_reload" = "0" ]; then
    echo "shm-guard: ${mb}MB (shm=${df_mb} maps=${map_mb}) panel=${panel} -- below thresholds"
    exit 0
fi

if ! rate_ok "$RELOAD_STAMP" "$RELOAD_MIN_S"; then
    echo "shm-guard: ${why} but a reload is rate-limited -- holding"
    exit 0
fi

echo "shm-guard: ${why} -- asking the page to reload (panel=${panel})"
date +%s > "$RELOAD_STAMP"
: > "$RELOAD_REQUEST" 2>/dev/null || true
sleep 45
before="$mb"
measure
freed=$(( before - mb ))
echo "shm-guard: reload ${before}MB -> ${mb}MB (freed ${freed}MB)"
# Do not leave an unconsumed request behind to reload the fresh page too.
rm -f "$RELOAD_REQUEST" 2>/dev/null || true

if [ "$mb" -ge "$RESTART_MB" ] && rate_ok "$RESTART_STAMP" "$RESTART_MIN_S"; then
    restart_kiosk "reload left it at ${mb}MB, over the ${RESTART_MB}MB mark"
fi
