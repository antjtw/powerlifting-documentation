import { units, INLINE_SECTIONS } from '../../../lib/content';
export function getStaticPaths() {
  return units.map((u) => ({ params: { id: u.number }, props: { u } }));
}
export function GET({ props }: any) {
  const { u } = props;
  const { parent, depth, ...rest } = u;
  return new Response(JSON.stringify({
    notice: 'Unofficial companion to the IPF Technical Rulebook. The IPF English text prevails. Wording is as published; see sha256 per clause.',
    edition: '2026', language: 'en', url: `/en/2026/${u.number}/`, ...rest,
  }, null, 1), { headers: { 'Content-Type': 'application/json' } });
}
