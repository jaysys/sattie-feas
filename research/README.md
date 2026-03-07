# Feasibility Demo Environment

이 저장소는 위성 촬영 feasibility 판정용 SQLite 데모 환경이다.

핵심 구성:

- SQLite 스키마: `bootstrap/schema.sql`
- Seed 데이터: `bootstrap/seed.sql`
- Repository 코드: `src/repository.py`
- FastAPI 기반 API 서버: `src/api_server.py`
- 프론트엔드 화면: `src/static/index.html`, `src/static/styles.css`, `src/static/app.js`
- Python 의존성: `requirements.txt`
- 테스트 시나리오: `src/test_scenarios.md`

## One-Shot Scripts

루트 one-shot 스크립트 4개가 환경 준비, 기동, 종료, 복원 검증을 담당한다.

초기 스키마, seed 데이터, DB 초기화 스크립트, 시나리오 SQL은 `bootstrap/` 폴더에 분리해 관리한다. 실제 SQLite DB 파일과 `.bak` 백업은 `db/` 폴더에서 관리한다. 운영 코드, 초기화 자산, 실행 산출물을 분리하기 위한 구조다.

### 1. 환경 준비

```sh
./one-shot-setup.sh
```

옵션:

```sh
./one-shot-setup.sh --force
./one-shot-setup.sh --no-backup
```

수행 내용:

- `venv` 생성 또는 재사용
- `requirements.txt` 기준 Python 패키지 설치
- 실행 스크립트 권한 부여
- `db/feasibility_satti.db`가 없으면 새로 생성
- `db/feasibility_satti.db`가 있으면 기본적으로 타임스탬프 `.bak` 백업 후 재생성
- Python 컴파일 검사
- 광학/SAR 시나리오 검사
- 요청 하위 후보건 초기 실행 이력 비어 있음 검사
- repository smoke test

### 2. 서버 기동

```sh
./one-shot-startup.sh
```

기본값:

- host: `127.0.0.1`
- port: `6003`
- reload: `on`

옵션:

```sh
./one-shot-startup.sh --no-reload
```

생성 파일:

- PID: `.runtime/api_server.pid`
- 로그: `.runtime/api_server.log`

### 3. 서버 종료

```sh
./one-shot-stop.sh
```

### 4. DB 삭제 후 복원 스모크 테스트

```sh
./one-shot-reset-and-verify.sh
```

수행 내용:

- 기존 managed 서버 정리
- `db/feasibility_satti.db` 삭제
- `one-shot-startup.sh`로 DB 자동 복원 및 서버 기동
- `/health` 확인
- 요청/후보 시드 복원 확인
- managed 서버 종료

## API

기본 서버 주소:

```text
http://127.0.0.1:6003
```

엔드포인트:

- `GET /`
- `GET /health`
- `GET /requests`
- `GET /requests/{request_code}`
- `GET /requests/{request_code}/request-candidates`
- `GET /requests/{request_code}/request-candidates/{candidate_code}`
- `POST /requests/{request_code}/request-candidates`
- `PATCH /requests/{request_code}/request-candidates/{candidate_code}`
- `DELETE /requests/{request_code}/request-candidates/{candidate_code}`
- `POST /requests/{request_code}/request-candidates/{candidate_code}/simulate`
- `POST /simulate`
- `GET /docs`
- `GET /redoc`

자세한 예시는 [src/api_usage.md](/Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study/src/api_usage.md)에 정리돼 있다.

## Frontend

루트 화면 주소:

```text
http://127.0.0.1:6003/
```

화면에는 요청건 2개가 표시되고, 각 요청 아래에서 후보건을 DB 기반으로 관리한다.

- `서울 AOI 광학 촬영 요청건`
- `서해 AOI SAR 촬영 요청건`

같은 화면에서 다음을 수행할 수 있다.

- 현재 후보 입력값 기준 요청 전체 feasibility 결과 확인
- 요청 하위 후보건 목록 조회
- 후보건 신규/수정/삭제
- 후보 입력값 저장
- 저장된 후보건 기준 검증 실행
- 후보별 현재 입력 기준 평가와 최신 저장 실행 결과 비교
- 후보별 사유/권고 확인

