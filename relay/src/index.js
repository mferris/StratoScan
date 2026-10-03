// StratoScan relay (Cloudflare Worker + D1). See docs/ROADMAP.md.
//
// POST /v1/heartbeat   signed by a unit; records its health (never a location)
// POST /v1/events      signed by a unit; moments for its paired phones (never a location)
//
// Pairing (roadmap 2.3), units signing with X-FR-Unit:
// POST /v1/unit/pairing          offer a one-time secret's hash (shown on screen as a QR code)
// POST /v1/unit/pairing/cancel   withdraw it
// GET  /v1/unit/phones           the phones paired with this unit, and any open offer
// POST /v1/unit/unpair           remove one phone, or all
// ...and phones signing with X-FR-Phone:
// POST /v1/pair                  present a unit's secret; become paired with it
// GET  /v1/phone/units           the units this phone is paired with
// POST /v1/phone/unpair          leave a unit
// POST /v1/phone/register        this phone's push token and which alerts it wants (2.1)
// POST /v1/phone/test            send this phone a test notification
// POST /v1/phone/activity        the token of a Live Activity the phone started (to end it later)
// GET  /fleet          the maintainer's view of every unit (HTTP Basic auth)
// GET  /fleet.json     the same, as JSON
// POST /fleet/name     name a unit ("Dad's radar")
// GET  /health         liveness
//
// A unit that cannot reach this keeps working exactly as before: the radar
// never depends on it.

import { verifyRequest, sha256Hex, b64urlDecode } from './auth.js';
// Only `default` may be exported from this file: the Workers runtime treats
// every named export of the main module as an entrypoint and refuses to
// start on anything else. Shared constants and helpers live in limits.js.
import {
  MAX_BODY, MIN_INTERVAL_S, MAX_UNITS, HISTORY_PER_UNIT, assess,
  MAX_EVENTS_PER_REQUEST, EVENTS_PER_HOUR, EVENTS_PER_UNIT, EVENT_RETENTION_S, cleanEvent,
  PAIRING_TTL_S, PAIRING_MAX_ATTEMPTS, MAX_PHONES_PER_UNIT, MAX_UNITS_PER_PHONE, cleanPhoneName,
  PUSHES_PER_HOUR, PUSHES_PER_HOUR_HARD, PUSHES_PER_BATCH, cleanKinds,
  LOCATION_TTL_S, LOCATION_MIN_GAP_S, LOCATION_BLOB_MAX, BOX_KEY_CONTEXT, NEARBY_KINDS,
} from './limits.js';
import * as apns from './apns.js';
import { fleetRoutes } from './fleets.js';

const nowS = () => Math.floor(Date.now() / 1000);

function json(status, obj) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

async function readBody(request) {
  const len = Number(request.headers.get('Content-Length') || 0);
  if (len > MAX_BODY) return null;
  const buf = new Uint8Array(await request.arrayBuffer());
  return buf.length > MAX_BODY ? null : buf;
}

const carriesLocation = text => /"(lat|lon|latitude|longitude)"\s*:/i.test(text);

async function heartbeat(request, env) {
  const body = await readBody(request);
  if (!body) return json(413, { error: 'too large' });
  const auth = await verifyRequest(request, body, nowS());
  if (auth.error) return json(401, { error: auth.error });

  let payload;
  try {
    payload = JSON.parse(new TextDecoder().decode(body));
  } catch {
    return json(400, { error: 'not json' });
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return json(400, { error: 'expected an object' });
  }
  // A location has no business here. Refuse rather than silently store one
  // if a future client bug ever included it.
  const text = JSON.stringify(payload);
  if (carriesLocation(text)) return json(400, { error: 'location fields are not accepted' });

  const db = env.DB;
  const existing = await db.prepare('SELECT last_ts FROM units WHERE id = ?').bind(auth.unit).first();
  if (existing) {
    if (auth.ts <= existing.last_ts) return json(409, { error: 'replayed or out of order' });
    if (auth.ts - existing.last_ts < MIN_INTERVAL_S) return json(429, { error: 'too frequent' });
  } else {
    const { n } = await db.prepare('SELECT COUNT(*) AS n FROM units').first();
    if (n >= MAX_UNITS) return json(503, { error: 'fleet full' });
  }

  const version = typeof payload.version === 'string' ? payload.version.slice(0, 32) : null;
  const seen = nowS();
  await db.batch([
    db.prepare(
      `INSERT INTO units (id, first_seen, last_seen, last_ts, version, payload)
       VALUES (?1, ?2, ?2, ?3, ?4, ?5)
       ON CONFLICT(id) DO UPDATE SET last_seen = ?2, last_ts = ?3, version = ?4, payload = ?5`
    ).bind(auth.unit, seen, auth.ts, version, text),
    db.prepare('INSERT INTO heartbeats (unit, ts, payload) VALUES (?, ?, ?)').bind(auth.unit, auth.ts, text),
    db.prepare(
      `DELETE FROM heartbeats WHERE unit = ?1 AND ts NOT IN
         (SELECT ts FROM heartbeats WHERE unit = ?1 ORDER BY ts DESC LIMIT ?2)`
    ).bind(auth.unit, HISTORY_PER_UNIT),
  ]);
  return json(200, { ok: true });
}

