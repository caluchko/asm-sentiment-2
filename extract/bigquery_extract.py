"""Run the GKG extraction query and export results to local parquet.

Drives the `bq` CLI (already authenticated via `gcloud auth login`) rather than
the BigQuery Python client, because Application Default Credentials are not set
up on this machine. Always passes the 1 TB --maximum_bytes_billed safety cap.

Usage:
    python extract/bigquery_extract.py            # run for real
    python extract/bigquery_extract.py --dry-run  # estimate bytes only
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

# bq/gcloud need a compatible Python; brew's pyexpat is broken, so pin 3.13.
BQ_ENV = {
    **os.environ,
    "CLOUDSDK_PYTHON": os.environ.get("CLOUDSDK_PYTHON", "/opt/homebrew/bin/python3.13"),
    "PATH": os.path.expanduser("~/google-cloud-sdk/bin") + os.pathsep + os.environ.get("PATH", ""),
}


def run_bq(sql: str, dry_run: bool = False) -> str:
    """Run SQL via the authenticated bq CLI; return JSON stdout (rows) or dry-run text."""
    cmd = [
        "bq", "query",
        f"--project_id={config.GCP_PROJECT}",
        "--use_legacy_sql=false",
        f"--maximum_bytes_billed={config.MAX_BYTES_BILLED}",
        "--format=json",
        "--max_rows=10000000",
    ]
    if dry_run:
        cmd.append("--dry_run")
    print(f"$ {' '.join(cmd)} < extraction_query.sql", file=sys.stderr)
    proc = subprocess.run(cmd, input=sql, env=BQ_ENV,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"bq exited {proc.returncode}")
    return proc.stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Estimate bytes scanned without running the query.")
    args = ap.parse_args()

    out = run_bq(config.EXTRACTION_QUERY_SQL.read_text(), dry_run=args.dry_run)
    if args.dry_run:
        print(out or "(dry-run complete; see stderr for bytes)")
        return

    import pandas as pd

    rows = json.loads(out) if out.strip() else []
    df = pd.DataFrame(rows)
    config.RAW_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(config.RAW_PARQUET, index=False)

    print(f"Rows extracted: {len(df):,}")
    print(f"Saved to: {config.RAW_PARQUET}")
    if "filter_match" in df.columns and len(df):
        print("\nfilter_match breakdown:")
        print(df["filter_match"].value_counts().to_string())


if __name__ == "__main__":
    main()
