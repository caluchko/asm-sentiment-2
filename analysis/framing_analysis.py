"""Analysis of Claude framing classifications."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from classify.fetch_text import has_quotes  # noqa: E402
from classify.sample import SAMPLE_PARQUET  # noqa: E402

RESULTS_JSONL = config.CLASSIFIED_DIR / "classifications.jsonl"


def _attach_text_quality(df: pd.DataFrame) -> pd.DataFrame:
    """Add a `text_quality` tier in {'fulltext', 'fallback', 'none'}.

    'none' means no full text AND no quotes — themes+tone+URL only, which is
    circular with the discovery filter, so these are excluded from analysis.
    New runs already record text_source='none' for these. Older results predate
    that and labelled them 'fallback', so we recover the tier by re-checking the
    GKG quotations from the sample parquet.
    """
    if df.empty or "text_source" not in df.columns:
        return df
    quotes = {}
    if SAMPLE_PARQUET.exists():
        s = pd.read_parquet(SAMPLE_PARQUET, columns=["gkg_id", "quotations"])
        quotes = dict(zip(s["gkg_id"], s["quotations"]))

    def quality(row) -> str:
        ts = row.get("text_source")
        if ts == "fulltext":
            return "fulltext"
        if ts == "none":
            return "none"
        # 'fallback' (or unknown): keep only if real quotes back it.
        return "fallback" if has_quotes(quotes.get(row.get("gkg_id"))) else "none"

    df = df.copy()
    df["text_quality"] = df.apply(quality, axis=1)
    return df


def load() -> pd.DataFrame:
    """Load classification results; empty DataFrame if none yet."""
    if not RESULTS_JSONL.exists():
        return pd.DataFrame()
    records = []
    with open(RESULTS_JSONL) as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    df = pd.DataFrame(records)
    if "error" in df.columns:
        df = df[df["error"].isna()] if df["error"].notna().any() else df
    return _attach_text_quality(df)


def classified(df: pd.DataFrame) -> pd.DataFrame:
    """Articles actually sent to Claude — excludes the no-text/quotes tier."""
    if df.empty or "text_quality" not in df.columns:
        return df
    return df[df["text_quality"] != "none"]


def relevant_only(df: pd.DataFrame) -> pd.DataFrame:
    """The analysis set: classifiable articles Claude judged actually about ASM.

    Excludes both the no-text/quotes tier (not classifiable) and the not-relevant
    tier (false positives). All framing/stance/solution reporting runs on this.
    """
    d = classified(df)
    if d.empty or "is_relevant" not in d.columns:
        return d
    return d[d["is_relevant"] == True]  # noqa: E712


def funnel(df: pd.DataFrame, by_country: bool = False):
    """Sampling funnel counts. Returns a dict (overall) or DataFrame (per country):
    sampled → excluded_no_text → classified → excluded_not_relevant → analysis."""
    def counts(d: pd.DataFrame) -> dict:
        no_text = int((d["text_quality"] == "none").sum()) if "text_quality" in d else 0
        clf = len(d) - no_text
        rel = len(relevant_only(d))
        return {
            "sampled": len(d),
            "excluded_no_text": no_text,
            "classified": clf,
            "excluded_not_relevant": clf - rel,
            "analysis": rel,
        }

    if df.empty:
        return pd.DataFrame() if by_country else counts(df)
    if not by_country:
        return counts(df)
    rows = [{"country": c, **counts(g)} for c, g in df.groupby("country")]
    return pd.DataFrame(rows)


def false_positive_rate(df: pd.DataFrame) -> pd.DataFrame:
    """Per-country precision diagnostic: share of CLASSIFIED articles Claude judged
    NOT actually about ASM. The no-text/quotes tier is excluded from the denominator
    (those are never classified in current runs). Columns: country, classified,
    not_relevant, fp_rate."""
    d = classified(df)
    if d.empty or "is_relevant" not in d.columns:
        return pd.DataFrame(columns=["country", "classified", "not_relevant", "fp_rate"])
    g = d.groupby("country")["is_relevant"]
    out = pd.DataFrame({
        "classified": g.size(),
        "not_relevant": g.apply(lambda s: (s == False).sum()),  # noqa: E712
    }).reset_index()
    out["fp_rate"] = (out["not_relevant"] / out["classified"]).round(3)
    return out


# Framings that occur often enough to read individually; the rest collapse to
# "other" so the 100%-stacked bars and heatmaps stay legible at n~200.
FRAMING_TOP = ["criminal_illegal", "policy_progress", "health_hazard",
               "environmental_threat"]
# Valence orderings so categorical axes read most→least critical / problem-focused.
STANCE_ORDER = ["critical", "mixed", "neutral", "sympathetic"]
SOLUTION_ORDER = ["problem_focused", "balanced", "solution_focused", "not_applicable"]


def _as_list(x) -> list[str]:
    if isinstance(x, (list, tuple)):
        items = list(x)
    elif x is None:
        items = []
    else:
        s = str(x)
        items = [] if s in ("None", "nan") else s.split(",")
    return [str(i).strip().lower() for i in items if str(i).strip()]


def with_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Add columns used by the dashboard's classification views:

    - `mineral_class`   — 'gold' if gold is among the GKG minerals, else 'non-gold'.
    - `framing_grouped` — framing with the rare tail collapsed to 'other'.
    """
    if df.empty:
        return df
    d = df.copy()
    if "minerals" in d.columns:
        d["mineral_class"] = d["minerals"].map(
            lambda m: "gold" if "gold" in _as_list(m) else "non-gold")
    if "framing" in d.columns:
        d["framing_grouped"] = d["framing"].where(
            d["framing"].isin(FRAMING_TOP), "other")
    return d


def framing_by_country(df: pd.DataFrame) -> pd.DataFrame:
    d = relevant_only(df)
    return (d.groupby(["country", "framing"]).size()
            .rename("articles").reset_index()
            .sort_values("articles", ascending=False))


def stance_by_country(df: pd.DataFrame) -> pd.DataFrame:
    d = relevant_only(df)
    return (d.groupby(["country", "stance"]).size()
            .rename("articles").reset_index())


if __name__ == "__main__":
    df = load()
    if df.empty:
        print("No classifications yet. Run classify/run_classification.py first.")
    else:
        print(f"{len(df)} classified articles\n")
        print("Framing by country:")
        print(framing_by_country(df).to_string(index=False))
