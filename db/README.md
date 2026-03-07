# SQLite DB Files

이 폴더는 실행 중 생성되거나 재생성되는 SQLite DB 파일만 보관한다.

포함 대상:

- `feasibility_satti.db`: 현재 데모 DB
- `archive/feasibility_satti.db.<timestamp>.bak`: one-shot setup이 만든 백업본

원칙:

- `bootstrap/`은 스키마, seed, 초기화 스크립트만 둔다.
- `db/`는 실제 SQLite 산출물만 둔다.
- `.bak` 백업은 `db/archive/`로 분리한다.
- 서버, repository 예제, 테스트 스크립트의 기본 DB 경로는 `./db/feasibility_satti.db`다.