// Events are delivered to the unit's paired phones (roadmap 2.1) and kept
// only EVENT_RETENTION_S: "a helicopter passed within 2 miles" says roughly
// where a unit is, to anyone who reads it.
async function events(request, env, ctx) {
  const body = await readBody(request);
  if (!body) return json(413, { error: 'too large' });
  const auth = await verifyRequest(request, body, nowS());
  if (auth.error) return json(401, { error: auth.error });

  let payload;
  try {
    payload = JSON.parse(new TextDecoder().decode(body));
  } catch {
    return json(400, { error: 'not json' });
  }
  if (carriesLocation(JSON.stringify(payload))) return json(400, { error: 'location fields are not accepted' });
  const list = payload && Array.isArray(payload.events) ? payload.events : null;
  if (!list || list.length === 0 || list.length > MAX_EVENTS_PER_REQUEST) {
    return json(400, { error: `expected 1-${MAX_EVENTS_PER_REQUEST} events` });
  }
  const clean = list.map(e => cleanEvent(e, auth.ts));
  const bad = clean.indexOf(null);
  if (bad !== -1) return json(400, { error: 'bad event', index: bad });

  const db = env.DB;
  // Nobody to deliver to: store nothing, and say so. The unit turns its
  // events off when it hears this, so an unpaired unit stops sending.
  const phones = await phoneCount(db, auth.unit);
  if (phones === 0) return json(200, { ok: true, stored: 0, phones: 0 });

  const state = await db.prepare('SELECT * FROM event_senders WHERE unit = ?').bind(auth.unit).first();
  if (state) {
    if (auth.ts <= state.last_ts) return json(409, { error: 'replayed or out of order' });
  } else {
    const { n } = await db.prepare('SELECT COUNT(*) AS n FROM event_senders').first();
    if (n >= MAX_UNITS) return json(503, { error: 'fleet full' });
  }
  let start = state ? state.window_start : auth.ts;
  let count = state ? state.window_count : 0;
  if (auth.ts - start >= 3600) { start = auth.ts; count = 0; }
  if (count + clean.length > EVENTS_PER_HOUR) return json(429, { error: 'too many events' });

  const received = nowS();
  await db.batch([
    db.prepare(
      `INSERT INTO event_senders (unit, last_ts, window_start, window_count) VALUES (?1, ?2, ?3, ?4)
       ON CONFLICT(unit) DO UPDATE SET last_ts = ?2, window_start = ?3, window_count = ?4`
    ).bind(auth.unit, auth.ts, start, count + clean.length),
    ...clean.map(e => db.prepare('INSERT INTO events (unit, ts, received, kind, payload) VALUES (?, ?, ?, ?, ?)')
      .bind(auth.unit, e.ts, received, e.kind, JSON.stringify(e))),
    db.prepare('DELETE FROM events WHERE unit = ? AND received < ?').bind(auth.unit, received - EVENT_RETENTION_S),
    db.prepare(
      `DELETE FROM events WHERE unit = ?1 AND rowid NOT IN
         (SELECT rowid FROM events WHERE unit = ?1 ORDER BY received DESC, rowid DESC LIMIT ?2)`
    ).bind(auth.unit, EVENTS_PER_UNIT),
  ]);
  // Delivery must never hold up, or fail, the unit's request.
  const delivery = deliver(env, auth.unit, clean).catch(() => {});
  if (ctx && ctx.waitUntil) ctx.waitUntil(delivery); else await delivery;
  return json(200, { ok: true, stored: clean.length, phones });
}

// ---- push delivery (roadmap 2.1) --------------------------------------------

