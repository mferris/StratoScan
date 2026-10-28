#!/usr/bin/env python3
"""A take-off sound when the radar is plugged in, never after a restart (#81).

The owner's ask (2026-10-23). The unit reports whether this boot was a
power-on: the bootloader's copy of the Pi's reset flags (PM_RSTS) has HADPOR,
bit 12, set when the power came on, and other bits after a reboot or a
watchdog reset (RDU read 0x1000 after a replug). The panel plays the sound
once per boot, in the first five minutes, through the usual volume, mute and
quiet hours, and only while its setting is on.

And it plays alone (2026-10-28). At the owner's plug-in test it played over
an aircraft's chime and announcement, as the page announced what was already
in range. On the panel alerts now wait from page load until the boot answer
says whether it plays, and while it plays; then they come in turn, an
emergency first. Without a power-on they wait only for that answer, and never
more than 15 s for it.

Run: python3 tests/test_boot_sound.py
"""
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


spec = importlib.util.spec_from_file_location("setup_server", ROOT / "deploy" / "setup-server.py")
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)
tmp = pathlib.Path(tempfile.mkdtemp())
# Read off RDU: 0x1000 after a replug (2026-10-23), 0x1020 after the weekly
# patch restart (2026-10-26). HADPOR stays set through a reboot, so the reboot
# bits beside it are what tell the two apart; an earlier version took HADPOR
# alone as a power-on and would have played after that restart.
for label, raw, want in (("power-on (0x1000, RDU after a replug)", b"\x00\x00\x10\x00", True),
                         ("RDU's weekly patch restart (0x1020)", b"\x00\x00\x10\x20", False),
                         ("a watchdog or software reset alone", b"\x00\x00\x00\x20", False),
                         ("HADPOR with any other reset bit", b"\x00\x00\x10\x05", False)):
    (tmp / "rsts").write_bytes(raw)
    ss.RSTS_PATH = str(tmp / "rsts")
    check(ss.boot_info()["powerOn"] is want, f"boot_info reads {label} as powerOn={want}")
ss.RSTS_PATH = str(tmp / "missing")
info = ss.boot_info()
check(info["powerOn"] is False and isinstance(info["uptimeS"], int) or info["uptimeS"] is None,
      "no reset flags (not a Pi): never a power-on")
shutil.rmtree(tmp, ignore_errors=True)
srv = (ROOT / "deploy" / "setup-server.py").read_text()
check('"boot": boot_info(),' in srv, "the panel's /onboard status carries it")

html = (ROOT / "index.html").read_text()
start = html.index("// ---- Take-off sound at power-on (#81)")
block = html[start:html.index("function playAlertSound() {", start)]
check("bootSound: true" in html.split("const DEFAULT_ALERT_SETTINGS")[1][:900], "the setting is on by default")
check("key: 'bootSound'" in html, "and has a row in Settings")
if not shutil.which("node"):
    print("skip page checks (no node)")
