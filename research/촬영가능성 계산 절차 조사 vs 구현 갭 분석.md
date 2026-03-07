# 촬영가능성 계산 절차 조사 vs 구현 갭 분석

기준일: 2026-03-07

## 목적

이 문서는 [촬영가능성 계산 절차 조사.md](/Users/jaehojoo/Desktop/codex-lgcns/real-sattie-study/research/%EC%B4%AC%EC%98%81%EA%B0%80%EB%8A%A5%EC%84%B1%20%EA%B3%84%EC%82%B0%20%EC%A0%88%EC%B0%A8%20%EC%A1%B0%EC%82%AC.md)의 리서치 내용과 현재 구현 사이의 차이를 정리하고, 구현 우선순위와 체크리스트를 관리하기 위한 문서다.

## 한 줄 결론

현재 구현은 `후보 입력값 기반 feasibility 데모 시뮬레이터`에서 `request context + pass/access + deconflict + 환경 snapshot + 누적확률 + proposal + SAR polarization + repeat-pass`를 반영하는 2차 엔진 수준까지 올라왔다.  
리서치 문서가 설명하는 `정식 feasibility 엔진`과 비교하면 남은 핵심 갭은 `request-level 완화 전후 확률 차이 집계`, `환경 상세 규칙의 정밀화`다.

## 전체 갭 요약

| 우선순위 | 갭 항목 | 현재 상태 | 목표 상태 | 비고 |
| --- | --- | --- | --- | --- |
| P1 | 서비스 정책 / 센서 옵션 / 상품 옵션 검증 | 스키마만 존재, 기본 평가 경로 미연결 | 현재 평가와 저장 실행 결과에 실제 반영 | 1차 구현 완료 |
| P2 | pass 기반 기하 접근 계산 | 후보 입력값에 수동 입력된 각도/커버리지 사용 | `satellite_pass`, `access_opportunity` 기반 pass 목록 계산 | 1차 구현 완료 |
| P3 | 누적 성공확률 / attempt proposal | 후보 1건당 단일 `P_total_candidate` 계산 | `1 - Π(1 - P_i)`와 `max_attempts` 기반 proposal 계산 | 1차 구현 완료 |
| P4 | 지상국 / 기존 임무 / 예약 deconflict | `p_conflict_adjusted` 단일 보정계수 | `station_contact_window`, `existing_task`, `existing_downlink_booking` 실제 반영 | 1차 구현 완료 |
| P5 | 광학/SAR 환경 상세 모델 | cloud, sun elevation, incidence 정도만 반영 | haze, sun azimuth, terrain risk, polarization 등 반영 | 2차 구현 완료 |
| P6 | proposal 산출물 확장 | summary/recommendation 수준 | first attempt, expected attempts, SLA, 완화 효과 수치화 | 2차 구현 완료 |

## 갭 상세

### P1. 서비스 정책 / 센서 옵션 / 상품 옵션 검증

리서치 근거:
- 요청 정규화와 서비스 정책 검증이 feasibility의 첫 단계다.
- 최소 주문 면적, 주문 cutoff, 우선순위 옵션, 제품 레벨, 파일 형식, 센서/모드 적합 여부를 먼저 걸러야 한다.

현재 상태:
- `service_policy`, `request_sensor_option`, `request_product_option` 테이블은 존재한다.
- 하지만 기본 current evaluation 경로는 `SimulationInput`만 받아 계산한다.
- 따라서 정책 불일치가 있어도 기본 계산만 통과하면 `가능`으로 나올 수 있다.

목표 상태:
- request context를 붙인 동적 평가에서 다음을 실제 검증한다.
  - 최소 주문 면적
  - 주문 cutoff
  - 요청/후보 우선순위 적합성
  - 센서 옵션 적합성
  - 제품 레벨 / 제품 유형 / 파일 형식 적합성

세부 체크리스트:
- [x] `get_request()`에 policy 메타데이터 추가
- [x] current evaluation 경로에 policy validation 레이어 추가
- [x] candidate simulate 저장 경로도 같은 validation 사용
- [x] POLICY stage reason / recommendation 생성
- [x] UI에 policy 영향 표시
- [x] API/문서/테스트 현행화

