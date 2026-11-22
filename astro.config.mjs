import { defineConfig } from 'astro/config';
import { readdirSync, readFileSync } from 'node:fs';

// Short links: /4.2.1 -> /en/2026/4.2.1 and /en/latest/4.2.1 -> the current edition.
const redirects = {};
const dir = new URL('./content/en/2026/', import.meta.url);
const walk = (n) => {
  if (n.type === 'chapter' || n.type === 'section') {
    // 1.1 and 1.2 sit inside chapter 1's numbered list, so they have no page of their own
    const inline = n.number === '1.1' || n.number === '1.2';
    const to = inline ? `/en/2026/1/#s-${n.number}` : `/en/2026/${n.number}/`;
    redirects[`/${n.number}`] = to;
    redirects[`/en/latest/${n.number}`] = to;
    if (inline) redirects[`/en/2026/${n.number}`] = to;
  }
  (n.content ?? []).forEach(walk);
};
for (const f of readdirSync(dir).filter((f) => /^ch-\d+\.json$/.test(f))) walk(JSON.parse(readFileSync(new URL(f, dir), 'utf8')));

export default defineConfig({
  site: 'https://powerlifting.digital',
  output: 'static',
  trailingSlash: 'always',
  build: { format: 'directory' },
  redirects,
});
