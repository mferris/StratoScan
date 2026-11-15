#!/usr/bin/env python3
"""The public gateway reads no body it has no use for (SR-23, 2026-11-15).

A GET or HEAD that says a body follows is refused before anything is read
and never reaches lighttpd; nothing the gateway passes on carries a body; a
violation report is the one body taken, and only a small one. The day's
visitor hashes stop at MAX_SEEN.

There is no limit on how many requests are in hand, and no memory or task
ceiling on the service: both were tried and taken out the same day, because
a few slow connections then denied the public address to everyone. The last
part of this file keeps them out.

Runs the real gateway in front of a stand-in for lighttpd.

Run: python3 tests/test_funnel_gateway_bodies.py
"""
import http.server
import importlib.util
import pathlib
import re
import socket
import sys
import tempfile
import threading
import time

root = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("fg", root / "deploy" / "funnel-gateway.py")
fg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fg)
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


received = []          # (method, path, Content-Length, Transfer-Encoding) of what reached the stand-in


class Upstream(http.server.BaseHTTPRequestHandler):
    def _any(self):
        received.append((self.command, self.path, self.headers.get("Content-Length"),
                         self.headers.get("Transfer-Encoding")))
        body = b"<html><script>go();</script></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    do_GET = do_HEAD = do_POST = _any

    def log_message(self, *a):
        pass


up = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
threading.Thread(target=up.serve_forever, daemon=True).start()
fg.UPSTREAM = "http://127.0.0.1:%d" % up.server_address[1]
gw = fg.QuietServer(("127.0.0.1", 0), fg.Handler)
threading.Thread(target=gw.serve_forever, daemon=True).start()
PORT = gw.server_address[1]


def raw(request, wait=5.0):
    """Send these bytes and nothing more; the status answered (None for a
    connection closed without one) and how long the answer took.

    Reads one whole answer (its headers, then as many bytes as its
    Content-Length says; for a HEAD, the headers) and stops there, instead of reading until the
    gateway closes. The gateway refuses a request without reading the body
    it came with, and closing a socket with bytes unread makes the kernel
    send a reset in place of a tidy close; whether that reset overtook the
    end of the answer was a matter of timing, and one run in four died on a
    ConnectionResetError. Now the answer is complete before the close is
    looked for, and a reset after it means what a close does."""
    s = socket.create_connection(("127.0.0.1", PORT), timeout=wait)
    t0 = time.monotonic()
    data = b""
    try:
        s.sendall(request)
        while not whole(data, request.startswith(b"HEAD ")):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    except (socket.timeout, ConnectionError):
        pass
    took = time.monotonic() - t0
    s.close()
    m = re.match(rb"HTTP/1\.[01] (\d{3})", data)
    return (int(m.group(1)) if m else None), took


def whole(data, head_only):
    """Whether these bytes are one complete answer (to a HEAD: its headers)."""
    head, sep, rest = data.partition(b"\r\n\r\n")
    if not sep:
        return False
    m = re.search(rb"^Content-Length: *(\d+)\r?$", head, re.M | re.I)
    return head_only or m is None or len(rest) >= int(m.group(1))


def req(method, path, *headers, body=b""):
    return ("%s %s HTTP/1.1\r\nHost: radar.example\r\n" % (method, path)).encode() \
        + b"".join(h.encode() + b"\r\n" for h in headers) + b"\r\n" + body


# ---- a GET or HEAD with a body ------------------------------------------------
check(raw(req("GET", "/"))[0] == 200 and raw(req("HEAD", "/index.html"))[0] == 200,
      "a GET and a HEAD without a body are answered")
check(raw(req("GET", "/", "Content-Length: 0"))[0] == 200, "and with Content-Length: 0, which says there is none")
n = len(received)
for method in ("GET", "HEAD"):
    for path in ("/", "/network", "/tar1090/data/receiver.json", "/api/aircraft"):
        status, _ = raw(req(method, path, "Content-Length: 5", body=b"hello"))
        check(status == 400, "%s %s with a 5-byte body: 400" % (method, path))
