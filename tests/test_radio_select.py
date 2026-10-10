#!/usr/bin/env python3
"""deploy/radio-select.py: the 1090 and 978 radios are picked by USB product
name, never by position (roadmap 5.3, 2026-10-10). The FlyCatcher's two
halves share serial 00000001, so the index is all there is to open them by,
and the index is whatever USB enumerated first."""
import importlib.util
import os
import pathlib
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent.parent
tmp = tempfile.mkdtemp()
os.environ["STRATOSCAN_RADIO_RUN"] = os.path.join(tmp, "run")
os.environ["STRATOSCAN_READSB_DEFAULT"] = os.path.join(tmp, "readsb")
spec = importlib.util.spec_from_file_location("rs", root / "deploy" / "radio-select.py")
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


def env(name):
    try:
        return dict(l.rstrip("\n").split("=", 1) for l in open(os.path.join(rs.RUN, name)) if "=" in l)
    except OSError:
        return None


with open(os.environ["STRATOSCAN_READSB_DEFAULT"], "w") as f:
    f.write('RECEIVER_OPTIONS="--device 0 --device-type rtlsdr --gain auto --ppm 0"\n'
            'DECODER_OPTIONS="--lat 35.8 --lon -78.7"\n'
            'NET_OPTIONS="--net --net-bind-address 127.0.0.1 --net-ri-port 30001"\n')

# The FlyCatcher, enumerated the wrong way round: the 978 half first.
rs.radios = lambda: [(0, "Nooelec", "FlyCatcher_UAT", "00000001"), (1, "Nooelec", "FlyCatcher_ADS_B", "00000001")]
rs.main()
e = env("readsb.env")
check(e and e["RECEIVER_OPTIONS"] == '"--device 1 --device-type rtlsdr --gain auto --ppm 0"',
      "readsb is pointed at the 1090 half by name, whatever its index: %s" % (e and e["RECEIVER_OPTIONS"]))
check(e and e["NET_OPTIONS"].endswith('--net-connector 127.0.0.1,30978,uat_in"'), "and reads the 978 decoder's feed")
check(env("uat.env") == {"UAT_INDEX": '"0"'}, "the 978 decoder gets the 978 half's index")

# One plain dongle, no name to go by: index 0, no 978 feed, as before.
rs.radios = lambda: [(0, "Realtek", "RTL2838UHIDIR", "00000001")]
rs.main()
e = env("readsb.env")
check(e["RECEIVER_OPTIONS"].startswith('"--device 0 ') and "uat_in" not in e["NET_OPTIONS"], "a single plain dongle: --device 0 and no 978 feed")
check(env("uat.env") is None, "and the 978 service is told there is no radio (no uat.env)")

# Two plain dongles: the first is the 1090 one; nothing claims to be 978.
rs.radios = lambda: [(0, "Realtek", "RTL2838", "A"), (1, "Realtek", "RTL2838", "B")]
rs.main()
check(env("readsb.env")["RECEIVER_OPTIONS"].startswith('"--device 0 ') and env("uat.env") is None,
      "two unnamed dongles: the first is 1090, no guess at 978")

# No radio: readsb keeps its own options, the 978 service is told there is none.
os.unlink(os.path.join(rs.RUN, "readsb.env"))
rs.radios = lambda: []
rs.main()
check(env("readsb.env") is None and env("uat.env") is None, "no radio: nothing written, readsb's defaults stand")

# A readsb file without --device at all still gets one.
with open(os.environ["STRATOSCAN_READSB_DEFAULT"], "w") as f:
    f.write('RECEIVER_OPTIONS="--device-type rtlsdr --gain 40"\nNET_OPTIONS="--net --net-connector 127.0.0.1,30978,uat_in"\n')
rs.radios = lambda: [(0, "Nooelec", "FlyCatcher_ADS_B", "00000001"), (1, "Nooelec", "FlyCatcher_UAT", "00000001")]
rs.main()
e = env("readsb.env")
check(e["RECEIVER_OPTIONS"] == '"--device 0 --device-type rtlsdr --gain 40"', "--device is added when readsb's options lack it")
check(e["NET_OPTIONS"].count("uat_in") == 1, "the 978 feed is not added twice")

# The installer, the updater and the image carry it.
inst = (root / "deploy" / "install-setup-server.sh").read_text()
ota = (root / "deploy" / "ota.py").read_text()
img = (root / "image" / "build.sh").read_text()
check('"radio-select.py"' in ota, "the updater may install radio-select.py")
check("stratoscan-uat.service" in inst and "stratoscan-radio.service" in inst and "readsb.service.d/stratoscan-radio.conf" in inst,
      "the installer installs the 978 service, the radio oneshot and readsb's drop-in")
check("dump978" in inst and "rtl-sdr" in inst, "the installer builds dump978 and installs rtl_sdr")
check("dump978-fa" in img and "stratoscan-uat.service" in img, "the image checks for the decoder and its service")
uat = (root / "deploy" / "stratoscan-uat.service").read_text()
check("--format CU8" in uat and "-s 2083334" in uat and "-f 978000000" in uat and "Restart=on-failure" in uat,
      "the 978 service: raw 8-bit samples at the UAT rate, and no restart loop on a unit without the radio")
check("127.0.0.1:30978" in uat and "127.0.0.1:30979" in uat, "the decoder listens on loopback only")
print("radio select checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
