#!/usr/bin/env python3
"""Operating-system updates that the daily security updates leave alone (#73).

Every radar installs Debian's and the Raspberry Pi Foundation's security
updates by itself each day (deploy/52stratoscan-unattended-upgrades). That
file holds back a few packages on purpose, because a bad one leaves a radar in
someone else's house unable to boot, off the network, or with a broken screen:

  chromium        the browser that draws the radar
  linux-image-*   the kernel, and the boot files that come with it
  firmware-*      the Wi-Fi chip's firmware

Held is not the same as never updated. This program updates them on a tested
path instead:

  1. THE VERSIONS ARE CHOSEN AND TESTED FIRST. os-packages.json, shipped with
     each signed release, names the exact versions to install. It reaches a
     radar only through the release rings (ota.py point 4): RDU, ring 0, runs
     them first, and each later ring gets them after its soak. A radar never
     moves a held package to a version nobody has tried.

  2. CHROMIUM PROVES ITSELF LIKE A RELEASE DOES. The versions it replaces are
     kept as .debs first; after the upgrade the kiosk restarts and the new
     browser must paint a frame within ota.py's limit, or the kept versions go
     back and that version is never tried again on this radar.

  3. A NEW KERNEL BOOTS ONCE ON TRIAL. Its boot files go into their own folder
     on the boot partition, and the Pi's firmware is asked to boot from there
     for one boot only ("tryboot"). The radar's normal boot files are left as
     they were. If the trial boot comes up and paints, it is made permanent; if
     it fails, hangs or is power-cycled, the next boot is the old kernel, and
     the new one is removed. A power cycle always gets the old kernel back.

  4. PATCHES TAKE EFFECT. A patched library only replaces the old one in
     memory when the programs using it restart. In the small hours, with the
     panel asleep, a radar that has programs running on replaced libraries
     restarts, at most once a week.

The EEPROM bootloader (rpi-eeprom) stays held: it is outside this path.

Usage:  os-update.py run                daily: install the tested versions
        os-update.py confirm            at boot: finish or undo a kernel trial
        os-update.py restart-if-needed  small hours: restart if patches wait
        os-update.py status             what the heartbeat reports
        os-update.py candidates         for the maintainer, on ring 0: the
                                        newest versions apt offers for this
                                        radar's held packages, written as an
                                        os-packages.json
"""
import fcntl
import fnmatch
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OPT_ROOT = os.environ.get("STRATOSCAN_OPT_ROOT", "/opt/stratoscan")
PACKAGES_FILE = os.environ.get("STRATOSCAN_OS_PACKAGES", os.path.join(OPT_ROOT, "os-packages.json"))
STATE_DIR = os.environ.get("STRATOSCAN_OTA_STATE", "/var/lib/stratoscan-ota")
STATE = os.path.join(STATE_DIR, "os-update.json")
STASH = os.path.join(STATE_DIR, "os-stash")
LOCK = os.path.join(STATE_DIR, "os-update.lock")
BOOT_DIR = os.environ.get("STRATOSCAN_BOOT_DIR", "/boot/firmware")
MODULES_DIR = os.environ.get("STRATOSCAN_MODULES_DIR", "/lib/modules")
NEXT_DIR = "stratoscan-next"          # the trial's boot files, under BOOT_DIR
PREV_DIR = "stratoscan-prev"          # the radar's own boot files, kept during a trial
TRYBOOT_FLAG = "/proc/device-tree/chosen/bootloader/tryboot"
UU_STAMP = "/var/lib/apt/periodic/unattended-upgrades-stamp"
WAKE_STATE_URL = os.environ.get("STRATOSCAN_WAKE_STATE_URL", "http://127.0.0.1/wake/state")

# What this program may move, by class. Anything else named in
# os-packages.json is ignored: the daily security updates own it.
APP_PACKAGES = ("chromium", "chromium-*", "rpi-chromium-mods")
BOOT_PACKAGES = ("linux-image-*", "linux-headers-*", "linux-kbuild-*", "raspi-firmware",
                 "raspberrypi-kernel", "raspberrypi-bootloader", "firmware-*")
