"""Mineral disaggregation from co-occurring GKG themes."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def load() -> pd.DataFrame:
    return pd.read_parquet(config.PROCESSED_PARQUET)


def mineral_counts(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["country"].isin(["Ghana", "Brazil"])]
    exploded = d[["country", "minerals"]].explode("minerals")
    return (exploded.groupby(["country", "minerals"]).size()
            .rename("articles").reset_index()
            .sort_values("articles", ascending=False))


if __name__ == "__main__":
    print(mineral_counts(load()).to_string(index=False))
