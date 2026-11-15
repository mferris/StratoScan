#!/usr/bin/env python3
"""Operating-system updates for the held packages (#73).

The daily security updates hold back Chromium, the kernel and Wi-Fi firmware.
os-update.py moves them, but only to versions named in the signed release's
os-packages.json, and only with a way back:

- Chromium: the replaced versions are kept as .debs; the new browser must
  paint, or they go back and that version is never tried again here. A
  pinned version apt no longer offers is noted once and nothing is touched;
  an install that fails with nothing unpacked puts nothing back.
- The kernel: one trial boot from its own folder (tryboot); kept only if it
  boots, paints and has a network; otherwise the old kernel is what boots and
  the new one is removed.
- Patched libraries: a small-hours restart with the panel asleep, at most
  weekly.

apt, dpkg, the paint check and the reboot are stood in for; the boot
partition is a temporary folder.

Run: python3 tests/test_os_update.py
"""
import importlib.util
import json
import os
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


tmp = pathlib.Path(tempfile.mkdtemp())
os.environ["STRATOSCAN_OTA_STATE"] = str(tmp / "state")
os.environ["STRATOSCAN_OS_PACKAGES"] = str(tmp / "os-packages.json")
os.environ["STRATOSCAN_BOOT_DIR"] = str(tmp / "boot")
os.environ["STRATOSCAN_MODULES_DIR"] = str(tmp / "modules")
spec = importlib.util.spec_from_file_location("osu", D / "os-update.py")
osu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(osu)
osu.log = lambda m: None


# ---- stand-ins ---------------------------------------------------------------

def vkey(v):
    return [int(x) if x.isdigit() else x for x in re.split(r"[.:+~-]", v)]


class World:
    """apt and dpkg, as far as os-update.py can see them."""

    def __init__(self):
        self.have = {}
        self.calls = []
        self.download_ok = True
        self.repack_ok = True
        self.install_ok = True
        self.install_partial = []      # packages apt replaces before it fails
        self.withdrawn = set()         # packages whose pinned version no archive offers
        self.update_ok = True          # apt-get update reaches the archives
        self.madison_ok = True
        self.on_install = None
        self.pkg_of_modules = {}
        self.purge_also = []           # what apt would remove besides the packages named
        self.purge_ok = True

    def run(self, cmd, timeout=120, cwd=None):
        self.calls.append(cmd)
        c = cmd[0]
        if c == "dpkg-query":
            return 0, "".join(f"{n}\t{v}\tii \n" for n, v in self.have.items()), ""
        if c == "dpkg" and cmd[1] == "--compare-versions":
            return (0 if vkey(cmd[2]) > vkey(cmd[4]) else 1), "", ""
        if c == "apt-get" and cmd[1] == "download":
            if self.download_ok:
                name, ver = cmd[-1].split("=")
                (pathlib.Path(cwd) / f"{name}_{ver}.deb").write_text("deb")
                return 0, "", ""
            return 100, "", "E: not available"
        if c == "dpkg-repack":
            if self.repack_ok:
                (pathlib.Path(cwd) / f"{cmd[1]}_repacked.deb").write_text("deb")
                return 0, "", ""
            return 1, "", "no"
        if c == "apt-get" and cmd[1] == "update":
            return (0 if self.update_ok else 100), "", ""
        if c == "apt-cache" and cmd[1] == "madison":
            # What the archives offer: an older build of each package asked
            # for, and the version os-packages.json pins unless withdrawn.
            if not self.madison_ok:
                return 100, "", "E: could not open the cache"
            pins = json.loads((tmp / "os-packages.json").read_text())["packages"]
            src = "http://archive.example.com/debian trixie/main arm64 Packages"
            out = ""
            for n in cmd[2:]:
                if n not in self.withdrawn:
                    out += f" {n} | {pins[n]} | {src}\n"
                out += f" {n} | 1:100.0-1 | {src}\n"
            return 0, out, ""
        if c == "apt-get" and cmd[1] == "install":
            if not self.install_ok:
                for spec_ in [a for a in cmd if "=" in a and not a.startswith("-") and "::" not in a]:
                    n, v = spec_.split("=", 1)
                    if n in self.install_partial:
                        self.have[n] = v
                return 100, "", "E: broken"
            for spec_ in [a for a in cmd if "=" in a and not a.startswith("-") and "::" not in a]:
                n, v = spec_.split("=", 1)
                self.have[n] = v
            if self.on_install:
                self.on_install()
            return 0, "", ""
        if c == "dpkg" and cmd[1] == "-S":
            # as on Raspberry Pi OS trixie: dpkg knows the modules only by
            # their /usr/lib path, and the headers own the folder too
            if not cmd[2].startswith("/usr/lib/modules/"):
                return 1, "", f"dpkg-query: no path found matching pattern {cmd[2]}"
            name = os.path.basename(cmd[2])
            return 0, f"linux-image-{name}, linux-headers-{name}: {cmd[2]}\n", ""
        if c == "apt-get" and cmd[1:4] == ["-s", "-q", "purge"]:
            return 0, "".join(f"Purg {n} [x]\n" for n in [*cmd[4:], *self.purge_also]), ""
        if c == "apt-get" and cmd[1] == "purge":
            if not self.purge_ok:
                return 100, "", "E: Could not get lock /var/lib/dpkg/lock-frontend"
            for n in cmd[4:]:
                self.have.pop(n, None)
            return 0, "", ""
        if c == "apt-get" and cmd[1] == "-s":
            return 0, ("Inst libssl3t64 [3.5.1-1] (3.5.1-1+deb13u1 Debian-Security:13/stable-security [arm64])\n"
                       "Inst tzdata [2025b-1] (2025b-4 Debian:13.1/stable [all])\n"
                       "Inst chromium [140] (141 Raspberry Pi:trixie/main [arm64])\n"), ""
        return 0, "", ""

    def ran(self, *head):
        return [c for c in self.calls if c[:len(head)] == list(head)]


