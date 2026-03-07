#!/usr/bin/env python3
#
# print_current_request_evaluations.py
# ------------------------------------
# Purpose:
#   Print request-level feasibility evaluations derived from the current
#   request-candidate input values using the shared simulator logic.
#
# Usage:
#   ./venv/bin/python ./bootstrap/print_current_request_evaluations.py
#   ./venv/bin/python ./bootstrap/print_current_request_evaluations.py ./db/feasibility_satti.db
#
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.repository import FeasibilityRepository


def main() -> int:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT_DIR / "db" / "feasibility_satti.db"
    repo = FeasibilityRepository(db_path)

    for request in repo.list_requests():
        payload = repo.get_request_report(str(request["request_code"]))
        if payload is None:
            continue

        print(f"=== Derived Evaluation: {request['request_code']} ===")
        print(
            "summary",
            payload["result"]["final_verdict"],
            f"p={payload['result']['overall_probability']}",
            f"risk={payload['result']['dominant_risk_code']}",
            f"best={payload['result']['best_candidate_code']}",
            f"first={payload['result'].get('first_feasible_attempt_at')}",
            f"expected_attempts={payload['result'].get('expected_attempt_count')}",
        )
        print(payload["result"]["summary_message"])
        print("candidates")
        for candidate in payload["candidates"]:
            print(
                f"  {candidate['candidate_code']}: "
                f"{candidate['candidate_status']} "
                f"p={candidate['p_total_candidate']}"
            )
        print("reasons")
        if payload["candidate_rejection_reasons"]:
            for reason in payload["candidate_rejection_reasons"]:
                print(
                    f"  {reason['candidate_code']}: {reason['reason_code']} "
                    f"[{reason['reason_stage']}/{reason['reason_severity']}]"
                )
        else:
            print("  none")
        print("recommendations")
        if payload["recommendations"]:
            for recommendation in payload["recommendations"]:
                print(
                    f"  {recommendation['recommendation_type']}: "
                    f"{recommendation['parameter_name']} -> {recommendation['recommended_value']}"
                )
        else:
            print("  none")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
