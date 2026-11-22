// Quote verification: every quoted span must be an exact substring of the cited unit's frozen text.
const norm = (s) => s.replace(/\s+/g, ' ').trim();

export function verifyAnswer(answer, units) {
  const problems = [];
  if (!answer || typeof answer !== 'object') return { ok: false, problems: ['not an object'] };
  const status = answer.status;
  if (!['answered', 'partly', 'not-covered'].includes(status)) problems.push('bad status');
  if (status !== 'not-covered') {
    if (!Array.isArray(answer.citations) || answer.citations.length === 0) problems.push('no citation: must cite or decline');
    for (const c of answer.citations ?? []) {
      const u = units.get(c.id);
      if (!u) { problems.push(`unknown id ${c.id}`); continue; }
      if (!c.quote || !norm(u.text).includes(norm(c.quote))) problems.push(`quote not found in ${c.id}`);
    }
  }
  if (typeof answer.short_answer !== 'string' || !answer.short_answer.trim()) problems.push('no short answer');
  return { ok: problems.length === 0, problems };
}
