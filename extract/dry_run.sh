#!/usr/bin/env bash
# Dry-run the extraction query to verify bytes scanned BEFORE spending any quota.
# Usage: ./extract/dry_run.sh [PROJECT_ID]
# If PROJECT_ID is omitted, the bq default project is used.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUERY_FILE="$SCRIPT_DIR/extraction_query.sql"

PROJECT_ARG=()
if [[ $# -ge 1 && -n "${1:-}" ]]; then
  PROJECT_ARG=(--project_id "$1")
fi

echo "Dry-running extraction query (no bytes billed)..."
bq query \
  "${PROJECT_ARG[@]}" \
  --use_legacy_sql=false \
  --dry_run \
  --flagfile=/dev/null \
  < "$QUERY_FILE"