async function deliver(env, unit, evs) {
  if (!apns.configured(env)) return;
  const db = env.DB;
  const { results } = await db.prepare(
    `SELECT p.* FROM pairings x JOIN phones p ON p.id = x.phone
      WHERE x.unit = ? AND p.token IS NOT NULL`
  ).bind(unit).all();
  // Most important first, so a busy batch never crowds out an emergency.
  const rank = e => (e.kind === 'emergency' ? 0 : e.kind === 'test' ? 1 : 2);
  const ordered = [...evs].sort((a, b) => rank(a) - rank(b));
  for (const phone of results || []) {
    let wants = [];
    try { wants = JSON.parse(phone.kinds); } catch { /* none */ }
    // Approaches start and end Live Activities, handled apart from alerts. An
    // approach to a phone's own location (roadmap 2.7) goes to that phone only.
    // A phone near its radar can get both for the same aircraft in one batch
    // (the radar's approach and its own); one countdown per aircraft is
    // enough, so the first that it wants wins.
    const seenHex = new Set();
    const approaches = ordered.filter(x => {
      if (x.kind !== 'approach' && x.kind !== 'approach_end') return false;
      if (x.phone && x.phone !== phone.id) return false;
      if (x.kind === 'approach' && !wants.includes(x.phone ? 'approach_me' : 'approach')) return false;
      const k = x.kind + ':' + x.hex;
      if (seenHex.has(k)) return false;
      seenHex.add(k);
      return true;
    });
    for (const e of approaches.slice(0, 2)) {
      await liveActivity(env, phone, unit, e, wants);
    }
    // Nearby alerts by where the owner wants them about (#44): the radar's
    // (no phone named), this phone's own (named), or both -- once each per
    // aircraft. A phone that hasn't chosen gets the radar's, as before.
    const aboutRadar = wants.includes('near_radar') || !wants.includes('near_me');
    const aboutMe = wants.includes('near_me');
    const seenNearby = new Set();
    const mine = ordered.filter(e => {
      if (e.kind === 'approach' || e.kind === 'approach_end') return false;
      if (e.kind === 'test') return true;
      if (!wants.includes(e.kind)) return false;
      if (!NEARBY_KINDS.includes(e.kind)) return !e.phone;          // emergencies: about the aircraft
      if (e.phone ? (e.phone !== phone.id || !aboutMe) : !aboutRadar) return false;
      const k = e.kind + ':' + e.hex;
      if (seenNearby.has(k)) return false;
      seenNearby.add(k);
      return true;
    });
    let dead = false;
    for (const e of mine.slice(0, PUSHES_PER_BATCH)) {
      const r = await pushTo(env, phone, apns.notificationFor(e, unit), e.kind === 'emergency' || e.kind === 'test');
      if (r.dead) { dead = true; break; }
    }
    const rest = mine.length - PUSHES_PER_BATCH;
    if (!dead && rest > 0) {
      await pushTo(env, phone, apns.summaryFor(rest, unit), false);
    }
    // One write per phone per request: the free plan also caps D1 queries.
    await db.prepare(
      `UPDATE phones SET window_start = ?, window_count = ?${phone.dead ? ', token = NULL' : ''} WHERE id = ?`
    ).bind(phone.window_start, phone.window_count, phone.id).run();
  }
}

async function liveActivity(env, phone, unit, e, wants) {
  const db = env.DB, now = nowS();
  if (e.kind === 'approach') {
    if (!wants.includes(e.phone ? 'approach_me' : 'approach')) return;
    const la = await db.prepare('SELECT start_token FROM live_activity_phones WHERE phone = ?').bind(phone.id).first();
    if (!la) return;                                    // this phone cannot start one (older iOS, or not allowed)
    const r = await pushTo(env, phone, apns.approachStart(e, unit, la.start_token, now), false);
    if (r.dead) await db.prepare('DELETE FROM live_activity_phones WHERE phone = ?').bind(phone.id).run();
    return;
  }
  // approach_end: only if the phone told us about the activity it started.
  const act = await db.prepare('SELECT token FROM live_activities WHERE phone = ? AND hex = ?').bind(phone.id, e.hex).first();
  if (!act) {
    // Not reported yet: remember the end, and send it when the token arrives.
    const had = await db.prepare('SELECT 1 FROM live_activity_phones WHERE phone = ?').bind(phone.id).first();
    if (had) {
      await db.prepare(
        `INSERT INTO live_activity_ends (phone, hex, at) VALUES (?1, ?2, ?3)
         ON CONFLICT(phone, hex) DO UPDATE SET at = ?3`
      ).bind(phone.id, e.hex, now).run();
    }
    return;
  }
  await pushTo(env, phone, apns.approachEnd(e, act.token, now), true);
  await db.prepare('DELETE FROM live_activities WHERE phone = ? AND hex = ?').bind(phone.id, e.hex).run();
}

// One push to one phone, within its hourly allowance. Updates the in-memory
// row only; the caller writes it back. Marks a token Apple calls dead.
async function pushTo(env, phone, notification, exempt) {
  const now = nowS();
  if (now - phone.window_start >= 3600) { phone.window_start = now; phone.window_count = 0; }
  const cap = exempt ? PUSHES_PER_HOUR_HARD : PUSHES_PER_HOUR;
  if (phone.window_count >= cap) return { ok: false, reason: 'rate limited' };
  phone.window_count += 1;
  const r = await apns.send(env, phone, notification, now, env.APNS_FETCH || fetch);
  // A dead Live Activity token says nothing about the phone's alert token.
  if (r.dead && !notification.token) phone.dead = true;
  return r;
}

// Forget push details of phones no longer paired with anything.
const forgetUnpairedPhones = db => db.batch([
  db.prepare('DELETE FROM phones WHERE id NOT IN (SELECT phone FROM pairings)'),
  db.prepare('DELETE FROM live_activity_phones WHERE phone NOT IN (SELECT phone FROM pairings)'),
  db.prepare('DELETE FROM live_activities WHERE phone NOT IN (SELECT phone FROM pairings)'),
  db.prepare('DELETE FROM live_activity_ends WHERE phone NOT IN (SELECT phone FROM pairings)'),
  db.prepare(`DELETE FROM phone_locations WHERE NOT EXISTS
    (SELECT 1 FROM pairings p WHERE p.phone = phone_locations.phone AND p.unit = phone_locations.unit)`),
]);

