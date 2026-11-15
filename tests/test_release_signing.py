#!/usr/bin/env python3
"""scripts/release.sh and the signing key (security review 2026-11-03).

Two things are checked, both against a copy of the script in a throwaway
tree with a throwaway key, a throwaway ssh-agent and a stand-in for `gh`.
Nothing here touches the maintainer's key, agent or GitHub.

1. The key is used through ssh-agent for the length of a run. The script
   loads it once, with a lifetime, asks for the passphrase once however many
   things it signs, and takes out exactly the key it put in on every way out:
   success, a refusal, a failed self-check, a signal. A key that was loaded
   before the run is used and left where it was.

2. `rollout` builds the next signed policy from files it downloads, and a
   release's files can be replaced after it is published. So it verifies the
   manifest and the existing policy against deploy/allowed_signers first and
   refuses before it loads the key.

The test key has a passphrase, given by an SSH_ASKPASS stand-in that counts
how often it is asked: that count is the number of prompts the maintainer
would have seen.

Run: python3 tests/test_release_signing.py
"""
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "release.sh")
PASSPHRASE = "test passphrase, used nowhere else"

checks = 0
failures = []


def check(ok, what):
    global checks
    checks += 1
    if not ok:
        failures.append(what)


def script(path, body):
    with open(path, "w") as f:
        f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class World:
    """A repository, a key, an agent and a fake GitHub, all under one directory."""

    def __init__(self):
        # Short, because a unix socket's path may be about 100 characters.
        self.tmp = tempfile.mkdtemp(prefix="rs-")
        t = self.tmp
        self.home = os.path.join(t, "home")
        self.bin = os.path.join(t, "bin")
        self.assets = os.path.join(t, "assets")       # what "GitHub" holds for the release
        self.uploads = os.path.join(t, "uploads")
        self.asked = os.path.join(t, "asked")          # one line per passphrase prompt
        self.addlog = os.path.join(t, "ssh-add.log")   # one line per ssh-add the script ran
        for d in (self.home, self.bin, self.assets, self.uploads):
            os.makedirs(d)

        self.key = os.path.join(t, "release-key")
        self.other = os.path.join(t, "other-key")
        self.stranger = os.path.join(t, "stranger-key")
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", PASSPHRASE, "-f", self.key], check=True)
        for k in (self.other, self.stranger):
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", k], check=True)
        # The script finds the public half inside the key file; a missing
        # .pub must not matter.
        self.pub = open(self.key + ".pub").read()
        os.unlink(self.key + ".pub")

        script(os.path.join(t, "askpass"),
               f"#!/bin/sh\necho asked >> '{self.asked}'\necho '{PASSPHRASE}'\n")
        real_ssh_add = shutil.which("ssh-add")
        script(os.path.join(self.bin, "ssh-add"),
               f"#!/bin/sh\necho \"$*\" >> '{self.addlog}'\nexec '{real_ssh_add}' \"$@\"\n")
        # `gh`, as far as release.sh uses it.
        script(os.path.join(self.bin, "gh"), f"""#!/bin/sh
[ "$1" = release ] || exit 1
case "$2" in
  view) [ -f '{t}/latest' ] && cat '{t}/latest'; exit 0 ;;
  download)
    shift 3; dir=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --pattern) pats="$pats $2"; shift 2 ;;
        --dir) dir=$2; shift 2 ;;
        *) shift ;;
      esac
    done
    n=0
    for p in $pats; do [ -f '{self.assets}'/"$p" ] && cp '{self.assets}'/"$p" "$dir/" && n=$((n+1)); done
    [ "$n" -gt 0 ] ;;
  upload)
    : > '{t}/uploading'
    [ -f '{t}/slow-upload' ] && sleep 3
    shift 3
    for f in "$@"; do [ -f "$f" ] && cp "$f" '{self.uploads}/'; done
    exit 0 ;;
  *) exit 1 ;;
esac
""")

        self.sock = os.path.join(t, "agent.sock")
        self.agent = subprocess.Popen(["ssh-agent", "-D", "-a", self.sock],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if os.path.exists(self.sock):
                break
            time.sleep(0.05)

        # The tree release.sh runs in: the script, the trust root, a payload.
        self.repo = os.path.join(t, "repo")
        os.makedirs(os.path.join(self.repo, "scripts"))
        os.makedirs(os.path.join(self.repo, "deploy"))
        shutil.copy(SCRIPT, os.path.join(self.repo, "scripts", "release.sh"))
        self.signers = os.path.join(self.repo, "deploy", "allowed_signers")
        self.trust(self.pub)

    def trust(self, pub):
        with open(self.signers, "w") as f:
            f.write("stratoscan-release " + pub)
            f.write("flightradar-release " + pub)

    def env(self, agent=True):
        e = {k: v for k, v in os.environ.items()
             if not k.startswith(("SSH_", "STRATOSCAN_", "FLIGHTRADAR_", "GIT_"))}
        e.update({
            "HOME": self.home,
            "PATH": self.bin + os.pathsep + e.get("PATH", ""),
            "STRATOSCAN_SIGNING_KEY": self.key,
            "SSH_ASKPASS": os.path.join(self.tmp, "askpass"),
            "SSH_ASKPASS_REQUIRE": "force",
        })
        if agent:
            e["SSH_AUTH_SOCK"] = self.sock
        return e

    def release_sh(self, *args, agent=True):
        for f in (self.asked, self.addlog):
            if os.path.exists(f):
                os.unlink(f)
        return subprocess.run(["sh", os.path.join(self.repo, "scripts", "release.sh"), *args],
                              env=self.env(agent), cwd=self.tmp, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=120)

    def lines(self, path):
        try:
            with open(path) as f:
                return [l.rstrip("\n") for l in f]
        except OSError:
            return []

    def prompts(self):
        return len(self.lines(self.asked))

    def adds(self):
        """The ssh-add calls that load a key (not -l listings or -d removals)."""
        return [l for l in self.lines(self.addlog) if "-t" in l.split() and "-d" not in l.split()]

    def agent_keys(self):
        r = subprocess.run(["ssh-add", "-L"], env=self.env(), capture_output=True, text=True)
        return sorted(" ".join(l.split()[:2]) for l in r.stdout.splitlines() if l.startswith("ssh-"))

    def preload(self, key):
        subprocess.run([shutil.which("ssh-add"), key], env=self.env(), stdin=subprocess.DEVNULL,
                       check=True, capture_output=True)

    def empty_agent(self):
        # This is the test's own agent; the script itself must never do this.
        subprocess.run([shutil.which("ssh-add"), "-D"], env=self.env(), capture_output=True)

    def sign(self, path, namespace, key=None):
        """Signs with a key FILE, as a past run of release.sh did."""
        e = self.env(agent=False)
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", key or self.key, "-n", namespace, path],
                       env=e, stdin=subprocess.DEVNULL, check=True, capture_output=True)

    def verifies(self, path, namespace, sig=None):
        with open(path, "rb") as f:
            return subprocess.run(
                ["ssh-keygen", "-Y", "verify", "-f", self.signers, "-I", "stratoscan-release",
                 "-n", namespace, "-s", sig or path + ".sig"],
                stdin=f, capture_output=True).returncode == 0

    def publish(self, version="2026.01.02.1", serial=40, ring=0, hours_ago=1.0, policy=True):
        """Puts a correctly signed release on the fake GitHub, as the latest."""
        shutil.rmtree(self.assets)
        os.makedirs(self.assets)
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        at = time.strftime(fmt, time.gmtime(time.time() - hours_ago * 3600))
        m = os.path.join(self.assets, "manifest.json")
        with open(m, "w") as f:
            json.dump({"version": version, "serial": serial, "created": at, "files": {}}, f)
        self.sign(m, "stratoscan")
        os.rename(m + ".sig", os.path.join(self.assets, "manifest.stratoscan.sig"))
        self.sign(m, "flightradar")
        if policy:
            p = os.path.join(self.assets, "rollout.json")
            with open(p, "w") as f:
                json.dump({"kind": "rollout", "version": version, "serial": serial, "ring": ring,
                           "paused": False, "released_at": at, "at": at, "note": "cut"}, f)
            self.sign(p, "stratoscan-rollout")
        with open(os.path.join(self.tmp, "latest"), "w") as f:
            f.write(version + "\n")
        return version

    def close(self):
        self.agent.terminate()
        self.agent.wait(timeout=10)
        shutil.rmtree(self.tmp, ignore_errors=True)


