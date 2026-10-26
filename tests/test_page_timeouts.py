#!/usr/bin/env python3
"""Nothing in the pages waits without a time limit (#86, 2026-10-26).

The owner asked that the radar never wait without limit on the free map or
anything else. The kiosk page waited on several things with no limit at all:
the Google Fonts @import held the page's script (and so the whole radar)
until the font host answered, start() awaited /config.json and receiver.json
before the draw loop, the aircraft poll and the heartbeat, the MapLibre
import could wedge the map for the life of the page, and every fetch but six
had no limit. The setup page's buttons could stay on "Joining…" for good
once the radar had moved to another network.

This scans both pages for any request without a signal, and runs the page's
own start(), withinTime(), deviceApi() and the setup page's api() under node
with stand-in requests that never answer.

Run: python3 tests/test_page_timeouts.py
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
html = (ROOT / "index.html").read_text()
setup = (ROOT / "deploy" / "setup-ui.html").read_text()
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def script(page):
    """The page's inline script, without its comment lines."""
    body = "\n".join(re.findall(r"<script>(.*?)</script>", page, re.S))
    return "\n".join(l for l in body.splitlines() if not l.strip().startswith("//"))


def calls(code, name):
    """Each call of `name`, with its whole argument list (brackets balanced)."""
    out = []
    for m in re.finditer(r"(?<![\w.$])" + re.escape(name) + r"\(", code):
        depth, j = 1, m.end()
        while depth and j < len(code):
            depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(code[j], 0)
            j += 1
        out.append(code[m.start():j])
    return out


def function(code, head):
    """A top-level function's source, from its head to its closing brace."""
    if head not in code:
        return ""
    start = code.index(head)
    return code[start:code.index("\n}\n", start) + 3]


page_js, setup_js = script(html), script(setup)

# ---- every request has a limit --------------------------------------------------------
for name, code in (("index.html", page_js), ("deploy/setup-ui.html", setup_js)):
    found = calls(code, "fetch")
    bare = [c for c in found if "signal:" not in c]
    check(len(found) >= (40 if name == "index.html" else 1) and not bare,
          f"{name}: all {len(found)} requests pass a time limit (signal: AbortSignal.timeout)")
    for c in bare:
        check(False, f"{name}: no limit on {' '.join(c.split())[:100]}")
    check("XMLHttpRequest" not in code and "EventSource" not in code and "WebSocket" not in code,
          f"{name}: and nothing asks the network any other way")
imports = calls(page_js, "import")
check(imports == ["import('./vendor/maplibre-gl.mjs')"], "the page's one module import is MapLibre")
init = function(page_js, "async function initMap()")
check("await withinTime(loadMapLibre(), MAPLIBRE_LOAD_TIMEOUT_MS);" in init,
      "the map waits for MapLibre for a limited time, not for ever")
check("catch (e)" in init and "mapRetryTimer = setTimeout(initMap, mapRetryMs);" in init.split("catch (e)")[1],
      "and a MapLibre that did not load, or not in time, is tried again with the map's backoff")

# ---- the fonts never hold the page ---------------------------------------------------------
styles = "\n".join(re.findall(r"<style>(.*?)</style>", html, re.S))
check("@import" not in styles, "no @import in the page's style (it holds the script until it answers)")
check(not re.search(r"<link[^>]+rel=\"stylesheet\"[^>]+href=\"https?:", html),
      "and no stylesheet from another host in the page's head")
check("const WEB_FONTS_URL = 'https://fonts.googleapis.com/" in page_js and "document.createElement('link')" in page_js
      and "document.head.appendChild(link)" in page_js, "the web fonts are added from the script, which nothing waits on")
check("document.fonts.load(f)" in page_js and ".then(redrawStaticLayers" in page_js.split("const WEB_FONTS_URL")[1][:900],
      "and the dial's text is drawn again once they come")

# ---- polls never pile up behind a slow answer ----------------------------------------------
for fn, flag in (("async function fetchAircraft()", "aircraftAsking"), ("async function refreshOnboarding()", "onboardAsking"),
                 ("async function refreshViewFeed()", "viewFeedAsking"), ("async function checkLightningNearby()", "lightningChecking")):
    body = function(page_js, fn)
    check(f"if ({flag}) return;" in body or f"|| {flag}) return;" in body, f"{fn.split()[2][:-2]}: one at a time")
check("if (e.name !== 'TimeoutError') connected = false;" in function(page_js, "async function fetchAircraft()"),
      "one slow aircraft poll is left to STALE_MS rather than flashing NO SIGNAL")
check("if (phonePollAsking) return;" in page_js and "if (otaPollAsking) return;" in page_js,
      "the Phone & Watch and update polls too")