async function phoneRegister(request, env) {
  const { auth, payload, error } = await signedJson(request, 'X-FR-Phone');
  if (error) return error;
  const token = payload.token;
  if (typeof token !== 'string' || !/^[0-9a-f]{64,200}$/.test(token)) return json(400, { error: 'expected a hex device token' });
  if (!['sandbox', 'production'].includes(payload.env)) return json(400, { error: "env must be 'sandbox' or 'production'" });
  const kinds = cleanKinds(payload.kinds);
  if (!kinds) return json(400, { error: 'unknown alert kind' });
  const db = env.DB;
  const known = await db.prepare('SELECT 1 FROM phones WHERE id = ?').bind(auth.unit).first();
  if (!known) {
    // Only a phone that is paired with something has any business here,
    // which bounds this table by the pairings table.
    const paired = await db.prepare('SELECT 1 FROM pairings WHERE phone = ?').bind(auth.unit).first();
    if (!paired) return json(403, { error: 'pair with a radar first' });
  }
  const la = payload.la_start_token;
  if (la !== undefined && la !== null && (typeof la !== 'string' || !/^[0-9a-f]{64,400}$/.test(la))) {
    return json(400, { error: 'expected a hex push-to-start token' });
  }
  await db.batch([
    db.prepare(
      `INSERT INTO phones (id, token, env, kinds, updated) VALUES (?1, ?2, ?3, ?4, ?5)
       ON CONFLICT(id) DO UPDATE SET token = ?2, env = ?3, kinds = ?4, updated = ?5`
    ).bind(auth.unit, token, payload.env, JSON.stringify(kinds), nowS()),
    la ? db.prepare(
      `INSERT INTO live_activity_phones (phone, start_token, updated) VALUES (?1, ?2, ?3)
       ON CONFLICT(phone) DO UPDATE SET start_token = ?2, updated = ?3`
    ).bind(auth.unit, la, nowS())
       : db.prepare('DELETE FROM live_activity_phones WHERE phone = ?').bind(auth.unit),
  ]);
  return json(200, { ok: true, kinds, push: apns.configured(env) });
}

// The phone reports the update token of a Live Activity it just started, so
// the relay can end it after the aircraft has passed.
async function phoneActivity(request, env) {
  const { auth, payload, error } = await signedJson(request, 'X-FR-Phone');
  if (error) return error;
  const { unit, hex, token } = payload;
  if (!isId(unit) || typeof hex !== 'string' || !/^[0-9a-f]{6}$/.test(hex)
      || typeof token !== 'string' || !/^[0-9a-f]{64,400}$/.test(token)) {
    return json(400, { error: 'expected unit, hex and a hex token' });
  }
  const db = env.DB;
  const paired = await db.prepare('SELECT 1 FROM pairings WHERE unit = ? AND phone = ?').bind(unit, auth.unit).first();
  if (!paired) return json(403, { error: 'not paired with that radar' });
  const now = nowS();
  // Did the approach already end before this report? Then end it now.
  const ended = await db.prepare('SELECT 1 FROM live_activity_ends WHERE phone = ? AND hex = ? AND at > ?')
    .bind(auth.unit, hex, now - 900).first();
  if (ended && apns.configured(env)) {
    const phone = await db.prepare('SELECT * FROM phones WHERE id = ?').bind(auth.unit).first();
    if (phone) {
      await pushTo(env, phone, apns.approachEnd({ hex }, token, now), true);
      await db.prepare('UPDATE phones SET window_start = ?, window_count = ? WHERE id = ?')
        .bind(phone.window_start, phone.window_count, phone.id).run();
    }
    await db.batch([
      db.prepare('DELETE FROM live_activity_ends WHERE phone = ? AND hex = ?').bind(auth.unit, hex),
      db.prepare('DELETE FROM live_activity_ends WHERE at < ?').bind(now - 900),
    ]);
    return json(200, { ok: true, ended: true });
  }
  await db.batch([
    db.prepare(
      `INSERT INTO live_activities (phone, unit, hex, token, created) VALUES (?1, ?2, ?3, ?4, ?5)
       ON CONFLICT(phone, hex) DO UPDATE SET unit = ?2, token = ?4, created = ?5`
    ).bind(auth.unit, unit, hex, token, now),
    // An activity lasts minutes; anything older is stale.
    db.prepare('DELETE FROM live_activities WHERE created < ?').bind(now - 3600),
    db.prepare('DELETE FROM live_activity_ends WHERE at < ?').bind(now - 900),
  ]);
  return json(200, { ok: true });
}

async function phoneTest(request, env) {
  const { auth, error } = await signedJson(request, 'X-FR-Phone');
  if (error) return error;
  if (!apns.configured(env)) return json(503, { error: 'Notifications are not set up on this StratoScan service yet.' });
  const phone = await env.DB.prepare('SELECT * FROM phones WHERE id = ?').bind(auth.unit).first();
  if (!phone || !phone.token) return json(409, { error: 'This phone has not registered for notifications.' });
  const r = await pushTo(env, phone, apns.notificationFor({ kind: 'test' }, 'test'), true);
  await env.DB.prepare(
    `UPDATE phones SET window_start = ?, window_count = ?${phone.dead ? ', token = NULL' : ''} WHERE id = ?`
  ).bind(phone.window_start, phone.window_count, phone.id).run();
  if (!r.ok) return json(r.reason === 'rate limited' ? 429 : 502, {
    error: r.reason === 'rate limited' ? 'Too many notifications this hour; try again later.'
                                       : `Apple did not accept it (${r.reason || r.status}).` });
  return json(200, { ok: true });
}

