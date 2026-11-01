#!/usr/bin/env python3
"""A tap on a control drawn over the map is that control's (2026-11-01).

On the panel the status pill at the bottom only flashed when touched, and
when an aircraft's label lay under it, a touch opened that aircraft's
details instead. The pill listened for 'click', which the browser sends
after pointerup, so its stopPropagation came too late: the stage's own
pointerup handler had already picked the aircraft under the finger. Its tap
now opens Device setup (WiFi first, the pill's detail above it) on the radar,
and every overlay control is listed in OVERLAY_CONTROLS, which the stage's
drag and tap handlers both leave alone.

The page's own listeners for the pill, the gear, the rewind button, the zoom,
home and lock buttons and the stage run under node with stand-in elements,
and a touch is dispatched as the browser does: pointerdown, pointerup, click,
each from the target up to the stage, with an aircraft label under every
control.

Run: python3 tests/test_overlay_taps.py
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


code = "\n".join(l for l in html.splitlines() if not l.strip().startswith("//"))


def statement(start):
    """The statement beginning at index start, to its balanced end."""
    depth, i, quote = 0, start, None
    while i < len(code):
        c = code[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c == "/" and code[i + 1:i + 2] == "/":
            i = code.find("\n", i)       # a trailing comment, apostrophes and all
            continue
        elif c in "'\"`":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0 and code[i + 1:i + 2] in (";", "\n"):
                return code[start:i + 2]
        i += 1
    return ""


def all_statements(head):
    return [statement(m.start()) for m in re.finditer(re.escape(head), code)]


def line(pattern):
    m = re.search(pattern, code, re.M)
    return m.group(0) if m else ""


def function(head):
    if head not in code:
        return ""
    start = code.index(head)
    return code[start:code.index("\n}\n", start) + 3]


CONTROLS = ["gearBtn", "rewindBtn", "zoomInBtn", "zoomOutBtn", "homeBtn", "lockBtn", "netPill"]

# Static: every overlay control the markup draws over the map is listed.
listed = line(r"^const OVERLAY_CONTROLS = .*$")
check(all(f"#{c}" in listed for c in CONTROLS), "OVERLAY_CONTROLS lists the pill, the lock and every other button over the map")
check("OVERLAY_CONTROLS" in line(r"^const VIEW_NOT_A_DRAG = .*$"), "a press on any of them is never a drag of the map")
check(not re.search(r"getElementById\('netPill'\)\.addEventListener\('click'", code),
      "the pill no longer waits for 'click', which comes after the stage has picked an aircraft")

src = "\n".join([
    line(r"^const OVERLAY_CONTROLS = .*$"), line(r"^const VIEW_NOT_A_DRAG = .*$"), line(r"^const VIEW_STEP = .*$"),
    line(r"^const viewPointers = .*$"), line(r"^let viewGesture = .*$"), line(r"^let viewTapSuppressed = .*$"),
    function("function syncFingers("), function("function stageToCanvas("), function("function pinchState("),
    function("function viewPointerEnd("), function("function openNetworkSettings("),
    function("function enterDeviceSetup("), function("function deviceNetLine("), function("function renderNetStatus("),
    line(r"^let deviceShowsNet = .*$"),
    line(r"^let netPillPress = .*$"),
    *all_statements("document.getElementById('netPill').addEventListener("),
    *all_statements("gearBtnEl.addEventListener('pointerup'"),
    *all_statements("document.getElementById('rewindBtn').addEventListener('pointerup'"),
    *all_statements("for (const [id, fn] of [['zoomInBtn'"),
    *all_statements("stage.addEventListener('pointer"),
])

if not shutil.which("node"):
    print("skip behaviour checks (no node)")
else:
    js = r"""
