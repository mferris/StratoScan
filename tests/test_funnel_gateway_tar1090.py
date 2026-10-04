#!/usr/bin/env python3
"""
The public tunnel must serve only the readsb/tar1090 data files that the
gateway rewrites or that hold counters, never the ones that locate the
antenna. Found 2026-10-04 on the live tunnel: aircraft.binCraft.zst, the
binary feed tar1090 prefers, carried the receiver's position unrounded in
its header while the rounded receiver.json beside it said 35.83, -78.79.
history and chunk files carry past aircraft.json snapshots with r_dst and
r_dir intact, and outline.json is the range outline drawn around the antenna.

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
]

# The rewritten and counters-only files, in every spelling lighttpd would
# route to the same file.
MUST_ALLOW = [
    "/tar1090/data/aircraft.json", "/tar1090/data/receiver.json", "/tar1090/data/stats.json",
    "/tar1090/data/status.json", "/tar1090/data/aircraft.json?_=1", "/tar1090/data/receiver.json/",
    "//tar1090/data/aircraft.json", "/./tar1090/data/stats.json",
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
    n = len(MUST_BLOCK) + len(MUST_ALLOW) + 4 + 2
    print(f"{n - len(failures)}/{n} tar1090 public-file checks passed")
    for f in failures:
        print("  FAILED:", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
