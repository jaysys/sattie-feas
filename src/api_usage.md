# API Usage

이 API 서버는 `FastAPI + Uvicorn` 기반으로 seed 데이터가 들어간 SQLite DB를 조회하고, 요청 하위 후보건을 생성·수정·삭제·검증할 수 있는 데모 서버다.

## 실행

```sh
./src/run_api_server.sh ./db/feasibility_satti.db 127.0.0.1 6003
```

기본 포트는 `6003`이다.

## 엔드포인트

### `GET /`

프론트엔드 대시보드. 요청건을 선택하고, 하위 후보건을 등록/수정/삭제/검증한다.

상단의 요청 개요와 운용 제한은 고객 또는 외부 시스템이 제공한 요청 원본 값으로 보고 읽기 전용으로 표시한다. 실제로 수정 가능한 값은 후보건 입력값이며, 이 값으로 현재 평가와 저장 실행 결과를 관리한다.

예시:

```sh
curl http://127.0.0.1:6003/
```

### `GET /health`

서버 상태 확인.

예시:

```sh
curl http://127.0.0.1:6003/health
```

### `GET /requests`

요청 목록 조회.

`request_code`는 시스템이 생성한 내부 요청코드다. 함께 사람이 읽는 `request_title`, 요청 목적을 담는 `request_description`, 1차 외부 요청 참조인 `external_request_code`, `external_source_system_code`도 포함된다.

예시:

```sh
curl http://127.0.0.1:6003/requests
```

### `POST /requests`

새 내부 요청을 생성한다. 내부 요청코드 `request_code`는 서버가 자동 생성한다. 외부 고객 요청번호가 함께 들어오면 `request_external_ref`에 primary 외부 참조로 저장된다.

현재 프론트의 `새 요청 생성` 화면은 데모용 편의 입력기다. UI에서는 아래 템플릿을 자동 사용한다.

- `customer_org_id = 1`
- `customer_user_id = 1`
- optical 정책이면 optical 센서/상품 기본 템플릿
- SAR 정책이면 SAR 센서/상품 기본 템플릿
- AOI는 입력한 중심점과 면적으로부터 정사각형 bbox/WKT를 생성

즉 API는 일반적인 요청 생성 엔드포인트이고, 현재 화면은 데모 마스터데이터 기준의 얇은 생성 폼이다.

필수 입력:

- 요청 헤더
  - `customer_org_id`
  - `customer_user_id`
  - `service_policy_id`
  - `request_title`
  - `request_description`
  - `requested_start_at`
  - `requested_end_at`
  - `priority_tier` (선택)
    - 미입력 시 `service_policy.priority_tier` 기본값 자동 적용
- AOI
  - `geometry_type`
  - `geometry_wkt`
  - `area_km2`
  - bounding box / centroid
- 제약
  - `coverage_ratio_required` 등
- 센서 옵션 1건 이상
- 상품 옵션 1건 이상

예시:

```json
{
  "customer_org_id": 1,
  "customer_user_id": 1,
  "service_policy_id": 2,
  "request_title": "서해 SAR 신규 감시 요청",
  "request_description": "서해 특정 해역에 대한 신규 SAR 감시 요청입니다.",
  "requested_start_at": "2026-03-12T00:00:00Z",
  "requested_end_at": "2026-03-13T00:00:00Z",
  "emergency_flag": true,
  "repeat_acquisition_flag": false,
  "monitoring_count": 1,
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
    "dominant_axis_deg": 90.0
  },
  "constraint": {
    "min_incidence_deg": 25.0,
    "max_incidence_deg": 40.0,
    "deadline_at": "2026-03-13T00:00:00Z",
    "coverage_ratio_required": 0.9
  },
  "sensor_options": [
    {
      "satellite_id": 2,
      "sensor_id": 2,
      "sensor_mode_id": 2,
      "preference_rank": 1,
      "is_mandatory": true,
      "polarization_code": "HH"
    }
  ],
  "product_options": [
    {
      "product_level_code": "L1C",
      "product_type_code": "SIGMA0",
      "file_format_code": "HDF5",
      "delivery_mode_code": "FTP",
      "ancillary_required_flag": true
    }
  ],
  "external_ref": {
    "source_system_code": "CUSTOMER_PORTAL",
    "external_request_code": "EXT-WESTSEA-NEW-9001",
    "external_request_title": "서해 해역 긴급 SAR 촬영 요청",
    "external_customer_org_name": "Seoul Disaster Analytics Center",
    "external_requester_name": "Kim Mina",
    "is_primary": true,
    "received_at": "2026-03-07T10:20:00Z"
  }
}
```

