// Request signing shared with deploy/relay_client.py.
//
// Each unit holds its own Ed25519 key, generated on the unit and never
// copied anywhere. Its public key (base64url, 43 chars) IS its unit id, so
// there is no registration secret baked into images to leak: a gifted unit
// in someone else's house carries nothing that can act for any other unit.
//
// Signed message: `${ts}\n${METHOD}\n${path}\n${hex sha256(body)}`
// Headers:        X-FR-Unit (or X-FR-Phone), X-FR-Time (unix seconds), X-FR-Sig (base64url)

export const MAX_SKEW_S = 300;

const enc = new TextEncoder();

export function b64urlEncode(bytes) {
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

// Only the one canonical spelling of each value (security review
// 2026-11-03, SR-50): unused trailing bits had to be zero, so that one
// signature could not be sent sixteen ways past the replay record, nor one
// id four ways. Every client (Python, Swift, Node) writes them that way.
export function b64urlDecode(s) {
  if (typeof s !== 'string' || !/^[A-Za-z0-9_-]+$/.test(s)) return null;
  const b64 = s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (s.length % 4)) % 4);
  let bytes;
  try {
    bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  } catch {
    return null;
  }
  return b64urlEncode(bytes) === s ? bytes : null;
}

// The signing headers' shape and freshness, checked before a body is read
// (SR-19): a request that can never verify is refused without reading or
// hashing whatever it carries. null when they look right.
export function headerError(request, nowS, idHeader = 'X-FR-Unit') {
  const id = request.headers.get(idHeader) || '';
  const tsRaw = request.headers.get('X-FR-Time') || '';
  const sigRaw = request.headers.get('X-FR-Sig') || '';
  if (!/^[A-Za-z0-9_-]{43}$/.test(id)) return 'bad unit id';
  if (!/^\d{9,11}$/.test(tsRaw)) return 'bad timestamp';
  if (Math.abs(nowS - Number(tsRaw)) > MAX_SKEW_S) return 'clock skew';
  if (!/^[A-Za-z0-9_-]{86}$/.test(sigRaw)) return 'bad signature';
  return null;
}

// A request's body, read up to `max` bytes and no further, whether or not
// it says how long it is (SR-19: a chunked body was buffered whole). null
// when it is longer.
export async function readCapped(request, max) {
  const said = request.headers.get('Content-Length');
  if (said !== null && !(Number(said) <= max)) return null;
  if (!request.body) return new Uint8Array(0);
  const reader = request.body.getReader();
  const parts = [];
  let n = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    n += value.byteLength;
    if (n > max) {
      try { await reader.cancel(); } catch { /* gone anyway */ }
      return null;
    }
    parts.push(value);
  }
  const out = new Uint8Array(n);
  let at = 0;
  for (const p of parts) { out.set(p, at); at += p.byteLength; }
  return out;
}

export async function sha256Hex(bytes) {
  const d = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  return [...d].map(b => b.toString(16).padStart(2, '0')).join('');
}

export function signedMessage(ts, method, path, bodyHash) {
  return `${ts}\n${method.toUpperCase()}\n${path}\n${bodyHash}`;
}

// Returns { unit, ts } when the request is authentic and fresh, else
// { error } with a short reason. `body` is the raw bytes already read.
// Phones sign the same way with their own Ed25519 key (CryptoKit's
// Curve25519.Signing), naming themselves in X-FR-Phone instead; `unit` in
// the result is then the phone's id.
export async function verifyRequest(request, body, nowS, idHeader = 'X-FR-Unit') {
  const unit = request.headers.get(idHeader) || '';
  const tsRaw = request.headers.get('X-FR-Time') || '';
  const sigRaw = request.headers.get('X-FR-Sig') || '';

  const pub = b64urlDecode(unit);
  if (!pub || pub.length !== 32) return { error: 'bad unit id' };
  if (!/^\d{9,11}$/.test(tsRaw)) return { error: 'bad timestamp' };
  const ts = Number(tsRaw);
  if (Math.abs(nowS - ts) > MAX_SKEW_S) return { error: 'clock skew' };
  const sig = b64urlDecode(sigRaw);
  if (!sig || sig.length !== 64) return { error: 'bad signature' };

  let key;
  try {
    key = await crypto.subtle.importKey('raw', pub, { name: 'Ed25519' }, false, ['verify']);
  } catch {
    return { error: 'bad unit id' };
  }
  const path = new URL(request.url).pathname;
  const msg = signedMessage(ts, request.method, path, await sha256Hex(body));
  const ok = await crypto.subtle.verify({ name: 'Ed25519' }, key, sig, enc.encode(msg));
  return ok ? { unit, ts } : { error: 'bad signature' };
}