else:
    js = r"""
const store = {};
const localStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
let ON_DEVICE = true, netInfo = null, allowed = true, played = 0;
const alertSettings = { bootSound: true };
function soundAllowedNow() { return allowed; }
function alertQuiet() { return true; }
function scheduleNextAlert() {}
""" + block.replace("function playTakeoffSound() {", "function playTakeoffSound() { played++; return;") + r"""
const out = {};
const boot = (id, powerOn, uptimeS) => { netInfo = { boot: { id, powerOn, uptimeS } }; maybePlayBootSound(); return played; };
out.powerOn = boot('a', true, 40);
out.again = boot('a', true, 220);                 // a page reload in the same boot
out.reboot = boot('b', false, 30);
out.late = boot('c', true, 900);
alertSettings.bootSound = false; out.off = boot('d', true, 30); alertSettings.bootSound = true;
allowed = false; out.quiet = boot('e', true, 30); allowed = true; out.quietLater = boot('e', true, 200);
ON_DEVICE = false; out.remote = boot('f', true, 30);
console.log(JSON.stringify(out));
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stderr[-1500:])
    check(o.get("powerOn") == 1, "after a power-on the take-off sound plays")
    check(o.get("again") == 1, "once: reloading the page in the same boot doesn't play it again")
    check(o.get("reboot") == 1, "a reboot or watchdog reset plays nothing")
    check(o.get("late") == 1, "nor a power-on more than five minutes ago")
    check(o.get("off") == 1, "nor anything with the setting off")
    check(o.get("quiet") == 1 and o.get("quietLater") == 1,
          "inside quiet hours (or muted) it stays silent, and doesn't play later in that boot")
    check(o.get("remote") == 1, "and only the panel plays it, not a phone or laptop viewing the page")

    # ---- it plays alone (2026-10-28) ------------------------------------------
    # The boot block, the alert queue and the two plain chimes, run under node
    # with a stand-in clock, panel and speech; every sound, panel and sentence
    # is logged with its time.
    def function(head):
        f = html[html.index(head):]
        return f[:f.index("\n}\n") + 3]
    queue = html[html.index("// ---- One alert at a time"):html.index("function checkNearbyAlert(pl, range)")]
    chimes = function("function playAirportPhaseSound(") + function("function playLightningAlertSound(")
    takeoff = "function playTakeoffSound() {\n  markSoundBusy(TAKEOFF_SOUND_MS);"
    check(takeoff in block, "the take-off sound marks its length as busy")
    harness = r"""
let now = 0; const timers = [];
const performance = { now: () => now };
function setTimeout(fn, ms) { const t = { at: now + (ms || 0), fn }; timers.push(t); return t; }
function clearTimeout(t) { const i = timers.indexOf(t); if (i >= 0) timers.splice(i, 1); }
function advance(ms) { const end = now + ms; for (;;) { timers.sort((a, b) => a.at - b.at); const t = timers[0]; if (!t || t.at > end) break; timers.shift(); now = t.at; t.fn(); } now = end; }
const S = SCENARIO;
const store = Object.assign({}, S.store);
const localStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
let ON_DEVICE = S.onDevice !== false, netInfo = null;
const alertSettings = { bootSound: S.setting !== false };
function soundAllowedNow() { return S.allowed !== false; }
const log = [];                      // [what, ms]
let busyUntil = 0, speaking = 0;
function markSoundBusy(ms) { busyUntil = Math.max(busyUntil, now + ms); }
function alertQuiet() { return speaking === 0 && now >= busyUntil; }
function speak(text) { log.push(['words ' + text, now]); speaking++; setTimeout(() => speaking--, 4000); }   // a sentence takes 4 s
function playTones() { log.push(['lightning chime', now]); }
function soundTheme() { return { airportPhase: phase => log.push([phase + ' chime', now]) }; }
const classes = new Set();
const detailPanelEl = {
  classList: { contains: c => classes.has(c), add: c => classes.add(c), remove: c => classes.delete(c) },
  querySelector: () => null,
};
const detailBackdropEl = { classList: { add() {}, remove() {} } };
let detailPanelHex = null, detailDismissTimer = null;
function showDetailPanel(p, isAlert) { classes.add('show'); isAlert ? classes.add('alert') : classes.delete('alert'); log.push(['show ' + p.hex, now]); }
const planes = new Map([['a1', {}], ['b2', {}], ['e9', {}]]);
""" + block.replace(takeoff, takeoff + " log.push(['take-off', now]); return;") + chimes + queue + function("function hideDetailPanel() {") + r"""
const alert = (hex, urgent) => ({ pl: { hex }, label: urgent ? 'EMERGENCY' : 'WITHIN 2 MILES', urgent,
  sound: () => { log.push(['chime ' + hex, now]); markSoundBusy(3000); }, speech: () => hex });
