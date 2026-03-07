# Repository Usage

이 문서는 `sqlite3` 기반 feasibility demo DB를 API 서버에서 바로 사용할 수 있도록 만든 repository 모듈 사용법을 설명한다.

## 파일

- `src/repository.py`
- `src/repository_example.py`

## 목적

`FeasibilityRepository`는 다음을 바로 제공한다.

- 요청 목록 조회
- 요청 상세 조회
- 내부 요청 신규 생성
- 외부 요청번호 매핑 조회
- 최신 feasibility run 조회
- 후보 촬영기회와 탈락 사유 조회
- 자원/downlink 체크 조회
- 확률 분해 조회
- 최종 결과와 추천안 조회
- API 응답용 집계 객체 생성

즉, 웹 API에서는 개별 SQL을 직접 흩뿌리기보다 repository 메서드를 호출해 JSON 직렬화 가능한 딕셔너리를 바로 받아 쓰는 구조로 사용할 수 있다.

## 주요 메서드

- `list_requests()`
- `get_request(request_code)`
- `create_request(request_data, request_aoi, request_constraint, request_sensor_options, request_product_options, external_ref=None)`
- `list_request_external_refs(request_code)`
- `create_request_external_ref(request_code, external_ref)`
- `set_request_external_ref_primary(request_code, request_external_ref_id)`
- `delete_request_external_ref(request_code, request_external_ref_id)`
- `get_request_aoi(request_code)`
- `get_request_constraint(request_code)`
- `list_request_sensor_options(request_code)`
- `list_request_product_options(request_code)`
- `get_latest_run(request_code)`
- `get_run_input_bundle(run_id)`
- `list_candidates(run_id)`
- `list_candidate_rejection_reasons(run_id)`
- `list_candidate_checks(run_id)`
- `list_candidate_probabilities(run_id)`
- `get_result(run_id)`
- `list_recommendations(run_id)`
- `get_request_report(request_code)`

## API 서버에서 쓰는 방식 예시

```python
from src.repository import FeasibilityRepository

repo = FeasibilityRepository("./db/feasibility_satti.db")
payload = repo.get_request_report("REQ-20260307-WESTSEA-SAR-001")
```

위 `payload`는 바로 JSON 응답 바디로 내려줄 수 있는 구조다.

## 예제 실행

광학 요청 예제:

```sh
python3 ./src/repository_example.py ./db/feasibility_satti.db REQ-20260307-SEOUL-001
```

SAR 요청 예제:

```sh
python3 ./src/repository_example.py ./db/feasibility_satti.db REQ-20260307-WESTSEA-SAR-001
```

## 집계 응답 구조

`get_request_report()`는 아래 키를 포함한다.

- `request`
- `external_refs`
- `aoi`
- `constraint`
- `sensor_options`
- `product_options`
- `run`
- `proposal`
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

중요한 점은 `get_request_report()`의 요청 전체 결과가 현재 `request_candidate_input`를 공통 시뮬레이터에 태운 동적 집계라는 것이다. 즉 `candidates`, `candidate_checks`, `candidate_rejection_reasons`, `candidate_probabilities`, `result`, `recommendations`는 seed 결과를 읽는 것이 아니라 현재 입력값에서 다시 계산된다.

현재 구현에서는 여기에 다음 레이어가 추가로 들어간다.

- request context 정책 검증
- `access_opportunity` 기반 pass 매핑과 `max_attempts` 기준 누적 성공확률 계산
- `station_contact_window`, `existing_task`, `existing_downlink_booking` 기반 운영 deconflict
- `weather_cell_forecast`, `solar_condition_snapshot`, `terrain_risk_snapshot` 기반 환경 리스크 반영

따라서 `result.overall_probability`는 대표 후보 1건의 확률이 아니라 요청 전체 시도 기준 누적확률이고, `result.first_feasible_attempt_at`, `result.expected_attempt_count`, `result.attempt_count_considered`, `result.max_attempts_considered`도 함께 제공된다. 반복 촬영 요청이면 `result.required_attempt_count`, `result.repeat_requirement_met`, `result.repeat_quality_threshold`, `result.repeat_spacing_hours_required`, `result.repeat_incidence_tolerance_deg`, `result.repeat_incidence_consistent_count`도 함께 계산된다. 추가로 `proposal` 객체가 정책/SLA/완화 제안 요약을 제공한다.

## 설계 의도

이 repository는 `request -> request_candidate -> current input evaluation` 흐름과, 별도의 `request_candidate -> saved run history` 흐름을 함께 유지한다. 그래서 API 서버에서 다음 화면을 바로 만들 수 있다.

- 요청 상세 화면
- optical/SAR 후보 비교 화면
- 탈락 사유 감사 화면
- recommendation 제안 화면
- 입력 snapshot 추적 화면
- 후보건 CRUD 및 현재 평가/저장 실행 결과 비교 화면

## `request_title`

`feasibility_request`의 `request_code`는 시스템 내부 요청코드다. 외부 시스템이 보낸 요청번호는 `request_external_ref`로 분리해 관리한다. `request_title`은 사람이 읽는 표시명이다.

- `list_requests()`는 `request_title`을 함께 반환한다.
- `get_request(request_code)`도 `request_title`과 1차 외부 요청참조(`external_request_code`, `external_source_system_code`)를 포함한다.
- `create_request_external_ref(request_code, external_ref)`는 기존 내부 요청에 외부 요청번호를 연결한다. `is_primary = true`로 저장하면 같은 요청의 기존 primary 외부 참조는 자동 해제된다.
- `set_request_external_ref_primary(request_code, request_external_ref_id)`는 기존 연결 중 하나를 primary 외부 참조로 승격한다.
- `delete_request_external_ref(request_code, request_external_ref_id)`는 외부 요청번호 매핑을 삭제한다. primary를 삭제하면 남은 참조 중 가장 앞선 항목이 자동 승격된다.