check("setInterval(otaLoad" not in setup_js and "const poll = async () => { await otaLoad(); otaTimer = setTimeout(poll, 5000); };" in setup_js,
      "the setup page asks for the update's progress only once the last answer is in")
check("delete sampleBuffers[url]" in page_js, "a sound that did not load is asked for again, not silent for good")
check("setTimeout(() => shardCache.delete(bkey), SHARD_RETRY_MS);" in page_js and "if (data === undefined)" in page_js,
      "a type-database shard that did not come is asked for again in a minute")
check("if (map && !mapLoadedOnce) {" in page_js, "a wake re-arms the map's load timer only for a map that never loaded")
arm = function(page_js, "function armMapLoadTimer(thisMap)")
check("!mapIsOffline && mapBaseTiles === 0 ? await fetchOfflineMeta() : null" in arm and "createMap(offlineStyle(meta), true)" in arm,
      "an online map whose tiles never came goes to the map on the device, not online again")

# ---- the setup page says what to do -------------------------------------------------------
join = setup_js.split("$('joinBtn').onclick")[1].split("\n};\n")[0]
check("timeoutMs: 90 * 1000" in join and "open this page again there and press Join to keep it" in join,
      "Join gives up after 90 s and says how to keep the new network")
check("$('joinBtn').disabled = false;" in join.split("catch (e)")[1], "and the button comes back")
check("Reload this page to try again." in function(setup_js, "async function boot()"),
      "a first answer that never came says to reload, not a bare error")

# ---- the behaviour, run under node ---------------------------------------------------------
if not shutil.which("node"):
    print("skip behaviour checks (no node)")
    print("page timeout checks passed" if not fails else "%d FAILED" % fails)
    sys.exit(1 if fails else 0)


def node(js):
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        print(r.stdout[-800:], r.stderr[-1500:])
        return {}


within = function(page_js, "function withinTime(p, ms)")
wait = (re.search(r"^const START_WAIT_MS = .*$", page_js, re.M) or [""])[0]
start = function(page_js, "async function start()")

# start(): the page's own code, with every name it calls stood in for, on a stand-in clock.
harness = r"""
let now = 0; const timers = []; const calls = [];
const fake = {
  setTimeout(fn, ms) { const t = { at: now + ms, fn, every: 0 }; timers.push(t); return t; },
  setInterval(fn, ms) { const t = { at: now + ms, fn, every: ms }; timers.push(t); return t; },
  clearTimeout(t) { const i = timers.indexOf(t); if (i >= 0) timers.splice(i, 1); },
};
fake.clearInterval = fake.clearTimeout;
const flush = () => new Promise(r => setImmediate(r));
async function advance(ms) {
  const end = now + ms;
  for (;;) {
    await flush();
    timers.sort((a, b) => a.at - b.at);
    const t = timers[0];
    if (!t || t.at > end) break;
    now = t.at;
    if (t.every) t.at += t.every; else timers.shift();
    t.fn();
  }
  now = end; await flush();
}
function make(state) {
  const env = new Proxy(state, {
    has: (t, k) => typeof k === 'string' && (k in t || !(k in globalThis)),
    get: (t, k) => {
      if (k in t) return t[k];
      if (k === Symbol.unscopables) return undefined;
      if (/^[A-Z0-9_]+$/.test(k)) return 60 * 60 * 1000;     // any interval constant: not within this test
      return (...a) => { calls.push(k); return Promise.resolve(); };
    },
    set: (t, k, v) => { t[k] = v; return true; },
  });
  return new Function('env', 'with (env) { return (function () {\n' + SRC + '\nreturn start; })(); }')(env);
}
const never = () => new Promise(() => {});
const rdu = { lat: 35.8776, lon: -78.7875 };
async function scenario(quick) {
  calls.length = 0; timers.length = 0; now = 0;
  const seen = {};
  const state = Object.assign(Object.create(null), fake, {
    home: null, homeFromCache: false, FETCH_INTERVAL_MS: 1000,
    loadAirportConfig() { calls.push('config'); return quick ? Promise.resolve().then(() => calls.push('config-done')) : never(); },
    loadHome() { calls.push('loadHome'); if (!quick) return never(); state.home = rdu; return Promise.resolve(); },
    useCachedHome() { calls.push('useCachedHome'); if (!state.home) { state.home = rdu; state.homeFromCache = true; } },
    fetchAircraft() { calls.push('fetchAircraft'); },
    requestAnimationFrame(f) { calls.push('raf:' + f.name); seen.raf = seen.raf ?? now; },
    tick() {},
  });
  const start = make(state);
  start();
  await advance(10000);
  return { calls: [...calls], rafAt: seen.raf ?? null };
}
(async () => {
  const out = {};
  const slow = await scenario(false);
  out.slowDraws = slow.calls.includes('raf:tick');
  out.slowRafAt = slow.rafAt;
  out.slowPolls = slow.calls.includes('fetchAircraft');
  out.slowCached = slow.calls.includes('useCachedHome');
  out.slowHomeAsks = slow.calls.filter(c => c === 'loadHome').length;
  const fast = await scenario(true);
  out.fastRafAt = fast.rafAt;
  out.fastOrder = fast.calls.indexOf('config-done') >= 0 && fast.calls.indexOf('config-done') < fast.calls.indexOf('discoverDatabaseFolder');
  out.fastHomeFirst = fast.calls.indexOf('loadHome') < fast.calls.indexOf('fetchAircraft');
  out.fastNoCache = !fast.calls.includes('useCachedHome');
  out.fastHomeAsks = fast.calls.filter(c => c === 'loadHome').length;
  console.log(JSON.stringify(out));
})();
"""
o = node("const SRC = " + json.dumps(within + "\n" + wait + "\n" + start) + ";\n" + harness)
check(o.get("slowDraws") is True and o.get("slowPolls") is True,
      "a radar that never answers /config.json or receiver.json: the draw loop, heartbeat and aircraft poll start anyway")
