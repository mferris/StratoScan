#!/usr/bin/env python3
"""
Local-only (127.0.0.1) endpoint that powers the kiosk display back on.

The screensaver (deploy/stratoscan-screensaver.service) uses swayidle +
wlopm to genuinely power the panel off when idle -- the only real "off"
available, since this Pi exposes no backlight control. Touch wakes it,
because touch is ordinary compositor input. An *alert*, though, happens
inside the browser, which has no way to reach the compositor. This is that
way: index.html POSTs /wake when an alert fires and "Alerts wake the
screen" is on (see wakeScreenForAlert), and lighttpd proxies it here
(95-stratoscan-wake.conf).

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
import glob
import http.server
import json
import os
import re
import subprocess
import threading
import time
import urllib.parse

LISTEN = ("127.0.0.1", 8084)
SCREENSAVER_UNIT = "stratoscan-screensaver.service"
KIOSK_UNIT = "stratoscan-kiosk.service"
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

# A browser restart cannot fix a fault below the browser (a hung compositor, a
# wedged GPU driver) -- this used to restart the kiosk every 15 minutes
# forever. The count of restarts that brought no frame back is left where the
# root watchdog (net-watchdog.py, which can reboot) reads it; a painted frame
# clears it. In the runtime dir, so a reboot starts the count over.
STUCK_FILE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
                          "stratoscan-kiosk-stuck")
_unrecovered_restarts = 0


def _record_stuck(n):
    try:
        if n:
            with open(STUCK_FILE, "w") as f:
                f.write(str(n))
        elif os.path.exists(STUCK_FILE):
            os.unlink(STUCK_FILE)
    except OSError:
        pass


def _display_is_on():
    """True only if we can positively confirm the panel is powered on.

    Anything unclear -- wlopm missing, no Wayland socket, unparseable output
    -- counts as "not on", so an uncertain watchdog stays its hand rather
    than restarting the kiosk on a bad reading.
    """
    _ensure_wayland()
    try:
        out = subprocess.run(["wlopm"], capture_output=True, text=True,
                             timeout=5).stdout
    except Exception:
        return False
    return any(line.strip().endswith(" on") for line in out.splitlines())


def _watchdog():
    global _last_restart, _unrecovered_restarts
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
            # A restart that did not bring a frame back is one we already
            # did, still unrecovered -- only reachable if there was a restart
            # before and no beat since.
            _unrecovered_restarts += 1
            _record_stuck(_unrecovered_restarts)
            silent_for = int(now - reference)
            print(f"watchdog: display on but no frame painted for {silent_for}s"
                  f" -- restarting {KIOSK_UNIT}"
                  f" (attempt {_unrecovered_restarts} without recovery)", flush=True)
            subprocess.run(["systemctl", "--user", "restart", KIOSK_UNIT],
                           timeout=60, check=False)
        except Exception as e:
            # A watchdog that dies is worse than one that misses a cycle.
            print(f"watchdog: cycle failed ({type(e).__name__})", flush=True)


def _ensure_wayland():
    """Point wlopm at the compositor even when the session had not published
    WAYLAND_DISPLAY when this service started. After a fresh boot the listener
    can start first, and then every wlopm call failed ("WAYLAND_DISPLAY is not
    set"): alerts could not light the panel, and the SCREEN button could not
    turn it on (seen on RDU 2026-10-11, after a day of restarts)."""
    if os.environ.get("WAYLAND_DISPLAY"):
        return
    rd = os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()
    socks = sorted(p for p in glob.glob(os.path.join(rd, "wayland-[0-9]*")) if not p.endswith(".lock"))
    if socks:
        os.environ["WAYLAND_DISPLAY"] = os.path.basename(socks[0])


def _panel_state():
    """'on', 'off', or '?': what wlopm says the output is doing."""
    _ensure_wayland()
    try:
        out = subprocess.run(["wlopm"], capture_output=True, text=True, timeout=5).stdout
        return out.split()[1] if len(out.split()) >= 2 else "?"
    except Exception:
        return "?"


# Wakes the page asks for on an alert. The screensaver keeps a panel lit by
# one of these for ALERT_HOLD_S (stratoscan-screensaver.service) unless
# someone touches it; any other wake (an update about to check its paint)
# gets the full idle time.
ALERT_WAKES = ("nearby", "rare", "emergency")
ALERT_FLAG = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "stratoscan-alert-wake")
# Written when the page reports its splash painted; boot-cover.py watches it.
PAGE_PAINTED_FLAG = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "stratoscan-page-painted")


# The alert hold (2026-10-11). An alert lights a dark panel for ALERT_HOLD_S
# and this listener puts it out again itself, unless someone touches the
# screen first (the page reports touches on /wake/touch). The screensaver's
# own flag-based 120 s timeout was meant to do this, and did in every test,
# but on real alerts overnight the panel always stayed lit the full 20
# minutes; so the hold no longer depends on it. Its 20-minute idle and its
# touch-to-wake are unchanged.
ALERT_HOLD_S = 120
HOLD_CHECK_S = 5
_hold_until = 0.0          # monotonic; 0 = no alert hold in force


def _hold_tick(now=None):
    """Put the panel out if an alert hold has run its course. True if it did."""
    global _hold_until
    _ensure_wayland()
    now = time.monotonic() if now is None else now
    if not _hold_until or now < _hold_until:
        return False
    _hold_until = 0.0
    if _panel_state() != "on":
        return False
    subprocess.run(["wlopm", "--off", "*"], timeout=5, check=False)
    subprocess.run(["logger", "-t", "stratoscan-screen", "off-after-alert"], timeout=5, check=False)
    return True


def _hold_loop():
    while True:
        time.sleep(HOLD_CHECK_S)
        try:
            _hold_tick()
        except Exception:
            pass               # a failed check must never take the listener down


# The screen's mode (2026-10-11), set by the radar page from the owner's
# settings and re-sent every few minutes, so a restart of either side
# settles within one. The page works out quiet hours; this only acts:
#   sleep   the screensaver runs: dark after 20 minutes untouched, alerts
#           light it for ALERT_HOLD_S (the default, as before)
#   on      always on: the screensaver is stopped and the panel kept lit
#   alerts  quiet hours, alerts light it: dark from the moment quiet hours
#           begin, then as `sleep`
#   dark    quiet hours, dark and silent: dark from the start of quiet
#           hours; the page sends no alert wakes; a touch still wakes it and
#           the 20-minute idle puts it out again
SCREEN_MODES = ("sleep", "on", "alerts", "dark")
_mode = "sleep"


def set_mode(mode):
    """Apply a screen mode. Returns what changed, for the journal."""
    global _mode, _hold_until
    if mode not in SCREEN_MODES:
        raise ValueError(mode)
    before, _mode = _mode, mode
    if mode == "on":
        _hold_until = 0.0
        subprocess.run(["systemctl", "--user", "stop", SCREENSAVER_UNIT], timeout=10, check=False)
        if _panel_state() != "on":
            subprocess.run(["logger", "-t", "stratoscan-screen", "on-always"], timeout=5, check=False)
        subprocess.run(["wlopm", "--on", "*"], timeout=5, check=False)
        return f"{before} -> on" if before != mode else ""
    # every other mode runs the screensaver
    if _unit_state(SCREENSAVER_UNIT) != "active":
        subprocess.run(["systemctl", "--user", "start", SCREENSAVER_UNIT], timeout=10, check=False)
    if mode in ("alerts", "dark") and before != mode:
        _hold_until = 0.0
        if _panel_state() == "on":
            subprocess.run(["wlopm", "--off", "*"], timeout=5, check=False)
            subprocess.run(["logger", "-t", "stratoscan-screen", "off-quiet"], timeout=5, check=False)
    return f"{before} -> {mode}" if before != mode else ""


def _unit_state(unit):
    try:
        return subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return "unknown"


def _wake(alert=False):
    if alert:
        with open(ALERT_FLAG, "w"):
            pass
    else:
        try:
            os.unlink(ALERT_FLAG)
        except OSError:
            pass
    if _panel_state() != "on":
        subprocess.run(["logger", "-t", "stratoscan-screen", "on-alert" if alert else "on-wake"],
                       timeout=5, check=False)
    subprocess.run(["wlopm", "--on", "*"], timeout=5, check=False)
    global _hold_until
    if _mode == "on":
        _hold_until = 0.0        # always on: nothing to hold, and no screensaver to restart
        return
    _hold_until = time.monotonic() + ALERT_HOLD_S if alert else 0.0
    subprocess.run(
        ["systemctl", "--user", "restart", SCREENSAVER_UNIT], timeout=10, check=False
    )


def screen_button():
    """The control arc's SCREEN button (deploy/controls.py): the panel off if it
    is on, on if it is off. Returns the panel's new state."""
    global _hold_until
    _hold_until = 0.0
    try:
        os.unlink(ALERT_FLAG)
    except OSError:
        pass
    if _panel_state() == "on":
        subprocess.run(["wlopm", "--off", "*"], timeout=5, check=False)
        subprocess.run(["logger", "-t", "stratoscan-screen", "off-button"], timeout=5, check=False)
        return "off"
    subprocess.run(["logger", "-t", "stratoscan-screen", "on-button"], timeout=5, check=False)
    subprocess.run(["wlopm", "--on", "*"], timeout=5, check=False)
    if _mode != "on":
        # a fresh idle time from now, as a touch would give
        subprocess.run(["systemctl", "--user", "restart", SCREENSAVER_UNIT], timeout=10, check=False)
    return "on"


# The shm guard asks for a page reload by creating this file. A reload frees
# roughly half the shared memory Chromium accumulates per document (measured:
# 151MB -> 72MB) without restarting the browser, so it is the cheap first move
# before a restart -- no black screen, no risk of coming back windowed.
#
# It is a FILE rather than an HTTP call so nothing new listens on the network:
# only a local process running as this user can request a reload, and the flag
# is delivered on the heartbeat the page already sends every 20 seconds.
# The updater watches this file to decide whether a new build actually
# renders. It is touched on every heartbeat, so its mtime is "the display
# painted a frame at least this recently" -- the same signal the frozen-display
# watchdog uses, reused so an update that blanks the screen is caught by the
# thing already watching the screen.
# In the USER's runtime directory, not /run/stratoscan. That one is setupd's
# RuntimeDirectory= (root:scsetup, 0750) and systemd recreates it with those
# owners every time setupd restarts -- so a stamp written there stopped being
# writable the moment the root helper was restarted, and this service, which
# runs as the desktop user, silently could not write it again.
#
# The cost of that was not a missing file. ota.py reads this to decide whether
# a new build renders, so a stamp that cannot be written makes every update
# look like it failed to paint, and roll back a build that was fine.
PAINT_STAMP = os.environ.get(
    "STRATOSCAN_PAINT_STAMP",
    os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
                 "stratoscan-painted"))


