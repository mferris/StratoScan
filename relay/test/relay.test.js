// Run: npm test  (node --test). Uses Node's WebCrypto (same Ed25519 API as
// Workers) and built-in SQLite behind a D1 stand-in, so the Worker code and
// its real SQL run unmodified.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import worker from '../src/index.js';
import {
  assess, HISTORY_PER_UNIT, MAX_UNITS, MIN_INTERVAL_S, STALE_AFTER_S,
  EVENTS_PER_HOUR, EVENTS_PER_UNIT, EVENT_RETENTION_S, MAX_EVENTS_PER_REQUEST,
  PAIRING_TTL_S, PAIRING_MAX_ATTEMPTS, MAX_PHONES_PER_UNIT,
} from '../src/limits.js';
import { sha256Hex, signedMessage } from '../src/auth.js';
import { makeD1 } from './d1-sqlite.js';

const SCHEMA = fileURLToPath(new URL('../schema.sql', import.meta.url));
const BASE = 'https://relay.example';
const b64url = bytes => Buffer.from(bytes).toString('base64url');

let clock = 1_800_000_000;
Date.now = () => clock * 1000;

async function newUnit() {
  const kp = await crypto.subtle.generateKey({ name: 'Ed25519' }, true, ['sign', 'verify']);
  const raw = new Uint8Array(await crypto.subtle.exportKey('raw', kp.publicKey));
  return { id: b64url(raw), key: kp.privateKey };
}

async function signed(unit, body, { ts = clock, path = '/v1/heartbeat', tamper = null, method = 'POST', as = 'X-FR-Unit' } = {}) {
  const bytes = new TextEncoder().encode(method === 'GET' ? '' : body);
  const msg = signedMessage(ts, method, path, await sha256Hex(bytes));
  const sig = new Uint8Array(await crypto.subtle.sign({ name: 'Ed25519' }, unit.key, new TextEncoder().encode(msg)));
  return new Request(BASE + path, {
    method,
    headers: { [as]: unit.id, 'X-FR-Time': String(ts), 'X-FR-Sig': b64url(sig), 'Content-Type': 'application/json' },
    ...(method === 'GET' ? {} : { body: tamper ?? body }),
  });
}

const env = (extra = {}) => ({ DB: makeD1(SCHEMA), ...extra });
const hb = obj => JSON.stringify({ version: '2026.09.27.16', uptime_s: 3600, ...obj });
const basic = pw => 'Basic ' + btoa('m:' + pw);

test('a signed heartbeat is stored, and its version recorded', async () => {
  const e = env(), u = await newUnit();
  const r = await worker.fetch(await signed(u, hb()), e);
  assert.equal(r.status, 200);
  const row = await e.DB.prepare('SELECT * FROM units WHERE id = ?').bind(u.id).first();
  assert.equal(row.version, '2026.09.27.16');
  assert.equal(row.last_ts, clock);
});

test('forged, altered, replayed and badly-timed requests are refused', async () => {
  const e = env(), u = await newUnit(), other = await newUnit();
  assert.equal((await worker.fetch(await signed(u, hb()), e)).status, 200);

  const replay = await worker.fetch(await signed(u, hb()), e);
  assert.equal(replay.status, 409, 'same timestamp again');

  clock += 60;
  assert.equal((await worker.fetch(await signed(u, hb()), e)).status, 429, 'faster than the minimum interval');

  const altered = await signed(u, hb(), { tamper: hb({ version: 'evil' }) });
  assert.equal((await worker.fetch(altered, e)).status, 401, 'body changed after signing');

  const wrongKey = await signed(other, hb());
  wrongKey.headers.set('X-FR-Unit', u.id);
  assert.equal((await worker.fetch(wrongKey, e)).status, 401, 'signed by a different key');

  const skewed = await signed(u, hb(), { ts: clock - 1000 });
  assert.equal((await worker.fetch(skewed, e)).status, 401, 'outside the clock window');

  const otherPath = await signed(u, hb(), { path: '/v1/other' });
  const moved = new Request(BASE + '/v1/heartbeat', { method: 'POST', headers: otherPath.headers, body: hb() });
  assert.equal((await worker.fetch(moved, e)).status, 401, 'signature bound to another path');

  clock += MIN_INTERVAL_S;
  assert.equal((await worker.fetch(await signed(u, hb()), e)).status, 200, 'a genuine later report');
});

