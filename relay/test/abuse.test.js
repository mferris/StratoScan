// Abuse (security review 2026-11-03): rate limits before any write (SR-04),
// self-minted keys (SR-03, SR-05), offer flooding and voiding (SR-03,
// SR-17), oversized and early bodies (SR-19), the daily cleanup (SR-22),
// and the small hardenings beside them (SR-14, SR-15, SR-20, SR-21, SR-50,
// SR-52). Every test also checks that a real unit, phone and pairing keep
// working.
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import worker from '../src/index.js';
import {
  MAX_UNITS, ACTIVE_UNIT_S, YOUNG_UNIT_S, HISTORY_YOUNG, HISTORY_PER_UNIT, MIN_INTERVAL_S,
  MAX_OFFERS_PER_NET, MAX_OPEN_OFFERS, YOUNG_PAIRING_S, YOUNG_PAIRING_URGENT_PER_HOUR, PUSHES_PER_HOUR_HARD,
  EVENT_RETENTION_S, HEARTBEAT_STORED_MAX, cleanHeartbeat,
} from '../src/limits.js';
import { RATES, resetLocalLimits, netBlock } from '../src/ratelimit.js';
import { checkedDisc, nearOf, latticeCentre } from '../src/netcache.js';
import { sha256Hex, signedMessage, b64urlDecode } from '../src/auth.js';
import { makeD1 } from './d1-sqlite.js';

const SCHEMA = fileURLToPath(new URL('../schema.sql', import.meta.url));
const MIGRATION = fileURLToPath(new URL('../migrations/2026-11-04-relay-harden.sql', import.meta.url));
const BASE = 'https://relay.example';
const b64url = bytes => Buffer.from(bytes).toString('base64url');
let clock = 1_850_000_000;
Date.now = () => clock * 1000;

beforeEach(() => resetLocalLimits());

async function newKey() {
  const kp = await crypto.subtle.generateKey({ name: 'Ed25519' }, true, ['sign', 'verify']);
  const raw = new Uint8Array(await crypto.subtle.exportKey('raw', kp.publicKey));
  return { id: b64url(raw), key: kp.privateKey };
}

async function signed(who, body, { path = '/v1/heartbeat', method = 'POST', as = 'X-FR-Unit', ip = null, ts = clock } = {}) {
  const bytes = new TextEncoder().encode(method === 'GET' ? '' : body);
  const msg = signedMessage(ts, method, path.split('?')[0], await sha256Hex(bytes));
  const sig = new Uint8Array(await crypto.subtle.sign({ name: 'Ed25519' }, who.key, new TextEncoder().encode(msg)));
  return new Request(BASE + path, {
    method,
    headers: { [as]: who.id, 'X-FR-Time': String(ts), 'X-FR-Sig': b64url(sig), 'Content-Type': 'application/json',
               ...(ip ? { 'CF-Connecting-IP': ip } : {}) },
    ...(method === 'GET' ? {} : { body }),
  });
}

const env = (extra = {}) => ({ DB: makeD1(SCHEMA), ...extra });
const count = (e, sql, ...a) => e.DB.raw.prepare(sql).get(...a).n;
const hb = (o = {}) => JSON.stringify({ version: '2026.11.04.1', uptime_s: 3600, ...o });
const heartbeat = async (e, u, opts) => worker.fetch(await signed(u, hb(), opts), e);
const secretHash = s => sha256Hex(new TextEncoder().encode(s));
const CODE = 'abuse-test-pairing-code-0001'; // notsecret: a stand-in for the code on a unit's screen
const offer = async (e, u, opts = {}) => worker.fetch(await signed(u, JSON.stringify({ secret_hash: await secretHash(opts.code || CODE) }),
  { path: '/v1/unit/pairing', ...opts }), e);
const pair = async (e, phone, u, secret = CODE, opts = {}) => worker.fetch(await signed(phone,
  JSON.stringify({ unit: u.id, secret, name: 'Test iPhone' }), { path: '/v1/pair', as: 'X-FR-Phone', ...opts }), e);
const ip4 = (i, net = 7) => `198.51.${net}.${i % 250 + 1}`;
const spread = i => `203.${Math.floor(i / 250) % 250}.${i % 250}.9`;   // a different /24 for each i

// ---- SR-04: rate limits before any write ----------------------------------------

test('one address is limited before anything is written, and gets back in after a minute', async () => {
  const e = env();
  const unit = await newKey();
  // A fresh key each time: only the address is in common.
  const leave = async ip => worker.fetch(await signed(await newKey(), JSON.stringify({ unit: unit.id }),
    { path: '/v1/phone/unpair', as: 'X-FR-Phone', ip }), e);
  for (let i = 0; i < RATES.strict.limit; i++) assert.equal((await leave('198.51.100.7')).status, 200);
  const before = count(e, 'SELECT COUNT(*) AS n FROM replay_guard');
  const r = await leave('198.51.100.7');
  assert.equal(r.status, 429);
  assert.equal(r.headers.get('Retry-After'), '60');
  assert.equal(count(e, 'SELECT COUNT(*) AS n FROM replay_guard'), before, 'refused before its replay record was written');
  assert.equal((await leave('198.51.100.8')).status, 200, 'another address is not affected');
  clock += 61;
  assert.equal((await leave('198.51.100.7')).status, 200, 'a minute later it may again');
});