NEVER = ("rpi-eeprom",)

TRIAL_PAINT_S = 300            # a whole boot, not just a kiosk restart
RESTART_MIN_UPTIME_S = 20 * 3600
RESTART_MIN_GAP_S = 6 * 86400
APT_TIMEOUT_S = 1800

_ota = None


def ota():
    """ota.py, for its paint check and kiosk restart: the same proof a
    release uses, not a second copy of it."""
    global _ota
    if _ota is None:
        spec = importlib.util.spec_from_file_location("stratoscan_ota", os.path.join(HERE, "ota.py"))
        _ota = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_ota)
    return _ota


class Fail(Exception):
    pass


def log(msg):
    print(f"os-update: {msg}", flush=True)


def run_cmd(cmd, timeout=120, cwd=None):
    """(returncode, stdout, stderr). The one place commands run, so the tests
    can stand in for apt and dpkg."""
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive", LC_ALL="C")
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
    return p.returncode, p.stdout, p.stderr


# ---- state ---------------------------------------------------------------

def load_state():
    try:
        with open(STATE) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    os.chmod(tmp, 0o644)        # the heartbeat reads it
    os.replace(tmp, STATE)


# ---- packages ------------------------------------------------------------

def package_class(name):
    if any(fnmatch.fnmatch(name, p) for p in NEVER):
        return None
    if any(fnmatch.fnmatch(name, p) for p in APP_PACKAGES):
        return "app"
    if any(fnmatch.fnmatch(name, p) for p in BOOT_PACKAGES):
        return "boot"
    return None


def installed_packages():
    """{name: version} of every installed package."""
    rc, out, _ = run_cmd(["dpkg-query", "-W", "-f", "${Package}\t${Version}\t${db:Status-Abbrev}\n"])
    have = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[2].startswith("ii"):
            have[parts[0]] = parts[1]
    return have


def version_gt(a, b):
    rc, _, _ = run_cmd(["dpkg", "--compare-versions", a, "gt", b], timeout=10)
    return rc == 0


def wanted_versions():
    """The tested versions from os-packages.json, or {} when there are none."""
    try:
        with open(PACKAGES_FILE) as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return {}
    pk = doc.get("packages") if isinstance(doc, dict) and doc.get("kind") == "os-packages" else None
    if not isinstance(pk, dict):
        return {}
    out = {}
    for name, ver in pk.items():
        if not (isinstance(name, str) and isinstance(ver, str)) or not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", name):
            continue
        if package_class(name) is None:
            log(f"ignoring {name}: not one this program updates")
            continue
        out[name] = ver
    return out


def plan(wanted, have, failed):
    """[(name, from, to, class)] for each installed package whose tested
    version is newer than what it has and has not failed here before."""
    steps = []
    for name, ver in sorted(wanted.items()):
        cur = have.get(name)
        if cur is None or cur == ver:
            continue
        if failed.get(name) == ver:
            continue
        if version_gt(ver, cur):
            steps.append((name, cur, ver, package_class(name)))
    return steps


def stash(steps):
    """Keep the versions being replaced, as .debs, or refuse: an upgrade with
    no way back is not one to make unattended."""
    shutil.rmtree(STASH, ignore_errors=True)
    os.makedirs(STASH)
    for name, cur, _, _ in steps:
        rc, _, _ = run_cmd(["apt-get", "download", "-q", f"{name}={cur}"], timeout=600, cwd=STASH)
        if rc != 0:
            # No longer offered by the archive: rebuild it from what is installed.
            rc, _, _ = run_cmd(["dpkg-repack", name], timeout=600, cwd=STASH)
        if rc != 0:
            raise Fail(f"could not keep {name} {cur} to go back to; not upgrading")
    log(f"kept {len(steps)} package(s) to go back to")


def restore_stash():
    debs = sorted(os.path.join(STASH, f) for f in os.listdir(STASH) if f.endswith(".deb")) \
        if os.path.isdir(STASH) else []
    if not debs:
        return False
    rc, _, err = run_cmd(["dpkg", "-i", "--force-confold", *debs], timeout=APT_TIMEOUT_S)
    if rc != 0:
        log(f"putting the kept versions back: {err.strip()[-300:]}")
        run_cmd(["apt-get", "-f", "install", "-y", "-q"], timeout=APT_TIMEOUT_S)
    return True


