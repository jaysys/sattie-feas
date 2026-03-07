#!/bin/sh
#
# one-shot-setup.sh
# -----------------
# Purpose:
#   Prepare the local demo environment from scratch or refresh it to a known-good state.
#
# What it does:
#   1. Ensures `python3` and `sqlite3` are available.
#   2. Creates `./venv` if it does not already exist.
#   3. Installs Python dependencies from `./requirements.txt`.
#   4. Ensures project helper scripts are executable.
#   5. Creates or rebuilds `./db/feasibility_satti.db`.
#   6. Compiles Python sources under `./src`.
#   7. Runs optical/SAR scenario checks and repository smoke tests.
#
# Default DB behavior:
#   - If `./db/feasibility_satti.db` does not exist:
#       Create a new database from `bootstrap/schema.sql` + `bootstrap/seed.sql`.
#   - If `./db/feasibility_satti.db` already exists:
#       Create a timestamped backup like `db/archive/feasibility_satti.db.YYYYMMDDHHMMSS.bak`
#       and then rebuild the database.
#
# Options:
#   --force
#       Rebuild the database even if it already exists.
#       In the current script this still rebuilds the DB; the useful difference is mainly
#       to make intent explicit in automation.
#   --no-backup
#       Rebuild the DB without creating a `.bak` copy first.
#   -h, --help
#       Print usage and exit.
#
# Examples:
#   ./one-shot-setup.sh
#   ./one-shot-setup.sh --no-backup
#   ./one-shot-setup.sh --force
#
# Outputs:
#   - Virtual environment: `./venv`
#   - Installed Python packages from `./requirements.txt`
#   - SQLite database: `./db/feasibility_satti.db`
#   - Optional DB backup: `./db/archive/feasibility_satti.db.<timestamp>.bak`
#
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"
DB_PATH="$ROOT_DIR/db/feasibility_satti.db"
DB_ARCHIVE_DIR="$ROOT_DIR/db/archive"
REQUIREMENTS_FILE="$ROOT_DIR/requirements.txt"
FORCE=0
NO_BACKUP=0

usage() {
    cat <<'EOF'
Usage: ./one-shot-setup.sh [--force] [--no-backup]

Options:
  --force      Rebuild the demo database even if it already exists.
  --no-backup  Do not create a timestamped backup before rebuilding.
  -h, --help   Show this help.

Default behavior:
  - If the DB does not exist, create it.
  - If the DB exists, create a timestamped .bak copy and rebuild it.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --force)
            FORCE=1
            ;;
        --no-backup)
            NO_BACKUP=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

cd "$ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 command not found" >&2
    exit 1
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "sqlite3 command not found" >&2
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "[setup] creating virtual environment"
    python3 -m venv "$VENV_DIR"
else
    echo "[setup] virtual environment already exists"
fi

echo "[setup] installing Python dependencies"
"$VENV_DIR/bin/pip" install -r "$REQUIREMENTS_FILE"

echo "[setup] making scripts executable"
chmod +x \
    "$ROOT_DIR/bootstrap/bootstrap_db.sh" \
    "$ROOT_DIR/bootstrap/migrate_db_schema.sh" \
    "$ROOT_DIR/bootstrap/run_test_scenarios.sh" \
    "$ROOT_DIR/src/run_api_server.sh" \
    "$ROOT_DIR/one-shot-setup.sh" \
    "$ROOT_DIR/one-shot-startup.sh" \
    "$ROOT_DIR/one-shot-stop.sh" \
    "$ROOT_DIR/one-shot-reset-and-verify.sh"

if [ -f "$DB_PATH" ]; then
    if [ "$FORCE" -eq 1 ]; then
        echo "[setup] rebuilding SQLite demo database (--force)"
        "$ROOT_DIR/bootstrap/bootstrap_db.sh" "$DB_PATH"
    else
        TS="$(date +%Y%m%d%H%M%S)"
        mkdir -p "$DB_ARCHIVE_DIR"
        BACKUP_PATH="$DB_ARCHIVE_DIR/feasibility_satti.db.${TS}.bak"
        if [ "$NO_BACKUP" -eq 1 ]; then
            echo "[setup] rebuilding SQLite demo database without backup"
        else
            echo "[setup] existing DB found, creating backup: $BACKUP_PATH"
            cp "$DB_PATH" "$BACKUP_PATH"
        fi
        "$ROOT_DIR/bootstrap/bootstrap_db.sh" "$DB_PATH"
    fi
else
    echo "[setup] demo database not found, creating a new one"
    "$ROOT_DIR/bootstrap/bootstrap_db.sh" "$DB_PATH"
fi

echo "[setup] compiling Python sources"
"$VENV_DIR/bin/python" -m compileall "$ROOT_DIR/src"

echo "[setup] running scenario checks"
"$ROOT_DIR/bootstrap/run_test_scenarios.sh" --pristine >/dev/null

echo "[setup] repository smoke checks"
"$VENV_DIR/bin/python" "$ROOT_DIR/src/repository_example.py" "$DB_PATH" REQ-20260307-SEOUL-001 >/dev/null
"$VENV_DIR/bin/python" "$ROOT_DIR/src/repository_example.py" "$DB_PATH" REQ-20260307-WESTSEA-SAR-001 >/dev/null

echo "[setup] complete"
echo "venv: $VENV_DIR"
echo "db:   $DB_PATH"
