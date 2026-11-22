# powerlifting.digital

Unofficial digital edition of the IPF Technical Rulebook 2026. See `docs/SPEC-DIGEST.md`.

```bash
npm install
npm run build      # verify hashes, build site, build search index
npm run dev
python3 -I tools/extract.py && python3 -I tools/coverage.py   # re-extract from the PDF
```