class FakeOta:
    def __init__(self, paints=True):
        self.paints = paints
        self.restarts = 0
        self.stamp = 0.0

    def wake_display(self):
        return True

    def kiosk_started_at(self):
        return self.restarts

    def restart_kiosk(self):
        self.restarts += 1

    def wait_for_new_paint(self, kiosk_was):
        return self.paints if callable(self.paints) is False else self.paints()

    def paint_stamp(self):
        return self.stamp


def fresh(world, fake_ota=None):
    import shutil
    shutil.rmtree(tmp / "state", ignore_errors=True)
    os.makedirs(tmp / "state")
    osu.run_cmd = world.run
    osu._ota = fake_ota or FakeOta()


def write_packages(pk):
    (tmp / "os-packages.json").write_text(json.dumps({"kind": "os-packages", "packages": pk}))


# ---- which packages, which versions -------------------------------------------

check(osu.package_class("chromium") == "app" and osu.package_class("chromium-common") == "app"
      and osu.package_class("rpi-chromium-mods") == "app", "Chromium and its parts are the browser class")
check(osu.package_class("linux-image-rpi-2712") == "boot" and osu.package_class("firmware-brcm80211") == "boot",
      "the kernel and Wi-Fi firmware are the boot class")
check(osu.package_class("rpi-eeprom") is None, "the EEPROM bootloader is never moved here")
check(osu.package_class("openssl") is None, "and ordinary packages are left to the daily security updates")

# every package the daily updates hold back has a path here (except the EEPROM)
uu = (D / "52stratoscan-unattended-upgrades").read_text()
black = re.findall(r'^\s*"([a-z0-9.+-]+)";', uu.split("Package-Blacklist")[1].split("};")[0], re.M)
for b in black:
    # the blacklist matches by prefix: "linux-image" holds linux-image-rpi-2712
    probe = b if osu.package_class(b) else b.rstrip("-") + "-rpi-2712"
    check(b == "rpi-eeprom" or osu.package_class(probe) is not None, f"held package {b} has a tested path")

write_packages({"chromium": "141", "openssl": "9", "rpi-eeprom": "1", "linux-image-rpi-2712": "2", "Bad Name": "1"})
w = osu.wanted_versions()
check(w == {"chromium": "141", "linux-image-rpi-2712": "2"}, "os-packages.json: only held packages are taken")
(tmp / "os-packages.json").write_text('{"kind": "something-else", "packages": {"chromium": "141"}}')
check(osu.wanted_versions() == {}, "a file of another kind is ignored")
(tmp / "os-packages.json").write_text("not json")
check(osu.wanted_versions() == {}, "a broken file is ignored")
shipped = json.loads((D / "os-packages.json").read_text())
check(shipped["kind"] == "os-packages" and isinstance(shipped["packages"], dict),
      "the shipped os-packages.json has the right shape")
