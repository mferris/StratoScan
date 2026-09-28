// Radome relay (Cloudflare Worker + D1). See docs/ROADMAP.md.
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
} from './limits.js';

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
async function events(request, env) {
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
  return json(200, { ok: true, stored: clean.length, phones });
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
  return json(200, { ok: true });
}

// ---- fleet view (maintainer only) -----------------------------------------

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
    headers: { 'WWW-Authenticate': 'Basic realm="Radome fleet", charset="UTF-8"' },
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

async function fleetPage(env) {
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
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Radome fleet</title>
<style>
  body{font:15px/1.4 system-ui,sans-serif;margin:16px;background:#0f1417;color:#e6e6e6}
  table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #2a3338;text-align:left;vertical-align:top}
  tr.warn td:nth-child(5){color:#ffb44d} tr.ok td:nth-child(5){color:#6fd08c} code{color:#8aa}
  input{background:#1b2226;color:#e6e6e6;border:1px solid #2a3338;padding:4px}
  button{background:#23424f;color:#e6e6e6;border:0;padding:5px 10px;margin-left:4px}
</style></head><body>
<h1>Radome fleet</h1><p>${rows ? '' : 'No unit has reported yet.'}</p>
<table><tr><th>Unit</th><th>Version</th><th>Last report</th><th>Uptime</th><th>Status</th><th>Alerts 24h</th><th></th></tr>${rows}</table>
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

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    const m = request.method;
    if (pathname === '/health' && m === 'GET') return json(200, { ok: true });
    if (pathname === '/v1/heartbeat' && m === 'POST') return heartbeat(request, env);
    if (pathname === '/v1/events' && m === 'POST') return events(request, env);
    if (pathname === '/v1/unit/pairing' && m === 'POST') return unitOffer(request, env);
    if (pathname === '/v1/unit/pairing/cancel' && m === 'POST') return unitCancelOffer(request, env);
    if (pathname === '/v1/unit/phones' && m === 'GET') return unitPhones(request, env);
    if (pathname === '/v1/unit/unpair' && m === 'POST') return unitUnpair(request, env);
    if (pathname === '/v1/pair' && m === 'POST') return phonePair(request, env);
    if (pathname === '/v1/phone/units' && m === 'GET') return phoneUnits(request, env);
    if (pathname === '/v1/phone/unpair' && m === 'POST') return phoneUnpair(request, env);
    if (pathname === '/fleet' || pathname === '/fleet.json' || pathname === '/fleet/name') {
      const state = maintainer(request, env);
      if (state !== 'ok') return needAuth(state);
      if (pathname === '/fleet' && m === 'GET') return fleetPage(env);
      if (pathname === '/fleet.json' && m === 'GET') {
        const now = nowS();
        return json(200, (await listUnits(env)).map(u => ({ ...u, payload: undefined, ...assess(u, now) })));
      }
      if (pathname === '/fleet/name' && m === 'POST') return nameUnit(request, env);
    }
    return json(404, { error: 'not found' });
  },
};
