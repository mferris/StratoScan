-- Relay hardening, second part (the 2026-11-04 re-review of SR-03, SR-04,
-- SR-05). Run ONCE, after 2026-11-04-relay-harden.sql, before deploying the
-- Worker that uses it:
--
--   npx wrangler d1 execute stratoscan-relay --remote --file=migrations/2026-11-04-relay-budget.sql
--
-- If the login may not use --file (README), run each statement below in
-- order with --command="...".
--
-- Additive only: one new table and two new columns with defaults. No
-- existing row is changed or removed. A fresh database needs none of this:
-- schema.sql has it all. ALTER TABLE ... ADD COLUMN is not repeatable; a
-- second run fails on the ALTER with "duplicate column name" and changes
-- nothing more.

CREATE TABLE IF NOT EXISTS write_budget (
  tag  TEXT PRIMARY KEY,
  day  INTEGER NOT NULL,
  n    INTEGER NOT NULL
);
ALTER TABLE pairings ADD COLUMN urgent_start INTEGER NOT NULL DEFAULT 0;
ALTER TABLE pairings ADD COLUMN urgent_count INTEGER NOT NULL DEFAULT 0;
