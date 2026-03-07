#!/usr/bin/env python3
#
# validate_gap_features.py
# ------------------------
# Purpose:
#   Verify extended gap-closure features on isolated temporary copies of the DB.
#
# Usage:
#   ./venv/bin/python ./bootstrap/validate_gap_features.py
#   ./venv/bin/python ./bootstrap/validate_gap_features.py ./db/feasibility_satti.db
#
from __future__ import annotations

import gc
import shutil
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.repository import FeasibilityRepository


class ScenarioWorkspace:
    def __init__(self, base_db_path: Path) -> None:
        self.base_db_path = base_db_path
        self.root = Path(tempfile.mkdtemp(prefix="gap_feature."))

    @contextmanager
    def scenario_db(self, name: str):
        temp_db = self.root / f"{name}.db"
        if temp_db.exists():
            temp_db.unlink()
        shutil.copy2(self.base_db_path, temp_db)
        try:
            yield temp_db
        finally:
            gc.collect()
            try:
                if temp_db.exists():
                    temp_db.unlink()
            except OSError:
                pass

    def cleanup(self) -> None:
        gc.collect()
        shutil.rmtree(self.root, ignore_errors=True)


def _print_candidate_gain(repo: FeasibilityRepository) -> None:
    output = repo.simulate_request_candidate_input(
        "REQ-20260307-SEOUL-001",
        repo.get_request_candidate_input("REQ-20260307-SEOUL-001", "OPT-CAND-003"),
        "OPT-CAND-003",
    )
    gains = [
        (
            recommendation["parameter_name"],
            recommendation.get("expected_probability_gain"),
        )
        for recommendation in output["recommendations"]
    ]
    print("candidate_gain", gains)



def _print_request_gain(repo: FeasibilityRepository) -> None:
    payload = repo.get_request_report("REQ-20260307-SEOUL-001")
    gains = [
        (
            recommendation["recommendation_type"],
            recommendation["parameter_name"],
            recommendation.get("expected_probability_gain"),
        )
        for recommendation in payload["proposal"]["relaxation_options"]
    ]
    print("request_gain", gains)



def _print_repeat_pass_check(workspace: ScenarioWorkspace) -> None:
    with workspace.scenario_db("repeat_pass") as temp_db:
        with sqlite3.connect(temp_db) as con:
            con.execute(
                """
                UPDATE feasibility_request
                SET repeat_acquisition_flag = 1,
                    monitoring_count = 2
                WHERE request_code = 'REQ-20260307-WESTSEA-SAR-001'
                """
            )
        repo = FeasibilityRepository(temp_db)
        payload = repo.get_request_report("REQ-20260307-WESTSEA-SAR-001")
        print(
            "repeat_pass",
            payload["result"]["final_verdict"],
            payload["result"]["dominant_risk_code"],
            f"required={payload['proposal']['required_attempt_count']}",
            f"met={payload['proposal']['repeat_requirement_met']}",
        )
        del repo



def _print_repeat_spacing_check(workspace: ScenarioWorkspace) -> None:
    with workspace.scenario_db("repeat_spacing") as temp_db:
        with sqlite3.connect(temp_db) as con:
            con.execute(
                """
                UPDATE feasibility_request
                SET repeat_acquisition_flag = 1,
                    monitoring_count = 2
                WHERE request_code = 'REQ-20260307-WESTSEA-SAR-001'
                """
            )
            con.execute(
                """
                UPDATE request_candidate_input
                SET expected_data_volume_gbit = 18.0,
                    recorder_free_gbit = 60.0,
                    recorder_backlog_gbit = 0.0,
                    available_downlink_gbit = 80.0,
                    power_margin_pct = 20.0,
                    thermal_margin_pct = 20.0
                WHERE request_candidate_id = 6
                """
            )
            con.execute(
                """
                UPDATE satellite_pass
                SET pass_start_at = '2026-03-11T00:20:00Z',
                    pass_end_at = '2026-03-11T00:32:00Z'
                WHERE satellite_pass_id = 6
                """
            )
            con.execute(
                """
                UPDATE access_opportunity
                SET access_start_at = '2026-03-11T00:24:10Z',
                    access_end_at = '2026-03-11T00:25:20Z'
                WHERE access_opportunity_id = 6
                """
            )
            con.execute(
                """
                UPDATE station_contact_window
                SET contact_start_at = '2026-03-11T00:50:00Z',
                    contact_end_at = '2026-03-11T00:57:00Z'
                WHERE contact_window_id = 4
                """
            )
        repo = FeasibilityRepository(temp_db)
        payload = repo.get_request_report("REQ-20260307-WESTSEA-SAR-001")
        print(
            "repeat_spacing",
            payload["result"]["final_verdict"],
            payload["result"]["dominant_risk_code"],
            f"required={payload['proposal']['required_attempt_count']}",
            f"spacing_hours={payload['proposal']['repeat_spacing_hours_required']}",
            f"spacing_met={payload['proposal']['repeat_spacing_met']}",
        )
        del repo



