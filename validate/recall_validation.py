"""Recall validation: what fraction of Phase 1.5 DOC API keyword results does the
BigQuery keyword-in-metadata extraction recover?

Phase 1.5 cached DOC API `artlist` responses for a 3-month window (2026-02-24 →
2026-05-25). We re-run the SAME BigQuery filter logic over that identical window
and measure URL overlap. Lower recall is expected because not every keyword
appears in the URL / quotes / names that GKG exposes — that gap is the documented
methodology limitation.

Usage:
    python validate/recall_validation.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from glob import glob
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from extract.bigquery_extract import run_bq  # noqa: E402

PHASE15_CACHE = Path("/Users/kennethdavis/Projects/ASM-sentiment-1.5/cache")

# DOC API window of the cached artlist responses.
VAL_START = "2026-02-24"
VAL_END = "2026-05-26"  # exclusive; cache enddatetime is 2026-05-25 23:59:59

# Which cached DOC API queries form the reference set for each country. We compare
# against the primary keyword filters (galamsey / garimpo) plus "illegal mining".
REFERENCE_QUERIES = {
    "Ghana": ["galamsey sourcecountry:GH", '"illegal mining" sourcecountry:GH'],
    "Brazil": ["garimpo sourcecountry:BR"],
}


def normalize_url(u: str) -> str:
    """Canonicalize a URL for set comparison: drop scheme, leading www, trailing /."""
    if not u:
        return ""
    u = u.strip()
    p = urllib.parse.urlparse(u if "//" in u else "//" + u)
    host = (p.netloc or "").lower().removeprefix("www.")
    path = re.sub(r"/+$", "", p.path)
    return f"{host}{path}".lower()


def load_doc_api_urls() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return ({country: urls}, {query: urls}) from cached DOC API artlist responses."""
    by_country: dict[str, set[str]] = {c: set() for c in REFERENCE_QUERIES}
    by_query: dict[str, set[str]] = {}
    wanted = {q: c for c, qs in REFERENCE_QUERIES.items() for q in qs}
    for f in glob(str(PHASE15_CACHE / "*.json")):
        if f.endswith(".fail.json"):
            continue
        d = json.load(open(f))
        if d.get("mode") != "artlist":
            continue
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(d["url"]).query)
        query = qs.get("query", [""])[0]
        if query not in wanted:
            continue
        try:
            arts = json.loads(d.get("response_text", "{}")).get("articles", [])
        except json.JSONDecodeError:
            arts = []
        urls = {normalize_url(a.get("url", "")) for a in arts} - {""}
        by_country[wanted[query]] |= urls
        by_query.setdefault(query, set()).update(urls)
    return by_country, by_query


def bigquery_window_urls() -> pd.DataFrame:
    """Run the canonical extraction filters over the validation window (cached)."""
    cache = config.VALIDATION_DIR / "bigquery_validation_window.parquet"
    if cache.exists():
        print(f"  (reusing cached BigQuery window: {cache.name}; delete to re-query)")
        return pd.read_parquet(cache)
    sql = config.EXTRACTION_QUERY_SQL.read_text()
    sql = sql.replace('TIMESTAMP("2025-01-01")', f'TIMESTAMP("{VAL_START}")')
    sql = sql.replace('TIMESTAMP("2026-01-01")', f'TIMESTAMP("{VAL_END}")')
    out = run_bq(sql)
    rows = json.loads(out) if out.strip() else []
    df = pd.DataFrame(rows)
    df["country"] = df["filter_match"].map(config.COUNTRY_OF_FILTER)
    df["norm_url"] = df["DocumentIdentifier"].apply(normalize_url)
    return df


def main() -> None:
    print(f"Validation window: {VAL_START} → {VAL_END}")
    doc, by_query = load_doc_api_urls()
    for c, urls in doc.items():
        print(f"  DOC API {c}: {len(urls)} unique URLs")

    print("\nRunning BigQuery extraction for the validation window...")
    bq = bigquery_window_urls()
    print(f"  BigQuery rows: {len(bq):,}")

    # Map each reference query to the country whose BigQuery URL set it compares against.
    query_country = {q: c for c, qs in REFERENCE_QUERIES.items() for q in qs}
    bq_by_country = {c: set(bq.loc[bq["country"] == c, "norm_url"]) - {""}
                     for c in REFERENCE_QUERIES}

    results = []
    print("\n— Recall by reference query (the decision-relevant view) —")
    for query, doc_urls in sorted(by_query.items()):
        country = query_country[query]
        bq_urls = bq_by_country[country]
        overlap = doc_urls & bq_urls
        recall = len(overlap) / len(doc_urls) if doc_urls else float("nan")
        results.append({"scope": f"query: {query}", "country": country,
                        "doc_api_urls": len(doc_urls), "bigquery_urls": len(bq_urls),
                        "overlap": len(overlap), "recall": round(recall, 3)})
        print(f"  {query:45s} recall={recall:5.1%}  ({len(overlap)}/{len(doc_urls)})")

    print("\n— Recall by country (combined reference set) —")
    for country, doc_urls in doc.items():
        if not doc_urls:
            continue
        bq_urls = bq_by_country[country]
        overlap = doc_urls & bq_urls
        recall = len(overlap) / len(doc_urls)
        results.append({"scope": "country (combined)", "country": country,
                        "doc_api_urls": len(doc_urls), "bigquery_urls": len(bq_urls),
                        "overlap": len(overlap), "recall": round(recall, 3)})
        print(f"  {country:45s} recall={recall:5.1%}  ({len(overlap)}/{len(doc_urls)})")

    res_df = pd.DataFrame(results)
    out_path = config.VALIDATION_DIR / "recall_summary.csv"
    res_df.to_csv(out_path, index=False)
    bq.to_parquet(config.VALIDATION_DIR / "bigquery_validation_window.parquet", index=False)
    print(f"\nSaved: {out_path}")
    # Judge on the PRIMARY keyword filter (galamsey for Ghana), not the combined set
    # that includes the weak full-text "illegal mining" query.
    primary = res_df[res_df["scope"] == "query: galamsey sourcecountry:GH"]["recall"]
    if len(primary):
        r = float(primary.iloc[0])
        verdict = (">70% — methodology defensible" if r >= 0.7
                   else "50–70% — usable with documented caveat" if r >= 0.5
                   else "<50% — keyword-in-metadata misses many full-text matches; document as a key limitation")
        print(f"Primary filter (galamsey) recall: {r:.1%} → {verdict}")


if __name__ == "__main__":
    main()
