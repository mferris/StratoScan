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

And a cabin ding first (2026-10-28): the owner asked for the "ding" heard
inside an airliner, then the take-off. Both go on the audio clock at once,
the take-off 0.2-0.4 s after the ding, and alerts wait for the whole of it.
The take-off's roar swells up from nothing, so started 1.3 s after the ding,
as at first, it left over 2 s of near-silence between them. Switching the
setting on in Settings plays it once, as a preview.

Run: python3 tests/test_boot_sound.py
"""
import importlib.util
import json
import pathlib
import re
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
let ON_DEVICE = true, netInfo = null, allowed = true;
const played = [];                   // each part of the startup sound, as it plays
const alertSettings = { bootSound: true };
function soundAllowedNow() { return allowed; }
function alertQuiet() { return true; }
function scheduleNextAlert() {}
function markSoundBusy() {}
function getAudioCtx() { return { currentTime: 0, state: 'running' }; }
""" + (block.replace("function playCabinDing(t0) {", "function playCabinDing(t0) { played.push('ding'); return;")
            .replace("function playTakeoffSound(t0) {", "function playTakeoffSound(t0) { played.push('take-off'); return;")) + r"""
const out = {};
const boot = (id, powerOn, uptimeS) => { netInfo = { boot: { id, powerOn, uptimeS } }; maybePlayBootSound(); return played.join(' '); };
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
    both = "ding take-off"
    check(o.get("powerOn") == both, "after a power-on the startup sound plays: the cabin ding, then the take-off")
    check(o.get("again") == both, "once: reloading the page in the same boot doesn't play it again")
    check(o.get("reboot") == both, "a reboot or watchdog reset plays nothing")
    check(o.get("late") == both, "nor a power-on more than five minutes ago")
    check(o.get("off") == both, "nor anything with the setting off")
    check(o.get("quiet") == both and o.get("quietLater") == both,
          "inside quiet hours (or muted) it stays silent, and doesn't play later in that boot")
    check(o.get("remote") == both, "and only the panel plays it, not a phone or laptop viewing the page")

    # ---- it plays alone (2026-10-28) ------------------------------------------
    # The boot block, the alert queue and the two plain chimes, run under node
    # with a stand-in clock, panel, speech and audio context; every sound,
    # panel and sentence is logged with its time. The startup sound runs as it
    # is: the stand-in context logs the ding and the take-off at the times they
    # are put on the audio clock for, and when the last of them stops.
    def function(head):
        f = html[html.index(head):]
        return f[:f.index("\n}\n") + 3]
    queue = html[html.index("// ---- One alert at a time"):html.index("function checkNearbyAlert(pl, range)")]
    chimes = function("function playAirportPhaseSound(") + function("function playLightningAlertSound(")
    check("function playStartupSound() {\n  markSoundBusy(STARTUP_SOUND_MS);" in block,
          "the startup sound marks its whole length as busy")
    m = re.search(r"const STARTUP_SOUND_MS = (\d+);", block)
    hold = int(m.group(1)) if m else 0
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
const alertSettings = { bootSound: S.setting !== false, muted: S.muted === true };
function soundAllowedNow() { return !alertSettings.muted && S.allowed !== false; }   // as the page's: mute first
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
let shownLabel = null;
function showDetailPanel(p, isAlert, label) { shownLabel = label; classes.add('show'); isAlert ? classes.add('alert') : classes.delete('alert'); log.push(['show ' + p.hex, now]); }
const planes = new Map([['a1', {}], ['b2', {}], ['e9', {}]]);
let soundEnds = 0;                   // when the last source scheduled stops
const param = () => ({ value: 0, setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {} });
function audioNode(kind) {
  return { kind, type: 'sine', frequency: param(), gain: param(), Q: param(), connect: n => n,
    start(t) {   // the ding is sine partials; the take-off is noise and two other waves
      const part = kind === 'osc' && this.type === 'sine' ? 'ding' : 'take-off', ms = Math.round(t * 1000);
      if (!log.some(([w, at]) => w === part && at === ms)) log.push([part, ms]);
    },
    stop(t) { soundEnds = Math.max(soundEnds, Math.round(t * 1000)); } };
}
const audio = { get currentTime() { return now / 1000; }, sampleRate: 8000, state: 'running',
  createOscillator: () => audioNode('osc'), createGain: () => audioNode('gain'), createBiquadFilter: () => audioNode('filter'),
  createBufferSource: () => audioNode('noise'), createBuffer: (c, n) => ({ getChannelData: () => new Float32Array(n) }) };
function getAudioCtx() { return audio; }
function getMasterGain() { return audioNode('out'); }
""" + block + chimes + queue + function("function hideDetailPanel() {") + r"""
const alert = (hex, urgent) => ({ pl: { hex }, label: urgent ? 'EMERGENCY' : 'WITHIN 2 MILES', urgent,
  sound: () => { log.push(['chime ' + hex, now]); markSoundBusy(3000); }, speech: () => hex });
function answer(boot) { netInfo = { boot }; maybePlayBootSound(); }
SCRIPT
if (soundEnds) log.push(['sound ends', soundEnds]);
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
    at = dict(log)
    ding, takeoff, ends = at.get("ding", 0), at.get("take-off", 0), at.get("sound ends", 0)
    check(log[:2] == [("ding", ding), ("take-off", takeoff)] and 1000 <= ding <= 1100,
          "after a power-on the startup sound plays as the answer comes, alone: the cabin ding first")
    check(200 <= takeoff - ding <= 400,
          "then the take-off, %d ms after the ding on the audio clock, so its slow swell is heard a second after the ding, not two"
          % (takeoff - ding))
    others = [(w, t) for w, t in log if w not in ("ding", "take-off", "sound ends")]
    check(others and all(t >= ends for _, t in others),
          "no alert, chime or words until the whole of it has finished (%.2f s), though an aircraft was in range from the start"
          % ((ends - 1000) / 1000))
    check(ends <= 1000 + hold <= ends + 1000, "the hold (%d ms) covers all of it, and ends within a second of it" % hold)
    shows = [w for w, _ in log if w.startswith("show ")]
    check(shows == ["show e9", "show a1"] and ("words a1", 1000 + hold + 9000) in log,
          "the alerts raised meanwhile wait, not dropped, and come after it in turn, the emergency first")
    check(("show e9", 1000 + hold) in log, "an emergency is shown the moment the hold ends")
    check(not any(w in ("takeoff chime", "lightning chime") and t < 1000 + hold for w, t in log)
          and ("landing chime", 33000) in log and ("lightning chime", 33000) in log,
          "the airport and lightning chimes during it are dropped; after it they sound as before")

    # No take-off sound: the hold ends with the answer, at 1 s.
    for label, kw in (("a reboot", dict(boot="{ id: 'r', powerOn: false, uptimeS: 30 }")),
                      ("a page reloaded later in the boot", dict(boot="{ id: 'q', powerOn: true, uptimeS: 900 }")),
                      ("a reload after it played this boot",
                       dict(boot="{ id: 'p', powerOn: true, uptimeS: 120 }", store={"stratoscan.bootSoundFor": "p"})),
                      ("quiet hours or mute", dict(boot="{ id: 'p', powerOn: true, uptimeS: 30 }", allowed=False)),
                      ("an answer without boot information", dict(boot="undefined"))):
        boot = kw.pop("boot")
        log = run("advance(500); raiseAlert(alert('a1'));\nadvance(500); answer(%s);\nadvance(100);" % boot, **kw)
        check(log[:3] == [("show a1", 1000), ("chime a1", 1000), ("words a1", 1000)],
              f"{label}: no take-off sound, and the waiting alert comes as soon as the answer does")

    # The take-off sound switched off, or the panel muted: nothing to wait for,
    # so no hold at all, whenever the answer comes.
    for label, kw in (("the setting off", dict(setting=False)), ("the panel muted", dict(muted=True))):
        log = run("advance(500); raiseAlert(alert('a1'));\nadvance(9500); answer({ id: 'p', powerOn: true, uptimeS: 30 });\nadvance(100);", **kw)
        check(log[:1] == [("show a1", 500)] and not {"ding", "take-off"} & set(dict(log)),
              f"{label}: no hold, the alert shows the moment it is raised")

    # An aircraft squawking an emergency inside the ring at load: the poll
    # raises its plain alert and then its emergency, both in the hold. One
    # alert waits per aircraft, so the emergency must take the plain one's
    # place, not be dropped (it is never raised again while it squawks).
    log = run(r"""
