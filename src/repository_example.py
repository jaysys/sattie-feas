from __future__ import annotations

#
# repository_example.py
# ---------------------
# Purpose:
#   Minimal executable example for `repository.py`.
#
# What it does:
#   - Opens the SQLite demo DB.
#   - Loads one feasibility request report through `FeasibilityRepository`.
#   - Prints the aggregated result as JSON.
#
# Intended use:
#   - Manual inspection of repository output shape.
#   - Smoke test target from `one-shot-setup.sh`.
#   - Quick validation that the DB, repository, and JSON serialization all work together.
#
# Examples:
#   python3 ./src/repository_example.py ./db/feasibility_satti.db REQ-20260307-SEOUL-001
#   python3 ./src/repository_example.py ./db/feasibility_satti.db REQ-20260307-WESTSEA-SAR-001
#
# Notes:
#   - This is not the API server.
#   - This is not production application code.
#   - It is a small diagnostic/helper entry point for local verification.
#
import json
import sys
from pathlib import Path

try:
    from repository import FeasibilityRepository
except ModuleNotFoundError:  # pragma: no cover - support package import
    from .repository import FeasibilityRepository


def main() -> int:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./db/feasibility_satti.db")
    request_code = sys.argv[2] if len(sys.argv) > 2 else "REQ-20260307-SEOUL-001"

    repo = FeasibilityRepository(db_path)
    report = repo.get_request_report(request_code)
    if report is None:
        print(json.dumps({"error": f"request not found: {request_code}"}, indent=2, ensure_ascii=False))
        return 1

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