# Chromium 156 (security review 2026-11-03, SR-09): four packages at one
# build. chromium-sandbox is among them again (2026-11-15): the archive
# offers it at that version, checked on ring 0, which only lacks the package
# itself. Left out, a unit that has it would keep a 154 sandbox beside a 156
# browser.
pk = shipped["packages"]
cr = {n: v for n, v in pk.items() if n.startswith("chromium")}
check(sorted(cr) == ["chromium", "chromium-common", "chromium-l10n", "chromium-sandbox"],
      "the shipped list pins the four Chromium packages, chromium-sandbox among them")
check(set(cr.values()) == {"1:156.0.8078.79-1~deb13u1+rpt1"}, "all at the same 156 build")
check(all(osu.package_class(n) == "app" for n in cr), "each is one os-update.py moves as the browser")
check(pk.get("linux-image-rpi-2712") == "1:6.18.50-1+rpt1" and pk.get("raspi-firmware") == "1:1.20260915-1",
      "the kernel and firmware pins are as they were: a kernel move is its own trial")
check("156" in shipped["tested_on"] and "on trial from 2026-11-15" in shipped["tested_on"]
      and "not passed" in shipped["tested_on"], "its note says 156 is on trial at ring 0, not that it has passed")
check("chromium-sandbox is pinned" in shipped["tested_on"] and "not listed" not in shipped["tested_on"]
      and "offered none" not in shipped["tested_on"],
      "and that chromium-sandbox is pinned, no longer that the archive had none")
write_packages(pk)
world = World()
fresh(world)
old = "1:154.0.8037.92-1~deb13u1+rpt1"
steps = osu.plan(osu.wanted_versions(), {"chromium": old, "chromium-common": old, "chromium-l10n": old,
                                         "chromium-sandbox": old, "linux-image-rpi-2712": "1:6.18.50-1+rpt1"}, {})
check([s[0] for s in steps] == ["chromium", "chromium-common", "chromium-l10n", "chromium-sandbox"]
      and all(s[3] == "app" for s in steps), "on a unit at 154 that has all four, the four move together")
steps = osu.plan(osu.wanted_versions(), {"chromium": old, "chromium-common": old, "chromium-l10n": old,
                                         "linux-image-rpi-2712": "1:6.18.50-1+rpt1"}, {})
check([s[0] for s in steps] == ["chromium", "chromium-common", "chromium-l10n"],
      "on a unit without chromium-sandbox (ring 0) three move, and apt is not asked to install a fourth")

world = World()
fresh(world)
have = {"chromium": "140", "chromium-common": "140", "linux-image-rpi-2712": "1"}
steps = osu.plan({"chromium": "141", "chromium-common": "141", "linux-image-rpi-2712": "1",
                  "chromium-sandbox": "141"}, have, {})
check([s[0] for s in steps] == ["chromium", "chromium-common"], "only installed packages behind their tested version move")
check(osu.plan({"chromium": "139"}, have, {}) == [], "never backwards")
check(osu.plan({"chromium": "141"}, have, {"chromium": "141"}) == [], "a version that failed here is not tried again")
check(len(osu.plan({"chromium": "142"}, have, {"chromium": "141"})) == 1, "but the next one is")


# ---- Chromium -------------------------------------------------------------

world = World()
world.have = {"chromium": "140", "chromium-common": "140"}
fresh(world, FakeOta(paints=True))
write_packages({"chromium": "141", "chromium-common": "141"})
rc = osu.run()
st = osu.load_state()
check(rc == 0 and world.have["chromium"] == "141", "a tested Chromium is installed")
check(len(world.ran("apt-get", "download")) == 2 and world.ran("apt-get", "download")[0][-1] == "chromium=140",
      "after keeping the versions it replaces")
check(st["result"]["ok"] and st["result"]["installed"] == {"chromium": "141", "chromium-common": "141"},
      "and recorded as installed and painting")
check(osu._ota.restarts == 1, "the kiosk restarted onto it")
check(st["versions"]["chromium"] == "141" and st["pending"] == 1,
      "the state carries the new version and the security updates waiting (not Chromium's)")

world = World()
world.have = {"chromium": "140", "chromium-common": "140"}
fresh(world, FakeOta(paints=False))
rc = osu.run()
st = osu.load_state()
check(rc == 1 and world.ran("dpkg", "-i"), "a Chromium that does not paint: the kept versions go back")
check(st["failed"] == {"chromium": "141", "chromium-common": "141"} and st["result"]["rolled_back"],
      "and that version is marked failed here")
world.calls.clear()
osu._ota = FakeOta(paints=True)
osu.run()
check(not world.ran("apt-get", "install"), "so the next day does not try it again")