class Element {
  constructor(id, parent) { this.id = id; this.parentNode = parent; this.listeners = {}; this.classes = new Set(); this.dataset = {}; this.textContent = ''; this.scrollTop = 0; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  closest(sel) {
    const ids = sel.split(',').map(s => s.trim().replace(/^#/, ''));
    for (let el = this; el; el = el.parentNode) if (ids.includes(el.id)) return el;
    return null;
  }
  get classList() { const c = this.classes; return { contains: k => c.has(k), add: k => c.add(k), remove: k => c.delete(k), toggle: (k, on) => on ? c.add(k) : c.delete(k) }; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 1080, height: 1080 }; }
}
const stage = new Element('stage', null);
const els = {};
for (const id of ['gearBtn', 'rewindBtn', 'zoomInBtn', 'zoomOutBtn', 'homeBtn', 'lockBtn', 'netPill', 'netPillText', 'detailPanel', 'settingsPanel'])
  els[id] = new Element(id, stage);
els.netPill.classList.add = () => {}; els.netPill.classList.remove = () => {};
els.netPillText.parentNode = els.netPill;
els.netPill.dataset.detail = 'Not connected to any network';
els.netPillText.textContent = 'NO NETWORK';
const document = { getElementById: id => els[id] };
const gearBtnEl = els.gearBtn, detailPanelEl = els.detailPanel, settingsPanelEl = els.settingsPanel;
const W = 1080, CX = 540, CY = 540;
let ON_DEVICE = true, home = null, followHex = null, viewLocked = false;
const view = { ox: 0, oy: 0, scale: 1 };
const locEl = {};
let viewFingers = 0, settingsSection = null, deviceView = null, deviceMsg = '';
const log = [];
const plane = { hex: 'a1b2c3' };
function findPlaneAtStagePoint() { return plane; }     // a label under every control
function findGhostAtStagePoint() { return null; }
function showDetailPanel(p) { log.push('detail'); detailPanelEl.classList.add('show'); }
function hideDetailPanel() { detailPanelEl.classList.remove('show'); }
function showGhostPanel() { log.push('ghost'); }
function showSettingsPanel() { log.push('settings'); settingsSection = null; deviceMsg = ''; settingsPanelEl.classList.add('show'); }
function hideSettingsPanel() { log.push('settings-closed'); settingsPanelEl.classList.remove('show'); }
function showRewindPanel() { log.push('rewind'); settingsSection = 'rewind'; settingsPanelEl.classList.add('show'); }
function renderSettingsPanel() {}
function loadDeviceStatus() { return Promise.resolve(); }
let otaState = null, netState = { cls: 'bad', text: 'NO NETWORK', detail: 'Not connected to any network' };
function loadOtaStatus() { log.push('ota'); otaState = { state: 'applying' }; return Promise.resolve(); }
function startOtaPolling() { log.push('ota-poll'); }
function netStatusState() { return netState; }
function esc(t) { return String(t); }
function showToast(t) { log.push('toast:' + t); }
function zoomViewAbout() { log.push('zoom'); }
function getAudioCtx() { return { resume: () => Promise.resolve() }; }
function goHome() { log.push('home'); }
function setLocked() { log.push('lock'); }
function setView() { log.push('pan'); }
""" + src + r"""
// One touch, as Chromium delivers it: each event from the target up through
// its ancestors to the stage, stopping where a listener stops it.
function dispatch(target, type, ev) {
  let stopped = false;
  const e = { ...ev, type, target, stopPropagation() { stopped = true; }, preventDefault() {} };
  for (let el = target; el && !stopped; el = el.parentNode)
    for (const fn of (el.listeners[type] || [])) fn(e);
}
function tap(target, x = 540, y = 1018, id = 1) {
  const ev = { pointerId: id, clientX: x, clientY: y, button: 0, isPrimary: true, pointerType: 'touch' };
  dispatch(target, 'pointerdown', ev);
  dispatch(target, 'pointerup', ev);
  dispatch(target, 'pointerleave', ev);
  dispatch(target, 'click', ev);
}
const reset = () => { log.length = 0; detailPanelEl.classList.remove('show'); settingsPanelEl.classList.remove('show'); settingsSection = null; };
(async () => {
  const out = {};
  for (const id of ['gearBtn', 'rewindBtn', 'zoomInBtn', 'zoomOutBtn', 'homeBtn', 'lockBtn', 'netPill', 'netPillText']) {
    reset(); tap(els[id]);
    out[id] = { log: log.filter(x => !x.startsWith('ota')), fingers: viewPointers.size };
  }
  reset(); tap(els.netPillText); await Promise.resolve();
  await Promise.resolve(); await Promise.resolve();
  out.pillOpens = { section: settingsSection, open: settingsPanelEl.classList.contains('show'), line: deviceNetLine(), msg: deviceMsg,
                    ota: log.includes('ota') && log.includes('ota-poll') };
  // The line follows the network while the panel is open.
  netState = { cls: 'ok', text: 'ONLINE', detail: 'TestNet · 192.168.1.23' };
  renderNetStatus();
  out.pillLive = deviceNetLine();
  // Into Device setup again from the menu: no line from the earlier visit.
  deviceMsg = 'stale'; enterDeviceSetup(false);
  out.menuEntry = { line: deviceNetLine(), msg: deviceMsg };
  netState = { cls: 'bad', text: 'NO NETWORK', detail: 'Not connected to any network' }; renderNetStatus();
  openNetworkSettings();
  tap(els.netPillText);
  out.pillAgainCloses = !settingsPanelEl.classList.contains('show');
  reset(); ON_DEVICE = false; tap(els.netPill); ON_DEVICE = true;
  out.publicToast = [...log];
  // A drag that begins on the map and ends over the pill is not a tap on it.
  reset();
  const ev = { pointerId: 7, clientX: 540, clientY: 700, button: 0, isPrimary: true, pointerType: 'touch' };
  dispatch(stage, 'pointerdown', ev);
  dispatch(stage, 'pointermove', { ...ev, clientY: 1018 });
  dispatch(els.netPill, 'pointerup', { ...ev, clientY: 1018 });
  dispatch(stage, 'pointerleave', { ...ev, clientY: 1018 });
  out.dragOntoPill = [...log];
  // And a tap on the open map still picks the aircraft.
  reset(); tap(stage, 540, 300, 9);
  out.mapTap = [...log];
  console.log(JSON.stringify(out));
})();
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stdout[-800:], r.stderr[-1500:])

