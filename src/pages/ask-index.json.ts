import { byId, hrefOf, labelOf, display, type Node } from '../lib/content';

// Flat index of every citable unit for the free, in-browser Ask. Text is verbatim.
export function GET() {
  const rows: any[] = [];
  for (const [id, { node, unit }] of byId) {
    let text = '';
    if (['clause', 'section', 'chapter', 'group'].includes(node.type)) {
      text = (node.content ?? []).filter((c: Node) => ['p', 'li', 'line'].includes(c.type)).map((c: Node) => c.text).join('\n');
      if (node.type === 'group' && node.lead) text = node.lead + '\n' + text;
    } else if (node.type === 'table') text = [node.header, ...node.rows].filter(Boolean).map((r: string[]) => r.join(' · ')).join('\n');
    else if (node.type === 'failure-matrix') text = Object.entries(node.matrix).flatMap(([c, cols]: any) => Object.entries(cols).flatMap(([l, rs]: any) => rs.map((r: string) => `${c} / ${l}: ${r}`))).join('\n');
    else continue;
    if (!text.trim()) continue;
    const head = node.type === 'section' || node.type === 'chapter' ? display(node.title!) : display(unit.title ?? '');
    rows.push({ id, u: hrefOf(id), t: labelOf(id), h: head, p: node.page, x: text });
  }
  return new Response(JSON.stringify(rows), { headers: { 'Content-Type': 'application/json' } });
}