world = World()
world.have = {"chromium": "140"}
world.download_ok = world.repack_ok = False
fresh(world)
write_packages({"chromium": "141"})
rc = osu.run()
check(rc == 1 and not world.ran("apt-get", "install") and world.have["chromium"] == "140",
      "no way back (neither download nor repack): no upgrade")
check("could not keep" in osu.load_state()["result"]["why"], "and it says why")

world = World()
world.have = {"chromium": "140"}
world.download_ok = False
fresh(world)
osu.run()
check(world.ran("dpkg-repack") and world.have["chromium"] == "141",
      "an old version no longer in the archive is rebuilt from the installed one")

write_packages({"chromium": "141", "chromium-common": "141"})
world = World()
world.have = {"chromium": "140", "chromium-common": "140"}
world.install_ok = False
world.install_partial = ["chromium-common"]
fresh(world)
rc = osu.run()
check(rc == 1 and world.ran("dpkg", "-i"), "apt failing part-way (one package replaced) puts the kept versions back")

# apt failing before it unpacked anything: the browser that is running is
# whole, so nothing is put back over it (2026-11-15).
world = World()
world.have = {"chromium": "140", "chromium-common": "140"}
world.install_ok = False
fresh(world)
rc = osu.run()
st = osu.load_state()
check(rc == 1 and world.ran("apt-get", "install") and not world.ran("dpkg", "-i") and osu._ota.restarts == 0,
      "apt failing with nothing unpacked: nothing is put back over the running browser, and the kiosk is not restarted")
check(world.have == {"chromium": "140", "chromium-common": "140"} and "apt could not install" in st["result"]["why"]
      and "failed" not in st, "the versions are as they were, it says why, and the version may be tried again")

# A pinned version the archives no longer offer (2026-11-15): asked first,
# noted once, and nothing else happens, that day or the next.
class Watched(FakeOta):
    woken = 0

    def wake_display(self):
        self.woken += 1
        return True


world = World()
world.have = {"chromium": "140", "chromium-common": "140", "linux-image-rpi-2712": "1"}
world.withdrawn = {"chromium-common"}
fake = Watched()
fresh(world, fake)
write_packages({"chromium": "141", "chromium-common": "141", "linux-image-rpi-2712": "2"})
rc = osu.run()
st = osu.load_state()
check(world.ran("apt-cache", "madison") == [["apt-cache", "madison", "chromium", "chromium-common"]],
      "apt is asked whether every pinned browser version is offered")
check(rc == 1 and st["result"]["why"] == "pinned version no longer offered: chromium-common 141"
      and st["result"]["ok"] is False and st["not_offered"] == {"chromium-common": "141"},
      "one that is not is a clear result, naming the package and version")
check(not world.ran("apt-get", "download") and not world.ran("dpkg-repack") and not (tmp / "state" / "os-stash").exists(),
      "nothing is kept")
check(fake.woken == 0 and fake.restarts == 0, "the display is not woken and the kiosk not restarted")
check(not world.ran("apt-get", "install") and not world.ran("dpkg", "-i") and "failed" not in st
      and world.have["chromium"] == "140", "nothing is installed or put back, and no version is marked failed")
check(not world.ran("systemctl", "reboot") and "trial" not in st, "and the kernel waits behind the browser")
check(osu.status()["held_update"] == "refused" and st["versions"]["chromium"] == "140" and "checked" in st,
      "the heartbeat says refused, and the rest of the daily run still happens")
at = st["result"]["at"]
world.calls.clear()
real_time = osu.time.time
osu.time.time = lambda: at + 86400
rc = osu.run()
osu.time.time = real_time
st = osu.load_state()
check(rc == 0 and st["result"]["at"] == at, "the next day the same stale pin is not recorded again, and does not fail the run")
check(len(world.ran("apt-cache", "madison")) == 1 and not world.ran("apt-get", "download") and not world.ran("apt-get", "install")
      and not world.ran("dpkg", "-i") and fake.woken == 0, "it costs one question to apt: no keeping, waking or installing")
world.withdrawn = set()
world.calls.clear()
write_packages({"chromium": "141", "chromium-common": "141"})     # (no kernel step: that is tested below)
rc = osu.run()
st = osu.load_state()
check(world.have["chromium"] == "141" and world.have["chromium-common"] == "141" and "not_offered" not in st
      and st["result"]["ok"], "once the version is offered again it is installed, and the note is gone")
check(world.calls.index(["apt-cache", "madison", "chromium", "chromium-common"])
      < min(world.calls.index(c) for c in world.calls if c[:2] in (["apt-get", "download"], ["apt-get", "install"]))
      and len(world.ran("apt-get", "update")) == 1,
      "the question comes before anything is kept or installed, with one refresh of apt's lists")

