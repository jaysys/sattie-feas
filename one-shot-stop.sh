#!/bin/sh
#
# one-shot-stop.sh
# ----------------
# Purpose:
#   Stop the local feasibility demo API server started by `./one-shot-startup.sh`.
#
# What it does:
#   1. Reads the server PID from `.runtime/api_server.pid`.
#   2. If the process is running, sends a normal `TERM`.
#   3. Waits up to 10 seconds for clean shutdown.
#   4. Removes stale PID files if the process is already gone.
#
# Behavior:
#   - If no PID file exists, the script exits successfully with a message.
#   - If the PID file exists but the process is already dead, the script removes the
#     stale PID file and exits successfully.
#   - If the process does not stop within 10 seconds, the script exits with an error.
#
# Example:
#   ./one-shot-stop.sh
#
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
PID_FILE="$ROOT_DIR/.runtime/api_server.pid"

cd "$ROOT_DIR"

if [ ! -f "$PID_FILE" ]; then
    echo "[stop] no pid file found"
    exit 0
fi

PID="$(cat "$PID_FILE")"

if ! kill -0 "$PID" >/dev/null 2>&1; then
    echo "[stop] process $PID is not running"
    rm -f "$PID_FILE"
    exit 0
fi

echo "[stop] stopping server pid $PID"
kill "$PID"

I=0
while kill -0 "$PID" >/dev/null 2>&1; do
    I=$((I + 1))
    if [ "$I" -ge 10 ]; then
        echo "[stop] process did not exit after 10 seconds" >&2
        exit 1
    fi
    sleep 1
done

rm -f "$PID_FILE"
echo "[stop] server stopped"