## `request_description`

`feasibility_request`에는 요청 목적과 기대 산출을 설명하는 `request_description`도 포함된다.

- `list_requests()`는 `request_description`을 함께 반환한다.
- `get_request(request_code)`도 `request_description`을 포함한다.
- 프론트엔드 요청 overview는 이 값을 설명 영역에 그대로 표시한다.

## 요청 원본값과 후보 입력값의 역할

`feasibility_request`, `request_aoi`, `request_constraint`는 고객 또는 외부 시스템이 준 원본 요청값으로 본다. 프론트엔드에서는 이 값들을 읽기 전용 요청 개요로 표시한다. 현재 `request_aoi`에는 `dominant_axis_deg`도 포함되며, 이 값은 광학 shadow risk 계산에서 AOI 방향성 보정에 사용되고, 요청 개요의 `AOI 방향` 항목으로도 표시된다.

반면 `request_candidate`와 `request_candidate_input`은 운영자가 가능성을 비교하기 위해 바꾸어 보는 내부 시뮬레이션 입력 세트다. 따라서 수정 가능한 값은 후보 입력값이며, 요청 전체 결과와 후보 현재 평가는 모두 이 입력값을 공통 시뮬레이터에 태워 계산한다.

## `request_candidate`

후보건은 요청 하위의 가상 가능성 판정 입력 세트다.

중요한 점은 후보건 seed가 초기 입력값만 가진다는 것이다. 초기 DB 생성 직후에는 `request_candidate_run*` 테이블이 비어 있으므로, 후보 상세의 `latest_run`은 비어 있거나 `null`이고 실행 이력도 없다. 실제 후보별 결과 저장은 `save_request_candidate_run(...)`이 호출될 때만 발생한다. 또한 `request_candidate_run`에는 `input_version_no`, `run_trigger_type`, `run_trigger_source_code`, `run_trigger_parameter_name`, `run_trigger_note`를 함께 저장할 수 있으므로, 실행 이력에서 어떤 입력 버전으로 저장됐는지와 수동 저장 실행인지, 추천안 반영 실행인지, 분리 후보 생성 실행인지 구분할 수 있다.

`request_candidate.is_baseline`는 실제 비교 기준축이다. 요청건당 기준안은 1건만 유지되며, 새 후보를 기준안으로 저장하면 같은 요청의 기존 기준안은 자동 해제된다. 기준안이 삭제되면 rank가 가장 앞선 후보가 자동으로 새 기준안이 된다. `candidate_code`는 사용자가 입력하지 않고 `create_request_candidate()`가 센서 유형과 요청별 순번을 기준으로 자동 생성한다.

또한 `list_request_candidates()`는 각 후보에 대해 `current_*` 필드로 현재 입력 기준 동적 평가 결과를 함께 반환하고, `get_request_candidate_report()`는 `current_evaluation`을 포함한다.

- `list_request_candidates(request_code)`
- `get_request_candidate_report(request_code, candidate_code)`
- `simulate_request_candidate_input(request_code, candidate_input)`
- `simulate_request_candidate_input(request_code, candidate_input, candidate_code=None)`
- `create_request_candidate(request_code, candidate, candidate_input)`
- `update_request_candidate(request_code, candidate_code, candidate, candidate_input)`
- `delete_request_candidate(request_code, candidate_code)`
- `save_request_candidate_run(request_code, candidate_code, output, simulated_at)`

이 메서드들로 후보건 입력값과 최신 검증 이력을 관리한다.

요청 전체 결과에서는 `baseline_candidate_code`, `baseline_candidate_title`이 별도로 계산되며, 반복 촬영의 입사각 일관성 비교와 request-level proposal 정렬도 기준안을 우선 참조한다.

`simulate_request_candidate_input()`은 request context를 함께 읽어 다음 정책 검증도 반영한다.

- 최소 주문 면적
- 주문 cutoff
- 요청/후보 우선순위 적합성
- 요청 센서 옵션 적합성
- 요청 상품 레벨 / 제품 유형 / 파일 형식 적합성

따라서 현재 UI의 `current_evaluation`은 pure simulator 결과가 아니라 `request context + simulator` 결과다. SAR 요청에서는 `request_sensor_option.polarization_code`와 `sensor_mode.supported_polarizations` 비교도 여기에 포함된다.

저장된 후보를 평가할 때 `candidate_code`를 넘기면 `access_opportunity` 매핑도 함께 적용된다. 이 경우 후보 입력 폼에 들어 있는 각도/커버리지 값보다 access 기반 값이 우선한다. 후보 단건 recommendation에는 `expected_probability_gain`이 계산되어 완화 전후 확률 차이를 확인할 수 있다. 요청 전체 `proposal.relaxation_options`에도 같은 필드가 들어가며, 이 값은 요청 전체 누적 성공확률이 얼마나 증가하는지를 뜻한다. SAR 반복 촬영에서 `REPEAT_PASS_INCIDENCE_INCONSISTENT`가 dominant risk가 되면 request-level proposal에는 `incidence_window`, `candidate_split` 완화안이 우선 제안된다. 프론트에서는 `incidence_window` 카드로 해당 후보 입력값을 즉시 갱신하고 검증 실행할 수 있고, `candidate_split` 카드로는 새 분리 후보를 생성해 바로 검증 실행할 수 있다.
