import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const root = fileURLToPath(new URL('../../content/', import.meta.url));
const dir = join(root, 'en/2026');

export type Node = {
  type: string; id?: string; number?: string; title?: string; toc_title?: string; label?: string;
  text?: string; page?: number; content?: Node[]; changed?: [number, number][]; changed_2026?: boolean;
  sha256?: string; caption?: string | null; [k: string]: any;
};

export const chapters: Node[] = readdirSync(dir)
  .filter((f) => /^ch-\d+\.json$/.test(f)).sort()
  .map((f) => JSON.parse(readFileSync(join(dir, f), 'utf8')));

export const edition = { id: '2026', effective: '2026-03-01', effectiveLabel: '1 March 2026', pdfPages: 45 };
export const struck: { page: number; text: string }[] = JSON.parse(readFileSync(join(root, 'en/2026.struck.json'), 'utf8'));
export const corrections: any[] = JSON.parse(readFileSync(join(root, 'corrections.json'), 'utf8'));
export const candidates: any[] = JSON.parse(readFileSync(join(root, 'candidates.json'), 'utf8'));

/** Every chapter and section, in reading order, with its parent. */
export type Unit = Node & { parent?: Node; depth: number };
export const units: Unit[] = [];
function collect(n: Node, parent?: Node, depth = 0) {
  if (n.type === 'chapter' || n.type === 'section') units.push({ ...n, parent, depth } as Unit);
  (n.content ?? []).forEach((c) => c.type === 'section' && collect(c, n, depth + 1));
}
chapters.forEach((c) => collect(c));
// replace shallow copies with the live nodes so mutations are shared
export const unitByNumber = new Map(units.map((u) => [u.number!, u]));

export const INLINE_SECTIONS = new Set(['1.1', '1.2']); // sit inside chapter 1's numbered list

export function titleOf(n: Node) { return n.title ?? ''; }

/** Sentence-case a verbatim UPPERCASE heading for display only. */
export function display(t: string) {
  const s = t.toLowerCase().replace(/(^|[(/]\s*)([a-z])/g, (_, a, b) => a + b.toUpperCase());
  return s.replace(/\b(Ipf|Ii)\b/g, (m) => m.toUpperCase());
}

export function allClauses(): { clause: Node; unit: Unit; path: string[] }[] {
  const out: { clause: Node; unit: Unit; path: string[] }[] = [];
  const walk = (n: Node, unit: Unit, path: string[]) => {
    for (const c of n.content ?? []) {
      if (c.type === 'clause') { out.push({ clause: c, unit, path: [...path, c.label!] }); walk(c, unit, [...path, c.label!]); }
      else if (c.type === 'group') walk(c, unit, path);
    }
  };
  for (const u of units) walk(u, u, []);
  return out;
}

export function neighbours(number: string) {
  const i = units.findIndex((u) => u.number === number);
  const ok = (u?: Unit) => u && !INLINE_SECTIONS.has(u.number!) ? u : undefined;
  let prev: Unit | undefined, next: Unit | undefined;
  for (let k = i - 1; k >= 0 && !prev; k--) prev = ok(units[k]);
  for (let k = i + 1; k < units.length && !next; k++) next = ok(units[k]);
  return { prev, next };
}

export function crumbs(u: Unit) {
  const out: Unit[] = [];
  let cur: Unit | undefined = u;
  while (cur) { out.unshift(cur); cur = cur.parent ? unitByNumber.get(cur.parent.number!) : undefined; }
  return out;
}

export function esc(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Escape text and wrap ranges the PDF printed in red (inserted in 2026) in <mark>. */
export function markup(text: string, ranges?: [number, number][]) {
  if (!ranges?.length) return esc(text);
  let out = '', pos = 0;
  for (const [a, b] of ranges) {
    out += esc(text.slice(pos, a)) + '<mark class="changed" title="Printed in red in the PDF: new or changed in the 2026 edition">' + esc(text.slice(a, b)) + '</mark>';
    pos = b;
  }
  return out + esc(text.slice(pos));
}

export function plainText(n: Node): string {
  const own = (n.content ?? []).filter((c) => ['p', 'li', 'line'].includes(c.type)).map((c) => c.text).join(' ');
  return own;
}

export const relations: { a: string; b: string; kind: string; note?: string }[] = JSON.parse(readFileSync(join(root, 'relations.json'), 'utf8'));
export const paths: { slug: string; title: string; who: string; intro: string; steps: { id?: string; signpost?: string }[] }[] = JSON.parse(readFileSync(join(root, 'paths.json'), 'utf8'));

/** id -> node, with its page unit. */
export const byId = new Map<string, { node: Node; unit: Unit }>();
(function index() {
  const walk = (n: Node, unit: Unit) => {
    if (n.id) byId.set(n.id, { node: n, unit });
    (n.content ?? []).forEach((c) => walk(c, c.type === 'section' ? (unitByNumber.get(c.number!) as Unit) : unit));
  };
  for (const c of chapters) walk(c, unitByNumber.get(c.number!) as Unit);
})();

export function hrefOf(id: string) {
  const hit = byId.get(id);
  if (!hit) return '/en/2026/';
  const { node, unit } = hit;
  const base = INLINE_SECTIONS.has(unit.number!) ? `/en/2026/1/` : `/en/2026/${unit.number}/`;
  return node.id === unit.id ? base : `${base}#${node.id!.slice(unit.id!.length + 1)}`;
}
export function labelOf(id: string) {
  const hit = byId.get(id);
  if (!hit) return id;
  const { node, unit } = hit;
  if (node.type === 'section' || node.type === 'chapter') return `${node.number} ${display(node.title!)}`;
  const prefix: string[] = [];
  const parts = id.slice(unit.id!.length + 1).split('.').map((x) => { prefix.push(x); const g = byId.get(`${unit.id}.${prefix.join('.')}`)?.node; if (g?.type === 'group' && g.title) return display(g.title.replace(/:$/, '')); return x; }).map((x) => (/^item-\d+$/.test(x) ? x.slice(5) + ')' : /^[a-z]$/.test(x) ? `(${x})` : /^pt-/.test(x) ? x.slice(3) + '.' : x));
  return `${unit.number} ${parts.join(' ')}`;
}
