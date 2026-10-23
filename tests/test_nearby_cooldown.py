#!/usr/bin/env python3
"""One nearby alert per half hour per plane (#79, 2026-10-23).

A plane flying circuits came inside the 2-mile ring every five minutes, and
each lap re-armed the panel's nearby alert: it lit 26 times in two and a half
hours one night. The phone's alerts already wait half an hour per plane
(deploy/events.py COOLDOWN_S); the panel now does too, across reloads. The
page's own code runs under node with a stand-in clock and storage.

Run: python3 tests/test_nearby_cooldown.py
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


start = html.index("// ---- Nearby alert: once per half hour per plane (#79)")
fn = html.index("function checkNearbyAlert(pl, range)")
end = html.index("\n}\n", fn) + 3
block = html[start:end]
events = (ROOT / "deploy" / "events.py").read_text()
check(re.search(r'"low_overhead": 30 \* 60', events) is not None and "30 * 60 * 1000" in block,
      "the panel waits as long as the phone does (30 minutes)")

if not shutil.which("node"):
    print("skip behaviour checks (no node)")
else:
    js = r"""
let clock = 1_800_000_000_000;
Date.now = () => clock;
const store = {};
let localStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
const ALERT_RADIUS_NM = 1.738, ALERT_CLEAR_RADIUS_NM = 2.0;
const alertSettings = { nearby: true };
const wakes = [], alerts = [], counted = [];
function recordSightingOnce(hex, kind) { counted.push(hex); }
function wakeScreenForAlert(why) { wakes.push(why); }
function raiseAlert(a) { alerts.push(a.pl.hex); }
function playAlertSound() {}
function announcementFor() { return ''; }
const MIN = 60 * 1000;
function lap(pl) { checkNearbyAlert(pl, 1.2); checkNearbyAlert(pl, 2.6); }
const out = {};
const load = new Function('localStorage', 'Date', 'ALERT_RADIUS_NM', 'ALERT_CLEAR_RADIUS_NM', 'alertSettings',
  'recordSightingOnce', 'wakeScreenForAlert', 'raiseAlert', 'playAlertSound', 'announcementFor',
  BLOCK + '\nreturn { checkNearbyAlert, lastNearbyAlertAt };');
let page = load(localStorage, Date, ALERT_RADIUS_NM, ALERT_CLEAR_RADIUS_NM, alertSettings,
  recordSightingOnce, wakeScreenForAlert, raiseAlert, playAlertSound, announcementFor);
const checkNearbyAlert = (pl, r) => page.checkNearbyAlert(pl, r);
const circling = { hex: 'ac097f' };
for (let i = 0; i < 6; i++) { lap(circling); clock += 5 * MIN; }        // six laps, five minutes apart
out.lapsWake = wakes.length; out.lapsAlert = alerts.length; out.lapsCounted = counted.length;
lap({ hex: 'b2b2b2' });                                                 // another plane meanwhile
out.otherPlane = alerts[alerts.length - 1] === 'b2b2b2';
clock += 1 * MIN; lap(circling);                                        // 31 minutes after its first alert
out.afterHalfHour = alerts.filter(h => h === 'ac097f').length;
clock += 5 * MIN;
page = load(localStorage, Date, ALERT_RADIUS_NM, ALERT_CLEAR_RADIUS_NM, alertSettings,
  recordSightingOnce, wakeScreenForAlert, raiseAlert, playAlertSound, announcementFor);   // the 04:00 restart
lap({ hex: 'ac097f' });
out.afterReload = alerts.filter(h => h === 'ac097f').length;
clock += 3 * 60 * MIN;
page = load(localStorage, Date, ALERT_RADIUS_NM, ALERT_CLEAR_RADIUS_NM, alertSettings,
  recordSightingOnce, wakeScreenForAlert, raiseAlert, playAlertSound, announcementFor);
out.pruned = page.lastNearbyAlertAt.size;
console.log(JSON.stringify(out));
""".replace("BLOCK", json.dumps(block))
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stderr[-1500:])
    check(o.get("lapsWake") == 1 and o.get("lapsAlert") == 1,
          "six laps five minutes apart: one wake and one alert, not six")
    check(o.get("lapsCounted") == 6, "every lap is still a sighting (the store keeps its own 5-minute rule)")
    check(o.get("otherPlane") is True, "another plane meanwhile still alerts")
    check(o.get("afterHalfHour") == 2, "the same plane alerts again once half an hour has passed")
    check(o.get("afterReload") == 2, "a reload (the 04:00 restart) remembers the last alert")
    check(o.get("pruned") == 0, "and a reload hours later starts with nothing left over")

print("nearby cooldown checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