# apt that cannot be asked, or lists that could not be refreshed and lack the
# version, say nothing about the archive: refused, but not remembered.
for how in ("madison_ok", "update_ok"):
    world = World()
    world.have = {"chromium": "140"}
    setattr(world, how, False)
    world.withdrawn = {"chromium"}
    fake = Watched()
    fresh(world, fake)
    write_packages({"chromium": "141"})
    rc = osu.run()
    st = osu.load_state()
    check(rc == 1 and "not_offered" not in st and "no longer offered" not in st["result"]["why"]
          and not world.ran("apt-get", "download") and not world.ran("apt-get", "install") and fake.woken == 0,
          f"apt unable to answer ({how.split('_')[0]}): refused untouched, and asked again tomorrow")
world = World()
world.have = {"chromium": "140"}
world.update_ok = False
fresh(world)
osu.run()
check(world.have["chromium"] == "141", "lists that could not be refreshed but already have the version: the install goes ahead")

write_packages({})
world = World()
world.have = {"chromium": "140"}
fresh(world)
osu.run()
check(not world.ran("apt-get", "install") and not world.ran("apt-get", "download"),
      "an empty list (what ships today) changes nothing")


# ---- the kernel trial -----------------------------------------------------

import shutil
boot = tmp / "boot"
mods = tmp / "modules"


def make_boot():
    shutil.rmtree(boot, ignore_errors=True)
    shutil.rmtree(mods, ignore_errors=True)
    (boot / "overlays").mkdir(parents=True)
    for f in ("kernel_2712.img", "kernel8.img", "initramfs_2712", "bcm2712-rpi-5-b.dtb"):
        (boot / f).write_text("old " + f)
    (boot / "overlays" / "vc4.dtbo").write_text("old overlay")
    (boot / "config.txt").write_text("dtparam=audio=on\nauto_initramfs=1\n")
    (boot / "cmdline.txt").write_text("console=tty3 root=PARTUUID=x quiet\n")
    (mods / "6.12.25+rpt-rpi-2712").mkdir(parents=True)
    (mods / "6.12.25+rpt-rpi-v8").mkdir(parents=True)


flag_dir = tmp / "dt" / "chosen" / "bootloader"
flag_dir.mkdir(parents=True)
osu.TRYBOOT_FLAG = str(flag_dir / "tryboot")


def set_tryboot(on):
    (flag_dir / "tryboot").write_bytes((1 if on else 0).to_bytes(4, "big"))


def kernel_install():
    # what the kernel package and the raspi-firmware hook do
    for f in ("kernel_2712.img", "kernel8.img", "initramfs_2712", "bcm2712-rpi-5-b.dtb"):
        (boot / f).write_text("new " + f)
    (boot / "overlays" / "vc4.dtbo").write_text("new overlay")
    (mods / "6.12.47+rpt-rpi-2712").mkdir()
    (mods / "6.12.47+rpt-rpi-v8").mkdir()


make_boot()
set_tryboot(False)
world = World()
world.have = {"linux-image-rpi-2712": "1:6.12.25-1", "linux-image-rpi-v8": "1:6.12.25-1"}
world.on_install = kernel_install
world.pkg_of_modules = {str(mods / "6.12.47+rpt-rpi-2712"): "linux-image-6.12.47+rpt-rpi-2712"}
fresh(world)
osu.kernel_release = lambda: "6.12.25+rpt-rpi-2712"
write_packages({"linux-image-rpi-2712": "1:6.12.47-1", "linux-image-rpi-v8": "1:6.12.47-1"})
osu.run()
st = osu.load_state()
check((boot / "kernel_2712.img").read_text() == "old kernel_2712.img"
      and (boot / "overlays" / "vc4.dtbo").read_text() == "old overlay",
      "after installing a kernel the radar's own boot files are back in place")
check((boot / "stratoscan-next" / "kernel_2712.img").read_text() == "new kernel_2712.img"
      and (boot / "stratoscan-next" / "overlays" / "vc4.dtbo").read_text() == "new overlay"
      and (boot / "stratoscan-next" / "cmdline.txt").exists(),
      "and the new ones are in their own folder")
tb = (boot / "tryboot.txt").read_text()
check(tb.startswith("dtparam=audio=on") and tb.rstrip().endswith("os_prefix=stratoscan-next/"),
      "tryboot.txt is config.txt plus the trial folder, for one boot")
