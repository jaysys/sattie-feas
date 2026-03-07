#!/bin/sh
#
# migrate_db_schema.sh
# --------------------
# Purpose:
#   Apply additive SQLite schema migrations to an existing working DB without
#   rebuilding it from bootstrap schema/seed.
#
# Usage:
#   ./bootstrap/migrate_db_schema.sh
#   ./bootstrap/migrate_db_schema.sh ./db/feasibility_satti.db
#
# Notes:
#   - This script is intentionally additive only.
#   - It currently migrates:
#       - `request_external_ref`
#       - `request_aoi.dominant_axis_deg`
#       - `request_candidate_run.input_version_no`
#       - `request_candidate_run.run_trigger_*`
#       - `request_candidate_input.opportunity_start_at/opportunity_end_at`
#   - Existing data is preserved.
#

set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DB_PATH=${1:-"$ROOT_DIR/db/feasibility_satti.db"}

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "[migrate] sqlite3 is required" >&2
  exit 1
fi

if [ ! -f "$DB_PATH" ]; then
  echo "[migrate] db file not found: $DB_PATH" >&2
  exit 1
fi

has_column() {
  sqlite3 "$DB_PATH" "PRAGMA table_info($1);" | awk -F'|' -v col="$2" '$2 == col { found = 1 } END { exit(found ? 0 : 1) }'
}

echo "[migrate] target db: $DB_PATH"

if has_column request_aoi dominant_axis_deg; then
  echo "[migrate] request_aoi.dominant_axis_deg already present"
else
  echo "[migrate] adding request_aoi.dominant_axis_deg"
  sqlite3 "$DB_PATH" "ALTER TABLE request_aoi ADD COLUMN dominant_axis_deg REAL;"
  sqlite3 "$DB_PATH" "
    UPDATE request_aoi
    SET dominant_axis_deg = CASE request_id
      WHEN 1 THEN 145.0
      WHEN 2 THEN 90.0
      ELSE dominant_axis_deg
    END
    WHERE dominant_axis_deg IS NULL;
  "
  echo "[migrate] backfilled dominant_axis_deg for known seeded request_id values"
fi

if sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'request_external_ref';" | grep -q request_external_ref; then
  echo "[migrate] request_external_ref already present"
else
  echo "[migrate] creating request_external_ref"
  sqlite3 "$DB_PATH" "
    CREATE TABLE request_external_ref (
      request_external_ref_id INTEGER PRIMARY KEY,
      request_id INTEGER NOT NULL,
      source_system_code TEXT NOT NULL,
      external_request_code TEXT NOT NULL,
      external_request_title TEXT,
      external_customer_org_name TEXT,
      external_requester_name TEXT,
      is_primary INTEGER NOT NULL DEFAULT 1 CHECK (is_primary IN (0, 1)),
      received_at TEXT,
      created_at TEXT NOT NULL,
      FOREIGN KEY (request_id) REFERENCES feasibility_request(request_id),
      UNIQUE (source_system_code, external_request_code)
    );
    CREATE INDEX idx_request_external_ref_request_id
      ON request_external_ref(request_id, is_primary);
  "
fi

if sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM request_external_ref;" | grep -q '^0$'; then
  echo "[migrate] seeding primary request_external_ref rows for known seeded requests"
  sqlite3 "$DB_PATH" "
    INSERT OR IGNORE INTO request_external_ref (
      request_external_ref_id, request_id, source_system_code, external_request_code, external_request_title,
      external_customer_org_name, external_requester_name, is_primary, received_at, created_at
    ) VALUES
      (1, 1, 'CUSTOMER_PORTAL', 'EXT-SEOUL-20260307-0001', '서울 도심 재난 대응용 광학 촬영 요청', 'Seoul Disaster Analytics Center', 'Kim Mina', 1, '2026-03-07T09:58:00Z', '2026-03-07T10:00:00Z'),
      (2, 2, 'CUSTOMER_PORTAL', 'EXT-WESTSEA-20260307-0002', '서해 해역 긴급 SAR 촬영 요청', 'Seoul Disaster Analytics Center', 'Kim Mina', 1, '2026-03-07T10:18:00Z', '2026-03-07T10:20:00Z');
  "
fi

if has_column request_candidate_run run_trigger_type; then
  echo "[migrate] request_candidate_run.run_trigger_* already present"
else
  echo "[migrate] adding request_candidate_run.run_trigger_* columns"
  sqlite3 "$DB_PATH" "ALTER TABLE request_candidate_run ADD COLUMN run_trigger_type TEXT;"
  sqlite3 "$DB_PATH" "ALTER TABLE request_candidate_run ADD COLUMN run_trigger_source_code TEXT;"
  sqlite3 "$DB_PATH" "ALTER TABLE request_candidate_run ADD COLUMN run_trigger_parameter_name TEXT;"
  sqlite3 "$DB_PATH" "ALTER TABLE request_candidate_run ADD COLUMN run_trigger_note TEXT;"
fi

if has_column request_candidate_run input_version_no; then
  echo "[migrate] request_candidate_run.input_version_no already present"
else
  echo "[migrate] adding request_candidate_run.input_version_no"
  sqlite3 "$DB_PATH" "ALTER TABLE request_candidate_run ADD COLUMN input_version_no INTEGER;"
fi

if has_column request_candidate_input opportunity_start_at; then
  echo "[migrate] request_candidate_input.opportunity_start_at already present"
else
  echo "[migrate] adding request_candidate_input.opportunity_start_at"
  sqlite3 "$DB_PATH" "ALTER TABLE request_candidate_input ADD COLUMN opportunity_start_at TEXT;"
fi

if has_column request_candidate_input opportunity_end_at; then
  echo "[migrate] request_candidate_input.opportunity_end_at already present"
else
  echo "[migrate] adding request_candidate_input.opportunity_end_at"
  sqlite3 "$DB_PATH" "ALTER TABLE request_candidate_input ADD COLUMN opportunity_end_at TEXT;"
fi

echo "[migrate] complete"