### `GET /requests/{request_code}`

특정 요청의 집계 리포트 조회.

경로의 `{request_code}`는 기본적으로 내부 요청코드지만, 현재 구현에서는 외부 요청번호가 유일하게 매핑된 경우 외부 요청번호로도 조회할 수 있다.

이 응답의 요청 전체 섹션은 더 이상 seed로 넣어둔 `feasibility_run/run_candidate` 결과를 그대로 쓰지 않는다. 현재 `request_candidate_input` 값들을 공통 시뮬레이터에 태워 동적으로 계산한 결과를 반환한다.

현재 구현에서는 다음이 함께 반영된다.

- request context 기반 정책 검증
- `access_opportunity` 기반 기하 후보 매핑
- `station_contact_window`, `existing_task`, `existing_downlink_booking` 기반 운영 deconflict
- `weather_cell_forecast`, `solar_condition_snapshot`, `terrain_risk_snapshot` 기반 환경 리스크 반영
- `max_attempts` 범위 내 누적 성공확률 계산

따라서 `result.overall_probability`는 best candidate 단일 확률이 아니라 요청 전체 시도 기준 누적확률이다. 응답에는 `first_feasible_attempt_at`, `expected_attempt_count`, `attempt_count_considered`, `max_attempts_considered`도 포함된다.

또한 요청 전체 응답에는 `external_refs`와 `proposal` 객체가 포함된다. `external_refs`는 외부 시스템 요청번호 매핑 목록이고, `proposal`은 정책명, 우선순위, 누적 성공확률, 첫 촬영기회, 예상 촬영기회 소진 수, 대표 후보, SLA 요약, 상위 완화 제안을 함께 제공한다.

`Feasibility Analysis Summary` 표는 계산 결과 중심으로 구성된다. 정책명, 정책상 집계 상한, 반복 품질 하한, 반복 최소 간격, 입사각 일관성 한도, SLA 요약 같은 내부 정책 파생값은 별도 `정책 적용 정보` 섹션에서 보여준다.

`Feasibility Analysis Summary` 표의 주요 필드 해석은 다음 기준을 따른다.

- `정책`, `요청 우선순위`
  - 요청 전체 feasibility를 해석하는 서비스 정책/SLA 기준값
- `누적 성공확률`
  - 단일 후보 확률이 아니라 정책상 집계 상한 범위 안에서 후보/촬영기회를 순차 반영한 요청 전체 누적 성공확률
- `예상 첫 촬영기회`
  - 위성 자동 재시도 시작 시각이 아니라, 현재 후보 집합 기준 첫 유효 촬영기회 시각
- `예상 촬영기회 소진 수`
  - 위성의 자동 재시도 횟수가 아니라, 요청 하위 후보/기회를 순차 검토할 때의 기대 소진 수
- `집계 반영 후보 수`, `정책상 집계 상한`
  - 누적 확률과 기대 소진 수 계산에 실제 반영한 후보 수 / 정책상 최대 반영 수
- `반복 품질 하한`, `품질 반영 시도 수`, `반복 최소 간격`, `입사각 일관성 한도`, `일관성 반영 시도 수`, `간격 충족 시도 수`
  - 반복 촬영 요구를 품질, SAR 입사각 일관성, 재방문 간격 기준으로 단계적으로 좁혀 가는 필드
- `SLA 요약`
  - 정책, 우선순위, 정책상 집계 상한 등 운영 해석의 기준을 요약한 값

후보 테이블에서는 `요청 시간창`과 `촬영기회`를 구분한다.

- `요청 시간창`
  - 고객이 요청한 `requested_start_at ~ requested_end_at`
- `촬영기회`
  - 후보 입력 화면에서 직접 넣은 `opportunity_start_at ~ opportunity_end_at`가 있으면 그 값을 우선 사용한다.
  - 없으면 그 시간창 안에서 계산된 `access_opportunity.access_start_at ~ access_end_at`를 사용한다.

