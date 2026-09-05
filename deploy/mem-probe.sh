#!/bin/sh
# Samples the kiosk's memory footprint so a slow leak is visible as a curve
# rather than as a frozen screen somebody happens to walk past.
#
# Written after Chromium's GPU command buffer failed to allocate on this
# device (see the watchdog in wake-listener.py). By the time it failed, the
# browser was holding 2.1GB of shared memory across 1,011 shm/memfd mappings;
# a restart returned it to 330MB. What grows, and how fast, is the open
# question -- so this records the pieces that would answer it: total shared
# memory, the /dev/shm arena the transfer buffers come from, and RSS plus
# shared-memory footprint broken out per Chromium process type, since a leak
# in the renderer and a leak in the GPU process point at different causes.
#
# TWO BUGS IN v1, BOTH OF WHICH MADE A RUNNING LEAK LOOK FIXED:
#
#   1. It sampled the FIRST process of each type. Chromium runs more than one
#      renderer, and for 308 consecutive samples this picked the idle one --
#      reporting renderer_maps=10, flat as a board, while the other renderer
#      climbed to 776 mappings and 1.5GB. A flat column was read as proof the
#      leak was gone. Every type is now summed across every process of that
#      type, and n_renderers is recorded so a changing process count cannot
#      masquerade as a changing footprint.
#
#   2. It recorded mapping COUNTS but not BYTES. The leak is 2MB blocks, so
#      counts and bytes happen to track here -- but a pool that grows its
#      blocks rather than its block count would be invisible. Both are logged.
#
# attributed_pct is the check that can fail: the shared memory this probe
# attributes to Chromium, over the kernel's system-wide Shmem. If the leak is
# inside a process this probe is looking at, that number stays high. If it
# drops while Shmem climbs, the growth has moved somewhere the probe cannot
# see -- and the flat per-process columns mean nothing, which is exactly the
# failure mode above.
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

HEADER="ts,kiosk_uptime_s,shmem_kb,shm_used_kb,browser_rss_kb,renderer_rss_kb,gpu_rss_kb,browser_maps,renderer_maps,gpu_maps,browser_shm_kb,renderer_shm_kb,gpu_shm_kb,n_renderers,attributed_pct,gpu_errors,aircraft,temp_c,throttled"
if [ ! -f "$OUT" ]; then
    echo "$HEADER" > "$OUT"
elif [ "$(head -1 "$OUT")" != "$HEADER" ]; then
    # A v1 file. Keep it -- it is the record of the leak being missed -- but
    # do not append a wider row to it, which would silently corrupt both.
    mv "$OUT" "${OUT%.csv}-v1.csv"
    echo "$HEADER" > "$OUT"
fi

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

shmem_kb=$(awk '/^Shmem:/ {print $2}' /proc/meminfo)
shm_used_kb=$(df -k /dev/shm | awk 'NR==2 {print $3}')

# One pass over every Chromium process, aggregated by type. Done in python
# rather than a shell loop because it has to sum byte ranges out of
# /proc/PID/maps, and because a shell loop over pgrep output is what picked
# the wrong renderer in v1.
stats=$(python3 - "$shmem_kb" <<'PY' 2>/dev/null || echo "0 0 0 0 0 0 0 0 0 0 0"
import os, sys

# The leaked mappings are unlinked shm files -- they appear as
# "/dev/shm/.org.chromium.Chromium.XXXXXX (deleted)". memfd-backed ones show
# as "/memfd:...". Match on the backing name, and count a mapping whether or
# not the file behind it still has a directory entry: unlinked is the normal
# state for these, not an edge case.
def is_shm(path):
    return "/dev/shm" in path or "memfd:" in path

agg = {}          # type -> [rss_kb, n_maps, shm_kb, n_procs]
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", "replace")
    except OSError:
        continue
    if "chromium" not in cmd:
        continue
    # Process type comes only from the command line. No --type= is the browser.
    #
    # Split on whitespace AND NULs. /proc/PID/cmdline is documented as
    # NUL-separated, but Chromium rewrites its own argv into a single
    # space-separated string with one trailing NUL so that ps shows a useful
    # process title -- so a NUL-only split yields one giant argument and every
    # process is misfiled as the browser. That is not a hypothetical: it is
    # what the first version of this fix did, putting all 891 mappings under
    # "browser" and reporting n_renderers=0.
    t = "browser"
    for arg in cmd.replace("\0", " ").split():
        if arg.startswith("--type="):
            t = arg[len("--type="):]
            break
    rss = maps = shm = 0
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmRSS:"):
                rss = int(line.split()[1]); break
        for line in open(f"/proc/{pid}/maps"):
            f = line.split(None, 5)
            if len(f) < 6 or not is_shm(f[5]):
                continue
            a, b = f[0].split("-")
            maps += 1
            shm += (int(b, 16) - int(a, 16)) // 1024
    except OSError:
        continue          # process exited mid-read; skip rather than log a zero
    e = agg.setdefault(t, [0, 0, 0, 0])
    e[0] += rss; e[1] += maps; e[2] += shm; e[3] += 1

def g(t, i):
    return agg.get(t, [0, 0, 0, 0])[i]

total_shm = sum(v[2] for v in agg.values())
sys_shm = int(sys.argv[1]) or 1
print(g("browser",0), g("renderer",0), g("gpu-process",0),
      g("browser",1), g("renderer",1), g("gpu-process",1),
      g("browser",2), g("renderer",2), g("gpu-process",2),
      g("renderer",3), round(100.0 * total_shm / sys_shm, 1))
PY
)

gpu_errors=$(journalctl --user-unit flightradar-kiosk.service --since "-${INTERVAL_LABEL}" --no-pager 2>/dev/null \
             | grep -c 'AllocateRingBuffer\|ContextResult' || true)

aircraft=$(curl -s --max-time 5 http://127.0.0.1/tar1090/data/aircraft.json 2>/dev/null \
           | python3 -c 'import json,sys
try: print(len(json.load(sys.stdin).get("aircraft", [])))
except Exception: print(-1)' 2>/dev/null || echo -1)

temp_c=$(vcgencmd measure_temp 2>/dev/null | tr -dc '0-9.' || echo 0)
throttled=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2 || echo NA)

# shellcheck disable=SC2086  -- $stats is eleven space-separated fields
printf '%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "$(date -Is)" "$uptime_s" "$shmem_kb" "$shm_used_kb" \
    "$(echo $stats | tr ' ' ',')" \
    "$gpu_errors" "$aircraft" "$temp_c" "$throttled" >> "$OUT"
