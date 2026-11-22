import { chapters, units } from '../../../lib/content';
export function GET() {
  return new Response(JSON.stringify({
    edition: '2026', effective: '2026-03-01', language: 'en',
    notice: 'Unofficial companion to the IPF Technical Rulebook. The IPF English text prevails.',
    units: units.map((u) => ({ number: u.number, type: u.type, title: u.title, page: u.page, url: `/api/2026/${u.number}.json` })),
    chapters: chapters.length,
  }, null, 1), { headers: { 'Content-Type': 'application/json' } });
}