check("os_prefix" not in (boot / "config.txt").read_text(), "config.txt itself is untouched")
check(st["trial"]["expect"] == "6.12.47+rpt-rpi-2712"
      and st["trial"]["images"] == ["linux-headers-6.12.47+rpt-rpi-2712", "linux-image-6.12.47+rpt-rpi-2712"],
      "the trial expects the new kernel of this radar's flavour, and knows its packages by their /usr/lib path")
check(world.ran("systemctl", "reboot", "--reboot-argument=0 tryboot"),
      "and reboots once onto it, in the form systemd 257 accepts")
world.calls.clear()
osu.run()
check(not world.ran("apt-get", "install"), "nothing else is installed while a trial is pending")

# the trial boot comes up and paints
set_tryboot(True)
osu.kernel_release = lambda: "6.12.47+rpt-rpi-2712"
osu.uptime_s = lambda: 60.0
osu.network_up = lambda: True
fake = FakeOta()
fake.stamp = 9e18
osu._ota = fake
osu.time.sleep = lambda s: None
check(osu.confirm() == 0, "a trial boot that paints with a network is kept")
st = osu.load_state()
check((boot / "kernel_2712.img").read_text() == "new kernel_2712.img"
      and (boot / "overlays" / "vc4.dtbo").read_text() == "new overlay"
      and not (boot / "tryboot.txt").exists() and not (boot / "stratoscan-next").exists()
      and not (boot / "stratoscan-prev").exists(), "its files become the radar's boot files, and the trial is tidied")
check("trial" not in st and st["result"]["ok"] and st["result"]["kernel"] == "6.12.47+rpt-rpi-2712",
      "recorded as installed")

# the trial boot hangs: the watchdog or a power cycle brings the old kernel
make_boot()
set_tryboot(False)
world = World()
world.have = {"linux-image-rpi-2712": "1:6.12.25-1"}
world.on_install = kernel_install
world.pkg_of_modules = {str(mods / "6.12.47+rpt-rpi-2712"): "linux-image-6.12.47+rpt-rpi-2712"}
fresh(world)
osu.kernel_release = lambda: "6.12.25+rpt-rpi-2712"
write_packages({"linux-image-rpi-2712": "1:6.12.47-1"})
osu.run()
world.calls.clear()
check(osu.confirm() == 1, "an ordinary boot with a trial pending: the trial failed")
st = osu.load_state()
check(world.ran("dpkg", "-i") and ["apt-get", "purge", "-y", "-q", "linux-headers-6.12.47+rpt-rpi-2712",
                                     "linux-image-6.12.47+rpt-rpi-2712"] in world.calls,
      "the kept packages go back and the trial kernel (and its headers) are removed")
check((boot / "kernel_2712.img").read_text() == "old kernel_2712.img" and not (boot / "tryboot.txt").exists(),
      "the radar keeps its own kernel")
check(st["failed"] == {"linux-image-rpi-2712": "1:6.12.47-1"} and "cleanup" not in st
      and st["result"]["why"] == "the trial boot did not come up", "and that version is marked failed")

# the trial boot comes up but never paints
make_boot()
set_tryboot(False)
world = World()
world.have = {"linux-image-rpi-2712": "1:6.12.25-1"}
world.on_install = kernel_install
world.pkg_of_modules = {str(mods / "6.12.47+rpt-rpi-2712"): "linux-image-6.12.47+rpt-rpi-2712"}
fresh(world)
osu.kernel_release = lambda: "6.12.25+rpt-rpi-2712"
osu.run()
set_tryboot(True)
osu.kernel_release = lambda: "6.12.47+rpt-rpi-2712"
fake = FakeOta()
fake.stamp = 0.0
osu._ota = fake
t = [1000.0]
osu.time.time = lambda: t.__setitem__(0, t[0] + 30) or t[0]
world.calls.clear()
check(osu.confirm() == 1 and world.ran("systemctl", "reboot"), "a trial boot that never paints reboots")
st = osu.load_state()
check(not world.ran("apt-get", "purge"), "without removing the kernel it is running on")
check(st.get("cleanup") and not (boot / "tryboot.txt").exists(), "and leaves the removal for the ordinary boot")
set_tryboot(False)
osu.kernel_release = lambda: "6.12.25+rpt-rpi-2712"
world.calls.clear()
osu.confirm()
check(world.ran("apt-get", "purge") and "cleanup" not in osu.load_state(), "which removes it")