test('a location is never accepted', async () => {
  const e = env(), u = await newUnit();
  clock += 1000;
  const r = await worker.fetch(await signed(u, hb({ receiver: { lat: 35.8, lon: -78.7 } })), e);
  assert.equal(r.status, 400);
  assert.equal(await e.DB.prepare('SELECT * FROM units').first(), null);
});

test('oversized and malformed bodies are refused', async () => {
  const e = env(), u = await newUnit();
  clock += 1000;
  assert.equal((await worker.fetch(await signed(u, JSON.stringify({ pad: 'x'.repeat(9000) })), e)).status, 413);
  assert.equal((await worker.fetch(await signed(u, '[1,2]'), e)).status, 400);
  assert.equal((await worker.fetch(await signed(u, 'not json'), e)).status, 400);
});

test('history is trimmed per unit', async () => {
  const e = env(), u = await newUnit();
  clock += 1000;
  for (let i = 0; i < HISTORY_PER_UNIT + 20; i++) {
    e.DB.raw.prepare('INSERT INTO heartbeats (unit, ts, payload) VALUES (?, ?, ?)').run(u.id, 1_000 + i, '{}');
  }
  assert.equal((await worker.fetch(await signed(u, hb()), e)).status, 200);
  const { n } = e.DB.raw.prepare('SELECT COUNT(*) AS n FROM heartbeats WHERE unit = ?').get(u.id);
  assert.equal(n, HISTORY_PER_UNIT);
});

test('first contact cannot grow the fleet without bound', async () => {
  const e = env();
  const ins = e.DB.raw.prepare('INSERT INTO units (id, first_seen, last_seen, last_ts) VALUES (?, 0, 0, 0)');
  for (let i = 0; i < MAX_UNITS; i++) ins.run('filler' + i);
  clock += 1000;
  assert.equal((await worker.fetch(await signed(await newUnit(), hb()), e)).status, 503);
});

test('the fleet view is never open', async () => {
  const u = await newUnit();
  const unconfigured = env();
  assert.equal((await worker.fetch(new Request(BASE + '/fleet'), unconfigured)).status, 503);

  const e = env({ FLEET_TOKEN: 's3cret' });
  clock += 1000;
  await worker.fetch(await signed(u, hb()), e);
  assert.equal((await worker.fetch(new Request(BASE + '/fleet'), e)).status, 401);
  assert.equal((await worker.fetch(new Request(BASE + '/fleet', { headers: { Authorization: basic('wrong') } }), e)).status, 401);

  const ok = await worker.fetch(new Request(BASE + '/fleet', { headers: { Authorization: basic('s3cret') } }), e);
  assert.equal(ok.status, 200);
  assert.match(await ok.text(), new RegExp(u.id.slice(0, 10)));
});

test('naming a unit works from the fleet page, not from another site, and is escaped', async () => {
  const e = env({ FLEET_TOKEN: 's3cret' }), u = await newUnit();
  clock += 1000;
  await worker.fetch(await signed(u, hb()), e);
  const form = n => new URLSearchParams({ unit: u.id, name: n });
  const post = origin => new Request(BASE + '/fleet/name', {
    method: 'POST', body: form('<b>Dad</b>'),
    headers: { Authorization: basic('s3cret'), 'Content-Type': 'application/x-www-form-urlencoded', ...(origin ? { Origin: origin } : {}) },
  });
  assert.equal((await worker.fetch(post('https://evil.example'), e)).status, 403);
  assert.equal((await worker.fetch(post(null), e)).status, 403);
  assert.equal((await worker.fetch(post(BASE), e)).status, 303);
  const page = await (await worker.fetch(new Request(BASE + '/fleet', { headers: { Authorization: basic('s3cret') } }), e)).text();
  assert.ok(page.includes('&lt;b&gt;Dad&lt;/b&gt;') && !page.includes('<b>Dad</b>'));
});

test('assess flags what needs attention', () => {
  const now = 2_000_000_000;
  const unit = (p, lastSeen = now) => ({ last_seen: lastSeen, payload: JSON.stringify(p) });
  assert.deepEqual(assess(unit({}), now).flags, []);
  assert.ok(assess(unit({}, now - STALE_AFTER_S - 1), now).flags.includes('silent'));
  assert.ok(assess(unit({ receiver: { age_s: 900 } }), now).flags.includes('receiver stale'));
  assert.ok(assess(unit({ rtc: { fitted: true, battery_mv: 2100 } }), now).flags.includes('RTC battery low'));
  assert.ok(!assess(unit({ rtc: { fitted: false, battery_mv: 2 } }), now).flags.includes('RTC battery low'));
  assert.ok(assess(unit({ storage: { gb_per_day: 9 } }), now).flags.includes('heavy writes'));
  assert.ok(assess(unit({ ota: { state: 'rolled_back' } }), now).flags.includes('update rolled_back'));
});

