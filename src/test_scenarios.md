# Feasibility Demo Test Scenarios

이 문서는 bootstrap seed 기준으로 어떤 테스트 시나리오를 검증할 수 있는지 정리한 문서다. 결정적인 seed 검증은 `./bootstrap/run_test_scenarios.sh --pristine`를 기준으로 본다. 작업 중인 `db/feasibility_satti.db`는 사용자가 추가한 후보와 실행 이력을 포함할 수 있다. 요청 하위 후보건은 초기 seed에서 입력값만 가지며, 후보 실행 결과는 `저장 후 검증 실행` 이후에 생성된다. 요청 전체 결과 섹션은 seed result 테이블이 아니라 현재 후보 입력값을 공통 시뮬레이터에 태운 동적 계산 결과를 사용한다. 현재 구현에는 request context 정책 검증, `access_opportunity` 기반 기하 매핑, `station_contact_window / existing_task / existing_downlink_booking` 기반 deconflict, `weather_cell_forecast / solar_condition_snapshot / terrain_risk_snapshot` 기반 환경 리스크, `max_attempts` 기준 누적 성공확률, `proposal` 산출물이 포함된다.

## 터미널에서 바로 실행하는 순서

프로젝트 루트에서 아래 순서로 실행하면 된다.

```sh
cd /Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study
./one-shot-setup.sh
./bootstrap/run_test_scenarios.sh --pristine
python ./src/repository_example.py ./db/feasibility_satti.db REQ-20260307-SEOUL-001
python ./src/repository_example.py ./db/feasibility_satti.db REQ-20260307-WESTSEA-SAR-001
./one-shot-startup.sh
curl http://127.0.0.1:6003/
curl http://127.0.0.1:6003/health
curl http://127.0.0.1:6003/requests
curl http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/external-refs
curl -X PATCH http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/external-refs/1 -H 'content-type: application/json' -d '{"is_primary": true}'
curl -X DELETE http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/external-refs/1
curl http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001
curl http://127.0.0.1:6003/requests/REQ-20260307-WESTSEA-SAR-001
curl -X POST http://127.0.0.1:6003/simulate -H 'content-type: application/json' -d '{"sensor_type":"SAR","priority_tier":"PRIORITY","area_km2":625,"window_hours":48,"cloud_pct":0,"max_cloud_pct":100,"required_off_nadir_deg":0,"max_off_nadir_deg":40,"predicted_incidence_deg":33,"min_incidence_deg":25,"max_incidence_deg":40,"sun_elevation_deg":0,"min_sun_elevation_deg":0,"coverage_ratio_predicted":0.98,"coverage_ratio_required":0.95,"expected_data_volume_gbit":28,"recorder_free_gbit":22,"recorder_backlog_gbit":20,"available_downlink_gbit":34,"power_margin_pct":14,"thermal_margin_pct":12}'
./one-shot-stop.sh
```

## 준비

DB를 다시 만들려면 아래를 실행한다.

```sh
./bootstrap/bootstrap_db.sh ./db/feasibility_satti.db
```

시나리오 SQL 및 동적 평가 스크립트는 아래와 같다.

- `bootstrap/test_optical_scenarios.sql`
- `bootstrap/test_sar_scenarios.sql`
- `bootstrap/test_request_candidate_scenarios.sql`
- `bootstrap/print_current_request_evaluations.py`

결정적인 seed 검증 예시는 다음과 같다.

```sh
./bootstrap/run_test_scenarios.sh --pristine
```

작업 중인 현재 DB 상태를 그대로 확인하려면:

```sh
cd /Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study
./bootstrap/run_test_scenarios.sh ./db/feasibility_satti.db
```

## 데이터 개요

현재 seed는 두 개의 독립 요청을 포함한다.

### 1. 광학 시나리오

- 요청 코드: `REQ-20260307-SEOUL-001`
- 위성: `KOMPSAT-3`
- 센서: `AEISS-A`
- 모드: `SPOTLIGHT`
- 특성: `cloud <= 20%`, `off-nadir <= 25°`, `7일 window`

기대 특징:

- 현재 입력 기준으로 후보 2개는 `CONDITIONALLY_FEASIBLE`
- 1개는 `OFF_NADIR_EXCEEDED`로 하드 탈락
- 기준 후보는 `CONTACT_WINDOW_PARTIALLY_BOOKED` 때문에 `CONDITIONALLY_FEASIBLE`가 된다.
- 다른 1개는 `CLOUD_PROBABILITY_TOO_HIGH`를 가진 `CONDITIONALLY_FEASIBLE`
- 요청 전체 최종 verdict는 `CONDITIONALLY_FEASIBLE`
- 요청 전체 `overall_probability`는 단일 후보 확률이 아니라 최대 시도 기준 누적확률이다.
- best candidate는 `OPT-CAND-001`

