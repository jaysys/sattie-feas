#!/bin/sh
#
# one-shot-reset-and-verify.sh
# ----------------------------
# Purpose:
#   End-to-end smoke test for DB reset, seed recovery, managed startup, health check,
#   and managed shutdown.
#
# What it does:
#   1. Stops the managed server if it is running.
#   2. Deletes `./db/feasibility_satti.db`.
#   3. Starts the app with `./one-shot-startup.sh`, which recreates the DB if missing.
#   4. Verifies `/health` responds.
#   5. Verifies seeded requests and request candidates exist.
#   6. Verifies seeded request candidates have no initial run history.
#   7. Stops the managed server.
#
# Notes:
#   - This script assumes port `6003` can be used by the app.
#   - If some other unmanaged process is already using `6003`, startup will fail and
#     the existing `one-shot-startup.sh` guidance will be shown.
#
# Example:
#   ./one-shot-reset-and-verify.sh
#
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
DB_PATH="$ROOT_DIR/db/feasibility_satti.db"
PYTHON_BIN="$ROOT_DIR/venv/bin/python"

cd "$ROOT_DIR"

./one-shot-stop.sh >/dev/null 2>&1 || true

if [ -f "$DB_PATH" ]; then
    echo "[reset-verify] removing existing DB: $DB_PATH"
    rm -f "$DB_PATH"
else
    echo "[reset-verify] DB already absent"
fi

echo "[reset-verify] starting app to trigger DB rebuild"
./one-shot-startup.sh

echo "[reset-verify] checking health endpoint"
"$PYTHON_BIN" - <<'PY'
import urllib.request
print(urllib.request.urlopen('http://127.0.0.1:6003/health', timeout=3).read().decode())
PY

echo "[reset-verify] checking seeded requests"
sqlite3 -header -column "$DB_PATH" "SELECT request_id, request_code, request_title FROM feasibility_request ORDER BY request_id;"

echo "[reset-verify] checking seeded request candidates"
sqlite3 -header -column "$DB_PATH" "SELECT request_id, candidate_code, candidate_title FROM request_candidate ORDER BY request_id, candidate_rank;"

echo "[reset-verify] checking seeded request candidate runs are empty"
sqlite3 -header -column "$DB_PATH" "SELECT COUNT(*) AS request_candidate_run_count FROM request_candidate_run;"

echo "[reset-verify] stopping app"
./one-shot-stop.sh

echo "[reset-verify] complete"