// ---- unit events (roadmap 2.2) ---------------------------------------------

const evBody = (events) => JSON.stringify({ v: 1, events });
const evt = (o = {}) => ({ kind: 'helicopter', ts: clock, hex: 'abc123', flight: 'N407XX', type: 'Bell 407',
  alt_ft: 1000, dist_nm: 1.5, dir: 'NE', ...o });
const postEvents = async (e, u, events, opts = {}) =>
  worker.fetch(await signed(u, evBody(events), { path: '/v1/events', ...opts }), e);
const stored = (e, u) => e.DB.raw.prepare('SELECT kind, payload FROM events WHERE unit = ? ORDER BY rowid').all(u.id);
// Events are only kept for a unit with a paired phone; most tests just need one.
const paired = (e, u, phone = 'P'.repeat(43)) =>
  e.DB.raw.prepare('INSERT INTO pairings (unit, phone, name, created) VALUES (?, ?, ?, ?)').run(u.id, phone, null, clock);

test('signed events are stored, whitelisted, with no need for health reports', async () => {
  const e = env(), u = await newUnit();
  paired(e, u);
  clock += 1000;
  const r = await postEvents(e, u, [evt(), evt({ kind: 'emergency', hex: 'aaaaa1', squawk: '7700', label: 'emergency', extra: 'x' })]);
  assert.equal(r.status, 200);
  assert.deepEqual(await r.json(), { ok: true, stored: 2, phones: 1 });
  const rows = stored(e, u);
  assert.deepEqual(rows.map(x => x.kind), ['helicopter', 'emergency']);
  const em = JSON.parse(rows[1].payload);
  assert.equal(em.squawk, '7700');
  assert.equal(em.extra, undefined, 'unknown fields are dropped');
  assert.equal(await e.DB.prepare('SELECT * FROM units').first(), null, 'events do not register a health-report unit');
});

test('an event carrying a location is refused, and nothing is stored', async () => {
  const e = env(), u = await newUnit();
  paired(e, u);
  clock += 1000;
  assert.equal((await postEvents(e, u, [evt({ lat: 35.8, lon: -78.7 })])).status, 400);
  assert.equal((await postEvents(e, u, [evt({ where: { latitude: 1 } })], { ts: clock + 1 })).status, 400);
  assert.equal(stored(e, u).length, 0);
});

test('bad events are refused whole', async () => {
  const e = env(), u = await newUnit();
  paired(e, u);
  clock += 1000;
  let ts = clock;
  const refused = async (events, why) => {
    ts += 1; clock = ts;
    assert.equal((await postEvents(e, u, events)).status, 400, why);
  };
  await refused([], 'empty');
  await refused(Array.from({ length: MAX_EVENTS_PER_REQUEST + 1 }, () => evt()), 'too many at once');
  await refused([evt({ kind: 'party' })], 'unknown kind');
  await refused([evt({ hex: 'ABC12' })], 'bad hex');
  await refused([evt({ ts: ts - 7200 })], 'too old');
  await refused([evt({ ts: ts + 3600 })], 'from the future');
  await refused([evt(), 'x'], 'one bad event spoils the batch');
  assert.equal(stored(e, u).length, 0);
});

test('event text is made safe for a lock screen', async () => {
  const e = env(), u = await newUnit();
  paired(e, u);
  clock += 1000;
  await postEvents(e, u, [evt({ label: 'Air\u0000 ambulance\u2028' + 'x'.repeat(100), dir: 'up', alt_ft: 1e9, squawk: '9999' })]);
  const p = JSON.parse(stored(e, u)[0].payload);
  assert.ok(p.label.startsWith('Air ambulance') && p.label.length <= 60 && !/[\u0000\u2028]/.test(p.label));
  assert.equal(p.dir, undefined);
  assert.equal(p.alt_ft, undefined);
  assert.equal(p.squawk, undefined);
});