function answer(boot) { netInfo = { boot }; maybePlayBootSound(); }
SCRIPT
console.log(JSON.stringify(log));
"""

    def run(script, **scenario):
        js = harness.replace("SCENARIO", json.dumps(scenario)).replace("SCRIPT", script)
        r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
        try:
            return [tuple(e) for e in json.loads(r.stdout.strip().splitlines()[-1])]
        except Exception:
            print(r.stderr[-1500:])
            return []

    # A power-on: the answer comes 1 s after load, with one aircraft already in
    # range; an emergency and two plain chimes come while the sound plays.
    log = run(r"""
advance(500); raiseAlert(alert('a1'));
advance(500); answer({ id: 'p', powerOn: true, uptimeS: 40 });
advance(1000); playAirportPhaseSound('takeoff'); playLightningAlertSound();
advance(1000); raiseAlert(alert('e9', true));
advance(30000); playAirportPhaseSound('landing'); playLightningAlertSound();
""")
    check(log[:1] == [("take-off", 1000)], "after a power-on the take-off sound plays as the answer comes, alone")
    check(len(log) > 1 and all(t >= 8000 for _, t in log[1:]),
          "no alert, chime or words until it has finished (7 s), though an aircraft was in range from the start")
    shows = [w for w, _ in log if w.startswith("show ")]
    check(shows == ["show e9", "show a1"] and ("words a1", 17000) in log,
          "the alerts raised meanwhile wait, not dropped, and come after it in turn, the emergency first")
    check(("show e9", 8000) in log, "an emergency is shown the moment the hold ends")
    check(not any(w in ("takeoff chime", "lightning chime") and t < 8000 for w, t in log)
          and ("landing chime", 33000) in log and ("lightning chime", 33000) in log,
          "the airport and lightning chimes during it are dropped; after it they sound as before")

    # No take-off sound: the hold ends with the answer, at 1 s.
    for label, kw in (("a reboot", dict(boot="{ id: 'r', powerOn: false, uptimeS: 30 }")),
                      ("a page reloaded later in the boot", dict(boot="{ id: 'q', powerOn: true, uptimeS: 900 }")),
                      ("a reload after it played this boot",
                       dict(boot="{ id: 'p', powerOn: true, uptimeS: 120 }", store={"stratoscan.bootSoundFor": "p"})),
                      ("the setting off", dict(boot="{ id: 'p', powerOn: true, uptimeS: 30 }", setting=False)),
                      ("quiet hours or mute", dict(boot="{ id: 'p', powerOn: true, uptimeS: 30 }", allowed=False)),
                      ("an answer without boot information", dict(boot="undefined"))):
        boot = kw.pop("boot")
        log = run("advance(500); raiseAlert(alert('a1'));\nadvance(500); answer(%s);\nadvance(100);" % boot, **kw)
        check(log[:3] == [("show a1", 1000), ("chime a1", 1000), ("words a1", 1000)],
              f"{label}: no take-off sound, and the waiting alert comes as soon as the answer does")

    # No answer at all: alerts wait 15 s at most.
    log = run("advance(500); raiseAlert(alert('a1'));\nadvance(29500);")
    check(log[:1] == [("show a1", 15000)], "with no answer, an alert waits 15 s at most")

    # An answer after that limit, while an alert is speaking: the sound waits
    # for the words, and the next alert waits for the sound.
    log = run(r"""
advance(500); raiseAlert(alert('a1'));
advance(15500); answer({ id: 'p', powerOn: true, uptimeS: 70 });
advance(1000); raiseAlert(alert('b2'));
advance(30000);
""")
    at = dict(log)
    check(at.get("show a1") == 15000 and at.get("take-off") == 19000,
          "a late answer still plays it, once the alert on screen has finished speaking")
    check(at.get("show b2", 0) >= 26000, "and the next alert waits for it to finish")

    log = run("raiseAlert(alert('a1')); answer({ id: 'p', powerOn: true, uptimeS: 30 }); advance(100);", onDevice=False)
    check(log[:1] == [("show a1", 0)] and "take-off" not in dict(log),
          "off the panel nothing waits: the alert shows at once")

print("boot sound checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