### P2. pass 기반 기하 접근 계산

리서치 근거:
- feasibility는 `satellite_pass`와 `access_opportunity` 기반으로 후보 pass를 생성해야 한다.
- cross-track reach, 접근 시각, segment, coverage ratio를 계산해야 한다.

현재 상태:
- 관련 테이블과 seed 데이터는 있으나 기본 동적 평가에서는 사용하지 않는다.
- 현재 후보 입력값의 `required_off_nadir_deg`, `predicted_incidence_deg`, `coverage_ratio_predicted`를 수동 입력값으로 직접 사용한다.

목표 상태:
- request-level 계산에서 `satellite_pass/access_opportunity`를 실제 candidate source로 사용
- 후보건은 pass를 직접 입력하는 대신 제약 프로필 역할을 갖고, pass 후보는 엔진이 계산

1차 구현 반영:
- `list_request_access_opportunities()`와 `get_request_candidate_access_opportunity()`를 추가했다.
- 후보 코드별로 `access_opportunity`를 매핑하여 `required_off_nadir_deg`, `predicted_incidence_deg`, `coverage_ratio_predicted`를 access 기반 값으로 덮어쓴다.
- `geometric_feasible_flag = 0`인 경우 `ACCESS_OPPORTUNITY_INFEASIBLE` hard reason을 생성한다.
- 요청 전체 `candidate_rows`는 access 시각 기준으로 정렬되며, UI도 이 순서를 그대로 사용한다.

세부 체크리스트:
- [x] request + constraint + sensor option -> access opportunity 후보 생성 로직 연결
- [x] `candidate_rows`를 입력값 기반이 아니라 pass 기반으로 전환
- [x] coverage / off-nadir / incidence 계산식을 seed snapshot과 연결
- [x] request UI의 후보 테이블을 pass 기반으로 재정렬

### P3. 누적 성공확률 / attempt proposal

리서치 근거:
- 단일 pass가 아니라 여러 pass의 누적 성공확률을 계산해야 한다.
- `P_total = 1 - Π(1 - P_i)` 및 `max_attempts` 기반 제안서가 필요하다.

현재 상태:
- 후보 1건마다 단일 `p_total_candidate`만 계산한다.
- 요청 전체 결과는 가장 좋은 후보 1건을 대표값으로 삼는다.

목표 상태:
- request-level 결과에서 후보 pass 다건을 누적하여 `overall_probability`, `first_attempt_at`, `expected_attempt_count`를 계산
- 서비스 정책 `max_attempts`와 시간창을 반영

1차 구현 반영:
- 요청 전체 결과의 `overall_probability`는 더 이상 best candidate 단일 확률이 아니라 시도 순서 기준 누적확률이다.
- `max_attempts` 범위 안의 후보들에 대해 `1 - Π(1 - P_i)`를 계산한다.
- `first_feasible_attempt_at`, `expected_attempt_count`, `attempt_count_considered`, `max_attempts_considered`를 결과에 포함한다.
- UI summary와 CLI 출력도 누적확률/첫 촬영기회/예상 촬영기회 소진 수를 표시한다.

세부 체크리스트:
- [x] pass별 `P_i` 계산
- [x] `1 - Π(1 - P_i)` 구현
- [x] `max_attempts` 반영
- [x] proposal message를 누적확률 기반으로 변경

### P4. 지상국 / 기존 임무 / 예약 deconflict

리서치 근거:
- 지상국 접촉 창, link rate, 예약 충돌, 기존 임무, 다운링크 backlog는 feasibility 핵심 제약이다.

현재 상태:
- 현재 구현은 `p_conflict_adjusted = priority + window_hours` 보정 수준이다.
- `station_contact_window`, `existing_task`, `existing_downlink_booking`는 기본 current evaluation에 연결되지 않는다.

목표 상태:
- 실제 contact window와 예약 충돌을 계산하여 downlink feasible 여부를 판단
- 기존 촬영과 시간 충돌하면 hard/soft reason 생성