def _mark_painted():
    try:
        os.makedirs(os.path.dirname(PAINT_STAMP), exist_ok=True)
        with open(PAINT_STAMP, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass   # a missing stamp costs a rollback, never a crash


RELOAD_REQUEST = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "stratoscan-reload-request")


def _take_reload_request():
    """True at most once per request file: the flag is consumed, not polled.

    Removed before answering rather than after, so a page that reloads and
    never comes back cannot leave a request that reloads its replacement too.
    """
    try:
        os.unlink(RELOAD_REQUEST)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


class Handler(http.server.BaseHTTPRequestHandler):
    # A client that connects and then sends nothing (or reads nothing) held a
    # thread for good; now the socket gives up after this many seconds
    # (security review 2026-10-04, item 7).
    timeout = 30
    def version_string(self):
        return "StratoScan"

    def do_POST(self):
        global _last_wake, _last_beat, _unrecovered_restarts
        _ensure_wayland()
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
            _mark_painted()
            if _unrecovered_restarts:
                _unrecovered_restarts = 0
                _record_stuck(0)
            if _take_reload_request():
                print("reload: instructing the page to reload", flush=True)
                body = b'{"reload":1}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(204)
            self.end_headers()
            return
        if path == "/wake/mode":
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
            mode = q.get("m", [""])[0]
            if mode not in SCREEN_MODES:
                self.send_error(400)
                return
            try:
                changed = set_mode(mode)
                if changed:
                    print(f"screen mode: {changed}", flush=True)
            except Exception:
                pass
            self.send_response(204)
            self.end_headers()
            return
        if path == "/wake/painted":
            # The page's splash is on screen: the boot cover (boot-cover.py),
            # which shows the same picture above everything, can go.
            try:
                with open(PAGE_PAINTED_FLAG, "w") as f:
                    f.write(str(time.time()))
            except OSError:
                pass
            self.send_response(204)
            self.end_headers()
            return
        if path == "/wake/touch":
            # Someone touched the screen: an alert hold gives way to the
            # ordinary idle time.
            global _hold_until
            _hold_until = 0.0
            try:
                os.unlink(ALERT_FLAG)   # the screensaver's own alert rule gives way too
            except OSError:
                pass
            # In "always on" no screensaver runs to wake the panel on a touch,
            # so a panel switched off by the SCREEN button is woken here.
            if _mode == "on" and _panel_state() == "off":
                subprocess.run(["logger", "-t", "stratoscan-screen", "on-touch"], timeout=5, check=False)
                subprocess.run(["wlopm", "--on", "*"], timeout=5, check=False)
            self.send_response(204)
            self.end_headers()
            return
        if path in ("/wake/button", "/wake/state"):
            # The control arc: its button, and what the status lamp dims by.
            panel = screen_button() if path == "/wake/button" else _panel_state()
            body = json.dumps({"panel": panel, "mode": _mode}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path != "/wake":
            self.send_error(404)
            return
        now = time.monotonic()
        # Why it was asked, for the journal: the page names the alert. Only
        # a short word of known characters is kept; anything else is "?".
        why = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "").get("why", ["?"])[0]
        why = why if re.fullmatch(r"[a-z:_-]{1,24}", why) else "?"
        if now - _last_wake >= MIN_INTERVAL_S:
            _last_wake = now
            try:
                state = _panel_state()
                alert = why.startswith(ALERT_WAKES)
                if alert and state == "on":
                    # Already lit: an alert does not buy the panel more time
                    # (the owner's ask, 2026-10-10), or a busy sky keeps it on.
                    # Not logged: it is most alerts, and nothing happens.
                    pass
                else:
                    print(f"wake: {why} (panel was {state}"
                          f"{'; lit for the alert hold' if alert else ''})", flush=True)
                    _wake(alert)
            except Exception:
                pass  # a failed wake must never take the listener down
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass  # systemd journal already timestamps; this would just be noise


if __name__ == "__main__":
    # A fresh process has restarted nothing yet, so any count on disk is a
    # previous instance's. Left in place it could never be cleared -- a
    # painted frame only clears the file when the in-memory count is non-zero
    # -- and net-watchdog would eventually reboot a healthy unit over it.
    _record_stuck(0)
    threading.Thread(target=_watchdog, daemon=True).start()
    threading.Thread(target=_hold_loop, daemon=True).start()
    http.server.ThreadingHTTPServer(LISTEN, Handler).serve_forever()