test('events are replay-guarded and rate-limited per unit', async () => {
  const e = env(), u = await newUnit();
  paired(e, u);
  clock += 1000;
  assert.equal((await postEvents(e, u, [evt()])).status, 200);
  assert.equal((await postEvents(e, u, [evt()])).status, 409, 'same timestamp again');
  let sent = 1;
  while (sent + MAX_EVENTS_PER_REQUEST <= EVENTS_PER_HOUR) {
    clock += 5;
    assert.equal((await postEvents(e, u, Array.from({ length: MAX_EVENTS_PER_REQUEST }, () => evt()))).status, 200);
    sent += MAX_EVENTS_PER_REQUEST;
  }
  clock += 5;
  assert.equal((await postEvents(e, u, Array.from({ length: EVENTS_PER_HOUR - sent + 1 }, () => evt()))).status, 429);
  clock += 3600;
  assert.equal((await postEvents(e, u, [evt()])).status, 200, 'a new hour, a new allowance');
});

test('events are kept only briefly, and bounded per unit', async () => {
  const e = env(), u = await newUnit();
  paired(e, u);
  const ins = e.DB.raw.prepare('INSERT INTO events (unit, ts, received, kind, payload) VALUES (?, ?, ?, ?, ?)');
  clock += 1000;
  ins.run(u.id, clock - EVENT_RETENTION_S - 10, clock - EVENT_RETENTION_S - 10, 'notable', '{}');
  for (let i = 0; i < EVENTS_PER_UNIT + 5; i++) ins.run(u.id, clock - 100, clock - 100, 'low_overhead', '{}');
  assert.equal((await postEvents(e, u, [evt()])).status, 200);
  const rows = stored(e, u);
  assert.equal(rows.length, EVENTS_PER_UNIT);
  assert.ok(!rows.some(r => r.kind === 'notable'), 'expired events are gone');
  assert.equal(rows.at(-1).kind, 'helicopter', 'the newest is kept');
});

test('the fleet page counts a unit\'s recent alerts', async () => {
  const e = env({ FLEET_TOKEN: 's3cret' }), u = await newUnit();
  paired(e, u);
  clock += 1000;
  await worker.fetch(await signed(u, hb()), e);
  clock += 1;
  await postEvents(e, u, [evt(), evt({ kind: 'notable', label: 'Air ambulance' })]);
  const list = await (await worker.fetch(new Request(BASE + '/fleet.json', { headers: { Authorization: basic('s3cret') } }), e)).json();
  assert.equal(list[0].events_24h, 2);
  const page = await (await worker.fetch(new Request(BASE + '/fleet', { headers: { Authorization: basic('s3cret') } }), e)).text();
  assert.ok(!page.includes('Air ambulance'), 'the fleet page shows counts, not what a unit saw');
});

test('a unit with no paired phone has its events dropped, and is told so', async () => {
  const e = env(), u = await newUnit();
  clock += 1000;
  const r = await postEvents(e, u, [evt()]);
  assert.equal(r.status, 200);
  assert.deepEqual(await r.json(), { ok: true, stored: 0, phones: 0 });
  assert.equal(stored(e, u).length, 0);
});

// ---- pairing (roadmap 2.3) ---------------------------------------------------

const offer = async (e, u, secret) => worker.fetch(await signed(u,
  JSON.stringify({ secret_hash: await sha256Hex(new TextEncoder().encode(secret)) }), { path: '/v1/unit/pairing' }), e);
const pair = async (e, phone, unit, secret, name = 'Test iPhone') => worker.fetch(await signed(phone,
  JSON.stringify({ unit: unit.id, secret, name }), { path: '/v1/pair', as: 'X-FR-Phone' }), e);
const getAs = async (e, who, path, as = 'X-FR-Unit') => (await worker.fetch(await signed(who, '', { path, method: 'GET', as }), e)).json();
const SECRET = 'test-pairing-code-for-unit-tests';