check(isinstance(o.get("slowRafAt"), (int, float)) and o["slowRafAt"] <= 5000,
      f"within a few seconds (drawing at {o.get('slowRafAt')} ms)")
check(o.get("slowCached") is True, "on the last known home, as when the receiver is down")
check(o.get("slowHomeAsks") == 1, "and the receiver's retries do not pile up behind the one still waiting")
check(o.get("fastRafAt") == 0 and o.get("fastOrder") is True and o.get("fastHomeFirst") is True,
      "answers in time: the same as before, config first, then home, then the polls, with no wait")
check(o.get("fastNoCache") is True and o.get("fastHomeAsks") == 1, "and no cached home and no retries when the receiver answered")

# withinTime, deviceApi and the setup page's api(), with real timers and requests that never answer.
device = page_js[page_js.index("const DEVICE_API = "):]
device = device[:device.index("\n}\n", device.index("async function deviceApi(")) + 3]
api = setup_js[setup_js.index("let TOKEN = null"):]
api = api[:api.index("\n}\n", api.index("async function api(")) + 3]
js = r"""
const hang = (url, opts = {}) => new Promise((resolve, reject) => {
  opts.signal.addEventListener('abort', () => reject(opts.signal.reason));
});
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const settle = (p) => Promise.race([p.then(v => ({ v }), e => ({ e })), sleep(3000).then(() => ({ hung: true }))]);
const document = { getElementById: () => null };
const ON_DEVICE = true;
let fetch = hang;
""" + within + "\n" + device + "\n" + api + r"""
(async () => {
  const out = {};
  let r = await settle(withinTime(new Promise(() => {}), 30));
  out.withinLate = !!r.e && r.e.name === 'TimeoutError';
  r = await settle(withinTime(Promise.resolve(7), 1000));
  out.withinInTime = r.v === 7;
  r = await settle(deviceApi('/onboard/ota', { timeoutMs: 50 }));
  out.deviceGivesUp = !r.hung && !!r.e && /did not answer in time/.test(r.e.message);
  r = await settle(api('wifi/connect', { timeoutMs: 50, method: 'POST' }));
  out.apiGivesUp = !r.hung && !!r.e && r.e.timedOut === true && !r.e.status;
  fetch = async () => ({ ok: false, status: 400, json: async () => ({ error: { message: 'Wrong password.' } }) });
  r = await settle(api('wifi/connect', { method: 'POST' }));
  out.apiRefusal = !!r.e && r.e.message === 'Wrong password.' && r.e.status === 400 && !r.e.timedOut;
  let seen = null;
  fetch = async (url, opts) => { seen = opts; return { ok: true, status: 200, json: async () => ({ fine: 1 }) }; };
  r = await settle(api('status'));
  out.apiDefault = r.v && r.v.fine === 1 && seen.signal instanceof AbortSignal && !('timeoutMs' in seen);
  r = await settle(deviceApi('/onboard'));
  out.deviceDefault = r.v && r.v.fine === 1 && seen.signal instanceof AbortSignal && !('timeoutMs' in seen);
  console.log(JSON.stringify(out));
})();
"""
o = node(js)
check(o.get("withinLate") is True and o.get("withinInTime") is True, "withinTime gives up when late, and passes an answer in time through")
check(o.get("deviceGivesUp") is True, "the panel's setup calls give up with a plain message when the listener never answers")
check(o.get("apiGivesUp") is True, "the setup page's calls give up too, marked as no answer rather than a refusal")
check(o.get("apiRefusal") is True, "while a refusal still says what the radar said")
check(o.get("apiDefault") is True and o.get("deviceDefault") is True,
      "every call has a limit even when the caller names none, and the option never reaches the request")

print("page timeout checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
