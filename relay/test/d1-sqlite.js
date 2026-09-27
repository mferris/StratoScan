// A minimal Cloudflare D1 stand-in over Node's built-in SQLite, so the
// relay's real SQL runs in tests: prepare().bind().first()/all()/run(), and
// batch(). Only the subset the relay uses.
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';

export function makeD1(schemaPath) {
  const db = new DatabaseSync(':memory:');
  db.exec(readFileSync(schemaPath, 'utf8'));
  const stmt = (sql, args = []) => ({
    bind: (...a) => stmt(sql, a),
    first: async () => db.prepare(sql).get(...args) ?? null,
    all: async () => ({ results: db.prepare(sql).all(...args) }),
    run: async () => { db.prepare(sql).run(...args); return { success: true }; },
  });
  return {
    prepare: sql => stmt(sql),
    batch: async stmts => {
      db.exec('BEGIN');
      try {
        for (const s of stmts) await s.run();
        db.exec('COMMIT');
      } catch (e) {
        db.exec('ROLLBACK');
        throw e;
      }
    },
    raw: db,
  };
}
