from __future__ import annotations

#
# repository.py
# -------------
# Purpose:
#   Central SQLite data access layer for the feasibility demo environment.
#
# Why this file exists:
#   - To keep SQL in one place instead of scattering it across the API server,
#     shell scripts, or example programs.
#   - To provide stable Python methods that return JSON-serializable dictionaries.
#   - To make the DB access pattern reusable from CLI tools, tests, and HTTP handlers.
#
# Main responsibilities:
#   1. Read request-level data:
#      - request header
#      - AOI
#      - constraints
#      - sensor options
#      - product options
#   2. Read run-level data:
#      - latest feasibility run
#      - run input bundle
#      - contact windows
#      - existing tasks
#      - downlink bookings
#   3. Read result-level data:
#      - candidates
#      - rejection reasons
#      - resource checks
#      - downlink checks
#      - probability breakdown
#      - final result
#      - recommendations
#      - audit events
#   4. Assemble a full aggregated payload with `get_request_report()`.
#
# Typical consumers:
#   - `src/api_server.py`
#   - `src/repository_example.py`
#   - future tests or batch scripts
#
# Notes:
#   - It intentionally uses only the Python standard library (`sqlite3`).
#   - Read-heavy 조회와 후보건 CRUD/검증 이력 저장을 함께 담당한다.
#   - The repository returns plain dict/list structures so they can be directly
#     serialized as JSON without extra mapping layers.
#
import sqlite3
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from simulator import SimulationInput, simulate_feasibility
except ModuleNotFoundError:  # pragma: no cover - support package import
    from .simulator import SimulationInput, simulate_feasibility


class FeasibilityRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    def _fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return self._rows_to_dicts(rows)

    def _fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def _execute_write(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self._connect() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return int(cursor.lastrowid)

    def _resolve_request_locator(self, request_key: str) -> dict[str, Any] | None:
        row = self._fetch_one(
            "SELECT request_id, request_code FROM feasibility_request WHERE request_code = ?",
            (request_key,),
        )
        if row is not None:
            return row
        return self._fetch_one(
            """
            SELECT fr.request_id, fr.request_code
            FROM request_external_ref rer
            JOIN feasibility_request fr ON fr.request_id = rer.request_id
            WHERE rer.external_request_code = ?
            ORDER BY rer.is_primary DESC, rer.request_external_ref_id
            LIMIT 1
            """,
            (request_key,),
        )

    def _resolve_request_id(self, request_key: str) -> int | None:
        row = self._resolve_request_locator(request_key)
        return int(row["request_id"]) if row is not None else None

    def _resolve_internal_request_code(self, request_key: str) -> str | None:
        row = self._resolve_request_locator(request_key)
        return str(row["request_code"]) if row is not None else None

    def _resolve_request_candidate_id(self, request_key: str, candidate_code: str) -> int | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return None
        row = self._fetch_one(
            """
            SELECT rc.request_candidate_id
            FROM request_candidate rc
            JOIN feasibility_request fr ON fr.request_id = rc.request_id
            WHERE fr.request_code = ? AND rc.candidate_code = ?
            """,
            (internal_request_code, candidate_code),
        )
        return int(row["request_candidate_id"]) if row is not None else None

    def _generate_candidate_code(self, conn: sqlite3.Connection, request_id: int, sensor_type: str) -> str:
        prefix = "SAR-CAND-" if str(sensor_type).upper() == "SAR" else "OPT-CAND-"
        rows = conn.execute(
            "SELECT candidate_code FROM request_candidate WHERE request_id = ?",
            (request_id,),
        ).fetchall()
        next_sequence = 1
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
        for row in rows:
            match = pattern.match(str(row["candidate_code"]))
            if match:
                next_sequence = max(next_sequence, int(match.group(1)) + 1)
        return f"{prefix}{next_sequence:03d}"

    def _generate_request_code(self, conn: sqlite3.Connection, created_at: str) -> str:
        date_token = self._parse_utc(created_at).strftime("%Y%m%d")
        prefix = f"REQ-{date_token}-"
        rows = conn.execute(
            "SELECT request_code FROM feasibility_request WHERE request_code LIKE ?",
            (f"{prefix}%",),
        ).fetchall()
        next_sequence = 1
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
        for row in rows:
            match = pattern.match(str(row["request_code"]))
            if match:
                next_sequence = max(next_sequence, int(match.group(1)) + 1)
        return f"{prefix}{next_sequence:06d}"

    def list_request_external_refs(self, request_key: str) -> list[dict[str, Any]]:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return []
        return self._fetch_all(
            """
            SELECT
                rer.request_external_ref_id,
                rer.source_system_code,
                rer.external_request_code,
                rer.external_request_title,
                rer.external_customer_org_name,
                rer.external_requester_name,
                rer.is_primary,
                rer.received_at,
                rer.created_at
            FROM request_external_ref rer
            JOIN feasibility_request fr ON fr.request_id = rer.request_id
            WHERE fr.request_code = ?
            ORDER BY rer.is_primary DESC, rer.request_external_ref_id
            """,
            (internal_request_code,),
        )

    def create_request_external_ref(self, request_key: str, external_ref: dict[str, Any]) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        request_id = self._resolve_request_id(request_key)
        if internal_request_code is None or request_id is None:
            return None
        with self._connect() as conn:
            if bool(external_ref.get("is_primary")):
                conn.execute(
                    "UPDATE request_external_ref SET is_primary = 0 WHERE request_id = ?",
                    (request_id,),
                )
            cursor = conn.execute(
                """
                INSERT INTO request_external_ref (
                    request_id,
                    source_system_code,
                    external_request_code,
                    external_request_title,
                    external_customer_org_name,
                    external_requester_name,
                    is_primary,
                    received_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    external_ref["source_system_code"],
                    external_ref["external_request_code"],
                    external_ref.get("external_request_title"),
                    external_ref.get("external_customer_org_name"),
                    external_ref.get("external_requester_name"),
                    1 if bool(external_ref.get("is_primary")) else 0,
                    external_ref.get("received_at"),
                    external_ref["created_at"],
                ),
            )
            conn.commit()
            request_external_ref_id = int(cursor.lastrowid)
            row = conn.execute(
                """
                SELECT
                    request_external_ref_id,
                    source_system_code,
                    external_request_code,
                    external_request_title,
                    external_customer_org_name,
                    external_requester_name,
                    is_primary,
                    received_at,
                    created_at
                FROM request_external_ref
                WHERE request_external_ref_id = ?
                """,
                (request_external_ref_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def set_request_external_ref_primary(self, request_key: str, request_external_ref_id: int) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        request_id = self._resolve_request_id(request_key)
        if internal_request_code is None or request_id is None:
            return None
        with self._connect() as conn:
            target = conn.execute(
                """
                SELECT request_external_ref_id
                FROM request_external_ref
                WHERE request_external_ref_id = ? AND request_id = ?
                """,
                (request_external_ref_id, request_id),
            ).fetchone()
            if target is None:
                return None
            conn.execute(
                "UPDATE request_external_ref SET is_primary = 0 WHERE request_id = ?",
                (request_id,),
            )
            conn.execute(
                "UPDATE request_external_ref SET is_primary = 1 WHERE request_external_ref_id = ?",
                (request_external_ref_id,),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT
                    request_external_ref_id,
                    source_system_code,
                    external_request_code,
                    external_request_title,
                    external_customer_org_name,
                    external_requester_name,
                    is_primary,
                    received_at,
                    created_at
                FROM request_external_ref
                WHERE request_external_ref_id = ?
                """,
                (request_external_ref_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def delete_request_external_ref(self, request_key: str, request_external_ref_id: int) -> bool:
        internal_request_code = self._resolve_internal_request_code(request_key)
        request_id = self._resolve_request_id(request_key)
        if internal_request_code is None or request_id is None:
            return False
        with self._connect() as conn:
            target = conn.execute(
                """
                SELECT request_external_ref_id, is_primary
                FROM request_external_ref
                WHERE request_external_ref_id = ? AND request_id = ?
                """,
                (request_external_ref_id, request_id),
            ).fetchone()
            if target is None:
                return False
            was_primary = bool(target["is_primary"])
            conn.execute(
                "DELETE FROM request_external_ref WHERE request_external_ref_id = ?",
                (request_external_ref_id,),
            )
            if was_primary:
                replacement = conn.execute(
                    """
                    SELECT request_external_ref_id
                    FROM request_external_ref
                    WHERE request_id = ?
                    ORDER BY request_external_ref_id
                    LIMIT 1
                    """,
                    (request_id,),
                ).fetchone()
                if replacement is not None:
                    conn.execute(
                        "UPDATE request_external_ref SET is_primary = 1 WHERE request_external_ref_id = ?",
                        (int(replacement["request_external_ref_id"]),),
                    )
            conn.commit()
        return True

    def create_request(
        self,
        request_data: dict[str, Any],
        request_aoi: dict[str, Any],
        request_constraint: dict[str, Any],
        request_sensor_options: list[dict[str, Any]],
        request_product_options: list[dict[str, Any]],
        external_ref: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        created_at = str(request_data["created_at"])
        with self._connect() as conn:
            policy_row = conn.execute(
                """
                SELECT priority_tier
                FROM service_policy
                WHERE service_policy_id = ?
                """,
                (int(request_data["service_policy_id"]),),
            ).fetchone()
            if policy_row is None:
                raise ValueError("유효하지 않은 서비스 정책입니다.")
            resolved_priority_tier = request_data.get("priority_tier") or policy_row["priority_tier"]
            request_code = self._generate_request_code(conn, created_at)
            cursor = conn.execute(
                """
                INSERT INTO feasibility_request (
                    customer_org_id,
                    customer_user_id,
                    service_policy_id,
                    request_code,
                    request_title,
                    request_description,
                    request_status,
                    request_channel,
                    priority_tier,
                    requested_start_at,
                    requested_end_at,
                    emergency_flag,
                    repeat_acquisition_flag,
                    monitoring_count,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_data["customer_org_id"],
                    request_data["customer_user_id"],
                    request_data["service_policy_id"],
                    request_code,
                    request_data["request_title"],
                    request_data["request_description"],
                    request_data["request_status"],
                    request_data["request_channel"],
                    resolved_priority_tier,
                    request_data["requested_start_at"],
                    request_data["requested_end_at"],
                    1 if bool(request_data.get("emergency_flag")) else 0,
                    1 if bool(request_data.get("repeat_acquisition_flag")) else 0,
                    int(request_data.get("monitoring_count") or 1),
                    created_at,
                ),
            )
            request_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO request_aoi (
                    request_id, geometry_type, geometry_wkt, srid, area_km2,
                    bbox_min_lon, bbox_min_lat, bbox_max_lon, bbox_max_lat,
                    centroid_lon, centroid_lat, dominant_axis_deg, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    request_aoi["geometry_type"],
                    request_aoi["geometry_wkt"],
                    int(request_aoi.get("srid") or 4326),
                    float(request_aoi["area_km2"]),
                    float(request_aoi["bbox_min_lon"]),
                    float(request_aoi["bbox_min_lat"]),
                    float(request_aoi["bbox_max_lon"]),
                    float(request_aoi["bbox_max_lat"]),
                    float(request_aoi["centroid_lon"]),
                    float(request_aoi["centroid_lat"]),
                    request_aoi.get("dominant_axis_deg"),
                    created_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO request_constraint (
                    request_id, max_cloud_pct, max_off_nadir_deg, min_incidence_deg, max_incidence_deg,
                    preferred_local_time_start, preferred_local_time_end, min_sun_elevation_deg, max_haze_index,
                    deadline_at, coverage_ratio_required, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    request_constraint.get("max_cloud_pct"),
                    request_constraint.get("max_off_nadir_deg"),
                    request_constraint.get("min_incidence_deg"),
                    request_constraint.get("max_incidence_deg"),
                    request_constraint.get("preferred_local_time_start"),
                    request_constraint.get("preferred_local_time_end"),
                    request_constraint.get("min_sun_elevation_deg"),
                    request_constraint.get("max_haze_index"),
                    request_constraint.get("deadline_at"),
                    float(request_constraint.get("coverage_ratio_required") or 1.0),
                    created_at,
                ),
            )
            for option in request_sensor_options:
                conn.execute(
                    """
                    INSERT INTO request_sensor_option (
                        request_id, satellite_id, sensor_id, sensor_mode_id, preference_rank,
                        is_mandatory, polarization_code, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        int(option["satellite_id"]),
                        int(option["sensor_id"]),
                        int(option["sensor_mode_id"]),
                        int(option["preference_rank"]),
                        1 if bool(option.get("is_mandatory")) else 0,
                        option.get("polarization_code"),
                        created_at,
                    ),
                )
            for option in request_product_options:
                conn.execute(
                    """
                    INSERT INTO request_product_option (
                        request_id, product_level_code, product_type_code, file_format_code,
                        delivery_mode_code, ancillary_required_flag, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        option["product_level_code"],
                        option["product_type_code"],
                        option["file_format_code"],
                        option["delivery_mode_code"],
                        1 if bool(option.get("ancillary_required_flag")) else 0,
                        created_at,
                    ),
                )
            if external_ref is not None:
                conn.execute(
                    """
                    INSERT INTO request_external_ref (
                        request_id, source_system_code, external_request_code, external_request_title,
                        external_customer_org_name, external_requester_name, is_primary, received_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        external_ref["source_system_code"],
                        external_ref["external_request_code"],
                        external_ref.get("external_request_title"),
                        external_ref.get("external_customer_org_name"),
                        external_ref.get("external_requester_name"),
                        1 if bool(external_ref.get("is_primary", True)) else 0,
                        external_ref.get("received_at"),
                        created_at,
                    ),
                )
            conn.commit()
        return self.get_request_report(request_code)

    def update_request(self, request_key: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return None

        request_id = self._resolve_request_id(internal_request_code)
        if request_id is None:
            return None

        allowed_columns = {
            "request_title": "request_title",
            "request_description": "request_description",
            "request_status": "request_status",
            "request_channel": "request_channel",
            "priority_tier": "priority_tier",
            "requested_start_at": "requested_start_at",
            "requested_end_at": "requested_end_at",
            "emergency_flag": "emergency_flag",
            "repeat_acquisition_flag": "repeat_acquisition_flag",
            "monitoring_count": "monitoring_count",
        }

        set_clauses: list[str] = []
        params: list[Any] = []
        for key, column in allowed_columns.items():
            if key not in updates:
                continue
            value = updates[key]
            if key in {"emergency_flag", "repeat_acquisition_flag"}:
                value = 1 if bool(value) else 0
            elif key == "monitoring_count":
                value = int(value)
            elif key == "request_status":
                value = str(value).upper()
            set_clauses.append(f"{column} = ?")
            params.append(value)

        if not set_clauses:
            return self.get_request_report(internal_request_code)

        params.append(request_id)
        sql = f"""
        UPDATE feasibility_request
        SET {", ".join(set_clauses)}
        WHERE request_id = ?
        """
        with self._connect() as conn:
            conn.execute(sql, tuple(params))
            conn.commit()
        return self.get_request_report(internal_request_code)

    def cancel_request(self, request_key: str) -> dict[str, Any] | None:
        return self.update_request(request_key, {"request_status": "CANCELLED"})

    def list_requests(self) -> list[dict[str, Any]]:
        sql = """
        SELECT
            fr.request_id,
            fr.request_code,
            fr.request_title,
            fr.request_description,
            fr.request_status,
            fr.priority_tier,
            fr.requested_start_at,
            fr.requested_end_at,
            fr.emergency_flag,
            rer.source_system_code AS external_source_system_code,
            rer.external_request_code AS external_request_code,
            rer.external_request_title AS external_request_title,
            rer.external_customer_org_name,
            rer.external_requester_name,
            co.org_name,
            cu.user_name,
            sp.policy_name
        FROM feasibility_request fr
        JOIN customer_org co ON co.customer_org_id = fr.customer_org_id
        JOIN customer_user cu ON cu.customer_user_id = fr.customer_user_id
        JOIN service_policy sp ON sp.service_policy_id = fr.service_policy_id
        LEFT JOIN request_external_ref rer
            ON rer.request_external_ref_id = (
                SELECT rer2.request_external_ref_id
                FROM request_external_ref rer2
                WHERE rer2.request_id = fr.request_id
                ORDER BY rer2.is_primary DESC, rer2.request_external_ref_id
                LIMIT 1
            )
        ORDER BY fr.request_id
        """
        return self._fetch_all(sql)

    def get_request(self, request_key: str) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return None
        sql = """
        SELECT
            fr.request_id,
            fr.request_code,
            fr.request_title,
            fr.request_description,
            fr.request_status,
            fr.request_channel,
            fr.priority_tier,
            fr.requested_start_at,
            fr.requested_end_at,
            fr.emergency_flag,
            fr.repeat_acquisition_flag,
            fr.monitoring_count,
            fr.created_at,
            rer.source_system_code AS external_source_system_code,
            rer.external_request_code AS external_request_code,
            rer.external_request_title AS external_request_title,
            rer.external_customer_org_name,
            rer.external_requester_name,
            rer.received_at AS external_received_at,
            co.org_name,
            co.org_type,
            cu.user_name,
            cu.email,
            sp.policy_name,
            sp.priority_tier AS policy_priority_tier,
            sp.min_order_area_km2,
            sp.order_cutoff_hours,
            sp.max_attempts
        FROM feasibility_request fr
        JOIN customer_org co ON co.customer_org_id = fr.customer_org_id
        JOIN customer_user cu ON cu.customer_user_id = fr.customer_user_id
        JOIN service_policy sp ON sp.service_policy_id = fr.service_policy_id
        LEFT JOIN request_external_ref rer
            ON rer.request_external_ref_id = (
                SELECT rer2.request_external_ref_id
                FROM request_external_ref rer2
                WHERE rer2.request_id = fr.request_id
                ORDER BY rer2.is_primary DESC, rer2.request_external_ref_id
                LIMIT 1
            )
        WHERE fr.request_code = ?
        """
        return self._fetch_one(sql, (internal_request_code,))

    @staticmethod
    def _parse_utc(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

    @staticmethod
    def _parse_time_hhmm(value: str) -> int:
        hour_str, minute_str = value.split(":", 1)
        return (int(hour_str) * 60 + int(minute_str)) % (24 * 60)

    @staticmethod
    def _format_minutes_hhmm(total_minutes: int) -> str:
        total_minutes = total_minutes % (24 * 60)
        return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"

    @staticmethod
    def _local_time_window_distance_minutes(local_minutes: int, start_minutes: int, end_minutes: int) -> int:
        if start_minutes <= end_minutes:
            if start_minutes <= local_minutes <= end_minutes:
                return 0
            return min(abs(local_minutes - start_minutes), abs(local_minutes - end_minutes))

        if local_minutes >= start_minutes or local_minutes <= end_minutes:
            return 0
        return min(abs(local_minutes - start_minutes), abs(local_minutes - end_minutes))

    @staticmethod
    def _priority_rank(priority_tier: str) -> int:
        rank = {
            "STANDARD": 1,
            "PRIORITY": 2,
            "ASSURED": 3,
            "URGENT": 4,
        }
        return rank.get(priority_tier, 0)

    @staticmethod
    def _product_policy_for_sensor(sensor_type: str) -> dict[str, set[str]]:
        if sensor_type == "SAR":
            return {
                "product_levels": {"L1C", "L1D", "L2A"},
                "product_types": {"SIGMA0", "SLC", "GEORECTIFIED"},
                "file_formats": {"HDF5", "GEOTIFF", "NETCDF"},
            }
        return {
            "product_levels": {"L1R", "L1G", "L2A"},
            "product_types": {"ORTHO_READY", "REFLECTANCE", "PANSHARPENED"},
            "file_formats": {"GEOTIFF", "JPEG2000", "PNG", "JPG"},
        }

    def _recompute_output_status(self, output: dict[str, Any]) -> dict[str, Any]:
        hard_reasons = [reason for reason in output["reasons"] if reason["reason_severity"] == "HARD"]
        soft_reasons = [reason for reason in output["reasons"] if reason["reason_severity"] == "SOFT"]
        total_probability = float(output["probabilities"]["p_total_candidate"])

        if hard_reasons:
            output["candidate_status"] = "REJECTED"
            output["final_verdict"] = "NOT_FEASIBLE"
            output["dominant_risk_code"] = hard_reasons[0]["reason_code"]
            output["summary_message"] = "정책, 기하, 환경, 자원, 다운링크 제약 중 하나 이상이 현재 요청 조건과 충돌하여 수행할 수 없습니다."
        elif soft_reasons or total_probability < 0.30:
            output["candidate_status"] = "CONDITIONAL"
            output["final_verdict"] = "CONDITIONALLY_FEASIBLE"
            output["dominant_risk_code"] = (soft_reasons[0]["reason_code"] if soft_reasons else "LOW_TOTAL_PROBABILITY")
            output["summary_message"] = "현재 입력으로 수행 가능성은 있으나, 정책 또는 운영 리스크가 남아 있어 조건부 검토가 필요합니다."
        else:
            output["candidate_status"] = "FEASIBLE"
            output["final_verdict"] = "FEASIBLE"
            output["dominant_risk_code"] = None
            output["summary_message"] = "현재 입력 기준으로 정책, 기하, 환경, 자원, 다운링크 제약을 모두 충족합니다."
        return output

    def _apply_request_policy_validation(
        self,
        request_row: dict[str, Any],
        aoi: dict[str, Any] | None,
        sensor_options: list[dict[str, Any]],
        product_options: list[dict[str, Any]],
        candidate_input: dict[str, Any],
        output: dict[str, Any],
    ) -> dict[str, Any]:
        policy_factor = 1.0
        policy_reason_count = 0

        def add_reason(reason_code: str, severity: str, message: str) -> None:
            nonlocal policy_factor, policy_reason_count
            output["reasons"].append(
                {
                    "reason_code": reason_code,
                    "reason_stage": "POLICY",
                    "reason_severity": severity,
                    "reason_message": message,
                }
            )
            policy_reason_count += 1
            if severity == "HARD":
                policy_factor = 0.0
            else:
                policy_factor = min(policy_factor, 0.85)

        def add_recommendation(parameter_name: str, current_value: str, recommended_value: str, message: str) -> None:
            output["recommendations"].append(
                {
                    "parameter_name": parameter_name,
                    "current_value": current_value,
                    "recommended_value": recommended_value,
                    "expected_effect_message": message,
                }
            )

        min_order_area = float(request_row["min_order_area_km2"])
        if float(candidate_input["area_km2"]) < min_order_area:
            add_reason(
                "MIN_ORDER_AREA_NOT_MET",
                "HARD",
                f"후보 면적이 서비스 정책 최소 주문 면적 {min_order_area:.1f} km²를 충족하지 못합니다.",
            )
            add_recommendation(
                "area_km2",
                f"{float(candidate_input['area_km2']):.1f}",
                f"{min_order_area:.1f}",
                "후보 면적을 정책 최소 주문 면적 이상으로 조정해야 계약 가능한 주문으로 볼 수 있습니다.",
            )

        request_created_at = self._parse_utc(str(request_row["created_at"]))
        requested_start_at = self._parse_utc(str(request_row["requested_start_at"]))
        cutoff_at = requested_start_at - timedelta(hours=int(request_row["order_cutoff_hours"]))
        if request_created_at > cutoff_at:
            add_reason(
                "ORDER_CUTOFF_MISSED",
                "HARD",
                "요청 생성 시각이 서비스 정책상 주문 마감 시각을 지났습니다.",
            )
            add_recommendation(
                "requested_start_at",
                str(request_row["requested_start_at"]),
                cutoff_at.isoformat().replace("+00:00", "Z"),
                "촬영 시작 시각을 늦추거나 다른 서비스 티어를 사용해야 정책 마감 조건을 맞출 수 있습니다.",
            )

        request_priority = str(request_row["priority_tier"])
        policy_priority = str(request_row["policy_priority_tier"])
        candidate_priority = str(candidate_input["priority_tier"])
        if self._priority_rank(candidate_priority) > self._priority_rank(request_priority):
            add_reason(
                "PRIORITY_UPGRADE_REQUIRED",
                "SOFT",
                "후보 우선순위가 현재 요청 또는 계약된 서비스 티어보다 높습니다.",
            )
            add_recommendation(
                "priority_tier",
                candidate_priority,
                request_priority,
                "현재 요청 범위 안에서 검토하려면 후보 우선순위를 원 요청 수준으로 되돌리거나 서비스 변경 절차가 필요합니다.",
            )
        if self._priority_rank(request_priority) > self._priority_rank(policy_priority):
            add_reason(
                "SERVICE_POLICY_PRIORITY_MISMATCH",
                "HARD",
                "요청 우선순위가 연결된 서비스 정책의 허용 우선순위를 초과합니다.",
            )

        allowed_sensor_types = {str(item["sensor_type"]) for item in sensor_options}
        if allowed_sensor_types and str(candidate_input["sensor_type"]) not in allowed_sensor_types:
            add_reason(
                "SENSOR_OPTION_MISMATCH",
                "HARD",
                "후보 센서 유형이 요청에 등록된 센서 옵션과 일치하지 않습니다.",
            )
            add_recommendation(
                "sensor_type",
                str(candidate_input["sensor_type"]),
                ", ".join(sorted(allowed_sensor_types)),
                "후보 센서 유형은 요청에 등록된 센서 옵션 범위 안에서 선택해야 합니다.",
            )

        if str(candidate_input["sensor_type"]) == "SAR":
            mandatory_sar = [item for item in sensor_options if str(item["sensor_type"]) == "SAR" and int(item["is_mandatory"]) == 1]
            if mandatory_sar and any(not item.get("polarization_code") for item in mandatory_sar):
                add_reason(
                    "POLARIZATION_NOT_SPECIFIED",
                    "HARD",
                    "SAR 요청에는 필수 편파 정보가 있어야 합니다.",
                )
            for item in mandatory_sar:
                requested_pol = str(item.get("polarization_code") or "").strip()
                supported = {
                    token.strip()
                    for token in str(item.get("supported_polarizations") or "").split(",")
                    if token.strip()
                }
                if requested_pol and supported and requested_pol not in supported:
                    add_reason(
                        "POLARIZATION_UNSUPPORTED",
                        "HARD",
                        f"요청 편파 {requested_pol}가 선택된 SAR 모드의 지원 편파 범위를 벗어납니다.",
                    )
                    add_recommendation(
                        "polarization_code",
                        requested_pol,
                        ", ".join(sorted(supported)),
                        "지원되는 편파 조합 안에서 요청 편파를 조정해야 SAR 모드 제약을 만족할 수 있습니다.",
                    )

        product_policy = self._product_policy_for_sensor(str(candidate_input["sensor_type"]))
        for option in product_options:
            if str(option["product_level_code"]) not in product_policy["product_levels"]:
                add_reason(
                    "PRODUCT_LEVEL_UNSUPPORTED",
                    "HARD",
                    f"{candidate_input['sensor_type']} 센서 유형에서 요청한 제품 레벨 {option['product_level_code']}은 지원 대상이 아닙니다.",
                )
            if str(option["product_type_code"]) not in product_policy["product_types"]:
                add_reason(
                    "PRODUCT_TYPE_UNSUPPORTED",
                    "HARD",
                    f"{candidate_input['sensor_type']} 센서 유형에서 요청한 제품 유형 {option['product_type_code']}은 지원 대상이 아닙니다.",
                )
            if str(option["file_format_code"]) not in product_policy["file_formats"]:
                add_reason(
                    "FILE_FORMAT_UNSUPPORTED",
                    "HARD",
                    f"{candidate_input['sensor_type']} 센서 유형에서 요청한 파일 형식 {option['file_format_code']}은 지원 대상이 아닙니다.",
                )

        if aoi is not None and float(aoi["area_km2"]) < min_order_area:
            add_reason(
                "REQUEST_AOI_TOO_SMALL",
                "HARD",
                f"원본 요청 AOI 면적이 서비스 정책 최소 면적 {min_order_area:.1f} km²보다 작습니다.",
            )

        output["probabilities"]["p_policy"] = round(policy_factor, 4)
        output["probabilities"]["p_conflict_adjusted"] = round(float(output["probabilities"]["p_conflict_adjusted"]) * policy_factor, 4)
        output["probabilities"]["p_total_candidate"] = round(float(output["probabilities"]["p_total_candidate"]) * policy_factor, 4)
        output["checks"]["policy_feasible_flag"] = 0 if any(
            reason["reason_stage"] == "POLICY" and reason["reason_severity"] == "HARD"
            for reason in output["reasons"]
        ) else 1
        output["checks"]["policy_alert_count"] = policy_reason_count
        output["checks"]["policy_summary"] = "정책 제약 없음" if policy_reason_count == 0 else f"정책 검토 항목 {policy_reason_count}건"
        return self._recompute_output_status(output)

    def _get_nearest_weather_forecast(self, target_area_code: str, target_time: str) -> dict[str, Any] | None:
        sql = """
        SELECT
            weather_cell_forecast_id,
            forecast_at,
            cloud_pct,
            haze_index,
            confidence_score
        FROM weather_cell_forecast
        WHERE target_area_code = ?
        ORDER BY ABS(julianday(forecast_at) - julianday(?)), weather_cell_forecast_id
        LIMIT 1
        """
        return self._fetch_one(sql, (target_area_code, target_time))

    def _get_nearest_solar_condition(self, target_area_code: str, target_time: str) -> dict[str, Any] | None:
        sql = """
        SELECT
            solar_condition_snapshot_id,
            target_time,
            sun_elevation_deg,
            sun_azimuth_deg,
            daylight_flag
        FROM solar_condition_snapshot
        WHERE target_area_code = ?
        ORDER BY ABS(julianday(target_time) - julianday(?)), solar_condition_snapshot_id
        LIMIT 1
        """
        return self._fetch_one(sql, (target_area_code, target_time))

    def _get_latest_terrain_risk(self, target_area_code: str) -> dict[str, Any] | None:
        sql = """
        SELECT
            terrain_risk_snapshot_id,
            risk_type,
            risk_score,
            generated_at
        FROM terrain_risk_snapshot
        WHERE target_area_code = ?
        ORDER BY generated_at DESC, terrain_risk_snapshot_id DESC
        LIMIT 1
        """
        return self._fetch_one(sql, (target_area_code,))

    @staticmethod
    def _compute_shadow_risk_score(
        sun_elevation_deg: float,
        sun_azimuth_deg: float,
        centroid_lat: float | None = None,
        dominant_axis_deg: float | None = None,
        target_time: str | None = None,
        local_capture_minutes: int | None = None,
    ) -> float:
        elevation_component = max(0.0, min(1.0, (35.0 - sun_elevation_deg) / 20.0))
        azimuth_offset = abs(sun_azimuth_deg - 180.0)
        azimuth_component = 0.0
        if sun_elevation_deg < 45.0:
            azimuth_component = max(0.0, min(1.0, (azimuth_offset - 35.0) / 90.0))
        latitude_component = 0.0
        if centroid_lat is not None:
            latitude_component = max(0.0, min(1.0, (abs(float(centroid_lat)) - 30.0) / 20.0))
        orientation_component = 0.0
        if dominant_axis_deg is not None:
            orientation_offset = abs(((float(sun_azimuth_deg) - float(dominant_axis_deg) + 180.0) % 360.0) - 180.0)
            orientation_component = max(0.0, min(1.0, (45.0 - orientation_offset) / 45.0))
        seasonal_component = 0.0
        if target_time:
            month = FeasibilityRepository._parse_utc(str(target_time)).month
            seasonal_component = {
                12: 1.0,
                1: 1.0,
                2: 0.9,
                3: 0.55,
                4: 0.35,
                5: 0.2,
                6: 0.1,
                7: 0.1,
                8: 0.2,
                9: 0.35,
                10: 0.55,
                11: 0.8,
            }.get(month, 0.4)
        local_noon_component = 0.0
        if local_capture_minutes is not None:
            local_noon_component = max(0.0, min(1.0, abs(local_capture_minutes - 12 * 60) / 240.0))
        return round(
            min(
                1.0,
                (elevation_component * 0.5)
                + (azimuth_component * 0.15)
                + (latitude_component * 0.1)
                + (orientation_component * 0.15)
                + (seasonal_component * 0.1)
                + (local_noon_component * 0.1),
            ),
            4,
        )

    def _apply_environment_snapshot_validation(
        self,
        aoi: dict[str, Any] | None,
        constraint: dict[str, Any] | None,
        candidate_input: dict[str, Any],
        access: dict[str, Any] | None,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        if aoi is None:
            return output

        target_area_code = f"AOI-REQ-{aoi['request_id']}"
        target_time = (
            access["access_start_at"]
            if access is not None and access.get("access_start_at")
            else None
        )
        env_factor = 1.0

        def add_env_reason(code: str, severity: str, message: str) -> None:
            nonlocal env_factor
            output["reasons"].append(
                {
                    "reason_code": code,
                    "reason_stage": "ENVIRONMENT",
                    "reason_severity": severity,
                    "reason_message": message,
                }
            )
            if severity == "HARD":
                env_factor = 0.0
            else:
                env_factor = min(env_factor, 0.85)

        if str(candidate_input["sensor_type"]) == "OPTICAL" and target_time is not None:
            weather = self._get_nearest_weather_forecast(target_area_code, target_time)
            solar = self._get_nearest_solar_condition(target_area_code, target_time)
            local_capture_minutes = None
            if aoi.get("centroid_lon") is not None:
                utc_capture = self._parse_utc(str(target_time))
                local_offset_minutes = int(round(float(aoi["centroid_lon"]) * 4.0))
                local_capture_minutes = (
                    utc_capture.hour * 60
                    + utc_capture.minute
                    + local_offset_minutes
                ) % (24 * 60)
                output["checks"]["local_capture_time_hhmm"] = self._format_minutes_hhmm(local_capture_minutes)
                if constraint is not None and constraint.get("preferred_local_time_start") and constraint.get("preferred_local_time_end"):
                    preferred_start = self._parse_time_hhmm(str(constraint["preferred_local_time_start"]))
                    preferred_end = self._parse_time_hhmm(str(constraint["preferred_local_time_end"]))
                    output["checks"]["preferred_local_time_start"] = constraint["preferred_local_time_start"]
                    output["checks"]["preferred_local_time_end"] = constraint["preferred_local_time_end"]
                    window_distance_minutes = self._local_time_window_distance_minutes(
                        local_capture_minutes,
                        preferred_start,
                        preferred_end,
                    )
                    output["checks"]["local_time_window_distance_min"] = window_distance_minutes
                    if window_distance_minutes > 180:
                        add_env_reason(
                            "LOCAL_TIME_WINDOW_MISALIGNED",
                            "HARD",
                            "예상 현지 촬영 시각이 요청 선호 현지시각 창에서 크게 벗어납니다.",
                        )
                    elif window_distance_minutes > 0:
                        add_env_reason(
                            "LOCAL_TIME_WINDOW_MISALIGNED",
                            "SOFT",
                            "예상 현지 촬영 시각이 요청 선호 현지시각 창을 일부 벗어납니다.",
                        )
            if local_capture_minutes is not None:
                output["checks"]["local_noon_distance_min"] = abs(local_capture_minutes - 12 * 60)
            if aoi.get("dominant_axis_deg") is not None:
                output["checks"]["dominant_axis_deg"] = aoi["dominant_axis_deg"]

            if weather is not None:
                output["checks"]["forecast_cloud_pct"] = weather["cloud_pct"]
                output["checks"]["forecast_haze_index"] = weather["haze_index"]
                output["checks"]["forecast_confidence_score"] = weather["confidence_score"]
                env_factor *= max(0.75, min(1.0, 0.75 + (float(weather["confidence_score"]) * 0.25)))

                max_haze_index = constraint["max_haze_index"] if constraint is not None else None
                if max_haze_index is not None and weather["haze_index"] is not None and float(weather["haze_index"]) > float(max_haze_index):
                    add_env_reason(
                        "HAZE_INDEX_TOO_HIGH",
                        "SOFT",
                        "예보 haze 지수가 요청 광학 품질 기준을 초과합니다.",
                    )

            if solar is not None:
                output["checks"]["forecast_sun_elevation_deg"] = solar["sun_elevation_deg"]
                output["checks"]["forecast_sun_azimuth_deg"] = solar["sun_azimuth_deg"]
                output["checks"]["daylight_flag"] = solar["daylight_flag"]
                if int(solar["daylight_flag"]) == 0:
                    add_env_reason(
                        "DAYLIGHT_NOT_AVAILABLE",
                        "HARD",
                        "예상 촬영 시각이 주간 조건을 만족하지 않습니다.",
                    )
                elif constraint is not None and constraint.get("min_sun_elevation_deg") is not None and float(solar["sun_elevation_deg"]) < float(constraint["min_sun_elevation_deg"]):
                    add_env_reason(
                        "SUN_ELEVATION_FORECAST_LOW",
                        "HARD",
                        "예보 기반 태양 고도가 요청 최소 조도 기준보다 낮습니다.",
                    )
                shadow_risk_score = self._compute_shadow_risk_score(
                    float(solar["sun_elevation_deg"]),
                    float(solar["sun_azimuth_deg"]),
                    float(aoi["centroid_lat"]) if aoi.get("centroid_lat") is not None else None,
                    float(aoi["dominant_axis_deg"]) if aoi.get("dominant_axis_deg") is not None else None,
                    str(target_time),
                    local_capture_minutes,
                )
                output["checks"]["shadow_risk_score"] = shadow_risk_score
                if shadow_risk_score >= 0.75:
                    add_env_reason(
                        "SHADOW_RISK_HIGH",
                        "HARD",
                        "예보 태양고도와 방위각 조합상 그림자 영향이 커 광학 판독 품질을 확보하기 어렵습니다.",
                    )
                elif shadow_risk_score >= 0.35:
                    add_env_reason(
                        "SHADOW_RISK_ELEVATED",
                        "SOFT",
                        "예보 태양고도와 방위각 조합상 그림자 영향이 커 광학 판독 품질 저하 가능성이 있습니다.",
                    )

        if str(candidate_input["sensor_type"]) == "SAR":
            terrain = self._get_latest_terrain_risk(target_area_code)
            if terrain is not None:
                output["checks"]["terrain_risk_type"] = terrain["risk_type"]
                output["checks"]["terrain_risk_score"] = terrain["risk_score"]
                risk_score = float(terrain["risk_score"])
                env_factor *= max(0.0, 1.0 - risk_score)
                if risk_score >= 0.2:
                    add_env_reason(
                        "TERRAIN_RISK_HIGH",
                        "HARD",
                        "지형 layover/shadow 위험도가 높아 현재 SAR 조건으로는 수행이 어렵습니다.",
                    )
                elif risk_score >= 0.1:
                    add_env_reason(
                        "TERRAIN_RISK_ELEVATED",
                        "SOFT",
                        "지형 layover/shadow 위험도가 높아 SAR 판독 품질 저하 가능성이 있습니다.",
                    )

        output["probabilities"]["p_env"] = round(float(output["probabilities"]["p_env"]) * env_factor, 4)
        output["probabilities"]["p_total_candidate"] = round(float(output["probabilities"]["p_total_candidate"]) * env_factor, 4)
        return self._recompute_output_status(output)

    def _prepare_candidate_geometry_input(
        self,
        request_code: str,
        candidate_code: str | None,
        candidate_input: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        adjusted = dict(candidate_input)
        explicit_start = adjusted.get("opportunity_start_at")
        explicit_end = adjusted.get("opportunity_end_at")
        if explicit_start and explicit_end:
            return adjusted, {
                "access_opportunity_id": None,
                "pass_start_at": explicit_start,
                "pass_end_at": explicit_end,
                "access_start_at": explicit_start,
                "access_end_at": explicit_end,
                "required_off_nadir_deg": adjusted.get("required_off_nadir_deg"),
                "predicted_incidence_deg": adjusted.get("predicted_incidence_deg"),
                "coverage_ratio_predicted": adjusted.get("coverage_ratio_predicted"),
                "geometric_feasible_flag": 1,
                "geometry_source": "CANDIDATE_OPPORTUNITY_INPUT",
            }
        if not candidate_code:
            return adjusted, None

        access = self.get_request_candidate_access_opportunity(request_code, candidate_code)
        if access is None:
            return adjusted, None

        if access.get("required_off_nadir_deg") is not None:
            adjusted["required_off_nadir_deg"] = access["required_off_nadir_deg"]
        if access.get("predicted_incidence_deg") is not None:
            adjusted["predicted_incidence_deg"] = access["predicted_incidence_deg"]
        if access.get("coverage_ratio_predicted") is not None:
            adjusted["coverage_ratio_predicted"] = access["coverage_ratio_predicted"]
        return adjusted, access

    @staticmethod
    def _contact_capacity_gbit(contact: dict[str, Any]) -> float:
        start_at = FeasibilityRepository._parse_utc(str(contact["contact_start_at"]))
        end_at = FeasibilityRepository._parse_utc(str(contact["contact_end_at"]))
        duration_seconds = max((end_at - start_at).total_seconds(), 0.0)
        return round(
            float(contact["downlink_rate_mbps"]) * duration_seconds * float(contact["link_efficiency_pct"]) / 1000.0,
            4,
        )

    def _get_candidate_contact_window(self, access: dict[str, Any]) -> dict[str, Any] | None:
        sql = """
        SELECT
            scw.contact_window_id,
            scw.ground_station_id,
            gs.station_code,
            gs.station_name,
            scw.satellite_id,
            scw.contact_start_at,
            scw.contact_end_at,
            scw.downlink_rate_mbps,
            scw.link_efficiency_pct,
            scw.availability_status
        FROM station_contact_window scw
        JOIN ground_station gs ON gs.ground_station_id = scw.ground_station_id
        WHERE scw.satellite_id = ?
          AND scw.contact_start_at >= ?
        ORDER BY scw.contact_start_at, scw.contact_window_id
        LIMIT 1
        """
        return self._fetch_one(sql, (access["satellite_id"], access["access_end_at"]))

    def _list_conflicting_existing_tasks(self, access: dict[str, Any]) -> list[dict[str, Any]]:
        sql = """
        SELECT
            existing_task_id,
            priority_tier,
            task_start_at,
            task_end_at,
            reserved_volume_gbit,
            task_status
        FROM existing_task
        WHERE satellite_id = ?
          AND task_status IN ('SCHEDULED', 'RESERVED')
          AND task_start_at < ?
          AND task_end_at > ?
        ORDER BY task_start_at, existing_task_id
        """
        return self._fetch_all(sql, (access["satellite_id"], access["access_end_at"], access["access_start_at"]))

    def _list_conflicting_downlink_bookings(self, contact: dict[str, Any]) -> list[dict[str, Any]]:
        sql = """
        SELECT
            existing_downlink_booking_id,
            booking_start_at,
            booking_end_at,
            reserved_volume_gbit,
            booking_status
        FROM existing_downlink_booking
        WHERE satellite_id = ?
          AND ground_station_id = ?
          AND booking_status IN ('RESERVED', 'SCHEDULED')
          AND booking_start_at < ?
          AND booking_end_at > ?
        ORDER BY booking_start_at, existing_downlink_booking_id
        """
        return self._fetch_all(
            sql,
            (
                contact["satellite_id"],
                contact["ground_station_id"],
                contact["contact_end_at"],
                contact["contact_start_at"],
            ),
        )

    def _prepare_candidate_operational_input(
        self,
        candidate_input: dict[str, Any],
        access: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
        adjusted = dict(candidate_input)
        if access is None:
            return adjusted, None, [], []
        if str(access.get("geometry_source") or "") == "CANDIDATE_OPPORTUNITY_INPUT" and access.get("satellite_id") is None:
            return adjusted, None, [], []

        contact = self._get_candidate_contact_window(access)
        if contact is None:
            return adjusted, None, self._list_conflicting_existing_tasks(access), []

        bookings = self._list_conflicting_downlink_bookings(contact)
        reserved_volume_gbit = round(sum(float(item["reserved_volume_gbit"]) for item in bookings), 4)
        contact_capacity_gbit = self._contact_capacity_gbit(contact)
        net_contact_capacity_gbit = max(0.0, round(contact_capacity_gbit - reserved_volume_gbit, 4))
        adjusted["available_downlink_gbit"] = min(float(adjusted["available_downlink_gbit"]), net_contact_capacity_gbit)
        contact["contact_capacity_gbit"] = contact_capacity_gbit
        contact["reserved_volume_gbit"] = reserved_volume_gbit
        contact["net_contact_capacity_gbit"] = net_contact_capacity_gbit
        return adjusted, contact, self._list_conflicting_existing_tasks(access), bookings

    def _apply_operational_validation(
        self,
        candidate_priority: str,
        contact: dict[str, Any] | None,
        task_conflicts: list[dict[str, Any]],
        booking_conflicts: list[dict[str, Any]],
        output: dict[str, Any],
    ) -> dict[str, Any]:
        conflict_factor = 1.0

        if contact is not None:
            output["checks"]["selected_contact_window_id"] = contact["contact_window_id"]
            output["checks"]["selected_ground_station_code"] = contact["station_code"]
            output["checks"]["selected_ground_station_name"] = contact["station_name"]
            output["checks"]["contact_start_at"] = contact["contact_start_at"]
            output["checks"]["contact_end_at"] = contact["contact_end_at"]
            output["checks"]["contact_capacity_gbit"] = contact["contact_capacity_gbit"]
            output["checks"]["booking_reserved_gbit"] = contact["reserved_volume_gbit"]
            output["checks"]["net_contact_capacity_gbit"] = contact["net_contact_capacity_gbit"]

        output["checks"]["task_conflict_count"] = len(task_conflicts)
        output["checks"]["booking_conflict_count"] = len(booking_conflicts)

        if contact is None:
            output["reasons"].append(
                {
                    "reason_code": "NO_CONTACT_WINDOW_AFTER_CAPTURE",
                    "reason_stage": "DOWNLINK",
                    "reason_severity": "HARD",
                    "reason_message": "촬영 직후 사용할 수 있는 지상국 downlink 창을 찾지 못했습니다.",
                }
            )
            output["recommendations"].append(
                {
                    "parameter_name": "contact_window",
                    "current_value": "none",
                    "recommended_value": "later contact or different station",
                    "expected_effect_message": "더 늦은 지상국 패스나 다른 지상국을 확보해야 다운링크 가능성을 검토할 수 있습니다.",
                }
            )
            conflict_factor = 0.0

        for task in task_conflicts:
            existing_priority = str(task["priority_tier"])
            if self._priority_rank(existing_priority) >= self._priority_rank(candidate_priority):
                output["reasons"].append(
                    {
                        "reason_code": "EXISTING_TASK_CONFLICT",
                        "reason_stage": "SCHEDULING",
                        "reason_severity": "HARD",
                        "reason_message": "동일 위성에 이미 예약된 촬영 task와 시간이 겹치며 우선순위가 더 높거나 같습니다.",
                    }
                )
                conflict_factor = 0.0
            else:
                output["reasons"].append(
                    {
                        "reason_code": "TASK_PREEMPTION_REVIEW",
                        "reason_stage": "SCHEDULING",
                        "reason_severity": "SOFT",
                        "reason_message": "기존 촬영 task와 시간이 겹치므로 선행 task 조정 여부를 운영자가 검토해야 합니다.",
                    }
                )
                conflict_factor = min(conflict_factor, 0.8)

        if contact is not None:
            if str(contact["availability_status"]) != "AVAILABLE":
                output["reasons"].append(
                    {
                        "reason_code": "CONTACT_WINDOW_UNAVAILABLE",
                        "reason_stage": "DOWNLINK",
                        "reason_severity": "HARD",
                        "reason_message": "선택된 지상국 contact window가 현재 사용 불가 상태입니다.",
                    }
                )
                conflict_factor = 0.0
            elif booking_conflicts and float(contact["net_contact_capacity_gbit"]) <= 0:
                output["reasons"].append(
                    {
                        "reason_code": "CONTACT_WINDOW_FULLY_BOOKED",
                        "reason_stage": "DOWNLINK",
                        "reason_severity": "HARD",
                        "reason_message": "선택된 지상국 contact window 용량이 기존 예약으로 모두 소진됐습니다.",
                    }
                )
                conflict_factor = 0.0
            elif booking_conflicts:
                output["reasons"].append(
                    {
                        "reason_code": "CONTACT_WINDOW_PARTIALLY_BOOKED",
                        "reason_stage": "DOWNLINK",
                        "reason_severity": "SOFT",
                        "reason_message": "선택된 지상국 contact window 일부 용량이 이미 예약되어 있어 다운링크 여유가 줄었습니다.",
                    }
                )
                conflict_factor = min(conflict_factor, 0.85)

        output["probabilities"]["p_conflict_adjusted"] = round(float(output["probabilities"]["p_conflict_adjusted"]) * conflict_factor, 4)
        output["probabilities"]["p_total_candidate"] = round(float(output["probabilities"]["p_total_candidate"]) * conflict_factor, 4)
        return self._recompute_output_status(output)

    def _apply_access_opportunity_validation(self, access: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        geometry_source = str(access.get("geometry_source") or "ACCESS_OPPORTUNITY")
        output["checks"]["geometry_source"] = geometry_source
        output["checks"]["access_opportunity_id"] = access["access_opportunity_id"]
        output["checks"]["pass_start_at"] = access["pass_start_at"]
        output["checks"]["pass_end_at"] = access["pass_end_at"]
        output["checks"]["access_start_at"] = access["access_start_at"]
        output["checks"]["access_end_at"] = access["access_end_at"]
        output["checks"]["geometric_feasible_flag"] = access["geometric_feasible_flag"]

        if geometry_source == "CANDIDATE_OPPORTUNITY_INPUT":
            return output

        if int(access["geometric_feasible_flag"]) == 0:
            output["reasons"].append(
                {
                    "reason_code": "ACCESS_OPPORTUNITY_INFEASIBLE",
                    "reason_stage": "GEOMETRY",
                    "reason_severity": "HARD",
                    "reason_message": "매핑된 access opportunity가 사전 기하 계산에서 infeasible로 판정됐습니다.",
                }
            )
            output["recommendations"].append(
                {
                    "parameter_name": "window_or_geometry",
                    "current_value": f"{access['access_start_at']} | coverage {access['coverage_ratio_predicted']}",
                    "recommended_value": "다른 pass 또는 더 넓은 시간창 사용",
                    "expected_effect_message": "다른 access opportunity를 사용할 수 있도록 시간창을 늘리거나 조건을 완화해야 합니다.",
                }
            )
            output["probabilities"]["p_geo"] = 0.0
            output["probabilities"]["p_total_candidate"] = 0.0

        return self._recompute_output_status(output)

    def get_request_aoi(self, request_key: str) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return None
        sql = """
        SELECT
            ra.*
        FROM request_aoi ra
        JOIN feasibility_request fr ON fr.request_id = ra.request_id
        WHERE fr.request_code = ?
        """
        return self._fetch_one(sql, (internal_request_code,))

    def get_request_constraint(self, request_key: str) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return None
        sql = """
        SELECT
            rc.*
        FROM request_constraint rc
        JOIN feasibility_request fr ON fr.request_id = rc.request_id
        WHERE fr.request_code = ?
        """
        return self._fetch_one(sql, (internal_request_code,))

    def list_request_sensor_options(self, request_key: str) -> list[dict[str, Any]]:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return []
        sql = """
        SELECT
            rso.request_sensor_option_id,
            s.satellite_code,
            s.satellite_name,
            se.sensor_name,
            se.sensor_type,
            sm.mode_code,
            sm.mode_name,
            sm.supported_polarizations,
            rso.preference_rank,
            rso.is_mandatory,
            rso.polarization_code
        FROM request_sensor_option rso
        JOIN feasibility_request fr ON fr.request_id = rso.request_id
        JOIN satellite s ON s.satellite_id = rso.satellite_id
        JOIN sensor se ON se.sensor_id = rso.sensor_id
        JOIN sensor_mode sm ON sm.sensor_mode_id = rso.sensor_mode_id
        WHERE fr.request_code = ?
        ORDER BY rso.preference_rank
        """
        return self._fetch_all(sql, (internal_request_code,))

    def list_request_product_options(self, request_key: str) -> list[dict[str, Any]]:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return []
        sql = """
        SELECT
            rpo.*
        FROM request_product_option rpo
        JOIN feasibility_request fr ON fr.request_id = rpo.request_id
        WHERE fr.request_code = ?
        ORDER BY rpo.request_product_option_id
        """
        return self._fetch_all(sql, (internal_request_code,))

    def list_request_access_opportunities(self, request_key: str) -> list[dict[str, Any]]:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return []
        sql = """
        SELECT
            ao.access_opportunity_id,
            ao.access_start_at,
            ao.access_end_at,
            ao.required_off_nadir_deg,
            ao.predicted_incidence_deg,
            ao.coverage_ratio_predicted,
            ao.geometric_feasible_flag,
            sp.pass_start_at,
            sp.pass_end_at,
            sp.satellite_id,
            se.sensor_type,
            se.sensor_name,
            sm.mode_code,
            sm.mode_name
        FROM access_opportunity ao
        JOIN request_aoi ra ON ra.request_aoi_id = ao.request_aoi_id
        JOIN feasibility_request fr ON fr.request_id = ra.request_id
        JOIN satellite_pass sp ON sp.satellite_pass_id = ao.satellite_pass_id
        JOIN sensor se ON se.sensor_id = ao.sensor_id
        JOIN sensor_mode sm ON sm.sensor_mode_id = ao.sensor_mode_id
        WHERE fr.request_code = ?
        ORDER BY ao.access_start_at, ao.access_opportunity_id
        """
        return self._fetch_all(sql, (internal_request_code,))

    def get_request_candidate_access_opportunity(self, request_key: str, candidate_code: str) -> dict[str, Any] | None:
        candidate = self.get_request_candidate(request_key, candidate_code)
        if candidate is None:
            return None
        ordered = self.list_request_access_opportunities(request_key)
        index = max(int(candidate["candidate_rank"]) - 1, 0)
        if index >= len(ordered):
            return None
        return ordered[index]

    def list_request_candidates(self, request_key: str) -> list[dict[str, Any]]:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return []
        sql = """
        SELECT
            rc.request_candidate_id,
            rc.candidate_code,
            rc.candidate_title,
            rc.candidate_description,
            rc.candidate_status,
            rc.candidate_rank,
            rc.is_baseline,
            rci.sensor_type,
            rci.priority_tier,
            rci.input_version_no,
            rcr.request_candidate_run_id AS latest_run_id,
            rcr.simulated_at AS latest_simulated_at,
            rcr.final_verdict AS latest_final_verdict,
            rcr.candidate_status AS latest_candidate_status,
            rcr.p_total_candidate AS latest_overall_probability,
            rcr.dominant_risk_code AS latest_dominant_risk_code,
            rcr.summary_message AS latest_summary_message
        FROM request_candidate rc
        JOIN feasibility_request fr ON fr.request_id = rc.request_id
        JOIN request_candidate_input rci ON rci.request_candidate_id = rc.request_candidate_id
        LEFT JOIN request_candidate_run rcr ON rcr.request_candidate_run_id = (
            SELECT rcr2.request_candidate_run_id
            FROM request_candidate_run rcr2
            WHERE rcr2.request_candidate_id = rc.request_candidate_id
            ORDER BY rcr2.simulated_at DESC, rcr2.request_candidate_run_id DESC
            LIMIT 1
        )
        WHERE fr.request_code = ?
        ORDER BY rc.candidate_rank, rc.request_candidate_id
        """
        items = self._fetch_all(sql, (internal_request_code,))
        for item in items:
            candidate_input = self.get_request_candidate_input(internal_request_code, str(item["candidate_code"]))
            if candidate_input is None:
                continue
            current = self.simulate_request_candidate_input(internal_request_code, candidate_input, str(item["candidate_code"]))
            if current is None:
                continue
            item["current_candidate_status"] = current["candidate_status"]
            item["current_final_verdict"] = current["final_verdict"]
            item["current_overall_probability"] = current["probabilities"]["p_total_candidate"]
            item["current_dominant_risk_code"] = current.get("dominant_risk_code")
            item["current_summary_message"] = current["summary_message"]
        return items

    def get_request_candidate(self, request_key: str, candidate_code: str) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return None
        sql = """
        SELECT
            rc.request_candidate_id,
            rc.candidate_code,
            rc.candidate_title,
            rc.candidate_description,
            rc.candidate_status,
            rc.candidate_rank,
            rc.is_baseline,
            rc.created_at,
            rc.updated_at
        FROM request_candidate rc
        JOIN feasibility_request fr ON fr.request_id = rc.request_id
        WHERE fr.request_code = ? AND rc.candidate_code = ?
        """
        return self._fetch_one(sql, (internal_request_code, candidate_code))

    def get_request_candidate_input(self, request_key: str, candidate_code: str) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return None
        sql = """
        SELECT
            rci.*
        FROM request_candidate_input rci
        JOIN request_candidate rc ON rc.request_candidate_id = rci.request_candidate_id
        JOIN feasibility_request fr ON fr.request_id = rc.request_id
        WHERE fr.request_code = ? AND rc.candidate_code = ?
        """
        return self._fetch_one(sql, (internal_request_code, candidate_code))

    def list_request_candidate_runs(self, request_key: str, candidate_code: str) -> list[dict[str, Any]]:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return []
        sql = """
        SELECT
            rcr.*
        FROM request_candidate_run rcr
        JOIN request_candidate rc ON rc.request_candidate_id = rcr.request_candidate_id
        JOIN feasibility_request fr ON fr.request_id = rc.request_id
        WHERE fr.request_code = ? AND rc.candidate_code = ?
        ORDER BY rcr.simulated_at DESC, rcr.request_candidate_run_id DESC
        """
        return self._fetch_all(sql, (internal_request_code, candidate_code))

    def get_request_candidate_latest_run(self, request_key: str, candidate_code: str) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return None
        sql = """
        SELECT
            rcr.*
        FROM request_candidate_run rcr
        JOIN request_candidate rc ON rc.request_candidate_id = rcr.request_candidate_id
        JOIN feasibility_request fr ON fr.request_id = rc.request_id
        WHERE fr.request_code = ? AND rc.candidate_code = ?
        ORDER BY rcr.simulated_at DESC, rcr.request_candidate_run_id DESC
        LIMIT 1
        """
        return self._fetch_one(sql, (internal_request_code, candidate_code))

    def list_request_candidate_run_reasons(self, request_candidate_run_id: int) -> list[dict[str, Any]]:
        return self._fetch_all(
            """
            SELECT
                *
            FROM request_candidate_run_reason
            WHERE request_candidate_run_id = ?
            ORDER BY request_candidate_run_reason_id
            """,
            (request_candidate_run_id,),
        )

    def list_request_candidate_run_recommendations(self, request_candidate_run_id: int) -> list[dict[str, Any]]:
        return self._fetch_all(
            """
            SELECT
                *
            FROM request_candidate_run_recommendation
            WHERE request_candidate_run_id = ?
            ORDER BY request_candidate_run_recommendation_id
            """,
            (request_candidate_run_id,),
        )

    def get_request_candidate_report(self, request_key: str, candidate_code: str) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return None
        candidate = self.get_request_candidate(internal_request_code, candidate_code)
        if candidate is None:
            return None

        candidate_input = self.get_request_candidate_input(internal_request_code, candidate_code)
        latest_run = self.get_request_candidate_latest_run(internal_request_code, candidate_code)
        latest_run_id = int(latest_run["request_candidate_run_id"]) if latest_run is not None else None

        return {
            "request": self.get_request(internal_request_code),
            "candidate": candidate,
            "input": candidate_input,
            "current_evaluation": self.simulate_request_candidate_input(internal_request_code, candidate_input, candidate_code) if candidate_input is not None else None,
            "latest_run": latest_run,
            "latest_reasons": self.list_request_candidate_run_reasons(latest_run_id) if latest_run_id is not None else [],
            "latest_recommendations": self.list_request_candidate_run_recommendations(latest_run_id) if latest_run_id is not None else [],
            "runs": self.list_request_candidate_runs(internal_request_code, candidate_code),
        }

    def create_request_candidate(self, request_key: str, candidate: dict[str, Any], candidate_input: dict[str, Any]) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        request_id = self._resolve_request_id(request_key)
        if request_id is None:
            return None

        with self._connect() as conn:
            generated_candidate_code = self._generate_candidate_code(conn, request_id, str(candidate_input["sensor_type"]))
            cursor = conn.execute(
                """
                INSERT INTO request_candidate (
                    request_id, candidate_code, candidate_title, candidate_description, candidate_status,
                    candidate_rank, is_baseline, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    generated_candidate_code,
                    candidate["candidate_title"],
                    candidate["candidate_description"],
                    candidate.get("candidate_status", "READY"),
                    candidate["candidate_rank"],
                    1 if candidate.get("is_baseline", False) else 0,
                    candidate["created_at"],
                    candidate["updated_at"],
                ),
            )
            candidate_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO request_candidate_input (
                    request_candidate_id, sensor_type, priority_tier, area_km2, window_hours,
                    opportunity_start_at, opportunity_end_at,
                    cloud_pct, max_cloud_pct, required_off_nadir_deg, max_off_nadir_deg,
                    predicted_incidence_deg, min_incidence_deg, max_incidence_deg, sun_elevation_deg,
                    min_sun_elevation_deg, coverage_ratio_predicted, coverage_ratio_required,
                    expected_data_volume_gbit, recorder_free_gbit, recorder_backlog_gbit,
                    available_downlink_gbit, power_margin_pct, thermal_margin_pct, input_version_no,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    candidate_input["sensor_type"],
                    candidate_input["priority_tier"],
                    candidate_input["area_km2"],
                    candidate_input["window_hours"],
                    candidate_input.get("opportunity_start_at"),
                    candidate_input.get("opportunity_end_at"),
                    candidate_input.get("cloud_pct"),
                    candidate_input.get("max_cloud_pct"),
                    candidate_input.get("required_off_nadir_deg"),
                    candidate_input.get("max_off_nadir_deg"),
                    candidate_input.get("predicted_incidence_deg"),
                    candidate_input.get("min_incidence_deg"),
                    candidate_input.get("max_incidence_deg"),
                    candidate_input.get("sun_elevation_deg"),
                    candidate_input.get("min_sun_elevation_deg"),
                    candidate_input["coverage_ratio_predicted"],
                    candidate_input["coverage_ratio_required"],
                    candidate_input["expected_data_volume_gbit"],
                    candidate_input["recorder_free_gbit"],
                    candidate_input["recorder_backlog_gbit"],
                    candidate_input["available_downlink_gbit"],
                    candidate_input["power_margin_pct"],
                    candidate_input["thermal_margin_pct"],
                    1,
                    candidate["created_at"],
                    candidate["updated_at"],
                ),
            )
            if candidate.get("is_baseline", False):
                self._clear_other_baselines(conn, request_id, candidate_id)
            self._ensure_request_baseline(conn, request_id)
            conn.commit()

        return self.get_request_candidate_report(internal_request_code, generated_candidate_code)

    def update_request_candidate(self, request_key: str, candidate_code: str, candidate: dict[str, Any], candidate_input: dict[str, Any]) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        request_candidate_id = self._resolve_request_candidate_id(request_key, candidate_code)
        if request_candidate_id is None:
            return None

        current_input = self.get_request_candidate_input(internal_request_code, candidate_code)
        next_version = int(current_input["input_version_no"]) + 1 if current_input is not None else 1
        request_id = self._resolve_request_id(internal_request_code)

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE request_candidate
                SET candidate_title = ?, candidate_description = ?, candidate_status = ?,
                    candidate_rank = ?, is_baseline = ?, updated_at = ?
                WHERE request_candidate_id = ?
                """,
                (
                    candidate["candidate_title"],
                    candidate["candidate_description"],
                    candidate.get("candidate_status", "READY"),
                    candidate["candidate_rank"],
                    1 if candidate.get("is_baseline", False) else 0,
                    candidate["updated_at"],
                    request_candidate_id,
                ),
            )
            conn.execute(
                """
                UPDATE request_candidate_input
                SET sensor_type = ?, priority_tier = ?, area_km2 = ?, window_hours = ?,
                    opportunity_start_at = ?, opportunity_end_at = ?,
                    cloud_pct = ?, max_cloud_pct = ?, required_off_nadir_deg = ?, max_off_nadir_deg = ?,
                    predicted_incidence_deg = ?, min_incidence_deg = ?, max_incidence_deg = ?,
                    sun_elevation_deg = ?, min_sun_elevation_deg = ?, coverage_ratio_predicted = ?,
                    coverage_ratio_required = ?, expected_data_volume_gbit = ?, recorder_free_gbit = ?,
                    recorder_backlog_gbit = ?, available_downlink_gbit = ?, power_margin_pct = ?,
                    thermal_margin_pct = ?, input_version_no = ?, updated_at = ?
                WHERE request_candidate_id = ?
                """,
                (
                    candidate_input["sensor_type"],
                    candidate_input["priority_tier"],
                    candidate_input["area_km2"],
                    candidate_input["window_hours"],
                    candidate_input.get("opportunity_start_at"),
                    candidate_input.get("opportunity_end_at"),
                    candidate_input.get("cloud_pct"),
                    candidate_input.get("max_cloud_pct"),
                    candidate_input.get("required_off_nadir_deg"),
                    candidate_input.get("max_off_nadir_deg"),
                    candidate_input.get("predicted_incidence_deg"),
                    candidate_input.get("min_incidence_deg"),
                    candidate_input.get("max_incidence_deg"),
                    candidate_input.get("sun_elevation_deg"),
                    candidate_input.get("min_sun_elevation_deg"),
                    candidate_input["coverage_ratio_predicted"],
                    candidate_input["coverage_ratio_required"],
                    candidate_input["expected_data_volume_gbit"],
                    candidate_input["recorder_free_gbit"],
                    candidate_input["recorder_backlog_gbit"],
                    candidate_input["available_downlink_gbit"],
                    candidate_input["power_margin_pct"],
                    candidate_input["thermal_margin_pct"],
                    next_version,
                    candidate["updated_at"],
                    request_candidate_id,
                ),
            )
            if request_id is not None and candidate.get("is_baseline", False):
                self._clear_other_baselines(conn, request_id, request_candidate_id)
            if request_id is not None:
                self._ensure_request_baseline(conn, request_id)
            conn.commit()

        return self.get_request_candidate_report(internal_request_code, candidate_code)

    def delete_request_candidate(self, request_key: str, candidate_code: str) -> bool:
        internal_request_code = self._resolve_internal_request_code(request_key)
        request_candidate_id = self._resolve_request_candidate_id(request_key, candidate_code)
        if request_candidate_id is None:
            return False

        with self._connect() as conn:
            run_rows = conn.execute(
                "SELECT request_candidate_run_id FROM request_candidate_run WHERE request_candidate_id = ?",
                (request_candidate_id,),
            ).fetchall()
            run_ids = [int(row["request_candidate_run_id"]) for row in run_rows]
            for run_id in run_ids:
                conn.execute(
                    "DELETE FROM request_candidate_run_reason WHERE request_candidate_run_id = ?",
                    (run_id,),
                )
                conn.execute(
                    "DELETE FROM request_candidate_run_recommendation WHERE request_candidate_run_id = ?",
                    (run_id,),
                )
            conn.execute(
                "DELETE FROM request_candidate_run WHERE request_candidate_id = ?",
                (request_candidate_id,),
            )
            conn.execute(
                "DELETE FROM request_candidate_input WHERE request_candidate_id = ?",
                (request_candidate_id,),
            )
            conn.execute(
                "DELETE FROM request_candidate WHERE request_candidate_id = ?",
                (request_candidate_id,),
            )
            request_id = self._resolve_request_id(internal_request_code) if internal_request_code is not None else None
            if request_id is not None:
                self._ensure_request_baseline(conn, request_id)
            conn.commit()
        return True

    def save_request_candidate_run(
        self,
        request_key: str,
        candidate_code: str,
        output: dict[str, Any],
        simulated_at: str,
        trigger: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        request_candidate_id = self._resolve_request_candidate_id(request_key, candidate_code)
        if request_candidate_id is None:
            return None

        latest_run = self._fetch_one(
            """
            SELECT run_sequence_no
            FROM request_candidate_run
            WHERE request_candidate_id = ?
            ORDER BY run_sequence_no DESC
            LIMIT 1
            """,
            (request_candidate_id,),
        )
        next_sequence = (int(latest_run["run_sequence_no"]) + 1) if latest_run is not None else 1
        current_input = self.get_request_candidate_input(internal_request_code, candidate_code)
        input_version_no = int(current_input["input_version_no"]) if current_input is not None and current_input.get("input_version_no") is not None else None

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO request_candidate_run (
                    request_candidate_id, run_sequence_no, input_version_no, simulated_at,
                    run_trigger_type, run_trigger_source_code, run_trigger_parameter_name, run_trigger_note,
                    candidate_status, final_verdict,
                    summary_message, dominant_risk_code, p_geo, p_env, p_resource, p_downlink,
                    p_conflict_adjusted, p_total_candidate, resource_feasible_flag, downlink_feasible_flag,
                    storage_headroom_gbit, backlog_after_capture_gbit, downlink_margin_gbit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_candidate_id,
                    next_sequence,
                    input_version_no,
                    simulated_at,
                    None if trigger is None else trigger.get("trigger_type"),
                    None if trigger is None else trigger.get("source_code"),
                    None if trigger is None else trigger.get("parameter_name"),
                    None if trigger is None else trigger.get("note"),
                    output["candidate_status"],
                    output["final_verdict"],
                    output["summary_message"],
                    output.get("dominant_risk_code"),
                    output["probabilities"]["p_geo"],
                    output["probabilities"]["p_env"],
                    output["probabilities"]["p_resource"],
                    output["probabilities"]["p_downlink"],
                    output["probabilities"]["p_conflict_adjusted"],
                    output["probabilities"]["p_total_candidate"],
                    1 if output["checks"]["resource_feasible_flag"] else 0,
                    1 if output["checks"]["downlink_feasible_flag"] else 0,
                    output["checks"]["storage_headroom_gbit"],
                    output["checks"]["backlog_after_capture_gbit"],
                    output["checks"]["downlink_margin_gbit"],
                ),
            )
            request_candidate_run_id = int(cursor.lastrowid)

            for reason in output["reasons"]:
                conn.execute(
                    """
                    INSERT INTO request_candidate_run_reason (
                        request_candidate_run_id, reason_code, reason_stage, reason_severity, reason_message
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        request_candidate_run_id,
                        reason["reason_code"],
                        reason["reason_stage"],
                        reason["reason_severity"],
                        reason["reason_message"],
                    ),
                )

            for recommendation in output["recommendations"]:
                conn.execute(
                    """
                    INSERT INTO request_candidate_run_recommendation (
                        request_candidate_run_id, parameter_name, current_value, recommended_value, expected_effect_message
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        request_candidate_run_id,
                        recommendation["parameter_name"],
                        recommendation["current_value"],
                        recommendation["recommended_value"],
                        recommendation["expected_effect_message"],
                    ),
                )

            conn.commit()

        return self.get_request_candidate_report(internal_request_code, candidate_code)

    def get_latest_run(self, request_key: str) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return None
        sql = """
        SELECT
            r.*
        FROM feasibility_run r
        JOIN feasibility_request fr ON fr.request_id = r.request_id
        WHERE fr.request_code = ?
        ORDER BY r.started_at DESC
        LIMIT 1
        """
        return self._fetch_one(sql, (internal_request_code,))

    def get_run_input_bundle(self, run_id: int) -> dict[str, Any] | None:
        sql = """
        SELECT
            rib.run_input_bundle_id,
            rib.policy_version,
            rib.created_at,
            os.orbit_snapshot_id,
            os.source_system AS orbit_source_system,
            os.source_version AS orbit_source_version,
            os.generated_at AS orbit_generated_at,
            ws.weather_snapshot_id,
            ws.provider_code AS weather_provider_code,
            ws.forecast_base_at,
            scs.solar_condition_snapshot_id,
            scs.algorithm_version AS solar_algorithm_version,
            trs.terrain_risk_snapshot_id,
            trs.dem_source,
            srs.resource_snapshot_id,
            srs.snapshot_at AS resource_snapshot_at,
            srs.recorder_free_gbit,
            srs.recorder_backlog_gbit,
            srs.power_margin_pct,
            srs.battery_soc_pct,
            srs.thermal_margin_pct
        FROM run_input_bundle rib
        JOIN orbit_snapshot os ON os.orbit_snapshot_id = rib.orbit_snapshot_id
        LEFT JOIN weather_snapshot ws ON ws.weather_snapshot_id = rib.weather_snapshot_id
        LEFT JOIN solar_condition_snapshot scs ON scs.solar_condition_snapshot_id = rib.solar_condition_snapshot_id
        LEFT JOIN terrain_risk_snapshot trs ON trs.terrain_risk_snapshot_id = rib.terrain_risk_snapshot_id
        JOIN spacecraft_resource_snapshot srs ON srs.resource_snapshot_id = rib.resource_snapshot_id
        WHERE rib.run_id = ?
        """
        return self._fetch_one(sql, (run_id,))

    def list_run_contact_windows(self, run_id: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            scw.contact_window_id,
            gs.station_code,
            gs.station_name,
            sat.satellite_code,
            scw.contact_start_at,
            scw.contact_end_at,
            scw.downlink_rate_mbps,
            scw.link_efficiency_pct,
            scw.availability_status
        FROM run_input_bundle rib
        JOIN run_input_contact_window ricw ON ricw.run_input_bundle_id = rib.run_input_bundle_id
        JOIN station_contact_window scw ON scw.contact_window_id = ricw.contact_window_id
        JOIN ground_station gs ON gs.ground_station_id = scw.ground_station_id
        JOIN satellite sat ON sat.satellite_id = scw.satellite_id
        WHERE rib.run_id = ?
        ORDER BY scw.contact_start_at
        """
        return self._fetch_all(sql, (run_id,))

    def list_run_existing_tasks(self, run_id: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            et.*
        FROM run_input_bundle rib
        JOIN run_input_existing_task riet ON riet.run_input_bundle_id = rib.run_input_bundle_id
        JOIN existing_task et ON et.existing_task_id = riet.existing_task_id
        WHERE rib.run_id = ?
        ORDER BY et.task_start_at
        """
        return self._fetch_all(sql, (run_id,))

    def list_run_downlink_bookings(self, run_id: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            edb.*,
            gs.station_code
        FROM run_input_bundle rib
        JOIN run_input_downlink_booking ridb ON ridb.run_input_bundle_id = rib.run_input_bundle_id
        JOIN existing_downlink_booking edb ON edb.existing_downlink_booking_id = ridb.existing_downlink_booking_id
        JOIN ground_station gs ON gs.ground_station_id = edb.ground_station_id
        WHERE rib.run_id = ?
        ORDER BY edb.booking_start_at
        """
        return self._fetch_all(sql, (run_id,))

    def list_candidates(self, run_id: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            rc.run_candidate_id,
            rc.candidate_rank,
            rc.candidate_status,
            rc.planned_capture_start_at,
            rc.planned_capture_end_at,
            rc.expected_data_volume_gbit,
            ao.required_off_nadir_deg,
            ao.predicted_incidence_deg,
            ao.coverage_ratio_predicted,
            sp.pass_start_at,
            sp.pass_end_at,
            sat.satellite_code,
            se.sensor_type,
            sm.mode_code,
            gs.station_code AS selected_ground_station_code,
            scw.contact_start_at AS selected_contact_start_at,
            scw.contact_end_at AS selected_contact_end_at
        FROM run_candidate rc
        JOIN access_opportunity ao ON ao.access_opportunity_id = rc.access_opportunity_id
        JOIN satellite_pass sp ON sp.satellite_pass_id = ao.satellite_pass_id
        JOIN satellite sat ON sat.satellite_id = sp.satellite_id
        JOIN sensor se ON se.sensor_id = ao.sensor_id
        JOIN sensor_mode sm ON sm.sensor_mode_id = ao.sensor_mode_id
        LEFT JOIN ground_station gs ON gs.ground_station_id = rc.selected_ground_station_id
        LEFT JOIN station_contact_window scw ON scw.contact_window_id = rc.selected_contact_window_id
        WHERE rc.run_id = ?
        ORDER BY rc.candidate_rank
        """
        return self._fetch_all(sql, (run_id,))

    def list_candidate_rejection_reasons(self, run_id: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            rc.run_candidate_id,
            crr.reason_code,
            crr.reason_stage,
            crr.reason_severity,
            crr.reason_message
        FROM run_candidate rc
        JOIN candidate_rejection_reason crr ON crr.run_candidate_id = rc.run_candidate_id
        WHERE rc.run_id = ?
        ORDER BY rc.candidate_rank, crr.rejection_reason_id
        """
        return self._fetch_all(sql, (run_id,))

    def list_candidate_checks(self, run_id: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            rc.run_candidate_id,
            crc.required_volume_gbit,
            crc.available_volume_gbit,
            crc.power_margin_pct,
            crc.thermal_margin_pct,
            crc.resource_feasible_flag,
            cdc.required_downlink_gbit,
            cdc.available_downlink_gbit,
            cdc.backlog_after_capture_gbit,
            cdc.downlink_feasible_flag
        FROM run_candidate rc
        JOIN candidate_resource_check crc ON crc.run_candidate_id = rc.run_candidate_id
        JOIN candidate_downlink_check cdc ON cdc.run_candidate_id = rc.run_candidate_id
        WHERE rc.run_id = ?
        ORDER BY rc.candidate_rank
        """
        return self._fetch_all(sql, (run_id,))

    def list_candidate_probabilities(self, run_id: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            rc.run_candidate_id,
            cp.p_geo,
            cp.p_env,
            cp.p_resource,
            cp.p_downlink,
            cp.p_conflict_adjusted,
            cp.p_total_candidate,
            cp.probability_model_version
        FROM run_candidate rc
        JOIN candidate_probability cp ON cp.run_candidate_id = rc.run_candidate_id
        WHERE rc.run_id = ?
        ORDER BY rc.candidate_rank
        """
        return self._fetch_all(sql, (run_id,))

    def get_result(self, run_id: int) -> dict[str, Any] | None:
        sql = """
        SELECT
            *
        FROM feasibility_result
        WHERE run_id = ?
        """
        return self._fetch_one(sql, (run_id,))

    def list_recommendations(self, run_id: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            *
        FROM feasibility_recommendation
        WHERE run_id = ?
        ORDER BY recommendation_rank
        """
        return self._fetch_all(sql, (run_id,))

    def list_audit_events(self, run_id: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            *
        FROM audit_event
        WHERE run_id = ?
        ORDER BY event_at
        """
        return self._fetch_all(sql, (run_id,))

    def get_request_report(self, request_key: str) -> dict[str, Any] | None:
        internal_request_code = self._resolve_internal_request_code(request_key)
        if internal_request_code is None:
            return None
        request_row = self.get_request(internal_request_code)
        if request_row is None:
            return None

        request_candidates = self.list_request_candidates(internal_request_code)
        dynamic = self._build_dynamic_request_result(internal_request_code, request_candidates)

        return {
            "request": request_row,
            "external_refs": self.list_request_external_refs(internal_request_code),
            "aoi": self.get_request_aoi(internal_request_code),
            "constraint": self.get_request_constraint(internal_request_code),
            "sensor_options": self.list_request_sensor_options(internal_request_code),
            "product_options": self.list_request_product_options(internal_request_code),
            "request_candidates": request_candidates,
            "run": dynamic["run"],
            "proposal": dynamic["proposal"],
            "input_bundle": None,
            "contact_windows": [],
            "existing_tasks": [],
            "downlink_bookings": [],
            "candidates": dynamic["candidates"],
            "candidate_checks": dynamic["candidate_checks"],
            "candidate_rejection_reasons": dynamic["candidate_rejection_reasons"],
            "candidate_probabilities": dynamic["candidate_probabilities"],
            "result": dynamic["result"],
            "recommendations": dynamic["recommendations"],
            "audit_events": [],
        }

    @staticmethod
    def _build_simulation_input(candidate_input: dict[str, Any]) -> SimulationInput:
        return SimulationInput(**{field: candidate_input[field] for field in SimulationInput.model_fields})

    def _simulate_candidate_input(self, candidate_input: dict[str, Any]) -> dict[str, Any]:
        return simulate_feasibility(self._build_simulation_input(candidate_input)).model_dump()

    @staticmethod
    def _apply_recommendation_to_input(
        candidate_input: dict[str, Any],
        parameter_name: str,
        recommended_value: str,
    ) -> dict[str, Any] | None:
        updated = dict(candidate_input)
        try:
            if parameter_name in {
                "max_off_nadir_deg",
                "max_cloud_pct",
                "recorder_backlog_gbit",
                "available_downlink_gbit",
                "area_km2",
            }:
                updated[parameter_name] = float(recommended_value)
            elif parameter_name == "priority_tier":
                updated[parameter_name] = recommended_value
            elif parameter_name == "polarization_code":
                updated[parameter_name] = recommended_value
            elif parameter_name == "incidence_window":
                min_value, max_value = [part.strip() for part in recommended_value.split("-", 1)]
                updated["min_incidence_deg"] = float(min_value)
                updated["max_incidence_deg"] = float(max_value)
            else:
                return None
        except (ValueError, TypeError):
            return None
        return updated

    def _estimate_recommendation_probability_gain(
        self,
        recommendation: dict[str, Any],
        base_adjusted_input: dict[str, Any],
        base_output: dict[str, Any],
        request_row: dict[str, Any],
        request_aoi: dict[str, Any] | None,
        request_constraint: dict[str, Any] | None,
        request_sensor_options: list[dict[str, Any]],
        request_product_options: list[dict[str, Any]],
        access: dict[str, Any] | None,
        contact: dict[str, Any] | None,
        task_conflicts: list[dict[str, Any]],
        booking_conflicts: list[dict[str, Any]],
        priority_tier: str,
    ) -> float | None:
        modified_input = self._apply_recommendation_to_input(
            dict(base_adjusted_input),
            str(recommendation["parameter_name"]),
            str(recommendation["recommended_value"]),
        )
        if modified_input is None:
            return None

        after = self._simulate_request_candidate_input_with_context(
            request_row,
            request_aoi,
            request_constraint,
            request_sensor_options,
            request_product_options,
            modified_input,
            access,
            contact,
            task_conflicts,
            booking_conflicts,
            priority_tier,
        )

        gain = float(after["probabilities"]["p_total_candidate"]) - float(base_output["probabilities"]["p_total_candidate"])
        return round(max(gain, 0.0), 4)

    def _enrich_output_recommendation_gains(
        self,
        request_row: dict[str, Any],
        request_aoi: dict[str, Any] | None,
        request_constraint: dict[str, Any] | None,
        request_sensor_options: list[dict[str, Any]],
        request_product_options: list[dict[str, Any]],
        candidate_code: str | None,
        adjusted_input: dict[str, Any],
        access: dict[str, Any] | None,
        contact: dict[str, Any] | None,
        task_conflicts: list[dict[str, Any]],
        booking_conflicts: list[dict[str, Any]],
        priority_tier: str,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        if not candidate_code:
            return output
        for recommendation in output["recommendations"]:
            gain = self._estimate_recommendation_probability_gain(
                {
                    "recommendation_type": candidate_code,
                    "parameter_name": recommendation["parameter_name"],
                    "recommended_value": recommendation["recommended_value"],
                },
                adjusted_input,
                output,
                request_row,
                request_aoi,
                request_constraint,
                request_sensor_options,
                request_product_options,
                access,
                contact,
                task_conflicts,
                booking_conflicts,
                priority_tier,
            )
            recommendation["expected_probability_gain"] = gain
        return output

    def _simulate_request_candidate_input_with_context(
        self,
        request_row: dict[str, Any],
        request_aoi: dict[str, Any] | None,
        request_constraint: dict[str, Any] | None,
        request_sensor_options: list[dict[str, Any]],
        request_product_options: list[dict[str, Any]],
        adjusted_input: dict[str, Any],
        access: dict[str, Any] | None,
        contact: dict[str, Any] | None,
        task_conflicts: list[dict[str, Any]],
        booking_conflicts: list[dict[str, Any]],
        priority_tier: str,
    ) -> dict[str, Any]:
        output = self._simulate_candidate_input(adjusted_input)
        output["checks"]["requested_start_at"] = request_row.get("requested_start_at")
        output["checks"]["requested_end_at"] = request_row.get("requested_end_at")
        opportunity_start = adjusted_input.get("opportunity_start_at")
        opportunity_end = adjusted_input.get("opportunity_end_at")
        if bool(opportunity_start) ^ bool(opportunity_end):
            output["checks"]["geometry_source"] = "CANDIDATE_OPPORTUNITY_INCOMPLETE"
            output["reasons"].append(
                {
                    "reason_code": "CANDIDATE_OPPORTUNITY_INCOMPLETE",
                    "reason_stage": "GEOMETRY",
                    "reason_severity": "HARD",
                    "reason_message": "촬영기회 시작시각과 종료시각은 둘 다 함께 입력되어야 합니다.",
                }
            )
            return self._recompute_output_status(output)
        if opportunity_start and opportunity_end:
            try:
                opportunity_start_dt = self._parse_utc(str(opportunity_start))
                opportunity_end_dt = self._parse_utc(str(opportunity_end))
                requested_start_dt = self._parse_utc(str(request_row["requested_start_at"]))
                requested_end_dt = self._parse_utc(str(request_row["requested_end_at"]))
            except ValueError:
                output["checks"]["geometry_source"] = "CANDIDATE_OPPORTUNITY_FORMAT_INVALID"
                output["reasons"].append(
                    {
                        "reason_code": "CANDIDATE_OPPORTUNITY_FORMAT_INVALID",
                        "reason_stage": "GEOMETRY",
                        "reason_severity": "HARD",
                        "reason_message": "촬영기회 시작/종료시각은 UTC ISO 형식(예: 2026-03-10T18:06:10Z)이어야 합니다.",
                    }
                )
                return self._recompute_output_status(output)
            if opportunity_end_dt <= opportunity_start_dt:
                output["checks"]["geometry_source"] = "CANDIDATE_OPPORTUNITY_INVALID"
                output["reasons"].append(
                    {
                        "reason_code": "CANDIDATE_OPPORTUNITY_INVALID",
                        "reason_stage": "GEOMETRY",
                        "reason_severity": "HARD",
                        "reason_message": "촬영기회 종료시각은 시작시각보다 뒤여야 합니다.",
                    }
                )
                return self._recompute_output_status(output)
            if opportunity_start_dt < requested_start_dt or opportunity_end_dt > requested_end_dt:
                output["checks"]["geometry_source"] = "CANDIDATE_OPPORTUNITY_OUTSIDE_REQUEST_WINDOW"
                output["reasons"].append(
                    {
                        "reason_code": "CANDIDATE_OPPORTUNITY_OUTSIDE_REQUEST_WINDOW",
                        "reason_stage": "GEOMETRY",
                        "reason_severity": "HARD",
                        "reason_message": "입력한 촬영기회 시각이 고객 요청 시작/종료 시각 범위를 벗어났습니다.",
                    }
                )
                return self._recompute_output_status(output)
        if access is not None:
            output = self._apply_access_opportunity_validation(access, output)
        else:
            output["checks"]["geometry_source"] = "REQUEST_WINDOW_ONLY"
            output["reasons"].append(
                {
                    "reason_code": "ACCESS_OPPORTUNITY_NOT_MAPPED",
                    "reason_stage": "GEOMETRY",
                    "reason_severity": "SOFT",
                    "reason_message": "요청 시간창은 있으나 이 후보에 대해 구체적인 촬영기회(access opportunity)가 아직 계산 또는 매핑되지 않았습니다.",
                }
            )
            output["recommendations"].append(
                {
                    "parameter_name": "access_opportunity_mapping",
                    "current_value": f"{request_row.get('requested_start_at')} ~ {request_row.get('requested_end_at')}",
                    "recommended_value": "요청 시간창 안에서 유효한 pass/access 계산 또는 선택",
                    "expected_effect_message": "고객 요청 시간창 안에서 실제 촬영기회를 계산하거나 선택해야 기하 접근과 첫 시도 시각을 더 정확히 판정할 수 있습니다.",
                }
            )
        output = self._apply_environment_snapshot_validation(request_aoi, request_constraint, adjusted_input, access, output)
        skip_operational_validation = (
            access is not None
            and str(access.get("geometry_source") or "") == "CANDIDATE_OPPORTUNITY_INPUT"
            and access.get("satellite_id") is None
        )
        if skip_operational_validation:
            output["checks"]["operational_source"] = "CANDIDATE_OPPORTUNITY_INPUT"
            output["reasons"].append(
                {
                    "reason_code": "CONTACT_WINDOW_NOT_MAPPED",
                    "reason_stage": "DOWNLINK",
                    "reason_severity": "SOFT",
                    "reason_message": "촬영기회 시각은 직접 입력됐지만, 이에 연결된 지상국 contact window는 아직 계산 또는 매핑되지 않았습니다.",
                }
            )
            output["recommendations"].append(
                {
                    "parameter_name": "contact_window_mapping",
                    "current_value": f"{opportunity_start} ~ {opportunity_end}",
                    "recommended_value": "입력 촬영기회에 대응하는 지상국 contact window 계산 또는 선택",
                    "expected_effect_message": "촬영기회 시각이 정해졌다면 이후 downlink 가능성은 해당 시각 뒤의 contact window 기준으로 다시 검토해야 합니다.",
                }
            )
        else:
            output = self._apply_operational_validation(priority_tier, contact, task_conflicts, booking_conflicts, output)
        return self._apply_request_policy_validation(
            request_row,
            request_aoi,
            request_sensor_options,
            request_product_options,
            adjusted_input,
            output,
        )

    def _prepare_request_candidate_context(
        self,
        request_code: str,
        candidate_code: str | None,
        candidate_input: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
        adjusted_input, access = self._prepare_candidate_geometry_input(request_code, candidate_code, candidate_input)
        adjusted_input, contact, task_conflicts, booking_conflicts = self._prepare_candidate_operational_input(adjusted_input, access)
        return adjusted_input, access, contact, task_conflicts, booking_conflicts

    def simulate_request_candidate_input(
        self,
        request_code: str,
        candidate_input: dict[str, Any],
        candidate_code: str | None = None,
        include_recommendation_gains: bool = True,
    ) -> dict[str, Any] | None:
        request_row = self.get_request(request_code)
        if request_row is None:
            return None
        request_aoi = self.get_request_aoi(request_code)
        request_constraint = self.get_request_constraint(request_code)
        request_sensor_options = self.list_request_sensor_options(request_code)
        request_product_options = self.list_request_product_options(request_code)

        adjusted_input, access, contact, task_conflicts, booking_conflicts = self._prepare_request_candidate_context(
            request_code,
            candidate_code,
            candidate_input,
        )
        output = self._simulate_request_candidate_input_with_context(
            request_row,
            request_aoi,
            request_constraint,
            request_sensor_options,
            request_product_options,
            adjusted_input,
            access,
            contact,
            task_conflicts,
            booking_conflicts,
            str(candidate_input["priority_tier"]),
        )
        if not include_recommendation_gains:
            return output
        return self._enrich_output_recommendation_gains(
            request_row,
            request_aoi,
            request_constraint,
            request_sensor_options,
            request_product_options,
            candidate_code,
            adjusted_input,
            access,
            contact,
            task_conflicts,
            booking_conflicts,
            str(candidate_input["priority_tier"]),
            output,
        )

    def _build_dynamic_request_result(
        self,
        request_code: str,
        request_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        request_row = self.get_request(request_code)
        candidate_rows: list[dict[str, Any]] = []
        candidate_checks: list[dict[str, Any]] = []
        candidate_reasons: list[dict[str, Any]] = []
        candidate_probabilities: list[dict[str, Any]] = []
        recommendations: list[dict[str, Any]] = []
        evaluated: list[dict[str, Any]] = []
        candidate_inputs_by_code: dict[str, dict[str, Any]] = {}
        evaluated_by_code: dict[str, dict[str, Any]] = {}
        candidate_contexts: dict[str, dict[str, Any]] = {}
        request_aoi = self.get_request_aoi(request_code)
        request_constraint = self.get_request_constraint(request_code)
        request_sensor_options = self.list_request_sensor_options(request_code)
        request_product_options = self.list_request_product_options(request_code)
        baseline_candidate = self._select_baseline_candidate(request_candidates)
        baseline_candidate_code = str(baseline_candidate["candidate_code"]) if baseline_candidate is not None else None
        for candidate in request_candidates:
            candidate_code = str(candidate["candidate_code"])
            candidate_input = self.get_request_candidate_input(request_code, candidate_code)
            if candidate_input is None:
                continue
            candidate_inputs_by_code[candidate_code] = dict(candidate_input)
            adjusted_input, access, contact, task_conflicts, booking_conflicts = self._prepare_request_candidate_context(
                request_code,
                candidate_code,
                candidate_input,
            )
            output = self._simulate_request_candidate_input_with_context(
                request_row,
                request_aoi,
                request_constraint,
                request_sensor_options,
                request_product_options,
                adjusted_input,
                access,
                contact,
                task_conflicts,
                booking_conflicts,
                str(candidate_input["priority_tier"]),
            )
            output = self._enrich_output_recommendation_gains(
                request_row,
                request_aoi,
                request_constraint,
                request_sensor_options,
                request_product_options,
                candidate_code,
                adjusted_input,
                access,
                contact,
                task_conflicts,
                booking_conflicts,
                str(candidate_input["priority_tier"]),
                output,
            )
            request_candidate_id = int(candidate["request_candidate_id"])
            probabilities = output["probabilities"]
            checks = output["checks"]
            candidate_contexts[candidate_code] = {
                "adjusted_input": dict(adjusted_input),
                "access": access,
                "contact": contact,
                "task_conflicts": list(task_conflicts),
                "booking_conflicts": list(booking_conflicts),
                "priority_tier": str(candidate_input["priority_tier"]),
            }

            candidate_rows.append(
                {
                    "run_candidate_id": request_candidate_id,
                    "candidate_code": candidate_code,
                    "candidate_title": candidate["candidate_title"],
                    "candidate_rank": candidate["candidate_rank"],
                    "candidate_status": output["candidate_status"],
                    "window_hours": candidate_input["window_hours"],
                    "opportunity_start_at": candidate_input.get("opportunity_start_at") or checks.get("access_start_at"),
                    "opportunity_end_at": candidate_input.get("opportunity_end_at") or checks.get("access_end_at"),
                    "requested_start_at": request_row.get("requested_start_at") if request_row is not None else None,
                    "requested_end_at": request_row.get("requested_end_at") if request_row is not None else None,
                    "pass_start_at": checks.get("pass_start_at"),
                    "pass_end_at": checks.get("pass_end_at"),
                    "access_start_at": checks.get("access_start_at"),
                    "access_end_at": checks.get("access_end_at"),
                    "geometric_feasible_flag": checks.get("geometric_feasible_flag"),
                    "geometry_source": checks.get("geometry_source", "INPUT_ONLY"),
                    "access_opportunity_id": checks.get("access_opportunity_id"),
                    "required_off_nadir_deg": access["required_off_nadir_deg"] if access is not None else candidate_input.get("required_off_nadir_deg"),
                    "predicted_incidence_deg": access["predicted_incidence_deg"] if access is not None else candidate_input.get("predicted_incidence_deg"),
                    "coverage_ratio_predicted": access["coverage_ratio_predicted"] if access is not None else candidate_input.get("coverage_ratio_predicted"),
                    "expected_data_volume_gbit": candidate_input["expected_data_volume_gbit"],
                    "p_total_candidate": probabilities["p_total_candidate"],
                }
            )

            candidate_checks.append(
                {
                    "run_candidate_id": request_candidate_id,
                    "candidate_code": candidate_code,
                    "candidate_title": candidate["candidate_title"],
                    "required_volume_gbit": candidate_input["expected_data_volume_gbit"],
                    "available_volume_gbit": candidate_input["recorder_free_gbit"],
                    "power_margin_pct": checks["power_margin_pct"],
                    "thermal_margin_pct": checks["thermal_margin_pct"],
                    "policy_feasible_flag": checks.get("policy_feasible_flag"),
                    "policy_alert_count": checks.get("policy_alert_count"),
                    "policy_summary": checks.get("policy_summary"),
                    "resource_feasible_flag": checks["resource_feasible_flag"],
                    "required_downlink_gbit": checks["backlog_after_capture_gbit"],
                    "available_downlink_gbit": checks.get("net_contact_capacity_gbit", candidate_input["available_downlink_gbit"]),
                    "backlog_after_capture_gbit": checks["backlog_after_capture_gbit"],
                    "downlink_feasible_flag": checks["downlink_feasible_flag"],
                    "selected_ground_station_code": checks.get("selected_ground_station_code"),
                    "selected_contact_window_id": checks.get("selected_contact_window_id"),
                    "contact_start_at": checks.get("contact_start_at"),
                    "contact_end_at": checks.get("contact_end_at"),
                    "contact_capacity_gbit": checks.get("contact_capacity_gbit"),
                    "booking_reserved_gbit": checks.get("booking_reserved_gbit"),
                    "net_contact_capacity_gbit": checks.get("net_contact_capacity_gbit"),
                    "task_conflict_count": checks.get("task_conflict_count"),
                    "booking_conflict_count": checks.get("booking_conflict_count"),
                    "forecast_cloud_pct": checks.get("forecast_cloud_pct"),
                    "forecast_haze_index": checks.get("forecast_haze_index"),
                    "forecast_confidence_score": checks.get("forecast_confidence_score"),
                    "forecast_sun_elevation_deg": checks.get("forecast_sun_elevation_deg"),
                    "forecast_sun_azimuth_deg": checks.get("forecast_sun_azimuth_deg"),
                    "shadow_risk_score": checks.get("shadow_risk_score"),
                    "local_capture_time_hhmm": checks.get("local_capture_time_hhmm"),
                    "local_noon_distance_min": checks.get("local_noon_distance_min"),
                    "dominant_axis_deg": checks.get("dominant_axis_deg"),
                    "preferred_local_time_start": checks.get("preferred_local_time_start"),
                    "preferred_local_time_end": checks.get("preferred_local_time_end"),
                    "local_time_window_distance_min": checks.get("local_time_window_distance_min"),
                    "daylight_flag": checks.get("daylight_flag"),
                    "terrain_risk_type": checks.get("terrain_risk_type"),
                    "terrain_risk_score": checks.get("terrain_risk_score"),
                }
            )

            candidate_probabilities.append(
                {
                    "run_candidate_id": request_candidate_id,
                    "candidate_code": candidate_code,
                    "candidate_title": candidate["candidate_title"],
                    "p_geo": probabilities["p_geo"],
                    "p_env": probabilities["p_env"],
                    "p_resource": probabilities["p_resource"],
                    "p_downlink": probabilities["p_downlink"],
                    "p_policy": probabilities.get("p_policy"),
                    "p_conflict_adjusted": probabilities["p_conflict_adjusted"],
                    "p_total_candidate": probabilities["p_total_candidate"],
                    "probability_model_version": "simulate_feasibility.v1",
                }
            )

            for reason in output["reasons"]:
                candidate_reasons.append(
                    {
                        "run_candidate_id": request_candidate_id,
                        "candidate_code": candidate_code,
                        "candidate_title": candidate["candidate_title"],
                        "reason_code": reason["reason_code"],
                        "reason_stage": reason["reason_stage"],
                        "reason_severity": reason["reason_severity"],
                        "reason_message": reason["reason_message"],
                    }
                )

            for recommendation_rank, recommendation in enumerate(output["recommendations"], start=1):
                recommendations.append(
                    {
                        "recommendation_rank": recommendation_rank,
                        "recommendation_type": candidate_code,
                        "parameter_name": recommendation["parameter_name"],
                        "current_value": recommendation["current_value"],
                        "recommended_value": recommendation["recommended_value"],
                        "expected_effect_message": recommendation["expected_effect_message"],
                        "expected_probability_gain": None,
                    }
                )

            evaluated_item = {
                "request_candidate_id": request_candidate_id,
                "candidate_code": candidate_code,
                "candidate_title": candidate["candidate_title"],
                "candidate_rank": candidate["candidate_rank"],
                "is_baseline": bool(candidate.get("is_baseline")),
                "final_verdict": output["final_verdict"],
                "candidate_status": output["candidate_status"],
                "summary_message": output["summary_message"],
                "dominant_risk_code": output.get("dominant_risk_code"),
                "overall_probability": probabilities["p_total_candidate"],
                "attempt_at": checks.get("access_start_at") or checks.get("pass_start_at"),
                "sensor_type": candidate_input["sensor_type"],
                "predicted_incidence_deg": access["predicted_incidence_deg"] if access is not None else candidate_input.get("predicted_incidence_deg"),
            }
            evaluated.append(evaluated_item)
            evaluated_by_code[candidate_code] = dict(evaluated_item)

        candidate_rows.sort(
            key=lambda item: (
                item["access_start_at"] or item["pass_start_at"] or "9999-12-31T23:59:59Z",
                int(item["candidate_rank"]),
            )
        )
        candidate_checks.sort(
            key=lambda item: next(
                (
                    row["candidate_rank"]
                    for row in candidate_rows
                    if int(row["run_candidate_id"]) == int(item["run_candidate_id"])
                ),
                999999,
            )
        )
        candidate_probabilities.sort(
            key=lambda item: next(
                (
                    row["candidate_rank"]
                    for row in candidate_rows
                    if int(row["run_candidate_id"]) == int(item["run_candidate_id"])
                ),
                999999,
            )
        )
        candidate_reasons.sort(
            key=lambda item: next(
                (
                    row["candidate_rank"]
                    for row in candidate_rows
                    if int(row["run_candidate_id"]) == int(item["run_candidate_id"])
                ),
                999999,
            )
        )
        evaluated.sort(
            key=lambda item: (
                item["attempt_at"] or "9999-12-31T23:59:59Z",
                int(item["candidate_rank"]),
            )
        )

        result = self._build_request_result_summary(request_row, evaluated, baseline_candidate_code)

        if result.get("dominant_risk_code") == "REPEAT_PASS_INCIDENCE_INCONSISTENT":
            baseline_incidence = result.get("repeat_baseline_incidence_deg")
            tolerance = result.get("repeat_incidence_tolerance_deg")
            filtered_candidates = result.get("repeat_incidence_filtered_candidates") or []
            for item in filtered_candidates[:2]:
                if baseline_incidence is None or tolerance is None:
                    continue
                min_incidence = max(0.0, float(baseline_incidence) - float(tolerance))
                max_incidence = float(baseline_incidence) + float(tolerance)
                candidate_code = str(item.get("candidate_code") or "")
                recommendations.append(
                    {
                        "recommendation_rank": 999,
                        "recommendation_type": candidate_code,
                        "parameter_name": "incidence_window",
                        "current_value": str(item.get("predicted_incidence_deg")),
                        "recommended_value": f"{min_incidence:.1f}-{max_incidence:.1f}",
                        "expected_effect_message": "반복 촬영 후보를 기준 입사각 그룹에 맞추면 동일 기하 조건으로 repeat-pass 묶음을 구성하기 쉬워집니다.",
                        "expected_probability_gain": None,
                    }
                )
                recommendations.append(
                    {
                        "recommendation_rank": 1000,
                        "recommendation_type": candidate_code,
                        "parameter_name": "candidate_split",
                        "current_value": str(item.get("predicted_incidence_deg")),
                        "recommended_value": "동일 입사각 그룹으로 후보 분리",
                        "expected_effect_message": "입사각 편차가 큰 후보는 별도 시나리오로 분리해 repeat-pass 묶음과 일반 단일 촬영 후보를 나누어 관리하는 편이 적절합니다.",
                        "expected_probability_gain": None,
                    }
                )

        def recommendation_sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
            dominant_priority = 1
            if result.get("dominant_risk_code") == "REPEAT_PASS_INCIDENCE_INCONSISTENT" and str(item.get("parameter_name")) in {"incidence_window", "candidate_split"}:
                dominant_priority = 0
            baseline_priority = 0 if item.get("recommendation_type") == baseline_candidate_code else 1
            candidate_rank = next(
                (
                    int(row["candidate_rank"])
                    for row in candidate_rows
                    if row["candidate_code"] == item["recommendation_type"]
                ),
                999999,
            )
            return (
                dominant_priority,
                baseline_priority,
                candidate_rank,
                int(item.get("recommendation_rank", 999999)),
            )

        recommendations.sort(key=recommendation_sort_key)

        for recommendation in recommendations:
            recommendation["expected_probability_gain"] = self._estimate_request_recommendation_probability_gain(
                request_row,
                recommendation,
                evaluated_by_code,
                candidate_contexts,
                request_aoi,
                request_constraint,
                request_sensor_options,
                request_product_options,
                result["overall_probability"],
            )

        proposal_option_limit = 4 if result.get("dominant_risk_code") == "REPEAT_PASS_INCIDENCE_INCONSISTENT" else 3

        proposal = {
            "service_policy_name": request_row["policy_name"] if request_row is not None else None,
            "request_priority_tier": request_row["priority_tier"] if request_row is not None else None,
            "cumulative_probability": result["overall_probability"],
            "first_feasible_attempt_at": result.get("first_feasible_attempt_at"),
            "expected_attempt_count": result.get("expected_attempt_count"),
            "max_attempts_considered": result.get("max_attempts_considered"),
            "attempt_count_considered": result.get("attempt_count_considered"),
            "required_attempt_count": result.get("required_attempt_count"),
            "repeat_requirement_met": result.get("repeat_requirement_met"),
            "repeat_quality_threshold": result.get("repeat_quality_threshold"),
            "repeat_quality_attempt_count": result.get("repeat_quality_attempt_count"),
            "repeat_spacing_hours_required": result.get("repeat_spacing_hours_required"),
            "repeat_incidence_tolerance_deg": result.get("repeat_incidence_tolerance_deg"),
            "repeat_incidence_consistent_count": result.get("repeat_incidence_consistent_count"),
            "repeat_incidence_met": result.get("repeat_incidence_met"),
            "repeat_spaced_attempt_count": result.get("repeat_spaced_attempt_count"),
            "repeat_spacing_met": result.get("repeat_spacing_met"),
            "best_candidate_code": result.get("best_candidate_code"),
            "best_candidate_title": result.get("best_candidate_title"),
            "baseline_candidate_code": result.get("baseline_candidate_code"),
            "baseline_candidate_title": result.get("baseline_candidate_title"),
            "sla_summary": (
                f"{request_row['policy_name']} 정책, 요청 우선순위 {request_row['priority_tier']}, "
                f"정책상 집계 상한 {result.get('max_attempts_considered') or 0}건 기준"
            )
            if request_row is not None
            else None,
            "relaxation_options": recommendations[:proposal_option_limit],
        }

        return {
            "run": {
                "run_status": "DERIVED_FROM_REQUEST_CANDIDATES",
                "algorithm_version": "simulate_feasibility.v1",
                "trigger_type": "CURRENT_INPUT_EVALUATION",
            },
            "proposal": proposal,
            "candidates": candidate_rows,
            "candidate_checks": candidate_checks,
            "candidate_rejection_reasons": candidate_reasons,
            "candidate_probabilities": candidate_probabilities,
            "result": result,
            "recommendations": recommendations,
        }

    def _build_request_result_summary(
        self,
        request_row: dict[str, Any] | None,
        evaluated: list[dict[str, Any]],
        baseline_candidate_code: str | None = None,
    ) -> dict[str, Any]:
        best = self._select_best_candidate(evaluated)
        baseline = self._select_baseline_candidate(evaluated, baseline_candidate_code)
        feasible_count = sum(1 for item in evaluated if item["final_verdict"] == "FEASIBLE")
        conditional_count = sum(1 for item in evaluated if item["final_verdict"] == "CONDITIONALLY_FEASIBLE")
        rejected_count = sum(1 for item in evaluated if item["final_verdict"] == "NOT_FEASIBLE")
        max_attempts = int(request_row["max_attempts"]) if request_row is not None and request_row["max_attempts"] is not None else len(evaluated)
        considered_attempts = evaluated[: max(max_attempts, 0)]
        survival_probability = 1.0
        expected_attempt_count = 0.0
        first_feasible_attempt_at: str | None = None

        for attempt in considered_attempts:
            p_i = max(0.0, min(1.0, float(attempt["overall_probability"])))
            if first_feasible_attempt_at is None and attempt["final_verdict"] != "NOT_FEASIBLE" and p_i > 0:
                first_feasible_attempt_at = attempt["attempt_at"]
            expected_attempt_count += survival_probability
            survival_probability *= 1.0 - p_i

        cumulative_probability = round(1.0 - survival_probability, 4) if considered_attempts else 0.0
        repeat_required = request_row is not None and int(request_row["repeat_acquisition_flag"]) == 1
        required_attempt_count = int(request_row["monitoring_count"]) if repeat_required else 1
        repeat_quality_threshold = None
        viable_attempts = [
            item for item in considered_attempts
            if item["final_verdict"] != "NOT_FEASIBLE" and float(item["overall_probability"]) > 0 and item.get("attempt_at")
        ]
        repeat_spacing_hours_required = None
        repeat_incidence_tolerance_deg = None
        repeat_quality_attempt_count = len(viable_attempts)
        repeat_incidence_consistent_count = len(viable_attempts)
        repeat_spaced_attempt_count = len(viable_attempts)
        repeat_baseline_incidence_deg = None
        repeat_incidence_filtered_candidates: list[dict[str, Any]] = []
        if repeat_required:
            sensor_types = {str(item.get("sensor_type") or "") for item in viable_attempts}
            repeat_quality_threshold = 0.20 if "SAR" in sensor_types else 0.25
            viable_attempts = [
                item for item in viable_attempts
                if float(item["overall_probability"]) >= repeat_quality_threshold
            ]
            repeat_quality_attempt_count = len(viable_attempts)
            if "SAR" in sensor_types:
                repeat_incidence_tolerance_deg = 5.0
                baseline_incidence = None
                if baseline is not None and baseline.get("predicted_incidence_deg") is not None:
                    baseline_incidence = float(baseline["predicted_incidence_deg"])
                    repeat_baseline_incidence_deg = baseline_incidence
                filtered_attempts: list[dict[str, Any]] = []
                for attempt in viable_attempts:
                    incidence_value = attempt.get("predicted_incidence_deg")
                    if incidence_value is None:
                        continue
                    incidence = float(incidence_value)
                    if baseline_incidence is None:
                        baseline_incidence = incidence
                        repeat_baseline_incidence_deg = incidence
                        filtered_attempts.append(attempt)
                        continue
                    if abs(incidence - baseline_incidence) <= repeat_incidence_tolerance_deg:
                        filtered_attempts.append(attempt)
                    else:
                        repeat_incidence_filtered_candidates.append(
                            {
                                "candidate_code": attempt.get("candidate_code"),
                                "candidate_title": attempt.get("candidate_title"),
                                "predicted_incidence_deg": incidence,
                            }
                        )
                viable_attempts = filtered_attempts
            repeat_incidence_consistent_count = len(viable_attempts)
            repeat_spacing_hours_required = 12 if "SAR" in sensor_types else 24
            spaced_attempts: list[dict[str, Any]] = []
            last_attempt_at: datetime | None = None
            for attempt in viable_attempts:
                current_attempt_at = self._parse_utc(str(attempt["attempt_at"]))
                if last_attempt_at is None or (current_attempt_at - last_attempt_at).total_seconds() >= repeat_spacing_hours_required * 3600:
                    spaced_attempts.append(attempt)
                    last_attempt_at = current_attempt_at
            repeat_spaced_attempt_count = len(spaced_attempts)
        repeat_requirement_met = repeat_spaced_attempt_count >= required_attempt_count
        repeat_incidence_met = repeat_incidence_consistent_count >= required_attempt_count
        repeat_spacing_met = (not repeat_required) or repeat_requirement_met

        if best is None:
            return {
                "final_verdict": None,
                "summary_message": "등록된 후보건이 없어 요청 전체 평가를 계산할 수 없습니다.",
                "overall_probability": None,
                "first_feasible_attempt_at": None,
                "expected_attempt_count": None,
                "max_attempts_considered": 0,
                "attempt_count_considered": 0,
                "required_attempt_count": required_attempt_count,
                "repeat_requirement_met": repeat_requirement_met,
                "repeat_quality_threshold": repeat_quality_threshold,
                "repeat_quality_attempt_count": repeat_quality_attempt_count,
                "repeat_spacing_hours_required": repeat_spacing_hours_required,
                "repeat_incidence_tolerance_deg": repeat_incidence_tolerance_deg,
                "repeat_baseline_incidence_deg": repeat_baseline_incidence_deg,
                "repeat_incidence_filtered_candidates": repeat_incidence_filtered_candidates,
                "repeat_incidence_consistent_count": repeat_incidence_consistent_count,
                "repeat_incidence_met": repeat_incidence_met,
                "repeat_spaced_attempt_count": repeat_spaced_attempt_count,
                "repeat_spacing_met": repeat_spacing_met,
                "dominant_risk_code": None,
                "best_candidate_code": None,
                "best_candidate_title": None,
                "baseline_candidate_code": baseline_candidate_code,
                "baseline_candidate_title": baseline.get("candidate_title") if baseline is not None else None,
                "feasible_count": 0,
                "conditional_count": 0,
                "rejected_count": 0,
            }

        if best["final_verdict"] == "FEASIBLE":
            final_verdict = "FEASIBLE"
        elif best["final_verdict"] == "CONDITIONALLY_FEASIBLE":
            final_verdict = "CONDITIONALLY_FEASIBLE"
        else:
            final_verdict = "NOT_FEASIBLE"

        if repeat_required and not repeat_requirement_met:
            final_verdict = "NOT_FEASIBLE" if feasible_count == 0 and conditional_count == 0 else "CONDITIONALLY_FEASIBLE"

        if feasible_count:
            summary_message = (
                f"가능 {feasible_count}건, 조건부 {conditional_count}건, 불가 {rejected_count}건입니다. "
                f"정책상 집계 상한 {len(considered_attempts)}건 기준 누적 성공확률은 {cumulative_probability * 100:.1f}%이며 "
                f"가장 유리한 후보는 {best['candidate_code']}입니다."
            )
        elif conditional_count:
            summary_message = (
                f"가능 후보는 없고 조건부 {conditional_count}건, 불가 {rejected_count}건입니다. "
                f"정책상 집계 상한 {len(considered_attempts)}건 기준 누적 성공확률은 {cumulative_probability * 100:.1f}%이며 "
                f"가장 유리한 후보는 {best['candidate_code']}입니다."
            )
        else:
            summary_message = (
                f"등록된 후보 {rejected_count}건 모두 현재 입력 기준으로 수행 불가합니다. "
                f"정책상 집계 상한 {len(considered_attempts)}건 기준 누적 성공확률은 {cumulative_probability * 100:.1f}%입니다."
            )

        if baseline is not None:
            baseline_phrase = f" 기준안은 {baseline['candidate_code']}"
            if best is not None and baseline["candidate_code"] != best["candidate_code"]:
                baseline_phrase += f", 최적안은 {best['candidate_code']}"
            baseline_phrase += "입니다."
            summary_message += baseline_phrase

        if repeat_required:
            if repeat_quality_attempt_count >= required_attempt_count and not repeat_incidence_met:
                repeat_message = (
                    f" 반복 촬영 요구 {required_attempt_count}회를 위해서는 기준 후보 대비 입사각 편차 "
                    f"{repeat_incidence_tolerance_deg:.1f}도 이하 후보가 더 필요합니다."
                )
            elif repeat_incidence_consistent_count >= required_attempt_count and not repeat_requirement_met:
                repeat_message = (
                    f" 반복 촬영 요구 {required_attempt_count}회를 위한 최소 재방문 간격 "
                    f"{repeat_spacing_hours_required}시간을 충족하지 못했습니다."
                )
            else:
                repeat_message = (
                    f" 반복 촬영 요구 {required_attempt_count}회를 "
                    f"{'충족했습니다' if repeat_requirement_met else '충족하지 못했습니다'}."
                )
            if repeat_quality_threshold is not None:
                repeat_message += f" 반복 카운트에는 성공확률 {repeat_quality_threshold:.2f} 이상 후보만 반영합니다."
            if repeat_incidence_tolerance_deg is not None:
                repeat_message += f" SAR 반복 카운트에는 입사각 편차 {repeat_incidence_tolerance_deg:.1f}도 이하 후보만 반영합니다."
            summary_message += repeat_message

        return {
            "final_verdict": final_verdict,
            "summary_message": summary_message,
            "overall_probability": cumulative_probability,
            "first_feasible_attempt_at": first_feasible_attempt_at,
            "expected_attempt_count": round(expected_attempt_count, 2) if considered_attempts else None,
            "max_attempts_considered": max_attempts,
            "attempt_count_considered": len(considered_attempts),
            "required_attempt_count": required_attempt_count,
            "repeat_requirement_met": repeat_requirement_met,
            "repeat_quality_threshold": repeat_quality_threshold,
            "repeat_quality_attempt_count": repeat_quality_attempt_count,
            "repeat_spacing_hours_required": repeat_spacing_hours_required,
            "repeat_incidence_tolerance_deg": repeat_incidence_tolerance_deg,
            "repeat_baseline_incidence_deg": repeat_baseline_incidence_deg,
            "repeat_incidence_filtered_candidates": repeat_incidence_filtered_candidates,
            "repeat_incidence_consistent_count": repeat_incidence_consistent_count,
            "repeat_incidence_met": repeat_incidence_met,
            "repeat_spaced_attempt_count": repeat_spaced_attempt_count,
            "repeat_spacing_met": repeat_spacing_met,
            "dominant_risk_code": (
                "REPEAT_PASS_INCIDENCE_INCONSISTENT"
                if repeat_required and repeat_quality_attempt_count >= required_attempt_count and not repeat_incidence_met
                else "REPEAT_PASS_SPACING_UNMET"
                if repeat_required and repeat_incidence_consistent_count >= required_attempt_count and not repeat_requirement_met
                else "REPEAT_PASS_REQUIREMENT_UNMET"
                if repeat_required and not repeat_requirement_met
                else best["dominant_risk_code"]
            ),
            "best_candidate_code": best["candidate_code"],
            "best_candidate_title": best["candidate_title"],
            "baseline_candidate_code": baseline["candidate_code"] if baseline is not None else baseline_candidate_code,
            "baseline_candidate_title": baseline["candidate_title"] if baseline is not None else None,
            "feasible_count": feasible_count,
            "conditional_count": conditional_count,
            "rejected_count": rejected_count,
        }

    def _estimate_request_recommendation_probability_gain(
        self,
        request_row: dict[str, Any] | None,
        recommendation: dict[str, Any],
        evaluated_by_code: dict[str, dict[str, Any]],
        candidate_contexts: dict[str, dict[str, Any]],
        request_aoi: dict[str, Any] | None,
        request_constraint: dict[str, Any] | None,
        request_sensor_options: list[dict[str, Any]],
        request_product_options: list[dict[str, Any]],
        base_overall_probability: float | None,
    ) -> float | None:
        if request_row is None or base_overall_probability is None:
            return None

        candidate_code = str(recommendation["recommendation_type"])
        base_context = candidate_contexts.get(candidate_code)
        base_evaluated = evaluated_by_code.get(candidate_code)
        if base_context is None or base_evaluated is None:
            return None

        modified_input = self._apply_recommendation_to_input(
            dict(base_context["adjusted_input"]),
            str(recommendation["parameter_name"]),
            str(recommendation["recommended_value"]),
        )
        if modified_input is None:
            return None

        output = self._simulate_request_candidate_input_with_context(
            request_row,
            request_aoi,
            request_constraint,
            request_sensor_options,
            request_product_options,
            modified_input,
            base_context["access"],
            base_context["contact"],
            base_context["task_conflicts"],
            base_context["booking_conflicts"],
            base_context["priority_tier"],
        )

        checks = output["checks"]
        updated_evaluated = dict(base_evaluated)
        updated_evaluated.update(
            {
                "final_verdict": output["final_verdict"],
                "candidate_status": output["candidate_status"],
                "summary_message": output["summary_message"],
                "dominant_risk_code": output.get("dominant_risk_code"),
                "overall_probability": output["probabilities"]["p_total_candidate"],
                "attempt_at": checks.get("access_start_at") or checks.get("pass_start_at"),
            }
        )

        evaluated = [updated_evaluated if code == candidate_code else dict(item) for code, item in evaluated_by_code.items()]
        evaluated.sort(
            key=lambda item: (
                item["attempt_at"] or "9999-12-31T23:59:59Z",
                int(item["candidate_rank"]),
            )
        )
        updated_result = self._build_request_result_summary(request_row, evaluated)
        if updated_result["overall_probability"] is None:
            return None
        gain = float(updated_result["overall_probability"]) - float(base_overall_probability)
        return round(max(gain, 0.0), 4)

    @staticmethod
    def _select_best_candidate(evaluated: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not evaluated:
            return None

        verdict_rank = {
            "FEASIBLE": 3,
            "CONDITIONALLY_FEASIBLE": 2,
            "NOT_FEASIBLE": 1,
        }
        return sorted(
            evaluated,
            key=lambda item: (
                verdict_rank.get(str(item["final_verdict"]), 0),
                float(item["overall_probability"]),
                -int(item["request_candidate_id"]),
            ),
            reverse=True,
        )[0]

    @staticmethod
    def _select_baseline_candidate(
        candidates: list[dict[str, Any]],
        baseline_candidate_code: str | None = None,
    ) -> dict[str, Any] | None:
        if not candidates:
            return None
        if baseline_candidate_code is not None:
            for candidate in candidates:
                if str(candidate.get("candidate_code")) == baseline_candidate_code:
                    return candidate
        explicit = [candidate for candidate in candidates if bool(candidate.get("is_baseline"))]
        if explicit:
            return sorted(
                explicit,
                key=lambda item: (
                    int(item.get("candidate_rank", 999999)),
                    -int(item.get("request_candidate_id", 0)),
                ),
            )[0]
        return sorted(
            candidates,
            key=lambda item: (
                int(item.get("candidate_rank", 999999)),
                -int(item.get("request_candidate_id", 0)),
            ),
        )[0]

    @staticmethod
    def _clear_other_baselines(conn: sqlite3.Connection, request_id: int, keep_request_candidate_id: int) -> None:
        conn.execute(
            """
            UPDATE request_candidate
            SET is_baseline = 0
            WHERE request_id = ? AND request_candidate_id <> ?
            """,
            (request_id, keep_request_candidate_id),
        )

    @staticmethod
    def _ensure_request_baseline(conn: sqlite3.Connection, request_id: int) -> None:
        current = conn.execute(
            """
            SELECT request_candidate_id
            FROM request_candidate
            WHERE request_id = ? AND is_baseline = 1
            ORDER BY candidate_rank, request_candidate_id
            LIMIT 1
            """,
            (request_id,),
        ).fetchone()
        if current is not None:
            return
        fallback = conn.execute(
            """
            SELECT request_candidate_id
            FROM request_candidate
            WHERE request_id = ?
            ORDER BY candidate_rank, request_candidate_id
            LIMIT 1
            """,
            (request_id,),
        ).fetchone()
        if fallback is None:
            return
        conn.execute(
            "UPDATE request_candidate SET is_baseline = 1 WHERE request_candidate_id = ?",
            (int(fallback["request_candidate_id"]),),
        )
