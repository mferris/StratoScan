#!/usr/bin/env python3
"""Boot straight to StratoScan (2026-10-11): deploy/quiet-boot.sh.

From power-on to the radar the panel should show the StratoScan picture and
nothing else: no firmware colour splash, no Raspberry Pi boot splash, no
kernel text, no desktop or taskbar. The script edits text files that decide
whether the unit boots at all (cmdline.txt is one line, and a broken one is
an SD card in a card reader), so its text edits are run here against copies.

Run: python3 tests/test_quiet_boot.py
"""
import os
import pathlib
import shutil
import struct
import subprocess
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


# RDU's own kernel command line, from a Raspberry Pi Imager install
RDU_CMDLINE = ("console=serial0,115200 console=tty1 root=PARTUUID=92fa63a6-02 rootfstype=ext4 "
               "fsck.repair=yes rootwait quiet splash plymouth.ignore-serial-consoles "
               "ds=nocloud;i=rpi-imager-1786642372509 cfg80211.ieee80211_regdom=US")
CONFIG = "dtparam=audio=on\n[pi5]\ndtoverlay=nospi10\n[all]\ndtparam=fan_temp2=70000\n"


def run(fw, autostart):
    env = dict(os.environ, QUIET_BOOT_FILES_ONLY="1", FW=str(fw), AUTOSTART=str(autostart))
    return subprocess.run(["sh", str(D / "quiet-boot.sh")], env=env, capture_output=True, text=True)


with tempfile.TemporaryDirectory() as t:
    t = pathlib.Path(t)
    (t / "cmdline.txt").write_text(RDU_CMDLINE + "\n")
    (t / "config.txt").write_text(CONFIG)
    (t / "autostart").write_text("/usr/bin/lwrespawn /usr/bin/pcmanfm-pi &\n/usr/bin/lwrespawn /usr/bin/wf-panel-pi &\n"
                                 "/usr/bin/kanshi &\n/usr/bin/lxsession-xdg-autostart\n")
    r = run(t, t / "autostart")
    check(r.returncode == 0, "the script runs: %s" % r.stderr.strip()[:200])

    cl = (t / "cmdline.txt").read_text()
    words = cl.split()
    check(cl.count("\n") == 1 and cl.endswith("\n"), "cmdline.txt is still exactly one line")
    check("console=tty3" in words and "console=tty1" not in words, "the console moved from tty1 to tty3")
    check("console=serial0,115200" in words, "the serial console is kept, for a UART cable")
    for w in ("quiet", "splash", "plymouth.ignore-serial-consoles", "logo.nologo", "loglevel=3", "vt.global_cursor_default=0"):
        check(words.count(w) == 1, "the command line has %s once" % w)
    check("root=PARTUUID=92fa63a6-02" in words and "rootwait" in words, "the root device and rootwait are untouched")
    check("ds=nocloud;i=rpi-imager-1786642372509" in words, "a word with a semicolon survives")
    check(set(RDU_CMDLINE.split()) - {"console=tty1"} <= set(words), "nothing else was dropped")
    check((t / "cmdline.txt.stratoscan-orig").read_text() == RDU_CMDLINE + "\n", "the original command line is kept")

    cfg = (t / "config.txt").read_text()
    check(cfg.startswith(CONFIG), "config.txt keeps everything it had")
    tail = cfg[len(CONFIG):]
    check("[all]" in tail and tail.index("[all]") < tail.index("disable_splash=1"),
          "disable_splash=1 is added under [all], whatever section the file ended in")

    a = (t / "autostart").read_text()
    check(a == (D / "labwc-autostart").read_text(), "the desktop's autostart is ours")
    check((t / "autostart.stratoscan-orig").exists(), "the original autostart is kept")

    # idempotent: a second run changes nothing and adds nothing
    before = {p.name: p.read_text() for p in t.iterdir()}
    r = run(t, t / "autostart")
    after = {p.name: p.read_text() for p in t.iterdir()}
    check(r.returncode == 0 and before == after, "a second run changes nothing")

    # a command line that already has its own loglevel keeps it
    (t / "cmdline.txt").write_text("console=tty1 root=/dev/mmcblk0p2 loglevel=7\n")
    (t / "cmdline.txt.stratoscan-orig").unlink()
    run(t, t / "autostart")
    w2 = (t / "cmdline.txt").read_text().split()
    check("loglevel=7" in w2 and "loglevel=3" not in w2, "an existing loglevel is left as it is")

