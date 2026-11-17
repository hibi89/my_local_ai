> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

> **[PRODUCT IDENTITY LOCK · OWNER CLARIFICATION · 2026-11-17]** `my_local_ai`는 **EAI의 후속 버전/확장판/완성판이 아니다.** EAI는 선택적으로 재사용할 알고리즘·CPU 분석·도구의 **기술 제공원**일 뿐이다. `my_local_ai`의 고유 목적은 **로컬 모델로 소프트웨어 구현을 지속 자동화하는 개인용 개발 시스템**이며, 정책·스케줄·실행/검증 게이트·진척 기준은 `my_local_ai`가 자체 소유한다. 원본 EAI ADR-0002(Qwen INPUT-only)는 EAI 원본의 아키텍처 지침이지 `my_local_ai`의 코딩 워커 사용 제한이 아니다. EAI 전체 13개 목표·자체 모델 연구의 100% 완료는 `my_local_ai`의 필수 조건이 아니다. 자세한 내용 `docs/PRODUCT_IDENTITY.md`. **P1 구현 우선/P2 검증 잠금 정책은 그대로 유지.**

# INSTANT_RUNBOOK — My Local AI (2026-11-17)
## 역할·시작
실행 전 확인: hibi89/my_local_ai, dev/instant-implementation-v1, exact SHA → AGENTS/HANDOFF/STATUS → REQUIREMENTS/FINAL_BLUEPRINT/SECURITY_MODEL → actual code+queue. 지금은 **설계 승인 대기**다. 다음 ㄱ은 사용자가 이 계획 승인한 경우에만 P1 실행으로 간주한다. 원본 EAI/AX 코드는 read-only, 비밀은 public repo에 올리지 않는다.

## P0 High 판단
선택 설계: **EAI의 다른 목적을 복제하지 않는** 독립 My Local AI Controller를 자체 구현하고, EAI의 유용한 일부 CPU 분석 기능은 선택적 advisor로, AX 실행기 일부를 provenance+라이선스+테스트 기준으로 재사용. 기존 F18 guest receipt 신뢰 경계가 안전 BLOCKER다. Qwen local coding worker 역할은 AX 안에서만, EAI 내부 Qwen은 INPUT-only.
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

## P1 브라우저 실행 최적화 — 모든 구현 담당 공통
- Codex/Instant/Qwen/OpenCode/선택형 Hydrogen은 **BE와 FE 전부 구현**하되 브라우저 자동 실행·반복 클릭·Playwright E2E·스크린샷 비교·반응형/접근성 전수 검증은 기본 `DEFERRED_TO_P2`.
- P1 성공 기준은 코드·UI 컴포넌트/API 연결·데이터 흐름·테스트 하네스/정확 SHA/문법·타입·필요 최소 빌드/국소 스모크 등이다. 브라우저 E2E PASS를 P1 후보 조건으로 요구하지 않는다.
- 보안·인증/권한/데이터손실/외부전송/F18 위험은 즉시 검사한다. 브라우저가 유일하게 필요한 구현/안전 확인이면 최소 시나리오만 실행하고 사유·정확 SHA·PASS/FAIL/NOT_RUN을 기록한다.
- **P2 전용:** 실제 브라우저/Playwright E2E, 다중 해상도, Console/Network, 키보드/a11y, 전체 통합·회귀. CLI-only면 비대상 근거 기록. 브라우저가 없으면 NOT_RUN. 기존 필수 CI는 끄거나 우회하지 않는다.

## Stop/HOLD
- 외부 API/유료·계정 권한/보안 설정·실 고객자료·GitHub push/PR·OS 자동실행·main 병합은 별도 승인.
- F18 trusted reviewer 실제 완료 전 중요 repo 자동 승격 금지. 주말 통합 시험은 일회용 합성 repo만.
- 새 브랜치 및 PR 자체가 기능 실행 또는 검증 증거가 아님.