advance(500); raiseAlert(alert('a1')); raiseAlert(alert('a1', true));
advance(500); answer({ id: 'r', powerOn: false, uptimeS: 30 });
advance(100); log.push(['label ' + shownLabel, now]);
advance(30000);
""")
    check([w for w, _ in log if w.startswith("show ")] == ["show a1"] and ("label EMERGENCY", 1100) in log,
          "an emergency raised in the hold for an aircraft whose plain alert waits replaces it, and is the one shown")

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
    check(at.get("show a1") == 15000 and 19000 <= at.get("ding", 0) <= 19100 and at.get("take-off", 0) > at["ding"],
          "a late answer still plays it, once the alert on screen has finished speaking")
    check(at.get("show b2", 0) >= at.get("sound ends", 10 ** 9), "and the next alert waits for all of it to finish")

    log = run("raiseAlert(alert('a1')); answer({ id: 'p', powerOn: true, uptimeS: 30 }); advance(100);", onDevice=False)
    check(log[:1] == [("show a1", 0)] and not {"ding", "take-off"} & set(dict(log)),
          "off the panel nothing waits: the alert shows at once")

    # ---- the ding is no louder than the nearby chime (2026-10-28) --------------
    # Its partials' peaks added up are the most it can reach; the nearby
    # chime's notes peak at 0.25.
    js = r"""
