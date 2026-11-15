#!/usr/bin/env python3
"""The radar's on-screen keyboard (2026-11-15).

A radar is set up from its own round screen, WiFi password and all, so the
page draws a keyboard. It was rows of 10, 9 and 7 small keys centred under
each other: it tapered toward the bottom, took about half the screen's
width, and had no quotes, brackets, comma or semicolon, so some WiFi
passwords could not be typed on it.

Now it is laid out as a phone's is: every row ten keys' width, the third
flanked by shift and delete, a wide space bar, Cancel and Hide above the
field; three layers that between them hold every printable ASCII character;
and the whole block inside the round panel's circle.

These read index.html.

Run: python3 tests/test_kiosk_keyboard.py
"""
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
html = (ROOT / "index.html").read_text()
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


block = html.split("const KBD_ROWS = {")[1].split("};")[0]
rows = {}
for name, body in re.findall(r"(\w+):\s*\[(.*?)\],\s*$", block, re.M):
    # each row is a JS string in single or double quotes; undo its escapes
    strs = re.findall(r"""'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)\"""", body)
    rows[name] = [re.sub(r"\\(.)", r"\1", a or b) for a, b in strs]
check(set(rows) == {"lower", "upper", "num", "sym"} and all(len(r) == 3 for r in rows.values()),
      "four sets of three rows: letters, capitals, numbers, symbols")
have = set("".join("".join(r) for r in rows.values())) | {" "}
missing = "".join(chr(c) for c in range(32, 127) if chr(c) not in have)
check(missing == "", "every printable ASCII character can be typed" + (f" (missing {missing!r})" if missing else ""))
check(all(len(r[0]) == 10 for r in rows.values()), "the top row is ten keys in every layer")
check(all(len(r[1]) in (9, 10) and len(r[2]) == 7 for r in rows.values()),
      "the middle row is nine or ten, and the third seven between its two wide keys")
check(rows["upper"] == [r.upper() for r in rows["lower"]], "capitals are the letters' own")
check(all(c in "".join(rows["num"]) for c in "0123456789-."), "a latitude or longitude is typed without leaving the number layer")

draw = html.split("function drawKeyboard() {")[1].split("\ndocument.getElementById('kbd').addEventListener")[0]
units = lambda action: float(re.search(r"'" + action + r"', ([\d.]+)\)", draw).group(1))
check(units("shift") == units("back") == units("more") == 1.5 and 7 + 2 * 1.5 == 10,
      "shift (or the other layer) and delete make the third row ten keys wide")
check(units("mode") + units("space") + units("done") == 10 and units("space") == 5, "the bottom row is ten wide, half of it the space bar")
check("add(r2, '', 'pad', 'none', 0.5);" in draw and draw.count("'pad', 'none', 0.5") == 2,
      "nine letters sit half a key in from each side")
check("flex: var(--u, 1) 1 0;" in html and "d.style.setProperty('--u', units);" in draw,
      "keys grow from their units, so each row fills the same width")

tap = html.split("document.getElementById('kbd').addEventListener('pointerup'")[1].split("\n});")[0]
check("{ lower: 'upper', upper: 'caps', caps: 'lower' }[kbdState.mode]" in tap
      and "if (kbdState.mode === 'upper') kbdState.mode = 'lower';" in tap,
      "shift gives one capital, again all capitals, again none")
check("mode === 'upper' ? 'caps' : mode" in html, "a field that opens on capitals (ERASE) keeps them")
check('<div id="kbdBar"><div data-action="cancel">Cancel</div><div id="kbdMask" data-action="mask"></div></div>' in html
      and "closest('.kbd-row div, #kbdBar div')" in tap and "if (a === 'cancel') return closeKeyboard(null);" in tap,
      "Cancel and Hide sit above the field, out of the typing rows")
check("kbdState.secret ? (kbdState.masked ? 'Show' : 'Hide') : ''" in draw and "#kbdBar div:empty { visibility: hidden; }" in html,
      "Hide is only offered for a password")

# The block is a rectangle in the round panel: its corners must be inside the circle.
css = html.split("#kbd {")[1].split("/* Night dimming")[0]
w = {m for m in re.findall(r"#kbd(?:Bar|Keys|Field)\b[^}]*?width: (\d+)%", html)}
check(w == {"80"} and "padding: 0;" in css.split("}")[0], "the bar, the field and the keys are one width, 80% of the panel")
D = 1080.0
lo, vmin, hi = map(float, re.search(r"\.kbd-row div \{[^}]*?height: clamp\((\d+)px, ([\d.]+)vmin, (\d+)px\)", html, re.S).groups())
key_h = min(hi, max(lo, vmin / 100 * D))
bar = float(re.search(r"#kbdBar \{[^}]*?min-height: (\d+)px", html).group(1))
field = float(re.search(r"#kbdField \{[^}]*?min-height: (\d+)px", html, re.S).group(1))
gap = float(re.search(r"#kbd \{[^}]*?gap: (\d+)px", html, re.S).group(1))
row_gap = float(re.search(r"#kbdKeys \{[^}]*?gap: (\d+)px", html).group(1))
check(field >= 84 + 35, "the field has room for two lines of typing before it grows, so the keys don't move under the finger")
# the worst the block is meant for: a two-line label over two lines typed
height = bar + gap + (field + 20) + gap + 4 * key_h + 3 * row_gap
corner = math.hypot(0.80 * D / 2, height / 2)
check(corner < D / 2 - 20, f"on the 1080 px round panel its corners are inside the circle, a two-line label included ({corner:.0f} px from the middle, of 540)")
check(".kbd-row div:active, #kbdBar div:active {" in html, "a key shows it was pressed")

print("kiosk keyboard checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