## Definition of Done
각 task가 README/코드만 추가했다고 COMPLETE 아님. REQ ID/실제 코드 sha/테스트 커맨드와 PASS·FAIL·SKIP·NOT_RUN/인증·회복·차단 근거를 남긴다. `IMPLEMENTED_UNVERIFIED`와 `VERIFIED` 혼동 금지.


---

## V1.1 설계 참조 — 별도 선택형 멀티워커 큐
2026-11-17 High 설계 브랜치에 Hydrogen ProviderPort, 병렬 격리 워커, 무료 한도·유료 전환 시 자동 OFF/fallback 구조를 추가했다. 상세 `docs/DETACHABLE_MULTI_MODEL_WORKERS.md`, 확장 큐 `docs/OPTIONAL_PROVIDER_TASK_QUEUE.json`.

**기존 MLA-001..030 / P1 28 작업·필수 30 REQ·P2 LOCKED는 그대로.** 이 문서 변경만으로 신규 READY를 자동 할당하거나 구현/검증 진척에 산입하지 않는다. 확장 mock/contract 코드의 허용 경로/의존성은 High가 실제 dev HEAD를 보고 따로 승인. 실제 Hydrogen API·비공개/고객 자료 송신·유료·키·GitHub 원격 쓰기는 owner 별도 GO까지 차단. OFF 이후 Qwen 기본경로 유지와 F18 독립 검증 경계를 보존한다.

### 새 채팅/모바일 `ㄱ` 실행 기준 — 브라우저 후행 재확인
1. 우선 최신 HEAD/AGENTS/HANDOFF/STATUS/REQ/Final Blueprint/queue 확인. P1 READY `MLA-012` 로컬 Ollama loopback guard부터 독립 READY 묶음 실행. 브라우저 테스트 대기/반복으로 P1 중단하지 말 것.
2. P1 수행자는 BE/FE 기능과 API 연결·검증 하네스까지 구현. 실 브라우저/Playwright·스크린샷/반응형/접근성·Console/Network 전수 검증은 `VERIFICATION_TASK_QUEUE.json#MLA-V007`의 P2로 이관. `BROWSER_NOT_RUN/DEFERRED_TO_P2` 기록.
3. 구체 연결: `MLA-019, MLA-021, MLA-025` → `MLA-V007`; CLI-only `MLA-006`은 브라우저 비대상. 전체 CI 수동 재실행/대기는 P1 후행, 기존 필수 CI는 유지.
4. 단, 인증·보안·비밀·권한·데이터 손실·F18 즉시 검사는 무조건 유지. 실제 불가피한 최소 브라우저 예외는 SHA·범위를 기록. 모델/게스트 self-PASS는 검증 증거가 아니다.


## 2026-11-17 P1 IMPLEMENTATION REPLAN — OWNER DIRECTIVE (non-executing code queue)

**Purpose:** unblock P1 BE/FE *code authoring only* without silently treating license, owner signer, reviewer isolation or verification as complete. `INSTANT_TASK_QUEUE.json.first_ready` now lists **P1_CODE_ONLY** tasks whose `p1_code_status=READY_CODE_ONLY`; it grants **no runtime operation**. All original `depends_on` and `status` remain the full acceptance/runtime dependency graph, including `BLOCKED_PROVENANCE` and `F18_SECURITY_HOLD`. New `p1_code_depends_on` expresses *source module authoring dependencies only*. Changing `p1_code_status` NEVER changes `runtime_authorization=HOLD_UNTIL_OWNER_GO_F18_AND_PHASE_GATES` or grants Git/OS/model/remote execution. For actual executor the only valid route is protected owner consent + original acceptance dependencies + independent F18 + pinned SHA + lease + P2/GO; the queue JSON is never a grant. No untrusted original code copying. Source files may be authored and synthetically tested on safe fixtures in P1, with honest `IMPLEMENTED_UNVERIFIED` even if runtime blocked. `scripts/p1_queue_replan.py` rejects missing runtime holds, loosened constraints, incorrect dependencies and fake 100%. This section replaces the older instruction to only edit tasks with `status=READY` for P1 code authoring, **not** the runtime/safety gate.
