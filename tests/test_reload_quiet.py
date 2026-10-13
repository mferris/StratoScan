#!/usr/bin/env python3
"""A memory-guard reload waits for an alert to finish, and alerts already
raised are not raised again after it (2026-10-13).

Seen on RDU: the shared-memory guard's reload landed six seconds into a
nearby alert; the voice stopped mid-sentence, the start-up picture showed,
and the reloaded page announced the same aircraft again.

The page's own code is run under node with a stand-in clock, timers,
location and sessionStorage, so this tests what the page does, not only
what it says.

Run: python3 tests/test_reload_quiet.py
"""
import json
import pathlib
import re
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


# The wiring, in the page
check("if (d && d.reload && !reloadWantedAt) reloadWhenQuiet();" in html,
      "the guard's reload request goes through reloadWhenQuiet, once")
check(html.count("location.reload();") >= 1 and "if (d && d.reload) location.reload();" not in html,
      "it no longer reloads on the spot")
for fn, ms in (("playAlertSound", 3000), ("playEmergencySound", 4000), ("playRareSound", 2000),
               ("playAirportPhaseSound", 2000)):
    body = html.split(f"function {fn}(")[1][:220]
    check(f"markSoundBusy({ms})" in body, f"{fn} marks the next {ms // 1000} s as busy")
speak = html.split("function speak(text")[1][:1800]
check("speechInFlight++" in speak and "src.onended = finished" in speak and "finished(); /*" in speak,
      "a spoken alert counts as in flight from its fetch until it has played, or failed")
check("setTimeout(finished, 30000)" in speak, "and can never hold a reload for more than 30 s")
check("window.addEventListener('pagehide', carryAlerts)" in html, "alerts are carried across any reload")
create = html.split("planes.set(n.hex, {")[1][:900]
check("carriedAlerts.planes.get(n.hex)" in create, "a reloaded page restores an aircraft's alert flags when it first sees it")

# The behaviour, run under node
block = "//" + html.split("// ---- A reload waits for a quiet moment")[1].split("const spokenBuffers")[0]
if not shutil.which("node"):
    print("skip behaviour checks (no node)")
else:
    js = r"""
let now = 0; const timers = [];
const performance = { now: () => now };
const Date = { now: () => 1_800_000_000_000 + now };
function setTimeout(fn, ms) { timers.push({ at: now + ms, fn }); }
function advance(ms) { const end = now + ms; for (;;) { timers.sort((a, b) => a.at - b.at); const t = timers[0]; if (!t || t.at > end) break; timers.shift(); now = t.at; t.fn(); } now = end; }
let reloads = 0; const location = { reload: () => { reloads++; } };
const store = new Map(); const sessionStorage = { getItem: k => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, v), removeItem: k => store.delete(k) };
const listeners = {}; const window = { addEventListener: (e, f) => { listeners[e] = f; } };
let lightningAlerted = false;
const planes = new Map();
""" + block + r"""
const out = {};
// 1. nothing sounding: the reload happens at once
reloadWhenQuiet(); out.quietNow = reloads === 1;
// 2. a chime then a spoken alert: the reload waits for both
reloads = 0; reloadWantedAt = 0;
markSoundBusy(3000); speechInFlight++;
reloadWhenQuiet(); advance(2000); out.heldDuringChime = reloads === 0;
advance(2000); out.heldDuringSpeech = reloads === 0;
speechInFlight--; advance(600); out.afterSpeech = reloads === 1;
// 3. something that never finishes cannot hold it for ever
reloads = 0; reloadWantedAt = 0; speechInFlight = 5;
reloadWhenQuiet(); advance(RELOAD_WAIT_MAX_MS - 1000); out.heldUnderCap = reloads === 0;
advance(2000); out.capReleases = reloads === 1;
// 4. the flags go across
planes.set('a1b2c3', { alerted: true, rareAlerted: false, airportPhaseAlerted: 'landing' });
planes.set('ffffff', { alerted: false });
lightningAlerted = true;
carryAlerts();
const saved = JSON.parse(store.get(CARRIED_ALERTS_KEY));
out.saved = saved.planes;
out.lightning = saved.lightning;
console.log(JSON.stringify(out));
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stderr[-800:])
    check(o.get("quietNow") is True, "with nothing sounding, the reload happens at once")
    check(o.get("heldDuringChime") is True and o.get("heldDuringSpeech") is True,
          "during a chime and its spoken sentence, it waits")
    check(o.get("afterSpeech") is True, "and goes as soon as the sentence has finished")
    check(o.get("heldUnderCap") is True and o.get("capReleases") is True,
          "an alert that never finishes holds it at most a minute")
    check(o.get("saved") == {"a1b2c3": {"alerted": True, "airportPhaseAlerted": "landing"}},
          "only aircraft with an alert already raised are carried, with just those flags")
    check(o.get("lightning") is True, "so is the storm alert")

    # and the reloaded side: a fresh page reads them back, once, and only if recent
    js2 = r"""
let now = 0; const performance = { now: () => now }; function setTimeout() {}
const location = { reload() {} }; const window = { addEventListener() {} };
let lightningAlerted = false; const planes = new Map();
const store = new Map(); const sessionStorage = { getItem: k => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, v), removeItem: k => store.delete(k) };
store.set('stratoscan_carried_alerts_v1', JSON.stringify({ at: DATE_AT, planes: { a1b2c3: { alerted: true } }, lightning: true }));
const Date = { now: () => 1_800_000_000_000 };
""" + block + r"""
console.log(JSON.stringify({ n: carriedAlerts.planes.size, a: (carriedAlerts.planes.get('a1b2c3') || {}).alerted === true, lightning: lightningAlerted, left: store.size }));
"""
    def run2(at):
        r2 = subprocess.run(["node", "-e", js2.replace("DATE_AT", str(at))], capture_output=True, text=True, timeout=30)
        try:
            return json.loads(r2.stdout.strip().splitlines()[-1])
        except Exception:
            print(r2.stderr[-800:])
            return {}
    fresh = run2(1_800_000_000_000 - 60_000)
    stale = run2(1_800_000_000_000 - 11 * 60_000)
    check(fresh.get("n") == 1 and fresh.get("a") and fresh.get("lightning") is True and fresh.get("left") == 0,
          "a page loaded a minute after the reload restores them, and clears the record")
    check(stale.get("n") == 0 and stale.get("lightning") is False, "one loaded eleven minutes later starts fresh")

print("reload quiet checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
