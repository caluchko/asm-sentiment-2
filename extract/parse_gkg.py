"""Parse raw GKG V2 fields into structured analysis columns.

Reads the raw extraction parquet and writes an enriched parquet with parsed
tone, subject countries, language, minerals, and country/filter tags.

Usage:
    python extract/parse_gkg.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def _isna(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "None", "nan")


def parse_v2tone(tone_str) -> dict:
    """Parse 'tone,posScore,negScore,polarity,activityRef,selfGroupRef,wordCount'."""
    keys = ["tone", "pos_score", "neg_score", "polarity",
            "activity_ref", "self_group_ref", "word_count"]
    if _isna(tone_str):
        return {k: None for k in keys}
    parts = str(tone_str).split(",")
    out = {}
    for k, v in zip(keys, parts):
        try:
            out[k] = float(v)
        except (ValueError, TypeError):
            out[k] = None
    for k in keys:
        out.setdefault(k, None)
    return out


def extract_subject_countries(v2locations) -> list[str]:
    """Extract ISO country codes from V2Locations (field index 2 of each block)."""
    if _isna(v2locations):
        return []
    countries = set()
    for block in str(v2locations).split(";"):
        parts = block.split("#")
        if len(parts) >= 3 and parts[2].strip():
            countries.add(parts[2].strip())
    return sorted(countries)


def extract_language(translation_info) -> str:
    """Extract source language from TranslationInfo; empty means original English."""
    if _isna(translation_info):
        return "eng"
    for part in str(translation_info).split(";"):
        part = part.strip()
        if part.startswith("srclc:"):
            return part.replace("srclc:", "")
    return "eng"


def identify_minerals(v2themes) -> list[str]:
    """Identify minerals from co-occurring GKG themes."""
    if _isna(v2themes):
        return ["unspecified"]
    themes = str(v2themes).upper()
    found = [m for m, tags in config.MINERAL_THEMES.items()
             if any(t in themes for t in tags)]
    return found if found else ["unspecified"]


def parse_date(date_str) -> pd.Timestamp:
    """GKG DATE is a YYYYMMDDHHMMSS string."""
    return pd.to_datetime(str(date_str), format="%Y%m%d%H%M%S", errors="coerce")


def main() -> None:
    df = pd.read_parquet(config.RAW_PARQUET)
    print(f"Loaded {len(df):,} raw rows")

    tone = df["V2Tone"].apply(parse_v2tone).apply(pd.Series)

    out = pd.DataFrame({
        "gkg_id": df["GKGRECORDID"],
        "date": df["DATE"].apply(parse_date),
        "url": df["DocumentIdentifier"],
        "source_domain": df["SourceCommonName"],
        "country": df["filter_match"].map(config.COUNTRY_OF_FILTER),
        "filter_type": df["filter_match"].map(config.FILTER_TYPE_OF_FILTER),
        "filter_match": df["filter_match"],
        "tone": tone["tone"],
        "pos_score": tone["pos_score"],
        "neg_score": tone["neg_score"],
        "polarity": tone["polarity"],
        "word_count": tone["word_count"],
        "subject_countries": df["V2Locations"].apply(extract_subject_countries),
        "original_language": df["TranslationInfo"].apply(extract_language),
        "minerals": df["V2Themes"].apply(identify_minerals),
        "themes_raw": df["V2Themes"],
        "quotations": df["V2Quotations"],
        "all_names": df["V2AllNames"],
    })

    config.PROCESSED_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(config.PROCESSED_PARQUET, index=False)
    print(f"Saved enriched dataset: {config.PROCESSED_PARQUET}")

    print("\n— Summary —")
    print(f"Date range: {out['date'].min()} → {out['date'].max()}")
    print(f"\nBy country:\n{out['country'].value_counts().to_string()}")
    print(f"\nBy filter type:\n{out['filter_type'].value_counts().to_string()}")
    print(f"\nTop languages:\n{out['original_language'].value_counts().head(8).to_string()}")
    print(f"\nMean tone by country:")
    print(out.groupby('country')['tone'].mean().round(3).to_string())
    mineral_counts = out['minerals'].explode().value_counts()
    print(f"\nMineral mentions:\n{mineral_counts.to_string()}")


if __name__ == "__main__":
    main()
