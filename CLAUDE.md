# Working in this repository

This is the public, open-source StratoScan repository (MIT). Everything
committed here is published, including its history.

Never add:

- personal details: names beyond the copyright and trademark lines, home
  addresses or coordinates, LAN addresses, login names, device hostnames,
  router or ISP details;
- account identifiers: Apple team or key IDs, Cloudflare account or database
  IDs, tailnet names, public tunnel hostnames;
- business material: company names, pricing, costs, orders, App Store plans,
  customers;
- how the maintainer runs their own service: signing keys, fleet lists,
  monitoring, runbooks.

Use placeholders instead: `<radar>`, `<user>`, `relay.example.com`,
`com.example.stratoscan`. Test fixtures use RDU airport (35.8776, -78.7875)
and 192.168.1.23.

Configuration that belongs to one person stays out of git:
`relay/wrangler.toml` (start from `relay/wrangler.example.toml`),
`ios/Config/Team.xcconfig`, and `.dev-pi`.

Private work elsewhere may read this repository. This repository never
reads, quotes or links to private material.

## The cases are one design

`enclosure/` holds several cases for the same hardware: Retro, Kitten, and
Retro with Dials. They share a core that every case must keep identical:
- the shell's internals and screw posts;
- the retainer;
- the back plate, with its USB-C pocket and vents;
- the antenna mounts and their covers;
- the gauges.

Only the outsides differ.

When you change any shared part, in any case:

1. Make the change in every full design (`retro-enclosure.scad` and
   `kitten-enclosure-twotone.scad`). Variants such as Retro with Dials
   `include` a full design, so they pick it up. Never copy a shared module
   into a variant.
2. Re-export that part's print files in every folder that ships them, and
   the variant's own print files if the change reaches them.
3. Run `python3 tests/test_enclosure_core.py`, and `sh run-checks.sh` in
   every case folder. The test fails for each of these:
   - shared modules or parameters that differ between designs;
   - a variant that redefines a shared part;
   - a print file of a different shape in different folders;
   - a print file that no longer matches its design;
   - an unregistered new case folder.
4. A new case is registered in that test, as a full design (`FULL`) or a
   variant (`VARIANTS`), before it is committed.
