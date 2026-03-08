from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from repository import FeasibilityRepository
    from simulator import SimulationInput, SimulationOutput, simulate_feasibility
except ModuleNotFoundError:  # pragma: no cover - support package import
    from .repository import FeasibilityRepository
    from .simulator import SimulationInput, SimulationOutput, simulate_feasibility


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 6003
DEFAULT_DB_PATH = Path(os.environ.get("FEASIBILITY_DB_PATH", "./db/feasibility_satti.db"))
STATIC_DIR = Path(__file__).resolve().parent / "static"


class DevStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict) -> FileResponse:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


class RequestCandidateCreate(BaseModel):
    """요청 하위 수행계획 후보를 신규 생성할 때 사용하는 입력 모델.

    운영 권장:
    - `candidate_rank`는 요청 내 후보 실행 순서를 의미하므로 1부터 연속되게 관리한다.
    - `is_baseline=true`는 요청당 1건만 유지하는 것을 권장한다.
    - `input`은 시뮬레이션 엔진 입력 원본이며, 저장 후 검증 실행 시 동일 값으로 재계산된다.
    """

    candidate_title: str
    candidate_description: str
    candidate_status: str = "READY"
    candidate_rank: int = Field(..., ge=1, description="요청 내 후보 우선순위(1부터 시작).")
    is_baseline: bool = False
    input: SimulationInput


class RequestCandidateUpdate(BaseModel):
    """기존 수행계획 후보의 메타/입력값을 갱신할 때 사용하는 모델."""

    candidate_title: str
    candidate_description: str
    candidate_status: str = "READY"
    candidate_rank: int = Field(..., ge=1, description="요청 내 후보 우선순위(1부터 시작).")
    is_baseline: bool = False
    input: SimulationInput


class CandidateRunTrigger(BaseModel):
    """후보 저장 실행의 트리거 출처를 기록하는 메타데이터.

    프런트에서 추천안 자동 적용/분리 후보 생성 등 실행 유형을 기록할 때 사용한다.
    """

    trigger_type: str | None = None
    source_code: str | None = None
    parameter_name: str | None = None
    note: str | None = None


class RequestExternalRefCreate(BaseModel):
    """내부 요청에 외부 시스템 요청번호를 매핑할 때 사용하는 모델."""

    source_system_code: str = Field(..., description="외부 연계 시스템 식별 코드. 예: CUSTOMER_PORTAL, PARTNER_API")
    external_request_code: str = Field(..., description="외부 시스템 요청번호. source_system_code와 조합해 전역 유니크.")
    external_request_title: str | None = None
    external_customer_org_name: str | None = None
    external_requester_name: str | None = None
    is_primary: bool = True
    received_at: str | None = None


class RequestExternalRefUpdate(BaseModel):
    """외부 요청번호 매핑의 속성 갱신 모델(현재는 primary 승격만 지원)."""

    is_primary: bool = True


class RequestAoiCreate(BaseModel):
    """요청 AOI(관심영역) 정의 모델.

    AOI 중심/면적/경계 정보는 시뮬레이션 설명 및 문서화에 사용된다.
    """

    geometry_type: str = Field(..., description="도형 타입. 현재 seed/테스트는 POLYGON 사용.")
    geometry_wkt: str = Field(..., description="AOI WKT 문자열.")
    srid: int = Field(4326, description="좌표계 SRID. 기본 4326(WGS84).")
    area_km2: float = Field(..., description="AOI 면적(km²).")
    bbox_min_lon: float
    bbox_min_lat: float
    bbox_max_lon: float
    bbox_max_lat: float
    centroid_lon: float
    centroid_lat: float
    dominant_axis_deg: float | None = None


class RequestConstraintCreate(BaseModel):
    """요청 제약조건(기상/기하/기한/품질) 입력 모델."""

    max_cloud_pct: float | None = None
    max_off_nadir_deg: float | None = None
    min_incidence_deg: float | None = None
    max_incidence_deg: float | None = None
    preferred_local_time_start: str | None = None
    preferred_local_time_end: str | None = None
    min_sun_elevation_deg: float | None = None
    max_haze_index: float | None = None
    deadline_at: str | None = None
    coverage_ratio_required: float = 1.0


class RequestSensorOptionCreate(BaseModel):
    """요청 시 허용/선호하는 센서 옵션 모델."""

    satellite_id: int
    sensor_id: int
    sensor_mode_id: int
    preference_rank: int = Field(..., ge=1, description="센서 옵션 우선순위(1이 가장 선호).")
    is_mandatory: bool = False
    polarization_code: str | None = None


class RequestProductOptionCreate(BaseModel):
    """산출물 포맷/전송 관련 옵션 모델."""

    product_level_code: str
    product_type_code: str
    file_format_code: str
    delivery_mode_code: str
    ancillary_required_flag: bool = False


class RequestCreate(BaseModel):
    """내부 촬영요청 생성 모델.

    필수 구성:
    - 기본 요청 메타(기관/사용자/정책/시간창)
    - AOI/제약/센서/산출물 옵션
    - 필요 시 외부 요청번호(primary) 초기 매핑
    """

    customer_org_id: int
    customer_user_id: int
    service_policy_id: int
    request_title: str
    request_description: str
    request_status: str = "SUBMITTED"
    request_channel: str = "API"
    priority_tier: str | None = None
    requested_start_at: str
    requested_end_at: str
    emergency_flag: bool = False
    repeat_acquisition_flag: bool = False
    monitoring_count: int = Field(1, ge=1, description="반복 모니터링 요구 횟수(최소 1).")
    aoi: RequestAoiCreate
    constraint: RequestConstraintCreate
    sensor_options: list[RequestSensorOptionCreate]
    product_options: list[RequestProductOptionCreate]
    external_ref: RequestExternalRefCreate | None = None