test('one signing key is limited after its signature, before its replay record', async () => {
  const e = env();
  const phone = await newKey();
  const unit = await newKey();
  const body = n => JSON.stringify({ unit: unit.id, blob: null, n });
  for (let i = 0; i < RATES.key.limit; i++) {
    clock += 1;
    await worker.fetch(await signed(phone, body(i), { path: '/v1/phone/location', as: 'X-FR-Phone', ip: spread(i) }), e);
  }
  const before = count(e, 'SELECT COUNT(*) AS n FROM replay_guard');
  clock += 1;
  const r = await worker.fetch(await signed(phone, body('x'), { path: '/v1/phone/location', as: 'X-FR-Phone', ip: spread(999) }), e);
  assert.equal(r.status, 429);
  assert.equal(count(e, 'SELECT COUNT(*) AS n FROM replay_guard'), before);
});

test('naming someone else\'s key without its signature uses none of its allowance', async () => {
  const e = env();
  const victim = await newKey(), forger = await newKey();
  for (let i = 0; i < RATES.key.limit * 2; i++) {
    clock += 1;
    const req = await signed(forger, JSON.stringify({ secret_hash: '0'.repeat(64) }), { path: '/v1/unit/pairing', ip: spread(i) });
    req.headers.set('X-FR-Unit', victim.id);
    assert.equal((await worker.fetch(req, e)).status, 401);
  }
  clock += 1;
  assert.equal((await offer(e, victim, { ip: spread(5000) })).status, 200);
});

test('the route\'s own checks come before the replay record', async () => {
  const e = env();
  const u = await newKey();
  clock += 1;
  const bad = await worker.fetch(await signed(u, JSON.stringify({ secret_hash: 'nope' }), { path: '/v1/unit/pairing' }), e);
  assert.equal(bad.status, 400);
  const phone = await newKey();
  for (const p of [{ unit: 'x' }, { unit: u.id, secret: 'short' }]) {
    clock += 1;
    assert.equal((await worker.fetch(await signed(phone, JSON.stringify(p), { path: '/v1/pair', as: 'X-FR-Phone' }), e)).status, 400);
  }
  assert.equal(count(e, 'SELECT COUNT(*) AS n FROM replay_guard'), 0, 'nothing written for requests that were never going to do anything');
});

test('every request counts per address, /health included', async () => {
  const e = env();
  let last;
  for (let i = 0; i <= RATES.ip.limit; i++) {
    last = await worker.fetch(new Request(BASE + '/health', { headers: { 'CF-Connecting-IP': '2001:db8::1' } }), e);
  }
  assert.equal(last.status, 429);
  assert.equal((await worker.fetch(new Request(BASE + '/health', { headers: { 'CF-Connecting-IP': '2001:db8::2' } }), e)).status, 200);
});

test('fleet page passwords are tried a limited number of times a minute per address (SR-18)', async () => {
  const e = env({ FLEET_TOKEN: 'a-long-random-fleet-password' });
  const tryPw = pw => worker.fetch(new Request(BASE + '/fleet', {
    headers: { Authorization: 'Basic ' + btoa('m:' + pw), 'CF-Connecting-IP': '198.51.100.20' } }), e);
  for (let i = 0; i < RATES.strict.limit; i++) assert.equal((await tryPw('guess' + i)).status, 401);
  assert.equal((await tryPw('a-long-random-fleet-password')).status, 429, 'even the right one, until the minute is up');
  clock += 61;
  assert.equal((await tryPw('a-long-random-fleet-password')).status, 200);
});

test('a Workers Rate Limiting binding is used when configured, and a failing one falls back', async () => {
  const keys = [];
  const binding = ok => ({ limit: async ({ key }) => { keys.push(key); return { success: ok }; } });
  const e = env({ RL_IP: binding(true), RL_STRICT: binding(true), RL_KEY: binding(false) });
  const u = await newKey();
  clock += 1;
  const r = await offer(e, u, { ip: '198.51.100.30' });
  assert.equal(r.status, 429, 'the binding said no');
  assert.deepEqual(keys, ['ip:198.51.100.30', 'strict:198.51.100.30', `key:${u.id}`]);
  const broken = { limit: async () => { throw new Error('binding down'); } };
  const e2 = env({ RL_IP: broken, RL_STRICT: broken, RL_KEY: broken });
  clock += 1;
  assert.equal((await offer(e2, u, { ip: '198.51.100.31' })).status, 200, 'counted in memory instead');
});

// ---- SR-03 / SR-05: minted keys ---------------------------------------------------

