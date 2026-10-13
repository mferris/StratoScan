// Audit 2026-10-12, from Codex's scan: a signed request that changes
// something is accepted once, and a pairing code pairs one phone.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import worker from '../src/index.js';
import { sha256Hex, signedMessage } from '../src/auth.js';
import { makeD1 } from './d1-sqlite.js';

const SCHEMA = fileURLToPath(new URL('../schema.sql', import.meta.url));
const BASE = 'https://relay.example';
const b64url = bytes => Buffer.from(bytes).toString('base64url');
let clock = 1_800_000_000;
Date.now = () => clock * 1000;

async function newKey() {
  const kp = await crypto.subtle.generateKey({ name: 'Ed25519' }, true, ['sign', 'verify']);
  return { id: b64url(new Uint8Array(await crypto.subtle.exportKey('raw', kp.publicKey))), key: kp.privateKey };
}
async function signed(who, body, path, as = 'X-FR-Unit', method = 'POST') {
  const bytes = new TextEncoder().encode(method === 'GET' ? '' : body);
  const msg = signedMessage(clock, method, path, await sha256Hex(bytes));
  const sig = new Uint8Array(await crypto.subtle.sign({ name: 'Ed25519' }, who.key, new TextEncoder().encode(msg)));
  return new Request(BASE + path, {
    method, headers: { [as]: who.id, 'X-FR-Time': String(clock), 'X-FR-Sig': b64url(sig), 'Content-Type': 'application/json' },
    ...(method === 'GET' ? {} : { body }),
  });
}
const SECRET = 'correct-horse-battery-staple';
const offerBody = async () => JSON.stringify({ secret_hash: await sha256Hex(new TextEncoder().encode(SECRET)) });

test('a cancelled pairing code does not come back when its offer is sent again', async () => {
  const e = { DB: makeD1(SCHEMA) };
  const unit = await newKey(), phone = await newKey();
  const offer = await signed(unit, await offerBody(), '/v1/unit/pairing');
  const replay = offer.clone();
  assert.equal((await worker.fetch(offer, e)).status, 200, 'the radar offers a code');
  clock += 1;
  assert.equal((await worker.fetch(await signed(unit, '{}', '/v1/unit/pairing/cancel'), e)).status, 200, 'and cancels it');
  assert.equal((await worker.fetch(replay, e)).status, 409, 'the same signed offer, sent again: refused');
  assert.equal(e.DB.raw.prepare('SELECT COUNT(*) AS n FROM pairing_offers').get().n, 0, 'no offer was restored');
  const pair = await signed(phone, JSON.stringify({ unit: unit.id, secret: SECRET }), '/v1/pair', 'X-FR-Phone');
  assert.equal((await worker.fetch(pair, e)).status, 404, 'so the code pairs nothing');
});

test('any signed change is accepted once; reads may repeat', async () => {
  const e = { DB: makeD1(SCHEMA) };
  const unit = await newKey();
  const r = await signed(unit, await offerBody(), '/v1/unit/pairing');
  const copy = r.clone();
  assert.equal((await worker.fetch(r, e)).status, 200);
  const again = await worker.fetch(copy, e);
  assert.equal(again.status, 409);
  assert.match((await again.json()).error, /already used/);
  clock += 1;
  assert.equal((await worker.fetch(await signed(unit, await offerBody(), '/v1/unit/pairing'), e)).status, 200,
    'a new request (a new time, so a new signature) is fine');
  const read = await signed(unit, '', '/v1/unit/phones', 'X-FR-Unit', 'GET');
  const readAgain = read.clone();
  assert.equal((await worker.fetch(read, e)).status, 200);
  assert.equal((await worker.fetch(readAgain, e)).status, 200, 'a read changes nothing, so it may repeat');
});

test('the replay record is pruned once nothing in it could still be fresh', async () => {
  const e = { DB: makeD1(SCHEMA) };
  const unit = await newKey();
  assert.equal((await worker.fetch(await signed(unit, await offerBody(), '/v1/unit/pairing'), e)).status, 200);
  const kept = e.DB.raw.prepare('SELECT expires FROM replay_guard').get().expires;
  assert.ok(kept >= clock + 600 && kept <= clock + 700, 'kept past the five-minute freshness window, not much longer');
  const real = Math.random;
  Math.random = () => 0;     // force the occasional prune
  clock = kept + 1;
  await worker.fetch(await signed(unit, await offerBody(), '/v1/unit/pairing'), e);
  Math.random = real;
  assert.equal(e.DB.raw.prepare('SELECT COUNT(*) AS n FROM replay_guard WHERE expires < ?').get(clock).n, 0);
});

// Two phones read the offer before either has used it: the moment the old
// read-then-pair-then-delete let both through. The stand-in database holds
// the first reader until the second has read too, so the overlap happens
// every run, not by luck of scheduling.
function overlappingReads(db) {
  let waiting = null, release = null;
  return {
    ...db,
    prepare(sql) {
      const st = db.prepare(sql);
      if (!/^SELECT \* FROM pairing_offers WHERE unit = \?$/.test(sql)) return st;
      const hold = s => ({
        ...s,
        bind: (...a) => hold(s.bind(...a)),
        first: async () => {
          const row = await s.first();
          if (!waiting) { waiting = new Promise(r => { release = r; }); await waiting; }
          else release();
          return row;
        },
      });
      return hold(st);
    },
  };
}

test('one pairing code pairs one phone, even two at the same moment', async () => {
  const e = { DB: overlappingReads(makeD1(SCHEMA)) };
  const unit = await newKey(), a = await newKey(), b = await newKey();
  assert.equal((await worker.fetch(await signed(unit, await offerBody(), '/v1/unit/pairing'), e)).status, 200);
  const body = JSON.stringify({ unit: unit.id, secret: SECRET });
  const [ra, rb] = await Promise.all([
    worker.fetch(await signed(a, body, '/v1/pair', 'X-FR-Phone'), e),
    worker.fetch(await signed(b, body, '/v1/pair', 'X-FR-Phone'), e),
  ]);
  assert.deepEqual([ra.status, rb.status].sort(), [200, 404], 'one phone pairs; the other is told the code is used');
  assert.equal(e.DB.raw.prepare('SELECT COUNT(*) AS n FROM pairings WHERE unit = ?').get(unit.id).n, 1);
});
