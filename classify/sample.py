"""Stratified sampling for Claude classification.

Selects ~SAMPLE_SIZE articles stratified by country, tone tercile, and filter
type so the classified subset spans the sentiment and discovery-method space.

Usage:
    python classify/sample.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

SAMPLE_PARQUET = config.CLASSIFIED_DIR / "sample.parquet"


def main() -> None:
    df = pd.read_parquet(config.PROCESSED_PARQUET)
    df = df[df["country"].isin(["Ghana", "Brazil"])].copy()
    df = df.dropna(subset=["tone"])

    # Tone tercile within each country.
    df["tone_tercile"] = df.groupby("country")["tone"].transform(
        lambda s: pd.qcut(s, 3, labels=["negative", "neutral", "positive"], duplicates="drop")
    )

    strata = ["country", "tone_tercile", "filter_type"]
    n_strata = df.groupby(strata, observed=True).ngroups
    per_stratum = max(1, config.SAMPLE_SIZE // max(1, n_strata))

    sampled = (
        df.groupby(strata, observed=True, group_keys=False)
        .apply(lambda g: g.sample(n=min(len(g), per_stratum), random_state=42))
    )

    # Top up to the target size if rounding left us short.
    if len(sampled) < config.SAMPLE_SIZE:
        remaining = df.drop(sampled.index)
        extra = remaining.sample(
            n=min(len(remaining), config.SAMPLE_SIZE - len(sampled)), random_state=42
        )
        sampled = pd.concat([sampled, extra])

    sampled = sampled.reset_index(drop=True)
    sampled.to_parquet(SAMPLE_PARQUET, index=False)

    print(f"Sampled {len(sampled)} articles → {SAMPLE_PARQUET}")
    print("\nBy country:")
    print(sampled["country"].value_counts().to_string())
    print("\nBy tone tercile:")
    print(sampled["tone_tercile"].value_counts().to_string())
    print("\nBy filter type:")
    print(sampled["filter_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
