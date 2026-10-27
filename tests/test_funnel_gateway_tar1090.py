#!/usr/bin/env python3
"""
The public tunnel must serve only the readsb/tar1090 data files that the
gateway rewrites or that hold nothing measured from the receiver, never the
ones that locate the antenna. Found 2026-10-04 on the live tunnel:
aircraft.binCraft.zst, the binary feed tar1090 prefers, carried the
receiver's position unrounded in its header while the rounded receiver.json
beside it said 35.88, -78.79. history and chunk files carry past
aircraft.json snapshots with r_dst and r_dir intact, and outline.json is the
range outline drawn around the antenna. stats.json joined them on 2026-10-26.

tar1090's own page, publicly (2026-10-26): its parameters that point it at
another server are refused, and it gets a Content-Security-Policy that keeps
its data to the radar and the services its own features use.

Run: python3 tests/test_funnel_gateway_tar1090.py
"""
import importlib.util
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("fg", root / "deploy" / "funnel-gateway.py")
fg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fg)
private = fg.Handler._is_tar1090_private
rewrites = getattr(fg, "PUBLIC_REWRITES", {})
refused = getattr(fg, "refused_query", lambda path: False)
tar1090_csp = getattr(fg, "TAR1090_CSP", "")
is_tar1090 = getattr(fg, "is_tar1090", lambda base: None)

MUST_BLOCK = [
    "/tar1090/data/aircraft.binCraft.zst", "/tar1090/data/aircraft.binCraft",
    "/tar1090/data/AIRCRAFT.BINCRAFT.ZST", "/TAR1090/data/aircraft.binCraft.zst",
    "/tar1090/data/aircraft.binCraft.zst?x=1", "//tar1090/data/aircraft.binCraft.zst",
    "/./tar1090/data/aircraft.binCraft.zst", "/x/../tar1090/data/aircraft.binCraft.zst",
    "/tar1090/data/%61ircraft.binCraft.zst", "/tar1090/%64ata/aircraft.binCraft.zst",
    "/tar1090/data/outline.json", "/tar1090/data/history_0.json", "/tar1090/data/history_119.json",
    "/tar1090/data/globe_6000.binCraft.zst", "/tar1090/data/traces/00/trace_full_abca00.json",
    "/tar1090/data/trace_full_abca00.json", "/tar1090/data/", "/tar1090/data",
    "/tar1090/chunks/chunks.json", "/tar1090/chunks/current_small.gz", "/tar1090/chunks/chunk_1791120289027.gz",
    "/tar1090/globe_history/2026/10/04/traces/00/trace_full_abca00.json",
    # the allowed names with something after them are different files
    "/tar1090/data/aircraft.json.gz", "/tar1090/data/receiver.json.bak", "/tar1090/data/aircraft.json/x",
    # readsb's statistics hold figures measured from the receiver's position,
    # and nothing public reads them (2026-10-26)
    "/tar1090/data/stats.json", "/./tar1090/data/stats.json", "/tar1090/data/STATS.json",
    "/tar1090/data/stats.json?x=1", "/tar1090/data/%73tats.json",
]

# The rewritten files and status.json, in every spelling lighttpd would route
# to the same file.
MUST_ALLOW = [
    "/tar1090/data/aircraft.json", "/tar1090/data/receiver.json",
    "/tar1090/data/status.json", "/tar1090/data/aircraft.json?_=1", "/tar1090/data/receiver.json/",
    "//tar1090/data/aircraft.json", "/./tar1090/data/status.json",
    # the page itself and everything else on the site are not this filter's business
    "/", "/index.html", "/tar1090/", "/tar1090/index.html", "/tar1090/style.css", "/tar1090/script.js",
    "/api/aircraft", "/sightings", "/config.json", "/tar1090x/data/outline.json",
]


