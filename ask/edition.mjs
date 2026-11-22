// Flattens the frozen 2026 edition into citable units for the Ask prompt and quote checks.
import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const dir = join(dirname(fileURLToPath(import.meta.url)), '../content/en/2026');

export function loadUnits() {
  const out = new Map();
  const walk = (n) => {
    if (n.type === 'clause') {
      const text = (n.content ?? []).filter((c) => ['p', 'li', 'line'].includes(c.type)).map((c) => c.text).join('\n');
      out.set(n.id, { id: n.id, label: n.label, page: n.page, text });
    }
    if (n.type === 'table') out.set(n.id, { id: n.id, page: n.page, text: [n.header, ...n.rows].filter(Boolean).map((r) => r.join(' | ')).join('\n') });
    if (n.type === 'failure-matrix') {
      const t = Object.entries(n.matrix).flatMap(([c, cols]) => Object.entries(cols).flatMap(([lift, rs]) => rs.map((r) => `${c} / ${lift}: ${r}`)));
      out.set(n.id, { id: n.id, page: n.page, text: t.join('\n') });
    }
    (n.content ?? []).forEach(walk);
  };
  for (const f of readdirSync(dir).filter((f) => /^ch-\d+\.json$/.test(f))) walk(JSON.parse(readFileSync(join(dir, f), 'utf8')));
  return out;
}

/** The whole edition as one cached prompt document: [id] text. */
export function editionDocument(units = loadUnits()) {
  return [...units.values()].map((u) => `[${u.id}] (PDF p.${u.page})\n${u.text}`).join('\n\n');
}
