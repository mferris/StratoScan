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

POST /wake       -> powers the output on; 204 on success.
POST /wake/alive -> the radar reporting that it just painted a frame. See
                    the watchdog below for why anything cares.

After waking we also restart the screensaver unit. swayidle fires its
`timeout` action once per idle period, so without this the display would
stay on indefinitely after an alert -- there is no further input to trigger
`resume` and re-arm it. Restarting resets the countdown, so the screen
blanks again IDLE_MINUTES after the alert, which is the behaviour you'd
expect.
"""
import http.server
import subprocess
import threading
import time

LISTEN = ("127.0.0.1", 8084)
SCREENSAVER_UNIT = "flightradar-screensaver.service"
KIOSK_UNIT = "flightradar-kiosk.service"
# One real wake per this many seconds. The endpoint is reachable from the
# public internet via Funnel (though funnel-gateway.py refuses it there),
# and a burst of alerts shouldn't mean a burst of unit restarts.
MIN_INTERVAL_S = 10
_last_wake = 0.0

# ---- Frozen-display watchdog ------------------------------------------
# Chromium's GPU context can die under the kiosk and not come back: the
# renderer keeps running -- timers still fire, fetches still succeed, the
# page is alive by every internal measure -- but nothing is ever painted
# again. The panel keeps showing whatever frame was up when it happened.
# Seen on this device: the GPU command buffer failed to allocate, logged the
# same error 345,000 times over 50 minutes, and the radar sat frozen with
# stale traffic on screen while the receiver underneath was perfectly
# healthy. Only someone walking up to it noticed.
#
# So the browser reports that it is still *painting*, which is the thing that
# actually failed, and cannot be inferred from outside: index.html posts here
# from inside its render loop, after a frame is genuinely drawn.
#
# The display being powered off is NOT a fault. The screensaver blanks the
# panel, and a hidden page legitimately stops receiving animation frames --
# so the heartbeat stops too, and treating that as a freeze would reboot the
# radar every night. wlopm reports the real power state, and the watchdog
# only acts while the panel is on.
FROZEN_AFTER_S = 150      # ~7 missed heartbeats; long enough to rule out a slow frame
WATCHDOG_PERIOD_S = 30
GRACE_AFTER_RESTART_S = 120   # Chromium and the map take a while to first paint
MIN_RESTART_INTERVAL_S = 15 * 60   # a page broken in a way a restart cannot fix must not spin
_last_beat = 0.0          # monotonic; 0 until the first frame is reported
_last_restart = 0.0
_started_at = time.monotonic()


def _display_is_on():
    """True only if we can positively confirm the panel is powered on.

    Anything unclear -- wlopm missing, no Wayland socket, unparseable output
    -- counts as "not on", so an uncertain watchdog stays its hand rather
    than restarting the kiosk on a bad reading.
    """
    try:
        out = subprocess.run(["wlopm"], capture_output=True, text=True,
                             timeout=5).stdout
    except Exception:
        return False
    return any(line.strip().endswith(" on") for line in out.splitlines())


def _watchdog():
    global _last_restart
    while True:
        time.sleep(WATCHDOG_PERIOD_S)
        try:
            now = time.monotonic()
            # Nothing has been heard since this service itself started: that
            # is a cold boot, not a freeze. The grace window covers Chromium
            # starting up; after it, silence is a real fault and is treated
            # as one -- a kiosk that never painted at all is just as broken
            # as one that stopped.
            reference = _last_beat or _started_at
            if now - reference < FROZEN_AFTER_S:
                continue
            if not _last_beat and now - _started_at < GRACE_AFTER_RESTART_S:
                continue
            if now - _last_restart < MIN_RESTART_INTERVAL_S:
                continue
            if not _display_is_on():
                continue   # blanked by the screensaver; no frames expected
            _last_restart = now
            silent_for = int(now - reference)
            print(f"watchdog: display on but no frame painted for {silent_for}s"
                  f" -- restarting {KIOSK_UNIT}", flush=True)
            subprocess.run(["systemctl", "--user", "restart", KIOSK_UNIT],
                           timeout=60, check=False)
        except Exception as e:
            # A watchdog that dies is worse than one that misses a cycle.
            print(f"watchdog: cycle failed ({type(e).__name__})", flush=True)


def _wake():
    subprocess.run(["wlopm", "--on", "*"], timeout=5, check=False)
    subprocess.run(
        ["systemctl", "--user", "restart", SCREENSAVER_UNIT], timeout=10, check=False
    )


class Handler(http.server.BaseHTTPRequestHandler):
    def version_string(self):
        return "FlightRadar"

    def do_POST(self):
        global _last_wake, _last_beat
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/wake/alive":
            if not _last_beat:
                # Logged once per start: proof in the journal that the kiosk
                # really is reporting frames, which is the difference between
                # a watchdog that catches a freeze and one that restarts a
                # perfectly healthy radar every fifteen minutes forever.
                print("watchdog: first painted frame reported "
                      f"{time.monotonic() - _started_at:.0f}s after start",
                      flush=True)
            _last_beat = time.monotonic()
            self.send_response(204)
            self.end_headers()
            return
        if path != "/wake":
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
    threading.Thread(target=_watchdog, daemon=True).start()
    http.server.ThreadingHTTPServer(LISTEN, Handler).serve_forever()
