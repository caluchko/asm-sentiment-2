"""Classify the stratified sample with the Claude API.

Fetches article text (with GKG-metadata fallback), prompts Claude for a
structured framing classification, and caches every result to disk so reruns
are incremental. Requires ANTHROPIC_API_KEY in the environment.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python classify/run_classification.py            # classify the sample
    python classify/run_classification.py --limit 10  # smoke-test on 10 articles
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from classify.fetch_text import get_article_text  # noqa: E402
from classify.prompt import SYSTEM_PROMPT, build_prompt  # noqa: E402
from classify.sample import SAMPLE_PARQUET  # noqa: E402

RESULTS_JSONL = config.CLASSIFIED_DIR / "classifications.jsonl"


def load_done() -> set[str]:
    if not RESULTS_JSONL.exists():
        return set()
    done = set()
    with open(RESULTS_JSONL) as f:
        for line in f:
            try:
                done.add(json.loads(line)["gkg_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def parse_json_block(text: str) -> dict:
    """Extract the JSON object from the model response."""
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in response")
    return json.loads(text[start:end + 1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--input", type=str, default=str(SAMPLE_PARQUET),
                    help="Parquet of articles to classify (default: the stratified sample).")
    args = ap.parse_args()

    # Prefer the env var; fall back to a locked-down key file so the secret never
    # has to be typed inline. See README for how to create it.
    if not os.environ.get("ANTHROPIC_API_KEY"):
        key_file = Path.home() / ".config" / "anthropic_key"
        if key_file.exists():
            os.environ["ANTHROPIC_API_KEY"] = key_file.read_text().strip()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("No API key. Set ANTHROPIC_API_KEY or create ~/.config/anthropic_key.")

    from anthropic import Anthropic

    client = Anthropic()
    df = pd.read_parquet(args.input)
    if args.limit:
        df = df.head(args.limit)

    done = load_done()
    print(f"{len(df)} sampled; {len(done)} already classified.")

    n_full = n_fallback = n_skip = n_ok = n_err = 0
    with open(RESULTS_JSONL, "a") as out:
        for _, row in df.iterrows():
            gkg_id = row["gkg_id"]
            if gkg_id in done:
                continue

            text, text_source = get_article_text(row)
            n_full += text_source == "fulltext"
            n_fallback += text_source == "fallback"

            # No full text and no quotes: only themes+tone+URL remain, which are
            # circular with the discovery filter. Log it as excluded and skip the
            # API call entirely (saves tokens) — it never enters the analysis set.
            if text_source == "none":
                out.write(json.dumps({
                    "gkg_id": gkg_id, "country": row["country"], "url": row["url"],
                    "tone": row["tone"], "filter_type": row["filter_type"],
                    "text_source": "none", "excluded": "no_text_or_quotes",
                }) + "\n")
                out.flush()
                n_skip += 1
                continue

            try:
                msg = client.messages.create(
                    model=config.CLAUDE_MODEL,
                    max_tokens=1024,
                    system=[{
                        "type": "text", "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    messages=[{"role": "user", "content": build_prompt(text)}],
                )
                classification = parse_json_block(msg.content[0].text)
                record = {
                    "gkg_id": gkg_id,
                    "country": row["country"],
                    "url": row["url"],
                    "tone": row["tone"],
                    "filter_type": row["filter_type"],
                    "text_source": text_source,
                    **classification,
                }
                n_ok += 1
            except Exception as e:  # noqa: BLE001
                record = {"gkg_id": gkg_id, "country": row["country"],
                          "url": row["url"], "error": str(e),
                          "text_source": text_source}
                n_err += 1

            out.write(json.dumps(record) + "\n")
            out.flush()
            time.sleep(config.CLASSIFY_DELAY_S)

    print(f"\nDone. ok={n_ok} err={n_err} skipped(no text/quotes)={n_skip} "
          f"| text: fulltext={n_full} fallback={n_fallback}")
    print(f"Results: {RESULTS_JSONL}")


if __name__ == "__main__":
    main()
