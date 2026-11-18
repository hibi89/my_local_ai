# My Local AI V2.0 — MESA + Evidence Gate + AXZERO 최종 통합설계
**확정:** 2026-11-18 KST, 사용자 V2.0 설계 변경 승인 / **유형:** P0 최종설계만 변경
**정본:** hibi89/my_local_ai@design/final-blueprint-v1 / docs/FINAL_BLUEPRINT.md §M
**대조:** dev/instant-implementation-v1@7ffd12c190392c6db675a69a5f5b54ff8ffb6f4a; AXZERO hibi89/Freelancer@product/ax-zero-local@3f55a831cb7f8ab85cd49bc3cee8470d0310d5ac; AXNODE product/axnode-sector-runtime@fa30a28aa61c166b519ddb2663c3620537767f4e
**우선순위:** 사용자 현재 지시 > V1.3 보안·고유 REQ/권리 > 해총 최신 0J/0E > 실제 코드/HEAD > 이 확장 문서의 과거 추정.
**범위 보호:** 기존 MLA 39 SWU + CodeShield 16 SWU = 55 P1 및 30 기본 REQ, 허용경로·의존성·수용조건·2+2 실패 이력은 변경하지 않는다. 이 문서 자체로 P1 구현/검증 완료가 증가하지 않는다.

## 1. 제품 정체성·성공 기준
MLA는 스스로 코드를 작성·검토 요청하는 **로컬 자동개발 Controller**다. MESA(MLA Experience & Strategy Advisor)는 실제 경험을 구조화하여 권한 없는 전략을 추천한다. Evidence Gate는 과거 증거의 현재 적용 가능성만 판정한다. AXZERO는 **검증·승인된 반복 업무를 고정 Typed IR/Operator로 재사용하여 불필요한 모델 호출을 제거**한다. Hydrogen은 승인된 경우에만 문제해결 제안과 독립 코딩 후보를 생성한다. AXNODE는 선택형 패키징/이동 포맷이다. EAI는 별도 제품으로 유지한다.
주요 성과 지표: 동일 수용조건에서 실제 승인된 REQ/시간, 총 경과시간, 모델 호출 수, 재작업·실패율, 검증 비용, CPU/RAM/VRAM. 인과적 효과와 절감 배수는 실제 대조실험 전 UNMEASURED.

## 2. 단일 권한·두 실행 경로
    사용자 CLI/UI → MLA Controller[Plan SHA, REQ/DAG, READY, scope, 2+2, 예산]
        → Evidence Gate[REUSABLE_ADVICE | REVALIDATION_REQUIRED | UNKNOWN | REVOKED]
        → MESA[AdvisorProposalV2, max top-3, 추천만]
        ├─ AXZERO[적격성 검사 + 검증된 Typed Operator/고정 템플릿만, AI 호출 불필요]
        └─ Qwen3 4B[기본 오프라인] / Hydrogen[기본 OFF] → 비신뢰 패치·제안
        → CodeShield 정적 검사 → 보호 Owner 승인·독립 F18·nonce/lease/Git CAS
        → 확인된 범위의 결과/실패/비용 관측 → 로컬 경험 원장
        → MESA 전략 갱신 제안 및 AXZERO 능력 후보 심사

* 실행 경로 A: **사전에 구현·검증된 결정론적 제품 소유 Typed Operator**만 자체 스키마, allowed-effects, 범위, 예산, owner 정책으로 실행 가능. 승인/독립 검수·보호 Git 쓰기를 별도로 요구하는 작업은 경계 유지.
* 실행 경로 B: **모델 생성 코드/테스트/스크립트/EXE/빌드 훅은 절대 자동 실행하지 않음.** 모델 출력은 scratch/worktree의 비신뢰 텍스트·Diff로만 보관. AST/Ruff/Semgrep PASS도 실행 허가·독립 F18·Git 승격 증거가 아니다.
* Worktree는 편집 충돌 분리이지 OS 프로세스 격리·네트워크 차단이 아니다. 두 경로 모두 VM/WSL2/Docker/Windows Sandbox/Hyper-V/Windows 컨테이너/AppContainer 사용 금지. OS 전체 egress 차단은 실증 전 미검증.

