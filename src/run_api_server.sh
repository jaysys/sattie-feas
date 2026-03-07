#!/bin/sh
#
# run_api_server.sh
# -----------------
# Purpose:
#   Low-level launcher for the local feasibility demo API server.
#
# What it does:
#   - Exports the SQLite DB path for the FastAPI app factory.
#   - Starts the app with the `uvicorn` CLI against `src.api_server:create_app_from_env`.
#   - Passes through DB path, host, port, and reload mode arguments.
#
# Default values:
#   - DB path: `./db/feasibility_satti.db`
#   - Host: `127.0.0.1`
#   - Port: `6003`
#   - Reload: `on`
#
# Intended use:
#   - Direct manual launch when you only want to start the server process itself.
#   - Internal helper used by `./one-shot-startup.sh`.
#
# Important distinction:
#   - This script does NOT manage PID files, log files, backgrounding, readiness checks,
#     or automatic environment setup.
#   - If you want the full managed startup flow, use `./one-shot-startup.sh` instead.
#
# Examples:
#   ./src/run_api_server.sh
#   ./src/run_api_server.sh ./db/feasibility_satti.db
#   ./src/run_api_server.sh ./db/feasibility_satti.db 127.0.0.1 6003
#   ./src/run_api_server.sh ./db/feasibility_satti.db 127.0.0.1 6003 --no-reload
#
set -eu

DB_PATH="${1:-./db/feasibility_satti.db}"
HOST="${2:-127.0.0.1}"
PORT="${3:-6003}"
RELOAD_MODE="${4:---reload}"

export FEASIBILITY_DB_PATH="$DB_PATH"

if [ "$RELOAD_MODE" = "--no-reload" ]; then
    exec ./venv/bin/uvicorn src.api_server:create_app_from_env --factory --host "$HOST" --port "$PORT"
fi

exec ./venv/bin/uvicorn src.api_server:create_app_from_env --factory --host "$HOST" --port "$PORT" --reload --reload-dir ./src
