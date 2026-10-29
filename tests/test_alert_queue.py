#!/usr/bin/env python3
"""Alerts take turns (2026-10-14).

On RDU, two alerts for two aircraft close together collided: the second
replaced the first's panel and both spoke at once. Now the second waits: the
panel says how many more are waiting, each alert has its time on screen and
its words finish before the next one's chime, closing the panel brings the
next, an emergency goes first, and one about an aircraft that has gone, or
that waited over a minute, is dropped.

The page's own queue code is run under node with a stand-in clock and panel,
off the device, with the take-off sound's hold (#81) in it: off the panel it
holds nothing, so all of this is as it was. tests/test_boot_sound.py runs the
hold on the panel.

Run: python3 tests/test_alert_queue.py
"""
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
html = (ROOT / "index.html").read_text()
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


start = html.index("// ---- One alert at a time")
end = html.index("function checkNearbyAlert(pl, range)")
block = html[start:end]
hide = html[html.index("function hideDetailPanel() {"):]
hide = hide[:hide.index("\n}\n") + 3]
hold = html[html.index("// ---- The take-off sound plays alone"):html.index("// ---- The chime, then the take-off")]

check(html.count("raiseAlert({") == 3, "nearby, notable and emergency alerts all go through the queue")
check("showDetailPanel(pl, true" not in html, "nothing opens an alert panel around it")
check("speech: () => announcementFor(pl)" in html, "an alert is worded when it is shown, so a waiting one is current")
check("urgent: true" in html.split("function checkEmergencySquawk")[1][:1500], "an emergency is marked urgent")

if not shutil.which("node"):
    print("skip behaviour checks (no node)")
else:
    js = r"""
let now = 0; const timers = [];
const performance = { now: () => now };
function setTimeout(fn, ms) { const t = { at: now + ms, fn }; timers.push(t); return t; }
function clearTimeout(t) { const i = timers.indexOf(t); if (i >= 0) timers.splice(i, 1); }
function advance(ms) { const end = now + ms; for (;;) { timers.sort((a, b) => a.at - b.at); const t = timers[0]; if (!t || t.at > end) break; timers.shift(); now = t.at; t.fn(); } now = end; }
const classes = new Set();
let tagMore = null;
const detailPanelEl = {
  classList: { contains: c => classes.has(c), add: c => classes.add(c), remove: c => classes.delete(c), toggle: (c, on) => on ? classes.add(c) : classes.delete(c) },
  querySelector: () => (classes.has('alert') ? { querySelector: () => tagMore, append: e => { tagMore = e; } } : null),
};
const detailBackdropEl = { classList: { add() {}, remove() {} } };
const document = { createElement: () => ({ className: '', textContent: '' }) };
let detailPanelHex = null, detailDismissTimer = null;
const shown = [], spoken = [];
function showDetailPanel(p, isAlert, label) { classes.add('show'); classes.toggle; isAlert ? classes.add('alert') : classes.delete('alert'); tagMore = null; detailPanelHex = p.hex; shown.push(`${p.hex}:${label}`); }
let speaking = 0;
function speak(text) { spoken.push(text); speaking++; setTimeout(() => speaking--, 4000); }   // a sentence takes 4 s
function alertQuiet() { return speaking === 0; }
const planes = new Map([['a1', {}], ['b2', {}], ['c3', {}], ['e9', {}]]);
const ON_DEVICE = false;     // a browser viewing the page
""" + hold + block + hide + r"""
const A = hex => ({ pl: { hex }, label: 'WITHIN 2 MILES', speech: () => `about ${hex}` });
const out = {};
out.noHold = bootHoldUntil === 0 && !bootHoldOn();
raiseAlert(A('a1'));
out.first = shown.slice();
raiseAlert(A('b2'));
out.secondWaits = shown.length === 1 && spoken.length === 1;
out.more = tagMore && tagMore.textContent;
raiseAlert(A('b2'));
out.noDuplicate = alertQueue.length === 1;
advance(8000);
out.notBeforeItsTime = shown.length === 1;
advance(1500);
out.secondShown = shown[1];
out.spokeInTurn = spoken.join(' | ');
out.noOverlap = speaking <= 1;
// an emergency arrives behind a waiting nearby alert: it goes first
raiseAlert(A('c3'));
raiseAlert({ pl: { hex: 'e9' }, label: 'EMERGENCY', urgent: true, speech: () => 'emergency e9' });
out.emergencyFirst = alertQueue[0].pl.hex === 'e9';
// closing the panel brings the next once the words have ended
hideDetailPanel();
advance(300);
out.waitsForWords = shown[shown.length - 1] === 'b2:WITHIN 2 MILES';   // b2's sentence is still being spoken
advance(5000);
out.afterClose = shown[shown.length - 1];
// one whose aircraft has gone is dropped
planes.delete('c3');
advance(20000);
out.dropped = !shown.some(s => s.startsWith('c3'));
// one that waited too long is dropped
advance(60000);
hideDetailPanel(); advance(10000);         // the emergency's panel closed, nothing waiting
raiseAlert(A('a1'));
const before = shown.length;
raiseAlert(A('b2'));
alertQueue[0].queuedAt = now - 61000;      // as if it had waited over a minute
advance(20000);
out.staleDropped = shown.length === before;
console.log(JSON.stringify(out));
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stderr[-800:])
    check(o.get("noHold") is True, "off the panel the take-off sound holds nothing back")
    check(o.get("first") == ["a1:WITHIN 2 MILES"], "the first alert shows at once")
    check(o.get("secondWaits") is True, "a second, for another aircraft, waits instead of replacing it or speaking over it")
    check((o.get("more") or "").strip() == "· 1 MORE", "and the panel says one more is waiting")
    check(o.get("noDuplicate") is True, "the same aircraft is not queued twice")
    check(o.get("notBeforeItsTime") is True, "the first keeps its time on screen")
    check(o.get("secondShown") == "b2:WITHIN 2 MILES", "then the second shows")
    check(o.get("spokeInTurn") == "about a1 | about b2" and o.get("noOverlap") is True, "and speaks after the first has finished")
    check(o.get("emergencyFirst") is True, "an emergency goes to the front of the queue")
    check(o.get("waitsForWords") is True, "closing the panel lets the current sentence finish first")
    check(o.get("afterClose") == "e9:EMERGENCY", "then brings the next one (the emergency)")
    check(o.get("dropped") is True, "an alert about an aircraft that has gone is dropped")
    check(o.get("staleDropped") is True, "and one that waited over a minute")

print("alert queue checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
