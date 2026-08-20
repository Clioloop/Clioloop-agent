---
name: grounded-citations
description: "Research with an auditable source ledger, quote verification, and claim-level citations."
version: 1.0.0
author: Clio Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  clio:
    tags: [research, citations, fact-checking, sources, verification]
    category: research
---

# Grounded Citations

Use this skill when a user needs current factual research, a fact check, a due-diligence report, or prose where every material claim must be traceable to a source.

## Contract

1. Search broadly, but cite only sources you actually opened.
2. Prefer primary sources, official records, papers, standards, and first-party documentation. Use secondary reporting to discover or contextualize primary evidence.
3. Record an exact supporting quote for every material claim before drafting. A URL by itself is not evidence.
4. Do not claim that a quote supports more than it says. Mark inference, estimate, conflict, and uncertainty explicitly.
5. Keep publication date and retrieval date distinct. For fast-changing facts, state both.
6. Never invent titles, URLs, authors, dates, page numbers, or quotes.
7. If sources disagree, preserve the disagreement rather than averaging it away.

## Workflow

1. **Define claims.** Break the request into atomic factual questions. Separate facts, calculations, interpretation, and recommendation.
2. **Discover sources.** Use `web_search` with exact phrases, domain filters, and primary-source terms. Open likely sources with `web_extract` or the browser.
3. **Capture evidence.** For each claim, save:
   - canonical URL;
   - title and publisher;
   - publication date if known;
   - retrieval timestamp;
   - exact quote or table row;
   - whether it supports, contradicts, or only contextualizes the claim.
4. **Verify quotes.** The quote must occur in the captured page text after whitespace normalization. Use `scripts/source_ledger.py add` when working in a project that needs a durable ledger.
5. **Triangulate.** High-impact claims need either one authoritative primary source or two independent credible sources. Ownership, legal status, pricing, security incidents, and health/safety claims deserve extra scrutiny.
6. **Draft from the ledger.** Put citations immediately after the claim, not at the end of a long paragraph. Use stable source IDs (`[S1]`, `[S2]`) while drafting.
7. **Fact-check pass.** Re-read every sentence containing a number, date, named entity, causal statement, superlative, or current-status verb. Remove or qualify anything not supported by the ledger.
8. **Render sources.** End with a compact numbered source list containing title, publisher, date, and URL. Do not repeat unused sources.

## Source ledger helper

```bash
python skills/research/grounded-citations/scripts/source_ledger.py init sources.json
python skills/research/grounded-citations/scripts/source_ledger.py add sources.json \
  --url https://example.com/report --title "Report title" \
  --claim "Atomic claim" --quote "Exact supporting quote" \
  --content-file captured-page.txt --relation supports
python skills/research/grounded-citations/scripts/source_ledger.py verify sources.json
python skills/research/grounded-citations/scripts/source_ledger.py render sources.json
```

`add` refuses a quote that does not occur in `--content-file`. The ledger stores a SHA-256 digest of the normalized evidence quote and writes atomically. It contains evidence and public URLs only—never credentials, cookies, auth headers, private user data, or unredacted tool output.

## Citation format

Use claim-level citations:

> The standard entered into force on 1 January 2026. [S2]

For a conflict:

> The regulator reports 41 incidents [S1], while the operator reports 37 for the same period [S3]; the sources define the reporting window differently.

For an inference:

> This suggests capacity was constrained during the launch window, although neither source states that directly. [S4][S5]

## Failure modes

- **Paywall or blocked page:** cite only a legitimately accessible primary/archived source; do not infer from a search snippet.
- **Dynamic page changed:** record the retrieval time and, where permitted, a stable document/PDF URL.
- **No supporting source:** say that the claim could not be verified and omit it from definitive prose.
- **Quote found only in a repost:** identify the repost as secondary and continue looking for the original.
- **User-provided evidence:** label it as user-provided rather than independently verified.