test('500 minted keys: one address gets nowhere, 500 addresses fill the fleet only for a month', async () => {
  const e = env({ NET_CACHE: { match: async () => undefined, put: async () => {}, delete: async () => true } });
  const real = await newKey();
  clock += 1000;
  assert.equal((await heartbeat(e, real)).status, 200);
  e.DB.raw.prepare('UPDATE units SET first_seen = first_seen - ?, reports = 40 WHERE id = ?').run(30 * 86400, real.id);

  // From one address: the per-address limit stops it long before the fleet fills.
  let through = 0;
  for (let i = 0; i < 500; i++) {
    if ((await heartbeat(e, await newKey(), { ip: '198.51.100.66' })).status === 200) through++;
  }
  assert.equal(through, RATES.strict.limit);

  // From 500 addresses: the fleet fills...
  const minted = [];
  for (let i = 0; minted.length + through + 1 < MAX_UNITS; i++) {
    const k = await newKey();
    assert.equal((await heartbeat(e, k, { ip: spread(i) })).status, 200);
    minted.push(k);
  }
  assert.equal((await heartbeat(e, await newKey(), { ip: spread(9000) })).status, 503, 'the fleet is full');
  // ...but every report kept is small, a young key keeps only a few, and the
  // real unit carries on.
  assert.ok(e.DB.raw.prepare('SELECT MAX(LENGTH(payload)) AS n FROM heartbeats').get().n < 400);
  clock += MIN_INTERVAL_S;
  assert.equal((await heartbeat(e, real, { ip: '192.168.1.23' })).status, 200, 'a real unit keeps reporting');
  // A minted key can't use the shared cache.
  const routes = await worker.fetch(await signed(minted[0], JSON.stringify({ planes: [] }), { path: '/v1/net/routes', ip: spread(1) }), e);
  assert.equal(routes.status, 403);

  // A month of silence later they hold no places, and the cleanup forgets them.
  clock += ACTIVE_UNIT_S;
  assert.equal((await heartbeat(e, real, { ip: '192.168.1.23' })).status, 200);
  const newcomer = await newKey();
  assert.equal((await heartbeat(e, newcomer, { ip: spread(9001) })).status, 200, 'a genuine new radar gets in');
  await worker.scheduled({}, e, { waitUntil() {} });
  assert.equal(count(e, 'SELECT COUNT(*) AS n FROM units'), 2);
  assert.equal(count(e, 'SELECT COUNT(*) AS n FROM heartbeats WHERE unit NOT IN (?, ?)', real.id, newcomer.id), 0);
});

test('a stored report is the whitelisted copy, and a young unit keeps only a few', async () => {
  const e = env();
  const u = await newKey();
  clock += 1000;
  const fat = hb({ junk: 'x'.repeat(6000), thermal: { temp_c: 51.2, throttled: '0x0', extra: 'y'.repeat(500) },
                   visits: [null, { date: '2026-11-03', views: 4, unique: 2, note: '<b>' }], os: { pending: 0, kernel: '6.18.50' } });
  assert.equal((await worker.fetch(await signed(u, fat), e)).status, 200);
  const row = e.DB.raw.prepare('SELECT payload FROM units WHERE id = ?').get(u.id);
  const p = JSON.parse(row.payload);
  assert.ok(row.payload.length < HEARTBEAT_STORED_MAX);
  assert.equal(p.junk, undefined);
  assert.deepEqual(p.thermal, { temp_c: 51.2, throttled: '0x0' });
  assert.deepEqual(p.visits, [{ date: '2026-11-03', views: 4, unique: 2 }], 'holes and unknown fields dropped (SR-20)');
  assert.deepEqual(p.os, { pending: 0, kernel: '6.18.50' });
  for (let i = 0; i < 6; i++) {
    clock += MIN_INTERVAL_S;
    assert.equal((await worker.fetch(await signed(u, hb()), e)).status, 200);
  }
  assert.equal(count(e, 'SELECT COUNT(*) AS n FROM heartbeats WHERE unit = ?', u.id), HISTORY_YOUNG);
  assert.equal(e.DB.raw.prepare('SELECT reports FROM units WHERE id = ?').get(u.id).reports, 7);
  clock += YOUNG_UNIT_S;
  for (let i = 0; i < 5; i++) {
    clock += MIN_INTERVAL_S;
    await worker.fetch(await signed(u, hb()), e);
  }
  assert.equal(count(e, 'SELECT COUNT(*) AS n FROM heartbeats WHERE unit = ?', u.id), HISTORY_YOUNG + 5,
    'a week on, it keeps a month\'s');
  assert.ok(HISTORY_PER_UNIT > HISTORY_YOUNG + 5);
});