1차 구현 반영:
- access opportunity 이후 가장 이른 `station_contact_window`를 선택한다.
- contact window의 `downlink_rate_mbps`, `link_efficiency_pct`, 기존 booking reserved volume으로 net contact capacity를 계산한다.
- 겹치는 `existing_task`가 있으면 우선순위 비교 후 `EXISTING_TASK_CONFLICT` 또는 `TASK_PREEMPTION_REVIEW`를 생성한다.
- contact booking이 겹치면 `CONTACT_WINDOW_PARTIALLY_BOOKED` 또는 `CONTACT_WINDOW_FULLY_BOOKED`를 생성하고 `p_conflict_adjusted`에 반영한다.

세부 체크리스트:
- [x] selected contact window 선택 로직
- [x] backlog + downlink capacity 계산을 station window 기반으로 연결
- [x] existing task / booking 충돌 reason 반영
- [x] `p_conflict_adjusted`를 실제 deconflict 기반 값으로 교체

### P5. 광학/SAR 환경 상세 모델

리서치 근거:
- 광학은 cloud/haze/sun azimuth/shadow
- SAR는 incidence/terrain risk/polarization/repeat-pass

현재 상태:
- 광학: cloud, sun elevation, haze, forecast confidence, sun azimuth, shadow risk, preferred local time window
- SAR: incidence, terrain risk, polarization policy 검증, repeat-pass requirement + repeat spacing + quality threshold + incidence consistency tolerance
- 다만 polarization은 mode compatibility 수준이고, repeat-pass는 request-level 요구 횟수, 최소 재방문 간격, 반복 카운트 품질 하한, 기준 후보 대비 입사각 일관성 한도를 반영하는 단계다.

목표 상태:
- `weather_snapshot`, `weather_cell_forecast`, `solar_condition_snapshot`, `terrain_risk_snapshot` 실제 사용

2차 구현 반영:
- 광학 요청은 nearest `weather_cell_forecast`, `solar_condition_snapshot`를 읽어 haze, 예보 신뢰도, 주간 여부, 예보 태양고도를 평가한다.
- 광학 요청은 `sun_elevation_deg + sun_azimuth_deg + request_aoi.centroid_lat + request_aoi.dominant_axis_deg + month + local_capture_time` 조합으로 `shadow_risk_score`를 계산하고 `SHADOW_RISK_ELEVATED/HIGH`를 생성한다.
- 광학 요청은 `centroid_lon`으로 현지시각을 근사 계산하고 `preferred_local_time_start/end`와 비교해 `LOCAL_TIME_WINDOW_MISALIGNED`를 생성한다.
- SAR 요청은 `terrain_risk_snapshot`의 risk score를 읽어 `TERRAIN_RISK_ELEVATED/HIGH`를 생성한다.
- SAR 요청은 `request_sensor_option.polarization_code`와 `sensor_mode.supported_polarizations`를 비교해 `POLARIZATION_UNSUPPORTED`를 생성한다.
- 반복 촬영이 요청된 경우 `repeat_acquisition_flag`, `monitoring_count`를 읽어 `required_attempt_count`, `repeat_requirement_met`, `repeat_quality_threshold`, `repeat_spacing_hours_required`, `repeat_spacing_met`, `repeat_incidence_tolerance_deg`를 계산하고 `REPEAT_PASS_REQUIREMENT_UNMET`, `REPEAT_PASS_INCIDENCE_INCONSISTENT`, `REPEAT_PASS_SPACING_UNMET`를 결과에 반영한다.
- UI에는 환경 스냅샷 항목이 별도 카드로 표시된다.

세부 체크리스트:
- [x] haze index 반영
- [x] sun azimuth / shadow rule 반영
- [x] preferred local time window 반영
- [x] terrain risk score 반영
- [x] SAR polarization 조건 반영
- [x] repeat-pass requirement 반영
- [x] repeat-pass spacing rule 반영
- [x] repeat-pass quality threshold 반영
- [x] repeat-pass incidence consistency 반영

### P6. proposal 산출물 확장

리서치 근거:
- feasibility proposal에는 `첫 시도일`, `예상 시도 횟수`, `완화 효과`, `SLA`가 포함되어야 한다.

현재 상태:
- summary message + recommendation 정도만 제공