test('a phone that presents the code on screen is paired, once', async () => {
  const e = env(), u = await newUnit(), phone = await newUnit(), late = await newUnit();
  clock += 1000;
  assert.equal((await offer(e, u, SECRET)).status, 200);
  const offered = await getAs(e, u, '/v1/unit/phones');
  assert.ok(offered.offer && offered.offer.expires === clock + PAIRING_TTL_S);
  assert.equal(e.DB.raw.prepare('SELECT secret_hash FROM pairing_offers').get().secret_hash.includes(SECRET), false,
    'the relay never stores the secret itself');

  const r = await pair(e, phone, u, SECRET);
  assert.equal(r.status, 200);
  assert.deepEqual(await r.json(), { ok: true, unit: u.id });
  const list = await getAs(e, u, '/v1/unit/phones');
  assert.deepEqual(list.phones.map(p => [p.phone, p.name]), [[phone.id, 'Test iPhone']]);
  assert.equal(list.offer, null, 'the code is spent');
  assert.deepEqual((await getAs(e, phone, '/v1/phone/units', 'X-FR-Phone')).units.map(x => x.unit), [u.id]);

  clock += 1;
  assert.equal((await pair(e, late, u, SECRET)).status, 404, 'a second phone cannot reuse the same code');
});

test('a wrong, expired or guessed code pairs nothing', async () => {
  const e = env(), u = await newUnit(), phone = await newUnit();
  clock += 1000;
  await offer(e, u, SECRET);
  assert.equal((await pair(e, phone, u, 'wrong-secret-0123456')).status, 403);
  for (let i = 1; i < PAIRING_MAX_ATTEMPTS; i++) { clock += 1; await pair(e, phone, u, 'wrong-secret-0123456'); }
  clock += 1;
  assert.equal((await pair(e, phone, u, SECRET)).status, 404, 'too many wrong guesses void the offer');

  await offer(e, u, SECRET);
  clock += PAIRING_TTL_S + 1;
  assert.equal((await pair(e, phone, u, SECRET)).status, 404, 'expired');
  assert.equal(e.DB.raw.prepare('SELECT COUNT(*) AS n FROM pairings').get().n, 0);

  clock += 1;
  await offer(e, u, SECRET);
  const forged = await signed(phone, JSON.stringify({ unit: u.id, secret: SECRET }), { path: '/v1/pair', as: 'X-FR-Unit' });
  assert.equal((await worker.fetch(forged, e)).status, 401, 'a phone must name itself as a phone');
});

test('the unit can withdraw a code, and remove one phone or all', async () => {
  const e = env(), u = await newUnit(), a = await newUnit(), b = await newUnit();
  clock += 1000;
  await offer(e, u, SECRET);
  assert.equal((await worker.fetch(await signed(u, '{}', { path: '/v1/unit/pairing/cancel' }), e)).status, 200);
  assert.equal((await pair(e, a, u, SECRET)).status, 404, 'withdrawn');

  for (const p of [a, b]) { clock += 1; await offer(e, u, SECRET); await pair(e, p, u, SECRET); }
  clock += 1;
  let r = await worker.fetch(await signed(u, JSON.stringify({ phone: a.id }), { path: '/v1/unit/unpair' }), e);
  assert.deepEqual(await r.json(), { ok: true, phones: 1 });
  clock += 1;
  await postEvents(e, u, [evt()]);
  clock += 1;
  r = await worker.fetch(await signed(u, JSON.stringify({ all: true }), { path: '/v1/unit/unpair' }), e);
  assert.deepEqual(await r.json(), { ok: true, phones: 0 });
  assert.equal(stored(e, u).length, 0, 'unpairing everyone also clears undelivered events');
});

test('a phone can leave a unit, and only its own pairing', async () => {
  const e = env(), u = await newUnit(), a = await newUnit(), b = await newUnit();
  clock += 1000;
  for (const p of [a, b]) { clock += 1; await offer(e, u, SECRET); await pair(e, p, u, SECRET); }
  clock += 1;
  const r = await worker.fetch(await signed(a, JSON.stringify({ unit: u.id }), { path: '/v1/phone/unpair', as: 'X-FR-Phone' }), e);
  assert.equal(r.status, 200);
  assert.deepEqual((await getAs(e, u, '/v1/unit/phones')).phones.map(p => p.phone), [b.id]);
});

test('pairing is bounded', async () => {
  const e = env(), u = await newUnit();
  const ins = e.DB.raw.prepare('INSERT INTO pairings (unit, phone, name, created) VALUES (?, ?, NULL, 0)');
  for (let i = 0; i < MAX_PHONES_PER_UNIT; i++) ins.run(u.id, String(i).padStart(43, 'x'));
  clock += 1000;
  await offer(e, u, SECRET);
  assert.equal((await pair(e, await newUnit(), u, SECRET)).status, 409);
});