### 2. SAR 시나리오

- 요청 코드: `REQ-20260307-WESTSEA-SAR-001`
- 위성: `KOMPSAT-5`
- 센서: `X-Band SAR`
- 모드: `STRIPMAP`
- 특성: `incidence angle 25° ~ 40°`, `48시간 window`, `PRIORITY`

기대 특징:

- 구름 제약이 직접 판정을 지배하지 않음
- 현재 입력 기준으로 첫 후보는 `CONTACT_WINDOW_PARTIALLY_BOOKED`와 `TERRAIN_RISK_ELEVATED`가 붙은 `CONDITIONALLY_FEASIBLE`
- 1개는 `INCIDENCE_ANGLE_OUT_OF_RANGE`로 탈락
- 1개는 `RECORDER_OVERFLOW`와 `DOWNLINK_MARGIN_LOW`로 탈락
- 요청 전체 최종 verdict는 `CONDITIONALLY_FEASIBLE`
- 요청 전체 `overall_probability`는 단일 후보 확률이 아니라 최대 시도 기준 누적확률이다.
- best candidate는 `SAR-CAND-001`

## 검증 시나리오 목록

### 광학 주문

1. 요청 원본과 제약이 정상 적재됐는지 확인
2. 광학 후보 입력값 3건이 seed로 적재됐는지 확인
3. 초기 후보 실행 이력이 모두 0건인지 확인
4. 동적 평가 결과에서 후보별 상태가 `CONDITIONAL`, `REJECTED`, `CONDITIONAL`로 나뉘는지 확인
5. 하드 탈락 사유가 `OFF_NADIR_EXCEEDED`인지 확인
6. soft risk가 `CLOUD_PROBABILITY_TOO_HIGH`인지 확인
7. 기준 후보에 `CONTACT_WINDOW_PARTIALLY_BOOKED`가 붙는지 확인
8. 요청 전체 summary가 누적 성공확률과 첫 시도 기준을 포함하는지 확인

직접 실행 커맨드:

```sh
cd /Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study
./bootstrap/run_test_scenarios.sh --pristine
```

### SAR 주문

1. 요청 제약이 incidence angle 범위 중심인지 확인
2. SAR 후보 입력값 3건이 seed로 적재됐는지 확인
3. 초기 후보 실행 이력이 모두 0건인지 확인
4. 동적 평가 결과에서 두 번째 후보가 각도 초과로 탈락하는지 확인
5. 세 번째 후보가 cloud가 아니라 recorder/downlink 병목으로 탈락하는지 확인
6. 첫 후보에 `CONTACT_WINDOW_PARTIALLY_BOOKED`가 붙는지 확인
7. SAR 후보들에 `TERRAIN_RISK_ELEVATED`가 반영되는지 확인
8. 요청 전체 best candidate가 `SAR-CAND-001`인지 확인하고 최종 verdict가 `CONDITIONALLY_FEASIBLE`인지 확인
9. 요청 전체 summary가 누적 성공확률과 시도 횟수 기준을 포함하는지 확인

직접 실행 커맨드:

```sh
cd /Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study
./bootstrap/run_test_scenarios.sh --pristine
```

## 해석 포인트

이 seed는 feasibility 엔진의 서로 다른 판정 패턴을 한 번에 보여주도록 구성했다.

- 광학 주문은 `기상`과 `촬영 각도`가 지배적인 경우
- SAR 주문은 `incidence angle`, `recorder backlog`, `downlink margin`이 지배적인 경우

즉, 같은 ERD와 같은 엔진 구조를 쓰더라도 센서 종류에 따라 어떤 외부 인풋이 더 중요한지가 달라진다는 점을 테스트할 수 있다.

## 추가로 해볼 수 있는 직접 검증 커맨드

### 요청 목록 확인

```sh
cd /Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study
sqlite3 -header -column ./db/feasibility_satti.db "SELECT request_id, request_code, priority_tier, request_status FROM feasibility_request ORDER BY request_id;"
```

### 현재 입력 기준 광학 결과 확인

```sh
cd /Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study
./venv/bin/python ./bootstrap/print_current_request_evaluations.py ./db/feasibility_satti.db
```

### 현재 입력 기준 SAR 결과 확인

```sh
cd /Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study
./venv/bin/python ./bootstrap/print_current_request_evaluations.py ./db/feasibility_satti.db
```

### gap 기능 검증

```sh
cd /Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study
./venv/bin/python ./bootstrap/validate_gap_features.py ./db/feasibility_satti.db
```

기대 결과:

- `candidate_gain` 출력에 recommendation별 `expected_probability_gain`이 포함된다.
- `request_gain` 출력에 proposal 완화안별 `expected_probability_gain`이 포함된다.
- `repeat_pass` 출력에서 반복 촬영 요구를 2회로 올리면 `REPEAT_PASS_REQUIREMENT_UNMET`가 표시된다.
- `repeat_spacing` 출력에서 반복 촬영 간격이 부족하면 `REPEAT_PASS_SPACING_UNMET`가 표시된다.
- `repeat_incidence` 출력에서 기준 후보 대비 입사각 일관성 한도가 적용되고 `REPEAT_PASS_INCIDENCE_INCONSISTENT`, `inc_tol=5.0`, `options=incidence_window,candidate_split`이 표시된다.
- `polarization` 출력에서 지원 편파를 바꾸면 `POLARIZATION_UNSUPPORTED`가 표시된다.
- `shadow` 출력에서 태양 고도/방위각 조합을 바꾸면 `SHADOW_RISK_ELEVATED` 또는 `SHADOW_RISK_HIGH`가 표시된다. 이 점수는 AOI 위도, AOI 방향성, 월, 현지시각 편차도 함께 반영한다.
- `local_time` 출력에서 현지시각 선호창을 바꾸면 `LOCAL_TIME_WINDOW_MISALIGNED`가 표시된다.

### Repository 출력 직접 보기

```sh
cd /Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study
python ./src/repository_example.py ./db/feasibility_satti.db REQ-20260307-SEOUL-001
python ./src/repository_example.py ./db/feasibility_satti.db REQ-20260307-WESTSEA-SAR-001
```

### API 서버 직접 테스트

```sh
cd /Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study
./one-shot-startup.sh
curl http://127.0.0.1:6003/
curl http://127.0.0.1:6003/health
curl http://127.0.0.1:6003/requests
curl http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001
curl http://127.0.0.1:6003/requests/REQ-20260307-WESTSEA-SAR-001
curl http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/request-candidates
curl http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/request-candidates/OPT-CAND-001
curl -X POST http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/request-candidates/OPT-CAND-001/simulate
curl -X POST http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/external-refs -H 'content-type: application/json' -d '{"source_system_code":"PARTNER_API","external_request_code":"PARTNER-SEOUL-777","external_request_title":"서울 광학 긴급 요청","external_customer_org_name":"Seoul Disaster Analytics Center","external_requester_name":"Han Mina","is_primary":true,"received_at":"2026-03-07T11:00:00Z"}'
curl -X PATCH http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/external-refs/1 -H 'content-type: application/json' -d '{"is_primary": true}'
curl -X DELETE http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/external-refs/1
curl -X POST http://127.0.0.1:6003/requests -H 'content-type: application/json' -d '{"customer_org_id":1,"customer_user_id":1,"service_policy_id":2,"request_title":"서해 SAR 신규 감시 요청","request_description":"서해 특정 해역에 대한 신규 SAR 감시 요청입니다.","requested_start_at":"2026-03-12T00:00:00Z","requested_end_at":"2026-03-13T00:00:00Z","emergency_flag":true,"repeat_acquisition_flag":false,"monitoring_count":1,"aoi":{"geometry_type":"POLYGON","geometry_wkt":"POLYGON((124.65 36.85,124.95 36.85,124.95 37.10,124.65 37.10,124.65 36.85))","srid":4326,"area_km2":510.0,"bbox_min_lon":124.65,"bbox_min_lat":36.85,"bbox_max_lon":124.95,"bbox_max_lat":37.10,"centroid_lon":124.80,"centroid_lat":36.975,"dominant_axis_deg":90.0},"constraint":{"min_incidence_deg":25.0,"max_incidence_deg":40.0,"deadline_at":"2026-03-13T00:00:00Z","coverage_ratio_required":0.9},"sensor_options":[{"satellite_id":2,"sensor_id":2,"sensor_mode_id":2,"preference_rank":1,"is_mandatory":true,"polarization_code":"HH"}],"product_options":[{"product_level_code":"L1C","product_type_code":"SIGMA0","file_format_code":"HDF5","delivery_mode_code":"FTP","ancillary_required_flag":true}],"external_ref":{"source_system_code":"CUSTOMER_PORTAL","external_request_code":"EXT-WESTSEA-NEW-9001","external_request_title":"서해 해역 긴급 SAR 촬영 요청","external_customer_org_name":"Seoul Disaster Analytics Center","external_requester_name":"Kim Mina","is_primary":true,"received_at":"2026-03-07T10:20:00Z"}}'
curl -X POST http://127.0.0.1:6003/simulate -H 'content-type: application/json' -d '{"sensor_type":"SAR","priority_tier":"PRIORITY","area_km2":625,"window_hours":48,"cloud_pct":0,"max_cloud_pct":100,"required_off_nadir_deg":0,"max_off_nadir_deg":40,"predicted_incidence_deg":33,"min_incidence_deg":25,"max_incidence_deg":40,"sun_elevation_deg":0,"min_sun_elevation_deg":0,"coverage_ratio_predicted":0.98,"coverage_ratio_required":0.95,"expected_data_volume_gbit":28,"recorder_free_gbit":22,"recorder_backlog_gbit":20,"available_downlink_gbit":34,"power_margin_pct":14,"thermal_margin_pct":12}'
./one-shot-stop.sh
```

