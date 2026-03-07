#!/bin/sh
#
# run_test_scenarios.sh
# ---------------------
# Purpose:
#   Execute the bundled input SQL checks and derived request-evaluation checks.
#   Use `--pristine` when you want deterministic seed verification from a fresh
#   temporary database rebuilt from `bootstrap/schema.sql` + `bootstrap/seed.sql`.
#
# What it does:
#   1. Runs optical request/input verification SQL.
#   2. Runs SAR request/input verification SQL.
#   3. Runs request-candidate verification SQL.
#   4. Prints request-level evaluations derived from the current candidate inputs.
#
# Usage:
#   ./bootstrap/run_test_scenarios.sh
#   ./bootstrap/run_test_scenarios.sh ./db/feasibility_satti.db
#   ./bootstrap/run_test_scenarios.sh --pristine
#
# Output:
#   - Column-formatted scenario query results in the current terminal
#
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
ROOT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
DB_PATH="$ROOT_DIR/db/feasibility_satti.db"
PRISTINE=0
TMP_DB=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --pristine)
            PRISTINE=1
            ;;
        *)
            DB_PATH="$1"
            ;;
    esac
    shift
done

cleanup() {
    if [ -n "$TMP_DB" ] && [ -f "$TMP_DB" ]; then
        rm -f "$TMP_DB"
    fi
}

trap cleanup EXIT INT TERM

if [ "$PRISTINE" -eq 1 ]; then
    TMP_DB="$(mktemp "${TMPDIR:-/tmp}/feasibility_satti_pristine.XXXXXX")"
    "$SCRIPT_DIR/bootstrap_db.sh" "$TMP_DB" >/dev/null
    DB_PATH="$TMP_DB"
    echo "[run-test] using pristine bootstrap database: $DB_PATH"
else
    echo "[run-test] using current database: $DB_PATH"
fi

echo "[optical scenarios]"
sqlite3 -header -column "$DB_PATH" < "$SCRIPT_DIR/test_optical_scenarios.sql"
echo
echo "[sar scenarios]"
sqlite3 -header -column "$DB_PATH" < "$SCRIPT_DIR/test_sar_scenarios.sql"
echo
echo "[request candidate scenarios]"
sqlite3 -header -column "$DB_PATH" < "$SCRIPT_DIR/test_request_candidate_scenarios.sql"
echo
echo "[derived request evaluations]"
"$ROOT_DIR/venv/bin/python" "$SCRIPT_DIR/print_current_request_evaluations.py" "$DB_PATH"
echo
"$ROOT_DIR/venv/bin/python" "$SCRIPT_DIR/validate_gap_features.py" "$DB_PATH"
