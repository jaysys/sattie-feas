#!/bin/sh
#
# one-shot-startup.sh
# -------------------
# Purpose:
#   Start the local feasibility demo API server.
#
# What it does:
#   1. Ensures `.runtime/` exists.
#   2. If `./venv` or `./db/feasibility_satti.db` is missing, runs `./one-shot-setup.sh`.
#   3. If the DB already exists, applies additive schema migrations with
#      `./bootstrap/migrate_db_schema.sh`.
#   4. Checks whether the configured port is already in use by some other process.
#   5. Starts the API server using `./src/run_api_server.sh`.
#   6. Waits until `http://127.0.0.1:6003/health` responds before reporting success.
#   7. Writes runtime metadata so the process can be stopped later.
#
# Cross-platform note:
#   - This script intentionally uses the same launch path on macOS and Linux.
#   - Background startup uses `nohup ... &` only; it does not switch to `setsid`
#     or other OS-specific launch commands.
#
# Default runtime values:
#   - Host: `127.0.0.1`
#   - Port: `6003`
#   - Reload: `on`
#
# Generated runtime files:
#   - PID file: `.runtime/api_server.pid`
#   - Log file: `.runtime/api_server.log`
#
# Behavior if already running:
#   - If a PID file exists and the process is still alive, the script exits without
#     starting another server.
#   - If no PID file exists but the port is already occupied, the script prints a
#     port-ownership diagnostic and exits with an error.
#
# Example:
#   ./one-shot-startup.sh
#   ./one-shot-startup.sh --no-reload
#
# After startup:
#   - Health check: `curl http://127.0.0.1:6003/health`
#   - Request list: `curl http://127.0.0.1:6003/requests`
#
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"
PID_FILE="$RUNTIME_DIR/api_server.pid"
LOG_FILE="$RUNTIME_DIR/api_server.log"
DB_PATH="$ROOT_DIR/db/feasibility_satti.db"
HOST="127.0.0.1"
PORT="6003"
PYTHON_BIN="$ROOT_DIR/venv/bin/python"
RELOAD_MODE="--reload"

if [ "${1:-}" = "--no-reload" ]; then
    RELOAD_MODE="--no-reload"
fi

print_port_owner() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true
    else
        echo "[startup] lsof command not available; cannot show port owner details" >&2
    fi
}

get_port_owner_pid() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1
    fi
}

print_port_kill_guide() {
    cat >&2 <<EOF
- 점유 프로세스 확인
  lsof -nP -iTCP:$PORT -sTCP:LISTEN

- 정상 종료 후 재기동
  kill \$(lsof -tiTCP:$PORT -sTCP:LISTEN) && ./one-shot-startup.sh

- 정상 종료가 안 되면 강제 종료 후 재기동
  kill -9 \$(lsof -tiTCP:$PORT -sTCP:LISTEN) && ./one-shot-startup.sh
EOF
}

port_in_use() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1
    else
        return 1
    fi
}

log_indicates_port_in_use() {
    if [ -f "$LOG_FILE" ]; then
        grep -E "Address already in use|Errno 48" "$LOG_FILE" >/dev/null 2>&1
    else
        return 1
    fi
}

cd "$ROOT_DIR"

mkdir -p "$RUNTIME_DIR"

if [ ! -d "$ROOT_DIR/venv" ] || [ ! -f "$DB_PATH" ]; then
    echo "[startup] environment missing, running setup first"
    "$ROOT_DIR/one-shot-setup.sh"
else
    echo "[startup] applying additive DB migrations"
    "$ROOT_DIR/bootstrap/migrate_db_schema.sh" "$DB_PATH" >/dev/null
fi

if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE")"
    if kill -0 "$PID" >/dev/null 2>&1; then
        echo "[startup] server already running with pid $PID"
        echo "url: http://$HOST:$PORT"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

if port_in_use; then
    echo "[startup] port $PORT is already in use, but no managed pid file is active" >&2
    echo "[startup] port owner detail:" >&2
    print_port_owner >&2
    print_port_kill_guide
    echo "[startup] stop the process above or free port $PORT, then run ./one-shot-startup.sh again" >&2
    exit 1
fi

echo "[startup] starting API server on $HOST:$PORT"
echo "[startup] reload mode: $RELOAD_MODE"
rm -f "$LOG_FILE"
nohup "$ROOT_DIR/src/run_api_server.sh" "$DB_PATH" "$HOST" "$PORT" "$RELOAD_MODE" >"$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" >"$PID_FILE"

I=0
while [ "$I" -lt 10 ]; do
    if ! kill -0 "$PID" >/dev/null 2>&1; then
        break
    fi

    if "$PYTHON_BIN" -c "import sys, urllib.request; urllib.request.urlopen('http://$HOST:$PORT/health', timeout=1).read(); sys.exit(0)" >/dev/null 2>&1; then
        echo "[startup] server started"
        echo "pid: $PID"
        echo "url: http://$HOST:$PORT"
        echo "log: $LOG_FILE"
        exit 0
    fi

    I=$((I + 1))
    sleep 1
done

echo "[startup] server failed to start" >&2
if port_in_use || log_indicates_port_in_use; then
    OWNER_PID="$(get_port_owner_pid || true)"
    if [ -n "$OWNER_PID" ]; then
        echo "[startup] port $PORT is currently occupied by:" >&2
        print_port_owner >&2
        print_port_kill_guide
        echo "[startup] since startup did not complete, the pid file has been removed" >&2
    else
        echo "[startup] startup log indicated a port-conflict condition, but no current listener was found on $PORT" >&2
        echo "[startup] this usually means a transient race or stale prior state; rerun ./one-shot-startup.sh" >&2
    fi
elif [ -f "$LOG_FILE" ]; then
    tail -n 40 "$LOG_FILE" >&2 || true
fi
rm -f "$PID_FILE"
exit 1
