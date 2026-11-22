import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { loadUnits } from './edition.mjs';
import { verifyAnswer } from './verify.mjs';
import { ask } from './handler.mjs';

const units = loadUnits();
const real = units.get('tr2026.3.8.f');

test('accepts an exact quote', () => {
  const r = verifyAnswer({ status: 'answered', short_answer: 'Over, not under.', citations: [{ id: 'tr2026.3.8.f', quote: 'but not under the singlet' }] }, units);
  assert.equal(r.ok, true, r.problems.join());
});
test('rejects a misquote', () => {
  const r = verifyAnswer({ status: 'answered', short_answer: 'x', citations: [{ id: 'tr2026.3.8.f', quote: 'knee sleeves may be worn under the singlet' }] }, units);
  assert.equal(r.ok, false);
});
test('rejects an answer with no citation', () => {
  assert.equal(verifyAnswer({ status: 'answered', short_answer: 'x', citations: [] }, units).ok, false);
});
test('allows a declined answer with no citation', () => {
  assert.equal(verifyAnswer({ status: 'not-covered', short_answer: 'Not in the Technical Rulebook.', citations: [] }, units).ok, true);
});
test('handler drops a misquoted model answer (falls back to search)', async () => {
  const bad = { status: 'answered', short_answer: 'x', citations: [{ id: 'tr2026.3.8.f', quote: 'made up' }] };
  const fetchImpl = async () => ({ ok: true, json: async () => ({ content: [{ text: JSON.stringify(bad) }] }) });
  assert.equal(await ask('q?', { apiKey: 'k', fetchImpl }), null);
});
test('handler returns a verified answer with page and footer', async () => {
  const good = { status: 'answered', short_answer: 'Over only.', citations: [{ id: 'tr2026.3.8.f', quote: real.text.slice(0, 20) }] };
  const fetchImpl = async () => ({ ok: true, json: async () => ({ content: [{ text: JSON.stringify(good) }] }) });
  const r = await ask('q?', { apiKey: 'k', fetchImpl });
  assert.equal(r.citations[0].page, 17);
  assert.match(r.footer, /not a ruling/);
});
test('no key means no answer', async () => assert.equal(await ask('q?', {}), null));
test('golden seed ids all exist', () => {
  const allIds = new Set();
  const walk = (n) => { if (n.id) allIds.add(n.id); (n.content ?? []).forEach(walk); };
  for (const f of readdirSync(new URL('../content/en/2026/', import.meta.url)).filter((f) => /^ch-/.test(f))) walk(JSON.parse(readFileSync(new URL('../content/en/2026/' + f, import.meta.url))));
  const g = JSON.parse(readFileSync(new URL('./golden.seed.json', import.meta.url)));
  for (const q of g) for (const id of q.must_cite) assert.ok(allIds.has(id), `${q.q}: ${id}`);
});
