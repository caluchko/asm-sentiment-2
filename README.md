# ASM Media Sentiment — Phase 2

Per-article media-framing analysis of artisanal & small-scale mining (ASM)
coverage for **Ghana** and **Brazil**, built on GDELT's Global Knowledge Graph
(GKG) via BigQuery, with Claude-based framing classification on a stratified
sample.

Phase 1 (global aggregate dashboard) → Phase 1.5 (per-country filter validation)
→ **Phase 2** (per-article, BigQuery-sourced, with framing classification).
Full design: [`asm-phase-2-plan.md`](asm-phase-2-plan.md).

## Results (2025 pilot)

| | Ghana | Brazil |
|---|---|---|
| Articles extracted | 4,504 | 975 |
| Dominant filter | `galamsey` keyword | `garimpo` keyword |
| Mean tone | −3.19 | −3.56 |
| Portuguese-language articles | — | 1,075 |

6,185 articles total (incl. 706 unclassified-country "other"). Gold is the
dominant identified mineral in both countries; tone is uniformly negative.

## Pipeline

```
BigQuery GKG (extract/extraction_query.sql)
   → data/raw/gkg_pilot_2025.parquet         (extract/bigquery_extract.py)
   → data/processed/articles_enriched.parquet (extract/parse_gkg.py)
        ├─ recall validation   (validate/recall_validation.py)
        ├─ precision spotcheck (validate/precision_spotcheck.py)
        ├─ analysis + dashboard (analysis/*, app.py)
        └─ stratified sample → Claude framing classification
             (classify/sample.py → fetch_text.py → run_classification.py)
```

## Setup

This machine's Homebrew Pythons have a broken `pyexpat`, and `gcloud` needs
Python 3.10–3.14, so the toolchain is split:

- **gcloud / bq**: tarball SDK at `~/google-cloud-sdk`, run with
  `CLOUDSDK_PYTHON=/opt/homebrew/bin/python3.13` (both exported from `~/.zshrc`).
- **Python pipeline**: venv built from the system Python 3.9 (which has a working
  pip/pyexpat).

```bash
# one-time
python3.9 -m venv .venv         # or /usr/bin/python3
.venv/bin/pip install -r requirements.txt
gcloud auth login               # interactive, browser

# extraction (always dry-run first)
.venv/bin/python extract/bigquery_extract.py --dry-run   # ~222 GB, free tier
.venv/bin/python extract/bigquery_extract.py             # → data/raw parquet
.venv/bin/python extract/parse_gkg.py                    # → data/processed parquet

# validation & analysis
.venv/bin/python validate/recall_validation.py
.venv/bin/python validate/precision_spotcheck.py         # then label, then --score

# classification (needs ANTHROPIC_API_KEY)
.venv/bin/python classify/sample.py
export ANTHROPIC_API_KEY=sk-ant-...
.venv/bin/python classify/run_classification.py

# dashboard
.venv/bin/streamlit run app.py
```

GCP project: `gen-lang-client-0024754648` (no billing linked → BigQuery sandbox;
the 2025 pilot scans 222 GB, well within the 1 TB/month free tier). **Always**
dry-run first; every query carries a 1 TB `--maximum_bytes_billed` cap.

## Methodology

GKG has **no article full text**, so keywords are searched in the fields where
they leave traces: the article URL (`DocumentIdentifier`), extracted quotes
(`Quotations`), extracted names (`AllNames`), and theme tags (`V2Themes`).
Per-country filters (from Phase 1.5):

- **Ghana** — `galamsey` / `illegal mining` keyword traces + WB_555 theme, gated
  on a Ghana location/URL signal. `galamsey` is ~94% Ghana-specific.
- **Brazil** — `garimpo` / `garimpeiro` keyword traces + WB_555 theme, gated on a
  Portuguese-language (`srclc:por`) or Brazil location/URL signal. The
  `sourcecountry:BR` filter is unreliable for translated content, so language is
  used instead.

### Classification text-sourcing & funnel

Each sampled article is classified on the best text available, in three tiers
(`classify/fetch_text.py`):

1. **`fulltext`** — the article page was fetched and extracted (trafilatura).
2. **`fallback`** — the fetch failed (dead/paywalled), but the GKG `Quotations`
   field carries quoted speech, so a metadata context block (quotes + themes +
   tone) is substantive enough to classify.
3. **`none`** — no full text *and* no quotes. The only remaining signal is
   themes + tone + URL, which is **circular** with the filter that surfaced the
   article. These are **not sent to Claude** (saving tokens) and are **excluded
   from all analysis and graphics**.

The dashboard's framing tab shows the resulting funnel. For the 2025 pilot's
300-article stratified sample:

| Stage | Count |
|---|---|
| Sampled for classification | 300 |
| Excluded — no text or quotes (`none`) | 62 |
| Classified by Claude | 238 |
| Excluded — not relevant to ASM (false positives) | 40 |
| **Analysis set** | **198** |

A sensitivity check confirmed the headline framing/stance conclusions are robust
to dropping the `none` tier: no category rank-order changes, with the largest
single shift ≈6 pp (Ghana stance, slightly less *critical*). Because `none`
articles are now excluded, the per-country **false-positive rate** is reported
over *classified* articles only (Brazil 21.6%, Ghana 11.5% for the pilot) — a
classified-only denominator, slightly different from earlier figures that
included un-classifiable rows.

## Known limitations

- **Recall (keyword-in-metadata vs full-text).** Measured against Phase 1.5's
  cached DOC API results over an identical 3-month window: the BigQuery approach
  recovers **48% of DOC API `galamsey` matches** for Ghana. Roughly half of
  full-text keyword hits leave no trace in URL/quotes/names and are missed. This
  is inherent to GKG (no full text) and is the methodology's main caveat.
- **Brazil keyword recall is unmeasurable** from Phase 1.5 data: DOC API's
  `garimpo sourcecountry:BR` itself returned only 1 article (the broken
  source-country filter), so there is no meaningful reference set.
- **Country codes** in `subject_countries` are GDELT/FIPS, not ISO.
- **Precision** is assessed by manual spot-check (`validate/precision_spotcheck.py`)
  and, on the classified sample, by Claude's own not-relevant rate (the
  false-positive rate, over classified articles) — not exhaustively.
- **Text-sourcing.** 21% of the pilot sample (62/300) had no full text and no
  quotes and are excluded as un-classifiable; see *Classification text-sourcing &
  funnel* above. Of the rest, framing/stance rest on `fulltext` (214) plus a
  smaller `fallback`-with-quotes tier (24).

## Layout

`config.py` (shared constants) · `extract/` (query, extraction, parsing) ·
`validate/` (recall, precision) · `classify/` (sample, fetch, prompt, run) ·
`analysis/` (tone, country, minerals, framing) · `app.py` (Streamlit) ·
`data/` (raw/processed/classified/validation, gitignored).