// ---- pairing (roadmap 2.3) --------------------------------------------------

const phoneCount = async (db, unit) =>
  (await db.prepare('SELECT COUNT(*) AS n FROM pairings WHERE unit = ?').bind(unit).first()).n;

async function signedJson(request, idHeader) {
  const body = await readBody(request);
  if (!body) return { error: json(413, { error: 'too large' }) };
  const auth = await verifyRequest(request, body, nowS(), idHeader);
  if (auth.error) return { error: json(401, { error: auth.error }) };
  if (request.method === 'GET') return { auth, payload: {} };
  try {
    const payload = JSON.parse(new TextDecoder().decode(body));
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error();
    return { auth, payload };
  } catch {
    return { error: json(400, { error: 'expected a JSON object' }) };
  }
}

const isId = v => typeof v === 'string' && (b64urlDecode(v) || []).length === 32;

async function unitOffer(request, env) {
  const { auth, payload, error } = await signedJson(request, 'X-FR-Unit');
  if (error) return error;
  if (typeof payload.secret_hash !== 'string' || !/^[0-9a-f]{64}$/.test(payload.secret_hash)) {
    return json(400, { error: 'secret_hash must be a hex SHA-256' });
  }
  const db = env.DB;
  // Expired codes are dead weight; left in place they would eventually fill
  // the table and stop every unit from pairing.
  await db.prepare('DELETE FROM pairing_offers WHERE expires <= ?').bind(nowS()).run();
  const had = await db.prepare('SELECT 1 FROM pairing_offers WHERE unit = ?').bind(auth.unit).first();
  if (!had) {
    const { n } = await db.prepare('SELECT COUNT(*) AS n FROM pairing_offers').first();
    if (n >= MAX_UNITS) return json(503, { error: 'too many open offers' });
  }
  const expires = nowS() + PAIRING_TTL_S;
  await db.prepare(
    `INSERT INTO pairing_offers (unit, secret_hash, expires, attempts) VALUES (?1, ?2, ?3, 0)
     ON CONFLICT(unit) DO UPDATE SET secret_hash = ?2, expires = ?3, attempts = 0`
  ).bind(auth.unit, payload.secret_hash, expires).run();
  return json(200, { ok: true, expires });
}

async function unitCancelOffer(request, env) {
  const { auth, error } = await signedJson(request, 'X-FR-Unit');
  if (error) return error;
  await env.DB.prepare('DELETE FROM pairing_offers WHERE unit = ?').bind(auth.unit).run();
  return json(200, { ok: true });
}

async function unitPhones(request, env) {
  const { auth, error } = await signedJson(request, 'X-FR-Unit');
  if (error) return error;
  const db = env.DB;
  const { results } = await db.prepare(
    'SELECT phone, name, created FROM pairings WHERE unit = ? ORDER BY created'
  ).bind(auth.unit).all();
  const offer = await db.prepare('SELECT expires FROM pairing_offers WHERE unit = ? AND expires > ?')
    .bind(auth.unit, nowS()).first();
  return json(200, { phones: results || [], offer: offer ? { expires: offer.expires } : null });
}

async function unitUnpair(request, env) {
  const { auth, payload, error } = await signedJson(request, 'X-FR-Unit');
  if (error) return error;
  const db = env.DB;
  if (payload.all === true) {
    await db.batch([
      db.prepare('DELETE FROM pairings WHERE unit = ?').bind(auth.unit),
      db.prepare('DELETE FROM pairing_offers WHERE unit = ?').bind(auth.unit),
      db.prepare('DELETE FROM events WHERE unit = ?').bind(auth.unit),
    ]);
  } else if (isId(payload.phone)) {
    await db.prepare('DELETE FROM pairings WHERE unit = ? AND phone = ?').bind(auth.unit, payload.phone).run();
  } else {
    return json(400, { error: 'name a phone, or all: true' });
  }
  await forgetUnpairedPhones(db);
  return json(200, { ok: true, phones: await phoneCount(db, auth.unit) });
}

