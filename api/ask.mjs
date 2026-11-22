// Vercel serverless function: POST /api/ask {q}. Returns a verified, cited answer, or {fallback:true}.
// Needs ANTHROPIC_API_KEY. Rate limit here is per-instance memory only: put a shared store
// (edge KV) and a hard monthly spend cap in front before launch.
import { ask } from '../ask/handler.mjs';

const hits = new Map();
const LIMIT = 20, WINDOW = 10 * 60 * 1000;

export default async function handler(req, res) {
  res.setHeader('content-type', 'application/json');
  if (req.method !== 'POST') { res.statusCode = 405; return res.end('{"error":"POST only"}'); }
  const ip = (req.headers['x-forwarded-for'] || '').split(',')[0] || 'unknown';
  const now = Date.now();
  const recent = (hits.get(ip) || []).filter((t) => now - t < WINDOW);
  if (recent.length >= LIMIT) { res.statusCode = 429; return res.end('{"fallback":true,"reason":"rate-limit"}'); }
  hits.set(ip, [...recent, now]);
  let q = '';
  try { q = (typeof req.body === 'string' ? JSON.parse(req.body) : req.body)?.q ?? ''; } catch { /* ignore */ }
  const answer = await ask(String(q), { apiKey: process.env.ANTHROPIC_API_KEY });
  res.end(JSON.stringify(answer ? { answer } : { fallback: true }));
}
