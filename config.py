"""Central configuration for ASM Media Sentiment — Phase 2.

Filter definitions, country configs, paths, and constants live here so the
extraction query, parsing, sampling, and analysis all share one source of truth.
"""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW_DIR = DATA / "raw"
PROCESSED_DIR = DATA / "processed"
CLASSIFIED_DIR = DATA / "classified"
VALIDATION_DIR = DATA / "validation"

for _d in (RAW_DIR, PROCESSED_DIR, CLASSIFIED_DIR, VALIDATION_DIR):
    _d.mkdir(parents=True, exist_ok=True)

EXTRACTION_QUERY_SQL = ROOT / "extract" / "extraction_query.sql"
RAW_PARQUET = RAW_DIR / "gkg_pilot_2025.parquet"
PROCESSED_PARQUET = PROCESSED_DIR / "articles_enriched.parquet"

# --------------------------------------------------------------------------- #
# BigQuery
# --------------------------------------------------------------------------- #
# Throwaway "Default Gemini Project" — NOT igold-reporting. No billing linked,
# so only dry-runs and free-tier/sandbox queries succeed.
GCP_PROJECT = "gen-lang-client-0024754648"
GKG_TABLE = "gdelt-bq.gdeltv2.gkg_partitioned"
MAX_BYTES_BILLED = 1_000_000_000_000  # 1 TB safety cap on every real query

# Pilot window (inclusive start, exclusive end) — matches extraction_query.sql.
PILOT_START = "2025-01-01"
PILOT_END = "2026-01-01"

# --------------------------------------------------------------------------- #
# Countries / filter tags (must match filter_match values in the SQL)
# --------------------------------------------------------------------------- #
COUNTRY_OF_FILTER = {
    "ghana_keyword": "Ghana",
    "ghana_theme": "Ghana",
    "brazil_keyword": "Brazil",
    "brazil_theme": "Brazil",
    "other": "Other",
}
FILTER_TYPE_OF_FILTER = {
    "ghana_keyword": "keyword",
    "ghana_theme": "theme",
    "brazil_keyword": "keyword",
    "brazil_theme": "theme",
    "other": "other",
}

# --------------------------------------------------------------------------- #
# Mineral identification from co-occurring GKG themes
# --------------------------------------------------------------------------- #
MINERAL_THEMES = {
    "gold": ["WB_2936_GOLD", "ECON_GOLDPRICE",
             "TAX_FNCACT_GOLD_MINERS", "TAX_FNCACT_GOLD_MINER"],
    "diamonds": ["WB_2939_DIAMONDS"],
    "cobalt": ["WB_2932_COBALT"],
    "tin": ["WB_2938_TIN"],
    "tantalum": ["WB_2941_TANTALUM"],
    "tungsten": ["WB_2940_TUNGSTEN"],
}

# --------------------------------------------------------------------------- #
# Claude classification
# --------------------------------------------------------------------------- #
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
CLASSIFY_DELAY_S = 0.5
MAX_ARTICLE_WORDS = 3000
SAMPLE_SIZE = 300  # target stratified sample (200–400)
