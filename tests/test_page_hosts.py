#!/usr/bin/env python3
"""The outside hosts the radar's pages name, and what those hosts are told (2026-10-26).

Google Fonts serves the page's two typefaces to the panel, every browser at
home and every visitor to the public page. It is asked without a referrer,
which from the public page was the radar's public address beside each
visitor's IP.

Run: python3 tests/test_page_hosts.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
page = (ROOT / "index.html").read_text()
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


code = "\n".join(l for l in page.splitlines() if not l.strip().startswith("//"))
fonts = code.split("const WEB_FONTS_URL", 1)[-1][:900]
check("link.referrerPolicy = 'no-referrer';" in fonts and fonts.index("referrerPolicy") < fonts.index("link.href = WEB_FONTS_URL"),
      "Google Fonts is asked for the stylesheet without a referrer, set before the request starts")
check(not re.search(r"<link[^>]+fonts\.googleapis", page), "and no stylesheet link in the markup asks it with one")

print("page host checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