## 3. V1.2 중복 제거·모듈 책임
| 구성 | 정본/재사용 | 경계 |
|---|---|---|
| MLA Controller | 기존 controller/decision.py, orchestrator, state | 최종 계획·DAG·승인·실행 가능 여부의 유일한 결정권 |
| MESA | 기존 docs/EXPERIENCE_LEARNING_ENGINE.md V1.2와 EXT-EXP-01..07을 **승계**, 신규 제품/중복 큐 생성 금지 | 관측/검색/실패 분류/전략 후보/사용자 아이디어/회귀 비교, **비권한 AdvisorProposal** |
| 선택형 EAI Advisor | 기존 advisors/eai.py 유효성 검증·READY 힌트 | 별도 제품 EAI의 내부 모듈 개명·필수 import 금지; MESA도 동일 권한 규칙 준수 |
| Evidence Gate | V1.2 evidence filter 확장, V2-GATE-01만 신규 | SHA·의존성·환경·검증 주체/버전·권한 검증, 신뢰 승격 불가 |
| AXZERO | hibi89/Freelancer/product/ax-zero-local 36 REQ·18 P1 작업 소유 | 별도 repo/branch 정본; MLA는 최소 선택형 adapter만 구현; 아직 제품 코드 0/18 |
| Hydrogen | 기존 V1.1 EXT-HYD-01..08 재사용 | 기본 OFF, 0달러 한도, 외부 송신 별도 GO, 미가용/요금 미확인 호출 금지 |
| AXNODE | 기존 별도 AXNODE 브랜치 | 필수 의존성 없음; 선택적 serializer 향후 |
MESA는 '다른 모델'이 아니라 로컬 Python+SQLite/FTS5 기반 전략 엔진이며 두 번째 GPU 모델·모델 파인튜닝을 요구하지 않는다. 기존 EAI 원본은 수정하지 않는다.

## 4. ExperienceRecordV2와 저장
기존 ExperienceEventV1/ExperienceSuggestionV1을 **폐기하지 않고 필드 확장/어댑터 변환**한다. 원칙은 불변 이벤트 + 상태전이 별도 이벤트, 버전 저장, 승인 범위별 삭제/TTL. 로컬 SQLite ONE WRITER 및 기존 APP_ID/버전/백업·복구 정책을 따르고 무승인 마이그레이션 금지. DB 실소유·스키마를 선조회하고 중복 테이블을 피한다.
ExperienceRecordV2 필수 계약:
- identity: experience_id, project_id, run_id, task_id, req_ids, attempt_id, plan_sha256(64), source_git_sha(40), branch_scope
- applicability: environment_fingerprint(OS/Python/toolchain), dependency_fingerprint(실제 읽기·쓰기 영향 집합/계약), input_contract_digest, output_contract_digest, data_class, rights_tag, owner_scope_ref
- strategy: strategy_id, strategy_version, problem_class, failure_class, root_cause_kind(HYPOTHESIS|EVIDENCED), proposed_action_digest, provenance
- observation: outcome(OBSERVED|FAILED|HOLD|CANDIDATE|NOT_RUN), independent_evidence_ref(nullable), receipt_issuer_ref(nullable), evidence_stage(UNTRUSTED|STATIC_ONLY|INDEPENDENTLY_VERIFIED), created_at, revoked_or_expired_at(nullable)
- metrics: duration_ms, model_calls, token_usage, cpu_peak_bytes, ram_peak_bytes, vram_peak_bytes(nullable), retry_count, total_validation_cost_ms, outcome_observed(nullable), measurement_provenance
- integrity: schema_version, record_digest, redaction_version, immutable event_id. 미확인값은 null/UNMEASURED; 0이나 PASS로 채우지 않는다.
물리 테이블은 기존 V1.2 안(experience_events, experience_candidates, skill_versions, retrieval_decisions, experience_approvals)을 재사용·확장한다. 필요하면 performance_observations, quarantine_records, capability_registry **참조 테이블만** 추가한다. 실제 고객 원본·프롬프트 전문·비밀키·토큰·불필요한 경로·대량 코드 복제 금지, 공개 GitHub DB 업로드 금지.
쓰기 시점은 작업 종료/오류 후 관측 이벤트. 모델·외부 제공자의 주장만으로 인증 PASS·Owner GO·성공 라벨 생성 불가. 레코드 중복은 (project,run,task,attempt,event_type,source_sha) 멱등키로 차단. 삭제 요청은 보호된 보존정책과 감사 가능한 tombstone·개인 기록 파기 기능의 별도 승인 후 구현.

