from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SensorType = Literal["OPTICAL", "SAR"]
PriorityTier = Literal["STANDARD", "PRIORITY", "URGENT"]


class SimulationInput(BaseModel):
    sensor_type: SensorType
    priority_tier: PriorityTier = "STANDARD"
    area_km2: float = Field(..., gt=0)
    window_hours: float = Field(..., gt=0)
    opportunity_start_at: str | None = None
    opportunity_end_at: str | None = None
    cloud_pct: float = Field(0, ge=0, le=100)
    max_cloud_pct: float = Field(20, ge=0, le=100)
    required_off_nadir_deg: float = Field(0, ge=0, le=60)
    max_off_nadir_deg: float = Field(25, ge=0, le=60)
    predicted_incidence_deg: float = Field(30, ge=0, le=60)
    min_incidence_deg: float = Field(25, ge=0, le=60)
    max_incidence_deg: float = Field(40, ge=0, le=60)
    sun_elevation_deg: float = Field(45, ge=0, le=90)
    min_sun_elevation_deg: float = Field(20, ge=0, le=90)
    coverage_ratio_predicted: float = Field(1.0, ge=0, le=1.2)
    coverage_ratio_required: float = Field(0.95, ge=0, le=1.0)
    expected_data_volume_gbit: float = Field(..., gt=0)
    recorder_free_gbit: float = Field(..., gt=0)
    recorder_backlog_gbit: float = Field(0, ge=0)
    available_downlink_gbit: float = Field(..., gt=0)
    power_margin_pct: float = Field(..., ge=0, le=100)
    thermal_margin_pct: float = Field(..., ge=0, le=100)


class Reason(BaseModel):
    reason_code: str
    reason_stage: str
    reason_severity: str
    reason_message: str


class Recommendation(BaseModel):
    parameter_name: str
    current_value: str
    recommended_value: str
    expected_effect_message: str


class SimulationOutput(BaseModel):
    candidate_status: str
    final_verdict: str
    summary_message: str
    dominant_risk_code: str | None
    probabilities: dict[str, float]
    checks: dict[str, float | bool]
    reasons: list[Reason]
    recommendations: list[Recommendation]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _priority_factor(priority_tier: PriorityTier) -> float:
    if priority_tier == "URGENT":
        return 0.99
    if priority_tier == "PRIORITY":
        return 0.97
    return 0.93