def _print_repeat_incidence_check(workspace: ScenarioWorkspace) -> None:
    with workspace.scenario_db("repeat_incidence") as temp_db:
        with sqlite3.connect(temp_db) as con:
            con.execute(
                """
                UPDATE feasibility_request
                SET repeat_acquisition_flag = 1,
                    monitoring_count = 2
                WHERE request_code = 'REQ-20260307-WESTSEA-SAR-001'
                """
            )
            con.execute(
                """
                UPDATE request_candidate_input
                SET expected_data_volume_gbit = 18.0,
                    recorder_free_gbit = 60.0,
                    recorder_backlog_gbit = 0.0,
                    available_downlink_gbit = 80.0,
                    power_margin_pct = 20.0,
                    thermal_margin_pct = 20.0
                WHERE request_candidate_id = 6
                """
            )
            con.execute(
                """
                UPDATE satellite_pass
                SET pass_start_at = '2026-03-11T12:40:00Z',
                    pass_end_at = '2026-03-11T12:52:00Z'
                WHERE satellite_pass_id = 6
                """
            )
            con.execute(
                """
                UPDATE access_opportunity
                SET access_start_at = '2026-03-11T12:44:10Z',
                    access_end_at = '2026-03-11T12:45:20Z',
                    predicted_incidence_deg = 35.0,
                    geometric_feasible_flag = 1
                WHERE access_opportunity_id = 6
                """
            )
            con.execute(
                """
                UPDATE station_contact_window
                SET contact_start_at = '2026-03-11T13:10:00Z',
                    contact_end_at = '2026-03-11T13:17:00Z'
                WHERE contact_window_id = 4
                """
            )
        repo = FeasibilityRepository(temp_db)
        payload = repo.get_request_report("REQ-20260307-WESTSEA-SAR-001")
        incidence_option_params = list(
            dict.fromkeys(
                item["parameter_name"]
                for item in payload["proposal"]["relaxation_options"]
                if item["parameter_name"] in {"incidence_window", "candidate_split"}
            )
        )
        print(
            "repeat_incidence",
            payload["result"]["final_verdict"],
            payload["result"]["dominant_risk_code"],
            f"required={payload['proposal']['required_attempt_count']}",
            f"inc_tol={payload['proposal']['repeat_incidence_tolerance_deg']}",
            f"spacing_met={payload['proposal']['repeat_spacing_met']}",
            f"options={','.join(incidence_option_params) if incidence_option_params else 'none'}",
        )
        del repo



def _print_polarization_check(workspace: ScenarioWorkspace) -> None:
    with workspace.scenario_db("polarization") as temp_db:
        with sqlite3.connect(temp_db) as con:
            con.execute(
                """
                UPDATE sensor_mode
                SET supported_polarizations = 'VV,VH'
                WHERE sensor_mode_id = 2
                """
            )
        repo = FeasibilityRepository(temp_db)
        output = repo.simulate_request_candidate_input(
            "REQ-20260307-WESTSEA-SAR-001",
            repo.get_request_candidate_input("REQ-20260307-WESTSEA-SAR-001", "SAR-CAND-001"),
            "SAR-CAND-001",
        )
        reasons = [
            reason["reason_code"]
            for reason in output["reasons"]
            if reason["reason_stage"] == "POLICY"
        ]
        print("polarization", output["final_verdict"], ",".join(reasons) if reasons else "NONE")
        del repo



def _print_shadow_risk_check(workspace: ScenarioWorkspace) -> None:
    with workspace.scenario_db("shadow") as temp_db:
        with sqlite3.connect(temp_db) as con:
            con.execute(
                """
                UPDATE solar_condition_snapshot
                SET sun_elevation_deg = 24.0,
                    sun_azimuth_deg = 96.0
                WHERE solar_condition_snapshot_id = 1
                """
            )
        repo = FeasibilityRepository(temp_db)
        output = repo.simulate_request_candidate_input(
            "REQ-20260307-SEOUL-001",
            repo.get_request_candidate_input("REQ-20260307-SEOUL-001", "OPT-CAND-001"),
            "OPT-CAND-001",
        )
        reasons = [
            reason["reason_code"]
            for reason in output["reasons"]
            if reason["reason_stage"] == "ENVIRONMENT"
        ]
        print(
            "shadow",
            output["final_verdict"],
            ",".join(reasons) if reasons else "NONE",
            f"score={output['checks'].get('shadow_risk_score')}",
        )
        del repo



def _print_local_time_check(workspace: ScenarioWorkspace) -> None:
    with workspace.scenario_db("local_time") as temp_db:
        with sqlite3.connect(temp_db) as con:
            con.execute(
                """
                UPDATE request_constraint
                SET preferred_local_time_start = '13:00',
                    preferred_local_time_end = '14:00'
                WHERE request_id = 1
                """
            )
        repo = FeasibilityRepository(temp_db)
        output = repo.simulate_request_candidate_input(
            "REQ-20260307-SEOUL-001",
            repo.get_request_candidate_input("REQ-20260307-SEOUL-001", "OPT-CAND-001"),
            "OPT-CAND-001",
        )
        reasons = [
            reason["reason_code"]
            for reason in output["reasons"]
            if reason["reason_stage"] == "ENVIRONMENT"
        ]
        print(
            "local_time",
            output["final_verdict"],
            ",".join(reasons) if reasons else "NONE",
            f"local={output['checks'].get('local_capture_time_hhmm')}",
            f"distance_min={output['checks'].get('local_time_window_distance_min')}",
        )
        del repo



def main() -> int:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT_DIR / "db" / "feasibility_satti.db"
    repo = FeasibilityRepository(db_path)
    workspace = ScenarioWorkspace(db_path)

    print("[gap feature checks]")
    try:
        _print_candidate_gain(repo)
        _print_request_gain(repo)
        del repo
        gc.collect()
        _print_repeat_pass_check(workspace)
        _print_repeat_spacing_check(workspace)
        _print_repeat_incidence_check(workspace)
        _print_polarization_check(workspace)
        _print_shadow_risk_check(workspace)
        _print_local_time_check(workspace)
    finally:
        workspace.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
