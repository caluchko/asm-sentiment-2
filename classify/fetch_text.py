"""Fetch article full text with a GKG-metadata fallback.

For each URL we try trafilatura; if the page is dead/paywalled we synthesize a
context block from the GKG quotations, themes, and tone so the classifier still
has something substantive to work with.
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 15


def fetch_url(url: str) -> str | None:
    """Return extracted main text, or None on failure."""
    try:
        import trafilatura
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        if resp.status_code != 200 or not resp.text:
            return None
        text = trafilatura.extract(resp.text, include_comments=False,
                                   include_tables=False)
        return text or None
    except Exception:
        return None


def quote_snippets(quotations) -> list[str]:
    """Extract the quote text from a GKG Quotations field.

    Field format: "quote|speaker|...;quote|speaker|...". Returns the (non-empty)
    quote strings only. This is the single source of truth for "does this article
    carry any quoted speech" — used both to build the fallback context and to
    decide whether an article is classifiable at all.
    """
    q = str(quotations or "")
    if q in ("", "None", "nan"):
        return []
    snippets = []
    for seg in q.split(";"):
        parts = seg.split("|")
        if parts and parts[0].strip():
            snippets.append(parts[0].strip())
    return snippets


def has_quotes(quotations) -> bool:
    """True if the GKG Quotations field carries any quoted speech."""
    return bool(quote_snippets(quotations))


def fallback_context(row) -> str:
    """Build a context block from GKG metadata when full text is unavailable."""
    parts = []
    snippets = quote_snippets(row.get("quotations"))
    if snippets:
        parts.append("Quoted speech:\n" + "\n".join(f"- {s}" for s in snippets[:15]))
    themes = str(row.get("themes_raw") or "")
    if themes and themes not in ("None", "nan"):
        tags = [t.split(",")[0] for t in themes.split(";") if t][:30]
        parts.append("GKG themes: " + ", ".join(tags))
    parts.append(f"Tone score: {row.get('tone')}  (pos {row.get('pos_score')}, "
                 f"neg {row.get('neg_score')})")
    parts.append(f"Source: {row.get('source_domain')}  URL: {row.get('url')}")
    return "\n\n".join(parts)


def truncate_words(text: str, max_words: int = config.MAX_ARTICLE_WORDS) -> str:
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words])


def get_article_text(row) -> tuple[str, str]:
    """Return (text, source) where source is 'fulltext', 'fallback', or 'none'.

    - 'fulltext'  — real article text was fetched.
    - 'fallback'  — full text failed but GKG carries quoted speech, so the
                    metadata context block is substantive enough to classify.
    - 'none'      — no full text AND no quotes. The only signal left would be
                    themes+tone+URL, which is circular with the filter that
                    surfaced the article; we refuse to classify it (returns "").
    """
    text = fetch_url(row.get("url", ""))
    if text and len(text.split()) >= 50:
        return truncate_words(text), "fulltext"
    if has_quotes(row.get("quotations")):
        return truncate_words(fallback_context(row)), "fallback"
    return "", "none"
