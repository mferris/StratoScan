// Nothing the relay asks of another service waits without a time limit (#86,
// 2026-10-26). Apple's push service, adsb.im and adsbdb are each given up on
// in time; a request a person waits on is answered before their phone gives
// up; and a phone Apple is slow for never holds up another phone's alerts.
// The services are stand-ins that never answer (they give up only when the
// request's signal fires, as fetch does), and the limits are shortened so
// this runs in a couple of seconds. Real time throughout: it is what the
// limits are measured in.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import worker from '../src/index.js';
import * as apns from '../src/apns.js';
import { tune as net } from '../src/netcache.js';
import { PUSHES_PER_BATCH } from '../src/limits.js';
import { sha256Hex, signedMessage } from '../src/auth.js';
import { makeD1 } from './d1-sqlite.js';

const SCHEMA = fileURLToPath(new URL('../schema.sql', import.meta.url));
const BASE = 'https://relay.example';
const b64url = bytes => Buffer.from(bytes).toString('base64url');

// The limits as shipped, then short ones for the tests.
const SHIPPED = { ...apns.tune, ...net };
apns.tune.sendMs = 200;
apns.tune.deliveryMs = 500;
net.routesMs = 200;
net.ownerMs = 200;
net.upstreamGapMs = 0;
const LIMIT = { timeout: 5000 };   // a test that would wait for ever fails instead

// Each signed step a second after the last, as a sender's clock would be.
let ts = Math.floor(Date.now() / 1000);
const tick = () => (ts = Math.max(ts + 1, Math.floor(Date.now() / 1000)));

async function newUnit() {
  const kp = await crypto.subtle.generateKey({ name: 'Ed25519' }, true, ['sign', 'verify']);
  const raw = new Uint8Array(await crypto.subtle.exportKey('raw', kp.publicKey));
  return { id: b64url(raw), key: kp.privateKey };
}

async function signed(who, body, { path, method = 'POST', as = 'X-FR-Unit' }) {
  const t = tick();
  const bytes = new TextEncoder().encode(method === 'GET' ? '' : body);
  const msg = signedMessage(t, method, path, await sha256Hex(bytes));
  const sig = new Uint8Array(await crypto.subtle.sign({ name: 'Ed25519' }, who.key, new TextEncoder().encode(msg)));
  return new Request(BASE + path, {
    method,
    headers: { [as]: who.id, 'X-FR-Time': String(t), 'X-FR-Sig': b64url(sig), 'Content-Type': 'application/json' },
    ...(method === 'GET' ? {} : { body }),
  });
}

// Another service: `answer(url)` says how it answers each request. A number
// is a status; 'hang' never answers; 'stall' answers 500 and then never
// sends the body. Every call is recorded, with when it was made and when
// the relay gave up on it.
function service(answer) {
  const calls = [];
  const f = (url, init = {}) => {
    const call = { url: String(url), at: Date.now(), timed: !!init.signal };
    calls.push(call);
    const how = answer(call.url);
    if (typeof how === 'number') return Promise.resolve(new Response(null, { status: how }));
    // Node does not wait on a signal's timer, so something must, or the
    // test would end with the request still open.
    const keep = setTimeout(() => {}, LIMIT.timeout);
    const gaveUp = () => { call.gaveUp = Date.now(); clearTimeout(keep); };
    if (how === 'stall') {
      return Promise.resolve(new Response(new ReadableStream({
        start(c) { init.signal?.addEventListener('abort', () => { gaveUp(); c.error(init.signal.reason); }); },
      }), { status: 500 }));
    }
    return new Promise((_, reject) => {
      init.signal?.addEventListener('abort', () => { gaveUp(); reject(init.signal.reason); });
    });
  };
  f.calls = calls;
  return f;
}

async function apnsKey() {
  const kp = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
  const der = Buffer.from(await crypto.subtle.exportKey('pkcs8', kp.privateKey)).toString('base64');
  return `-----BEGIN PRIVATE KEY-----\n${der.match(/.{1,64}/g).join('\n')}\n-----END PRIVATE KEY-----\n`; // notsecret
}