test('a phone name is made safe', async () => {
  const e = env(), u = await newUnit(), phone = await newUnit();
  clock += 1000;
  await offer(e, u, SECRET);
  await pair(e, phone, u, SECRET, 'Mike\u0000s\u2028 phone' + 'x'.repeat(80));
  const name = e.DB.raw.prepare('SELECT name FROM pairings').get().name;
  assert.ok(name.startsWith('Mikes phone') && name.length <= 40);
});

// The unit signs in Python (deploy/heartbeat.py), the relay verifies in
// JavaScript. This fixture was signed on a real unit with a throwaway key; if
// either side's canonical message drifts, every real unit gets rejected.
test('a request signed by the Python unit client verifies', async () => {
  const { readFileSync } = await import('node:fs');
  const fx = JSON.parse(readFileSync(new URL('./python-signed.fixture.json', import.meta.url)));
  clock = Number(fx.headers['X-FR-Time']);
  const e = env();
  const req = new Request(BASE + '/v1/heartbeat', { method: 'POST', headers: fx.headers, body: fx.body });
  assert.equal((await worker.fetch(req, e)).status, 200);
  const tampered = new Request(BASE + '/v1/heartbeat', { method: 'POST', headers: fx.headers, body: fx.body.replace('fixture', 'fixturf') });
  clock += 1;
  assert.equal((await worker.fetch(tampered, env())).status, 401);
});

// The phone signs in Swift (ios/Radome/Pairing/RelayIdentity.swift, CryptoKit).
// Same guarantee as the Python fixture above, for the other client.
test('a request signed by the iOS app verifies', async () => {
  const { readFileSync } = await import('node:fs');
  const fx = JSON.parse(readFileSync(new URL('./swift-signed.fixture.json', import.meta.url)));
  clock = Number(fx.headers['X-FR-Time']);
  const ok = await worker.fetch(new Request(BASE + fx.path, { method: 'GET', headers: fx.headers }), env());
  assert.equal(ok.status, 200);
  assert.deepEqual(await ok.json(), { units: [] });
  const moved = await worker.fetch(new Request(BASE + '/v1/unit/phones', { method: 'GET', headers: fx.headers }), env());
  assert.equal(moved.status, 401, 'the signature is bound to its path');
});

// ---- push (roadmap 2.1) ------------------------------------------------------
// Apple is replaced by a recorder (env.APNS_FETCH): real APNs needs HTTP/2
// from Cloudflare's edge, so it can only be exercised once deployed.

import { PUSHES_PER_HOUR, PUSHES_PER_HOUR_HARD, PUSHES_PER_BATCH } from '../src/limits.js';
import * as apns from '../src/apns.js';

async function apnsKey() {
  const kp = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
  const der = Buffer.from(await crypto.subtle.exportKey('pkcs8', kp.privateKey)).toString('base64');
  return { pem: `-----BEGIN PRIVATE KEY-----\n${der.match(/.{1,64}/g).join('\n')}\n-----END PRIVATE KEY-----\n`, pub: kp.publicKey };
}

function apple(replies = []) {
  const sent = [];
  const fetchImpl = async (url, init) => {
    sent.push({ url, headers: init.headers, body: JSON.parse(init.body) });
    const [status, reason] = replies.shift() || [200];
    return new Response(reason ? JSON.stringify({ reason }) : null, { status });
  };
  return { sent, fetchImpl };
}

async function pushEnv(replies) {
  const key = await apnsKey();
  const a = apple(replies);
  return { e: env({ APNS_KEY: key.pem, APNS_KEY_ID: 'KEYID12345', APNS_TEAM_ID: 'TEAM123456',
                    APNS_TOPIC: 'com.example.radome', APNS_FETCH: a.fetchImpl }), key, a };
}

const TOKEN = 'ab'.repeat(32);
const register = async (e, phone, body) => worker.fetch(await signed(phone, JSON.stringify(body),
  { path: '/v1/phone/register', as: 'X-FR-Phone' }), e);

async function pairedPhone(e, u, opts = {}) {
  const phone = await newUnit();
  await offer(e, u, SECRET); await pair(e, phone, u, SECRET);
  clock += 1;
  const r = await register(e, phone, { token: opts.token || TOKEN, env: opts.env || 'sandbox', kinds: opts.kinds });
  assert.equal(r.status, 200);
  return phone;
}