# the reboot is refused (as systemd 257 refused the old form on RDU)
make_boot()
set_tryboot(False)
world = World()
world.have = {"linux-image-rpi-2712": "1:6.12.25-1"}
world.on_install = kernel_install
real_run = world.run
def refusing(cmd, timeout=120, cwd=None):
    if cmd[:2] == ["systemctl", "reboot"]:
        world.calls.append(cmd)
        return 1, "", "Too many arguments."
    return real_run(cmd, timeout, cwd)
fresh(world)
osu.run_cmd = refusing
osu.kernel_release = lambda: "6.12.25+rpt-rpi-2712"
write_packages({"linux-image-rpi-2712": "1:6.12.47-1"})
rc = osu.run()
st = osu.load_state()
check(rc == 1 and "trial" not in st and "cleanup" not in st and not (boot / "tryboot.txt").exists(),
      "a refused reboot undoes the trial instead of leaving it waiting")
check(["apt-get", "purge", "-y", "-q", "linux-headers-6.12.47+rpt-rpi-2712", "linux-image-6.12.47+rpt-rpi-2712"] in world.calls
      and (boot / "kernel_2712.img").read_text() == "old kernel_2712.img", "its kernel removed, the radar's own kept")
check("failed" not in st and "refused" in st["result"]["why"], "and the version is not marked failed, so it may be tried again")

# a radar that cannot boot a trial keeps its kernel
make_boot()
shutil.rmtree(tmp / "dt")
world = World()
world.have = {"linux-image-rpi-2712": "1:6.12.25-1"}
fresh(world)
rc = osu.run()
check(rc == 1 and not world.ran("apt-get", "install") and "cannot boot a trial" in osu.load_state()["result"]["why"],
      "no tryboot support: the kernel is not touched")


# ---- older kernels are removed ----------------------------------------------
# Each kernel is about 190 MB on the card, and nothing else removed them: RDU
# had two by 2026-10-14, and a monthly kernel would add ~2 GB a year.

def kernel_pkgs(v):
    return {f"linux-image-{v}+rpt-rpi-2712": "x", f"linux-image-{v}+rpt-rpi-v8": "x",
            f"linux-headers-{v}+rpt-rpi-2712": "x", f"linux-headers-{v}+rpt-common-rpi": "x",
            f"linux-kbuild-{v}+rpt": "x"}


def kept_trial(world):
    """A trial of 6.12.47 from 6.12.25 that boots and paints."""
    flag_dir.mkdir(parents=True, exist_ok=True)
    make_boot()
    set_tryboot(False)
    fresh(world)
    osu.kernel_release = lambda: "6.12.25+rpt-rpi-2712"
    write_packages({"linux-image-rpi-2712": "1:6.12.47-1"})
    osu.run()
    set_tryboot(True)
    osu.kernel_release = lambda: "6.12.47+rpt-rpi-2712"
    fake = FakeOta()
    fake.stamp = 9e18
    osu._ota = fake
    osu.time.time = __import__("time").time
    world.calls.clear()
    return osu.confirm()


def with_kernels(*versions):
    w = World()
    w.have = {"linux-image-rpi-2712": "1:6.12.25-1", "linux-image-6.12.25+deb13-arm64": "x"}
    for v in versions:
        w.have.update(kernel_pkgs(v))
    def install():
        kernel_install()
        w.have.update(kernel_pkgs("6.12.47"))
    w.on_install = install
    return w


world = with_kernels("6.12.20", "6.12.25")
check(kept_trial(world) == 0, "a kernel trial is kept")
purge = world.ran("apt-get", "purge")
check(purge == [["apt-get", "purge", "-y", "-q", *sorted(kernel_pkgs("6.12.20"))]],
      "and the older kernels' packages go: images, headers (with the common ones) and kbuild")
check(all(n in world.have for n in [*kernel_pkgs("6.12.25"), *kernel_pkgs("6.12.47")]),
      "keeping the radar's new kernel and the one it came from")
check("linux-image-6.12.25+deb13-arm64" in world.have and "linux-image-rpi-2712" in world.have,
      "and anything that is not a versioned Raspberry Pi kernel")
check(world.calls.index(["apt-get", "-s", "-q", "purge", *sorted(kernel_pkgs("6.12.20"))]) < world.calls.index(purge[0]),
      "apt is asked first what the removal would take")
check((boot / "kernel_2712.img").read_text() == "new kernel_2712.img", "the boot files are the kept kernel's")

world = with_kernels("6.12.20", "6.12.25")
world.purge_also = ["stratoscan-something"]
kept_trial(world)
check(not world.ran("apt-get", "purge") and "linux-image-6.12.20+rpt-rpi-2712" in world.have,
      "if apt would remove anything else, nothing is removed")

