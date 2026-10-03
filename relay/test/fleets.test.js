// Fleets (roadmap 1.13). Run: npm test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import worker from '../src/index.js';
import { normaliseCode } from '../src/fleets.js';
import { sha256Hex, signedMessage } from '../src/auth.js';
import { makeD1 } from './d1-sqlite.js';

const SCHEMA = fileURLToPath(new URL('../schema.sql', import.meta.url));
const BASE = 'https://relay.example';
const b64url = bytes => Buffer.from(bytes).toString('base64url');
let clock = 1_900_000_000;
Date.now = () => clock * 1000;

async function newUnit() {
  const kp = await crypto.subtle.generateKey({ name: 'Ed25519' }, true, ['sign', 'verify']);
  const raw = new Uint8Array(await crypto.subtle.exportKey('raw', kp.publicKey));
  return { id: b64url(raw), key: kp.privateKey };
}

async function signed(unit, path, body = '', method = 'POST') {
  const bytes = new TextEncoder().encode(method === 'GET' ? '' : body);
  const msg = signedMessage(clock, method, path, await sha256Hex(bytes));
  const sig = new Uint8Array(await crypto.subtle.sign({ name: 'Ed25519' }, unit.key, new TextEncoder().encode(msg)));
  return new Request(BASE + path, {
    method,
    headers: { 'X-FR-Unit': unit.id, 'X-FR-Time': String(clock), 'X-FR-Sig': b64url(sig), 'Content-Type': 'application/json' },
    ...(method === 'GET' ? {} : { body }),
  });
}

const env = () => ({ DB: makeD1(SCHEMA), FLEET_TOKEN: 's3cret' });
const basic = 'Basic ' + btoa('m:s3cret');
const form = (path, fields, { origin = BASE, cookie = null, auth = true } = {}) => new Request(BASE + path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded', Origin: origin,
             ...(auth ? { Authorization: basic } : {}), ...(cookie ? { Cookie: cookie } : {}) },
  body: new URLSearchParams(fields).toString(),
});

// Creates a fleet through the maintainer's page; returns its shown-once secrets.
async function createFleet(e, name) {
  const r = await worker.fetch(form('/fleet/fleets/new', { name, label: 'test' }), e);
  assert.equal(r.status, 200);
  const html = await r.text();
  const code = /class="secret">([0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4})</.exec(html)?.[1];
  const token = /\/f\/([A-Za-z0-9_-]{43})/.exec(html)?.[1];
  assert.ok(code && token, 'both secrets are shown');
  return { code, token, html };
}

async function signIn(e, token) {
  const r = await worker.fetch(new Request(`${BASE}/f/${token}`), e);
  assert.equal(r.status, 303);
  const set = r.headers.get('Set-Cookie');
  assert.match(set, /HttpOnly/); assert.match(set, /Secure/); assert.match(set, /SameSite=Strict/);
  return set.split(';')[0];
}

const hb = obj => JSON.stringify({ version: '2026.10.03.1', uptime_s: 3600, ...obj });

test('invite codes forgive case, spaces, dashes and the usual slips', () => {
  assert.equal(normaliseCode('abcd-efgh-jkmn'), 'ABCDEFGHJKMN');
  assert.equal(normaliseCode(' ABCD EFGH JKMN '), 'ABCDEFGHJKMN');
  assert.equal(normaliseCode('0OIL-1111-2222'), '001111112222');
  assert.equal(normaliseCode('too-short'), null);
  assert.equal(normaliseCode(42), null);
});

test('only the maintainer can create a fleet, and only from the fleet page', async () => {
  const e = env();
  assert.equal((await worker.fetch(form('/fleet/fleets/new', { name: 'x' }, { auth: false }), e)).status, 401);
  assert.equal((await worker.fetch(form('/fleet/fleets/new', { name: 'x' }, { origin: 'https://evil.example' }), e)).status, 403);
  const { html } = await createFleet(e, 'Family');
  assert.match(html, /shown <b>once<\/b>/);
  const row = await e.DB.prepare('SELECT * FROM fleets').first();
  assert.equal(row.name, 'Family');
  assert.ok(!html.includes(row.invite_hash), 'the page shows the code, never its stored hash');
});

test('secrets are stored only as fingerprints', async () => {
  const e = env();
  const { code, token } = await createFleet(e, 'Family');
  const dump = JSON.stringify([
    ...(await e.DB.prepare('SELECT * FROM fleets').all()).results,
    ...(await e.DB.prepare('SELECT * FROM fleet_admins').all()).results]);
  assert.ok(!dump.includes(code) && !dump.includes(normaliseCode(code)), 'no invite code stored');
  assert.ok(!dump.includes(token), 'no administrator token stored');
});