def dry_policy(out):
    """The directory a dry-run rollout left its policy in."""
    for line in out.splitlines():
        if "Policy in " in line:
            return line.split("Policy in ", 1)[1].strip()
    return None


def main():
    for tool in ("ssh-keygen", "ssh-add", "ssh-agent", "git"):
        if not shutil.which(tool):
            print(f"SKIPPED: no {tool} on this machine")
            return 0
    w = World()
    try:
        cases(w)
    finally:
        w.close()
    if failures:
        print(f"{len(failures)} of {checks} release signing checks FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"{checks}/{checks} release signing checks passed")
    return 0


def cases(w):
    other_pub = " ".join(open(w.other + ".pub").read().split()[:2])
    release_pub = " ".join(w.pub.split()[:2])

    # --- the key is loaded for the run and removed after it -----------------
    v = w.publish()
    r = w.release_sh("rollout", v, "--ring", "1", "--force", "--dry-run")
    d = dry_policy(r.stdout)
    check(r.returncode == 0 and d is not None, "a rollout with an empty agent runs: " + r.stderr[-300:])
    check(d is not None and w.verifies(os.path.join(d, "rollout.json"), "stratoscan-rollout"),
          "and the policy it signed through the agent is one a unit accepts")
    check(d is not None and json.load(open(os.path.join(d, "rollout.json")))["ring"] == 1,
          "and it is the policy that was asked for")
    check(w.prompts() == 1, f"the passphrase is asked for once (asked {w.prompts()} times)")
    adds = w.adds()
    life = adds[0].split()[adds[0].split().index("-t") + 1] if len(adds) == 1 and "-t" in adds[0].split() else ""
    check(len(adds) == 1 and life.isdigit() and 0 < int(life) <= 900,
          f"the key is loaded once, with a lifetime of minutes: {adds}")
    check(w.agent_keys() == [], "the key the run loaded is out of the agent afterwards")
    check(not any(l.split()[:1] == ["-D"] for l in w.lines(w.addlog)),
          "the script never empties the agent")

    # --- a key someone else loaded is not the script's to remove ------------
    w.preload(w.other)
    r = w.release_sh("rollout", v, "--ring", "1", "--force", "--dry-run")
    check(r.returncode == 0 and w.agent_keys() == [other_pub],
          "another key in the agent is still there after the run, and the release key is not")

    # --- a release key loaded beforehand is used and left -------------------
    w.preload(w.key)
    r = w.release_sh("rollout", v, "--ring", "1", "--force", "--dry-run")
    d = dry_policy(r.stdout)
    check(r.returncode == 0 and d is not None and w.verifies(os.path.join(d, "rollout.json"), "stratoscan-rollout"),
          "a run with the key already loaded signs")
    check(w.prompts() == 0 and w.adds() == [],
          "and neither asks for the passphrase nor loads anything")
    check(w.agent_keys() == sorted([other_pub, release_pub]),
          "and leaves the agent exactly as it found it")
    w.empty_agent()

    # --- no agent: a clear refusal, nothing signed ---------------------------
    r = w.release_sh("rollout", v, "--ring", "1", "--force", "--dry-run", agent=False)
    check(r.returncode != 0 and "ssh-agent" in r.stderr and w.prompts() == 0,
          "with no agent the run stops, says so, and never asks for the passphrase")
    check(dry_policy(r.stdout) is None, "and reports no signed policy")

    # --- showing a policy needs no key ---------------------------------------
    r = w.release_sh("rollout", v)
    check(r.returncode == 0 and "ring 0" in r.stdout and w.prompts() == 0 and w.adds() == [],
          "showing the policy asks for nothing")

    # --- a refusal that needs no signature never loads the key --------------
    r = w.release_sh("rollout", v, "--ring", "1", "--dry-run")
    check(r.returncode != 0 and "soaks" in r.stderr and w.adds() == [],
          "the soak refusal comes before the key is loaded")

    # --- every way out removes the key --------------------------------------
    # A failed self-check: the key in the file is not the one units trust...
    # (the downloads must still verify, so they are signed by the trusted one).
    w.trust(open(w.stranger + ".pub").read())
    shutil.rmtree(w.assets); os.makedirs(w.assets)
    m = os.path.join(w.assets, "manifest.json")
    with open(m, "w") as f:
        json.dump({"version": v, "serial": 40, "created": "2026-01-01T00:00:00Z", "files": {}}, f)
    w.sign(m, "stratoscan", key=w.stranger)
    os.rename(m + ".sig", os.path.join(w.assets, "manifest.stratoscan.sig"))
    r = w.release_sh("rollout", v, "--ring", "0", "--dry-run")
    # Refused before the key is loaded at all (2026-11-15): the key file's
    # fingerprint is checked against the devices' own list first. It used to
    # be loaded, sign, and fail the self-check afterwards.
    check(r.returncode != 0 and "is not one deploy/allowed_signers names" in r.stderr,
          "a key the devices do not trust is refused, and nothing is signed with it")
    check(len(w.adds()) == 0 and w.agent_keys() == [],
          "before it is ever loaded into the agent")
    w.trust(w.pub)

    # ...and a signal, while the upload is under way.
    v = w.publish(hours_ago=30)
    open(os.path.join(w.tmp, "slow-upload"), "w").close()
    for f in (w.asked, w.addlog, os.path.join(w.tmp, "uploading")):
        if os.path.exists(f):
            os.unlink(f)
    p = subprocess.Popen(["sh", os.path.join(w.repo, "scripts", "release.sh"), "rollout", v, "--ring", "1"],
                         env=w.env(), cwd=w.tmp, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.time() + 30
    while time.time() < deadline and not os.path.exists(os.path.join(w.tmp, "uploading")):
        time.sleep(0.05)
    held = w.agent_keys()
    p.send_signal(signal.SIGTERM)
    p.communicate(timeout=30)
    check(held == [release_pub], "positive control: the key is in the agent while the run signs and uploads")
    check(p.returncode == 143 and w.agent_keys() == [],
          f"a run stopped by a signal removes the key before it goes (exit {p.returncode})")
    os.unlink(os.path.join(w.tmp, "slow-upload"))

    # A real (not dry) rollout, start to finish.
    shutil.rmtree(w.uploads); os.makedirs(w.uploads)
    r = w.release_sh("rollout", v, "--ring", "1")
    up = os.path.join(w.uploads, "rollout.json")
    check(r.returncode == 0 and os.path.exists(up) and w.verifies(up, "stratoscan-rollout")
          and json.load(open(up))["ring"] == 1 and w.agent_keys() == [] and w.prompts() == 1,
          "a published rollout is signed, uploaded, asked once, and leaves the agent empty")

    # --- downloads are verified before anything in them is believed ---------
    def refused(what, *args):
        r = w.release_sh("rollout", v, *args)
        check(r.returncode != 0 and "REFUSED" in r.stderr and "not signed by the release key" in r.stderr,
              what + ": refused" + ("" if r.returncode else " (it ran)"))
        check(w.adds() == [] and w.prompts() == 0, what + ": refused before the key is loaded")
        check(dry_policy(r.stdout) is None, what + ": no policy signed")

    # The attack: ring 3 and an old release time, written into the policy
    # asset, so that the next --pause or --resume signs them.
    v = w.publish(ring=0, hours_ago=1)
    p = os.path.join(w.assets, "rollout.json")
    forged = json.load(open(p))
    forged.update(ring=3, released_at="2026-01-01T00:00:00Z")
    with open(p, "w") as f:
        json.dump(forged, f)
    refused("a policy edited after it was signed", "--pause", "--dry-run")
    refused("a policy edited after it was signed, shown", )

    w.publish(ring=3, hours_ago=100)
    os.unlink(os.path.join(w.assets, "rollout.json.sig"))
    refused("a policy with no signature", "--resume", "--dry-run")

    w.publish()
    os.unlink(os.path.join(w.assets, "rollout.json.sig"))
    w.sign(os.path.join(w.assets, "rollout.json"), "stratoscan-rollout", key=w.stranger)
    refused("a policy signed by another key", "--pause", "--dry-run")

    w.publish()
    os.unlink(os.path.join(w.assets, "rollout.json.sig"))
    w.sign(os.path.join(w.assets, "rollout.json"), "stratoscan")
    refused("a policy signed as if it were a manifest", "--pause", "--dry-run")

    w.publish()
    m = os.path.join(w.assets, "manifest.json")
    edited = json.load(open(m))
    edited["created"] = "2026-01-01T00:00:00Z"
    with open(m, "w") as f:
        json.dump(edited, f)
    refused("a manifest edited after it was signed", "--ring", "1", "--dry-run")

    w.publish()
    os.unlink(os.path.join(w.assets, "manifest.stratoscan.sig"))
    os.unlink(os.path.join(w.assets, "manifest.json.sig"))
    refused("a manifest with no signature", "--ring", "0", "--dry-run")

    # Another release's manifest and policy, both genuinely signed, attached
    # to this one.
    w.publish(version="2025.12.01.1", serial=20, ring=3, hours_ago=500)
    r = w.release_sh("rollout", v, "--pause", "--dry-run")
    check(r.returncode != 0 and "some other release" in r.stderr and w.adds() == [],
          "a signed manifest for a different release is refused")

    # Positive controls, so the refusals above are for the right reason.
    w.publish(ring=1, hours_ago=30)
    r = w.release_sh("rollout", v, "--pause", "--dry-run")
    d = dry_policy(r.stdout)
    pol = json.load(open(os.path.join(d, "rollout.json"))) if d else {}
    check(r.returncode == 0 and pol.get("paused") is True and pol.get("ring") == 1,
          "an untouched release pauses at the ring its signed policy names")
    w.publish()
    os.unlink(os.path.join(w.assets, "manifest.stratoscan.sig"))
    r = w.release_sh("rollout", v)
    check(r.returncode == 0, "a release from before the rename, with only the older manifest signature, is read")
    w.publish(policy=False)
    r = w.release_sh("rollout", v)
    check(r.returncode == 0 and "no rollout policy" in r.stdout, "a release with no policy at all is still shown as such")
    check(w.agent_keys() == [], "the agent is empty at the end of all of it")

    # --- a whole release: three signatures, one prompt -----------------------
    git = lambda *a: subprocess.run(["git", "-C", w.repo, *a], env=dict(w.env(), GIT_CONFIG_GLOBAL=os.devnull,
                                    GIT_CONFIG_SYSTEM=os.devnull), check=True, capture_output=True, text=True)
    for d in ("sounds", "vendor"):
        os.makedirs(os.path.join(w.repo, d))
        open(os.path.join(w.repo, d, "placeholder"), "w").close()
    with open(os.path.join(w.repo, "index.html"), "w") as f:
        f.write("<html></html>\n")
    # The advisory check needs the network; it has its own test.
    script(os.path.join(w.repo, "scripts", "check-vendor.py"), "import sys\nsys.exit(0)\n")
    git("init", "-q", "-b", "main")
    git("add", "-A")
    git("-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "one")
    origin = os.path.join(w.tmp, "origin.git")
    subprocess.run(["git", "init", "-q", "--bare", origin], check=True, capture_output=True)
    git("remote", "add", "origin", origin)
    git("push", "-q", "origin", "main")
    os.unlink(os.path.join(w.tmp, "latest"))          # no release yet
    r = w.release_sh("2026.01.03.1", "--dry-run")
    out = os.path.join(w.repo, "dist", "2026.01.03.1")
    check(r.returncode == 0 and "self-check: both" in r.stdout, "a release builds and passes its self-check: " + r.stderr[-300:])
    m = os.path.join(out, "manifest.json")
    check(os.path.exists(m) and w.verifies(m, "stratoscan", os.path.join(out, "manifest.stratoscan.sig")),
          "the manifest signature made through the agent verifies")
    check(os.path.exists(m) and subprocess.run(
              ["ssh-keygen", "-Y", "verify", "-f", w.signers, "-I", "flightradar-release", "-n", "flightradar",
               "-s", m + ".sig"], stdin=open(m, "rb"), capture_output=True).returncode == 0,
          "so does the one for updaters from before the rename")
    check(w.verifies(os.path.join(out, "rollout.json"), "stratoscan-rollout") if os.path.exists(m) else False,
          "and the rollout policy's")
    check(w.prompts() == 1 and len(w.adds()) == 1,
          f"three signatures, one passphrase prompt (asked {w.prompts()} times)")
    check(w.agent_keys() == [], "and the key is gone from the agent when the release is cut")


if __name__ == "__main__":
    sys.exit(main())
