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

async function signed(unit, body, { ts = clock, path = '/v1/heartbeat', tamper = null } = {}) {
  const bytes = new TextEncoder().encode(body);
  const msg = signedMessage(ts, 'POST', path, await sha256Hex(bytes));
  const sig = new Uint8Array(await crypto.subtle.sign({ name: 'Ed25519' }, unit.key, new TextEncoder().encode(msg)));
  return new Request(BASE + path, {
    method: 'POST',
    headers: { 'X-FR-Unit': unit.id, 'X-FR-Time': String(ts), 'X-FR-Sig': b64url(sig), 'Content-Type': 'application/json' },
    body: tamper ?? body,
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

test('signed events are stored, whitelisted, with no need for health reports', async () => {
  const e = env(), u = await newUnit();
  clock += 1000;
  const r = await postEvents(e, u, [evt(), evt({ kind: 'emergency', hex: 'aaaaa1', squawk: '7700', label: 'emergency', extra: 'x' })]);
  assert.equal(r.status, 200);
  assert.deepEqual(await r.json(), { ok: true, stored: 2 });
  const rows = stored(e, u);
  assert.deepEqual(rows.map(x => x.kind), ['helicopter', 'emergency']);
  const em = JSON.parse(rows[1].payload);
  assert.equal(em.squawk, '7700');
  assert.equal(em.extra, undefined, 'unknown fields are dropped');
  assert.equal(await e.DB.prepare('SELECT * FROM units').first(), null, 'events do not register a health-report unit');
});

test('an event carrying a location is refused, and nothing is stored', async () => {
  const e = env(), u = await newUnit();
  clock += 1000;
  assert.equal((await postEvents(e, u, [evt({ lat: 35.8, lon: -78.7 })])).status, 400);
  assert.equal((await postEvents(e, u, [evt({ where: { latitude: 1 } })], { ts: clock + 1 })).status, 400);
  assert.equal(stored(e, u).length, 0);
});

test('bad events are refused whole', async () => {
  const e = env(), u = await newUnit();
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
  clock += 1000;
  await worker.fetch(await signed(u, hb()), e);
  clock += 1;
  await postEvents(e, u, [evt(), evt({ kind: 'notable', label: 'Air ambulance' })]);
  const list = await (await worker.fetch(new Request(BASE + '/fleet.json', { headers: { Authorization: basic('s3cret') } }), e)).json();
  assert.equal(list[0].events_24h, 2);
  const page = await (await worker.fetch(new Request(BASE + '/fleet', { headers: { Authorization: basic('s3cret') } }), e)).text();
  assert.ok(!page.includes('Air ambulance'), 'the fleet page shows counts, not what a unit saw');
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
