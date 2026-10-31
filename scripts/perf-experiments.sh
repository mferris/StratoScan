#!/bin/sh
# Measure where the kiosk's CPU goes, one suspect at a time (roadmap 1.11, #35).
#
# Run from a development machine. For each experiment it writes the page's
# switches to /var/www/html/data/perf-debug.json on the unit, asks the page to
# reload (the same channel the shm guard uses), wakes the panel -- a blanked
# panel draws nothing and would read artificially cheap -- lets it settle, then
# runs scripts/perf-probe.py over SSH. Afterwards the switches file is removed
# and the page reloaded, leaving the unit exactly as it was.
#
# Usage: sh scripts/perf-experiments.sh user@host [minutes-per-experiment]
set -u
HOST="${1:?usage: sh scripts/perf-experiments.sh user@host [minutes]}"
MIN="${2:-5}"
SETTLE=75
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="${PERF_OUT:-/tmp/perf-experiments-$(date +%Y%m%d-%H%M).txt}"

set_flags() {  # <json or empty>
    if [ -n "$1" ]; then
        echo "$1" | ssh -o ConnectTimeout=10 "$HOST" 'sudo tee /var/www/html/data/perf-debug.json >/dev/null'
    else
        ssh -o ConnectTimeout=10 "$HOST" 'sudo rm -f /var/www/html/data/perf-debug.json'
    fi
    # The empty body (-d "") matters: lighttpd refuses a POST with no
    # Content-Length with 411, so the wake never arrives (2026-10-30, #81).
    ssh -o ConnectTimeout=10 "$HOST" 'curl -s -m 10 -o /dev/null -d "" "http://127.0.0.1/wake?why=perf"; touch "/run/user/$(id -u)/stratoscan-reload-request"'
}

panel() {
    ssh -o ConnectTimeout=10 "$HOST" 'WD=$(basename $(ls /run/user/$(id -u)/wayland-*[0-9] | head -1)); XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$WD wlopm 2>/dev/null | awk "/HDMI/ {print \$2}"'
}

run() {  # <label> <json>
    set_flags "$2"
    sleep "$SETTLE"
    ssh -o ConnectTimeout=10 "$HOST" 'curl -s -m 10 -o /dev/null -d "" "http://127.0.0.1/wake?why=perf"'
    before=$(panel)
    res=$(ssh -o ConnectTimeout=10 "$HOST" python3 - --minutes "$MIN" --every 5 --json < "$HERE/perf-probe.py")
    after=$(panel)
    printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$before/$after" "$(echo "$res" | tr -d '\n' | tr -s ' ')" >> "$OUT"
    echo "$(date +%T) done: $1 (panel $before/$after)"
}

: > "$OUT"
echo "$(date +%T) experiments, $MIN min each, results in $OUT"
run baseline     ''
run noLabels     '{"noLabels": true}'
run noMap        '{"noMap": true}'
run noMapFilter  '{"noMapFilter": true}'
run tinyCanvas   '{"tinyCanvas": true}'
run noSweep      '{"noSweep": true}'
run allOff       '{"noLabels": true, "noMap": true, "noSweep": true, "tinyCanvas": true}'
run fps5         '{"fps": 5}'
set_flags ''
echo "$(date +%T) finished; switches removed, page reloaded"
