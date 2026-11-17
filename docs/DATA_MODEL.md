# My Local AI — 로컬 SQLite 스키마 및 복구 V1 (설계)

SQLite3/Python3.11 stdlib, WAL, foreign_keys=ON, one-writer controller, bounded busy_timeout. 기본 DB는 사용자 로컬 앱 데이터 디렉터리(아직 생성 안 됨), Git/고객 repo 외부. 마이그레이션 전 원본 보존/일관된 backup + SHA + 복구 경로, destructive migration 사전 GO.

| 테이블 | 주요 PK / 기능 |
|---|---|
| `schema_version` | version, migration_sha, applied_at, 이전 복구 정보 |
| `plans` | plan_id PK, plan_sha UNIQUE, 승인 scope/state, blueprint SHA |
| `tasks` | (plan_id, task_id) PK, req_ids, deps_sha, allowed_paths_sha, state |
| `runs` | run_id PK, plan_id, started/ended, host, model, baseline_git_sha, outcome |
| `leases` | (run_id,task_id) PK, epoch/nonce/expiry, exclusive fencing |
| `attempts` | task/attempt_no PK, candidate_sha, model_calls, fix_once_used, outcome |
| `reviews` | receipt_id PK, candidate_sha, reviewer_tool_sha, trust_boundary_id, checks_digest, verdict |
| `integration` | plan_sha+task_id UNIQUE, verified_receipt_id, git_ref, target_sha |
| `events` | event_id PK, timestamp UTC, reason_code, redacted detail |
| `metrics` | task throughput, RAM/CPU/VRAM observation, duration, error class; only synthetic |
| `owner_consents` | approval_id, scope_sha, approved_at/expires_at/revoked_at, no credentials |

**트랜잭션:** 선택 가능한 READY 목록/종속 검증 → BEGIN IMMEDIATE lease(epoch++) → 모델 작업은 트랜잭션 밖 → 격리 reviewer 증거 수집 → 정본 plan/source/epoch/작업 경로를 재검증한 후 안전한 local Git ref CAS → crash recovery reconciliation. DB 성공 + Git 실패/반대 경우 모두 SHA를 비교해 조정하고 중복 실행 금지. 불명확한 staging 폴더는 삭제 대신 HOLD_MANUAL_REVIEW.

**로그/보존:** raw 프롬프트·고객 코드·비밀 키/개인 경로 DB 금지; 에러 코드를 최소 공개. 로컬 개인 로그는 Git 무시, 수동 파기 정책 별도. 재시작 후 동일 작업 2중 파일 적용 방지 test; 고장 이전 last verified ref 복구.
