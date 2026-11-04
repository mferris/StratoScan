// A daily write budget for new keys, per address (security review
// 2026-11-03, SR-04; the 2026-11-04 re-review).
//
// The per-minute limits stop bursts, but not a day: 60 writes a minute from
// one address is 86,400 a day, and the free plan allows 100,000 rows written
// a day for everyone. Anyone can mint keys, so what a new key may write is
// also counted per address for the whole UTC day, in D1 (a minute is all
// Cloudflare's rate-limit bindings can count).
//
// Only keys that are not yet settled are counted (`settledUnit`,
// `settledPhone`): a radar with two days of reports, or a radar or phone
// with a pairing more than a day old. Everything a settled radar and its
// phones do goes uncounted, so a household's radars and phones are counted
// only while they are new, and a real setup (a few reports, a few pairing
// codes, a pairing, a registration) uses a small part of the day's budget.
//
// What is stored: a 16-hex-digit fingerprint of the address's /64 (IPv4:
// the address), mixed with the day, so one day's rows say nothing about
// another's; and for IPv6 the same for its /48. The cleanup deletes the
// rows once their day is over. Never the address itself.
import { sha256Hex } from './auth.js';
import { clientIp, addressKey, netBlock, isV6 } from './ratelimit.js';
import { MEMBER_MIN_AGE_S, MEMBER_MIN_REPORTS, YOUNG_PAIRING_S } from './limits.js';

// Per UTC day. A budgeted request writes about three rows (its own, its
// replay record, this counter), so one address can use at most about
// 750 rows a day of the 100,000 -- it takes some 130 addresses (or /64s)
// to use up a day's writes, instead of two -- and a /48 at most 3,000.
export const NEW_KEY_BUDGET = { addr: 250, net: 1000 };

const fingerprint = async (kind, key, day) =>
  (await sha256Hex(new TextEncoder().encode(`stratoscan-budget-v1:${day}:${kind}:${key}`))).slice(0, 16);

export const budgetDay = now => Math.floor(now / 86400);

// Spends `weight` of the caller's budget. False (and nothing written) when
// it would go over; true otherwise, and always without an address (tests,
// local development).
export async function spend(env, request, now, weight = 1) {
  const ip = clientIp(request);
  const addr = addressKey(ip) || ip;
  if (!addr || weight <= 0) return true;
  const day = budgetDay(now);
  const rows = [[await fingerprint('a', addr, day), NEW_KEY_BUDGET.addr]];
  if (isV6(ip)) rows.push([await fingerprint('n', netBlock(ip), day), NEW_KEY_BUDGET.net]);
  const db = env.DB;
  for (const [tag, cap] of rows) {
    const row = await db.prepare('SELECT n FROM write_budget WHERE tag = ?').bind(tag).first();
    if ((row ? row.n : 0) + weight > cap) return false;
  }
  await db.batch(rows.map(([tag]) => db.prepare(
    'INSERT INTO write_budget (tag, day, n) VALUES (?1, ?2, ?3) ON CONFLICT(tag) DO UPDATE SET n = n + ?3'
  ).bind(tag, day, weight)));
  return true;
}

// A radar with two days of reports (as the shared cache counts them), or
// with a pairing more than a day old. A radar whose health reports are off
// has no reports, so it settles through its first pairing.
export const settledUnit = async (db, unit, now) => !!(await db.prepare(
  `SELECT 1 AS x FROM units WHERE id = ?1 AND first_seen <= ?2 AND reports >= ?3
   UNION ALL SELECT 1 FROM pairings WHERE unit = ?1 AND created <= ?4 LIMIT 1`
).bind(unit, now - MEMBER_MIN_AGE_S, MEMBER_MIN_REPORTS, now - YOUNG_PAIRING_S).first());

// A phone with a pairing more than a day old.
export const settledPhone = async (db, phone, now) => !!(await db.prepare(
  'SELECT 1 AS x FROM pairings WHERE phone = ? AND created <= ? LIMIT 1'
).bind(phone, now - YOUNG_PAIRING_S).first());

// The same test as SQL, for the pairing offer of unit `o.unit`: ?1 is
// now - MEMBER_MIN_AGE_S, ?2 MEMBER_MIN_REPORTS, ?3 now - YOUNG_PAIRING_S.
export const SETTLED_OFFER_SQL = `(EXISTS (SELECT 1 FROM units u WHERE u.id = o.unit AND u.first_seen <= ?1 AND u.reports >= ?2)
  OR EXISTS (SELECT 1 FROM pairings x WHERE x.unit = o.unit AND x.created <= ?3))`;
export const settledOfferArgs = now => [now - MEMBER_MIN_AGE_S, MEMBER_MIN_REPORTS, now - YOUNG_PAIRING_S];
