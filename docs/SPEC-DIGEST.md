# Spec digest

Source: `IPF Technical Rulebook web experience spec.pdf` (22 Nov 2026) and the 2026 IPF Technical Rulebook PDF.

**Goal.** A fast, multilingual, accessible site where every rule has its own URL and (later) plain-language questions are answered with exact quoted rules. Unofficial companion by Ant White; the IPF English text prevails.

**Principles.** Meaning is sacred (verbatim, hash-checked, corrections logged) · one rule one URL · answers cite the rule · works with no JavaScript · English prevails in every language.

**Phases.** 1 Foundations (extraction, content model, English rule pages, keyword search, print) · 2 Ask beta · 3 Languages (Welsh, Japanese, IPF imports) · 4 Showcase (loaded-bar hero, card matrix flip, tools, venue mode, offline, edition diff).

## Finding that changes the spec's premise

The rulebook PDF is a **redline**: red bold text is new in 2026, red/black struck-through text is deleted. The spec treats oddities such as "his their", "may must", "three four" and the doubled 7.20 (b) / 3.12 (g) as published wording. They are deletions sitting beside their replacements. This build follows the markings:

- struck text is excluded from rule text and listed at `/en/redline/` (`content/en/2026.struck.json`);
- red text is kept and flagged `changed_2026` (highlighted, listed at `/en/changes/`).

Please confirm this reading. If a clean copy of the 2026 text exists, diff against it.

## What is built (phase 1)

- `tools/extract.py` PDF to `content/en/2026/ch-NN.json` (chapters, sections, clauses, groups, tables, figures), with printed labels, PDF page, SHA-256 per unit.
- `tools/coverage.py` word-for-word check of JSON against the PDF text (0 missing, 0 extra).
- `tools/verify.mjs` build gate: hashes match `content/en/2026.hashes.lock.json` unless a `content/corrections.json` entry exists.
- `content/candidates.json` proposed corrections, none applied; for Ant's sign-off.
- Astro site in `src/`: chapters/sections at `/en/2026/{n}/`, anchors per clause, copy link/citation, short links `/{n}`, Pagefind search, print styles, light/dark, open data `/api/2026/`, `llms.txt`.

## Not yet done

Figures/photos (placeholders, rights unchecked) · Failure-card flip, scoreboard, plate loader · Ask service · Welsh/Japanese · Approved List and wider IPF library · golden question set · offline PWA · edition diff · domain registration · axe CI.

## Known extraction notes

Clause ids: `tr2026.{section}.item-N` (numbered), `.a` (lettered), `.pt-x` (A./1. sub-items); duplicate printed labels get `-2` (6.1 (b)). Chapter 1's 1.1 and 1.2 sit inside its numbered list, so they render inline. Chapter 1 title comes from the contents page. Section headings are shown as printed (uppercase).
