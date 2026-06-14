# Methodology — ASM Media Sentiment (Phase 2)

Per-article media-framing analysis of artisanal & small-scale mining (ASM)
coverage for **Ghana** and **Brazil**, built on GDELT's Global Knowledge Graph
(GKG v2) via BigQuery, with Claude-based framing classification on a stratified
sample.

This document describes the data, the filtering strategy, the classification
pipeline, and the known limitations, with the exact counts from the 2025 pilot.
Numbers are drawn from `data/processed/articles_enriched.parquet` (extraction)
and `data/classified/classifications.jsonl` (classification).

> **Lineage.** Phase 1 was a global aggregate dashboard. Phase 1.5 validated
> per-country filters against the GDELT DOC API. **Phase 2** (this work) is the
> per-article, BigQuery-sourced pipeline with framing classification. The full
> design rationale lives in [`asm-phase-2-plan.md`](asm-phase-2-plan.md).

---

## 1. Data source

GDELT GKG v2 (`gdelt-bq.gdeltv2.gkg_partitioned`), queried over the full 2025
calendar year (`2025-01-01` ≤ `_PARTITIONTIME` < `2026-01-01`).

The single most important property of GKG: **it contains no article full
text.** GKG records the article URL (`DocumentIdentifier`), GDELT's theme tags
(`V2Themes`), a lexical tone score (`V2Tone`), extracted named entities
(`AllNames`), extracted quotations (`Quotations`), geographic references
(`V2Locations`), and translation metadata (`TranslationInfo`). Every keyword
filter therefore searches **traces** the article leaves in those fields — never
the body text. This shapes both the recall ceiling (Section 5) and the
classification text-sourcing tiers (Section 4).

---

## 2. Per-country filtering strategy

Phase 1.5 established that **a single global filter is not viable** — ASM
vocabulary, language, and theme behaviour differ enough between countries that
one query either misses Brazil or floods on false positives. Phase 2 therefore
uses **per-country filters**, combined into one extraction query
(`extract/extraction_query.sql`). Each returned row is tagged with the filter
that matched (`filter_match`), with keyword matches taking precedence over theme
matches.

### Ghana
- **Keyword traces:** `galamsey` (the local term for illegal small-scale
  mining) or `illegal mining`, found in the URL, quotations, or names.
- **Theme:** GDELT's `WB_555` (artisanal/small-scale mining) tag.
- **Gate:** a Ghana location signal (`V2Locations` contains `GH`) or `ghana` in
  the URL. `galamsey` is ~94% Ghana-specific, making it the highest-precision
  filter in the study.

### Brazil
- **Keyword traces:** `garimpo` / `garimpeiro` (Portuguese for informal
  mining / informal miner), in the URL, quotations, or names.
- **Theme:** `WB_555`.
- **Gate:** a **Portuguese-language** signal (`TranslationInfo` contains
  `srclc:por`) **or** a Brazil location/URL signal. Phase 1.5 found GDELT's
  `sourcecountry:BR` filter unreliable for translated content, so **language is
  used as the primary gate instead of source country.**

> **Important — the filters are a parallel disjunction, not a sequential
> sieve.** The extraction query is one boolean expression
> (`Ghana-clause OR Brazil-clause`) evaluated atomically in BigQuery. There is
> no ordered "remove by keyword, then remove by theme" cascade. The `CASE`
> statement only *labels* each surviving row by which clause matched (keyword
> before theme), so every article carries exactly one mutually-exclusive
> `filter_match` tag. This matters for the funnel diagram (Section 6).

### Extraction results (2025 pilot)

| `filter_match` | Country | Articles |
|---|---|---:|
| `ghana_keyword` | Ghana | 3,151 |
| `ghana_theme`   | Ghana | 1,353 |
| `brazil_keyword`| Brazil | 837 |
| `brazil_theme`  | Brazil | 138 |
| `other`         | unattributed | 706 |
| **Total** | | **6,185** |

Per-country rollup: **Ghana 4,504 · Brazil 975 · Other 706.** Mean lexical tone
is uniformly negative (Ghana −3.19, Brazil −3.56, Other −4.20). Brazilian
coverage is predominantly Portuguese (867 of 975 articles); Ghanaian coverage is
almost entirely English (4,494 of 4,504).

---

## 3. Enrichment

`extract/parse_gkg.py` turns raw GKG rows into one analysis row per article
(`data/processed/articles_enriched.parquet`), deriving:

- **Tone** and its components (positive/negative scores, polarity) from `V2Tone`.
- **Minerals**, inferred from co-occurring GKG themes (e.g. `WB_2936_GOLD`,
  `WB_2939_DIAMONDS`). Gold dominates both countries. See `config.MINERAL_THEMES`.
- **Original language**, from `TranslationInfo` (pre-translation).
- **Subject countries**, from `V2Locations` (GDELT/FIPS codes, *not* ISO).

---

## 4. Framing classification (Claude)

A **stratified sample of 300** articles (`classify/sample.py`, stratified across
the four country×filter strata: ghana_keyword 86, ghana_theme 82, brazil_keyword
79, brazil_theme 53) is classified by **Claude Haiku 4.5** into a fixed schema
(`classify/prompt.py`):