test('a paired phone gets its alerts, signed the way Apple requires', async () => {
  const { e, key, a } = await pushEnv();
  const u = await newUnit();
  clock += 1000;
  await pairedPhone(e, u);
  clock += 1;
  await postEvents(e, u, [evt({ kind: 'helicopter', hex: 'abc123', flight: 'N407XX', alt_ft: 1000, dist_nm: 1.5, dir: 'NE' })]);
  assert.equal(a.sent.length, 1);
  const p = a.sent[0];
  assert.equal(p.url, `https://api.sandbox.push.apple.com/3/device/${TOKEN}`, 'a development build uses the sandbox');
  assert.equal(p.headers['apns-topic'], 'com.example.radome');
  assert.equal(p.headers['apns-push-type'], 'alert');
  assert.equal(p.body.aps.alert.title, 'Helicopter nearby');
  assert.equal(p.body.aps.alert.body, 'N407XX · Bell 407 · 1,000 ft · 2 mi NE');
  assert.equal(p.body.aps['thread-id'], u.id);

  const [h, c, s] = p.headers.authorization.replace('bearer ', '').split('.');
  const dec = x => JSON.parse(Buffer.from(x, 'base64url').toString());
  assert.deepEqual(dec(h), { alg: 'ES256', kid: 'KEYID12345' });
  assert.equal(dec(c).iss, 'TEAM123456');
  assert.ok(await crypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, key.pub,
    Buffer.from(s, 'base64url'), new TextEncoder().encode(`${h}.${c}`)), 'the provider token verifies with the key');
});

test('a notification never carries a position', async () => {
  const n = apns.notificationFor({ kind: 'emergency', ts: 1, hex: 'aaaaa1', squawk: '7700', label: 'emergency',
    flight: 'DAL123', alt_ft: 3000, dist_nm: 4, dir: 'SW' }, 'U'.repeat(43));
  const text = JSON.stringify(n).toLowerCase();
  for (const w of ['"lat"', '"lon"', 'latitude', 'longitude']) assert.ok(!text.includes(w));
  assert.equal(n.urgent, true);
  assert.equal(n.payload.aps.alert.title, 'Emergency · squawk 7700');
  assert.equal(n.payload.aps['interruption-level'], 'time-sensitive');
});

test('phones get only the kinds they asked for; emergencies are never rate-limited', async () => {
  const { e, a } = await pushEnv();
  const u = await newUnit();
  clock += 1000;
  await pairedPhone(e, u, { kinds: ['emergency'], env: 'production' });
  clock += 1;
  await postEvents(e, u, [evt({ kind: 'helicopter' }), evt({ kind: 'emergency', hex: 'aaaaa1', squawk: '7700' })]);
  assert.equal(a.sent.length, 1);
  assert.ok(a.sent[0].url.startsWith('https://api.push.apple.com/'), 'an App Store build uses production');
  assert.equal(a.sent[0].headers['apns-priority'], '10');

  const { e: e2, a: a2 } = await pushEnv();
  const u2 = await newUnit();
  clock += 1000;
  await pairedPhone(e2, u2);
  for (let i = 0; i < PUSHES_PER_HOUR + 5; i++) {
    clock += 5;
    await postEvents(e2, u2, [evt({ kind: 'low_overhead', hex: (0x100000 + i).toString(16) })]);
  }
  assert.equal(a2.sent.length, PUSHES_PER_HOUR, 'ordinary alerts are capped per phone per hour');
  clock += 5;
  await postEvents(e2, u2, [evt({ kind: 'emergency', hex: 'aaaaa2' })]);
  assert.equal(a2.sent.length, PUSHES_PER_HOUR + 1, 'an emergency still goes through');
});

test('a token Apple says is dead is forgotten', async () => {
  const { e, a } = await pushEnv([[410, 'Unregistered']]);
  const u = await newUnit();
  clock += 1000;
  const phone = await pairedPhone(e, u);
  clock += 1;
  await postEvents(e, u, [evt()]);
  clock += 5;
  await postEvents(e, u, [evt({ hex: 'abc124' })]);
  assert.equal(a.sent.length, 1, 'nothing more is sent to a dead token');
  assert.equal(e.DB.raw.prepare('SELECT token FROM phones WHERE id = ?').get(phone.id).token, null);
});