def main():
    failures = []
    for p in MUST_BLOCK:
        if not private(p):
            failures.append(f"NOT BLOCKED (location leak): {p!r}")
    for p in MUST_ALLOW:
        if private(p):
            failures.append(f"wrongly blocked: {p!r}")
    # The public receiver.json must tell tar1090 not to ask for the refused
    # files, or every public viewer's page breaks trying.
    flags = fg.PUBLIC_RECEIVER_FLAGS
    for k, want in (("binCraft", False), ("zstd", False), ("outlineJson", False), ("history", 0)):
        if flags.get(k) != want:
            failures.append(f"public receiver.json leaves {k} on")
    # And the two filters agree on what the allowlist means: a file the
    # gateway rewrites must be one it allows, or the rewrite is unreachable.
    for p in (fg.ROUNDED_PATH, fg.STRIPPED_PATH):
        if p not in fg.TAR1090_PUBLIC_FILES:
            failures.append(f"rewritten file not in the allowlist: {p}")
    # Every allowed file is either rewritten or holds nothing measured from
    # the receiver: a file added here has to be one or the other.
    for p in fg.TAR1090_PUBLIC_FILES:
        if p not in rewrites and p != "/tar1090/data/status.json":
            failures.append(f"allowed but neither rewritten nor known harmless: {p}")
    checks = 1

    # tar1090's parameters that point its page at another server's data or
    # tiles are refused publicly, in every spelling tar1090 itself would read
    # (it lowercases names after URLSearchParams has decoded them).
    for q in ("/tar1090/?aiscatcher_server=https://x.example", "/tar1090/index.html?AISCATCHER_SERVER=x",
              "/tar1090/?Aiscatcher_Server=x", "/tar1090/?ais%63atcher_server=x", "/tar1090/?aiscatcher%5Fserver=x",
              "/tar1090/?aiscatcher%255Fserver=x", "/tar1090/?zoom=9&aiscatcher_server=x",
              "/tar1090/?aiscatcher_server", "/tar1090/?aiscatcher_server=", "/tar1090/?droneJson=https://x.example/d.json",
              "/tar1090/?dronejson=x", "/tar1090/?customTiles=https://x.example/{z}/{x}/{y}.png",
              "/tar1090/?CUSTOMTILES=x", "/tar1090?customTiles=x", "/?aiscatcher_server=x",
              "/tar1090/?customTiles=removex", "/tar1090/?customTiles=remove&aiscatcher_server=x"):
        checks += 1
        if not refused(q):
            failures.append(f"NOT REFUSED: {q!r}")
    for q in ("/tar1090/", "/tar1090/?zoom=9&lat=35.88&lon=-78.79", "/tar1090/?icao=a1b2c3",
              "/tar1090/?customTiles=remove", "/", "/?x=aiscatcher_server", "/tar1090/#aiscatcher_server=x",
              "/api/aircraft?network=1"):
        checks += 1
        if refused(q):
            failures.append(f"wrongly refused: {q!r}")

    # A CSP on tar1090's pages: data only from the radar and the services
    # tar1090's own features use; never a host that serves anyone's uploads.
    csp = dict((d.split(" ", 1) + [""])[:2] for d in tar1090_csp.split("; "))
    connect = csp.get("connect-src", "").split()
    for want, ok in ((("default-src", "'none'"), csp.get("default-src") == "'none'"),
                     (("connect-src", "'self'"), "'self'" in connect),
                     (("connect-src", "no wildcard"), not any(h in ("*", "https:", "http:", "data:") or "*" in h for h in connect)),
                     (("connect-src", "no upload hosts"), not any("githubusercontent" in h or "arcgis" in h for h in connect)),
                     (("connect-src", "photos"), "https://api.planespotters.net" in connect),
                     (("frame-ancestors", "'none'"), csp.get("frame-ancestors") == "'none'"),
                     (("object-src", "'none'"), csp.get("object-src") == "'none'"),
                     (("base-uri", "'none'"), csp.get("base-uri") == "'none'"),
                     (("report-uri", "/csp-report"), csp.get("report-uri") == "/csp-report")):
        checks += 1
        if not ok:
            failures.append(f"tar1090 CSP: {want}")
    for p in ("/tar1090", "/tar1090/", "/tar1090/index.html", "/TAR1090/", "/x/../tar1090/"):
        checks += 1
        if not is_tar1090(fg.Handler._normalise(p)):
            failures.append(f"not treated as tar1090's page: {p!r}")
    for p in ("/", "/index.html", "/tar1090x/", "/tar1090.html"):
        checks += 1
        if is_tar1090(fg.Handler._normalise(p)):
            failures.append(f"wrongly treated as tar1090's page: {p!r}")
    n = len(MUST_BLOCK) + len(MUST_ALLOW) + 4 + 2 + checks
    print(f"{n - len(failures)}/{n} tar1090 public-file checks passed")
    for f in failures:
        print("  FAILED:", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
