// Request signing shared with deploy/relay_client.py.
//
// Each unit holds its own Ed25519 key, generated on the unit and never
// copied anywhere. Its public key (base64url, 43 chars) IS its unit id, so
// there is no registration secret baked into images to leak: a gifted unit
// in someone else's house carries nothing that can act for any other unit.
//
// Signed message: `${ts}\n${METHOD}\n${path}\n${hex sha256(body)}`
// Headers:        X-FR-Unit, X-FR-Time (unix seconds), X-FR-Sig (base64url)

export const MAX_SKEW_S = 300;

const enc = new TextEncoder();

export function b64urlDecode(s) {
  if (typeof s !== 'string' || !/^[A-Za-z0-9_-]+$/.test(s)) return null;
  const b64 = s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (s.length % 4)) % 4);
  try {
    return Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  } catch {
    return null;
  }
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
export async function verifyRequest(request, body, nowS) {
  const unit = request.headers.get('X-FR-Unit') || '';
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
