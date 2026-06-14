# ASM Media Sentiment — Phase 2

## Project context
Phase 2 of an ASM (artisanal & small-scale mining) media sentiment analysis project.
Phase 1 repo: https://github.com/caluchko/asm-sentiment
Phase 1.5 validation data is cached in the Phase 1.5 project directory.
Full plan: `asm-phase-2-plan.md`.

## Key findings from Phase 1.5
- WB_555 theme works for Ghana (600 art/year) but fails for Brazil (24 art/year)
- Keyword "galamsey" is the best Ghana filter (2,220 art/year, high precision)
- Keyword "garimpo + sourcecountry:BR" is broken (3 art/year)
- sourcecountry filter is unreliable for translated content; use sourcelang instead
- ENV_MINING + WB_2936_GOLD has ~7% precision for Brazil (vocabulary collisions)
- A single global filter is not viable; per-country strategies are needed

## Architecture
BigQuery GKG → local parquet → analysis + Claude classification → Streamlit
No DOC API in the production pipeline. DOC API only for recall validation.

## Environment (IMPORTANT — this machine)
- gcloud/bq are a **tarball install at `~/google-cloud-sdk`** (brew cask postinstall
  fails). They run only with `CLOUDSDK_PYTHON=/opt/homebrew/bin/python3.13` because the
  brew/python.org Pythons have a broken `pyexpat` and system python3 is 3.9 (too old).
  `~/.zshrc` sets this up; new terminals are fine.
- Python pipeline uses a venv at `./.venv` (built from `python3.13`). Activate with
  `source .venv/bin/activate`.
- Active GCP account: davis.kenneth.j@gmail.com. Project `gen-lang-client-0024754648`
  (the throwaway Gemini default). **Do not touch `igold-reporting`.** No billing linked,
  so only dry-runs / sandbox-eligible queries work.

## BigQuery notes
- Table: gdelt-bq.gdeltv2.gkg_partitioned
- Live schema names the quote/name fields `Quotations` and `AllNames` (no V2 prefix);
  `DATE` is INTEGER YYYYMMDDHHMMSS. The query aliases them to V2Quotations/V2AllNames.
- Always include the `_PARTITIONTIME` filter
- Always dry-run first; always pass `--maximum_bytes_billed=1000000000000`
- Dry-run confirmed: 2025 pilot scans **222.6 GB** (~22% of 1 TB free tier)
- GKG has no full article text; keywords are searched in URL, quotes, names
- Export results to local parquet; do not re-query for analysis

## GDELT DOC API notes (recall validation only)
- Rate limits aggressively; use 60s+ delays
- Whitelisted UA: "GDELT DOC Python API client 1.12.0 - https://github.com/alex9smith/gdelt-doc-api"
- gdeltdoc library has trailing-space bug; use raw requests if needed
- Phase 1.5 cached responses are in the Phase 1.5 project cache/ directory

## Layout
- `config.py` — paths, filter tags, mineral themes, Claude settings
- `extract/` — extraction_query.sql, dry_run.sh, bigquery_extract.py, parse_gkg.py
- `validate/`, `classify/`, `analysis/`, `app.py` (Streamlit)
- `data/{raw,processed,classified,validation}` — gitignored