world = with_kernels("6.12.20", "6.12.25")
world.purge_ok = False
check(kept_trial(world) == 0 and osu.load_state()["keep_kernels"] == ["6.12.47+rpt-rpi-2712", "6.12.25+rpt-rpi-2712"],
      "apt busy at that boot: the kernel is still kept, and what to keep is remembered")
world.purge_ok = True
world.calls.clear()
osu.run()
check("linux-image-6.12.20+rpt-rpi-2712" not in world.have and "linux-image-6.12.25+rpt-rpi-2712" in world.have,
      "so the next daily run removes them")
world.calls.clear()
osu.run()
check(not world.ran("apt-get", "purge"), "and then has nothing to remove")

fresh(world)
world.have.update(kernel_pkgs("6.12.20"))
osu.save_state({"keep_kernels": ["6.12.47+rpt-rpi-2712"]})
osu.kernel_release = lambda: "6.12.20+rpt-rpi-2712"
osu.prune_kernels(osu.load_state())
check("linux-image-6.12.20+rpt-rpi-2712" in world.have, "the kernel it is running on is never removed")
fresh(world)
osu.kernel_release = lambda: "6.12.47+rpt-rpi-2712"
world.calls.clear()
osu.run()
check(not world.ran("apt-get", "purge"), "and nothing is removed before a trial has been kept here")


# ---- restarts after patches -------------------------------------------------

world = World()
fresh(world)
reboots = lambda: world.ran("systemctl", "reboot")
osu.stale_processes = lambda: ["sshd", "lighttpd"]
osu.uptime_s = lambda: 3 * 86400.0
osu.panel_on = lambda: False
now = 2_000_000_000
osu.restart_if_needed(now)
check(len(reboots()) == 1 and osu.load_state()["last_restart"] == now,
      "patched libraries waiting, panel asleep, up three days: restart")
osu.restart_if_needed(now + 86400)
check(len(reboots()) == 1, "not again within the week")
osu.restart_if_needed(now + 7 * 86400)
check(len(reboots()) == 2, "but the next week, if more are waiting")
fresh(world)
osu.panel_on = lambda: True
osu.restart_if_needed(now)
check(len(reboots()) == 2, "never with the panel on")
osu.panel_on = lambda: False
osu.uptime_s = lambda: 3600.0
osu.restart_if_needed(now)
check(len(reboots()) == 2, "nor an hour after a boot")
osu.uptime_s = lambda: 3 * 86400.0
osu.stale_processes = lambda: []
osu.restart_if_needed(now)
check(len(reboots()) == 2, "nor when nothing is waiting")
src = (D / "os-update.py").read_text()
check("return True     # can't tell: assume someone is looking" in src, "a panel it cannot read counts as on")


# ---- what the heartbeat sends -----------------------------------------------

fresh(World())
osu.save_state({"pending": 3, "pending_since": 123, "versions": {"chromium": "141"},
                "stale": ["sshd"], "result": {"ok": False, "rolled_back": {"chromium": "141"}}})
s = osu.status()
check(s["pending"] == 3 and s["chromium"] == "141" and s["restart_waiting"] and s["held_update"] == "rolled back"
      and "kernel" in s and "last_patch_age_s" in s, "status: patch age, waiting updates, versions, outcome")
hb = (D / "heartbeat.py").read_text()
check('"os": os_patch_state()' in hb and "never runs apt" in hb, "the heartbeat sends it, without running apt")


# ---- wiring ------------------------------------------------------------------

ota_src = (D / "ota.py").read_text()
check('"os-update.py", "os-packages.json"' in ota_src, "releases may install os-update.py and os-packages.json")
check("def wait_for_new_paint(kiosk_was" in ota_src and "if wait_for_new_paint(kiosk_was):" in ota_src,
      "ota.py and os-update.py share one paint check")
inst = (D / "install-setup-server.sh").read_text()
for u in ("stratoscan-os-update.timer", "stratoscan-os-restart.timer", "stratoscan-os-confirm.service"):
    check(u in inst.split('echo "== enabling =="')[1], f"the installer enables {u}")
    check((D / u).exists(), f"{u} exists")
check("dpkg-repack" in inst and "os-update.py; do" in inst and "deploy/os-packages.json" in inst,
      "the installer adds dpkg-repack, os-update.py and the versions file")
check(os.access(D / "os-update.py", os.X_OK), "os-update.py is executable")
timer = (D / "stratoscan-os-update.timer").read_text()
check("17:00" in timer, "the daily run is before ota-auto's evening window")

print("os update checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
