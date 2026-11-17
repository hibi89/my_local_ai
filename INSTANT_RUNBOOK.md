# INSTANT_RUNBOOK — My Local AI (2026-11-17)
## 역할·시작
실행 전 확인: hibi89/my_local_ai, dev/instant-implementation-v1, exact SHA → AGENTS/HANDOFF/STATUS → REQUIREMENTS/FINAL_BLUEPRINT/SECURITY_MODEL → actual code+queue. 지금은 **설계 승인 대기**다. 다음 ㄱ은 사용자가 이 계획 승인한 경우에만 P1 실행으로 간주한다. 원본 EAI/AX 코드는 read-only, 비밀은 public repo에 올리지 않는다.

## P0 High 판단
선택 설계: 독립 새 단일 repo에 검증된 EAI CPU와 AX 실행기 모듈만 provenance+라이선스+테스트로 선별 이식. 기존 F18 guest receipt 신뢰 경계가 안전 BLOCKER다. Qwen local coding worker 역할은 AX 안에서만, EAI 내부 Qwen은 INPUT-only.
공식 구현·검증 상태 UNASSESSED. full CI는 P1 구현 후보 후 묶되 안전한 국소/필수 검사 유지.

## 최초 READY 5개 — 독립 병렬 설계/구현 후보
- **MLA-001** REQ-01,REQ-02 Pin exact EAI/AX source/branch/blob SHA, audit owned/third-party licenses; no source copy until approved; 경로 docs/PROVENANCE_AND_LICENSES.md, docs/IMPORT_MANIFEST.json, scripts/audit_sources.py, tests/unit/test_source_audit.py; 안전 SOURCE_READ_ONLY;LICENSE_REVIEW;NO_EXTERNAL_DATA; 위험 HIGH
- **MLA-002** REQ-03,REQ-04 Strict canonical immutable PlanSpec/TaskSpec parse, SHA, duplicates, path/glob, dependency constraints and owner approval separation; 경로 src/my_local_ai/contracts/__init__.py, src/my_local_ai/contracts/plan.py, src/my_local_ai/contracts/task.py, tests/unit/test_contracts.py; 안전 NO_EXECUTION;NO_SECRET;PLAN_HASH; 위험 HIGH
- **MLA-003** REQ-15,REQ-23,REQ-24 Reproduce guest receipt spoof failure, record trusted verifier architecture and denial expectations before runtime integration; 경로 docs/SECURITY_MODEL.md, docs/TRUST_BOUNDARY_DESIGN.md, tests/security/test_receipt_forgery.py; 안전 NO_HOST_UNTRUSTED_TEST;F18_HOLD; 위험 CRITICAL
- **MLA-004** REQ-30 Safe synthetic test harness Python 3.11+; low permission CI read-only, no model/network/secret checkout; baseline test exact SHA; 경로 pyproject.toml, tests/conftest.py, tests/unit/test_smoke.py, .github/workflows/ci.yml; 안전 NO_PAID_RUNNER;NO_SECRET;NO_PRIVILEGED_WORKFLOW; 위험 MEDIUM
- **MLA-005** REQ-25,REQ-27 Synthetic metric record schema, no false real speed; 3B/4B comparisons planned but no model invoked by default; 경로 scripts/benchmark_synthetic.py, tests/unit/test_benchmark_contract.py, docs/MODEL_BENCHMARK_PLAN.md; 안전 NO_MODEL_DOWNLOAD;NO_PRIVATE_SOURCE;NO_COST; 위험 LOW

## 실행 운영
1. 브랜치 dev에서 HEAD lease 확인, 사용자 승인된 설계 SHA와 작업 ID 스코프 고정.
2. 서로 독립적인 READY 3~10개를 묶어서 소스/테스트 작성. 실제 파일은 allowed_paths만.
3. 모델 실행/시크릿/네트워크/권한/원본 파일에 영향 있는 변경은 그 즉시 국소 test/fail-closed 검사, 기본 전체 CI 대기는 하지 않는다.
4. 각 변경 뒤 실제 SHA와 소스 경로/기능 근거 기록, STATUS/HANDOFF는 주요 단계에서만 갱신. 전체 분모/가중 근거 없는 +1%p 금지.
5. 기존 안전 기능·F18 HOLD는 유지; 누락되거나 위조 가능한 VERIFIED는 CODE_CANDIDATE_UNVERIFIED로 격하.
6. 모델/보안/원본/구조 고위험 또는 두 번째 진전 없는 실패는 High 판단; 다른 독립 READY 계속.
7. 32 REQ 코드 후보 전수 준비 시 P2 전체 Linux/Windows CI·실사용/보안·회귀로 진입; P3 독립 감사, P4 High 인수/사용자 GO.

## Stop/HOLD
- 외부 API/유료·계정 권한/보안 설정·실 고객자료·GitHub push/PR·OS 자동실행·main 병합은 별도 승인.
- F18 trusted reviewer 실제 완료 전 중요 repo 자동 승격 금지. 주말 통합 시험은 일회용 합성 repo만.
- 새 브랜치 및 PR 자체가 기능 실행 또는 검증 증거가 아님.

## Definition of Done
각 task가 README/코드만 추가했다고 COMPLETE 아님. REQ ID/실제 코드 sha/테스트 커맨드와 PASS·FAIL·SKIP·NOT_RUN/인증·회복·차단 근거를 남긴다. `IMPLEMENTED_UNVERIFIED`와 `VERIFIED` 혼동 금지.