const pushEnv = async apple => ({ DB: makeD1(SCHEMA), APNS_KEY: await apnsKey(), APNS_KEY_ID: 'KEYID12345',
  APNS_TEAM_ID: 'TEAM123456', APNS_TOPIC: 'com.example.stratoscan', APNS_FETCH: apple });

const TOKEN = 'ab'.repeat(32);
const LA_TOKEN = 'cd'.repeat(40);
const ACT_TOKEN = 'ef'.repeat(40);
// A stand-in for the one-time code a unit shows on its screen; real codes
// are random and never stored.
const TEST_PAIRING_CODE = 'test-pairing-code-for-unit-tests'; // notsecret

const post = async (e, who, path, body, as = 'X-FR-Unit', ctx) =>
  worker.fetch(await signed(who, JSON.stringify(body), { path, as }), e, ctx);

async function pairedPhone(e, u, { token = TOKEN, kinds, la } = {}) {
  const phone = await newUnit();
  const hash = await sha256Hex(new TextEncoder().encode(TEST_PAIRING_CODE));
  assert.equal((await post(e, u, '/v1/unit/pairing', { secret_hash: hash })).status, 200);
  assert.equal((await post(e, phone, '/v1/pair', { unit: u.id, secret: TEST_PAIRING_CODE }, 'X-FR-Phone')).status, 200);
  const r = await post(e, phone, '/v1/phone/register', { token, env: 'sandbox', kinds, la_start_token: la }, 'X-FR-Phone');
  assert.equal(r.status, 200);
  return phone;
}

const evt = (o = {}) => ({ kind: 'low_overhead', ts, hex: 'abc123', flight: 'N407XX', alt_ft: 1000, ...o });
const postEvents = (e, u, events) => post(e, u, '/v1/events', { v: 1, events });
const row = (e, phone) => e.DB.raw.prepare('SELECT token, window_count FROM phones WHERE id = ?').get(phone.id);

// The text of a call's arguments, from just inside its opening bracket.
function argsAt(src, i) {
  let depth = 1, j = i;
  for (; j < src.length && depth; j++) depth += src[j] === '(' ? 1 : src[j] === ')' ? -1 : 0;
  return src.slice(i, j - 1);
}

