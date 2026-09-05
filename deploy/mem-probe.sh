#!/bin/sh
# Samples the kiosk's memory footprint so a slow leak is visible as a curve
# rather than as a frozen screen somebody happens to walk past.
#
# Written after Chromium's GPU command buffer failed to allocate on this
# device (see the watchdog in wake-listener.py). By the time it failed, the
# browser was holding 2.1GB of shared memory across 1,011 shm/memfd mappings;
# a restart returned it to 330MB. What grows, and how fast, is the open
# question -- so this records the pieces that would answer it: total shared
# memory, the /dev/shm arena the GPU transfer buffers come from, and RSS plus
# mapping counts broken out per Chromium process type, since a leak in the
# renderer and a leak in the GPU process point at completely different causes.
#
# Deliberately cheap: one pass over a handful of /proc files every few
# minutes, on a Pi that is already thermally tight. The GPU error count is
# scoped to the last interval rather than the whole boot so the journal is
# not re-scanned from the beginning on every sample.
#
# Install: /opt/flightradar/mem-probe.sh, run by flightradar-memprobe.timer.
set -eu

OUT="${STATE_DIRECTORY:-/var/lib/flightradar-memprobe}/samples.csv"
INTERVAL_LABEL="${1:-5min}"

if [ ! -f "$OUT" ]; then
    echo "ts,kiosk_uptime_s,shmem_kb,shm_used_kb,browser_rss_kb,renderer_rss_kb,gpu_rss_kb,browser_maps,renderer_maps,gpu_maps,gpu_errors,aircraft,temp_c,throttled" > "$OUT"
fi

# Chromium's process types are only distinguishable from their command line.
main_pid=$(systemctl --user -M <user>@ show flightradar-kiosk.service -p ExecMainPID --value 2>/dev/null || echo 0)
[ -n "$main_pid" ] || main_pid=0

uptime_s=0
if [ "$main_pid" != "0" ] && [ -d "/proc/$main_pid" ]; then
    start_ticks=$(awk '{print $22}' "/proc/$main_pid/stat" 2>/dev/null || echo 0)
    hz=$(getconf CLK_TCK)
    boot_s=$(awk '/^btime/ {print $2}' /proc/stat)
    now_s=$(date +%s)
    uptime_s=$(( now_s - boot_s - start_ticks / hz ))
fi

rss_of() { [ -n "$1" ] && awk '/^VmRSS:/ {print $2}' "/proc/$1/status" 2>/dev/null || echo 0; }
# Shared-memory mappings are the ones that grew before the failure: /dev/shm
# files and anonymous memfds, both of which back GPU transfer buffers.
maps_of() { [ -n "$1" ] && grep -c -E '/dev/shm|memfd' "/proc/$1/maps" 2>/dev/null || echo 0; }

pid_of_type() {
    for p in $(pgrep -f 'chromium' 2>/dev/null); do
        if tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | grep -q -- "--type=$1"; then
            echo "$p"; return
        fi
    done
}

# The browser process is the one with no --type= at all.
browser_pid=""
for p in $(pgrep -f 'chromium' 2>/dev/null); do
    if ! tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | grep -q -- '--type='; then
        browser_pid="$p"; break
    fi
done
renderer_pid=$(pid_of_type renderer)
gpu_pid=$(pid_of_type gpu-process)

shmem_kb=$(awk '/^Shmem:/ {print $2}' /proc/meminfo)
shm_used_kb=$(df -k /dev/shm | awk 'NR==2 {print $3}')

gpu_errors=$(journalctl --user-unit flightradar-kiosk.service --since "-${INTERVAL_LABEL}" --no-pager 2>/dev/null \
             | grep -c 'AllocateRingBuffer\|ContextResult' || true)

aircraft=$(curl -s --max-time 5 http://127.0.0.1/tar1090/data/aircraft.json 2>/dev/null \
           | python3 -c 'import json,sys
try: print(len(json.load(sys.stdin).get("aircraft", [])))
except Exception: print(-1)' 2>/dev/null || echo -1)

temp_c=$(vcgencmd measure_temp 2>/dev/null | tr -dc '0-9.' || echo 0)
throttled=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2 || echo NA)

printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "$(date -Is)" "$uptime_s" "$shmem_kb" "$shm_used_kb" \
    "$(rss_of "$browser_pid")" "$(rss_of "$renderer_pid")" "$(rss_of "$gpu_pid")" \
    "$(maps_of "$browser_pid")" "$(maps_of "$renderer_pid")" "$(maps_of "$gpu_pid")" \
    "$gpu_errors" "$aircraft" "$temp_c" "$throttled" >> "$OUT"