test('cleanHeartbeat keeps what the fleet pages read from a real report', () => {
  const real = {
    v: 1, version: '2026.10.30.1', serial: 2026103001, uptime_s: 86400,
    ota: { state: 'checked', held: 'ring 1 waits for ring 0 (soak)' },
    receiver: { age_s: 1, aircraft: 41, messages_per_min: 9000, signal_db: -12.3, noise_db: -30.1, restarts: 0 },
    display: { painted_age_s: 2 }, storage: { device: 'mmcblk0', gb_per_day: 0.81, rate_window_h: 6, lifetime_gb: 412.5, free_pct: 71.2 },
    rtc: { fitted: true, battery_mv: 3010, charging: false }, thermal: { temp_c: 55.1, throttled: '0x50000' },
    power: { undervoltage_24h: 0 }, ring: 0, memory_mb: { MemTotal: 3794, MemAvailable: 2101, Shmem: 210 },
    last_watchdog_reboot_age_s: null,
    os: { last_patch_age_s: 3600, pending: 0, pending_since: null, chromium: '154.0.1', kernel: '6.18.50', restart_waiting: false, trial: false, held_update: 'ok' },
    name: 'Test radar', visits: [{ date: '2026-11-03', views: 12, unique: 5 }],
  };
  assert.deepEqual(cleanHeartbeat(real), real);
});

test('a young pairing gets only a few urgent alerts an hour; a day on, the usual allowance', async () => {
  const sent = [];
  const kp = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
  const der = Buffer.from(await crypto.subtle.exportKey('pkcs8', kp.privateKey)).toString('base64');
  const e = env({
    APNS_KEY: `-----BEGIN PRIVATE KEY-----\n${der.match(/.{1,64}/g).join('\n')}\n-----END PRIVATE KEY-----\n`, // notsecret: made for this test
    APNS_KEY_ID: 'KEYID12345', APNS_TEAM_ID: 'TEAM123456', APNS_TOPIC: 'com.example.stratoscan',
    APNS_FETCH: async url => { sent.push(url); return new Response(null, { status: 200 }); },
  });
  const unit = await newKey(), phone = await newKey();
  clock += 1000;
  await offer(e, unit);
  assert.equal((await pair(e, phone, unit)).status, 200);
  clock += 1;
  assert.equal((await worker.fetch(await signed(phone, JSON.stringify({ token: 'ab'.repeat(32), env: 'sandbox', kinds: ['emergency'] }),
    { path: '/v1/phone/register', as: 'X-FR-Phone' }), e)).status, 200);
  const emergency = async i => {
    clock += 6;
    return worker.fetch(await signed(unit, JSON.stringify({ v: 1, events: [{ kind: 'emergency', ts: clock, hex: (0x400000 + i).toString(16), squawk: '7700' }] }),
      { path: '/v1/events' }), e);
  };
  for (let i = 0; i < 20; i++) assert.equal((await emergency(i)).status, 200);
  assert.equal(sent.length, YOUNG_PAIRING_URGENT_PER_HOUR);
  clock += YOUNG_PAIRING_S;
  sent.length = 0;
  for (let i = 0; i < PUSHES_PER_HOUR_HARD + 5; i++) await emergency(100 + i);
  assert.equal(sent.length, PUSHES_PER_HOUR_HARD, 'an established pairing: emergencies up to the hard cap');
});

test('a dead token is forgotten only if it is still the one on file (SR-21)', async () => {
  let e;
  const kp = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
  const der = Buffer.from(await crypto.subtle.exportKey('pkcs8', kp.privateKey)).toString('base64');
  const fresh = 'cd'.repeat(32);
  e = env({
    APNS_KEY: `-----BEGIN PRIVATE KEY-----\n${der.match(/.{1,64}/g).join('\n')}\n-----END PRIVATE KEY-----\n`, // notsecret: made for this test
    APNS_KEY_ID: 'KEYID12345', APNS_TEAM_ID: 'TEAM123456', APNS_TOPIC: 'com.example.stratoscan',
    APNS_FETCH: async () => {
      // The phone re-registers with a new token while Apple is answering.
      e.DB.raw.prepare('UPDATE phones SET token = ?').run(fresh);
      return new Response(JSON.stringify({ reason: 'Unregistered' }), { status: 410 });
    },
  });
  const unit = await newKey(), phone = await newKey();
  clock += 1000;
  await offer(e, unit);
  await pair(e, phone, unit);
  clock += 1;
  await worker.fetch(await signed(phone, JSON.stringify({ token: 'ab'.repeat(32), env: 'sandbox' }), { path: '/v1/phone/register', as: 'X-FR-Phone' }), e);
  clock += 1;
  await worker.fetch(await signed(unit, JSON.stringify({ v: 1, events: [{ kind: 'test', ts: clock }] }), { path: '/v1/events' }), e);
  assert.equal(e.DB.raw.prepare('SELECT token FROM phones').get().token, fresh);
});

// ---- SR-03 / SR-17: pairing offers ------------------------------------------------

