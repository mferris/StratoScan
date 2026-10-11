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