test('registering needs a pairing, a real token and known kinds', async () => {
  const { e } = await pushEnv();
  const stranger = await newUnit();
  clock += 1000;
  assert.equal((await register(e, stranger, { token: TOKEN, env: 'sandbox' })).status, 403);
  const u = await newUnit();
  const phone = await pairedPhone(e, u);
  clock += 1;
  assert.equal((await register(e, phone, { token: 'xyz', env: 'sandbox' })).status, 400);
  clock += 1;
  assert.equal((await register(e, phone, { token: TOKEN, env: 'staging' })).status, 400);
  clock += 1;
  assert.equal((await register(e, phone, { token: TOKEN, env: 'sandbox', kinds: ['fireworks'] })).status, 400);
});

test('a phone can ask for a test notification', async () => {
  const { e, a } = await pushEnv();
  const u = await newUnit();
  clock += 1000;
  const phone = await pairedPhone(e, u);
  clock += 1;
  const r = await worker.fetch(await signed(phone, '{}', { path: '/v1/phone/test', as: 'X-FR-Phone' }), e);
  assert.equal(r.status, 200);
  assert.equal(a.sent.at(-1).body.aps.alert.title, 'Radome test');

  const unset = env();
  const p2 = await newUnit();
  clock += 1;
  assert.equal((await worker.fetch(await signed(p2, '{}', { path: '/v1/phone/test', as: 'X-FR-Phone' }), unset)).status, 503,
    'says plainly when push is not set up');
});

test('a burst of alerts stays within Cloudflare limits: a few pushes, then one summary', async () => {
  const { e, a } = await pushEnv();
  const u = await newUnit();
  clock += 1000;
  await pairedPhone(e, u);
  await pairedPhone(e, u);
  clock += 1;
  const burst = Array.from({ length: 8 }, (_, i) => evt({ kind: 'low_overhead', hex: (0x200000 + i).toString(16) }));
  burst.push(evt({ kind: 'emergency', hex: 'aaaaa9', squawk: '7700' }));
  await postEvents(e, u, burst);
  assert.equal(a.sent.length, 2 * (PUSHES_PER_BATCH + 1), 'per phone: PUSHES_PER_BATCH alerts and one summary');
  const first = a.sent[0].body.aps.alert.title;
  assert.ok(first.startsWith('Emergency'), 'the emergency goes first, not crowded out');
  assert.equal(a.sent[PUSHES_PER_BATCH].body.aps.alert.body, `${9 - PUSHES_PER_BATCH} more alerts from this radar`);
});

test('emergencies pass the ordinary cap, but not the hard one', async () => {
  const { e, a } = await pushEnv();
  const u = await newUnit();
  clock += 1000;
  await pairedPhone(e, u, { kinds: ['emergency'] });
  for (let i = 0; i < PUSHES_PER_HOUR_HARD + 5; i++) {
    clock += 5;
    await postEvents(e, u, [evt({ kind: 'emergency', hex: (0x300000 + i).toString(16) })]);
  }
  assert.equal(a.sent.length, PUSHES_PER_HOUR_HARD);
});

test('expired pairing codes never block new ones', async () => {
  const e = env(), u = await newUnit();
  const ins = e.DB.raw.prepare('INSERT INTO pairing_offers (unit, secret_hash, expires) VALUES (?, ?, ?)');
  clock += 1000;
  for (let i = 0; i < MAX_UNITS; i++) ins.run('old' + i, '0'.repeat(64), clock - 1);
  assert.equal((await offer(e, u, SECRET)).status, 200);
  assert.equal(e.DB.raw.prepare('SELECT COUNT(*) AS n FROM pairing_offers').get().n, 1);
});

test('a phone paired with nothing is forgotten, token and all', async () => {
  const { e } = await pushEnv();
  const u = await newUnit();
  clock += 1000;
  const phone = await pairedPhone(e, u);
  clock += 1;
  await worker.fetch(await signed(phone, JSON.stringify({ unit: u.id }), { path: '/v1/phone/unpair', as: 'X-FR-Phone' }), e);
  assert.equal(e.DB.raw.prepare('SELECT COUNT(*) AS n FROM phones').get().n, 0);
  const again = await pairedPhone(e, u);
  clock += 1;
  await worker.fetch(await signed(u, JSON.stringify({ all: true }), { path: '/v1/unit/unpair' }), e);
  assert.equal(e.DB.raw.prepare('SELECT COUNT(*) AS n FROM phones WHERE id = ?').get(again.id).n, 0,
    'the unit unpairing everyone forgets them too');
});