test('offer flooding: a few per network, the newest 500 in all, and real radars still pair', async () => {
  const e = env();
  clock += 1000;
  let open = 0;
  for (let i = 0; i < 20; i++) {
    clock += 1;
    const r = await offer(e, await newKey(), { ip: ip4(i) });
    if (r.status === 200) open++; else assert.equal(r.status, 429);
  }
  assert.equal(open, MAX_OFFERS_PER_NET, 'one /24 holds only a few open codes');
  // The same for an IPv6 /48, whatever the rest of the address.
  open = 0;
  for (let i = 0; i < 12; i++) {
    clock += 1;
    if ((await offer(e, await newKey(), { ip: `2001:db8:42:${i.toString(16)}::${i + 1}` })).status === 200) open++;
  }
  assert.equal(open, MAX_OFFERS_PER_NET);

  // Many networks: the table keeps the newest MAX_OPEN_OFFERS, so a real
  // radar's fresh code always goes in, and the flood pushes out its own.
  for (let i = 0; i < MAX_OPEN_OFFERS + 50; i++) {
    resetLocalLimits();
    assert.equal((await offer(e, await newKey(), { ip: spread(i), code: `flood-code-${i}-xxxxxxxx` })).status, 200);
  }
  assert.equal(count(e, 'SELECT COUNT(*) AS n FROM pairing_offers'), MAX_OPEN_OFFERS);
  const unit = await newKey(), phone = await newKey();
  clock += 1;
  assert.equal((await offer(e, unit, { ip: '192.168.1.23' })).status, 200);
  assert.equal(count(e, 'SELECT COUNT(*) AS n FROM pairing_offers'), MAX_OPEN_OFFERS);
  clock += 1;
  assert.equal((await pair(e, phone, unit)).status, 200, 'and its phone pairs');
  // No address is kept, only a short fingerprint of the network block.
  const nets = e.DB.raw.prepare('SELECT DISTINCT net FROM pairing_offers').all().map(r => r.net);
  assert.ok(nets.every(n => n === null || /^[0-9a-f]{16}$/.test(n)));
});

test('a stranger cannot void a radar\'s open code with wrong guesses (SR-17)', async () => {
  const e = env();
  const unit = await newKey(), owner = await newKey();
  clock += 1000;
  assert.equal((await offer(e, unit)).status, 200);
  for (let i = 0; i < 50; i++) {
    clock += 1;
    const r = await pair(e, await newKey(), unit, `wrong-guess-${i}-0123456789`, { ip: spread(i) });
    assert.equal(r.status, 404);
  }
  assert.equal(count(e, 'SELECT COUNT(*) AS n FROM pairing_offers'), 1, 'the code is still open');
  assert.equal(e.DB.raw.prepare('SELECT attempts FROM pairing_offers').get().attempts, 0, 'and guesses wrote nothing');
  clock += 1;
  assert.equal((await pair(e, owner, unit)).status, 200, 'the owner\'s phone pairs');
});

// ---- SR-19: bodies --------------------------------------------------------------

function streamOf(bytes, chunk = 1024) {
  let at = 0, pulled = 0;
  const s = new ReadableStream({
    pull(c) {
      pulled++;
      if (at >= bytes.length) { c.close(); return; }
      c.enqueue(bytes.slice(at, at + chunk));
      at += chunk;
    },
  }, { highWaterMark: 0 });
  s.pulled = () => pulled;
  return s;
}

test('an oversized body is refused however it is sent, and read no further than the limit', async () => {
  const e = env();
  const u = await newKey();
  clock += 1000;
  const big = new TextEncoder().encode(JSON.stringify({ pad: 'x'.repeat(100_000) }));
  const signedReq = await signed(u, '{}', { path: '/v1/unit/pairing' });
  const body = streamOf(big);
  const chunked = new Request(BASE + '/v1/unit/pairing', { method: 'POST', headers: signedReq.headers, body, duplex: 'half' });
  assert.equal(chunked.headers.get('Content-Length'), null);
  assert.equal((await worker.fetch(chunked, e)).status, 413);
  assert.ok(body.pulled() < 20, `read ${body.pulled()} chunks of a 100 KB body before refusing`);

  const said = new Request(BASE + '/v1/heartbeat', { method: 'POST', headers: { ...Object.fromEntries(signedReq.headers), 'Content-Length': '999999' }, body: '{}' });
  assert.equal((await worker.fetch(said, e)).status, 413);
});

test('a disc handed up is read no further than its limit', async () => {
  const e = env({ NET_CACHE: { match: async () => undefined, put: async () => {}, delete: async () => true } });
  const u = await newKey();
  clock += 1000;
  const c = latticeCentre(35.8776, -78.7875);
  const path = `/v1/net/disc/${c.lat}/${c.lon}`;
  const head = await signed(u, '{}', { path, method: 'PUT' });
  const body = streamOf(new Uint8Array(4 * 1024 * 1024).fill(32), 64 * 1024);
  const r = await worker.fetch(new Request(BASE + path, { method: 'PUT', headers: head.headers, body, duplex: 'half' }), e);
  assert.equal(r.status, 413);
  assert.ok(body.pulled() <= 50 + 2);
});

