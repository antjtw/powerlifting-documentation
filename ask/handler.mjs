// Ask the Rulebook: one function. Reads the whole edition (cached), returns a verified, cited answer,
// or null so the caller falls back to keyword search. Never answers without a verified citation.
import { loadUnits, editionDocument } from './edition.mjs';
import { verifyAnswer } from './verify.mjs';

const units = loadUnits();
const doc = editionDocument(units);

export const SYSTEM = `You answer questions about the 2026 IPF Technical Rulebook using ONLY the rules supplied below.
Rules:
- Reply with one JSON object: {"status":"answered"|"partly"|"not-covered","short_answer":string (1-3 sentences, in the user's language),"citations":[{"id":string,"quote":string}]}.
- Every quote must be copied exactly, character for character, from the cited unit. Cite the exact sentence relied on.
- If the rules do not cover the question (for example anti-doping, By-Laws, the Approved List), use status "not-covered", cite nothing, and say so. Never use outside knowledge.
- If rules interact or are ambiguous, say so and cite both.
- For anti-doping, medical, safeguarding or eligibility questions, give no advice; point to the IPF or the national anti-doping body.
- Numbers (ages, loading, compensatory time) are computed by tools, not by you.
- Wording differences between clauses are never resolved; show both.`;

export async function ask(question, { apiKey, model = 'claude-sonnet-5-5', fetchImpl = fetch } = {}) {
  if (!apiKey || !question?.trim()) return null;
  const body = {
    model, max_tokens: 700,
    system: [
      { type: 'text', text: SYSTEM },
      { type: 'text', text: `RULES (2026 edition):\n\n${doc}`, cache_control: { type: 'ephemeral' } },
    ],
    messages: [{ role: 'user', content: question.slice(0, 600) }],
  };
  let res;
  try {
    res = await fetchImpl('https://api.anthropic.com/v1/messages', {
      method: 'POST', headers: { 'content-type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' }, body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const text = data.content?.map((c) => c.text ?? '').join('') ?? '';
    const answer = JSON.parse(text.slice(text.indexOf('{'), text.lastIndexOf('}') + 1));
    const check = verifyAnswer(answer, units);
    if (!check.ok) return null;
    return { ...answer, citations: answer.citations.map((c) => ({ ...c, page: units.get(c.id).page })), footer: 'Guidance, not a ruling. On the platform, the referees and Jury decide.' };
  } catch { return null; }
}
