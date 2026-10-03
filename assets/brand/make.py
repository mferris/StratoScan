#!/usr/bin/env python3
"""Writes the StratoScan brand SVGs from one definition of the mark.

The mark ("Climb", Stratosphere colours): a radar scope with its sweep, and
three blips climbing toward it, changing colour with height -- green near the
ground, cyan, then white where the air runs out. Below about 32 px it drops to
two larger blips and a heavier ring, or the dots merge into a smudge.

    python3 assets/brand/make.py [--font PATH_TO_ChakraPetch-SemiBold.ttf]

Without --font the wordmark files are left as they are (the letters are
outlined from the font, so the SVGs never depend on it being installed);
fontTools is needed only for that step. The PNGs (app icon, social preview)
are rendered from these SVGs; see README.md.
"""
import argparse
import os

HERE = os.path.dirname(os.path.abspath(__file__))

SKY = "#0a1a3a"       # icon background
RING = "#274a86"
SWEEP = "#5ee7ff"
LOW, MID, HIGH = "#3ddc97", "#5ee7ff", "#ffffff"
SCAN_ON_LIGHT = "#0e7fa3"   # the cyan is too pale to read on white
INK = "#0a1a3a"


def mark(small=False, mono=None, tint=None):
    """The symbol's shapes in a 100x100 box. mono: one colour for everything
    (sweep fill kept faint); tint: grey levels for iOS's tinted icon."""
    c = lambda colour, grey: mono or (grey if tint else colour)
    if small:
        return (
            f'<circle cx="50" cy="50" r="38" fill="none" stroke="{c(RING, "#6b6b6b")}" stroke-width="7"/>'
            f'<path d="M50 50 L50 12 A38 38 0 0 1 82.9 31 Z" fill="{c(SWEEP, "#ffffff")}" opacity="0.35"/>'
            f'<line x1="50" y1="50" x2="82.9" y2="31" stroke="{c(SWEEP, "#ffffff")}" stroke-width="8" stroke-linecap="round"/>'
            f'<circle cx="30" cy="64" r="7" fill="{c(LOW, "#9a9a9a")}"/>'
            f'<circle cx="45" cy="36" r="8.5" fill="{c(HIGH, "#ffffff")}"/>'
        )
    ring_opacity = ' opacity="0.45"' if mono else ""
    return (
        f'<circle cx="50" cy="50" r="36" fill="none" stroke="{c(RING, "#6b6b6b")}" stroke-width="4"{ring_opacity}/>'
        f'<path d="M50 50 L50 14 A36 36 0 0 1 81.2 32 Z" fill="{c(SWEEP, "#ffffff")}" opacity="0.32"/>'
        f'<line x1="50" y1="50" x2="81.2" y2="32" stroke="{c(SWEEP, "#ffffff")}" stroke-width="4.5" stroke-linecap="round"/>'
        f'<circle cx="50" cy="50" r="3.4" fill="{c(SWEEP, "#ffffff")}"/>'
        f'<circle cx="27" cy="67" r="3.4" fill="{c(LOW, "#8a8a8a")}"/>'
        f'<circle cx="35" cy="53" r="4.2" fill="{c(MID, "#c4c4c4")}"/>'
        f'<circle cx="46" cy="36" r="5" fill="{c(HIGH, "#ffffff")}"/>'
    )


def svg(body, w=100, h=100, title="StratoScan"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{title}"><title>{title}</title>{body}</svg>\n')


def icon(body_fn, background):
    """A square app icon: the mark at 92% on a background (or none). iOS
    rounds the corners itself, cutting less than the margin left here."""
    bg = f'<rect width="100" height="100" fill="{background}"/>' if background else ""
    return svg(bg + f'<g transform="translate(4 4) scale(0.92)">{body_fn}</g>')


def wordmark_paths(font_path, text_colours, cap_height, tm=True):
    """'Strato' and 'Scan' outlined from the font, scaled so capitals are
    cap_height tall, then a small trademark sign (TM) at cap height in the
    first part's colour. Returns (svg_body, width).

    The TM is part of the wordmark so it travels with the name wherever the
    logo is shown: the radar's screen, the setup page, the README, the apps.
    It is TM, not R: (R) may only be used once the mark is registered."""
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont

    font = TTFont(font_path)
    cmap = font.getBestCmap()
    glyphs = font.getGlyphSet()
    caps = font["OS/2"].sCapHeight or font["head"].unitsPerEm * 0.7
    s = cap_height / caps
    x = 0.0
    out = []
    for part, colour in text_colours:
        pen = SVGPathPen(glyphs)
        for ch in part:
            name = cmap[ord(ch)]
            # font units are y-up; SVG is y-down, baseline at y=0
            glyphs[name].draw(TransformPen(pen, (s, 0, 0, -s, x, 0)))
            x += glyphs[name].width * s
        # ".name" means a class for the page's CSS to colour (the inline logo
        # follows the kiosk's themes); anything else is a fill colour
        paint = f'class="{colour[1:]}"' if colour.startswith(".") else f'fill="{colour}"'
        out.append(f'<path {paint} d="{pen.getCommands()}"/>')
    if tm:
        name = cmap[0x2122]
        bp = BoundsPen(glyphs)
        glyphs[name].draw(bp)
        x0, y0, x1, y1 = bp.bounds
        st = s * (0.36 * caps) / (y1 - y0)       # about a third of a capital
        gap = 0.06 * caps * s
        pen = SVGPathPen(glyphs)
        # top of the sign level with the tops of the capitals
        glyphs[name].draw(TransformPen(pen, (st, 0, 0, -st, x + gap - st * x0, st * y1 - cap_height)))
        colour = text_colours[0][1]
        paint = f'class="{colour[1:]}"' if colour.startswith(".") else f'fill="{colour}"'
        out.append(f'<path {paint} d="{pen.getCommands()}"/>')
        x += gap + st * (x1 - x0)
    return "".join(out), x


# The pages that carry the mark. The logo goes between <!--brand:logo-->
# markers (as often as they appear); the favicon replaces the page's
# <link rel="icon" href="data:..."> in place.
PAGES = ("index.html", "deploy/setup-ui.html", "relay/src/index.js")
ROOT = os.path.dirname(os.path.dirname(HERE))


def favicon_link():
    import urllib.parse
    small = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
             f'<rect width="100" height="100" rx="22" fill="{SKY}"/>{mark(small=True)}</svg>')
    uri = urllib.parse.quote(small, safe=" =:/'<>.,-").replace('"', "'")
    return f'<link rel="icon" href="data:image/svg+xml,{uri}">'