# The body is claimed and never sent. A gateway that tried to read it would
# sit until its 30 s socket timeout; the answer must come at once.
status, took = raw(req("GET", "/", "Content-Length: 2000000000"), wait=8)
check(status == 400 and took < 3, "a GET claiming 2 GB and sending none is refused at once, not waited for (%.1f s)" % took)
for h in ("Transfer-Encoding: chunked", "Transfer-Encoding: gzip", "Content-Length: -1", "Content-Length: abc",
          "Content-Length: 0x10", "Content-Length:", "Content-Length: 0\r\nContent-Length: 7"):
    status, took = raw(req("GET", "/", *h.split("\r\n")), wait=8)
    check(status == 400 and took < 3, "refused at once: GET with %s" % h.replace("\r\n", " and "))
check(len(received) == n, "none of them reached lighttpd")
check(all(cl is None and te is None for _, _, cl, te in received),
      "and nothing the gateway passed on had a body or a length")
src = (root / "deploy" / "funnel-gateway.py").read_text()
check("data=" not in src.split("def _proxy", 1)[1].split("def _relay", 1)[0] and src.count("self.rfile.read(") == 1,
      "the gateway reads from a client in one place only, the violation report, and passes no body on")

# ---- the one body it takes ------------------------------------------------------
report = b'{"csp-report":{"effective-directive":"img-src","blocked-uri":"https://x.example/p"}}'
fg._csp_reports.clear()
check(raw(req("POST", "/csp-report", "Content-Length: %d" % len(report), body=report))[0] == 204
      and fg.csp_summary()["reports"] == {"img-src x.example": 1}, "a violation report is counted")
status, took = raw(req("POST", "/csp-report", "Content-Length: %d" % (fg.CSP_REPORT_MAX_BYTES + 1)), wait=8)
check(status == 204 and took < 3 and sum(fg.csp_summary()["reports"].values()) == 1,
      "one over %d bytes is answered and not read" % fg.CSP_REPORT_MAX_BYTES)
for h in ("Content-Length: abc", "Content-Length: -5"):
    status, took = raw(req("POST", "/csp-report", h), wait=8)
    check(status == 204 and took < 3, "a report with %s is answered and not read" % h)
status, took = raw(req("POST", "/", "Content-Length: 2000000000"), wait=8)
check(status == 405 and took < 3, "a write anywhere else is refused without reading its body")
check(fg.Handler.timeout == 30 and fg._StatsHandler.timeout == 30, "a silent client is still given up on after 30 s")

# ---- no limit on how many at once (tried and taken out, 2026-11-15) -----------------
# With 48 places, 48 connections that said nothing held the public address
# shut for everyone until each timed out. Sixty silent ones are held open
# here, and the next caller must still be answered.
idle = [socket.create_connection(("127.0.0.1", PORT), timeout=5) for _ in range(60)]
time.sleep(0.3)
check(all(raw(req("GET", "/"))[0] == 200 for _ in range(5)),
      "with 60 silent connections held open, the next callers are still answered")
for s in idle:
    s.close()
check(not hasattr(fg, "MAX_AT_ONCE") and "Semaphore" not in src and "process_request" not in src,
      "the gateway has no limit on requests in hand")

# ---- the day's visitor hashes ----------------------------------------------------
fg.MAX_SEEN = 50
v = fg.Visits(directory=tempfile.mkdtemp(), now=lambda: 1790000000.0)
UA = "Mozilla/5.0 (Macintosh) Safari/605"
for i in range(400):
    v.record("GET", "/", {"User-Agent": UA, "X-Forwarded-For": "198.51.100.%d, 203.0.113.%d" % (i % 250, i)})
    v.record("GET", "/api/aircraft", {"User-Agent": UA, fg.APP_HEADER: "1", "X-Forwarded-For": "203.0.113.%d" % i})
day = next(iter(v.days.values()))
check(len(v._seen) == 50 and len(v._app_seen) == 50, "no more than MAX_SEEN hashes are kept, whatever a caller sends")
check(day["views"] == 400 and day["unique"] == 50 and day["app_devices"] == 50,
      "every view is still counted; visitors past the limit are not counted as new")

# ---- and no ceiling on the service ---------------------------------------------------
# A task ceiling is the same limit by another name (past it a new connection
# gets no thread), and past a memory ceiling the service is killed mid-answer.
unit = (root / "deploy" / "stratoscan-funnel-gateway.service").read_text()
check(not re.search(r"^\s*(MemoryMax|MemoryHigh|TasksMax|LimitNPROC)\s*=", unit, re.M),
      "the unit file sets no memory or task ceiling")
check("Restart=always" in unit, "and still starts the gateway again if it stops")

print("gateway body checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