async function phonePair(request, env) {
  const { auth, payload, error } = await signedJson(request, 'X-FR-Phone');
  if (error) return error;
  const { unit, secret } = payload;
  if (!isId(unit) || typeof secret !== 'string' || secret.length < 16 || secret.length > 64) {
    return json(400, { error: 'expected unit and secret' });
  }
  const db = env.DB;
  const offer = await db.prepare('SELECT * FROM pairing_offers WHERE unit = ?').bind(unit).first();
  if (!offer || offer.expires <= nowS()) {
    if (offer) await db.prepare('DELETE FROM pairing_offers WHERE unit = ?').bind(unit).run();
    return json(404, { error: 'That pairing code has been used or has expired. Start again from the radar’s screen.' });
  }
  const given = await sha256Hex(new TextEncoder().encode(secret));
  if (!timingSafeEqual(given, offer.secret_hash)) {
    if (offer.attempts + 1 >= PAIRING_MAX_ATTEMPTS) {
      await db.prepare('DELETE FROM pairing_offers WHERE unit = ?').bind(unit).run();
    } else {
      await db.prepare('UPDATE pairing_offers SET attempts = attempts + 1 WHERE unit = ?').bind(unit).run();
    }
    return json(403, { error: 'That is not the code on the radar’s screen.' });
  }
  const already = await db.prepare('SELECT 1 FROM pairings WHERE unit = ? AND phone = ?').bind(unit, auth.unit).first();
  if (!already) {
    if (await phoneCount(db, unit) >= MAX_PHONES_PER_UNIT) {
      return json(409, { error: `A radar can be paired with at most ${MAX_PHONES_PER_UNIT} phones. Unpair one first.` });
    }
    const { n } = await db.prepare('SELECT COUNT(*) AS n FROM pairings WHERE phone = ?').bind(auth.unit).first();
    if (n >= MAX_UNITS_PER_PHONE) {
      return json(409, { error: `A phone can be paired with at most ${MAX_UNITS_PER_PHONE} radars. Unpair one first.` });
    }
  }
  await db.batch([
    db.prepare(
      `INSERT INTO pairings (unit, phone, name, created) VALUES (?1, ?2, ?3, ?4)
       ON CONFLICT(unit, phone) DO UPDATE SET name = ?3`
    ).bind(unit, auth.unit, cleanPhoneName(payload.name), nowS()),
    // One use only: the code on screen is spent.
    db.prepare('DELETE FROM pairing_offers WHERE unit = ?').bind(unit),
  ]);
  return json(200, { ok: true, unit });
}

async function phoneUnits(request, env) {
  const { auth, error } = await signedJson(request, 'X-FR-Phone');
  if (error) return error;
  const { results } = await env.DB.prepare(
    'SELECT unit, created FROM pairings WHERE phone = ? ORDER BY created'
  ).bind(auth.unit).all();
  return json(200, { units: results || [] });
}

async function phoneUnpair(request, env) {
  const { auth, payload, error } = await signedJson(request, 'X-FR-Phone');
  if (error) return error;
  if (!isId(payload.unit)) return json(400, { error: 'name a unit' });
  await env.DB.prepare('DELETE FROM pairings WHERE unit = ? AND phone = ?').bind(payload.unit, auth.unit).run();
  await forgetUnpairedPhones(env.DB);
  return json(200, { ok: true });
}

// ---- fleet view (maintainer only) -----------------------------------------

// ---- where the phone is (roadmap 2.7) ---------------------------------------
// The phone encrypts its location to one radar's box key; the relay keeps the
// ciphertext for that radar to collect, and can never read it.

const paired = (db, unit, phone) =>
  db.prepare('SELECT 1 FROM pairings WHERE unit = ? AND phone = ?').bind(unit, phone).first();

// A radar publishes its box key, signed by its identity key.
async function unitBoxKey(request, env) {
  const { auth, payload, error } = await signedJson(request, 'X-FR-Unit');
  if (error) return error;
  const key = b64urlDecode(payload.key || ''), sig = b64urlDecode(payload.sig || '');
  if (!key || key.length !== 32 || !sig || sig.length !== 64) return json(400, { error: 'key and sig expected' });
  // Checked here too, so a bad key never reaches a phone (which checks again).
  const id = await crypto.subtle.importKey('raw', b64urlDecode(auth.unit), { name: 'Ed25519' }, false, ['verify']);
  const ok = await crypto.subtle.verify({ name: 'Ed25519' }, id, sig, new TextEncoder().encode(BOX_KEY_CONTEXT + payload.key));
  if (!ok) return json(400, { error: 'signature does not match the unit' });
  await env.DB.prepare(
    `INSERT INTO unit_box_keys (unit, key, sig, updated) VALUES (?1, ?2, ?3, ?4)
     ON CONFLICT(unit) DO UPDATE SET key = ?2, sig = ?3, updated = ?4`
  ).bind(auth.unit, payload.key, payload.sig, nowS()).run();
  return json(200, { ok: true });
}

// A paired phone fetches that key (and checks the signature itself).
async function phoneBoxKey(request, env) {
  const { auth, payload, error } = await signedJson(request, 'X-FR-Phone');
  if (error) return error;
  if (!isId(payload.unit)) return json(400, { error: 'name a unit' });
  if (!(await paired(env.DB, payload.unit, auth.unit))) return json(403, { error: 'not paired with that unit' });
  const row = await env.DB.prepare('SELECT key, sig FROM unit_box_keys WHERE unit = ?').bind(payload.unit).first();
  if (!row) return json(404, { error: 'that radar has not published a key yet' });
  return json(200, { key: row.key, sig: row.sig });
}

