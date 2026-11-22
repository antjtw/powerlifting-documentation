#!/usr/bin/env node
// Integrity gate: recompute every text hash and compare with the frozen lock.
// A changed hash is only allowed with a matching entry in content/corrections.json.
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dir = join(root, 'content/en/2026');
const lock = JSON.parse(readFileSync(join(root, 'content/en/2026.hashes.lock.json'), 'utf8'));
const corrFile = join(root, 'content/corrections.json');
const corrections = existsSync(corrFile) ? JSON.parse(readFileSync(corrFile, 'utf8')) : [];
const allowed = new Set(corrections.map((c) => c.id));
const sha = (t) => createHash('sha256').update(t, 'utf8').digest('hex');

const errors = [];
const seen = new Set();
let checked = 0;

function walk(n) {
  const kids = n.content ?? [];
  let own = null;
  if (n.type === 'clause') own = kids.filter((c) => ['p', 'li', 'line'].includes(c.type)).map((c) => c.text).join('\n');
  if (n.type === 'p' || n.type === 'li' || n.type === 'line') own = n.text;
  if (own !== null) {
    checked++;
    if (sha(own) !== n.sha256) errors.push(`${n.id ?? '(unnamed)'}: stored hash does not match its text`);
  }
  if (n.id) {
    if (seen.has(n.id)) errors.push(`duplicate id ${n.id}`);
    seen.add(n.id);
    if (n.sha256 && lock[n.id] !== n.sha256 && !allowed.has(n.id)) errors.push(`${n.id}: hash differs from lock with no corrections-log entry`);
  }
  kids.forEach(walk);
}

for (const f of readdirSync(dir).filter((f) => /^ch-\d+\.json$/.test(f))) walk(JSON.parse(readFileSync(join(dir, f), 'utf8')));
for (const id of Object.keys(lock)) if (!seen.has(id)) errors.push(`${id}: in lock but missing from content`);

if (errors.length) {
  console.error(`verify: ${errors.length} problem(s)\n` + errors.slice(0, 30).join('\n'));
  process.exit(1);
}
console.log(`verify: ${checked} text units and ${seen.size} ids OK, ${corrections.length} logged corrections`);