test('signing headers that can never verify are refused before the body is read', async () => {
  const e = env();
  for (const [path, method] of [['/v1/heartbeat', 'POST'], ['/v1/events', 'POST'], ['/v1/unit/pairing', 'POST'], ['/v1/net/routes', 'POST']]) {
    const body = streamOf(new Uint8Array(4096));
    const bad = new Request(BASE + path, { method, body, duplex: 'half',
      headers: { 'X-FR-Unit': 'not-a-key', 'X-FR-Time': String(clock), 'X-FR-Sig': 'x' } });
    assert.equal((await worker.fetch(bad, e)).status, 401, path);
    assert.equal(body.pulled(), 0, `${path}: nothing read`);
    const stale = new Request(BASE + path, { method, body: streamOf(new Uint8Array(10)), duplex: 'half',
      headers: { 'X-FR-Unit': 'A'.repeat(43), 'X-FR-Time': String(clock - 3600), 'X-FR-Sig': 'A'.repeat(86) } });
    assert.equal((await worker.fetch(stale, e)).status, 401, `${path}: stale`);
  }
});

// ---- SR-22: the daily cleanup ----------------------------------------------------

test('the daily cleanup keeps every promise and every real radar', async () => {
  const e = env();
  const db = e.DB.raw, now = clock += 1000;
  const old = now - ACTIVE_UNIT_S - 1;
  const ins = db.prepare('INSERT INTO units (id, first_seen, last_seen, last_ts, name, reports) VALUES (?, ?, ?, 0, ?, 1)');
  ins.run('minted', old, old, null);
  ins.run('named', old, old, 'Test radar');
  ins.run('in-fleet', old, old, null);
  ins.run('paired', old, old, null);
  ins.run('recent', now - 86400, now - 3600, null);
  db.prepare("INSERT INTO fleet_members (unit, fleet, joined) VALUES ('in-fleet', 'f', 0)").run();
  db.prepare("INSERT INTO pairings (unit, phone, name, created) VALUES ('paired', 'phone-a', NULL, 0)").run();
  for (const u of ['minted', 'named', 'recent']) {
    db.prepare('INSERT INTO heartbeats (unit, ts, payload) VALUES (?, ?, ?)').run(u, now - 3600, '{}');
    db.prepare('INSERT INTO heartbeats (unit, ts, payload) VALUES (?, ?, ?)').run(u, old, '{}');
  }
  db.prepare("INSERT INTO events (unit, ts, received, kind, payload) VALUES ('silent', 0, ?, 'test', '{}')").run(now - EVENT_RETENTION_S - 1);
  db.prepare("INSERT INTO events (unit, ts, received, kind, payload) VALUES ('paired', 0, ?, 'test', '{}')").run(now - 60);
  db.prepare('INSERT INTO replay_guard (sig, expires) VALUES (?, ?), (?, ?)').run('old', now - 1, 'fresh', now + 100);
  db.prepare('INSERT INTO pairing_offers (unit, secret_hash, expires) VALUES (?, ?, ?), (?, ?, ?)').run('a', '0'.repeat(64), now - 1, 'b', '0'.repeat(64), now + 100);
  db.prepare('INSERT INTO event_senders (unit, last_ts, window_start, window_count) VALUES (?, ?, 0, 0), (?, ?, 0, 0)').run('gone', old, 'paired', now - 60);
  db.prepare("INSERT INTO phones (id, token, env, kinds, updated) VALUES ('phone-a', 't', 'sandbox', '[]', 0), ('phone-b', 't', 'sandbox', '[]', 0)").run();
  db.prepare("INSERT INTO phone_locations (phone, unit, blob, updated) VALUES ('phone-a', 'paired', 'x', ?)").run(now - 7 * 3600);
  db.prepare("INSERT INTO live_activities (phone, unit, hex, token, created) VALUES ('phone-a', 'paired', 'abc123', 't', ?)").run(now - 7200);
  db.prepare("INSERT INTO unit_box_keys (unit, key, sig, updated) VALUES ('paired', 'k', 's', 0)").run();

  await worker.scheduled({ cron: '17 4 * * *' }, e, { waitUntil() {} });
  const ids = t => db.prepare(`SELECT * FROM ${t}`).all();
  assert.deepEqual(ids('units').map(u => u.id).sort(), ['in-fleet', 'named', 'paired', 'recent']);
  assert.deepEqual(ids('heartbeats').map(h => `${h.unit}@${h.ts === old ? 'old' : 'new'}`).sort(), ['named@new', 'recent@new']);
  assert.deepEqual(ids('events').map(x => x.unit), ['paired']);
  assert.deepEqual(ids('replay_guard').map(x => x.sig), ['fresh']);
  assert.deepEqual(ids('pairing_offers').map(x => x.unit), ['b']);
  assert.deepEqual(ids('event_senders').map(x => x.unit), ['paired']);
  assert.deepEqual(ids('phones').map(x => x.id), ['phone-a'], 'a phone paired with nothing is forgotten');
  assert.deepEqual(ids('pairings').map(x => x.unit), ['paired'], 'pairings are never touched');
  assert.equal(ids('phone_locations').length, 0);
  assert.equal(ids('live_activities').length, 0);
  assert.equal(ids('unit_box_keys').length, 1, 'box keys are kept');
});

