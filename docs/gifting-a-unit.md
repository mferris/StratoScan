# Gifting a unit: the two things code cannot fix

Everything else in this project is enforced by code that ships with the
device. These two are properties of the *tailnet* the unit joins, so they
live in the Tailscale admin console and have to be set there before a unit
leaves the house.

Both are fixed by the same change: **give gifted units a tag.**

---

## Managed radars and everyone else

There are two kinds of radar, and this document is about the first.

**Managed:** units you give away and want to look after remotely.
- The **radar itself** joins your tailnet as a tagged device. The person you gave it to never gets a Tailscale login and never sees your network.
- You can reach the radar (SSH and its web page), and it gets a public address (Funnel) for its owner's app away from home.
- The radar can't reach anything of yours.

What you'll be able to do:
- you can log in to a device on someone else's home network, so **tell them**;
- from that shell you could also reach other devices on their network, so treat it as access they've lent you, not yours to use.

**Everyone else:** bought or built their own.
- They don't join your tailnet.
- Alerts (through the relay), pairing and signed updates work for them exactly as for managed radars.
- A public address, if they want one, comes from their own Tailscale account, through the setup page's "Public web address" step.

## Preparing a managed radar

Do this at home before it leaves, once the policy change below is in place.

1. In the Tailscale admin console, under **Settings → Keys**, generate an auth key that is:
   - **one-off**;
   - **pre-approved**;
   - tagged **`tag:stratoscan`**.

   A device joined with a tagged key is tagged from the start, and tagged devices don't expire.
2. On the radar's setup page, open **Public web address**:
   - paste the key;
   - give it a hostname (for example `stratoscan-mom`; nothing that would identify them to the public);
   - turn the public address on.
3. Check it from outside the house: run `ssh mferris@<hostname>` over the tailnet, and open the public address on a phone with WiFi off.
4. At its new home, the owner only needs to give it their WiFi, on its screen. Tailscale stays joined when the network changes.

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
    "tag:stratoscan": ["autogroup:admin"],
  },

  "acls": [
    // ... your existing rules stay as they are ...

    // You -> the radar units: SSH to maintain, HTTP for the page.
    {
      "action": "accept",
      "src":    ["autogroup:member"],
      "dst":    ["tag:stratoscan:22,80"],
    },

    // There is deliberately NO rule with "src": ["tag:stratoscan"].
    // Tailscale default-denies, so a gifted unit can reach nothing on the
    // tailnet. That absence is the security control -- adding a broad rule
    // later silently undoes this whole document.
  ],

  // Funnel is granted per node and is NOT inherited by a tagged node.
  // Without this the public URL stops working the moment you tag the unit.
  "nodeAttrs": [
    {
      "target": ["tag:stratoscan"],
      "attr":   ["funnel"],
    },
  ],
}
```

### Step 2 — on the unit

```bash
sudo tailscale up --advertise-tags=tag:stratoscan --reset
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
1-hour ban. SSH has been key-only on every unit since 2026-09-28 (no
passwords, no root login), so the recovery route when keys fail is the
unit's own screen or its setup page, not SSH.

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


## Installing a managed radar

The installer does the unit-side hardening itself when told the radar is a
managed one (security review 2026-10-04, items 6 and 8). Make one SSH key
pair per fleet first, so a key found on one unit opens nothing else:

```
ssh-keygen -t ed25519 -f ~/.ssh/stratoscan-fleet-family -C "stratoscan fleet: family"
```

Then, on the unit, from the checkout:

```
MANAGED=1 MAINTAINER_USER=<the unit's login user> \
MAINTAINER_PUBKEY="$(cat ~/.ssh/stratoscan-fleet-family.pub)" \
sudo sh deploy/install-setup-server.sh
```

What that changes, and only that:

- **SSH only over Tailscale.** An nftables rule drops port 22 from anywhere
  but the tailnet (`deploy/stratoscan-managed.nft`). The radar's page stays
  on the LAN for its owner; the public tunnel was outbound-only already.
- **A narrow sudo rule.** The login user may run the maintenance commands
  as root (`deploy/stratoscan-maintainer.sudoers`: apply or check an update,
  restart or look at the StratoScan services, read the journal, reboot) and
  nothing else; Raspberry Pi OS's `NOPASSWD: ALL` is removed and the user
  leaves the `sudo` group. Real changes reach the unit as signed updates.
  Service-file changes, which the updater refuses, need the owner at the
  keyboard; keep them rare.
- **Writes to the shared stores only from private addresses**
  (`deploy/92-stratoscan-managed-writes.conf`), so a radar on a shared
  network takes its sighting and approach records only from its own LAN,
  its setup hotspot or the tailnet.
- **The fleet's key** goes into the user's `authorized_keys`, once.
- **Rollout ring 1.** Releases reach units in rings (README, "A release
  reaches units in rings"): a managed unit starts in ring 1, so it takes a
  release the day after the maintainer's own radar has run it, not at the
  same time. `RING=2` or `RING=3` on the install command puts it later in
  the order; the file is `/etc/stratoscan/ring`.

Nothing here runs on RDU or on a unit its owner administers: without
`MANAGED=1` the installer skips the whole block (the ring file is written
for every unit; without `MANAGED=1` or `RING=` it says 3, everyone).