- **framing** (primary, choose one): `livelihood`, `environmental_threat`,
  `health_hazard`, `criminal_illegal`, `policy_progress`, `human_interest`,
  `gold_market`, `child_labour`, `gender`.
- **secondary_framings** (zero or more of the above).
- **stance**: `critical` / `mixed` / `neutral` / `sympathetic`.
- **solution_orientation**: `problem_focused` / `balanced` / `solution_focused`
  / `not_applicable`.
- plus `is_relevant` (is this actually about ASM?), subject countries,
  confidence, and a short rationale.

### Text-sourcing tiers

Because GKG has no body text, each sampled article is classified on the best text
available, in three tiers (`classify/fetch_text.py`):

1. **`fulltext`** — the article page was fetched and extracted (trafilatura).
2. **`fallback`** — the fetch failed (dead link / paywall), but GKG's
   `Quotations` field carries real quoted speech, so a metadata context block
   (quotes + themes + tone) is substantive enough to classify.
3. **`none`** — no full text **and** no quotes. The only remaining signal is
   themes + tone + URL, which is **circular** with the filter that surfaced the
   article. These are **not sent to Claude** and are **excluded from all analysis
   and graphics.**

### Classification funnel (2025 pilot, n = 300 sampled)

| Stage | Count |
|---|---:|
| Sampled for classification | 300 |
| Excluded — no text or quotes (`none`) | 62 |
| **Classified by Claude** | **238** |
| Excluded — not actually about ASM (false positives) | 40 |
| **Analysis set** | **198** |

Text tiers among the 300: `fulltext` 214, `fallback` (quote-backed) 24,
`none` 62. All framing / stance / solution-orientation reporting runs on the
**198-article analysis set**.

Per-country funnel:

| Country | Sampled | No text/quotes | Classified | Not relevant | Analysis set |
|---|---:|---:|---:|---:|---:|
| Ghana  | 168 | 55 | 113 | 13 | 100 |
| Brazil | 132 |  7 | 125 | 27 |  98 |

The **false-positive rate** (not-relevant share of *classified* articles) is
**Ghana 11.5% (13/113)** and **Brazil 21.6% (27/125)** — a classified-only
denominator, since `none`-tier rows are never classified.

---

## 5. Known limitations

- **Recall (keyword-in-metadata vs full-text).** Benchmarked against Phase 1.5's
  cached DOC API results over an identical 3-month window, the BigQuery approach
  recovers **~48% of DOC API `galamsey` matches** for Ghana. Roughly half of
  full-text keyword hits leave no trace in URL / quotes / names and are missed.
  This is inherent to GKG and is the methodology's main caveat.
- **Brazil recall is unmeasurable** from Phase 1.5 data: DOC API's
  `garimpo sourcecountry:BR` itself returned only 1 article (the broken
  source-country filter), so there is no reference set to benchmark against.
- **Tone is lexical.** GDELT's tone is dictionary-based, so sympathetic
  victim-focused coverage can still read negative.
- **Country codes** in subject-country fields are GDELT/FIPS, not ISO.
- **Precision** is assessed by manual spot-check
  (`validate/precision_spotcheck.py`) and by Claude's not-relevant rate on the
  sample — not exhaustively.
- **Text-sourcing.** 21% of the sample (62/300) had no full text and no quotes
  and were dropped as un-classifiable. The analysis set rests on `fulltext` (214
  available) plus a smaller quote-backed `fallback` tier.

A sensitivity check confirmed the headline framing/stance conclusions are robust
to dropping the `none` tier: no category rank-order changes, largest single shift
≈ 6 pp.

---

## 6. Proposed funnel (Sankey) diagram

> *(Design note for review — not yet built into the dashboard.)*

A Sankey is **feasible and a good fit**, with one framing caveat. The honest
structure is **two flows, not one continuous sieve:**

**Flow A — Extraction breakdown (population = 6,185 extracted articles).**
This is a *partition*, not a sequential filter (see the note in Section 2): every
article carries one `filter_match`, so the widths add up exactly.

```
Matched extraction query (6,185)
├─ Ghana (4,504) ─┬─ galamsey/illegal-mining keyword (3,151)
│                 └─ WB_555 theme                    (1,353)
├─ Brazil (975) ──┬─ garimpo/garimpeiro keyword       (837)
│                 └─ WB_555 theme                      (138)
└─ Other / unattributed (706)
```

**Flow B — Classification funnel (population = 300 stratified sample).**
This one *is* genuinely sequential and is the natural Sankey:

```
Sampled (300)
├─ no text/quotes → excluded            (62)
└─ classified (238)
   ├─ not relevant → excluded           (40)
   └─ analysis set                      (198)
```

**Why not one diagram from 6,185 → 198?** Because the 300 is a *stratified
sample* of the 6,185, not the survivors of a filter — chaining them would imply
6,185 articles funneled down to 198, which is false. The two should be drawn as
separate Sankeys (or one with a clear visual break and a "stratified sample"
node tapped off the extraction pool).

Recommended implementation: a new **"Methodology"** tab in `app.py` rendering
this document plus two `plotly.graph_objects.Sankey` figures driven by
`framing_analysis.funnel(by_country=True)` and the `filter_match` value counts,
so the diagram stays in sync with the data automatically.