// ---- the cache: aged membership (SR-03), discs (SR-14), routes (SR-15), near (SR-52) ----

test('the shared cache serves a radar only after two days of reports, and its phones with it', async () => {
  const cache = new Map();
  const e = env({
    NET_CACHE: { match: async k => cache.get(String(k)), put: async (k, r) => { cache.set(String(k), r); }, delete: async k => cache.delete(String(k)) },
    NET_FETCH: async () => new Response('[]', { status: 200 }),
  });
  const u = await newKey(), phone = await newKey();
  const routes = (who, as = 'X-FR-Unit') => signed(who, JSON.stringify({ planes: [] }), { path: '/v1/net/routes', as }).then(r => worker.fetch(r, e));
  clock += 1000;
  assert.equal((await heartbeat(e, u)).status, 200);
  e.DB.raw.prepare('INSERT INTO pairings (unit, phone, name, created) VALUES (?, ?, NULL, ?)').run(u.id, phone.id, clock);
  assert.equal((await routes(u)).status, 403, 'one report is not enough');
  assert.equal((await routes(phone, 'X-FR-Phone')).status, 403, 'nor is a pairing with such a radar');
  for (let i = 0; i < 8; i++) {
    clock += 6 * 3600;
    assert.equal((await heartbeat(e, u)).status, 200);
  }
  assert.equal((await routes(u)).status, 200, 'two days of reports');
  assert.equal((await routes(phone, 'X-FR-Phone')).status, 200);
});

test('a disc handed up keeps aircraft fields only in their real form (SR-14)', () => {
  const c = latticeCentre(35.8776, -78.7875);
  const real = { ac: [{ hex: 'a1b2c3', flight: 'DAL123  ', r: 'N123AB', t: 'B738', squawk: '1200', lat: 36, lon: -79,
    alt_baro: 35000, gs: 450.2, nav_modes: ['autopilot', 'vnav'], lastPosition: { lat: 36, lon: -79, seen_pos: 3 } },
    { hex: '~2d0f11', alt_baro: 'ground', lat: 35.9, lon: -78.8 }], total: 2, now: 1 };
  const buf = new TextEncoder().encode(JSON.stringify(real));
  assert.equal(checkedDisc(buf, c), buf, 'adsb.lol\'s own answer passes through untouched');
  const evil = { ac: [
    { hex: 'a1b2c3', flight: '<script>', r: 'N123AB', t: 'Boeing 737 with a long story', squawk: '7700 MAYDAY', lat: 36, lon: -79, alt_baro: 1e300, desc: 'z'.repeat(500), ctl: 'a b' },
    { hex: 'not-hex', lat: 36, lon: -79 },
    { hex: 'c0ffee', lat: 36, lon: -79, deep: { a: { b: { c: 1 } } } },
  ], total: 3 };
  const out = JSON.parse(checkedDisc(new TextEncoder().encode(JSON.stringify(evil)), c));
  assert.deepEqual(out.ac, [{ hex: 'a1b2c3', r: 'N123AB', lat: 36, lon: -79 }, { hex: 'c0ffee', lat: 36, lon: -79 }]);
  assert.equal(out.total, 2);
  assert.equal(checkedDisc(new TextEncoder().encode('{"ac":[{"hex":"a1b2c3","lat":-30,"lon":100}]}'), c), null, 'still: positions outside the disc');
});

test('a false position marks a route "unconfirmed" only for its own cell (SR-15)', async () => {
  const cache = new Map(), asked = [];
  const e = env({
    NET_CACHE: {
      match: async k => { const b = cache.get(String(k)); return b === undefined ? undefined : new Response(b); },
      put: async (k, r) => { cache.set(String(k), await r.text()); }, delete: async k => cache.delete(String(k)),
    },
    NET_FETCH: async (url, init) => {
      const planes = JSON.parse(init.body).planes;
      asked.push(planes);
      return new Response(JSON.stringify(planes.map(p => ({ callsign: p.callsign, plausible: p.lat > 30,
        _airports: [{ location: 'Raleigh' }, { location: 'Atlanta' }] }))), { status: 200 });
    },
  });
  const liar = await newKey(), honest = await newKey();
  clock += 1000;
  for (const u of [liar, honest]) {
    assert.equal((await heartbeat(e, u)).status, 200);
    e.DB.raw.prepare('UPDATE units SET first_seen = first_seen - ?, reports = 12 WHERE id = ?').run(3 * 86400, u.id);
  }
  const ask = async (u, lat, lng) => (await (await worker.fetch(await signed(u, JSON.stringify({ planes: [{ callsign: 'DAL2164', lat, lng }] }),
    { path: '/v1/net/routes' }), e)).json())[0];
  assert.equal((await ask(liar, -10, 50)).plausible, false);
  assert.equal((await ask(honest, 35.9, -78.8)).plausible, true, 'the honest radar still sees the real verdict');
  assert.equal(asked.length, 2);
});