# the session list itself
a = (D / "labwc-autostart").read_text()
lines = [l for l in a.splitlines() if l and not l.startswith("#")]
check(not any("pcmanfm" in l or "wf-panel" in l for l in lines), "no desktop and no taskbar")
check(any("swaybg" in l and "/usr/share/stratoscan/splash.png" in l for l in lines), "the picture is the background")
check("/usr/bin/kanshi &" in lines, "kanshi still sets the display up")
check("/usr/bin/lxsession-xdg-autostart" in lines,
      "XDG autostart still runs (autotouch, the power key, the session environment the kiosk needs)")

# the picture: the panel's size, and the colour the page's splash uses
png = (D / "boot-splash" / "splash.png").read_bytes()
w, h = struct.unpack(">II", png[16:24])
check((w, h) == (1080, 1080), "splash.png is 1080 x 1080 (it is %d x %d)" % (w, h))
html = (ROOT / "index.html").read_text()
check("#splash { background: #0a0d0f; }" in html, "the page's splash has the picture's background")
check("#0a0d0f" in (D / "boot-splash" / "make-splash.sh").read_text(), "and the picture is made on that colour")
check("#0a0d0f" in a, "and swaybg fills round it with the same colour")

# the installer runs it, and the script is careful
inst = (D / "install-setup-server.sh").read_text()
check("sh deploy/quiet-boot.sh" in inst, "the installer runs quiet-boot.sh")
q = (D / "quiet-boot.sh").read_text()
check("dpkg-divert --package stratoscan --add --rename" in q,
      "the Raspberry Pi splash picture is diverted, so a package upgrade cannot put it back")
check("plymouth-set-default-theme -R pix" in q, "the initramfs is rebuilt with the new picture")
check("for f in splash.png pix.script" in q, "the splash script is diverted too")
ps = (D / "boot-splash" / "pix.script").read_text()
code = "\n".join(l for l in ps.splitlines() if not l.lstrip().startswith("#"))
check("SetUpdateStatusFunction" not in code and "Image.Text" not in code,
      "the splash script prints no start-up messages")
check("Image(\"splash.png\")" in code and "Sprite(image)" in code, "it draws the picture")
check("10 / 255" in code and "13 / 255" in code and "15 / 255" in code, "on the picture's own background colour")

# ---- the boot cover: the picture above Chromium until the page paints ----
import importlib.util
os.environ["XDG_RUNTIME_DIR"] = tempfile.mkdtemp()
spec = importlib.util.spec_from_file_location("bc", D / "boot-cover.py")
bc = importlib.util.module_from_spec(spec); spec.loader.exec_module(bc)
flag = pathlib.Path(bc.FLAG)
check(str(flag).startswith(os.environ["XDG_RUNTIME_DIR"]), "the cover's flag lives in the session's runtime directory")
check(not bc.should_close(100.0, 101.0), "the cover stays while the page has not painted")
check(bc.should_close(100.0, 100.0 + bc.MAX_S + 1), "and gives up after MAX_S, whatever happens")
spec = importlib.util.spec_from_file_location("wl", D / "wake-listener.py")
wl = importlib.util.module_from_spec(spec); spec.loader.exec_module(wl)
check(wl.PAGE_PAINTED_FLAG == bc.FLAG, "the listener writes the flag the cover watches")
H = [v for v in vars(wl).values() if isinstance(v, type) and hasattr(v, "do_POST")][0]
h = H.__new__(H); h.path = "/wake/painted"; got = []
h.send_response = lambda c, *a: got.append(c); h.end_headers = lambda: None; h.send_error = lambda c, *a: got.append(c)
h.do_POST()
check(got == [204] and flag.exists(), "POST /wake/painted answers 204 and writes the flag")
check(bc.should_close(100.0, 101.0), "and then the cover closes")
bsrc = (D / "boot-cover.py").read_text()
check(bc.UNCOVERED_PX >= 1 and "set_margin(win, GtkLayerShell.Edge.RIGHT, UNCOVERED_PX)" in bsrc,
      "the cover leaves a sliver uncovered, so Chromium keeps drawing and the page can report")
check("/usr/bin/python3 /opt/stratoscan/boot-cover.py &" in (D / "labwc-autostart").read_text(), "the session starts the cover")
check("boot-cover.py" in inst and '"boot-cover.py"' in (D / "ota.py").read_text(), "the installer installs it and updates may replace it")
check("gir1.2-gtklayershell-0.1" in q, "quiet-boot.sh installs the layer-shell binding the cover needs")
check("fetch('/wake/painted'" in html and "if (ON_DEVICE) requestAnimationFrame" in html,
      "the page reports its first painted frames, on the unit only")
fg = (D / "funnel-gateway.py").read_text()
check('LOCAL_ONLY_PATHS = ("/wake"' in fg, "and /wake stays off the public tunnel")

print("quiet boot checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