    def did(key):
        return (o.get(key) or {}).get("log", ["(did not run)"])

    for key, expect, what in [
        ("netPill", ["settings"], "the pill"),
        ("netPillText", ["settings"], "the pill's words"),
        ("gearBtn", ["settings"], "the gear"),
        ("rewindBtn", ["rewind"], "the rewind button"),
        ("zoomInBtn", ["zoom"], "zoom in"),
        ("zoomOutBtn", ["zoom"], "zoom out"),
        ("homeBtn", ["home"], "home"),
        ("lockBtn", ["lock"], "the lock"),
    ]:
        check(did(key) == expect, f"a touch on {what} over an aircraft's label does its own job, never the aircraft's details ({did(key)})")
        check((o.get(key) or {}).get("fingers") == 0, f"and leaves no finger held on the map ({what})")
    po = o.get("pillOpens") or {}
    check(po.get("open") is True and po.get("section") == "device",
          "on the radar the pill opens Device setup, where WiFi is")
    check("NO NETWORK: Not connected to any network" in (po.get("line") or ""), "with the pill's own detail at the top")
    check(po.get("msg") == "", "kept apart from the panel's own messages")
    check(po.get("ota") is True, "and the update row loaded (and a running update followed), as from the menu")
    check("ONLINE: TestNet" in (o.get("pillLive") or ""), "the pill's line follows the network while the panel is open")
    me = o.get("menuEntry") or {}
    check(me.get("line") == "" and me.get("msg") == "", "and entering Device setup from the menu later shows no stale line")
    check(o.get("pillAgainCloses") is True, "and a second touch on the pill closes it, as the gear does")
    check(o.get("publicToast") == ["toast:Not connected to any network"],
          "a public viewer, with no network settings to open, is shown the detail")
    check("settings" not in (o.get("dragOntoPill") or ["settings"]) and "detail" not in (o.get("dragOntoPill") or ["detail"]),
          "a drag of the map that ends on the pill opens nothing")
    check(o.get("mapTap") == ["detail"], f"and the next touch on the open map still opens the aircraft under it ({o.get('mapTap')})")

print("overlay tap checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