## 5. Evidence Gate: '추천 재사용'과 '인증 재발급' 분리
입력: EvidenceQueryV1(project, plan_sha256, source_git_sha, dependency_fingerprint, input/output schema digests, toolchain+scanner+rule SHA, environment, desired_effects, data_class, scope, evidence_refs).
출력: EvidenceDecisionV1(state, candidate_refs, compatibility_reasons, invalidations, permitted_use='ADVICE_ONLY', revalidation_tasks, checked_at, decision_digest).
판정은 **권리/민감도/승인 범위 → 현재 환경/의존성 → 검증 주체·규칙/버전·만료·취소 → 부작용/입출력/경로** 순서. 영향 없는 다른 파일의 SHA 변화만으로 전략 추천을 모두 버릴 필요는 없지만, 이전 검증 영수증은 새로운 source SHA에 대해 재서명·새 독립 PASS로 사용할 수 없다. 변경의 영향 범위가 입증 안 되면 UNKNOWN/REVALIDATION_REQUIRED.
상태: REUSABLE_ADVICE(조건 충족시 추천 가능), REVALIDATION_REQUIRED(검증 필수), UNKNOWN, REVOKED. 시스템 실행 허가/권한/서명은 이 결과에서 절대 생성하지 않는다. revoked/poisoned/expired/충돌 스킬은 검색 격리. 증거 검색 캐시가 안전 게이트를 대신하지 않는다.

## 6. MESA: 최소 실사용과 재설계 정책
단계: (1) 권리·민감도 필터로 실패/성공/중단·사용자 제안 기록, (2) SQLite 메타데이터/FTS5 결정적 검색, (3) Evidence Gate 적용, (4) top-3 AdvisorProposalV2 [strategy_ref, evidence_ids, applicability, reasons, limitations, estimated_cost, confidence_kind], (5) Controller가 안전한 READY 중에서만 참고, (6) 실제 수용 결과에 따라 버전 추천 순위 갱신.
사용자 제안은 CANDIDATE에 기록하며 기계가 곧바로 승인/실행하지 않는다. 적은 표본은 success-rate 확정치 아님; 반례·실패를 함께 보존하고 drift·오염을 격리한다. 경험 DB 없거나 훼손/FTS5 없음/MESA OFF일 때 원래 Qwen·Controller 경로로 정상 fallback.
기존 해총 2+2는 그대로: 실제 무진전 2회 후 그 SWU만 격리·MESA 대안 추천, 달라진 방법 2회, 누적 4회 실패 시 Sol Max 배치. 보안 임계 경로는 0회부터 전문 지원 요청 가능. 모델 상담·문서·조회·CI 폴링은 실패 횟수에 포함하지 않는다.

## 7. AXZERO: 신뢰된 능력만 AI 호출 0 후보
AXZERO는 독립 개발 제품. v1 최소 경계 AXZERO.CapabilityQueryV1(request_id, task_type, input_contract_digest, environment_fingerprint, proposed_effects, source_sha, scope_ref, budget) → CapabilityDecisionV1(decision=EXECUTE_NO_AI|REQUEST_MODEL|REQUIRE_APPROVAL|BLOCK, capability_id, artifact_sha, verifier_ref, policy_digest, verified_input_domain, rollback_ref, actual_model_calls). MLA는 결과를 **참고**하고 원본/승인/F18·효과 정책을 독립 재확인한다.
- 최초 API는 읽기전용 capability 발견/자격 조회와 버전·SHA 검증만. AXZERO 미설치·구현 전이면 Qwen 경로 그대로.
- EXECUTE_NO_AI는 개발자 소유의 **기존 승인 Typed Operator** 또는 별도로 권리·서명·독립 수용된 고정 템플릿이 입력 계약/효과/권한/기기 상한을 정확히 만족할 때만 승인 후보. 임의 합성 코드·패키지·스크립트를 자동 실행하는 기능은 V2 범위 밖.
- 선택 호출 시에도 Controller가 own decision+owner scope+lease를 재검사, 보호된 변경·Git CAS·F18 경계는 독립. 선행 승인 범위 밖이면 REQUIRE_APPROVAL/HOLD.
- AXZERO 새 기능·컴파일러/IR·롤백·호출 제거율의 정본은 AXZERO 브랜치; MLA는 adapter만 보관. AXNODE 내보내기는 후순위, 원장 필수 포맷 아님.

## 8. Hydrogen 문제해결·코딩 2가지 역할
기존 EXT-HYD-01..08 유지. Qwen 무진전 → MESA의 검증된 대안/안전한 재설계 → 남는 문제가 있으면 해당 계정의 실제 무료 자격·모델 ID·쿼터·데이터 전송 scope·사용자 GO를 확인한 경우에만 공개·합성 최소 입력으로 Hydrogen Advisor를 선택. 독립 비충돌 READY가 실제 있고 별도 개발 worker 허용 시 후보 코드 생성 가능하나 직접 파일시스템/셸/GitHub 접근권 없음.
remote_enabled=false, max_spend_usd=0, cost_eligibility UNKNOWN→DENY, model_available UNVERIFIED→DENY, secret/customer/private content→DENY. 무료라고 자동 데이터 전송 승인되는 것이 아니다. 429/401/403/5xx/타임아웃/중복 결과는 기존 V1.1 정책에 따라 bounded HOLD/안전 재할당. Hydrogen 없이 모든 기본 로컬 경로 작동.