const peaks = [];
const param = () => ({ value: 0, setValueAtTime() {}, exponentialRampToValueAtTime() {}, linearRampToValueAtTime(v) { peaks.push(v); } });
const node = () => ({ frequency: param(), gain: param(), connect: n => n, start() {}, stop() {} });
function getAudioCtx() { return { currentTime: 0, createOscillator: node, createGain: node }; }
function getMasterGain() { return node(); }
""" + function("function playCabinDing(t0) {") + r"""
playCabinDing(0);
console.log(JSON.stringify(peaks));
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    try:
        peaks = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        peaks = []
        print(r.stderr[-1500:])
    check(len(peaks) > 1 and sum(peaks) <= 0.25,
          "the ding is no louder than the nearby chime: its partials peak at %.3f together, the chime at 0.25" % sum(peaks))

    # ---- Settings plays it when it is switched on (2026-10-28) ------------------
    # The settings panel's own tap handler, run with a stand-in row and switch.
    h = html.index("settingsPanelEl.addEventListener('pointerup', (e) => {")
    js = r"""
const handlers = {};
const settingsPanelEl = { addEventListener: (type, fn) => { handlers[type] = fn; } };
let settingsPointerStart = null;
const alertSettings = { bootSound: false, muted: false, nearby: true };
const heard = [];
function saveAlertSettings() {}
function renderSettingsPanel() {}
function allowThroughQuiet(ms) { heard.push('through quiet hours for ' + ms); }
function playStartupSound() { heard.push('ding and take-off'); }
const STARTUP_SOUND_MS = %d;
""" % hold + html[h:html.index("\n});\n", h) + 5] + r"""
function tapSwitch(key) {          // a tap on the switch in that setting's row
  const row = { dataset: { key }, classList: { contains: () => false } };
  const target = { closest: sel => (sel === '.sp-row' ? row : sel === '.sp-switch' ? {} : null) };
  handlers.pointerup({ target, clientX: 0, clientY: 0, stopPropagation() {} });
  return heard.splice(0);
}
const out = {};
out.on = tapSwitch('bootSound');
out.off = tapSwitch('bootSound');
alertSettings.muted = true;
out.muted = tapSwitch('bootSound').concat(tapSwitch('bootSound'));
alertSettings.muted = false;
out.other = tapSwitch('nearby').concat(tapSwitch('nearby'));
console.log(JSON.stringify(out));
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stderr[-1500:])
    check(o.get("on") == ["through quiet hours for %d" % hold, "ding and take-off"],
          "switching it on in Settings plays it once, as a preview, heard through quiet hours for all of it")
    check(o.get("off") == [], "switching it off plays nothing")
    check(o.get("muted") == [], "nor switching it on or off while the panel is muted")
    check(o.get("other") == [], "and no other switch plays it")

print("boot sound checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