요청 표시명은 `feasibility_request.request_title`에서 가져오고, 요청 설명은 `feasibility_request.request_description`에서 가져온다. `feasibility_request`, `request_aoi`, `request_constraint`는 고객 또는 외부 시스템이 준 원본 요청값으로 보고 화면에서 읽기 전용으로 표시한다. 후보건은 `request_candidate`와 `request_candidate_input`에서 관리한다. 후보건 seed는 입력값만 포함하며, 초기 상태에서는 `latest_run`이 비어 있다. 요청 전체 결과 섹션은 현재 후보 입력값들을 공통 시뮬레이터에 태운 동적 계산 결과를 사용한다. 후보별 실행 결과는 `저장 후 검증 실행` 시 `request_candidate_run*` 테이블에 저장된다. `request_candidate.is_baseline`는 요청건당 1건만 유지되는 실제 기준축이며, 반복 입사각 비교와 request-level proposal 정렬에도 반영된다.

기존 작업 DB를 재생성 없이 유지하면서 새 컬럼을 추가해야 할 때는 `./bootstrap/migrate_db_schema.sh ./db/feasibility_satti.db`를 사용한다. 현재 additive migration 대상에는 `request_aoi.dominant_axis_deg`, `request_candidate_run.input_version_no`, `request_candidate_run.run_trigger_*`가 포함된다.

현재 입력 기준 평가에는 `service_policy`, `request_sensor_option`, `request_product_option` 기반 정책 검증이 포함된다. 따라서 요청과 맞지 않는 센서 유형, 최소 주문 면적 미달, 상품 형식 불일치, 주문 cutoff 위반은 `POLICY` stage reason으로 표시된다. SAR 요청에서는 `polarization_code`와 `supported_polarizations`를 비교해 `POLARIZATION_UNSUPPORTED`도 같은 POLICY stage에서 검증한다.

추가로 `access_opportunity` 기반 기하 매핑, `max_attempts` 기준 누적 성공확률 계산, `station_contact_window / existing_task / existing_downlink_booking` 기반 deconflict, `weather_cell_forecast / solar_condition_snapshot / terrain_risk_snapshot` 기반 환경 리스크 반영, `proposal` 산출물이 반영됐다. 따라서 요청 전체 `overall_probability`는 대표 후보 1건의 확률이 아니라 시도 순서 기준 누적확률이며, `first_feasible_attempt_at`, `expected_attempt_count`, `required_attempt_count`, `repeat_requirement_met`, `repeat_quality_threshold`, `repeat_spacing_hours_required`, `repeat_spacing_met`, `repeat_incidence_tolerance_deg`, `repeat_incidence_consistent_count`, `proposal`을 함께 해석해야 한다. baseline 후보라도 contact window booking, 기존 task 충돌, terrain risk, repeat-pass 요구 미충족, repeat spacing 미충족, 입사각 일관성 부족 때문에 `CONDITIONALLY_FEASIBLE` 또는 `NOT_FEASIBLE`가 될 수 있다. `REPEAT_PASS_INCIDENCE_INCONSISTENT`가 걸리면 proposal에는 `incidence_window`, `candidate_split` 완화안이 추가되고, 프론트에서 `incidence_window`는 해당 후보에 즉시 반영 후 검증 실행할 수 있고, `candidate_split`은 새 분리 후보를 생성해 즉시 검증 실행할 수 있다. 이 실행은 `request_candidate_run.input_version_no`, `request_candidate_run.run_trigger_*`로 저장되어 후보 상세의 `실행 이력`에서 추적할 수 있고, UI에서 `전체 이력` / `추천안 실행만` 필터로 나눠볼 수 있다. 광학은 `sun_elevation + sun_azimuth + AOI 위도 + AOI 방향성 + 월 + 현지시각 편차` 조합으로 `shadow_risk_score`를 계산하고, `preferred_local_time_start/end`와 비교한 `LOCAL_TIME_WINDOW_MISALIGNED`를 평가한다. 요청 개요에는 원본 `AOI 방향`도 표시된다. proposal 완화안에는 요청 전체 누적 성공확률 기준 `expected_probability_gain`이 포함된다.