test('every call the relay makes to another service has a time limit', () => {
  const dir = fileURLToPath(new URL('../src/', import.meta.url));
  let checked = 0;
  for (const f of readdirSync(dir).filter(n => n.endsWith('.js'))) {
    const src = readFileSync(dir + f, 'utf8')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/(^|[^:'"`\\])\/\/.*$/gm, '$1');                 // comments, not URLs
    for (const m of src.matchAll(/\bfetch\w*\s*(?:\(env\)\s*)?\(/g)) {
      if (/async\s+$/.test(src.slice(0, m.index))) continue;        // the Worker's own handler
      const args = argsAt(src, m.index + m[0].length);
      if (/^\s*\.\.\.\w+\s*$/.test(args)) continue;                 // passes its caller's on
      checked++;
      assert.match(args, /signal:\s*AbortSignal\.timeout\(/, `${f}: ${m[0]}${args.slice(0, 50)}... waits without a limit`);
    }
  }
  assert.ok(checked >= 3, `found the calls to Apple, adsb.im and adsbdb (${checked})`);
});

test('the shipped limits fit inside what waits on them', () => {
  assert.ok(SHIPPED.sendMs > 0 && SHIPPED.sendMs <= 10_000, 'one push: about 10 s at most');
  assert.ok(SHIPPED.sendMs + 2000 < 15_000, 'the test button is answered before the app gives up (15 s)');
  assert.ok(SHIPPED.deliveryMs >= SHIPPED.sendMs && SHIPPED.deliveryMs <= 25_000,
    'a delivery ends inside the 30 s Cloudflare allows after the reply');
  assert.ok(SHIPPED.routesMs + SHIPPED.upstreamGapMs < 6000, 'routes: inside the app\'s 6 s');
  assert.ok(SHIPPED.ownerMs + SHIPPED.upstreamGapMs < 8000, 'owners: inside the radar\'s 8 s');
});

test('a push Apple never answers, or never finishes answering, is given up on', LIMIT, async () => {
  const e = await pushEnv();
  const note = apns.notificationFor({ kind: 'test' }, 'test');
  let t0 = Date.now();
  const r = await apns.send(e, { env: 'sandbox', token: TOKEN }, note, ts, service(() => 'hang'), 100);
  assert.deepEqual(r, { ok: false, status: 0, reason: 'timed out', dead: false });
  assert.ok(Date.now() - t0 < 1000, `gave up after ${Date.now() - t0} ms`);
  t0 = Date.now();
  const half = await apns.send(e, { env: 'sandbox', token: TOKEN }, note, ts, service(() => 'stall'), 100);
  assert.equal(half.ok, false);
  assert.equal(half.status, 500);
  assert.ok(Date.now() - t0 < 1000, 'a body that never comes is not waited on either');
});

test('the test button hears that Apple did not answer, well before the phone gives up', LIMIT, async () => {
  const e = await pushEnv(service(() => 'hang'));
  const u = await newUnit();
  const phone = await pairedPhone(e, u);
  const t0 = Date.now();
  const r = await post(e, phone, '/v1/phone/test', {}, 'X-FR-Phone');
  assert.equal(r.status, 504);
  assert.match((await r.json()).error, /did not answer in time/);
  assert.ok(Date.now() - t0 < apns.tune.sendMs + 500, `answered after ${Date.now() - t0} ms`);
  assert.equal(row(e, phone).token, TOKEN, 'a silent Apple says nothing about the token');
});

test('a phone Apple sits on does not hold up another phone\'s alerts', LIMIT, async () => {
  const slow = 'a1'.repeat(32), quick = 'b2'.repeat(32);
  const apple = service(url => (url.endsWith(slow) ? 'hang' : 200));
  const e = await pushEnv(apple);
  const u = await newUnit();
  const first = await pairedPhone(e, u, { token: slow });
  const second = await pairedPhone(e, u, { token: quick });
  const r = await postEvents(e, u, [evt({ kind: 'emergency', hex: 'aaaaa1', squawk: '7700' })]);
  assert.equal(r.status, 200);
  const s = apple.calls.find(c => c.url.endsWith(slow)), q = apple.calls.find(c => c.url.endsWith(quick));
  assert.ok(s && q && s.gaveUp, 'both phones were sent to, and the silent one given up on');
  assert.ok(q.at < s.gaveUp, 'the second phone did not wait for the first');
  assert.equal(row(e, first).window_count, 1, 'the slow phone\'s row is still written back');
  assert.equal(row(e, second).window_count, 1);
});

test('a countdown push Apple sits on does not hold back the same phone\'s emergency', LIMIT, async () => {
  const apple = service(url => (url.endsWith(LA_TOKEN) ? 'hang' : 200));
  const e = await pushEnv(apple);
  const u = await newUnit();
  const phone = await pairedPhone(e, u, { kinds: ['emergency', 'approach'], la: LA_TOKEN });
  await postEvents(e, u, [evt({ kind: 'approach', hex: 'a90002', eta_s: 120 }),
                          evt({ kind: 'emergency', hex: 'aaaaa1', squawk: '7700' })]);
  const la = apple.calls.find(c => c.url.endsWith(LA_TOKEN)), alert = apple.calls.find(c => c.url.endsWith(TOKEN));
  assert.ok(la && alert && la.gaveUp);
  assert.ok(alert.at < la.gaveUp, 'the emergency went while the countdown was still waiting');
  assert.equal(row(e, phone).window_count, 2, 'both counted against the hour');
});

test('a delivery stops at its deadline, however many pushes Apple sits on', LIMIT, async () => {
  const apple = service(() => 'hang');
  const e = await pushEnv(apple);
  const u = await newUnit();
  const phone = await pairedPhone(e, u);
  const burst = Array.from({ length: PUSHES_PER_BATCH + 2 }, (_, i) => evt({ hex: (0x200000 + i).toString(16) }));
  const t0 = Date.now();
  assert.equal((await postEvents(e, u, burst)).status, 200);
  const took = Date.now() - t0;
  // One after another, 3 alerts and a summary would take 4 x sendMs.
  assert.ok(took < (PUSHES_PER_BATCH + 1) * apns.tune.sendMs - 50, `delivery took ${took} ms`);
  assert.equal(apple.calls.length, PUSHES_PER_BATCH, 'the summary, past the deadline, was not sent');
  assert.ok(apple.calls.every(c => c.timed && c.gaveUp));
  assert.equal(row(e, phone).window_count, PUSHES_PER_BATCH, 'and not counted against the hour');
});

test('a Live Activity ended before the phone reported it: the report does not wait on Apple', LIMIT, async () => {
  const apple = service(url => (url.endsWith(ACT_TOKEN) ? 'hang' : 200));
  const e = await pushEnv(apple);
  const u = await newUnit();
  const phone = await pairedPhone(e, u, { kinds: ['approach'], la: LA_TOKEN });
  await postEvents(e, u, [evt({ kind: 'approach', hex: 'a90002', eta_s: 60 })]);
  await postEvents(e, u, [evt({ kind: 'approach_end', hex: 'a90002' })]);     // before the phone reported
  const later = [];
  const t0 = Date.now();
  const r = await post(e, phone, '/v1/phone/activity', { unit: u.id, hex: 'a90002', token: ACT_TOKEN }, 'X-FR-Phone',
    { waitUntil: p => later.push(p) });
  assert.deepEqual(await r.json(), { ok: true, ended: true });
  assert.ok(Date.now() - t0 < apns.tune.sendMs, 'answered without waiting for Apple');
  await Promise.all(later);
  const end = apple.calls.find(c => c.url.endsWith(ACT_TOKEN));
  assert.ok(end && end.gaveUp, 'the end went out after the reply, and was given up on in time');
});

test('routes and owners: a service that never answers is given up on in time', LIMIT, async () => {
  const cache = new Map();
  const NET_CACHE = {
    async match(k) { const b = cache.get(String(k)); return b === undefined ? undefined : new Response(b); },
    async put(k, res) { cache.set(String(k), await res.text()); },
    async delete(k) { return cache.delete(String(k)); },
  };
  for (const how of ['hang', 'stall']) {
    const svc = service(() => how);
    const e = { DB: makeD1(SCHEMA), NET_FETCH: svc, NET_CACHE };
    const u = await newUnit();
    assert.equal((await post(e, u, '/v1/heartbeat', { version: '2026.10.26.1', uptime_s: 60 })).status, 200);
    let t0 = Date.now();
    const routes = await post(e, u, '/v1/net/routes', { planes: [{ callsign: 'AAL1801', lat: 35.9, lng: -78.8 }] });
    assert.equal(routes.status, 502, `routes (${how})`);
    assert.ok(Date.now() - t0 < 1000, `routes (${how}) answered after ${Date.now() - t0} ms`);
    t0 = Date.now();
    const owner = await worker.fetch(await signed(u, '', { path: '/v1/net/owner/a1b2c3', method: 'GET' }), e);
    assert.equal(owner.status, 502, `owner (${how})`);
    assert.ok(Date.now() - t0 < 1000, `owner (${how}) answered after ${Date.now() - t0} ms`);
    assert.ok(svc.calls.length === 2 && svc.calls.every(c => c.timed && c.gaveUp));
    assert.equal(cache.size, 0, 'nothing is cached from a service that did not answer');
  }
});
