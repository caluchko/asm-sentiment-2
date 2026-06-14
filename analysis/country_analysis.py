"""Subject-country analysis: which countries articles are actually about
(from V2Locations), independent of the source/filter country."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def load() -> pd.DataFrame:
    return pd.read_parquet(config.PROCESSED_PARQUET)


def subject_country_counts(df: pd.DataFrame, country: str | None = None) -> pd.DataFrame:
    d = df if country is None else df[df["country"] == country]
    exploded = d[["country", "subject_countries"]].explode("subject_countries")
    exploded = exploded.dropna(subset=["subject_countries"])
    return (exploded.groupby("subject_countries").size()
            .sort_values(ascending=False).rename("articles").reset_index())


if __name__ == "__main__":
    df = load()
    for c in ("Ghana", "Brazil"):
        print(f"\nTop subject countries for {c}-filtered articles:")
        print(subject_country_counts(df, c).head(10).to_string(index=False))