test('a radar joins with the invite code, can check, and can leave', async () => {
  const e = env(), u = await newUnit();
  const { code } = await createFleet(e, 'Family');
  let r = await worker.fetch(await signed(u, '/v1/unit/fleet', JSON.stringify({ code: 'ABCD-EFGH-JKMN' })), e);
  assert.equal(r.status, 404, 'a wrong code joins nothing');
  r = await worker.fetch(await signed(u, '/v1/unit/fleet', JSON.stringify({ code: code.toLowerCase() })), e);
  assert.equal(r.status, 200);
  assert.deepEqual((await r.json()).fleet, { name: 'Family' });
  r = await worker.fetch(await signed(u, '/v1/unit/fleet', '', 'GET'), e);
  assert.deepEqual((await r.json()).fleet, { name: 'Family' });
  r = await worker.fetch(await signed(u, '/v1/unit/fleet/leave', '{}'), e);
  assert.equal(r.status, 200);
  r = await worker.fetch(await signed(u, '/v1/unit/fleet', '', 'GET'), e);
  assert.equal((await r.json()).fleet, null);
});

test('joining needs the radar’s own signature', async () => {
  const e = env(), u = await newUnit(), other = await newUnit();
  const { code } = await createFleet(e, 'Family');
  const forged = await signed(other, '/v1/unit/fleet', JSON.stringify({ code }));
  forged.headers.set('X-FR-Unit', u.id);
  assert.equal((await worker.fetch(forged, e)).status, 401);
});

test('an administrator sees their fleet, and only theirs', async () => {
  const e = env(), a = await newUnit(), b = await newUnit();
  const fam = await createFleet(e, 'Family');
  const club = await createFleet(e, 'Club');
  await worker.fetch(await signed(a, '/v1/unit/fleet', JSON.stringify({ code: fam.code })), e);
  await worker.fetch(await signed(b, '/v1/unit/fleet', JSON.stringify({ code: club.code })), e);
  await worker.fetch(await signed(a, '/v1/heartbeat', hb({ name: 'Mom’s radar', visits: [{ date: 'd', views: 12, unique: 5 }] })), e);
  clock += 1;
  await worker.fetch(await signed(b, '/v1/heartbeat', hb({ name: 'Clubhouse' })), e);

  const cookie = await signIn(e, fam.token);
  const html = await (await worker.fetch(new Request(BASE + '/f', { headers: { Cookie: cookie } }), e)).text();
  assert.match(html, /Mom’s radar/);
  assert.match(html, /12 views, 5 visitors/);
  assert.ok(!html.includes('Clubhouse') && !html.includes(b.id.slice(0, 10)), 'another fleet’s radar is not shown');
  assert.equal((await worker.fetch(new Request(BASE + '/f'), e)).status, 401, 'no cookie, no page');
  assert.equal((await worker.fetch(new Request(BASE + '/f/' + 'x'.repeat(43)), e)).status, 404, 'a made-up link');
});

test('an administrator can remove a radar from their fleet, not from another', async () => {
  const e = env(), a = await newUnit(), b = await newUnit();
  const fam = await createFleet(e, 'Family');
  const club = await createFleet(e, 'Club');
  await worker.fetch(await signed(a, '/v1/unit/fleet', JSON.stringify({ code: fam.code })), e);
  await worker.fetch(await signed(b, '/v1/unit/fleet', JSON.stringify({ code: club.code })), e);
  const cookie = await signIn(e, fam.token);
  assert.equal((await worker.fetch(form('/f/remove', { unit: b.id }, { cookie, auth: false }), e)).status, 303);
  assert.ok(await e.DB.prepare('SELECT 1 FROM fleet_members WHERE unit = ?').bind(b.id).first(), 'the club’s radar stays');
  assert.equal((await worker.fetch(form('/f/remove', { unit: a.id }, { cookie, auth: false, origin: 'https://evil.example' }), e)).status, 403);
  await worker.fetch(form('/f/remove', { unit: a.id }, { cookie, auth: false }), e);
  assert.equal(await e.DB.prepare('SELECT 1 FROM fleet_members WHERE unit = ?').bind(a.id).first(), null);
});

test('a new invite code replaces the old one', async () => {
  const e = env(), u = await newUnit();
  const fam = await createFleet(e, 'Family');
  const cookie = await signIn(e, fam.token);
  const html = await (await worker.fetch(form('/f/invite', {}, { cookie, auth: false }), e)).text();
  const fresh = /class="secret">([0-9A-Z-]{14})</.exec(html)[1];
  assert.equal((await worker.fetch(await signed(u, '/v1/unit/fleet', JSON.stringify({ code: fam.code })), e)).status, 404);
  assert.equal((await worker.fetch(await signed(u, '/v1/unit/fleet', JSON.stringify({ code: fresh })), e)).status, 200);
});

test('the maintainer’s page lists fleets without their secrets', async () => {
  const e = env();
  const fam = await createFleet(e, 'Family');
  const html = await (await worker.fetch(new Request(BASE + '/fleet', { headers: { Authorization: basic } }), e)).text();
  assert.match(html, /Family/);
  assert.ok(!html.includes(fam.code) && !html.includes(fam.token));
});