def simulate_feasibility(payload: SimulationInput) -> SimulationOutput:
    reasons: list[Reason] = []
    recommendations: list[Recommendation] = []

    if payload.sensor_type == "OPTICAL":
        off_nadir_excess = max(0.0, payload.required_off_nadir_deg - payload.max_off_nadir_deg)
        p_geo_off_nadir = _clamp(1.0 - off_nadir_excess / max(payload.max_off_nadir_deg, 1.0), 0.0, 1.0)
        cloud_excess = max(0.0, payload.cloud_pct - payload.max_cloud_pct)
        p_env_cloud = _clamp(1.0 - payload.cloud_pct / 100.0, 0.0, 1.0)
        p_env_cloud_soft = _clamp(1.0 - cloud_excess / 40.0, 0.0, 1.0)
        sun_gap = max(0.0, payload.min_sun_elevation_deg - payload.sun_elevation_deg)
        p_env_sun = _clamp(1.0 - sun_gap / max(payload.min_sun_elevation_deg, 1.0), 0.0, 1.0)

        if payload.required_off_nadir_deg > payload.max_off_nadir_deg:
            reasons.append(
                Reason(
                    reason_code="OFF_NADIR_EXCEEDED",
                    reason_stage="GEOMETRY",
                    reason_severity="HARD",
                    reason_message="요구 오프나디르 각도가 고객 제한을 초과했습니다.",
                )
            )
            recommendations.append(
                Recommendation(
                    parameter_name="max_off_nadir_deg",
                    current_value=f"{payload.max_off_nadir_deg:.1f}",
                    recommended_value=f"{payload.required_off_nadir_deg + 2.0:.1f}",
                    expected_effect_message="오프나디르 제한을 완화하면 기하 제약으로 막힌 패스를 다시 검토할 수 있습니다.",
                )
            )

        if payload.cloud_pct > payload.max_cloud_pct:
            reasons.append(
                Reason(
                    reason_code="CLOUD_PROBABILITY_TOO_HIGH",
                    reason_stage="ENVIRONMENT",
                    reason_severity="SOFT",
                    reason_message="예상 구름량이 요청한 광학 품질 기준을 초과했습니다.",
                )
            )
            recommendations.append(
                Recommendation(
                    parameter_name="max_cloud_pct",
                    current_value=f"{payload.max_cloud_pct:.1f}",
                    recommended_value=f"{min(100.0, payload.cloud_pct + 5.0):.1f}",
                    expected_effect_message="구름 허용치를 완화하면 조건부 패스를 실제 사용 가능 후보로 전환할 수 있습니다.",
                )
            )

        if payload.sun_elevation_deg < payload.min_sun_elevation_deg:
            reasons.append(
                Reason(
                    reason_code="SUN_ELEVATION_TOO_LOW",
                    reason_stage="ENVIRONMENT",
                    reason_severity="HARD",
                    reason_message="태양 고도가 요청한 최소 조도 기준보다 낮습니다.",
                )
            )

        p_geo_mode = p_geo_off_nadir
        p_env = p_env_cloud * p_env_cloud_soft * p_env_sun
    else:
        center_incidence = (payload.min_incidence_deg + payload.max_incidence_deg) / 2.0
        half_window = max((payload.max_incidence_deg - payload.min_incidence_deg) / 2.0, 1.0)
        full_window = max(payload.max_incidence_deg - payload.min_incidence_deg, 1.0)
        incidence_distance = abs(payload.predicted_incidence_deg - center_incidence)
        p_geo_mode = _clamp(1.0 - incidence_distance / full_window, 0.0, 1.0)
        p_env = 0.985

        if payload.predicted_incidence_deg < payload.min_incidence_deg or payload.predicted_incidence_deg > payload.max_incidence_deg:
            reasons.append(
                Reason(
                    reason_code="INCIDENCE_ANGLE_OUT_OF_RANGE",
                    reason_stage="GEOMETRY",
                    reason_severity="HARD",
                    reason_message="예상 SAR 입사각이 사용자 지정 운용 범위를 벗어났습니다.",
                )
            )
            recommendations.append(
                Recommendation(
                    parameter_name="incidence_window",
                    current_value=f"{payload.min_incidence_deg:.1f}-{payload.max_incidence_deg:.1f}",
                    recommended_value=f"{max(0.0, payload.min_incidence_deg - 3.0):.1f}-{payload.max_incidence_deg + 3.0:.1f}",
                    expected_effect_message="입사각 허용 범위를 넓히면 기하학적 가능성을 회복할 수 있습니다.",
                )
            )

    coverage_ratio = payload.coverage_ratio_predicted / max(payload.coverage_ratio_required, 0.01)
    p_geo_coverage = _clamp(coverage_ratio, 0.0, 1.0)
    p_geo = p_geo_mode * p_geo_coverage

    storage_headroom = payload.recorder_free_gbit - payload.expected_data_volume_gbit
    backlog_after_capture = payload.recorder_backlog_gbit + payload.expected_data_volume_gbit
    downlink_margin = payload.available_downlink_gbit - backlog_after_capture

    p_resource_storage = _clamp(payload.recorder_free_gbit / (payload.expected_data_volume_gbit * 1.15), 0.0, 1.0)
    p_resource_power = _clamp(payload.power_margin_pct / 25.0, 0.0, 1.0)
    p_resource_thermal = _clamp(payload.thermal_margin_pct / 25.0, 0.0, 1.0)
    p_resource = p_resource_storage * p_resource_power * p_resource_thermal

    p_downlink = _clamp(payload.available_downlink_gbit / max(backlog_after_capture, 1.0), 0.0, 1.0)
    nominal_window_hours = 72.0 if payload.sensor_type == "OPTICAL" else 48.0
    p_conflict_adjusted = _priority_factor(payload.priority_tier) * _clamp(payload.window_hours / nominal_window_hours, 0.7, 1.0)
    p_total_candidate = _clamp(p_geo * p_env * p_resource * p_downlink * p_conflict_adjusted, 0.0, 1.0)

    if payload.coverage_ratio_predicted < payload.coverage_ratio_required:
        reasons.append(
            Reason(
                reason_code="COVERAGE_SHORTFALL",
                reason_stage="GEOMETRY",
                reason_severity="HARD",
                reason_message="예상 장면 커버리지가 요청 최소 비율보다 낮습니다.",
            )
        )

    if storage_headroom < 0:
        reasons.append(
            Reason(
                reason_code="RECORDER_OVERFLOW",
                reason_stage="RESOURCE",
                reason_severity="HARD",
                reason_message="가용 레코더 용량이 예상 촬영 데이터량보다 작습니다.",
            )
        )
        recommendations.append(
            Recommendation(
                parameter_name="recorder_backlog_gbit",
                current_value=f"{payload.recorder_backlog_gbit:.1f}",
                recommended_value=f"{max(0.0, payload.recorder_backlog_gbit - payload.expected_data_volume_gbit):.1f}",
                expected_effect_message="이 패스 전에 레코더 백로그를 줄이면 저장 여유를 회복할 수 있습니다.",
            )
        )

    if downlink_margin < 0:
        reasons.append(
            Reason(
                reason_code="DOWNLINK_MARGIN_LOW",
                reason_stage="DOWNLINK",
                reason_severity="HARD",
                reason_message="계획된 다운링크 용량이 촬영 데이터와 기존 백로그를 함께 처리하기에 부족합니다.",
            )
        )
        recommendations.append(
            Recommendation(
                parameter_name="available_downlink_gbit",
                current_value=f"{payload.available_downlink_gbit:.1f}",
                recommended_value=f"{backlog_after_capture + 10.0:.1f}",
                expected_effect_message="더 길거나 더 빠른 contact window를 확보하면 다운링크 가능성을 회복할 수 있습니다.",
            )
        )

    if payload.power_margin_pct < 8:
        reasons.append(
            Reason(
                reason_code="POWER_MARGIN_LOW",
                reason_stage="RESOURCE",
                reason_severity="SOFT" if payload.power_margin_pct >= 5 else "HARD",
                reason_message="요청한 촬영 프로파일에 비해 전력 마진이 부족합니다.",
            )
        )

    if payload.thermal_margin_pct < 8:
        reasons.append(
            Reason(
                reason_code="THERMAL_MARGIN_LOW",
                reason_stage="RESOURCE",
                reason_severity="SOFT" if payload.thermal_margin_pct >= 5 else "HARD",
                reason_message="요청한 dwell 및 duty cycle에 비해 열 마진이 부족합니다.",
            )
        )

    hard_reasons = [reason for reason in reasons if reason.reason_severity == "HARD"]
    soft_reasons = [reason for reason in reasons if reason.reason_severity == "SOFT"]

    if hard_reasons:
        candidate_status = "REJECTED"
        final_verdict = "NOT_FEASIBLE"
        dominant_risk_code = hard_reasons[0].reason_code
    elif soft_reasons or p_total_candidate < 0.30:
        candidate_status = "CONDITIONAL"
        final_verdict = "CONDITIONALLY_FEASIBLE"
        dominant_risk_code = (soft_reasons[0].reason_code if soft_reasons else "LOW_TOTAL_PROBABILITY")
    else:
        candidate_status = "FEASIBLE"
        final_verdict = "FEASIBLE"
        dominant_risk_code = None

    if final_verdict == "FEASIBLE":
        summary_message = "이 시뮬레이션 패스는 기하, 환경, 자원, 다운링크 점검을 모두 통과합니다."
    elif final_verdict == "CONDITIONALLY_FEASIBLE":
        summary_message = "이 패스는 사용 가능하지만, 하나 이상의 소프트 제약 또는 낮은 확률 항목에 대해 운영자 검토가 필요합니다."
    else:
        summary_message = "이 패스는 하나 이상의 하드 제약을 위반하므로 현재 조건 그대로는 스케줄링하면 안 됩니다."

    return SimulationOutput(
        candidate_status=candidate_status,
        final_verdict=final_verdict,
        summary_message=summary_message,
        dominant_risk_code=dominant_risk_code,
        probabilities={
            "p_geo": round(p_geo, 4),
            "p_env": round(p_env, 4),
            "p_resource": round(p_resource, 4),
            "p_downlink": round(p_downlink, 4),
            "p_conflict_adjusted": round(p_conflict_adjusted, 4),
            "p_total_candidate": round(p_total_candidate, 4),
        },
        checks={
            "resource_feasible_flag": storage_headroom >= 0 and payload.power_margin_pct >= 5 and payload.thermal_margin_pct >= 5,
            "downlink_feasible_flag": downlink_margin >= 0,
            "storage_headroom_gbit": round(storage_headroom, 2),
            "backlog_after_capture_gbit": round(backlog_after_capture, 2),
            "downlink_margin_gbit": round(downlink_margin, 2),
            "power_margin_pct": round(payload.power_margin_pct, 2),
            "thermal_margin_pct": round(payload.thermal_margin_pct, 2),
        },
        reasons=reasons,
        recommendations=recommendations,
    )
