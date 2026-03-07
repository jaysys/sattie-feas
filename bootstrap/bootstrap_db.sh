#!/bin/sh
#
# bootstrap_db.sh
# ---------------
# Purpose:
#   Recreate the SQLite demo database from the canonical bootstrap assets in this folder.
#
# What it does:
#   1. Deletes the target DB file if it already exists.
#   2. Applies `schema.sql`.
#   3. Applies `seed.sql`.
#
# Usage:
#   ./bootstrap/bootstrap_db.sh
#   ./bootstrap/bootstrap_db.sh ./db/feasibility_satti.db
#
# Output:
#   - Rebuilt SQLite DB file at the target path
#
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
ROOT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
DB_PATH="${1:-$ROOT_DIR/db/feasibility_satti.db}"
SCHEMA_SQL="$SCRIPT_DIR/schema.sql"
SEED_SQL="$SCRIPT_DIR/seed.sql"

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "sqlite3 command not found" >&2
    exit 1
fi

mkdir -p "$(dirname "$DB_PATH")"
rm -f "$DB_PATH"
sqlite3 "$DB_PATH" < "$SCHEMA_SQL"
sqlite3 "$DB_PATH" < "$SEED_SQL"

echo "Initialized SQLite database at: $DB_PATH"
