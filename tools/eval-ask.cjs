// Retrieval check for the free Ask: for each golden-seed question, is a required rule in the top results?
// Usage: serve dist/ on :4321, then NODE_PATH=$(npm root -g) node tools/eval-ask.cjs
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const seed = JSON.parse(fs.readFileSync('ask/golden.seed.json', 'utf8'));
  const idx = JSON.parse(fs.readFileSync('dist/ask-index.json', 'utf8'));
  const url = Object.fromEntries(idx.map((r) => [r.id, r.u]));
  const urlsFor = (id) => idx.filter((r) => r.id === id || r.id.startsWith(id + '.')).map((r) => r.u);
  const b = await chromium.launch(); const p = await b.newPage(); let hit = 0, n = 0; const misses = [];
  for (const g of seed.filter((g) => g.must_cite.length)) {
    n++;
    await p.goto('http://localhost:4321/en/ask/?q=' + encodeURIComponent(g.q)); await p.waitForTimeout(700);
    const got = await p.$$eval('#out blockquote a', (a) => a.map((x) => x.getAttribute('href')));
    const ok = g.must_cite.some((id) => urlsFor(id).some((u) => got.includes(u)));
    if (ok) hit++; else misses.push(g.q);
  }
  console.log(`retrieval: ${hit}/${n} questions have a required rule in the top results`);
  misses.forEach((m) => console.log('  miss:', m));
  await b.close();
})();