test('a phone\'s view is a multiple of 0.05 degrees (SR-52)', () => {
  assert.deepEqual(nearOf('35.85,-78.80,40'), { lat: 35.85, lon: -78.8, nm: 40 });
  assert.deepEqual(nearOf('36,-79,40'), { lat: 36, lon: -79, nm: 40 });
  assert.equal(nearOf('35.87,-78.80,40'), false);
  assert.equal(nearOf('35.85,-78.79,40'), false);
});

// ---- SR-50: one spelling per signature and id ------------------------------------

test('a signature or id spelled any way but the canonical one is refused', async () => {
  const e = env();
  const u = await newKey();
  clock += 1000;
  const req = await signed(u, hb());
  const sig = req.headers.get('X-FR-Sig');
  // The last character of an 86-character signature carries 4 unused bits.
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
  const last = alphabet.indexOf(sig.at(-1));
  const twin = sig.slice(0, -1) + alphabet[last ^ 1];
  assert.equal(b64urlDecode(twin), null);
  const forged = new Request(req.url, { method: 'POST', headers: { ...Object.fromEntries(req.headers), 'X-FR-Sig': twin }, body: hb() });
  assert.equal((await worker.fetch(forged, e)).status, 401);
  const idLast = alphabet.indexOf(u.id.at(-1));
  assert.equal(b64urlDecode(u.id.slice(0, -1) + alphabet[idLast ^ 1]), null);
  assert.equal((await worker.fetch(req, e)).status, 200, 'the canonical one is fine');
});

// ---- addresses ------------------------------------------------------------------

test('network blocks: /24 for IPv4, /48 for IPv6', () => {
  assert.equal(netBlock('192.168.1.23'), '192.168.1.0/24');
  assert.equal(netBlock('2001:db8:42:1::5'), '2001:db8:42::/48');
  assert.equal(netBlock('2001:0db8:0042:ffff:1:2:3:4'), '2001:db8:42::/48');
  assert.equal(netBlock('2001:db8::1'), '2001:db8:0::/48');
  assert.equal(netBlock('::1'), '0:0:0::/48');
  assert.equal(netBlock('999.1.1.1'), null);
  assert.equal(netBlock('nonsense'), null);
  assert.equal(netBlock(null), null);
});

// ---- the migration --------------------------------------------------------------

test('the migration adds what the new code needs to a live database, losing nothing', () => {
  const db = new DatabaseSync(':memory:');
  // The two tables it changes, as the live database has them.
  db.exec(`CREATE TABLE units (id TEXT PRIMARY KEY, name TEXT, first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL,
             last_ts INTEGER NOT NULL, version TEXT, payload TEXT);
           CREATE TABLE heartbeats (unit TEXT NOT NULL, ts INTEGER NOT NULL, payload TEXT NOT NULL);
           CREATE TABLE pairing_offers (unit TEXT PRIMARY KEY, secret_hash TEXT NOT NULL, expires INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0);
           CREATE TABLE events (unit TEXT NOT NULL, ts INTEGER NOT NULL, received INTEGER NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);`);
  const now = Math.floor(Date.now() / 1000);
  const real = Math.floor(new Date().getTime() / 1000);   // strftime('now') is the real clock, not the test's
  db.prepare("INSERT INTO units VALUES ('rdu', 'Test radar', ?, ?, ?, '2026.10.30.1', '{}')").run(real - 60 * 86400, real, now);
  db.prepare("INSERT INTO units VALUES ('young', NULL, ?, ?, ?, NULL, '{}')").run(real - 86400, real, now);
  for (let i = 0; i < 3; i++) db.prepare("INSERT INTO heartbeats VALUES ('young', ?, '{}')").run(i);
  db.prepare("INSERT INTO pairing_offers VALUES ('rdu', ?, ?, 0)").run('0'.repeat(64), now + 600);
  db.exec(readFileSync(MIGRATION, 'utf8'));
  const units = db.prepare('SELECT id, name, reports FROM units ORDER BY id').all().map(r => ({ ...r }));
  assert.deepEqual(units, [{ id: 'rdu', name: 'Test radar', reports: 4 }, { id: 'young', name: null, reports: 3 }]);
  assert.deepEqual({ ...db.prepare('SELECT unit, net FROM pairing_offers').get() }, { unit: 'rdu', net: null });
  // And the result has every column the fresh schema has.
  const fresh = new DatabaseSync(':memory:');
  fresh.exec(readFileSync(SCHEMA, 'utf8'));
  for (const t of ['units', 'pairing_offers']) {
    const cols = d => d.prepare(`PRAGMA table_info(${t})`).all().map(c => c.name).sort();
    assert.deepEqual(cols(db), cols(fresh), t);
  }
});