## 9. Owner/F18 UI 구조 개선 (기존 SWU-008·021에 흡수)

**2026-11-18 사용자 추가 승인:** 다른 세션 WTS 전달을 폐기하고 [Owner 자체 세션 승인+F18 분리 실행 정본](OWNER_SESSION_F18_APPROVED_REDESIGN_20261118.md)의 서명된 challenge/response 구현으로 확정했다. 이 섹션의 과거 '대체안' 문구는 설계 이력이며, 정적 검수만으로 REQ-14 테스트 완료를 주장할 수 없다. Windows 보호 키·계정·EXE 설치 및 실제 시험은 NOT_RUN.
dev HEAD 7ffd12c190392c6db675a69a5f5b54ff8ffb6f4a에서 3개 Windows 보호 서버 소스는 존재하나 실제 Owner WTSSendMessageW 권한 오류 5, F18 정상·Defender 실검사 NOT_RUN 상태. 55 SWU 기준 52/55 = 94.55%는 코드 큐의 최신 관측치(새 설계 커밋으로 변동 없음). 기존 MLA-SWU-008/021 및 CS-SWU-012의 완료·실기기 증거 없이 100% 처리 금지.
권한 오류의 유일한 해법을 서비스 계정의 광범위한 세션 권한 확대로 두지 않는다. **대체안은 사용자가 별도 로그인한 보호된 Owner 대화형 세션에서 수동 실행하는 승인 UI + 기존 보호 서비스의 서명된 요청/응답**이다.
- Owner UI는 전체 action summary, exact plan/source SHA, scope/effects, TTL, nonce, lease, target file, 승인 후 발생할 일까지 표시하고 기본 거절. 16000자 초과는 조용히 잘라내지 않고 거부/별도 안전보기.
- Owner SID/세션·별도 보호 CNG/TPM 서명 주체·service SCM PID/image·pipe ACL 및 challenge/response·request digest를 검증한다. Controller/coder와 같은 권한 도메인만으로 Owner 독립성 성립 불가; 별도 신뢰 주체 없으면 HOLD. 단순 UI 클릭/프로세스 입력값을 Owner 서명으로 취급하지 않는다.
- 별도 UI가 Owner 자신의 인터랙티브 세션에서 실행되는 것은 **WTS의 타 세션 메시지 발송** 권한에 덜 의존하게 하는 설계안이며, 현재 환경에서 작동 검증되지 않았다. 실제 권한 최소화·인증/키 접근·설치·ACL·서비스 변경은 별도 Owner 승인과 원상복구 절차 필요.
- F18 정적 검수 서명은 STATIC_ONLY. 기존 REQ-14의 '독립 테스트 실행' 요구를 충족했다고 주장하지 않는다. 실행 금지 Zero-VM V1.3과의 수용조건 충돌을 별도 High/Owner 판정 후 매핑하며, 자동 합격/테스트 실행은 금지.
- 보호 서비스·Defender 스캐너 소스는 기존 V1.3 코드에 두고 V2 확장 때문에 재구현하지 않는다. CodeShield/Owner/F18/nonce/lease/Git CAS가 AXZERO/MESA/외부 워커보다 우선.

## 10. 실행 리소스·프라이버시
목표 PC: Windows 11 Pro, GTX 1050 Ti VRAM 4GB, RAM 16GB, Python 3.11, Ollama Qwen3 4B 1개. MESA/AXZERO 기본 경로에 추가 상주 AI/GPU/VM 없음. 로컬 Python·SQLite 중심, FTS5 없으면 INDEX 검색 fallback, top-k<=3, bounded DB/event size/retention, 검사기 순차 실행. 시스템 전체 egress/성능 수치·VRAM 절감 배수는 UNMEASURED. 외부 API/클라우드/유료/고객 자료 전송/Windows 정책/신규 권한/main/Production/상용 출시 별도 승인.

