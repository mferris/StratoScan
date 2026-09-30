#!/usr/bin/env python3
"""Validation and config-rewrite tests for the root helper.

setupd.py is the privilege boundary for the setup server: it runs as root
and the unprivileged web tier can only reach it through a closed verb enum.
These tests pin the two things most likely to cause real harm.

1. Input validation. Every parameter is re-validated inside the root helper
   rather than trusted from the caller, so these cases matter even if the
   web tier is compromised.

2. The /etc/default/readsb rewriter. That file is shell-sourced by root at
   boot, making it a command-execution sink -- and it also holds the options
   that make the receiver work at all. A rewrite that mangles it either runs
   attacker input as root or stops the device receiving.

Run: python3 tests/test_setupd_validation.py
"""
import importlib.util
import os
import pathlib
import re
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("setupd", ROOT / "deploy" / "setupd.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
d.os.chown = lambda *a, **k: None  # the daemon runs as root; tests do not

# Deliberately FICTIONAL coordinates. An earlier version of this fixture used
# the development receiver's real position to 14 decimal places, which is a
# home address in numeric form and has no business in a git history.
SAMPLE_READSB = (
    'RECEIVER_OPTIONS="--device 0 --device-type rtlsdr --gain auto --ppm 0"\n'
    'DECODER_OPTIONS="--lat 38.88880000000000 --lon -77.0000000000000'
    ' --max-range 450 --write-json-every 1"\n'
    'NET_OPTIONS="--net --net-bind-address 127.0.0.1 --net-ri-port 30001"\n'
    'JSON_OPTIONS="--json-location-accuracy 2 --range-outline-hours 24"\n'
)

REJECT = [
    ("ssid", d.v_ssid, ["-injected", "a" * 33, "x\x00y", "l\nb", 123, ""]),
    # "-injected": v_ssid rejected a leading dash to keep nmcli from reading
    # the value as an option; v_psk did not, though it reaches nmcli the same
    # way as an argument.
    ("psk", d.v_psk, ["short", "pass\nword", "a" * 100, "-injected"]),
    # Coordinates are global now -- the device is gifted abroad. Only
    # genuinely impossible values are rejected; 51.5N/0.1E is London, not an
    # error, and it used to be one.
    ("lat", d.v_lat, ["35.8", True, float("nan"), float("inf"), 90.1, -90.1]),
    ("lon", d.v_lon, [None, True, 180.1, -180.1, "0"]),
    ("hostname", d.v_ts_hostname, ["UPPER", "-lead", "trail-", "has space", "a" * 40]),
    ("authkey", d.v_authkey, ["nope", "tskey-short", "; rm -rf /", ""]),
    ("atc_mount", d.v_atc_mount, ["../etc", "UPPER", "a", "x" * 50, "semi;colon"]),
    # The address goes into a URL query for the geocoder, and the timezone
    # string reaches timedatectl, so both are bounded before they travel.
    ("query", d.v_query, ["", "ab", "x" * 201, None, 123]),
    ("timezone", d.v_timezone, ["../etc/passwd", "Not/A/Real/Zone/Here",
                                "Europe/Amsterdam; rm -rf /", "", None, 7]),
    ("country", d.v_country, ["USA", "u", "1A", "", None, "N L"]),
]

ACCEPT = [
    (d.v_ssid, "MyNetwork"), (d.v_ssid, "café wifi"),
    (d.v_psk, "goodpass123"), (d.v_psk, "0" * 64), (d.v_psk, None),
    (d.v_lat, 35.8776), (d.v_lon, -78.7875),
    # Leiden, Menlo Park, Sydney, and the extremes -- all must be accepted.
    (d.v_lat, 52.1601), (d.v_lon, 4.4970),
    (d.v_lat, 37.4530), (d.v_lon, -122.1817),
    (d.v_lat, -33.8688), (d.v_lon, 151.2093),
    (d.v_lat, 90.0), (d.v_lat, -90.0), (d.v_lon, 180.0), (d.v_lon, -180.0),
    (d.v_ts_hostname, "stratoscan-1"),
    (d.v_authkey, "tskey-auth-" + "x" * 20),
    (d.v_atc_mount, "krdu_app2"), (d.v_atc_mount, ""),
    (d.v_query, "Rapenburg 70, Leiden, Netherlands"),
    (d.v_query, "1 Hacker Way, Menlo Park, CA"),
    (d.v_country, "NL"), (d.v_country, "us"),
]


def check_validation(fails):
    for name, fn, values in REJECT:
        for v in values:
            try:
                fn(v)
                fails.append(f"{name}: accepted {v!r}")
            except d.Err:
                pass
    for fn, v in ACCEPT:
        try:
            fn(v)
        except d.Err as e:
            fails.append(f"rejected valid {v!r}: {e.code}")


def check_readsb(fails):
    tmp = tempfile.mkdtemp()
    try:
        d.STATE_DIR = tmp
        d.READSB_ORIG = os.path.join(tmp, "orig")
        d.READSB_BACKUP = os.path.join(tmp, "bak")

        def rewrite(content, lat, lon):
            p = os.path.join(tmp, "readsb")
            with open(p, "w") as f:
                f.write(content)
            d.READSB_DEFAULT = p
            d.rewrite_readsb_location(lat, lon)
            with open(p) as f:
                return f.read()

        out = rewrite(SAMPLE_READSB, 41.786, -87.7524)
        for key in ("RECEIVER_OPTIONS", "NET_OPTIONS", "JSON_OPTIONS"):
            a = re.search(rf'{key}="(.*)"', SAMPLE_READSB).group(1)
            b = re.search(rf'{key}="(.*)"', out).group(1)
            if a != b:
                fails.append(f"{key} was modified")
        dec = re.search(r'DECODER_OPTIONS="(.*)"', out).group(1)
        for keep in ("--max-range 450", "--write-json-every 1"):
            if keep not in dec:
                fails.append(f"lost option {keep!r}")
        if "--lat 41.78600" not in dec or "--lon -87.75240" not in dec:
            fails.append(f"coordinates not applied: {dec!r}")

        # --lat=X spelling, and a file with no --lon at all
        out2 = rewrite('DECODER_OPTIONS="--lat=1.0 --max-range 450"\n', 40.0, -75.0)
        if "--lat=40.00000" not in out2 or "--lon -75.00000" not in out2:
            fails.append(f"equals-spelling/append failed: {out2!r}")

        # a shell metacharacter already in the file must stop the write
        try:
            rewrite('DECODER_OPTIONS="--lat 1 --evil `id` --lon 2"\n', 40.0, -75.0)
            fails.append("accepted a backtick token into a root-sourced file")
        except d.Err as e:
            if e.code != "readsb_unsafe_token":
                fails.append(f"wrong refusal code: {e.code}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_no_shell(fails):
    src = (ROOT / "deploy" / "setupd.py").read_text()
    if "shell=True" in src:
        fails.append("setupd.py contains shell=True")
    if "os.system" in src:
        fails.append("setupd.py contains os.system")
    # shutdown must never be remotely reachable: it needs a physical visit
    if '"shutdown"' in src or "poweroff" in src:
        fails.append("setupd.py exposes a shutdown/poweroff verb")


def check_reset(fails):
    """The two reset tiers must differ in exactly the way that matters.

    'Settings' has to be survivable remotely -- if it dropped the network it
    would be indistinguishable from a brick to anyone without a keyboard.
    'Full' has to erase everything tied to the previous owner, because a unit
    handed on still carrying their WiFi password, their tailnet identity and
    a heatmap of their home airport is a privacy problem, not untidiness.
    """
    tmp = tempfile.mkdtemp()
    try:
        calls = []

        class FakeProc:
            returncode = 0
            stdout = (b"uuid-aaa:802-11-wireless\nuuid-bbb:802-11-wireless\n"
                      b"uuid-eth:802-3-ethernet\n")
            stderr = b""

        d.run = lambda argv, **k: (calls.append(argv), FakeProc())[1]
        d.hotspot_start = lambda: (calls.append(["hotspot_start"]), {}) [1]
        d.STATE_DIR = tmp
        d.CONFIG_JSON = os.path.join(tmp, "config.json")
        d.READSB_DEFAULT = os.path.join(tmp, "readsb")
        d.READSB_ORIG = os.path.join(tmp, "orig")
        d.PENDING = os.path.join(tmp, "pending.json")
        pristine = 'DECODER_OPTIONS="--lat 0.00000 --lon 0.00000"\n'

        def seed():
            for path, body in ((d.READSB_ORIG, pristine),
                               (d.READSB_DEFAULT, 'DECODER_OPTIONS="--lat 35.8 --lon -78.7"\n'),
                               (d.CONFIG_JSON, '{"airport":{"code":"RDU"}}'),
                               (os.path.join(tmp, "setup.json"), '{"claimed":true}'),
                               (d.PENDING, "{}")):
                with open(path, "w") as f:
                    f.write(body)

        seed(); calls.clear()
        d.reset_settings()
        if os.path.exists(d.CONFIG_JSON):
            fails.append("reset_settings left config.json")
        if any("delete" in " ".join(map(str, c)) for c in calls):
            fails.append("reset_settings deleted a network profile (would strand the device)")
        if not os.path.exists(os.path.join(tmp, "setup.json")):
            fails.append("reset_settings erased the admin password")

        events_set = []

        class FakeEvents:
            @staticmethod
            def set_enabled(v): events_set.append(v)
        d._events = lambda: FakeEvents
        forgot = []

        class FakePairing:
            @staticmethod
            def forget_everything(): forgot.append(True)
        d._pairing = lambda: FakePairing

        seed(); calls.clear()
        d.reset_full()
        if events_set != [False]:
            fails.append("reset_full left phone alerts on (they would reach the previous owner)")
        if forgot != [True]:
            fails.append("reset_full left the previous owner's phones paired")
        deleted = [c[3] for c in calls
                   if len(c) > 3 and c[1] == "connection" and c[2] == "delete"]
        if "uuid-aaa" not in deleted or "uuid-bbb" not in deleted:
            fails.append("reset_full left a WiFi profile behind")
        if "uuid-eth" in deleted:
            fails.append("reset_full deleted the ethernet profile")
        if os.path.exists(os.path.join(tmp, "setup.json")):
            fails.append("reset_full left the previous owner's password")
        if os.path.exists(d.CONFIG_JSON):
            fails.append("reset_full left config.json")
        if not any(c[0] == "hotspot_start" for c in calls):
            fails.append("reset_full did not raise the hotspot (unit arrives unreachable)")
        if not any("logout" in " ".join(map(str, c)) for c in calls):
            fails.append("reset_full did not log out of tailscale")

        # ---- no coordinates survive a full reset ------------------------
        # The saved "original" can itself hold a position (whoever built the
        # unit), and a unit located by hand has no original at all -- which
        # used to skip the location reset entirely.
        d.OFFLINE_MAP_DIR = os.path.join(tmp, "offline-map")
        for label, keep_orig in (("with a saved original", True),
                                 ("with no saved original (located by hand)", False)):
            seed()
            with open(d.READSB_ORIG, "w") as f:
                f.write('DECODER_OPTIONS="--lat 51.50000 --lon -0.12000 --max-range 450"\n')
            if not keep_orig:
                os.unlink(d.READSB_ORIG)
                with open(d.READSB_DEFAULT, "w") as f:
                    f.write('DECODER_OPTIONS="--lat 35.8 --lon -78.7 --max-range 450"\n')
            for sub in ("", ".new"):
                os.makedirs(os.path.join(d.OFFLINE_MAP_DIR + sub, "tiles"), exist_ok=True)
            calls.clear()
            d.reset_full()
            with open(d.READSB_DEFAULT) as f:
                after = f.read()
            if re.search(r"--l(at|on)", after):
                fails.append(f"reset_full left coordinates in readsb {label}: {after.strip()}")
            if "--max-range 450" not in after:
                fails.append(f"reset_full dropped unrelated readsb options {label}")
            flat = [" ".join(map(str, c)) for c in calls]
            restart = next((i for i, c in enumerate(flat) if c.endswith("restart readsb")), None)
            stop_map = next((i for i, c in enumerate(flat) if "stop stratoscan-offline-map" in c), None)
            if restart is None:
                fails.append(f"reset_full did not restart readsb {label} (old position stays published)")
            if stop_map is None:
                fails.append(f"reset_full did not stop an in-flight offline-map build {label}")
            elif restart is not None and stop_map < restart:
                fails.append("the offline map was cleared before readsb stopped reporting the old house")
            for sub in ("", ".new"):
                if os.path.exists(d.OFFLINE_MAP_DIR + sub):
                    fails.append(f"reset_full left offline-map{sub} (an extract around their house)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_health_verbs(fails):
    """The health-report switch accepts a real boolean and nothing else."""
    calls = []

    class FakeHB:
        RELAY_URL = "https://relay.example"
        LAST = "/nonexistent"
        @staticmethod
        def set_enabled(v): calls.append(v)
        @staticmethod
        def enabled(): return bool(calls and calls[-1])
        @staticmethod
        def load_key(create=False): return None
        @staticmethod
        def _json(p): return {}

    d._heartbeat = lambda: FakeHB
    for bad in ("true", 1, None, "yes", [True]):
        try:
            d.set_health_report(bad)
            fails.append(f"set_health_report accepted {bad!r}")
        except d.Err:
            pass
    if calls:
        fails.append("a rejected value still changed the setting")
    if d.set_health_report(True).get("enabled") is not True or calls != [True]:
        fails.append("set_health_report(True) did not enable reporting")
    if "set_health_report" not in d.MUTATING:
        fails.append("set_health_report must take the state lock")


def check_pairing_verbs(fails):
    """Only a well-formed phone id reaches pairing.py; relay errors come back as Err."""
    removed = []

    class FakeRelayError(Exception):
        pass

    class FakePairing:
        RelayError = FakeRelayError
        @staticmethod
        def remove(phone): removed.append(phone); return {"phones": 0}
        @staticmethod
        def start(): raise FakeRelayError("Could not reach the StratoScan service. Is this radar online?")

    real = d._pairing
    d._pairing = lambda: FakePairing
    try:
        for bad in (None, 1, "", "x" * 42, "x" * 44, "../../etc/passwd" + "x" * 27, "a b" + "x" * 40):
            try:
                d.pair_remove(bad)
                fails.append(f"pair_remove accepted {bad!r}")
            except d.Err:
                pass
        if removed:
            fails.append("a rejected phone id still reached pairing.py")
        good = "A" * 20 + "_-" + "b" * 21
        if d.pair_remove(good) != {"phones": 0} or removed != [good]:
            fails.append("pair_remove did not pass a valid phone id through")
        try:
            d.pair_start()
            fails.append("a relay failure was not reported")
        except d.Err as e:
            if "Could not reach" not in e.detail:
                fails.append("a relay failure lost its reason")
    finally:
        d._pairing = real
    for v in ("pair_start", "pair_cancel", "pair_remove"):
        if v not in d.MUTATING:
            fails.append(f"{v} must take the state lock")
    if "pair_status" in d.MUTATING:
        fails.append("pair_status does network I/O and must not hold the state lock")


def check_feeding_verbs(fails):
    """The FlightAware switch accepts a real boolean and runs the install in the background."""
    calls = []
    real_run, real_exists = d.run, d.os.path.exists

    class P:
        returncode = 0
        stdout = b'{"flightaware": {"installed": false, "active": false}}'
        stderr = b""

    d.run = lambda argv, **k: (calls.append(argv), P())[1]
    d.os.path.exists = lambda p: True if p == d.FEEDING else real_exists(p)
    try:
        for bad in ("true", 1, None, [True]):
            try:
                d.set_feeding(bad)
                fails.append(f"set_feeding accepted {bad!r}")
            except d.Err:
                pass
        if calls:
            fails.append("a rejected value still ran a command")
        d.set_feeding(True)
        if not any(c[:1] == ["systemd-run"] and "enable-flightaware" in c for c in calls):
            fails.append("turning feeding on must run in its own transient unit")
        calls.clear()
        d.set_feeding(False)
        if not any("disable-flightaware" in c for c in calls):
            fails.append("turning feeding off did not disable it")
        if "set_feeding" not in d.MUTATING:
            fails.append("set_feeding must take the state lock")
    finally:
        d.run, d.os.path.exists = real_run, real_exists


def main():
    fails = []
    check_health_verbs(fails)
    check_feeding_verbs(fails)
    check_pairing_verbs(fails)
    check_validation(fails)
    check_readsb(fails)
    check_no_shell(fails)
    check_reset(fails)
    for f in fails:
        print("FAIL:", f)
    print("all setupd checks passed" if not fails else f"{len(fails)} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