def apt_install(steps):
    run_cmd(["apt-get", "update", "-q"], timeout=600)
    rc, _, err = run_cmd(
        ["apt-get", "install", "-y", "-q", "--no-install-recommends",
         "--allow-downgrades", "--allow-change-held-packages",
         "-o", "Dpkg::Options::=--force-confdef", "-o", "Dpkg::Options::=--force-confold",
         *[f"{name}={ver}" for name, _, ver, _ in steps]],
        timeout=APT_TIMEOUT_S)
    if rc != 0:
        raise Fail("apt could not install " + ", ".join(f"{n} {v}" for n, _, v, _ in steps)
                   + ": " + err.strip()[-300:])


# ---- Chromium: upgrade, prove, or put back --------------------------------

def update_app(steps, state):
    o = ota()
    stash(steps)
    o.wake_display()
    kiosk_was = o.kiosk_started_at()
    try:
        apt_install(steps)
    except Fail:
        restore_stash()
        raise
    o.restart_kiosk()
    if o.wait_for_new_paint(kiosk_was):
        log("installed and painting: " + ", ".join(f"{n} {v}" for n, _, v, _ in steps))
        state["result"] = {"at": int(time.time()), "ok": True,
                           "installed": {n: v for n, _, v, _ in steps}}
        return True
    log("no frame painted with the new browser -- putting the kept versions back")
    kiosk_was = o.kiosk_started_at()
    restore_stash()
    o.restart_kiosk()
    o.wait_for_new_paint(kiosk_was)
    for n, _, v, _ in steps:
        state.setdefault("failed", {})[n] = v
    state["result"] = {"at": int(time.time()), "ok": False,
                       "rolled_back": {n: v for n, _, v, _ in steps},
                       "why": "the display did not paint with the new browser"}
    return False


# ---- the kernel: one trial boot -------------------------------------------

def boot_files():
    """The kernel's files in the boot partition's root: kernels, initramfs,
    device trees and overlays. config.txt and cmdline.txt are the radar's own
    and are not among them."""
    names = []
    for f in sorted(os.listdir(BOOT_DIR)):
        if fnmatch.fnmatch(f, "kernel*.img") or f.startswith("initramfs") or f.endswith(".dtb"):
            names.append(f)
    if os.path.isdir(os.path.join(BOOT_DIR, "overlays")):
        names.append("overlays")
    return names


def copy_boot(names, src_dir, dst_dir):
    """Copy boot files so that a power cut at any moment leaves each one
    either old or new, never half-written: a file goes to a temporary name
    and is renamed over; a folder (overlays/) is copied whole beside the old
    one and swapped in."""
    os.makedirs(dst_dir, exist_ok=True)
    for n in names:
        s, d = os.path.join(src_dir, n), os.path.join(dst_dir, n)
        if os.path.isdir(s):
            new, old = d + ".stratoscan-new", d + ".stratoscan-old"
            shutil.rmtree(new, ignore_errors=True)
            shutil.rmtree(old, ignore_errors=True)
            shutil.copytree(s, new)
            if os.path.isdir(d):
                os.rename(d, old)
            os.rename(new, d)
            shutil.rmtree(old, ignore_errors=True)
        elif os.path.exists(s):
            tmp = d + ".stratoscan-tmp"
            shutil.copy2(s, tmp)
            with open(tmp, "rb") as f:
                os.fsync(f.fileno())
            os.replace(tmp, d)


def flavour(release):
    m = re.search(r"(rpi-[0-9a-z]+|v8|v7l?|2712)$", release)
    return m.group(1) if m else release


def module_dirs():
    try:
        return set(os.listdir(MODULES_DIR))
    except OSError:
        return set()


def tryboot_supported():
    return os.path.isdir(os.path.dirname(TRYBOOT_FLAG)) and os.path.isfile(os.path.join(BOOT_DIR, "config.txt"))