### 프론트엔드 후보건 테스트

```sh
cd /Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study
./one-shot-startup.sh
# 브라우저에서 http://127.0.0.1:6003/ 접속
./one-shot-stop.sh
```

브라우저에서 확인할 요청건:

- `서울 AOI 광학 촬영 요청건`
- `서해 AOI SAR 촬영 요청건`

브라우저에서 추가 확인:

- 각 요청 아래 후보건 3개가 보인다.
- 후보건을 클릭하면 입력값, 현재 입력 기준 평가, 최신 저장 실행 결과가 함께 로드된다.
- 요청 전체 섹션은 현재 후보 입력값 기준 동적 평가 결과를 보여준다.
- 요청 전체 확률은 `max_attempts` 범위에서 계산한 누적 성공확률이다.
- `Feasibility Analysis Summary` 패널에 첫 촬영기회, 예상 촬영기회 소진 수, SLA 요약이 보인다.
- 상단 요청 개요/운용 제한은 고객 원본 요청값으로 읽기 전용이며, `AOI 방향`이 보인다.
- `외부 요청번호 매핑` 패널은 기본 닫힘 상태이며, 우측 상단 토글 아이콘으로 열고 닫을 수 있다.
- `새 후보 준비`를 누르면 신규 후보 초안이 열린다.
- `후보 저장`이 동작한다.
- `저장 후 검증 실행`을 누르면 그 시점의 입력값으로 최신 저장 실행 결과가 계산되어 갱신된다.
- `기준안 여부`를 체크해 저장하면 같은 요청의 기존 기준안은 자동 해제된다.
- 요청을 다시 열면 기준안 후보가 우선 로드되고 목록에 `기준안` 배지가 보인다.
- `incidence_window` proposal 카드의 `기존 후보 반영 후 실행` 버튼을 누르면 대상 후보 입력값이 즉시 갱신되고 바로 검증 실행된다.
- `candidate_split` proposal 카드의 `분리 후보 생성` 버튼을 누르면 새 `DRAFT` 후보가 생성되고 즉시 검증 실행까지 수행된다.
- 후보 상세의 `실행 이력` 섹션에 `input vN`, 실행 출처, 확률이 함께 기록된다.
- `실행 이력`의 `전체 이력` / `추천안 실행만` 필터가 동작한다.
- `선택 후보 삭제`가 동작한다.

정책 검증 직접 확인 예시:

```sh
curl -X POST http://127.0.0.1:6003/requests/REQ-20260307-SEOUL-001/simulate-candidate-input \
  -H 'content-type: application/json' \
  -d '{"sensor_type":"SAR","priority_tier":"URGENT","area_km2":50,"window_hours":168,"cloud_pct":18,"max_cloud_pct":20,"required_off_nadir_deg":18.5,"max_off_nadir_deg":25,"predicted_incidence_deg":30,"min_incidence_deg":25,"max_incidence_deg":40,"sun_elevation_deg":44,"min_sun_elevation_deg":20,"coverage_ratio_predicted":0.98,"coverage_ratio_required":0.95,"expected_data_volume_gbit":14,"recorder_free_gbit":48,"recorder_backlog_gbit":12,"available_downlink_gbit":42,"power_margin_pct":19,"thermal_margin_pct":16}'
```

기대 결과:

- `NOT_FEASIBLE`
- `MIN_ORDER_AREA_NOT_MET`
- `SENSOR_OPTION_MISMATCH`
- `PRODUCT_*_UNSUPPORTED`
- `reason_stage = POLICY`

추가 확인 SQL:

```sh
cd /Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study
sqlite3 -header -column ./db/feasibility_satti.db "SELECT request_id, request_code, request_title, request_description FROM feasibility_request ORDER BY request_id;"
sqlite3 -header -column ./db/feasibility_satti.db "SELECT request_id, source_system_code, external_request_code, is_primary FROM request_external_ref ORDER BY request_id, request_external_ref_id;"
sqlite3 -header -column ./db/feasibility_satti.db "SELECT request_id, candidate_code, candidate_title, candidate_rank FROM request_candidate ORDER BY request_id, candidate_rank;"
```