class RequestUpdate(BaseModel):
    """요청 메타정보를 부분 수정할 때 사용하는 모델(PATCH)."""

    request_title: str | None = None
    request_description: str | None = None
    request_status: str | None = None
    request_channel: str | None = None
    priority_tier: str | None = None
    requested_start_at: str | None = None
    requested_end_at: str | None = None
    emergency_flag: bool | None = None
    repeat_acquisition_flag: bool | None = None
    monitoring_count: int | None = Field(None, ge=1)


class RequestCancel(BaseModel):
    """요청 취소 시 운영 메모를 남기기 위한 입력 모델."""

    cancel_reason: str | None = None


SIMULATION_INPUT_FIELDS = (
    "sensor_type",
    "priority_tier",
    "area_km2",
    "window_hours",
    "opportunity_start_at",
    "opportunity_end_at",
    "cloud_pct",
    "max_cloud_pct",
    "required_off_nadir_deg",
    "max_off_nadir_deg",
    "predicted_incidence_deg",
    "min_incidence_deg",
    "max_incidence_deg",
    "sun_elevation_deg",
    "min_sun_elevation_deg",
    "coverage_ratio_predicted",
    "coverage_ratio_required",
    "expected_data_volume_gbit",
    "recorder_free_gbit",
    "recorder_backlog_gbit",
    "available_downlink_gbit",
    "power_margin_pct",
    "thermal_margin_pct",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def to_candidate_meta(payload: RequestCandidateCreate | RequestCandidateUpdate) -> dict[str, object]:
    timestamp = utc_now()
    return {
        "candidate_title": payload.candidate_title,
        "candidate_description": payload.candidate_description,
        "candidate_status": payload.candidate_status,
        "candidate_rank": payload.candidate_rank,
        "is_baseline": payload.is_baseline,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def to_candidate_input(payload: RequestCandidateCreate | RequestCandidateUpdate) -> dict[str, object]:
    return payload.input.model_dump()


def create_app(db_path: Path) -> FastAPI:
    repo = FeasibilityRepository(db_path)
    app = FastAPI(
        title="K-Sattie Feasibility Analysis API",
        version="1.0.0",
        description=(
            "위성 촬영요청 feasibility 시뮬레이션/평가 API입니다.\n\n"
            "개발 가이드 핵심:\n"
            "1) `/requests`로 내부 요청을 생성합니다.\n"
            "2) `/requests/{request_code}`로 요청 전체 리포트를 조회합니다.\n"
            "3) `/requests/{request_code}/request-candidates`로 수행계획 후보를 관리합니다.\n"
            "4) `/simulate-candidate-input`은 저장 없이 현재 입력값을 즉시 시뮬레이션합니다.\n"
            "5) `/simulate`는 요청 컨텍스트 없이 단일 입력만 계산하는 엔진 테스트 용도입니다.\n\n"
            "식별자 원칙:\n"
            "- `request_code`: 내부 요청 식별자(서버 발번)\n"
            "- `external_request_code`: 외부 시스템 요청번호(별도 매핑)\n"
            "- `candidate_code`: 요청 하위 수행계획 후보 식별자\n\n"
            "시간 필드 권장:\n"
            "- UTC ISO-8601(`...Z`) 형식 사용을 권장합니다."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.mount("/static", DevStaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "index.html",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @app.get(
        "/health",
        tags=["system"],
        summary="헬스체크",
        description=(
            "API 프로세스 생존 여부를 확인하는 기본 상태 점검 엔드포인트입니다.\n\n"
            "운영 가이드:\n"
            "- 이 API는 비즈니스 데이터 무결성을 보장하지 않으며, 프로세스 응답 가능 여부만 확인합니다.\n"
            "- DB 연결 상태까지 점검하려면 실제 읽기 API(`/requests`)를 함께 호출하세요."
        ),
    )
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/requests",
        tags=["request"],
        summary="요청 목록 조회",
        description=(
            "내부 요청 카탈로그(요약 목록)를 조회합니다.\n\n"
            "설계 의도:\n"
            "- 좌측 요청 목록/검색의 초기 데이터 소스 역할\n"
            "- 상세 리포트 조회 전 lightweight 목록 제공\n\n"
            "권장 사용:\n"
            "1) 목록 조회 후 사용자가 선택한 `request_code`를 확보\n"
            "2) `GET /requests/{request_code}`로 상세 리포트 조회"
        ),
    )
    def list_requests() -> dict[str, list[dict[str, object]]]:
        return {"items": repo.list_requests()}

    @app.post(
        "/requests",
        tags=["request"],
        summary="요청 생성",
        description=(
            "외부/내부 사용자가 feasibility 검토를 시작할 때 호출하는 최초 진입 API입니다.\n\n"
            "설계 의도:\n"
            "- 내부 식별자(`request_code`)와 외부 식별자(`external_request_code`)를 분리 관리합니다.\n"
            "- 요청 원본(AOI/제약/센서/산출물)을 한 트랜잭션으로 저장해 재현 가능한 기준 입력을 만듭니다.\n"
            "- 이후 후보 생성/시뮬레이션/실행 이력은 이 요청을 기준으로 누적됩니다.\n\n"
            "저장 범위(원자적 생성):\n"
            "1) feasibility_request: 요청 메타(기관/사용자/정책/우선순위/시간창)\n"
            "2) request_aoi: AOI 도형/면적/경계/중심 정보\n"
            "3) request_constraint: 기상/기하/품질/기한 제약\n"
            "4) request_sensor_option: 위성/센서/모드 선호 및 필수여부\n"
            "5) request_product_option: 산출물 포맷/전송 요구\n"
            "6) request_external_ref(optional): 외부 요청번호 primary 매핑\n\n"
            "필드 운영 가이드:\n"
            "- `requested_start_at`, `requested_end_at`: UTC ISO-8601(`...Z`) 권장\n"
            "- `monitoring_count`: 반복 촬영 요구 횟수(최소 1)\n"
            "- `priority_tier` 미입력 시 정책 기본 우선순위로 해석 가능(구현/저장 규칙 준수)\n"
            "- `external_ref`는 선택이며, 입력 시 동일 source/code 조합 중복은 409로 거절됩니다.\n\n"
            "대표 실패 케이스:\n"
            "- 400: 입력 검증 오류(필수값 누락, rank<1 등)\n"
            "- 409: 외부 요청번호 중복(`source_system_code + external_request_code`)\n\n"
            "생성 후 권장 호출 순서:\n"
            "1) `GET /requests/{request_code}`로 통합 리포트 확인\n"
            "2) `POST /requests/{request_code}/request-candidates`로 후보 추가\n"
            "3) `POST /requests/{request_code}/simulate-candidate-input`로 저장 전 즉시 평가\n"
            "4) `POST /requests/{request_code}/request-candidates/{candidate_code}/simulate`로 실행 이력 저장"
        ),
    )
    def create_request(
        payload: RequestCreate = Body(
            ...,
            examples={
                "optical_emergency": {
                    "summary": "광학 긴급 단건 요청(외부 요청번호 포함)",
                    "description": "재난 상황에서 광학 우선 촬영을 요청하고, 외부 포털 번호를 primary로 동시에 연결하는 예시",
                    "value": {
                        "customer_org_id": 1,
                        "customer_user_id": 1,
                        "service_policy_id": 1,
                        "request_title": "서울 AOI 광학 촬영 요청건",
                        "request_description": "서울 도심 침수 의심 지역 광학 판독 요청",
                        "request_status": "SUBMITTED",
                        "request_channel": "API",
                        "priority_tier": "URGENT",
                        "requested_start_at": "2026-03-12T00:00:00Z",
                        "requested_end_at": "2026-03-13T00:00:00Z",
                        "emergency_flag": True,
                        "repeat_acquisition_flag": False,
                        "monitoring_count": 1,
                        "aoi": {
                            "geometry_type": "POLYGON",
                            "geometry_wkt": "POLYGON((126.90 37.50,127.05 37.50,127.05 37.62,126.90 37.62,126.90 37.50))",
                            "srid": 4326,
                            "area_km2": 145.2,
                            "bbox_min_lon": 126.90,
                            "bbox_min_lat": 37.50,
                            "bbox_max_lon": 127.05,
                            "bbox_max_lat": 37.62,
                            "centroid_lon": 126.975,
                            "centroid_lat": 37.56,
                            "dominant_axis_deg": 90.0,
                        },
                        "constraint": {
                            "max_cloud_pct": 30.0,
                            "max_off_nadir_deg": 35.0,
                            "min_sun_elevation_deg": 20.0,
                            "deadline_at": "2026-03-13T00:00:00Z",
                            "coverage_ratio_required": 0.9,
                        },
                        "sensor_options": [
                            {
                                "satellite_id": 1,
                                "sensor_id": 1,
                                "sensor_mode_id": 1,
                                "preference_rank": 1,
                                "is_mandatory": True,
                            }
                        ],
                        "product_options": [
                            {
                                "product_level_code": "L1C",
                                "product_type_code": "ORTHO",
                                "file_format_code": "GEOTIFF",
                                "delivery_mode_code": "FTP",
                                "ancillary_required_flag": True,
                            }
                        ],
                        "external_ref": {
                            "source_system_code": "CUSTOMER_PORTAL",
                            "external_request_code": "EXT-SEOUL-OPT-9001",
                            "external_request_title": "서울 광학 긴급 촬영 요청",
                            "external_customer_org_name": "Seoul Disaster Analytics Center",
                            "external_requester_name": "Kim Mina",
                            "is_primary": True,
                            "received_at": "2026-03-11T23:40:00Z",
                        },
                    },
                },
                "sar_repeat_monitoring": {
                    "summary": "SAR 반복 모니터링 요청",
                    "description": "야간/기상 영향을 줄이기 위해 SAR 기준으로 반복 횟수를 명시한 예시",
                    "value": {
                        "customer_org_id": 1,
                        "customer_user_id": 1,
                        "service_policy_id": 2,
                        "request_title": "서해 AOI SAR 촬영 요청건",
                        "request_description": "서해 선박 밀집 구간 반복 모니터링",
                        "request_status": "SUBMITTED",
                        "request_channel": "API",
                        "priority_tier": "PRIORITY",
                        "requested_start_at": "2026-03-12T00:00:00Z",
                        "requested_end_at": "2026-03-14T00:00:00Z",
                        "emergency_flag": False,
                        "repeat_acquisition_flag": True,
                        "monitoring_count": 2,
                        "aoi": {
                            "geometry_type": "POLYGON",
                            "geometry_wkt": "POLYGON((124.65 36.85,124.95 36.85,124.95 37.10,124.65 37.10,124.65 36.85))",
                            "srid": 4326,
                            "area_km2": 510.0,
                            "bbox_min_lon": 124.65,
                            "bbox_min_lat": 36.85,
                            "bbox_max_lon": 124.95,
                            "bbox_max_lat": 37.10,
                            "centroid_lon": 124.80,
                            "centroid_lat": 36.975,
                            "dominant_axis_deg": 90.0,
                        },
                        "constraint": {
                            "min_incidence_deg": 25.0,
                            "max_incidence_deg": 40.0,
                            "deadline_at": "2026-03-14T00:00:00Z",
                            "coverage_ratio_required": 0.95,
                        },
                        "sensor_options": [
                            {
                                "satellite_id": 2,
                                "sensor_id": 2,
                                "sensor_mode_id": 2,
                                "preference_rank": 1,
                                "is_mandatory": True,
                                "polarization_code": "HH",
                            }
                        ],
                        "product_options": [
                            {
                                "product_level_code": "L1C",
                                "product_type_code": "SIGMA0",
                                "file_format_code": "HDF5",
                                "delivery_mode_code": "FTP",
                                "ancillary_required_flag": True,
                            }
                        ],
                    },
                },
            },
        )
    ) -> dict[str, object]:
        try:
            created = repo.create_request(
                {
                    "customer_org_id": payload.customer_org_id,
                    "customer_user_id": payload.customer_user_id,
                    "service_policy_id": payload.service_policy_id,
                    "request_title": payload.request_title,
                    "request_description": payload.request_description,
                    "request_status": payload.request_status,
                    "request_channel": payload.request_channel,
                    "priority_tier": payload.priority_tier,
                    "requested_start_at": payload.requested_start_at,
                    "requested_end_at": payload.requested_end_at,
                    "emergency_flag": payload.emergency_flag,
                    "repeat_acquisition_flag": payload.repeat_acquisition_flag,
                    "monitoring_count": payload.monitoring_count,
                    "created_at": utc_now(),
                },
                payload.aoi.model_dump(),
                payload.constraint.model_dump(),
                [item.model_dump() for item in payload.sensor_options],
                [item.model_dump() for item in payload.product_options],
                payload.external_ref.model_dump() if payload.external_ref is not None else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except sqlite3.IntegrityError as exc:
            detail = str(exc)
            if "request_external_ref.source_system_code, request_external_ref.external_request_code" in detail:
                raise HTTPException(status_code=409, detail="external request code already exists for the given source system") from exc
            raise HTTPException(status_code=409, detail=detail) from exc
        return created

    @app.get(
        "/requests/{request_code}",
        tags=["request"],
        summary="요청 상세 리포트 조회",
        description=(
            "요청 단위 통합 리포트를 반환합니다.\n\n"
            "포함 데이터:\n"
            "- 요청 원본 메타, AOI, 제약, 정책\n"
            "- 외부 요청번호 매핑 목록\n"
            "- 요청 하위 후보 목록 및 현재 요약\n"
            "- proposal(누적확률/반복요건/완화제안) 및 점검 결과\n\n"
            "설계 의도:\n"
            "- 화면 렌더링에 필요한 데이터를 단일 API로 공급해 왕복 호출을 줄입니다.\n"
            "- 요청 상태를 재현 가능한 스냅샷 형태로 제공합니다.\n\n"
            "오류 케이스:\n"
            "- 404: 존재하지 않는 `request_code`"
        ),
    )
    def get_request(request_code: str) -> dict[str, object]:
        payload = repo.get_request_report(request_code)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        return payload

    @app.patch(
        "/requests/{request_code}",
        tags=["request"],
        summary="요청 메타 수정",
        description=(
            "요청 메타정보를 부분 수정합니다(PATCH).\n\n"
            "설계 의도:\n"
            "- 요청 자체를 재생성하지 않고 제목/설명/시간창/우선순위/상태를 운영 중에 보정\n"
            "- 후보/실행 이력/외부 매핑은 유지한 채 요청 헤더만 업데이트\n\n"
            "운영 규칙:\n"
            "- 바디에 포함된 필드만 수정됩니다.\n"
            "- `monitoring_count`는 1 이상이어야 합니다.\n"
            "- 상태 전이 정책(예: CANCELLED 이후 재오픈)은 상위 운영정책에서 통제하세요.\n\n"
            "오류 케이스:\n"
            "- 404: 요청 없음\n"
            "- 400: 유효하지 않은 입력"
        ),
    )
    def update_request(
        request_code: str,
        payload: RequestUpdate = Body(
            ...,
            examples={
                "retitle_and_reschedule": {
                    "summary": "요청명/설명/시간창 수정",
                    "value": {
                        "request_title": "서울 AOI 광학 촬영 요청건(수정)",
                        "request_description": "우선 판독 구역 변경에 따라 시간창 보정",
                        "requested_start_at": "2026-03-12T06:00:00Z",
                        "requested_end_at": "2026-03-13T06:00:00Z",
                        "priority_tier": "PRIORITY",
                    },
                },
                "status_update": {
                    "summary": "요청 상태 변경",
                    "value": {
                        "request_status": "IN_REVIEW",
                    },
                },
            },
        ),
    ) -> dict[str, object]:
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="at least one field must be provided for update")
        updated = repo.update_request(request_code, updates)
        if updated is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        return updated

    @app.post(
        "/requests/{request_code}/cancel",
        tags=["request"],
        summary="요청 취소",
        description=(
            "요청 상태를 `CANCELLED`로 변경합니다.\n\n"
            "설계 의도:\n"
            "- 삭제가 아닌 상태 전환으로 취소 이력을 보존\n"
            "- 취소 후에도 기존 후보/실행 결과 조회는 가능(운영정책에 따라 후속 실행은 제한 가능)\n\n"
            "운영 권장:\n"
            "- `cancel_reason`에 취소 사유/요청자/변경 티켓 정보를 남겨 추적성을 확보하세요.\n\n"
            "오류 케이스:\n"
            "- 404: 요청 없음"
        ),
    )
    def cancel_request(
        request_code: str,
        payload: RequestCancel = Body(
            default=RequestCancel(),
            examples={
                "cancel_with_reason": {
                    "summary": "사유를 남기고 취소",
                    "value": {
                        "cancel_reason": "고객 요청 철회(티켓 #OPS-2026-311)",
                    },
                }
            },
        ),
    ) -> dict[str, object]:
        cancelled = repo.cancel_request(request_code)
        if cancelled is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        return {
            "cancelled": True,
            "cancelled_at": utc_now(),
            "cancel_reason": payload.cancel_reason,
            "request": cancelled.get("request"),
        }

    @app.get(
        "/requests/{request_code}/result-access",
        tags=["request"],
        summary="결과 데이터 접근 안내 조회",
        description=(
            "요청의 산출물 전달 방식(`delivery_mode_code`)을 기준으로 결과 데이터 접근 가이드를 제공합니다.\n\n"
            "설계 의도:\n"
            "- 실제 파일 다운로드 API가 분리되어 있거나 외부 시스템 연계인 경우, 소비자가 접근 경로를 빠르게 파악\n"
            "- 요청 상태/최신 판정/전달 옵션을 한 번에 요약해 후속 자동화에 활용\n\n"
            "주의:\n"
            "- 이 API는 '안내/가이드'이며, 실제 파일 바이너리를 내려주지 않습니다.\n"
            "- 실제 다운로드 주소/인증 토큰은 운영 환경의 배포 시스템에 따라 별도 제공됩니다."
        ),
    )
    def get_request_result_access(request_code: str) -> dict[str, object]:
        request_row = repo.get_request(request_code)
        if request_row is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")

        product_options = repo.list_request_product_options(request_code)
        report = repo.get_request_report(request_code) or {}
        latest_run = repo.get_latest_run(request_code)

        def _delivery_guide(mode: str) -> dict[str, object]:
            normalized = str(mode or "").upper()
            if normalized == "FTP":
                return {
                    "access_channel": "FTP",
                    "guide_message": "운영 FTP 엔드포인트에 접속해 요청코드 기준 경로에서 산출물을 조회합니다.",
                    "uri_template": "ftp://<host>/<base_path>/{request_code}/",
                    "required_credentials": ["ftp_user", "ftp_password_or_key"],
                }
            if normalized == "S3":
                return {
                    "access_channel": "S3",
                    "guide_message": "오브젝트 스토리지 버킷에서 요청코드 prefix로 산출물을 조회합니다.",
                    "uri_template": "s3://<bucket>/<prefix>/{request_code}/",
                    "required_credentials": ["access_key", "secret_key", "region"],
                }
            if normalized == "API":
                return {
                    "access_channel": "API",
                    "guide_message": "운영 결과 제공 API를 통해 요청코드 기준으로 파일 메타/다운로드 링크를 조회합니다.",
                    "uri_template": "https://<result-api>/requests/{request_code}/products",
                    "required_credentials": ["api_token"],
                }
            return {
                "access_channel": normalized or "UNKNOWN",
                "guide_message": "운영 전달 정책 문서를 확인해 접근 경로를 조회하세요.",
                "uri_template": None,
                "required_credentials": [],
            }

        delivery_guides = []
        for option in product_options:
            guide = _delivery_guide(str(option.get("delivery_mode_code") or ""))
            delivery_guides.append(
                {
                    "product_level_code": option.get("product_level_code"),
                    "product_type_code": option.get("product_type_code"),
                    "file_format_code": option.get("file_format_code"),
                    "delivery_mode_code": option.get("delivery_mode_code"),
                    "ancillary_required_flag": bool(option.get("ancillary_required_flag")),
                    **guide,
                }
            )

        return {
            "request_code": request_row.get("request_code"),
            "request_title": request_row.get("request_title"),
            "request_status": request_row.get("request_status"),
            "latest_run_id": latest_run.get("run_id") if latest_run else None,
            "latest_final_verdict": (report.get("result") or {}).get("final_verdict"),
            "latest_overall_probability": (report.get("result") or {}).get("overall_probability"),
            "delivery_access_guides": delivery_guides,
        }

    @app.get(
        "/requests/{request_code}/external-refs",
        tags=["external-ref"],
        summary="외부 요청번호 매핑 목록 조회",
        description=(
            "내부 요청에 연결된 외부 요청번호 매핑 목록을 조회합니다.\n\n"
            "설계 의도:\n"
            "- 내부 식별자와 외부 식별자 간 연결 상태를 명시적으로 확인\n"
            "- primary/secondary 구분을 통해 대외 연계 우선 식별자를 관리\n\n"
            "오류 케이스:\n"
            "- 404: 요청 없음"
        ),
    )
    def list_request_external_refs(request_code: str) -> dict[str, list[dict[str, object]]]:
        if repo.get_request(request_code) is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        return {"items": repo.list_request_external_refs(request_code)}

    @app.post(
        "/requests/{request_code}/external-refs",
        tags=["external-ref"],
        summary="외부 요청번호 매핑 생성",
        description=(
            "기존 내부 요청에 외부 요청번호를 추가 연결합니다.\n\n"
            "설계 의도:\n"
            "- 내부 요청(`request_code`)과 외부 요청번호를 느슨하게 연결하여 다수 채널 연계를 지원합니다.\n"
            "- 하나의 요청에 primary/secondary 외부 참조를 둘 수 있습니다.\n"
            "- 외부 요청번호 중복 입력은 source/code 조합 단위로 차단합니다.\n\n"
            "운영 규칙:\n"
            "- `source_system_code + external_request_code`는 전역 유니크(중복 시 409)\n"
            "- `is_primary=true`로 저장 시 기존 primary는 해제될 수 있습니다.\n"
            "- 화면에서는 외부 요청번호를 식별자로 쓰지 말고 `request_external_ref_id`를 사용하세요."
        ),
    )
    def create_request_external_ref(
        request_code: str,
        payload: RequestExternalRefCreate = Body(
            ...,
            examples={
                "partner_primary_ref": {
                    "summary": "파트너 시스템 번호를 primary로 연결",
                    "value": {
                        "source_system_code": "PARTNER_API",
                        "external_request_code": "PARTNER-SEOUL-777",
                        "external_request_title": "서울 광학 긴급 요청",
                        "external_customer_org_name": "Seoul Disaster Analytics Center",
                        "external_requester_name": "Han Mina",
                        "is_primary": True,
                        "received_at": "2026-03-07T11:00:00Z",
                    },
                },
                "secondary_ref": {
                    "summary": "보조 채널 번호를 secondary로 연결",
                    "value": {
                        "source_system_code": "CUSTOMER_PORTAL",
                        "external_request_code": "EXT-SEOUL-ARCHIVE-1004",
                        "external_request_title": "서울 요청 백업 식별번호",
                        "is_primary": False,
                    },
                },
            },
        ),
    ) -> dict[str, object]:
        if repo.get_request(request_code) is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        try:
            created = repo.create_request_external_ref(
                request_code,
                {
                    "source_system_code": payload.source_system_code,
                    "external_request_code": payload.external_request_code,
                    "external_request_title": payload.external_request_title,
                    "external_customer_org_name": payload.external_customer_org_name,
                    "external_requester_name": payload.external_requester_name,
                    "is_primary": payload.is_primary,
                    "received_at": payload.received_at,
                    "created_at": utc_now(),
                },
            )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "external request code already exists for the given source system: "
                        f"{payload.source_system_code}/{payload.external_request_code}"
                    ),
                ) from exc
            raise
        if created is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        return created

    @app.patch(
        "/requests/{request_code}/external-refs/{request_external_ref_id}",
        tags=["external-ref"],
        summary="외부 요청번호 primary 지정",
        description=(
            "지정한 외부 요청번호 매핑을 primary로 승격합니다.\n\n"
            "운영 규칙:\n"
            "- 현재 구현은 `is_primary=true`만 허용합니다.\n"
            "- primary 변경 시 동일 요청의 기존 primary는 자동 해제됩니다.\n\n"
            "오류 케이스:\n"
            "- 400: `is_primary=false` 입력\n"
            "- 404: 요청 또는 매핑 ID 없음"
        ),
    )
    def update_request_external_ref(
        request_code: str,
        request_external_ref_id: int,
        payload: RequestExternalRefUpdate = Body(
            ...,
            examples={
                "set_primary": {
                    "summary": "해당 외부 매핑을 primary로 지정",
                    "value": {"is_primary": True},
                }
            },
        ),
    ) -> dict[str, object]:
        if repo.get_request(request_code) is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        if not payload.is_primary:
            raise HTTPException(status_code=400, detail="only primary assignment is supported")
        updated = repo.set_request_external_ref_primary(request_code, request_external_ref_id)
        if updated is None:
            raise HTTPException(
                status_code=404,
                detail=f"external request ref not found: {request_code}/{request_external_ref_id}",
            )
        return updated

    @app.delete(
        "/requests/{request_code}/external-refs/{request_external_ref_id}",
        tags=["external-ref"],
        summary="외부 요청번호 매핑 삭제",
        description=(
            "지정한 외부 요청번호 매핑을 삭제합니다.\n\n"
            "운영 규칙:\n"
            "- 삭제 대상이 primary인 경우, 남은 매핑 중 하나가 자동 primary가 될 수 있습니다.\n"
            "- 삭제 후 외부 식별자 기반 조회/연계 로직 영향 여부를 클라이언트에서 확인하세요.\n\n"
            "오류 케이스:\n"
            "- 404: 요청 또는 매핑 ID 없음"
        ),
    )
    def delete_request_external_ref(request_code: str, request_external_ref_id: int) -> dict[str, object]:
        if repo.get_request(request_code) is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        deleted = repo.delete_request_external_ref(request_code, request_external_ref_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"external request ref not found: {request_code}/{request_external_ref_id}",
            )
        return {
            "deleted": True,
            "request_code": request_code,
            "request_external_ref_id": request_external_ref_id,
        }

    @app.get(
        "/requests/{request_code}/request-candidates",
        tags=["candidate"],
        summary="요청 후보 목록 조회",
        description=(
            "요청 하위 수행계획 후보 목록을 조회합니다.\n\n"
            "설계 의도:\n"
            "- 후보 카드/테이블 렌더링용 요약 데이터 제공\n"
            "- 기준안 여부/순위/상태를 중심으로 비교 가능하게 구성\n\n"
            "오류 케이스:\n"
            "- 404: 요청 없음"
        ),
    )
    def list_request_candidates(request_code: str) -> dict[str, list[dict[str, object]]]:
        if repo.get_request(request_code) is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        return {"items": repo.list_request_candidates(request_code)}

    @app.get(
        "/requests/{request_code}/request-candidates/{candidate_code}",
        tags=["candidate"],
        summary="요청 후보 상세 조회",
        description=(
            "특정 후보의 상세 리포트를 조회합니다.\n\n"
            "포함 데이터:\n"
            "- 후보 메타(제목/설명/순위/기준안 여부)\n"
            "- 후보 입력값 원본\n"
            "- 현재 평가 결과(확률/주요 위험/사유/점검)\n"
            "- 저장 실행 이력(run sequence)\n\n"
            "오류 케이스:\n"
            "- 404: 요청 또는 후보 없음"
        ),
    )
    def get_request_candidate(request_code: str, candidate_code: str) -> dict[str, object]:
        payload = repo.get_request_candidate_report(request_code, candidate_code)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"request candidate not found: {request_code}/{candidate_code}")
        return payload

    @app.post(
        "/requests/{request_code}/request-candidates",
        tags=["candidate"],
        summary="요청 후보 생성",
        description=(
            "요청 하위 수행계획 후보를 신규 생성합니다.\n\n"
            "설계 의도:\n"
            "- 요청 원본과 분리된 다수의 수행계획 가설(candidate)을 독립 비교합니다.\n"
            "- 후보별 입력은 이후 저장 실행 이력의 기준점이 됩니다.\n"
            "- `candidate_code`는 서버가 발번하며 클라이언트는 제목/순위/입력에 집중합니다.\n\n"
            "권장 운영:\n"
            "- 기준안은 1건(`is_baseline=true`)만 유지\n"
            "- `candidate_rank`는 실행 우선순위이므로 1부터 연속 정렬\n"
            "- 초안 작성 후 `/simulate-candidate-input`으로 저장 전 즉시 검증 가능"
        ),
    )
    def create_request_candidate(
        request_code: str,
        payload: RequestCandidateCreate = Body(
            ...,
            examples={
                "sar_baseline": {
                    "summary": "SAR 기준안 후보 생성",
                    "value": {
                        "candidate_title": "기본 Stripmap 안",
                        "candidate_description": "기본 SAR 촬영 조건으로 가능한지 보는 기준 후보입니다.",
                        "candidate_status": "READY",
                        "candidate_rank": 1,
                        "is_baseline": True,
                        "input": {
                            "sensor_type": "SAR",
                            "priority_tier": "PRIORITY",
                            "area_km2": 625.0,
                            "window_hours": 48.0,
                            "predicted_incidence_deg": 28.0,
                            "min_incidence_deg": 25.0,
                            "max_incidence_deg": 40.0,
                            "coverage_ratio_predicted": 0.99,
                            "coverage_ratio_required": 0.95,
                            "expected_data_volume_gbit": 22.0,
                            "recorder_free_gbit": 44.0,
                            "recorder_backlog_gbit": 8.0,
                            "available_downlink_gbit": 36.0,
                            "power_margin_pct": 18.0,
                            "thermal_margin_pct": 16.0,
                        },
                    },
                },
                "optical_relaxed_cloud": {
                    "summary": "광학 구름 완화 비교안",
                    "value": {
                        "candidate_title": "구름 완화 검토안",
                        "candidate_description": "구름 허용치를 조정한 비교 후보",
                        "candidate_status": "READY",
                        "candidate_rank": 2,
                        "is_baseline": False,
                        "input": {
                            "sensor_type": "OPTICAL",
                            "priority_tier": "URGENT",
                            "area_km2": 145.2,
                            "window_hours": 24.0,
                            "cloud_pct": 42.0,
                            "max_cloud_pct": 45.0,
                            "required_off_nadir_deg": 17.0,
                            "max_off_nadir_deg": 35.0,
                            "sun_elevation_deg": 34.0,
                            "min_sun_elevation_deg": 20.0,
                            "coverage_ratio_predicted": 0.93,
                            "coverage_ratio_required": 0.9,
                            "expected_data_volume_gbit": 16.0,
                            "recorder_free_gbit": 30.0,
                            "recorder_backlog_gbit": 6.0,
                            "available_downlink_gbit": 28.0,
                            "power_margin_pct": 20.0,
                            "thermal_margin_pct": 19.0,
                        },
                    },
                },
            },
        ),
    ) -> dict[str, object]:
        if repo.get_request(request_code) is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        created = repo.create_request_candidate(
            request_code,
            {
                **to_candidate_meta(payload),
            },
            to_candidate_input(payload),
        )
        if created is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        return created

    @app.patch(
        "/requests/{request_code}/request-candidates/{candidate_code}",
        tags=["candidate"],
        summary="요청 후보 수정",
        description=(
            "요청 하위 수행계획 후보의 메타/입력값을 갱신합니다.\n\n"
            "설계 의도:\n"
            "- 후보 초안 보정, 비교안 파생, 기준안 전환 등 반복 편집 지원\n"
            "- 저장 실행 전 단계에서 입력값을 안전하게 누적 수정\n\n"
            "운영 규칙:\n"
            "- `candidate_code`는 불변이며 PATCH로 변경하지 않습니다.\n"
            "- `candidate_rank` 충돌/정렬 정책은 클라이언트에서 명시적으로 관리 권장\n\n"
            "오류 케이스:\n"
            "- 404: 요청/후보 없음"
        ),
    )
    def update_request_candidate(
        request_code: str,
        candidate_code: str,
        payload: RequestCandidateUpdate = Body(
            ...,
            examples={
                "update_candidate_geometry": {
                    "summary": "후보 제목/순위/기하 입력 갱신",
                    "value": {
                        "candidate_title": "입사각 완화 비교안",
                        "candidate_description": "입사각 범위를 완화해 재평가하는 후보",
                        "candidate_status": "READY",
                        "candidate_rank": 2,
                        "is_baseline": False,
                        "input": {
                            "sensor_type": "SAR",
                            "priority_tier": "PRIORITY",
                            "area_km2": 625.0,
                            "window_hours": 48.0,
                            "predicted_incidence_deg": 31.0,
                            "min_incidence_deg": 23.0,
                            "max_incidence_deg": 42.0,
                            "coverage_ratio_predicted": 0.97,
                            "coverage_ratio_required": 0.95,
                            "expected_data_volume_gbit": 22.0,
                            "recorder_free_gbit": 44.0,
                            "recorder_backlog_gbit": 8.0,
                            "available_downlink_gbit": 36.0,
                            "power_margin_pct": 18.0,
                            "thermal_margin_pct": 16.0,
                        },
                    },
                }
            },
        ),
    ) -> dict[str, object]:
        updated = repo.update_request_candidate(
            request_code,
            candidate_code,
            {
                **to_candidate_meta(payload),
            },
            to_candidate_input(payload),
        )
        if updated is None:
            raise HTTPException(status_code=404, detail=f"request candidate not found: {request_code}/{candidate_code}")
        return updated

    @app.delete(
        "/requests/{request_code}/request-candidates/{candidate_code}",
        tags=["candidate"],
        summary="요청 후보 삭제",
        description=(
            "요청 하위 수행계획 후보를 삭제합니다.\n\n"
            "운영 가이드:\n"
            "- 기준안 후보 삭제 시 후속 기준안 재지정 전략을 함께 고려하세요.\n"
            "- 삭제된 후보의 UI 선택 상태/비교 상태를 클라이언트에서 초기화해야 합니다.\n\n"
            "오류 케이스:\n"
            "- 404: 요청/후보 없음"
        ),
    )
    def delete_request_candidate(request_code: str, candidate_code: str) -> dict[str, object]:
        deleted = repo.delete_request_candidate(request_code, candidate_code)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"request candidate not found: {request_code}/{candidate_code}")
        return {"deleted": True, "request_code": request_code, "candidate_code": candidate_code}

    @app.post(
        "/requests/{request_code}/request-candidates/{candidate_code}/simulate",
        tags=["simulation"],
        summary="후보 저장 실행(시뮬레이션+이력저장)",
        description=(
            "저장된 후보 입력값으로 시뮬레이션을 수행하고 실행 이력을 저장합니다.\n\n"
            "설계 의도:\n"
            "- 화면의 '저장 후 검증 실행'을 API로 분리해 재현 가능한 run history를 남깁니다.\n"
            "- 실행 시점의 입력 버전/트리거 메타를 함께 기록해 추적성을 확보합니다.\n\n"
            "트리거 메타 활용:\n"
            "- 수동 실행: trigger 생략 가능\n"
            "- 추천안 반영 실행: trigger_type/source_code/parameter_name/note 기록 권장"
        ),
    )
    def simulate_request_candidate(
        request_code: str,
        candidate_code: str,
        trigger: CandidateRunTrigger | None = Body(
            default=None,
            examples={
                "manual_run": {
                    "summary": "수동 저장 실행",
                    "value": None,
                },
                "recommendation_apply": {
                    "summary": "추천안 반영 실행",
                    "value": {
                        "trigger_type": "RECOMMENDATION_APPLY",
                        "source_code": "UI_PROPOSAL_CARD",
                        "parameter_name": "max_cloud_pct",
                        "note": "구름 허용치를 35 -> 45로 완화 후 실행",
                    },
                },
            },
        ),
    ) -> dict[str, object]:
        candidate_input = repo.get_request_candidate_input(request_code, candidate_code)
        if candidate_input is None:
            raise HTTPException(status_code=404, detail=f"request candidate not found: {request_code}/{candidate_code}")
        output = repo.simulate_request_candidate_input(request_code, candidate_input, candidate_code)
        if output is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        saved = repo.save_request_candidate_run(
            request_code,
            candidate_code,
            output,
            utc_now(),
            trigger.model_dump() if trigger is not None else None,
        )
        if saved is None:
            raise HTTPException(status_code=404, detail=f"request candidate not found: {request_code}/{candidate_code}")
        return saved

    @app.post(
        "/requests/{request_code}/simulate-candidate-input",
        tags=["simulation"],
        summary="요청 컨텍스트 기반 입력 즉시 시뮬레이션",
        description=(
            "후보를 저장하지 않고 현재 입력값으로 즉시 평가합니다.\n\n"
            "설계 의도:\n"
            "- 폼 입력 변경 시 즉각적인 판정 피드백 제공(저장 전 검토)\n"
            "- 요청 컨텍스트(정책/기존 후보/외부 계산 데이터)를 반영해 현실적인 결과 반환\n\n"
            "사용 패턴:\n"
            "- 신규 초안: `candidate_code` 없이 호출\n"
            "- 기존 후보 편집: `candidate_code` 전달해 기존 컨텍스트 반영"
        ),
    )
    def simulate_request_candidate_input(
        request_code: str,
        payload: SimulationInput = Body(
            ...,
            examples={
                "draft_optical_input": {
                    "summary": "광학 초안 입력 즉시 평가",
                    "value": {
                        "sensor_type": "OPTICAL",
                        "priority_tier": "URGENT",
                        "area_km2": 145.2,
                        "window_hours": 24.0,
                        "cloud_pct": 38.0,
                        "max_cloud_pct": 40.0,
                        "required_off_nadir_deg": 18.0,
                        "max_off_nadir_deg": 35.0,
                        "sun_elevation_deg": 32.0,
                        "min_sun_elevation_deg": 20.0,
                        "coverage_ratio_predicted": 0.92,
                        "coverage_ratio_required": 0.9,
                        "expected_data_volume_gbit": 15.5,
                        "recorder_free_gbit": 28.0,
                        "recorder_backlog_gbit": 5.0,
                        "available_downlink_gbit": 26.0,
                        "power_margin_pct": 21.0,
                        "thermal_margin_pct": 20.0,
                    },
                }
            },
        ),
        candidate_code: str | None = Query(
            default=None,
            description="현재 편집 중인 기존 후보 코드. 전달 시 기존 후보 컨텍스트를 함께 반영합니다.",
        ),
    ) -> dict[str, object]:
        if repo.get_request(request_code) is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        output = repo.simulate_request_candidate_input(request_code, payload.model_dump(), candidate_code)
        if output is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        return output

    @app.post(
        "/simulate",
        response_model=SimulationOutput,
        tags=["simulation"],
        summary="순수 엔진 시뮬레이션",
        description=(
            "요청 컨텍스트 없이 입력값만으로 feasibility 엔진 결과를 계산합니다.\n\n"
            "설계 의도:\n"
            "- 엔진 단위 테스트/파라미터 튜닝/회귀 검증에 사용\n"
            "- DB 상태나 요청/후보 관계에 영향받지 않는 순수 계산 경로 제공"
        ),
    )
    def simulate(
        payload: SimulationInput = Body(
            ...,
            examples={
                "sar_engine_test": {
                    "summary": "SAR 엔진 단일 입력 테스트",
                    "value": {
                        "sensor_type": "SAR",
                        "priority_tier": "PRIORITY",
                        "area_km2": 625.0,
                        "window_hours": 48.0,
                        "predicted_incidence_deg": 28.0,
                        "min_incidence_deg": 25.0,
                        "max_incidence_deg": 40.0,
                        "coverage_ratio_predicted": 0.99,
                        "coverage_ratio_required": 0.95,
                        "expected_data_volume_gbit": 22.0,
                        "recorder_free_gbit": 44.0,
                        "recorder_backlog_gbit": 8.0,
                        "available_downlink_gbit": 36.0,
                        "power_margin_pct": 18.0,
                        "thermal_margin_pct": 16.0,
                    },
                }
            },
        )
    ) -> SimulationOutput:
        return simulate_feasibility(payload)

    return app


app = create_app(DEFAULT_DB_PATH)


def create_app_from_env() -> FastAPI:
    return create_app(Path(os.environ.get("FEASIBILITY_DB_PATH", "./db/feasibility_satti.db")))


def main() -> int:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    host = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_HOST
    port = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_PORT
    reload_enabled = len(sys.argv) > 4 and sys.argv[4] == "--reload"

    os.environ["FEASIBILITY_DB_PATH"] = str(db_path)
    print(f"Serving feasibility demo FastAPI on http://{host}:{port}")
    print(f"Using database: {db_path}")
    if reload_enabled:
        print("Reload mode: enabled")
    uvicorn.run(
        "src.api_server:create_app_from_env",
        factory=True,
        host=host,
        port=port,
        log_level="info",
        reload=reload_enabled,
        reload_dirs=["src"] if reload_enabled else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
