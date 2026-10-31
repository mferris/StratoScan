#!/usr/bin/env python3
"""No shell script POSTs with curl without a body (2026-10-30, #81).

lighttpd answers a POST that carries no Content-Length with 411 Length
Required and never passes it on. A bare `curl -X POST URL` sends no
Content-Length, and curl still exits 0 on the 411, so the request silently
does nothing. That is how ota-auto.sh's wake never reached the wake listener:
the panel stayed dark and no unattended update could install.

So every curl in a shell script (or a systemd unit's shell line) that POSTs
must also send a body (the same goes for PUT, which lighttpd treats alike) (-d/--data*, --json, -F/--form, -T) or set the
Content-Length header itself. -d '' is enough: it sends Content-Length: 0.

Run: python3 tests/test_curl_posts.py
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

POST = re.compile(r"(?:^|\s)(?:-X\s*|--request[\s=]+)['\"]?(?:POST|PUT)\b")
BODY = re.compile(r"(?:^|\s)(?:-d|--data(?:-raw|-binary|-urlencode|-ascii)?|--json|-F|--form|-T|--upload-file)(?=[\s='\"]|$)"
                  r"|(?:^|\s)-d\S"
                  r"|Content-Length:")


def tracked_files():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                         capture_output=True, text=True, check=True).stdout
    for name in out.splitlines():
        if name.startswith("vendor/") or "/vendor/" in name:
            continue
        if name.endswith((".sh", ".service")):
            path = ROOT / name
            if path.is_file():
                yield path


def curl_commands(text):
    """Each curl command in a script, with line continuations joined, cut at
    the end of its command (; | && || or the end of the line)."""
    joined = re.sub(r"\\\n", " ", text)
    for lineno, line in enumerate(joined.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for m in re.finditer(r"(?<![\w./-])curl(?=\s)", line):
            rest = line[m.start():]
            cmd = re.split(r";|\|\||&&|\|(?!\|)", rest, maxsplit=1)[0]
            yield lineno, cmd.strip()


def offenders(files):
    bad = []
    for path in files:
        for lineno, cmd in curl_commands(path.read_text(errors="replace")):
            if POST.search(cmd) and not BODY.search(cmd):
                bad.append(f"{path.relative_to(ROOT)}: {cmd}")
    return bad


def main():
    failures = []
    checks = 0

    # The detector itself, so a clean run means something.
    samples = {
        "curl -s -m 10 -X POST \"$WAKE_URL\" >/dev/null": True,
        "curl -s -X POST http://127.0.0.1/wake; touch x": True,
        "curl -s --request POST http://x": True,
        "curl -s -X PUT http://x": True,
        "curl -s -X PUT -d '' http://x": False,
        "curl -s -m 10 -d '' \"$WAKE_URL\"": False,
        "curl -s -X POST -d '' http://x": False,
        "curl -s -X POST --data '{}' http://x": False,
        "curl -s -X POST -H 'Content-Length: 0' http://x": False,
        "curl -s http://x": False,
    }
    for cmd, should_flag in samples.items():
        checks += 1
        flagged = any(POST.search(c) and not BODY.search(c)
                      for _, c in curl_commands(cmd + "\n"))
        if flagged != should_flag:
            failures.append(f"detector got {cmd!r} wrong (flagged={flagged})")

    files = list(tracked_files())
    checks += 1
    if not any(p.name == "ota-auto.sh" for p in files):
        failures.append("did not find deploy/ota-auto.sh; is the scan looking in the right place?")

    checks += 1
    bad = offenders(files)
    if bad:
        failures.append("curl POSTs with no body (lighttpd answers 411; add -d ''):"
                        + "".join("\n       " + b for b in bad))

    for f in failures:
        print("FAIL:", f)
    print(f"{checks - len(failures)}/{checks} curl POST checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
