import { units, chapters } from '../lib/content';
export function GET() {
  const lines = [
    '# powerlifting.digital',
    '',
    '> Unofficial digital edition of the IPF Technical Rulebook 2026 (effective 01.03.2026). Not produced or endorsed by the IPF. The IPF English text prevails over anything here.',
    '',
    'Rule wording is verbatim from the IPF PDF. Cite rules by number, for example "IPF TR 2026, 4.2.1 6)". Structured data: /api/2026/index.json. Each unit also has /en/2026/{number}/.',
    '',
    '## Chapters and sections',
    ...units.map((u) => `- [${u.number} ${u.title}](/en/2026/${u.number}/)`),
    '',
  ];
  return new Response(lines.join('\n'), { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}