여기서 `expected_attempt_count`는 위성이 같은 촬영을 자동으로 여러 번 재시도한다는 뜻이 아니라, 요청 하위 후보/촬영기회를 순서대로 검토한다고 볼 때 평균적으로 몇 개의 촬영기회를 소진하게 되는지를 나타내는 기대값이다. `attempt_count_considered / max_attempts_considered`는 누적 성공확률과 집계 해석에 실제 반영한 기회 수와 정책상 최대 집계 상한을 뜻한다.

화면은 `고객 요청 정보/제한`, `정책 적용 정보`, `Feasibility Analysis Summary`를 분리해서 보여준다. `정책 적용 정보`에는 정책명, 정책상 집계 상한, 반복 품질 하한, 반복 최소 간격, 입사각 일관성 한도, SLA 요약 같은 내부 정책 파생값이 들어간다. `Feasibility Analysis Summary`는 누적 성공확률, 예상 첫 촬영기회, 예상 촬영기회 소진 수, 집계 반영 후보 수, 반복 요구 충족 여부처럼 요청 전체 후보 집합을 계산한 결과 중심으로 구성된다.

또한 요청 식별자는 내부/외부를 분리한다. `feasibility_request.request_code`는 시스템이 생성한 내부 요청코드이고, 외부 고객이나 파트너가 보내는 요청번호는 `request_external_ref.external_request_code`로 별도 관리한다. API에서는 `POST /requests`로 내부 요청을 새로 생성하고, `GET /requests/{request_code}/external-refs`, `POST /requests/{request_code}/external-refs`, `PATCH /requests/{request_code}/external-refs/{id}`, `DELETE /requests/{request_code}/external-refs/{id}`로 외부 요청번호 매핑을 조회/추가/기본지정/삭제할 수 있다. 이때 `priority_tier`는 선택 입력이며, 생략하면 `service_policy.priority_tier` 기본값을 자동 적용한다. 후보도 마찬가지로 사용자가 후보코드를 직접 넣지 않고, `request_candidate.candidate_code`를 서버가 자동 발번한다.

후보 테이블에서는 `요청 시간창`과 `촬영기회`를 분리해 본다. `요청 시간창`은 고객이 준 시작/종료 시각이고, `촬영기회`는 후보 입력 화면에서 직접 지정한 `opportunity_start_at ~ opportunity_end_at` 또는 그 시간창 안에서 계산된 `access_opportunity`의 실제 시각이다. 화면에서는 `datetime-local`로 입력하지만 저장 시 UTC ISO 문자열로 변환한다. 따라서 `촬영기회 미계산`은 고객 요청 시간창은 있으나 구체적인 촬영기회 시각 직접 입력도, pass/access 매핑도 아직 없는 상태를 뜻한다.

## 테스트 시나리오

광학/SAR 시나리오는 아래 파일로 실행한다.

```sh
./bootstrap/run_test_scenarios.sh --pristine
```

추가 gap 기능 검증:

```sh
./venv/bin/python ./bootstrap/validate_gap_features.py ./db/feasibility_satti.db
```

관련 문서:

- [src/test_scenarios.md](/Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study/src/test_scenarios.md)
- [bootstrap/test_optical_scenarios.sql](/Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study/bootstrap/test_optical_scenarios.sql)
- [bootstrap/test_sar_scenarios.sql](/Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study/bootstrap/test_sar_scenarios.sql)
- [bootstrap/test_request_candidate_scenarios.sql](/Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study/bootstrap/test_request_candidate_scenarios.sql)

## Repository 사용

Python 예제:

```sh
./venv/bin/python ./src/repository_example.py ./db/feasibility_satti.db REQ-20260307-SEOUL-001
./venv/bin/python ./src/repository_example.py ./db/feasibility_satti.db REQ-20260307-WESTSEA-SAR-001
```

자세한 사용법은 [src/repository_usage.md](/Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study/src/repository_usage.md)에 있다.
