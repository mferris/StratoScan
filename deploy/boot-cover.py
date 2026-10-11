#!/usr/bin/env python3
"""The StratoScan picture over everything, from the start of the kiosk's
session until the page has painted its own copy of it (2026-10-11).

Without this, a power-on showed the picture three times with gaps between:
the boot splash, then the desktop background (swaybg), then -- after a
white flash while Chromium's window was still empty, and a black frame
while the page started -- the page's own splash. A recording of a boot on
RDU showed the white for about 0.7 s and the black for about 0.4 s.

This window sits on the compositor's overlay layer, above Chromium, showing
the same picture on the same background. The page posts /wake/painted once
its splash is on screen (deploy/wake-listener.py writes FLAG), and this
window then closes: the picture underneath is identical, so nothing seems
to change. It gives up after MAX_S whatever happens, so a page that never
loads cannot leave the screen covered.

Started from the session's autostart (deploy/labwc-autostart).
"""
import os
import sys
import time

PICTURE = "/usr/share/stratoscan/splash.png"
BACKGROUND = "#0a0d0f"   # the picture's own background
MAX_S = 60
POLL_MS = 100
UNCOVERED_PX = 1
FLAG = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "stratoscan-page-painted")


def should_close(started, now, flag=FLAG, max_s=MAX_S):
    return os.path.exists(flag) or now - started > max_s


def main():
    # A flag left by an earlier session would close the cover at once.
    try:
        os.unlink(FLAG)
    except OSError:
        pass
    if not os.path.exists(PICTURE):
        return 0
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf, GLib, Gtk, GtkLayerShell

    win = Gtk.Window()
    GtkLayerShell.init_for_window(win)
    GtkLayerShell.set_namespace(win, "stratoscan-boot-cover")
    GtkLayerShell.set_layer(win, GtkLayerShell.Layer.OVERLAY)
    for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                 GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
        GtkLayerShell.set_anchor(win, edge, True)
    GtkLayerShell.set_exclusive_zone(win, -1)
    # One column of pixels at the right edge is left uncovered -- on the round
    # panel it is outside the circle. A window that is completely hidden gets
    # no frame callbacks from the compositor, so Chromium stops drawing and
    # the page's requestAnimationFrame never runs: covered whole, the page
    # could not report that it had painted until MAX_S ran out (seen on RDU,
    # 2026-10-11: the cover stayed 60 s). With one column showing, the page
    # draws behind the cover and reports at once.
    GtkLayerShell.set_margin(win, GtkLayerShell.Edge.RIGHT, UNCOVERED_PX)
    # The picture is the window's background, placed where the page and
    # swaybg place it: centred on the whole screen, in whole pixels. As a
    # child widget it would hold the window at its own 1080 px width and
    # undo the uncovered column above.
    _, iw, ih = GdkPixbuf.Pixbuf.get_file_info(PICTURE)
    geo = win.get_display().get_monitor(0).get_geometry()
    x, y = (geo.width - iw) // 2, (geo.height - ih) // 2
    css = Gtk.CssProvider()
    css.load_from_data((
        "window { background-color: %s; background-image: url('file://%s');"
        " background-repeat: no-repeat; background-position: %dpx %dpx; }"
        % (BACKGROUND, PICTURE, x, y)).encode())
    Gtk.StyleContext.add_provider_for_screen(win.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    win.show_all()

    started = time.monotonic()

    def check():
        if should_close(started, time.monotonic()):
            Gtk.main_quit()
            return False
        return True

    GLib.timeout_add(POLL_MS, check)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
