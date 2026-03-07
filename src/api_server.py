from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
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
    candidate_title: str
    candidate_description: str
    candidate_status: str = "READY"
    candidate_rank: int = Field(..., ge=1)
    is_baseline: bool = False
    input: SimulationInput


class RequestCandidateUpdate(BaseModel):
    candidate_title: str
    candidate_description: str
    candidate_status: str = "READY"
    candidate_rank: int = Field(..., ge=1)
    is_baseline: bool = False
    input: SimulationInput


class CandidateRunTrigger(BaseModel):
    trigger_type: str | None = None
    source_code: str | None = None
    parameter_name: str | None = None
    note: str | None = None


class RequestExternalRefCreate(BaseModel):
    source_system_code: str
    external_request_code: str
    external_request_title: str | None = None
    external_customer_org_name: str | None = None
    external_requester_name: str | None = None
    is_primary: bool = True
    received_at: str | None = None


class RequestExternalRefUpdate(BaseModel):
    is_primary: bool = True


class RequestAoiCreate(BaseModel):
    geometry_type: str
    geometry_wkt: str
    srid: int = 4326
    area_km2: float
    bbox_min_lon: float
    bbox_min_lat: float
    bbox_max_lon: float
    bbox_max_lat: float
    centroid_lon: float
    centroid_lat: float
    dominant_axis_deg: float | None = None


class RequestConstraintCreate(BaseModel):
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
    satellite_id: int
    sensor_id: int
    sensor_mode_id: int
    preference_rank: int = Field(..., ge=1)
    is_mandatory: bool = False
    polarization_code: str | None = None


class RequestProductOptionCreate(BaseModel):
    product_level_code: str
    product_type_code: str
    file_format_code: str
    delivery_mode_code: str
    ancillary_required_flag: bool = False


class RequestCreate(BaseModel):
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
    monitoring_count: int = Field(1, ge=1)
    aoi: RequestAoiCreate
    constraint: RequestConstraintCreate
    sensor_options: list[RequestSensorOptionCreate]
    product_options: list[RequestProductOptionCreate]
    external_ref: RequestExternalRefCreate | None = None


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
        title="Feasibility Demo API",
        version="1.0.0",
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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/requests")
    def list_requests() -> dict[str, list[dict[str, object]]]:
        return {"items": repo.list_requests()}

    @app.post("/requests")
    def create_request(payload: RequestCreate) -> dict[str, object]:
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

    @app.get("/requests/{request_code}")
    def get_request(request_code: str) -> dict[str, object]:
        payload = repo.get_request_report(request_code)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        return payload

    @app.get("/requests/{request_code}/external-refs")
    def list_request_external_refs(request_code: str) -> dict[str, list[dict[str, object]]]:
        if repo.get_request(request_code) is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        return {"items": repo.list_request_external_refs(request_code)}

    @app.post("/requests/{request_code}/external-refs")
    def create_request_external_ref(request_code: str, payload: RequestExternalRefCreate) -> dict[str, object]:
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

    @app.patch("/requests/{request_code}/external-refs/{request_external_ref_id}")
    def update_request_external_ref(
        request_code: str,
        request_external_ref_id: int,
        payload: RequestExternalRefUpdate,
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

    @app.delete("/requests/{request_code}/external-refs/{request_external_ref_id}")
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

    @app.get("/requests/{request_code}/request-candidates")
    def list_request_candidates(request_code: str) -> dict[str, list[dict[str, object]]]:
        if repo.get_request(request_code) is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        return {"items": repo.list_request_candidates(request_code)}

    @app.get("/requests/{request_code}/request-candidates/{candidate_code}")
    def get_request_candidate(request_code: str, candidate_code: str) -> dict[str, object]:
        payload = repo.get_request_candidate_report(request_code, candidate_code)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"request candidate not found: {request_code}/{candidate_code}")
        return payload

    @app.post("/requests/{request_code}/request-candidates")
    def create_request_candidate(request_code: str, payload: RequestCandidateCreate) -> dict[str, object]:
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

    @app.patch("/requests/{request_code}/request-candidates/{candidate_code}")
    def update_request_candidate(request_code: str, candidate_code: str, payload: RequestCandidateUpdate) -> dict[str, object]:
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

    @app.delete("/requests/{request_code}/request-candidates/{candidate_code}")
    def delete_request_candidate(request_code: str, candidate_code: str) -> dict[str, object]:
        deleted = repo.delete_request_candidate(request_code, candidate_code)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"request candidate not found: {request_code}/{candidate_code}")
        return {"deleted": True, "request_code": request_code, "candidate_code": candidate_code}

    @app.post("/requests/{request_code}/request-candidates/{candidate_code}/simulate")
    def simulate_request_candidate(
        request_code: str,
        candidate_code: str,
        trigger: CandidateRunTrigger | None = None,
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

    @app.post("/requests/{request_code}/simulate-candidate-input")
    def simulate_request_candidate_input(request_code: str, payload: SimulationInput, candidate_code: str | None = None) -> dict[str, object]:
        if repo.get_request(request_code) is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        output = repo.simulate_request_candidate_input(request_code, payload.model_dump(), candidate_code)
        if output is None:
            raise HTTPException(status_code=404, detail=f"request not found: {request_code}")
        return output

    @app.post("/simulate", response_model=SimulationOutput)
    def simulate(payload: SimulationInput) -> SimulationOutput:
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
