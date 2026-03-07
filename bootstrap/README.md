# Bootstrap Assets

이 폴더는 최초 SQLite 환경을 만들기 위한 초기화 자산을 분리해서 관리하는 위치다.

포함 대상:

- `schema.sql`: 초기 스키마 정의
- `seed.sql`: 최초 seed 데이터
- `bootstrap_db.sh`: 스키마 + seed로 DB를 재생성하는 스크립트
- `migrate_db_schema.sh`: 기존 작업 DB에 additive schema migration을 적용하는 스크립트
- `run_test_scenarios.sh`: 시드 데이터 검증용 SQL 실행 스크립트. `--pristine` 옵션으로 임시 pristine DB를 만들어 결정적으로 검증할 수 있다.
- `test_optical_scenarios.sql`: 광학 요청 검증 SQL
- `test_sar_scenarios.sql`: SAR 요청 검증 SQL
- `test_request_candidate_scenarios.sql`: 요청건 하위 후보건 검증 SQL
- `print_current_request_evaluations.py`: 현재 후보 입력값 기준 동적 요청 평가 출력 스크립트
- `validate_gap_features.py`: polarization / repeat-pass / recommendation gain 검증 스크립트

설계 원칙:

- `src/`는 애플리케이션 코드만 둔다.
- `bootstrap/`은 초기화, seed, 검증 SQL 같은 부트스트랩 자산만 둔다.
- 실제 SQLite DB 파일과 `.bak` 백업은 `db/` 폴더에서 관리한다.
- DB를 다시 만들 때는 `bootstrap/bootstrap_db.sh`를 사용한다.
- 기존 작업 DB를 유지한 채 컬럼만 추가할 때는 `bootstrap/migrate_db_schema.sh`를 사용한다.
- 현재 additive migration 대상:
  - `request_aoi.dominant_axis_deg`
  - `request_candidate_run.input_version_no`
  - `request_candidate_run.run_trigger_type`
  - `request_candidate_run.run_trigger_source_code`
  - `request_candidate_run.run_trigger_parameter_name`
  - `request_candidate_run.run_trigger_note`
- 요청 하위 후보건 seed는 입력값만 포함한다.
- 후보별 실행 결과는 seed로 넣지 않고, `저장 후 검증 실행` 이후 `request_candidate_run*` 테이블에 저장한다.
- 요청 식별자는 내부/외부를 분리한다. `feasibility_request.request_code`는 시스템 내부 요청코드이고, 외부 고객 요청번호는 `request_external_ref`에 저장한다.
- 후보코드는 `request_candidate.candidate_code`를 서버가 자동 생성한다.

예시:

```sh
./bootstrap/bootstrap_db.sh ./db/feasibility_satti.db
./bootstrap/migrate_db_schema.sh ./db/feasibility_satti.db
./bootstrap/run_test_scenarios.sh --pristine
./venv/bin/python ./bootstrap/validate_gap_features.py ./db/feasibility_satti.db
```