// A paired phone leaves its encrypted location for one radar; null withdraws it.
async function phoneLocation(request, env) {
  const { auth, payload, error } = await signedJson(request, 'X-FR-Phone');
  if (error) return error;
  const db = env.DB, now = nowS();
  if (!isId(payload.unit)) return json(400, { error: 'name a unit' });
  if (!(await paired(db, payload.unit, auth.unit))) return json(403, { error: 'not paired with that unit' });
  if (payload.blob === null) {
    await db.prepare('DELETE FROM phone_locations WHERE phone = ? AND unit = ?').bind(auth.unit, payload.unit).run();
    return json(200, { ok: true, cleared: true });
  }
  if (typeof payload.blob !== 'string' || payload.blob.length > LOCATION_BLOB_MAX
      || !/^[A-Za-z0-9_-]+$/.test(payload.blob) || (b64urlDecode(payload.blob) || []).length < 32 + 12 + 16 + 8) {
    return json(400, { error: 'blob expected' });
  }
  const last = await db.prepare('SELECT updated FROM phone_locations WHERE phone = ? AND unit = ?')
    .bind(auth.unit, payload.unit).first();
  if (last && now - last.updated < LOCATION_MIN_GAP_S) return json(429, { error: 'too soon' });
  await db.prepare(
    `INSERT INTO phone_locations (phone, unit, blob, updated) VALUES (?1, ?2, ?3, ?4)
     ON CONFLICT(phone, unit) DO UPDATE SET blob = ?3, updated = ?4`
  ).bind(auth.unit, payload.unit, payload.blob, now).run();
  return json(200, { ok: true });
}

// A radar collects its phones' encrypted locations.
async function unitLocations(request, env) {
  const { auth, error } = await signedJson(request, 'X-FR-Unit');
  if (error) return error;
  const db = env.DB, now = nowS();
  await db.prepare('DELETE FROM phone_locations WHERE updated < ?').bind(now - LOCATION_TTL_S).run();
  const { results } = await db.prepare(
    `SELECT l.phone, l.blob, l.updated FROM phone_locations l
       JOIN pairings p ON p.phone = l.phone AND p.unit = l.unit
      WHERE l.unit = ?`
  ).bind(auth.unit).all();
  return json(200, { locations: results || [] });
}

function timingSafeEqual(a, b) {
  const ea = new TextEncoder().encode(a), eb = new TextEncoder().encode(b);
  let diff = ea.length ^ eb.length;
  for (let i = 0; i < Math.max(ea.length, eb.length); i++) diff |= (ea[i] || 0) ^ (eb[i] || 0);
  return diff === 0;
}

function maintainer(request, env) {
  // Never open by default: with no token configured, the fleet view does
  // not exist rather than being public.
  if (!env.FLEET_TOKEN) return 'unconfigured';
  const h = request.headers.get('Authorization') || '';
  const m = /^Basic\s+(.+)$/i.exec(h);
  if (!m) return 'denied';
  let decoded = '';
  try { decoded = atob(m[1]); } catch { return 'denied'; }
  const password = decoded.slice(decoded.indexOf(':') + 1);
  return timingSafeEqual(password, env.FLEET_TOKEN) ? 'ok' : 'denied';
}