따라서 `촬영기회 미계산`은 고객 요청 시간창은 있지만, 해당 후보에 대해 구체적인 촬영기회 시각을 직접 입력하지도 않았고 pass/access 매핑도 아직 없다는 뜻이다.

후보 입력 화면에서는 `window_hours`와 별도로 `opportunity_start_at`, `opportunity_end_at`를 넣을 수 있다. 화면 입력은 `datetime-local` 형식으로 받지만 저장과 API payload는 UTC ISO 문자열로 변환해 사용한다. 이 두 값이 모두 들어오면 현재 구현은 이를 `후보가 직접 지정한 촬영기회 시각`으로 보고 기하 해석과 첫 시도 시각 표시에 우선 반영한다. 단, 이 경우에도 지상국 contact/downlink는 별도 계산 또는 매핑이 필요하다.

예시:

```sh
curl http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001
curl http://127.0.0.1:6003/requests/REQ-20260307-WESTSEA-SAR-001
```

### `GET /requests/{request_code}/external-refs`

기존 요청에 연결된 외부 요청번호 목록을 조회한다.

예시:

```sh
curl http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/external-refs
```

### `POST /requests/{request_code}/external-refs`

기존 요청에 외부 요청번호를 추가로 연결한다. `source_system_code + external_request_code`는 전체 시스템에서 유니크하며, `is_primary = true`로 저장하면 같은 요청의 기존 primary 외부 참조는 자동 해제된다.

예시:

```json
{
  "source_system_code": "CUSTOMER_PORTAL",
  "external_request_code": "EXT-SEOUL-20260307-9001",
  "external_request_title": "서울 도심 광학 재촬영 요청",
  "external_customer_org_name": "Seoul Disaster Analytics Center",
  "external_requester_name": "Kim Jisoo",
  "is_primary": true,
  "received_at": "2026-03-07T10:15:00Z"
}
```

### `PATCH /requests/{request_code}/external-refs/{request_external_ref_id}`

지정한 외부 요청번호를 해당 요청의 primary 외부 참조로 승격한다.

예시:

```sh
curl -X PATCH http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/external-refs/1 \
  -H 'content-type: application/json' \
  -d '{"is_primary": true}'
```

### `DELETE /requests/{request_code}/external-refs/{request_external_ref_id}`

외부 요청번호 매핑을 삭제한다. primary 외부 참조를 지우면 남아 있는 가장 앞선 참조가 자동으로 새 primary가 된다.

예시:

```sh
curl -X DELETE http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/external-refs/1
```

### `GET /requests/{request_code}/request-candidates`

요청 하위 후보건 목록 조회.

각 후보 항목에는 `latest_*` 저장 실행 결과와 별도로 `current_*` 현재 입력 기준 평가 값이 함께 포함된다.

예시:

```sh
curl http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/request-candidates
```

### `GET /requests/{request_code}/request-candidates/{candidate_code}`

후보건 입력값, 최신 실행 결과, 실행 이력 조회.

초기 seed 상태에서는 후보 입력값만 존재하므로 `latest_run`은 비어 있거나 `null`이고, `runs`도 빈 배열일 수 있다. 실제 실행 이력은 `저장 후 검증 실행` 이후에만 생성된다. 실행 이력이 생성되면 `runs[*].input_version_no`, `runs[*].run_trigger_type`, `runs[*].run_trigger_source_code`, `runs[*].run_trigger_parameter_name`, `runs[*].run_trigger_note`로 입력 버전과 실행 출처를 함께 추적할 수 있다.

예시:

```sh
curl http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/request-candidates/OPT-CAND-001
```

### `POST /requests/{request_code}/request-candidates`

요청 하위 후보건 생성.

`candidate_code`는 서버가 자동 생성한다. 클라이언트는 후보 제목, 설명, 순서, 기준안 여부, 입력값만 보낸다.

예시:

```sh
curl -X POST http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/request-candidates \
  -H 'content-type: application/json' \
  -d '{
    "candidate_title": "신규 비교안",
    "candidate_description": "입력값을 바꿔 확인하는 신규 후보",
    "candidate_status": "DRAFT",
    "candidate_rank": 4,
    "is_baseline": false,
    "input": {
      "sensor_type": "OPTICAL",
      "priority_tier": "STANDARD",
      "area_km2": 400,
      "window_hours": 72,
      "cloud_pct": 15,
      "max_cloud_pct": 20,
      "required_off_nadir_deg": 18,
      "max_off_nadir_deg": 25,
      "predicted_incidence_deg": 30,
      "min_incidence_deg": 25,
      "max_incidence_deg": 40,
      "sun_elevation_deg": 35,
      "min_sun_elevation_deg": 20,
      "coverage_ratio_predicted": 0.98,
      "coverage_ratio_required": 0.95,
      "expected_data_volume_gbit": 12,
      "recorder_free_gbit": 48,
      "recorder_backlog_gbit": 8,
      "available_downlink_gbit": 40,
      "power_margin_pct": 18,
      "thermal_margin_pct": 16
    }
  }'
```

`is_baseline = true`로 저장하면 같은 요청의 다른 후보 기준안은 자동 해제된다. 요청건당 기준안은 1건만 유지된다.

### `PATCH /requests/{request_code}/request-candidates/{candidate_code}`

후보건 수정.

### `DELETE /requests/{request_code}/request-candidates/{candidate_code}`

후보건 삭제.

### `POST /requests/{request_code}/request-candidates/{candidate_code}/simulate`

저장된 후보 입력값을 기준으로 검증을 실행하고 실행 이력을 저장한다.

선택적으로 body에 실행 트리거 메타데이터를 함께 보낼 수 있다.

- `trigger_type`
- `source_code`
- `parameter_name`
- `note`
- `note`

예시:

```sh
curl -X POST http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/request-candidates/OPT-CAND-001/simulate
```

### `POST /requests/{request_code}/simulate-candidate-input`

현재 요청 context를 붙여 후보 입력값을 즉시 평가한다.

이 엔드포인트는 단순 `/simulate`와 달리 다음을 함께 검증한다.

- 서비스 정책 최소 주문 면적
- 주문 cutoff
- 요청/후보 우선순위 적합성
- 요청 센서 옵션 적합성
- 요청 상품 레벨 / 제품 유형 / 파일 형식 적합성
- SAR 편파 호환성

저장된 후보를 수정 중이면 `candidate_code` query parameter를 함께 보내 access opportunity 기반 기하값을 현재 평가에 반영할 수 있다. 여기의 `candidate_code`는 사용자가 입력하는 값이 아니라 서버가 생성한 내부 후보코드다.

응답 recommendation에는 후보 단건 기준 `expected_probability_gain`이 포함될 수 있다. 이 값은 동일 request context에서 추천값을 적용했을 때 `p_total_candidate`가 얼마나 증가하는지를 추정한 값이다. 요청 전체 응답의 `proposal.relaxation_options`에도 같은 필드가 들어가며, 이 경우 값은 요청 전체 누적 성공확률 증가량을 의미한다.

화면의 `완화 제안` 카드에 표시되는 값은 아래처럼 해석한다.

- `current`
  - 현재 후보 입력값 또는 현재 access 상태값이다.
  - 예: 현재 backlog, 현재 downlink 가용량, 현재 access 시각/coverage
- `recommended`
  - 엔진이 계산해 만든 완화안이다.
  - 예: backlog 목표값, downlink 확보 목표값, 다른 pass 사용 권고
- `gain`
  - 해당 완화안을 적용했을 때의 예상 확률 증가량이다.
  - 후보 단건 recommendation에서는 `p_total_candidate` 증가량, 요청 전체 `proposal.relaxation_options`에서는 요청 전체 누적 성공확률 증가량을 뜻한다.

`proposal.expected_attempt_count`는 위성이 같은 촬영을 자동으로 여러 번 재시도한다는 뜻이 아니다. 이 값은 요청 하위 후보 또는 촬영기회를 순서대로 검토한다고 볼 때 평균적으로 몇 개의 촬영기회를 소진하게 되는지를 나타내는 기대값이다. `proposal.attempt_count_considered`는 그 계산에 실제 반영한 후보/기회 수이며, `max_attempts_considered`는 정책상 반영 가능한 최대 집계 상한이다.

예시:

```sh
curl -X POST http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/simulate-candidate-input \
  -H 'content-type: application/json' \
  -d '{
    "sensor_type": "OPTICAL",
    "priority_tier": "STANDARD",
    "area_km2": 400,
    "window_hours": 168,
    "cloud_pct": 18,
    "max_cloud_pct": 20,
    "required_off_nadir_deg": 18.5,
    "max_off_nadir_deg": 25,
    "predicted_incidence_deg": 30,
    "min_incidence_deg": 25,
    "max_incidence_deg": 40,
    "sun_elevation_deg": 44,
    "min_sun_elevation_deg": 20,
    "coverage_ratio_predicted": 0.98,
    "coverage_ratio_required": 0.95,
    "expected_data_volume_gbit": 14,
    "recorder_free_gbit": 48,
    "recorder_backlog_gbit": 12,
    "available_downlink_gbit": 42,
    "power_margin_pct": 19,
    "thermal_margin_pct": 16
  }'
```

저장된 후보를 access opportunity와 함께 평가하는 예시:

```sh
curl -X POST 'http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/simulate-candidate-input?candidate_code=OPT-CAND-002' \
  -H 'content-type: application/json' \
  -d '{
    "sensor_type": "OPTICAL",
    "priority_tier": "STANDARD",
    "area_km2": 400,
    "window_hours": 168,
    "cloud_pct": 12,
    "max_cloud_pct": 20,
    "required_off_nadir_deg": 27.4,
    "max_off_nadir_deg": 25,
    "predicted_incidence_deg": 30,
    "min_incidence_deg": 25,
    "max_incidence_deg": 40,
    "sun_elevation_deg": 46,
    "min_sun_elevation_deg": 20,
    "coverage_ratio_predicted": 0.93,
    "coverage_ratio_required": 0.95,
    "expected_data_volume_gbit": 14,
    "recorder_free_gbit": 48,
    "recorder_backlog_gbit": 12,
    "available_downlink_gbit": 42,
    "power_margin_pct": 19,
    "thermal_margin_pct": 16
  }'
```

### `POST /simulate`

입력 파라미터를 받아 synthetic feasibility 판정을 수행한다.

예시:

```sh
curl -X POST http://127.0.0.1:6003/simulate \
  -H 'content-type: application/json' \
  -d '{
    "sensor_type": "OPTICAL",
    "priority_tier": "STANDARD",
    "area_km2": 400,
    "window_hours": 168,
    "cloud_pct": 34,
    "max_cloud_pct": 20,
    "required_off_nadir_deg": 20.5,
    "max_off_nadir_deg": 25,
    "predicted_incidence_deg": 30,
    "min_incidence_deg": 25,
    "max_incidence_deg": 40,
    "sun_elevation_deg": 42,
    "min_sun_elevation_deg": 20,
    "coverage_ratio_predicted": 0.97,
    "coverage_ratio_required": 0.95,
    "expected_data_volume_gbit": 14,
    "recorder_free_gbit": 48,
    "recorder_backlog_gbit": 10,
    "available_downlink_gbit": 40,
    "power_margin_pct": 19,
    "thermal_margin_pct": 15
  }'
```

### `GET /docs`

Swagger UI 문서.

예시:

```sh
curl http://127.0.0.1:6003/docs
```

### `GET /redoc`

ReDoc 문서.

예시:

```sh
curl http://127.0.0.1:6003/redoc
```

## 응답 구조

`/requests/{request_code}`는 `repository.py`의 `get_request_report()` 결과를 그대로 반환한다.

주요 키:

- `request`
- `aoi`
- `constraint`
- `sensor_options`
- `product_options`
- `request_candidates`
- `run`
- `input_bundle`
- `contact_windows`
- `existing_tasks`
- `downlink_bookings`
- `candidates`
- `candidate_checks`
- `candidate_rejection_reasons`
- `candidate_probabilities`
- `result`
- `recommendations`
- `audit_events`

`request` 객체에는 시스템 내부 요청코드인 `request_code`, `request_title`, `request_description`, `external_request_code`, `external_source_system_code`가 함께 들어 있다.

`external_refs`에는 외부 요청번호 매핑 목록이 들어 있다.

`candidates`, `candidate_checks`, `candidate_rejection_reasons`, `candidate_probabilities`, `result`, `recommendations`는 현재 후보 입력값 기준 동적 계산 결과다.

특히 `candidate_probabilities`에 들어 있는 값은 모두 계산값이다.

