"""Precision spot-check: emit ~50 article titles per country for manual relevance
review. Title is derived from the URL slug (GKG has no title field).

Fill in the `relevant` column (1/0) by hand, then run with --score to compute
precision per country.

Usage:
    python validate/precision_spotcheck.py            # write spotcheck CSV
    python validate/precision_spotcheck.py --score     # score a filled-in CSV
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

SPOTCHECK_CSV = config.VALIDATION_DIR / "precision_spotcheck.csv"
PER_COUNTRY = 50


def title_from_url(url: str) -> str:
    """Best-effort human-readable title from a news URL slug."""
    if not isinstance(url, str) or not url:
        return ""
    path = urlparse(url).path
    slug = re.sub(r"\.(html?|php|aspx?)$", "", path.rstrip("/").split("/")[-1])
    slug = re.sub(r"^\d{4,}[-_]?", "", slug)          # leading article IDs
    slug = re.sub(r"[-_]\d{4,}$", "", slug)            # trailing IDs
    words = re.split(r"[-_]+", slug)
    words = [w for w in words if w and not w.isdigit()]
    return " ".join(words).strip().capitalize()


def build() -> None:
    df = pd.read_parquet(config.PROCESSED_PARQUET)
    df = df[df["country"].isin(["Ghana", "Brazil"])].copy()
    df["title_guess"] = df["url"].apply(title_from_url)

    rng_seed = 42
    samples = []
    for country in ("Ghana", "Brazil"):
        sub = df[df["country"] == country]
        n = min(PER_COUNTRY, len(sub))
        samples.append(sub.sample(n=n, random_state=rng_seed))
    out = pd.concat(samples)[
        ["country", "filter_type", "source_domain", "title_guess", "url"]
    ].reset_index(drop=True)
    out["relevant"] = ""  # to be filled in manually: 1 = about ASM, 0 = not

    SPOTCHECK_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(SPOTCHECK_CSV, index=False)
    print(f"Wrote {len(out)} rows to {SPOTCHECK_CSV}")
    print("Fill the 'relevant' column (1/0), then re-run with --score.")


def score() -> None:
    df = pd.read_csv(SPOTCHECK_CSV)
    df = df[df["relevant"].astype(str).str.strip().isin(["0", "1"])]
    if df.empty:
        print("No labelled rows yet. Fill the 'relevant' column with 1/0 first.")
        return
    df["relevant"] = df["relevant"].astype(int)
    print("Precision (manual spot-check):")
    for country, g in df.groupby("country"):
        print(f"  {country}: {g['relevant'].mean():.1%} relevant ({g['relevant'].sum()}/{len(g)})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", action="store_true")
    args = ap.parse_args()
    score() if args.score else build()


if __name__ == "__main__":
    main()
