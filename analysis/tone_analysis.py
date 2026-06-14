"""Per-article tone trends by country."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def load() -> pd.DataFrame:
    return pd.read_parquet(config.PROCESSED_PARQUET)


def monthly_tone(df: pd.DataFrame) -> pd.DataFrame:
    """Mean tone and article volume per month per country."""
    d = df[df["country"].isin(["Ghana", "Brazil"])].dropna(subset=["date"]).copy()
    d["month"] = d["date"].dt.to_period("M").dt.to_timestamp()
    out = (d.groupby(["month", "country"])
             .agg(mean_tone=("tone", "mean"), volume=("gkg_id", "count"))
             .reset_index())
    return out


def tone_distribution(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["country"].isin(["Ghana", "Brazil"])][["country", "tone"]].dropna()


if __name__ == "__main__":
    df = load()
    mt = monthly_tone(df)
    print(mt.pivot(index="month", columns="country", values="mean_tone").round(2).to_string())