- `p_geo`
- `p_env`
- `p_resource`
- `p_downlink`
- `p_policy`
- `p_conflict_adjusted`
- `p_total_candidate`

이 값들은 원본 입력이 아니라, 후보 입력값과 외부 snapshot, 정책 조건을 바탕으로 엔진이 산출한 중간 확률과 최종 확률이다.

후보 상세 응답에는 다음이 들어 있다.

- `candidate`
- `input`
- `current_evaluation`
- `latest_run`
- `latest_reasons`
- `latest_recommendations`
- `runs`

초기 seed 기준으로는:

- `candidate`, `input`은 항상 존재
- `latest_run`은 비어 있거나 `null`
- `latest_reasons`, `latest_recommendations`, `runs`는 빈 배열일 수 있음

`/simulate` 응답 주요 키:

- `candidate_status`
- `final_verdict`
- `summary_message`
- `dominant_risk_code`
- `probabilities`
- `checks`
- `reasons`
- `recommendations`

## 프론트엔드 후보 관리

루트 화면 `/`에는 요청 2건이 표시되며, overview 설명은 `request_description`을 그대로 사용한다.

- `서울 AOI 광학 촬영 요청건`
- `서해 AOI SAR 촬영 요청건`

같은 화면에서 `request_candidate`와 `request_candidate_input`을 편집하고, `POST /requests/{request_code}/simulate-candidate-input`로 현재 입력 기준 평가를 갱신한 뒤, `POST /requests/{request_code}/request-candidates/{candidate_code}/simulate`를 호출해 후보별 최신 저장 실행 결과를 갱신한다. 새 후보 생성 시 `candidate_code`는 서버가 자동 발번하며, 화면에서는 읽기 전용으로만 표시된다. 외부 고객 요청번호는 `POST /requests/{request_code}/external-refs`로 내부 요청에 추가 연결한다.

요청 전체 결과 카드와 후보별 검증 결과 섹션도 같은 시뮬레이터를 사용한다. 즉 초기 seed 입력값만으로도 화면에는 현재 입력 기준 평가가 보이며, `저장 후 검증 실행`을 수행하면 후보 전용 최신 실행 이력이 별도로 저장된다. 후보 입력 폼 값을 바꾸면 `현재 입력 기준 평가`는 자동으로 다시 계산되고, 후보 목록과 후보 상세에서는 `현재 평가`와 `최신 저장 실행 결과`를 함께 볼 수 있다. 현재 입력 기준 평가에는 정책 검증 결과가 함께 반영되므로, 요청과 맞지 않는 센서/상품/우선순위 입력은 `POLICY` stage reason으로 표출된다. SAR 요청에서는 편파 호환성도 같은 POLICY stage에서 검증되고, 요청 전체 결과에는 `required_attempt_count`, `repeat_requirement_met`, `repeat_quality_threshold`, `repeat_quality_attempt_count`, `repeat_spacing_hours_required`, `repeat_spacing_met`, `repeat_incidence_tolerance_deg`, `repeat_incidence_consistent_count`, `repeat_incidence_met`가 포함되어 반복 촬영 요구, 반복 카운트 품질 하한, 재방문 간격 충족 여부, 기준 후보 대비 입사각 일관성 한도를 함께 확인할 수 있다. `REPEAT_PASS_INCIDENCE_INCONSISTENT`가 걸리면 proposal 완화안에는 `incidence_window`, `candidate_split`이 함께 제안된다. `incidence_window` 카드의 `기존 후보 반영 후 실행` 버튼은 해당 후보 입력값을 즉시 PATCH한 뒤 바로 검증 실행하고, `candidate_split` 카드의 `분리 후보 생성` 버튼은 새 `DRAFT` 후보를 만들고 즉시 검증 실행한다. 광학 요청에서는 `shadow_risk_score`, `local_capture_time_hhmm`, `local_noon_distance_min`, `local_time_window_distance_min`, `dominant_axis_deg`가 계산되어 sun azimuth / shadow / AOI 위도 / AOI 방향성 / 계절 / 현지시각 선호창 영향을 현재 평가와 요청 전체 결과에서 함께 볼 수 있다. 요청 개요에는 원본 `AOI 방향`도 함께 표시된다. 후보 상세 recommendation에는 적용 시 예상되는 `expected_probability_gain`이 함께 표시된다.