def booted_on_trial():
    try:
        with open(TRYBOOT_FLAG, "rb") as f:
            return int.from_bytes(f.read()[:4], "big") == 1
    except OSError:
        return False


def du(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, _, files in os.walk(path):
        total += sum(os.path.getsize(os.path.join(root, f)) for f in files)
    return total


def start_trial(steps, state):
    if not tryboot_supported():
        raise Fail("this radar's firmware cannot boot a trial; the kernel stays as it is")
    names = boot_files()
    need = sum(du(os.path.join(BOOT_DIR, n)) for n in names)
    st = os.statvfs(BOOT_DIR)
    if st.f_bavail * st.f_frsize < 3 * need:
        raise Fail("not enough room on the boot partition for a trial")
    stash(steps)
    prev, nxt = os.path.join(BOOT_DIR, PREV_DIR), os.path.join(BOOT_DIR, NEXT_DIR)
    shutil.rmtree(prev, ignore_errors=True)
    shutil.rmtree(nxt, ignore_errors=True)
    copy_boot(names, BOOT_DIR, prev)
    running = kernel_release()
    before = module_dirs()
    try:
        apt_install(steps)
    except Fail:
        copy_boot(names, prev, BOOT_DIR)
        restore_stash()
        shutil.rmtree(prev, ignore_errors=True)
        raise
    new = sorted(m for m in module_dirs() - before if flavour(m) == flavour(running))
    expect = new[-1] if new else running
    # The trial's files to their own folder, the radar's own back in place:
    # an ordinary boot, by power cut or by watchdog, is the old kernel.
    copy_boot(boot_files(), BOOT_DIR, nxt)
    shutil.copy2(os.path.join(BOOT_DIR, "cmdline.txt"), os.path.join(nxt, "cmdline.txt"))
    copy_boot(names, prev, BOOT_DIR)
    with open(os.path.join(BOOT_DIR, "config.txt")) as f:
        config = f.read()
    with open(os.path.join(BOOT_DIR, "tryboot.txt"), "w") as f:
        f.write(config.rstrip("\n") + "\n\n# StratoScan kernel trial (#73): this boot only.\n"
                f"[all]\nos_prefix={NEXT_DIR}/\n")
    images = []
    for m in new:
        # Debian's merged /usr: /lib is a link to /usr/lib, and dpkg knows
        # the modules only by their /usr/lib path (found on RDU 2026-10-13,
        # before the first trial: asking by /lib finds nothing, and a failed
        # trial would have left its kernel installed).
        for base in ("/usr/lib/modules", MODULES_DIR):
            rc, out, _ = run_cmd(["dpkg", "-S", os.path.join(base, m)], timeout=30)
            if rc == 0 and out.strip():
                images += [p.strip() for p in out.split(":")[0].split(",") if p.strip()]
                break
    state["trial"] = {"started": int(time.time()), "expect": expect, "from": running,
                      "packages": {n: [c, v] for n, c, v, _ in steps}, "images": sorted(set(images))}
    save_state(state)
    log(f"trial boot of {expect} (from {running}); rebooting once onto it")
    run_cmd(["sync"], timeout=60)
    # systemd 257 (trixie) takes the firmware's argument only as an option:
    # the older `systemctl reboot "0 tryboot"` is refused as "Too many
    # arguments", which on RDU's first trial (2026-10-13) left everything
    # staged and nothing rebooting. A refused reboot now undoes the trial
    # rather than leave it waiting for whatever restart comes next.
    rc, _, err = run_cmd(["systemctl", "reboot", "--reboot-argument=0 tryboot"], timeout=60)
    if rc != 0:
        abandon_trial(state, f"the trial reboot was refused: {err.strip()[-200:]}")
        raise Fail("the trial reboot was refused; the kernel stays as it is")


def kernel_release():
    return os.uname().release


def uptime_s():
    with open("/proc/uptime") as f:
        return float(f.read().split()[0])


def abandon_trial(state, why):
    """Undo a trial that never booted, through no fault of the kernel: the
    kept packages go back, the trial's kernel is removed, and the version is
    NOT marked failed, so the next run may try again."""
    trial = state.pop("trial", {})
    p = os.path.join(BOOT_DIR, "tryboot.txt")
    if os.path.exists(p):
        os.remove(p)
    state["cleanup"] = {"images": trial.get("images", []),
                        "release": trial.get("expect"), "from": trial.get("from")}
    finish_cleanup(state)
    state["result"] = {"at": int(time.time()), "ok": False, "why": why}
    save_state(state)
    log(f"kernel trial abandoned: {why}")


def network_up():
    rc, out, _ = run_cmd(["ip", "route", "show", "default"], timeout=10)
    return rc == 0 and "default" in out


def confirm():
    """At boot: keep a trial kernel that came up and painted, undo one that
    did not, and finish undoing one the last boot gave up on."""
    state = load_state()
    if state.get("cleanup"):
        finish_cleanup(state)
        return 0
    trial = state.get("trial")
    if not trial:
        return 0
    running, tried = kernel_release(), booted_on_trial()
    if tried and running == trial["expect"]:
        o = ota()
        o.wake_display()
        deadline = time.time() + TRIAL_PAINT_S
        boot_at = time.time() - uptime_s()
        painted = net = False
        while time.time() < deadline and not (painted and net):
            painted = painted or o.paint_stamp() > boot_at
            net = net or network_up()
            time.sleep(5)
        if painted and net:
            promote(trial, state)
            return 0
        why = "the trial boot did not paint" if not painted else "the trial boot had no network"
        fail_trial(state, why)
        log("rebooting onto the radar's own kernel")
        run_cmd(["sync"], timeout=60)
        run_cmd(["systemctl", "reboot"], timeout=60)
        return 1
    # An ordinary boot with a trial pending: the trial boot never came up, or
    # was cut short. This is already the old kernel.
    fail_trial(state, "the trial boot did not come up" if not tried else
               f"the trial booted {running}, not {trial['expect']}")
    finish_cleanup(state)
    return 1


def promote(trial, state):
    nxt = os.path.join(BOOT_DIR, NEXT_DIR)
    names = [n for n in os.listdir(nxt) if n != "cmdline.txt"]
    copy_boot(names, nxt, BOOT_DIR)
    run_cmd(["sync"], timeout=60)
    for p in (os.path.join(BOOT_DIR, "tryboot.txt"),):
        if os.path.exists(p):
            os.remove(p)
    shutil.rmtree(nxt, ignore_errors=True)
    shutil.rmtree(os.path.join(BOOT_DIR, PREV_DIR), ignore_errors=True)
    shutil.rmtree(STASH, ignore_errors=True)
    state.pop("trial", None)
    state["result"] = {"at": int(time.time()), "ok": True,
                       "installed": {n: v[1] for n, v in trial["packages"].items()},
                       "kernel": trial["expect"]}
    state["keep_kernels"] = [r for r in (trial["expect"], trial.get("from")) if r]
    save_state(state)
    log(f"kernel {trial['expect']} booted and painted; it is now the radar's kernel")
    prune_kernels(state)


def kernel_base(release):
    """What one kernel's packages share: 6.18.50+rpt-rpi-2712 -> 6.18.50+rpt
    (linux-image-, linux-headers-, the -common-rpi headers, linux-kbuild-)."""
    m = re.match(r"(\d+\.\d+(?:\.\d+)*\+rpt)(?:-|$)", release or "")
    return m.group(1) if m else None


def prune_kernels(state, have=None):
    """Remove the packages of every Raspberry Pi kernel but the radar's own
    and the one it came from (state["keep_kernels"], set when a trial is
    kept). Each kernel is about 190 MB on the card and nothing else removes
    them: the daily updates leave kernels to this program, and on RDU two
    were already kept by 2026-10-14. Removing an older kernel leaves the boot
    partition alone (its hooks act only when no kernel of that flavour is
    left), and apt is asked first, so nothing goes but those packages."""
    keep = state.get("keep_kernels")
    running = kernel_base(kernel_release())
    if not keep or not running:
        return []
    bases = {running} | {kernel_base(r) for r in keep} - {None}
    old = sorted(n for n in (have if have is not None else installed_packages())
                 if (m := re.fullmatch(r"linux-(?:image|headers|kbuild)-(\d+\.\d+(?:\.\d+)*\+rpt)(?:-[a-z0-9-]+)?", n))
                 and m.group(1) not in bases)
    if not old:
        return []
    try:
        rc, out, err = run_cmd(["apt-get", "-s", "-q", "purge", *old], timeout=600)
        going = set(re.findall(r"^(?:Purg|Remv) (\S+)", out, re.M))
        if rc != 0 or going - set(old):
            log("older kernels kept: apt would remove more than them "
                f"({', '.join(sorted(going - set(old))) or err.strip()[-200:]})")
            return []
        rc, _, err = run_cmd(["apt-get", "purge", "-y", "-q", *old], timeout=APT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError) as e:
        rc, err = 1, str(e)
    if rc != 0:
        log(f"older kernels kept for now (the next daily run tries again): {err.strip()[-200:]}")
        return []
    log(f"removed older kernels: {' '.join(old)}")
    return old


def fail_trial(state, why):
    trial = state.pop("trial", {})
    p = os.path.join(BOOT_DIR, "tryboot.txt")
    if os.path.exists(p):
        os.remove(p)
    for n, (_, v) in trial.get("packages", {}).items():
        state.setdefault("failed", {})[n] = v
    state["cleanup"] = {"images": trial.get("images", []),
                        "release": trial.get("expect"), "from": trial.get("from")}
    state["result"] = {"at": int(time.time()), "ok": False,
                       "rolled_back": {n: v[1] for n, v in trial.get("packages", {}).items()},
                       "why": why}
    save_state(state)
    log(f"kernel trial failed: {why}")


def finish_cleanup(state):
    """On the radar's own kernel: put the kept packages back and remove the
    trial's kernel, so nothing later copies its files over the boot ones."""
    c = state["cleanup"]
    if c.get("release") != c.get("from") and kernel_release() == c.get("release"):
        log("still on the trial kernel; it is removed after the next boot")
        return
    restore_stash()
    images = [i for i in c.get("images", []) if i]
    if images:
        run_cmd(["apt-get", "purge", "-y", "-q", *images], timeout=APT_TIMEOUT_S)
    shutil.rmtree(os.path.join(BOOT_DIR, NEXT_DIR), ignore_errors=True)
    shutil.rmtree(os.path.join(BOOT_DIR, PREV_DIR), ignore_errors=True)
    shutil.rmtree(STASH, ignore_errors=True)
    state.pop("cleanup", None)
    save_state(state)
    log("the trial kernel is removed; the radar runs its own")


# ---- the daily run --------------------------------------------------------

def pending_security():
    """How many security updates apt has waiting (simulated, no change)."""
    rc, out, _ = run_cmd(["apt-get", "-s", "-q", "-o", "Debug::NoLocking=1", "upgrade"], timeout=600)
    if rc != 0:
        return None
    return sum(1 for line in out.splitlines()
               if line.startswith("Inst ") and re.search(r"[-:]security|Debian-Security", line)
               and package_class(line.split()[1]) is None)


def run():
    state = load_state()
    if state.get("trial") or state.get("cleanup"):
        log("a kernel trial is still being finished; nothing else until it is")
        return 0
    have = installed_packages()
    steps = plan(wanted_versions(), have, state.get("failed", {}))
    app = [s for s in steps if s[3] == "app"]
    boot = [s for s in steps if s[3] == "boot"]
    ok = True
    try:
        if app:
            ok = update_app(app, state)
            save_state(state)
            have = installed_packages()
        if boot and ok:
            start_trial(boot, state)       # reboots
            return 0
        if not steps:
            log("the held packages are at their tested versions")
        # Again here, in case apt was busy at the boot that kept the kernel.
        if prune_kernels(state, have):
            have = installed_packages()
    except Fail as e:
        log(f"REFUSED: {e}")
        state["result"] = {"at": int(time.time()), "ok": False, "why": str(e)}
        ok = False
    n = pending_security()
    if n is not None:
        if n and not state.get("pending_since"):
            state["pending_since"] = int(time.time())
        elif not n:
            state.pop("pending_since", None)
        state["pending"] = n
    state["versions"] = versions(have)
    state["checked"] = int(time.time())
    save_state(state)
    return 0 if ok else 1


def versions(have):
    return {"chromium": have.get("chromium"),
            "kernel": kernel_release(),
            "kernel_package": next((v for k, v in sorted(have.items())
                                    if k.startswith("linux-image-rpi-")), None)}


# ---- restarts after patches ------------------------------------------------

def stale_processes():
    """Processes still running a library that an update has replaced."""
    stale = set()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/maps") as f:
                for line in f:
                    if line.endswith("(deleted)\n") and ".so" in line \
                            and re.search(r" /(usr/)?lib/", line):
                        with open(f"/proc/{pid}/comm") as c:
                            stale.add(c.read().strip())
                        break
        except OSError:
            continue
    return sorted(stale)


def panel_on():
    try:
        req = urllib.request.Request(WAKE_STATE_URL, data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r).get("panel") == "on"
    except Exception:
        return True     # can't tell: assume someone is looking


def restart_if_needed(now=None):
    now = now or time.time()
    state = load_state()
    stale = stale_processes()
    state["stale"] = stale
    save_state(state)
    if not stale:
        return 0
    uptime = uptime_s()
    if uptime < RESTART_MIN_UPTIME_S:
        log(f"patched libraries wait in {len(stale)} program(s); up only {uptime / 3600:.0f} h")
        return 0
    if now - state.get("last_restart", 0) < RESTART_MIN_GAP_S:
        log("patched libraries wait; restarted within the week already")
        return 0
    if state.get("trial") or state.get("cleanup"):
        return 0
    if panel_on():
        log("patched libraries wait, but the panel is on; not now")
        return 0
    log("restarting so patched libraries take effect: " + ", ".join(stale[:12]))
    state["last_restart"] = int(now)
    save_state(state)
    run_cmd(["systemctl", "reboot"], timeout=60)
    return 0


# ---- reporting ------------------------------------------------------------

def status():
    """What the heartbeat sends: small, and nothing that runs apt."""
    state = load_state()
    try:
        last_patch = int(time.time() - os.stat(UU_STAMP).st_mtime)
    except OSError:
        last_patch = None
    res = state.get("result") or {}
    return {
        "last_patch_age_s": last_patch,
        "pending": state.get("pending"),
        "pending_since": state.get("pending_since"),
        "chromium": (state.get("versions") or {}).get("chromium"),
        "kernel": kernel_release(),
        "restart_waiting": bool(state.get("stale")),
        "trial": bool(state.get("trial")),
        "held_update": None if not res else ("ok" if res.get("ok") else
                                             "rolled back" if res.get("rolled_back") else "refused"),
    }


def candidates():
    """For the maintainer, on ring 0: the newest versions apt offers for this
    radar's held packages, as an os-packages.json to test and then ship."""
    run_cmd(["apt-get", "update", "-q"], timeout=600)
    have = installed_packages()
    names = sorted(n for n in have if package_class(n))
    rc, out, _ = run_cmd(["apt-cache", "policy", *names], timeout=120)
    pk, cur = {}, None
    for line in out.splitlines():
        if line and not line.startswith(" "):
            cur = line.rstrip(":")
        elif cur and line.strip().startswith("Candidate:"):
            v = line.split(":", 1)[1].strip()
            if v and v != "(none)":
                pk[cur] = v
    newer = {n: v for n, v in pk.items() if v != have.get(n)}
    print(json.dumps({"kind": "os-packages",
                      "tested_on": "<radar, date>",
                      "packages": pk,
                      "_newer_than_installed": newer}, indent=1, sort_keys=True))
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        print(json.dumps(status(), indent=1))
        return 0
    if cmd == "candidates":
        return candidates()
    if os.geteuid() != 0:
        log("needs root")
        return 2
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(LOCK, "w") as lk:
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            log("an update is already running")
            return 0
        if cmd == "run":
            return run()
        if cmd == "confirm":
            return confirm()
        if cmd == "restart-if-needed":
            return restart_if_needed()
    log(f"unknown command {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