목표 상태:
- request-level proposal object를 별도 구조로 제공

2차 구현 반영:
- 요청 전체 응답에 `proposal` 객체를 추가했다.
- `proposal`에는 정책명, 우선순위, 누적 성공확률, 첫 촬영기회 시각, 예상 촬영기회 소진 수, 정책상 집계 상한, 대표 후보, SLA 요약, 상위 완화 제안을 담는다.
- 후보 단건 current evaluation에서는 recommendation별 `expected_probability_gain`을 계산한다.
- 요청 전체 proposal에도 `required_attempt_count`, `repeat_requirement_met`를 포함한다.
- UI에는 `Feasibility Analysis Summary` 패널이 추가됐다.
- `incidence_window` 추천안은 해당 후보 입력값에 즉시 반영 후 검증 실행할 수 있고, `candidate_split` 추천안은 새 분리 후보를 생성해 즉시 검증 실행할 수 있다.

세부 체크리스트:
- [x] first feasible attempt at 계산
- [x] expected attempts 계산
- [x] policy/SLA 문구 추가
- [x] 후보 단건 완화 전/후 확률 차이 계산
- [x] 요청 전체 완화 전/후 확률 차이 집계
- [x] request-level proposal을 UI action과 연결

## 구현 우선순위

### 1단계
- P1 서비스 정책 / 센서 옵션 / 상품 옵션 검증

### 2단계
- P2 pass 기반 기하 접근 계산
- P3 누적 성공확률 / attempt proposal

### 3단계
- P4 지상국 / 기존 임무 / 예약 deconflict

### 4단계
- P5 광학/SAR 환경 상세 모델
- P6 proposal 산출물 확장

## 진행 상태

### 완료
- [x] 갭 분석 문서 생성
- [x] P1 서비스 정책 / 센서 옵션 / 상품 옵션 검증 1차 구현
- [x] P2 pass 기반 기하 접근 계산 1차 구현
- [x] P3 누적 성공확률 / attempt proposal 1차 구현
- [x] P4 지상국 / 기존 임무 / 예약 deconflict 1차 구현
- [x] P5 광학/SAR 환경 상세 모델 1차 구현
- [x] P6 proposal 산출물 확장 1차 구현
- [x] P5 SAR polarization / repeat-pass 2차 구현
- [x] P6 후보 단건 완화 전/후 확률 차이 2차 구현

### 진행 중
- [ ] 환경 상세 규칙 정밀화

## 확률 분해 해석

현재 UI의 `모델 분해 결과`에 표시되는 `P(geo)`, `P(env)`, `P(resource)`, `P(downlink)`, `P(policy)`, `P(conflict-adjusted)`, `P(total)`은 모두 계산값이다.

- 입력/스냅샷:
  - 후보 입력값
  - request 원본 제약
  - access opportunity
  - weather / solar / terrain snapshot
  - contact window / booking / existing task
- 계산값:
  - `P(geo)`
  - `P(env)`
  - `P(resource)`
  - `P(downlink)`
  - `P(policy)`
  - `P(conflict-adjusted)`
  - `P(total)`

즉 `P(total)`은 실측값이 아니라 위 각 평가축을 종합해 계산한 최종 후보 확률이다.

## 완화 제안 해석

현재 UI의 `완화 제안` 카드에는 서로 다른 성격의 값이 함께 표시된다.

- `current`
  - 현재 후보 입력값 또는 현재 access 상태값
  - 예: 현재 backlog, 현재 downlink 가용량, 현재 access 시각/coverage
- `recommended`
  - 엔진이 계산한 완화안
  - 예: 목표 backlog, 목표 downlink 용량, 다른 pass 사용 권고
- `gain`
  - 해당 완화안을 적용했을 때의 예상 확률 증가량
  - 후보 단건 recommendation이면 `p_total_candidate` 증가량, 요청 전체 proposal이면 누적 성공확률 증가량

따라서 `완화 제안`의 모든 값이 동일한 종류의 계산값은 아니다. `current`는 현재 상태/입력값이고, `recommended`와 `gain`은 엔진이 생성한 계산 결과다.
