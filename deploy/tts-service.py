#!/usr/bin/env python3
"""
Local text-to-speech for spoken alerts, entirely on the unit (no internet).

Runs Piper (github.com/OHF-voice/piper1-gpl, GPL-3.0-or-later) as its own
program, with the LJSpeech voice (public-domain dataset). The page asks for
a short phrase and plays the WAV through its own volume and mute, like any
other alert sound. Installed into its own virtualenv by
install-setup-server.sh; this file is OTA-updatable, Piper itself is not.

  GET /tts?text=...   -> audio/wav   (127.0.0.1 only; refused on the public Funnel)

The voice loads once (~3 s) and a phrase then takes ~1-2 s on a Pi 5.
Repeated phrases come from a small in-memory cache. Only plain text of a
bounded length is accepted: this is a CPU-heavy endpoint and has no business
reading arbitrary input aloud.
"""
import collections
import http.server
import io
import os
import re
import sys
import threading
import urllib.parse
import wave

LISTEN = ("127.0.0.1", 8089)
VOICE = os.environ.get("FLIGHTRADAR_TTS_VOICE",
                       "/opt/flightradar/tts/voices/en_US-ljspeech-medium.onnx")
MAX_TEXT = 240
TEXT_RE = re.compile(r"^[A-Za-z0-9 ,.'’:;!?()&/%°\-]+$")
CACHE_SIZE = 64

_voice = None
_voice_error = None
_lock = threading.Lock()          # one synthesis at a time: it is CPU-bound anyway
_cache = collections.OrderedDict()


def load_voice():
    global _voice, _voice_error
    try:
        from piper import PiperVoice
        _voice = PiperVoice.load(VOICE)
    except Exception as e:          # missing venv or voice: the page falls back to chimes
        _voice_error = f"{type(e).__name__}: {e}"
        print(f"tts: voice unavailable ({_voice_error})", file=sys.stderr, flush=True)


def synthesize(text):
    with _lock:
        if text in _cache:
            _cache.move_to_end(text)
            return _cache[text]
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            _voice.synthesize_wav(text, w)
        data = buf.getvalue()
        _cache[text] = data
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
        return data


def valid_text(text):
    text = (text or "").strip()
    if not text or len(text) > MAX_TEXT or not TEXT_RE.match(text):
        return None
    return text


class Handler(http.server.BaseHTTPRequestHandler):
    timeout = 30

    def version_string(self):
        return "StratoScan"

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path.rstrip("/") != "/tts":
            return self._send(404, b"not found\n", "text/plain")
        if _voice is None:
            return self._send(503, b"voice unavailable\n", "text/plain")
        text = valid_text((urllib.parse.parse_qs(url.query).get("text") or [""])[0])
        if text is None:
            return self._send(400, b"plain text up to 240 characters\n", "text/plain")
        try:
            return self._send(200, synthesize(text), "audio/wav")
        except Exception as e:
            print(f"tts: synthesis failed ({type(e).__name__})", file=sys.stderr, flush=True)
            return self._send(500, b"synthesis failed\n", "text/plain")


if __name__ == "__main__":
    load_voice()
    server = http.server.ThreadingHTTPServer(LISTEN, Handler)
    server.daemon_threads = True
    server.serve_forever()
