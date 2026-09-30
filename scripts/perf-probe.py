#!/usr/bin/env python3
"""
Measure what the kiosk costs to run: CPU per Chromium process, the Pi's
temperature and fan, throttling, and how much traffic was on screen while
it was measured. Roadmap 1.11 (#35) is judged by these numbers, and every
later change to the kiosk is checked against them.

Read-only. It installs nothing and changes nothing, so it is run from a
development machine by piping it over SSH:

    ssh <user>@<radar> python3 - --minutes 10 < scripts/perf-probe.py

Options:
    --minutes N    how long to sample (default 10)
    --every S      seconds between samples (default 5)
    --json         print the summary as JSON instead of a table

Traffic matters as much as code: the renderer's cost grows with the number of
aircraft drawn. Compare runs taken at a similar time of day, and read the
aircraft column before reading anything else.
"""
import argparse
import glob
import json
import re
import os
import statistics
import subprocess
import sys
import time

CLK_TCK = os.sysconf("SC_CLK_TCK")
AIRCRAFT_JSON = "/run/readsb/aircraft.json"
TEMP = "/sys/class/thermal/thermal_zone0/temp"
FAN_STEP = "/sys/class/thermal/cooling_device0/cur_state"
TYPE_ARG = re.compile(rb"--type=([a-z-]+)")


def chromium_processes():
    """{pid: role} for every Chromium process. The role is its --type
    (gpu-process, renderer, utility...), or "browser" for the parent."""
    procs = {}
    for d in glob.glob("/proc/[0-9]*"):
        try:
            with open(d + "/comm") as f:
                if f.read().strip() != "chromium":
                    continue
            with open(d + "/cmdline", "rb") as f:
                args = f.read().split(b"\0")
        except OSError:
            continue
        # Chromium rewrites its children's command lines into one space-joined
        # string, so --type= has to be found anywhere, not as its own argument.
        role = "browser"
        m = TYPE_ARG.search(b" ".join(args))
        if m:
            role = m.group(1).decode()
        procs[int(d[6:])] = role
    return procs


def cpu_ticks(pid):
    """utime + stime for one process, or None if it has gone."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            fields = f.read().rsplit(")", 1)[1].split()
        return int(fields[11]) + int(fields[12])
    except (OSError, IndexError, ValueError):
        return None


def rss_mb(pid):
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def read_int(path):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def fan_rpm():
    for path in glob.glob("/sys/devices/platform/cooling_fan/hwmon/*/fan1_input"):
        return read_int(path)
    return None


def throttled():
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                             text=True, timeout=5).stdout
        return int(out.strip().split("=")[1], 16)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def aircraft_on_screen():
    """Aircraft with a fresh position -- roughly what the radar is drawing."""
    try:
        with open(AIRCRAFT_JSON) as f:
            ac = json.load(f).get("aircraft", [])
    except (OSError, ValueError):
        return None
    return sum(1 for a in ac if "lat" in a and a.get("seen_pos", 99) < 30)


def summarise(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return {"mean": round(statistics.fmean(vals), 1), "max": round(max(vals), 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--every", type=float, default=5)
    ap.add_argument("--json", action="store_true")
    opt = ap.parse_args()

    samples = {"cpu": {}, "temp": [], "fan": [], "step": [], "aircraft": []}
    worst_throttle = 0
    prev = {pid: cpu_ticks(pid) for pid in chromium_processes()}
    prev_t = time.monotonic()
    end = prev_t + opt.minutes * 60
    started = time.strftime("%Y-%m-%d %H:%M")

    while time.monotonic() < end:
        time.sleep(opt.every)
        now_t = time.monotonic()
        dt = now_t - prev_t
        procs = chromium_processes()
        by_role = {}
        cur = {}
        for pid, role in procs.items():
            t = cpu_ticks(pid)
            cur[pid] = t
            if t is None or prev.get(pid) is None:
                continue          # started or ended mid-interval: skip, don't guess
            pct = (t - prev[pid]) / CLK_TCK / dt * 100   # % of ONE core
            by_role[role] = by_role.get(role, 0) + pct
        for role, pct in by_role.items():
            samples["cpu"].setdefault(role, []).append(pct)
        samples["cpu"].setdefault("chromium total", []).append(sum(by_role.values()))
        prev, prev_t = cur, now_t

        t = read_int(TEMP)
        samples["temp"].append(t / 1000 if t is not None else None)
        samples["fan"].append(fan_rpm())
        samples["step"].append(read_int(FAN_STEP))
        samples["aircraft"].append(aircraft_on_screen())
        th = throttled()
        if th:
            worst_throttle |= th

    procs = chromium_processes()
    result = {
        "started": started,
        "minutes": opt.minutes,
        "samples": len(samples["temp"]),
        "aircraft": summarise(samples["aircraft"]),
        "cpu_pct_of_one_core": {r: summarise(v) for r, v in sorted(samples["cpu"].items())},
        "temp_c": summarise(samples["temp"]),
        "fan_rpm": summarise(samples["fan"]),
        "fan_step": summarise(samples["step"]),
        "throttled_flags": hex(worst_throttle),
        "chromium_processes": len(procs),
        "chromium_rss_mb": round(sum(rss_mb(p) for p in procs)),
    }

    if opt.json:
        print(json.dumps(result, indent=1))
        return
    print(f"perf-probe  {result['started']}  {opt.minutes:g} min, "
          f"{result['samples']} samples every {opt.every:g}s")
    print(f"  aircraft on screen   {fmt(result['aircraft'])}")
    for role, s in result["cpu_pct_of_one_core"].items():
        print(f"  cpu {role:<17}{fmt(s)}  (% of one core)")
    print(f"  temperature C        {fmt(result['temp_c'])}")
    print(f"  fan rpm              {fmt(result['fan_rpm'])}")
    print(f"  fan step (0-4)       {fmt(result['fan_step'])}")
    print(f"  throttled flags      {result['throttled_flags']}  {explain_throttle(worst_throttle)}")
    print(f"  chromium             {result['chromium_processes']} processes, "
          f"{result['chromium_rss_mb']} MB")


THROTTLE_BITS = {0: "under-voltage now", 1: "frequency capped now", 2: "throttled now",
                 3: "soft temperature limit now", 16: "under-voltage has occurred",
                 17: "frequency cap has occurred", 18: "throttling has occurred",
                 19: "soft temperature limit has occurred"}


def explain_throttle(v):
    return "; ".join(t for b, t in THROTTLE_BITS.items() if v >> b & 1) or "none"


def fmt(s):
    return "n/a" if s is None else f"mean {s['mean']:>6}   max {s['max']:>6}"


if __name__ == "__main__":
    sys.exit(main())
