# Gifting a unit: the two things code cannot fix

Everything else in this project is enforced by code that ships with the
device. These two are properties of the *tailnet* the unit joins, so they
live in the Tailscale admin console and have to be set there before a unit
leaves the house.

Both are fixed by the same change: **give gifted units a tag.**

---

## Why an untagged unit is a problem

A unit set up with a personal auth key joins as a **user-owned node**. It
carries the owner's identity on the tailnet, which has two consequences.

### 1. It can reach the owner's other machines

Measured from a deployed unit, against a tailnet with no rule permitting it:

```
100.69.39.2:5900    OPEN    <- screen sharing, a personal laptop
100.108.51.100:80   OPEN    <- a personal server
100.108.51.100:443  OPEN
```

The recipient has physical access. The node key sits in
`/var/lib/tailscale/tailscaled.state`; file mode is irrelevant against
someone holding the SD card. That makes a gifted unit a durable, credentialed
foothold on a private network — not because the recipient is untrustworthy,
but because their house, their network, and whoever owns the hardware next
all inherit it.

### 2. Its key expires, and the Funnel dies with it

User-owned node keys expire. On a unit checked in September 2026:

```
node key expiry : 2027-02-10        (146 days out)
```

On that date the node drops off the tailnet and the public Funnel URL stops
resolving. Recovery requires re-authenticating in a browser **signed in to
the owner's Tailscale account** — which the recipient does not have. The
unit would simply stop working remotely, with no local symptom and nothing
the person holding it could do.

**Tagged nodes have key expiry disabled by default.** This is the larger of
the two reasons to tag, and the one with a date attached.

---

## The change

### Step 1 — policy file (admin console → Access controls)

The tag must exist in `tagOwners` *before* any node can advertise it.

```jsonc
{
  "tagOwners": {
    "tag:flightradar": ["autogroup:admin"],
  },

  "acls": [
    // ... your existing rules stay as they are ...

    // You -> the radar units: SSH to maintain, HTTP for the page.
    {
      "action": "accept",
      "src":    ["autogroup:member"],
      "dst":    ["tag:flightradar:22,80"],
    },

    // There is deliberately NO rule with "src": ["tag:flightradar"].
    // Tailscale default-denies, so a gifted unit can reach nothing on the
    // tailnet. That absence is the security control -- adding a broad rule
    // later silently undoes this whole document.
  ],

  // Funnel is granted per node and is NOT inherited by a tagged node.
  // Without this the public URL stops working the moment you tag the unit.
  "nodeAttrs": [
    {
      "target": ["tag:flightradar"],
      "attr":   ["funnel"],
    },
  ],
}
```

### Step 2 — on the unit

```bash
sudo tailscale up --advertise-tags=tag:flightradar --reset
```

This re-authenticates the node. Expect to approve it once in a browser.

### Step 3 — verify, in this order

```bash
# the unit can no longer reach your machines (every line should fail)
for t in <your-other-tailnet-ips>; do
  for p in 22 80 443 5900; do
    timeout 3 bash -c "echo > /dev/tcp/$t/$p" 2>/dev/null \
      && echo "STILL OPEN $t:$p" || echo "blocked $t:$p"
  done
done

# the Funnel still works (nodeAttrs took effect)
tailscale funnel status
curl -o /dev/null -w '%{http_code}\n' https://<unit>.<tailnet>.ts.net/

# key expiry is gone
tailscale status --json | grep -i keyexpiry
```

If the Funnel broke, `nodeAttrs` is missing or misspelled — that is the one
step whose failure is silent until someone outside the house tries the URL.

---

## Note on SSH

`fail2ban` is installed and jails `sshd`: 5 failures in 10 minutes earns a
1-hour ban. Password authentication stays enabled on purpose — it is the
recovery route when nothing else works — and this is what makes that safe to
keep.

`ignoreip` exempts `100.64.0.0/10` and `fd7a:115c:a1e0::/48` so a bad run of
passwords can never lock the owner out of the tailnet recovery path. **That
exemption only helps if the ACL above actually permits you to reach the unit
over the tailnet** — the `dst` rule granting port 22 is what makes it real.
Without that rule the exemption protects a route that does not exist.

Be aware the counter is more sensitive than it looks: one `ssh` invocation
can log more than one failure, so roughly three failed attempts is enough to
trigger a ban. Tune in `/etc/fail2ban/jail.local` if that is too tight:

```bash
sudo fail2ban-client set sshd unbanip <your-ip>   # clear a ban now
sudo fail2ban-client status sshd                  # see what is banned
```
