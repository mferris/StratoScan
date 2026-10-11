#!/usr/bin/env python3
"""The control arc's parts are listed twice in this repo: in full in the
case's README ("Buy"), and in one row of docs/SHOPPING.md ("Coming later").
When one changes, the other must too. This test fails until they agree.

KEY_PARTS names each part as both lists must mention it. A new part, or a
renamed one, fails here first: add it to KEY_PARTS and to both lists.

Run: python3 tests/test_control_arc_parts.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
README = ROOT / "enclosure" / "Retro Radar with Dials" / "README.md"
SHOPPING = ROOT / "docs" / "SHOPPING.md"

# (what to look for in the README's table, what to look for in SHOPPING's row)
KEY_PARTS = [
    ("EC11 rotary encoder with push switch, 20 mm D shaft", "EC11 rotary encoder with push switch and 20 mm D shaft"),
    ("12 mm momentary push button", "12 mm momentary"),
    ("5 mm RGB LED, common cathode", "5 mm common-cathode RGB LED"),
    ("220 Ω resistors", "220 Ω resistors"),
    ("M3 x 10 screws", "M3 x 10 screws"),
    ("M3 x 5 heat-set inserts", "M3 x 5 inserts"),
    ("M2.5 x 8 countersunk self-tapping screws", "M2.5 x 8 countersunk"),
    ("Thin hook-up wire", "thin wire"),
    ("Female jumper housings", "header jumpers"),
]
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


text = README.read_text()
buy = text[text.index("## Buy"):]
buy = buy[:buy.index("\n## ", 1)]
rows = [l for l in buy.splitlines() if l.startswith("| ") and not l.startswith("| Part") and not l.startswith("|---")]
names = [r.split("|")[1].strip() for r in rows]
check(len(names) == len(KEY_PARTS),
      "the README lists %d parts and the test knows %d (a part was added or removed: update KEY_PARTS, "
      "docs/SHOPPING.md and the private order list)" % (len(names), len(KEY_PARTS)))
for want, _ in KEY_PARTS:
    check(any(want in n for n in names), "the README lists: %s" % want)

shop = SHOPPING.read_text()
row = [l for l in shop.splitlines() if "control arc" in l.lower() and "5.1" in l]
check(len(row) == 1, "docs/SHOPPING.md has one row for the control arc")
for _, want in KEY_PARTS:
    check(bool(row) and want in row[0], "the shopping list's row mentions: %s" % want)
check(bool(row) and "Retro%20Radar%20with%20Dials/README.md#buy" in row[0], "and points to the README's full list")

print("control arc parts checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
