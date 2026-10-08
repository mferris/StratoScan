#!/usr/bin/env python3
"""The public page's Content-Security-Policy (security review 2026-10-04,
item 5): scripts only from the page's own files and its one inline block,
named by hash -- never 'unsafe-inline' -- so a script that slipped past the
page's escaping could still not run. Report-only until a quiet spell on the
live radar; violation reports are counted, bounded, never stored."""
import base64
import hashlib
import importlib.util
import json
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("fg", root / "deploy" / "funnel-gateway.py")
fg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fg)

fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


def h(b):
    return "'sha256-%s'" % base64.b64encode(hashlib.sha256(b).digest()).decode()


sample = b'<html><script src="vendor/x.js"></script><script>alert(1)</script>\n<script>\n  go();\n</script></html>'
policy = fg.page_csp(sample)
check(h(b"alert(1)") in policy and h(b"\n  go();\n") in policy, "each inline block is named by the hash of its exact bytes")
script_src = [d for d in policy.split("; ") if d.startswith("script-src")][0]
check("'unsafe-inline'" not in script_src and "'unsafe-eval'" not in script_src, "scripts are never 'unsafe-inline' or 'unsafe-eval'")
check(script_src.startswith("script-src 'self' 'sha256-"), "and come from the page's own files otherwise")
check(policy.startswith("default-src 'none'"), "everything not listed is refused")
for d in ("frame-ancestors 'none'", "object-src 'none'", "base-uri 'none'", "form-action 'none'", "report-uri /csp-report"):
    check(d in policy, "has %s" % d)
check(fg.page_csp(sample) is policy, "the policy for the same page is cached")

page = (root / "index.html").read_bytes()
real = fg.page_csp(page)
blocks = [b for b in re.findall(rb"<script>(.*?)</script>", page, re.S) if b.strip()]
check(len(blocks) == 1 and h(blocks[0]) in real, "the real page has one inline block and the policy names it")
text = page.decode("utf-8")
check(not re.search(r'<[a-z]+[^>]*\son[a-z]+\s*=', text), "the page has no inline event handlers (a hash policy would block them)")
check(not re.search(r'href=["\']javascript:', text), "and no javascript: links")
check("'self'" in real and "https://tiles.openfreemap.org" in real and "https://fonts.gstatic.com" in real, "the page's hosts are listed")
check(fg.CSP_HEADER == "Content-Security-Policy-Report-Only", "report-only by default (CSP_ENFORCE=1 switches it)")

# Reports: counted by directive and host, bounded, nothing else kept.
fg._csp_reports.clear()
report = {"csp-report": {"document-uri": "https://radar.example/?secret=1", "effective-directive": "img-src",
                         "blocked-uri": "https://evil.example/pixel.png"}}
fg.note_csp_report(json.dumps(report).encode())
fg.note_csp_report(json.dumps(report).encode())
fg.note_csp_report(b"not json at all")
s = fg.csp_summary()
check(s["reports"].get("img-src evil.example") == 2, "a report counts as directive + host")
check(s["reports"].get("unreadable") == 1, "a broken report counts as unreadable")
check("secret" not in json.dumps(s), "nothing from the report's page address is kept")
for i in range(fg.CSP_REPORT_KEYS + 20):
    fg.note_csp_report(json.dumps({"csp-report": {"violated-directive": "connect-src", "blocked-uri": "https://h%d.example" % i}}).encode())
check(len(fg.csp_summary()["reports"]) <= fg.CSP_REPORT_KEYS and fg.csp_summary()["reports"].get("other", 0) > 0,
      "the count of distinct keys is bounded; the rest go to 'other'")
check(fg.Handler._normalise("/csp-report") == "/csp-report" and not fg.Handler._is_read_only_public("/csp-report"),
      "/csp-report is its own path, not a store")
print("csp checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