## 11. 실행 단계와 분리된 분모
**A — 기존 MLA V1.3 보존/완성:** dev 최신 HEAD·실제 보호 서버/Windows 권한 오류 5·REQ-14 충돌 확인. 기존 55 SWU·30 REQ·8 P2/별도 감사 유지; 현재 52/55 후보, P2 LOCKED, UNASSESSED. 설계 승인 자체로 실제 서비스 GO 없음.
**B — MESA 최소판:** 기존 EXT-EXP-01..07에서 schema→로컬 관측 수집→검색→전략 후보→Controller 비권한 연결→CLI/FE 조회. 원래 작업 이력/allowed_paths 보존. 순차 구현할 때 다른 유효 READY와 충돌 검사.
**C — AXZERO 독립 개발:** AXZERO 원본의 AXZ-001/003/006부터 기존 18 SWU 큐 진행; MLA 작업자 임의 원본 변경 금지. MESA 수집은 AXZERO 완성 없이 가능.
**D — 신규 V2 연결:** docs/OPTIONAL_V2_INTEGRATION_TASK_QUEUE.json 5개 신규 수직 SWU: Evidence Gate(1), AXZERO read-only adapter(1), 적격성·효과 판정(1), bounded typed-op bridge(1), A/B metrics(1). AXZERO 부재 시 해당 브리지만 HOLD, MESA/MLA 정상.
**E — Hydrogen:** 기존 EXT-HYD-01..08 설계 재사용; mock transport부터. 실제 API·키·무료 티어/전송 승인은 별도.
**F — AXNODE:** 후속 선택형 이동/패키징, 필수 의존성 아님.
기존 경험학습 7 SWU + 신규 V2 접점 5 SWU = **별도 확장 12 SWU 계획**(기존 기본 55와 더하지 않음). Hydrogen 기존 8개는 또 다른 독립 선택형 큐. AXZERO 자체 18 SWU는 원본 repo 집계. 과거 28개 legacy task, 39 MLA SWU, 16 CodeShield SWU를 중복 합산하거나 변경하지 않는다.
P1 V2 확장 소스가 READY 되려면 해당 확장 구현 범위·권한·보안 경계를 승인받고 별도 상태 전이한다. P2(기본·확장)는 실제 검증/결함 수정/Win11/F18/브라우저/복구를 독립 수행한다. 문서 저장·Mock/계약/테스트 수만으로 SWU 완료 처리 불가.

## 12. 수용조건/검증 표준
- AXZERO/MESA/Hydrogen/FTS5 OFF·미설치·오류여도 기존 MLA 기본 경로 회귀 없음.
- 같은 오류가 재발하면 권리 필터·실제 의존성 기준 top-3 경험 추천. 위조·충돌·오염·실패/유효기간 만료·다른 프로젝트 자료 거부.
- source SHA나 rule/환경 변경 후 인증 재발급/승격 0; '재사용 추천'만 가능. 과거 비독립 PASS를 독립 증거로 전환하지 않음.
- 사용자 해결법은 CANDIDATE, 실제 독립 증거/승인 전 자동 실행·기능 편입 없음.
- 상태/복구/승인·폐기/중단 및 idempotent 재시작, 권한·scope·lease·nonce·원본 보호 유지.
- 변경 영향 없는 전략 조회는 가능하되, 신뢰 증거로 사용하려면 현재 수용조건으로 재검증.
- 실제 성능: 동일 시작 SHA, 입력 범위·데이터 등급·수용 기준·독립 검수·실행 비용으로 MESA/AXZERO OFF vs ON 비교. 총 경과시간·검증 비용 포함, 표본 부족/측정 불가면 UNMEASURED.
- VRAM 점유 추정/AI 호출 제거율·속도 향상·'학습 완료'를 증거 없이 주장하지 않는다. 즉시 안전 검사와 P2 전체 검증/독립 감사 차단을 유지.

## 13. 인계/변경 금지
이번 변경은 **P0 설계**. 기존 dev HEAD·AXZERO·AXNODE·EAI·해총 중앙 원장·Windows 서비스/TPM/계정/ACL·실사용·외부 API를 건드리지 않는다. STATUS/HANDOFF 기준 SHA는 그 브랜치가 실제 가리키는 값이며 설계 커밋만으로 P1 구현률 0개 진전.
후속 개발자는 최신 HEAD, AGENTS→HANDOFF/STATUS→REQUIREMENTS/§M→기존 55 SWU와 확장 큐→실제 코드 순으로 비교; 기존 MESA V1.2/EXT-EXP-01..07, Hydrogen V1.1/EXT-HYD-01..08, AXZERO 36 REQ/18 SWU는 유지하면서 필요한 호출자→기능→결과를 코드로 구현한다.