def sync_pages(inline_logo):
    import re
    for rel in PAGES:
        path = os.path.join(ROOT, rel)
        text = open(path).read()
        new = re.sub(r'<link rel="icon" href="data:image/svg\+xml,[^"]*">', lambda m: favicon_link(), text)
        if inline_logo:
            new = re.sub(r"<!--brand:logo-->.*?<!--/brand:logo-->",
                         lambda m: f"<!--brand:logo-->{inline_logo}<!--/brand:logo-->", new, flags=re.S)
        if new != text:
            open(path, "w").write(new)
            print("updated", rel)


def write(name, text):
    with open(os.path.join(HERE, name), "w") as f:
        f.write(text)
    print("wrote", name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", help="ChakraPetch-SemiBold.ttf, to (re)build the wordmark files")
    a = ap.parse_args()

    write("symbol.svg", svg(mark()))
    write("symbol-small.svg", svg(mark(small=True)))
    write("symbol-mono.svg", svg(mark(mono="currentColor")))
    write("symbol-mono-small.svg", svg(mark(small=True, mono="currentColor")))
    write("icon.svg", icon(mark(), SKY))
    write("icon-small.svg", svg(f'<rect width="100" height="100" fill="{SKY}"/>' + mark(small=True)))
    write("icon-dark.svg", icon(mark(), None))            # iOS draws its own dark background
    write("icon-tinted.svg", icon(mark(tint=True), None))  # grey levels; iOS applies the tint

    inline = None
    if a.font:
        # For pages: the words take the page's colours (.ss-strato, .ss-scan)
        words, width = wordmark_paths(a.font, [("Strato", ".ss-strato"), ("Scan", ".ss-scan")], cap_height=42)
        w = round(116 + width + 4)
        inline = (f'<svg class="ss-logo" viewBox="0 0 {w} 100" role="img" aria-label="StratoScan">'
                  f'<rect width="100" height="100" rx="22" fill="{SKY}"/>'
                  f'<g transform="translate(10 10) scale(0.8)">{mark()}</g>'
                  f'<g transform="translate(116 71)">{words}</g></svg>')
        for name, strato, scan in (("logo-on-dark.svg", "#ffffff", SWEEP),
                                   ("logo-on-light.svg", INK, SCAN_ON_LIGHT)):
            words, width = wordmark_paths(a.font, [("Strato", strato), ("Scan", scan)], cap_height=42)
            # the mark on its sky tile, so the white blip and pale sweep read
            # on a light page as well as a dark one
            tile = f'<rect width="100" height="100" rx="22" fill="{SKY}"/><g transform="translate(10 10) scale(0.8)">{mark()}</g>'
            body = tile + f'<g transform="translate(116 71)">{words}</g>'
            write(name, svg(body, w=round(116 + width + 4), h=100, title="StratoScan"))
        # The words alone, for the apps: they draw the mark natively
        # (ios/Shared/BrandMark.swift) and set this beside it
        words, width = wordmark_paths(a.font, [("Strato", "#ffffff"), ("Scan", SWEEP)], cap_height=42)
        # cropped to the capitals (42 tall, no descenders), 2 units spare
        write("wordmark-on-dark.svg", svg(f'<g transform="translate(1 44)">{words}</g>',
                                          w=round(width + 2), h=46, title="StratoScan"))
        # and dark letters, for the app's Daylight theme (iOS picks by appearance)
        words, width = wordmark_paths(a.font, [("Strato", INK), ("Scan", SCAN_ON_LIGHT)], cap_height=42)
        write("wordmark-on-light.svg", svg(f'<g transform="translate(1 44)">{words}</g>',
                                           w=round(width + 2), h=46, title="StratoScan"))
        # The apps' copies are these files exactly; keep them so.
        for src, dst in (("wordmark-on-dark.svg", "ios/StratoScan/App/Assets.xcassets/Wordmark.imageset/Wordmark.svg"),
                         ("wordmark-on-light.svg", "ios/StratoScan/App/Assets.xcassets/WordmarkLight.imageset/WordmarkLight.svg"),
                         ("wordmark-on-dark.svg", "ios/StratoScanWatch/Assets.xcassets/Wordmark.imageset/Wordmark.svg")):
            with open(os.path.join(HERE, src)) as f, open(os.path.join(ROOT, dst), "w") as g:
                g.write(f.read())
    sync_pages(inline)


if __name__ == "__main__":
    main()