function needAuth(state) {
  if (state === 'unconfigured') return new Response('fleet view not configured\n', { status: 503 });
  return new Response('authentication required\n', {
    status: 401,
    headers: { 'WWW-Authenticate': 'Basic realm="StratoScan fleet", charset="UTF-8"' },
  });
}

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function ago(s) {
  if (s < 90) return `${s}s ago`;
  if (s < 5400) return `${Math.round(s / 60)}m ago`;
  if (s < 172800) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

async function listUnits(env) {
  const { results } = await env.DB.prepare(
    `SELECT u.id, u.name, u.first_seen, u.last_seen, u.version, u.payload,
            (SELECT COUNT(*) FROM events e WHERE e.unit = u.id AND e.received > ?) AS events_24h
       FROM units u ORDER BY u.last_seen DESC`
  ).bind(nowS() - 86400).all();
  return results || [];
}

async function fleetPage(env, fleetsHtml = '') {
  const now = nowS();
  const rows = (await listUnits(env)).map(u => {
    const { flags, p } = assess(u, now);
    const uptimeD = p.uptime_s ? (p.uptime_s / 86400).toFixed(1) + 'd' : '—';
    return `<tr class="${flags.length ? 'warn' : 'ok'}">
      <td><b>${esc(u.name || '(unnamed)')}</b><br><code>${esc(u.id.slice(0, 10))}…</code></td>
      <td>${esc(u.version || '—')}</td>
      <td>${esc(ago(now - u.last_seen))}</td>
      <td>${esc(uptimeD)}</td>
      <td>${flags.length ? esc(flags.join(', ')) : 'healthy'}</td>
      <td>${esc(u.events_24h || 0)}</td>
      <td><form method="post" action="/fleet/name"><input type="hidden" name="unit" value="${esc(u.id)}">
        <input name="name" maxlength="40" value="${esc(u.name || '')}" placeholder="name"><button>Save</button></form></td>
    </tr>`;
  }).join('');
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>StratoScan fleet</title><link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 rx=%2222%22 fill=%22%230a1a3a%22/><circle cx=%2250%22 cy=%2250%22 r=%2238%22 fill=%22none%22 stroke=%22%23274a86%22 stroke-width=%227%22/><path d=%22M50 50 L50 12 A38 38 0 0 1 82.9 31 Z%22 fill=%22%235ee7ff%22 opacity=%220.35%22/><line x1=%2250%22 y1=%2250%22 x2=%2282.9%22 y2=%2231%22 stroke=%22%235ee7ff%22 stroke-width=%228%22 stroke-linecap=%22round%22/><circle cx=%2230%22 cy=%2264%22 r=%227%22 fill=%22%233ddc97%22/><circle cx=%2245%22 cy=%2236%22 r=%228.5%22 fill=%22%23ffffff%22/></svg>">
<style>
  body{font:15px/1.4 system-ui,sans-serif;margin:16px;background:#0f1417;color:#e6e6e6}
  table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #2a3338;text-align:left;vertical-align:top}
  tr.warn td:nth-child(5){color:#ffb44d} tr.ok td:nth-child(5){color:#6fd08c} code{color:#8aa}
  input{background:#1b2226;color:#e6e6e6;border:1px solid #2a3338;padding:4px}
  button{background:#23424f;color:#e6e6e6;border:0;padding:5px 10px;margin-left:4px}
</style></head><body>
<h1>StratoScan fleet</h1><p>${rows ? '' : 'No unit has reported yet.'}</p>
<table><tr><th>Unit</th><th>Version</th><th>Last report</th><th>Uptime</th><th>Status</th><th>Alerts 24h</th><th></th></tr>${rows}</table>
${fleetsHtml}
</body></html>`;
  return new Response(html, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store',
      'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'",
      'X-Content-Type-Options': 'nosniff',
    },
  });
}

async function nameUnit(request, env) {
  // Browsers resend Basic credentials to any page that posts here, so a form
  // on another site could rename units. Only accept this site's own form.
  const origin = request.headers.get('Origin');
  if (!origin || origin !== new URL(request.url).origin) {
    return new Response('cross-site request refused\n', { status: 403 });
  }
  const form = await request.formData();
  const unit = String(form.get('unit') || '');
  const name = String(form.get('name') || '').trim().slice(0, 40) || null;
  await env.DB.prepare('UPDATE units SET name = ? WHERE id = ?').bind(name, unit).run();
  return new Response(null, { status: 303, headers: { Location: '/fleet' } });
}

const fleets = fleetRoutes({ json, signedJson, nowS, maintainer, needAuth, assess, esc, ago });

export default {
  async fetch(request, env, ctx) {
    const { pathname } = new URL(request.url);
    const m = request.method;
    if (pathname === '/health' && m === 'GET') return json(200, { ok: true });
    if (pathname === '/v1/heartbeat' && m === 'POST') return heartbeat(request, env);
    if (pathname === '/v1/events' && m === 'POST') return events(request, env, ctx);
    if (pathname === '/v1/unit/pairing' && m === 'POST') return unitOffer(request, env);
    if (pathname === '/v1/unit/pairing/cancel' && m === 'POST') return unitCancelOffer(request, env);
    if (pathname === '/v1/unit/phones' && m === 'GET') return unitPhones(request, env);
    if (pathname === '/v1/unit/unpair' && m === 'POST') return unitUnpair(request, env);
    if (pathname === '/v1/pair' && m === 'POST') return phonePair(request, env);
    if (pathname === '/v1/phone/units' && m === 'GET') return phoneUnits(request, env);
    if (pathname === '/v1/phone/unpair' && m === 'POST') return phoneUnpair(request, env);
    if (pathname === '/v1/phone/register' && m === 'POST') return phoneRegister(request, env);
    if (pathname === '/v1/phone/test' && m === 'POST') return phoneTest(request, env);
    if (pathname === '/v1/phone/activity' && m === 'POST') return phoneActivity(request, env);
    if (pathname === '/v1/unit/boxkey' && m === 'POST') return unitBoxKey(request, env);
    if (pathname === '/v1/unit/locations' && m === 'GET') return unitLocations(request, env);
    if (pathname === '/v1/phone/boxkey' && m === 'POST') return phoneBoxKey(request, env);
    if (pathname === '/v1/phone/location' && m === 'POST') return phoneLocation(request, env);
    const fleetReply = await fleets.route(request, env, pathname, m);
    if (fleetReply) return fleetReply;
    if (pathname === '/fleet' || pathname === '/fleet.json' || pathname === '/fleet/name') {
      const state = maintainer(request, env);
      if (state !== 'ok') return needAuth(state);
      if (pathname === '/fleet' && m === 'GET') return fleetPage(env, await fleets.fleetsSection(env));
      if (pathname === '/fleet.json' && m === 'GET') {
        const now = nowS();
        return json(200, (await listUnits(env)).map(u => ({ ...u, payload: undefined, ...assess(u, now) })));
      }
      if (pathname === '/fleet/name' && m === 'POST') return nameUnit(request, env);
    }
    return json(404, { error: 'not found' });
  },
};
