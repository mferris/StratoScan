#!/usr/bin/env python3
"""
Local-only (127.0.0.1) endpoint that powers the kiosk display back on.

The screensaver (deploy/flightradar-screensaver.service) uses swayidle +
wlopm to genuinely power the panel off when idle -- the only real "off"
available, since this Pi exposes no backlight control. Touch wakes it,
because touch is ordinary compositor input. An *alert*, though, happens
inside the browser, which has no way to reach the compositor. This is that
way: index.html POSTs /wake when an alert fires and "Alerts wake the
screen" is on (see wakeScreenForAlert), and lighttpd proxies it here
(95-flightradar-wake.conf).

Runs as a --user service, unlike the other stores here: it needs the
session's WAYLAND_DISPLAY to talk to the compositor at all, which a
DynamicUser system service cannot have.

POST /wake -> powers the output on; 204 on success.

After waking we also restart the screensaver unit. swayidle fires its
`timeout` action once per idle period, so without this the display would
stay on indefinitely after an alert -- there is no further input to trigger
`resume` and re-arm it. Restarting resets the countdown, so the screen
blanks again IDLE_MINUTES after the alert, which is the behaviour you'd
expect.
"""
import http.server
import subprocess
import time

LISTEN = ("127.0.0.1", 8084)
SCREENSAVER_UNIT = "flightradar-screensaver.service"
# One real wake per this many seconds. The endpoint is reachable from the
# public internet via Funnel (though funnel-gateway.py refuses it there),
# and a burst of alerts shouldn't mean a burst of unit restarts.
MIN_INTERVAL_S = 10
_last_wake = 0.0


def _wake():
    subprocess.run(["wlopm", "--on", "*"], timeout=5, check=False)
    subprocess.run(
        ["systemctl", "--user", "restart", SCREENSAVER_UNIT], timeout=10, check=False
    )


class Handler(http.server.BaseHTTPRequestHandler):
    def version_string(self):
        return "FlightRadar"

    def do_POST(self):
        global _last_wake
        if self.path.rstrip("/") != "/wake":
            self.send_error(404)
            return
        now = time.monotonic()
        if now - _last_wake >= MIN_INTERVAL_S:
            _last_wake = now
            try:
                _wake()
            except Exception:
                pass  # a failed wake must never take the listener down
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass  # systemd journal already timestamps; this would just be noise


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(LISTEN, Handler).serve_forever()
