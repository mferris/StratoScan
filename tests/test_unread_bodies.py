#!/usr/bin/env python3
"""Unread response bodies are let go (2026-10-15).

Chromium hands each response body to the page through a 2 MB shared-memory
pipe, mapped until the Response is garbage-collected. The kiosk's
fire-and-forget posts (sighting classifications and records, the wake
pings) and the error replies nobody read left a few a minute: found with
DevTools on the first unit, 10 of 17 sighting posts in 3 minutes never
finished, and the renderer's shared memory grew 6-10 MB a minute, so the shm
guard reloaded the page every ~80 minutes.

The page now cancels any body still unread 10 s after its response arrived,
and the posts that never want their reply let it go at once. This runs the
page's own wrapper under node and checks the call sites.

Run: python3 tests/test_unread_bodies.py
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


main = html[html.index("</div>\n\n<script>\n") + len("</div>\n\n<script>\n"):]
code = "\n".join(l for l in main.splitlines() if not l.strip().startswith("//"))
first_fetch = re.search(r"(?<![.\w])fetch\(", code.split("window.fetch = async function")[1]).start()
check(code.index("window.fetch = async function") < code.index("fetch('/data/perf-debug.json'"),
      "the page wraps fetch before its first request")
check("drain" in code[:2000] and "UNREAD_BODY_MS = 10000" in code[:2000], "with a 10 s limit and a drain() for replies nobody wants")

# Every fire-and-forget request lets its reply go.
for m in re.finditer(r"^.*\bfetch\([^\n]*\.catch\([^\n]*$", code, re.M):
    line = m.group(0)
    if ".then(" not in line or "drain" not in line:
        check(False, f"a fire-and-forget request drains its reply: {line.strip()[:90]}")
def statements(pattern):
    """Each call matching `pattern`, up to the end of its statement."""
    out = []
    for m in re.finditer(pattern, code):
        start = code.rfind("\n", 0, m.start()) + 1          # from its line's start: drain(await ...)
        end = code.find(";\n", m.start())
        out.append(code[start:end if end > 0 else m.start() + 300])
    return out


wake = statements(r"fetch\('/wake")
check(len(wake) >= 6 and all("drain" in w for w in wake), f"all {len(wake)} wake pings let their replies go")
store = [st for st in statements(r"(?<!function )storeWrite\(") if "return fetch(url" not in st]
check(len(store) >= 4 and all("drain" in st for st in store), f"all {len(store)} store writes read or drain their replies")
check("res && res.ok ? res.json() : (drain(res), null)" in code, "a refused sighting count's reply is let go too")

# The wrapper itself, run under node with a stand-in fetch and clock.
if not shutil.which("node"):
    print("skip behaviour checks (no node)")
else:
    block = main[main.index("const nativeFetch"):main.index("\n}\n", main.index("function drain(")) + 3]
    js = r"""
let now = 0; const timers = [];
function setTimeout(fn, ms) { timers.push({ at: now + ms, fn }); }
function advance(ms) { now += ms; for (const t of timers.splice(0)) { if (t.at <= now) t.fn(); else timers.push(t); } }
function resp(body = true) {
  const r = { bodyUsed: false, cancelled: 0 };
  r.body = body ? { cancel() { r.cancelled++; return Promise.resolve(); } } : null;
  r.json = async () => { r.bodyUsed = true; return {}; };
  return r;
}
const queue = [];
const window = { fetch: async () => queue.shift() };
""" + block + r"""
(async () => {
  const out = {};
  const unread = resp(); queue.push(unread); await window.fetch('/x');
  advance(9000); out.notYet = unread.cancelled === 0;
  advance(2000); out.unreadCancelled = unread.cancelled === 1;
  const read = resp(); queue.push(read); const r2 = await window.fetch('/y'); await r2.json();
  advance(20000); out.readKept = read.cancelled === 0;
  const empty = resp(false); queue.push(empty); await window.fetch('/z'); advance(20000); out.noBodyFine = true;
  const now1 = resp(); out.drainNow = drain(now1) === now1 && now1.cancelled === 1;
  out.drainNull = drain(null) === null;
  console.log(JSON.stringify(out));
})();
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
        print(r.stderr[-800:])
    check(o.get("notYet") is True and o.get("unreadCancelled") is True, "a body nobody reads is cancelled after 10 s, not before")
    check(o.get("readKept") is True, "a body the page is reading is never touched")
    check(o.get("noBodyFine") is True, "a reply without a body (204) is fine")
    check(o.get("drainNow") is True and o.get("drainNull") is True, "drain() lets a reply go at once, and takes none")

print("unread body checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
