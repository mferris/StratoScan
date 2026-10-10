#!/usr/bin/env python3
"""Which radio is which, by name rather than by position.

The FlyCatcher is two RTL2832U radios on one board, one for 1090 MHz and one
for 978 MHz, and Nooelec gives both the serial number 00000001. Everything
that opens an RTL-SDR picks it by serial or by index, so with two halves on
the same serial only the index is left -- and the index is whichever the USB
bus enumerated first, which readsb was trusting with `--device 0`. It had
been right on every boot so far (2026-10-10); it would not have stayed so.

So this runs just before readsb and the 978 decoder start (ExecStartPre in
their units, and once at boot) and writes, from the radios' USB product
names, environment files the two read:

  /run/stratoscan-radio/readsb.env   RECEIVER_OPTIONS with --device set to
                                     the 1090 radio's index, and NET_OPTIONS
                                     with the 978 decoder's feed connected
                                     when there is a 978 radio
  /run/stratoscan-radio/uat.env      UAT_INDEX, the 978 radio's index; absent
                                     when there is no 978 radio, so its
                                     service exits quietly (roadmap 5.3)

A unit with one plain dongle gets index 0 and no 978 feed, as before. No
radio at all writes nothing, and readsb fails as it always did, for the
watchdog to recover. Nothing here can keep readsb from starting: every
failure is logged and leaves readsb its own defaults.

The owner can switch either radio off on the radar's settings screen
(2026-10-10). The switches live in RADIOS_FILE, {"1090": bool, "978": bool},
both on when it is absent. 1090 off runs readsb with no radio at all
(--device-type none), so it still collects the 978 decoder's and the
network's aircraft for the screens; 978 off is the same as having no 978
radio: no uat.env, no feed.
"""
import ctypes
import os
import re
import shlex
import sys

RUN = os.environ.get("STRATOSCAN_RADIO_RUN", "/run/stratoscan-radio")
READSB_DEFAULT = os.environ.get("STRATOSCAN_READSB_DEFAULT", "/etc/default/readsb")
# Product-name hints, in order of preference, matched case-insensitively.
ADSB_HINTS = ("FlyCatcher_ADS_B", "ADS-B", "ADSB", "1090")
UAT_HINTS = ("FlyCatcher_UAT", "UAT", "978")
UAT_FEED = "--net-connector 127.0.0.1,30978,uat_in"    # readsb reads dump978's raw output
RADIOS_FILE = os.environ.get("STRATOSCAN_RADIOS_FILE", "/etc/stratoscan/radios.json")


def switches():
    """The owner's switches: {"1090": bool, "978": bool}, both on by default."""
    out = {"1090": True, "978": True}
    try:
        import json
        with open(RADIOS_FILE) as f:
            d = json.load(f)
        for k in out:
            if isinstance(d.get(k), bool):
                out[k] = d[k]
    except (OSError, ValueError, AttributeError):
        pass
    return out


def radios():
    """[(index, manufacturer, product, serial)] from librtlsdr, in its order."""
    try:
        lib = ctypes.CDLL("librtlsdr.so.0")
    except OSError:
        return []
    out = []
    for i in range(lib.rtlsdr_get_device_count()):
        bufs = [ctypes.create_string_buffer(256) for _ in range(3)]
        if lib.rtlsdr_get_device_usb_strings(i, *bufs) == 0:
            out.append((i, *(b.value.decode("utf-8", "replace") for b in bufs)))
        else:
            out.append((i, "", "", ""))
    return out


def pick(found, hints, exclude=()):
    for hint in hints:
        for r in found:
            if r[0] not in exclude and hint.lower() in r[2].lower():
                return r
    return None


def choose(found):
    """(adsb radio, uat radio): either may be None."""
    uat = pick(found, UAT_HINTS)
    adsb = pick(found, ADSB_HINTS, exclude={uat[0]} if uat else ())
    if adsb is None:
        rest = [r for r in found if not uat or r[0] != uat[0]]
        adsb = rest[0] if rest else None
    return adsb, uat


def _options(text):
    """The quoted NAME="..." assignments of an /etc/default/readsb."""
    return {m.group(1): m.group(3) for m in
            re.finditer(r'^\s*([A-Z_]+)=(["\'])(.*)\2\s*$', text, re.M)}


def readsb_env(options, adsb, uat, adsb_on=True):
    """The overrides for readsb, from its own options: --device set to the
    1090 radio, and the 978 feed added when there is a 978 radio. With the
    1090 radio switched off, no radio at all: readsb keeps running for the
    978 feed and the screens."""
    toks = shlex.split(options.get("RECEIVER_OPTIONS", ""))
    if not adsb_on:
        toks = ["--device-type", "none"]
    elif adsb is not None:
        if "--device" in toks:
            toks[toks.index("--device") + 1] = str(adsb[0])
        else:
            toks = ["--device", str(adsb[0])] + toks
    net = shlex.split(options.get("NET_OPTIONS", ""))
    if uat is not None and "uat_in" not in " ".join(net):
        net += UAT_FEED.split()
    return {"RECEIVER_OPTIONS": " ".join(toks), "NET_OPTIONS": " ".join(net)}


def write_env(path, values):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        for k, v in values.items():
            f.write(f'{k}="{v}"\n')
    os.replace(tmp, path)


def main():
    found = radios()
    adsb, uat = choose(found)
    on = switches()
    if not on["978"]:
        uat = None                   # switched off: as if there were no 978 radio
    os.makedirs(RUN, exist_ok=True)
    uat_env = os.path.join(RUN, "uat.env")
    if not found:
        print("radio: no RTL-SDR found; readsb keeps its own options", flush=True)
        try:
            os.unlink(uat_env)
        except OSError:
            pass
        return 0
    try:
        with open(READSB_DEFAULT) as f:
            options = _options(f.read())
    except OSError as e:
        print(f"radio: cannot read {READSB_DEFAULT} ({e}); readsb keeps its own options", flush=True)
        options = None
    if options is not None:
        write_env(os.path.join(RUN, "readsb.env"), readsb_env(options, adsb, uat, on["1090"]))
    if uat is not None:
        write_env(uat_env, {"UAT_INDEX": str(uat[0])})
    else:
        try:
            os.unlink(uat_env)
        except OSError:
            pass
    desc = lambda r: f"#{r[0]} {r[2] or 'unnamed'}" if r else "none"
    print(f"radio: 1090 {desc(adsb) if on['1090'] else 'switched off'}, "
          f"978 {desc(uat) if on['978'] else 'switched off'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:          # never keep readsb from starting
        print(f"radio: {type(e).__name__}: {e}", flush=True)
        sys.exit(0)
