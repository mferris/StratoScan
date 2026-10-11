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
BACKGROUND = b"window { background-color: #0a0d0f; }"   # the picture's own background
MAX_S = 60
POLL_MS = 100
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
    from gi.repository import GLib, Gtk, GtkLayerShell

    win = Gtk.Window()
    GtkLayerShell.init_for_window(win)
    GtkLayerShell.set_namespace(win, "stratoscan-boot-cover")
    GtkLayerShell.set_layer(win, GtkLayerShell.Layer.OVERLAY)
    for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                 GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
        GtkLayerShell.set_anchor(win, edge, True)
    GtkLayerShell.set_exclusive_zone(win, -1)
    css = Gtk.CssProvider()
    css.load_from_data(BACKGROUND)
    Gtk.StyleContext.add_provider_for_screen(win.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    win.add(Gtk.Image.new_from_file(PICTURE))   # centred, at its own size
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
