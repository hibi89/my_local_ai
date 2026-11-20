> **[2026-11-18 KST · OWNER-APPROVED OWNER-SESSION/F18 EXECUTION REDESIGN]** `§N` and [Owner 자체 세션·F18 분리 설계](OWNER_SESSION_F18_APPROVED_REDESIGN_20261118.md) are now authoritative for MLA-SWU-008/021 implementation. WTS cross-session delivery is replaced by separately pinned interactive Owner UI+signed challenge/response; REQ-14 executed tests remain UNSATISFIED under Zero-VM. No OS install/ACL/key/go/verification is authorized by document commit alone. P1 source candidate counts unchanged until actual acceptance.

> **[2026-11-18 KST · OWNER APPROVED V2.0 DESIGN CANONICAL]** Current V2.0 scope: [§M and MLA_V2_FINAL_ARCHITECTURE_MESA_AXZERO_20261118.md](docs/MLA_V2_FINAL_ARCHITECTURE_MESA_AXZERO_20261118.md). MESA inherits existing V1.2 EXT-EXP-01..07; Evidence Gate + AXZERO bridge are optional additions; Hydrogen V1.1/AXNODE optional; existing V1.3 Zero-VM security and 55 SWU remain unchanged. Design commit only, not implementation/OS/remote/API approval. Historical progress below is superseded by actual dev HEAD + task queues.

> **[2026-11-18 KST · OWNER NO-VM NO-CONTAINER CANONICAL OVERRIDE]** 최신 사용자 확정 설계: **VM·Windows Sandbox·Hyper-V·WSL2·Docker·Windows 컨테이너·AppContainer 설치/실행/선택적 fallback 의존성 0**. 이전 J/K절에 남은 fallback·AppContainer 후보는 모두 폐기한다. **CPU-first Pure Player + 검증된 허용목록 Typed Operator + 비실행 CodeShield + 로컬 Qwen 하나**가 기본이다. 임의 AI 생성 코드/테스트/스크립트/패키지 훅은 실행하지 않고 HOLD한다. 격리 Worktree는 OS 보안 격리가 아니다. 별도 보호 소유자 승인·독립 F18·nonce/lease·Git CAS·원본/비밀/외부 송신 안전조건은 완화하지 않는다. 변경은 설계에 한하며 Codex 작업 중인 dev 소스/실기기 안전 증거는 그대로 미검증이다.

> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

> **[PRODUCT IDENTITY LOCK · OWNER CLARIFICATION · 2026-11-17]** `my_local_ai`는 **EAI의 후속 버전/확장판/완성판이 아니다.** EAI는 선택적으로 재사용할 알고리즘·CPU 분석·도구의 **기술 제공원**일 뿐이다. `my_local_ai`의 고유 목적은 **로컬 모델로 소프트웨어 구현을 지속 자동화하는 개인용 개발 시스템**이며, 정책·스케줄·실행/검증 게이트·진척 기준은 `my_local_ai`가 자체 소유한다. 원본 EAI ADR-0002(Qwen INPUT-only)는 EAI 원본의 아키텍처 지침이지 `my_local_ai`의 코딩 워커 사용 제한이 아니다. EAI 전체 13개 목표·자체 모델 연구의 100% 완료는 `my_local_ai`의 필수 조건이 아니다. 자세한 내용 `docs/PRODUCT_IDENTITY.md`. **P1 구현 우선/P2 검증 잠금 정책은 그대로 유지.**

# My Local AI — High 전체 최종설계 V1 후보
**작성 2026-11-17 KST. 사용자 요청에 따른 새 저장소 설계 정본; 구현/검증 완료 주장 아님.**

## A. 비전·성공조건
GPT-6 High가 한 번 작성한 최종설계의 전체 REQ-ID/의존성/허용 경로/수용조건을 PC가 지속적으로 처리한다. 하나의 Qwen 로컬 코딩 워커가 구현·1회 수정하고, 독립 검증기가 안전 여부를 결정한다. 실패 작업은 HOLD하고 독립 READY를 계속 진행하며 재부팅 후 중복 작업 없이 복구한다. 목표는 **BE/FE 구현완성률 100% 후보까지 로컬 AI가 수행**; 전체 검증률 100% 자동화는 확장 목표. UI 디자인은 외부 Astra 검수로 보완할 수 있다.

초기 기기: Windows 11 Pro/GTX1050Ti/RAM16GB, 기존 Ollama Qwen3 4B. **My Local AI 자체 Controller 중심**, Python3.11/SQLite, Git worktree, OpenCode 연계. EAI 분석 모듈은 필요한 경우 선택적 부속 기능으로만 사용한다. 무료·오프라인 기본; 외부 모델/유료 API 기본 OFF.

## B. 아키텍처 대안(비용·성능·유지보수)
| 방식 | 성능/속도 | 비용 | 위험 | 결론 |
|---|---|---|---|---|
| A EAI 단독 100% 완성한 다음 AX 병합 | 중복 개발로 통합 늦음 | 무료지만 모델 코딩기 재구축 | 변경 많음 | 제외 |
| B 두 기존 repo를 런타임 필수 의존성으로 연결 | 빠른 임시 시범 | 무료 | 버전/설치/복구 복잡 | 초기 비교 실험에 한정 |
| **C 새 repo에 검증·라이선스 확인한 모듈만 선별 이식** | 기존 코딩기 재사용, 최종 단일 실행 | 무료 중심 | 이식 경계 검수 필요 | **선택** |

결론: 원본 EAI/AX repo·브랜치/main은 보존, 새 `my_local_ai`에 **고유 Controller·계획 검증·작업 큐·TrustedReviewBoundary·SQLite·CLI**를 구현한다. EAI의 일부 CPU 알고리즘은 보조 도구로 **선택적 재사용**하고, AX 코딩 실행기는 감사 후 필요한 기능만 선별 이식한다. EAI의 13개 typed goal이나 독립 AI 자체 모델 연구를 그대로 이식·완료할 필요는 없고, 원본 EAI 제품의 범위를 축소·변경하지도 않는다.

## C. 기능 범위
1. High 최종설계/REQ-ID·작업 스펙 검증, 정확 Git SHA/문서 SHA 고정, DAG/READY 스케줄.
2. **My Local AI Controller:** 승인된 작업 계획의 DAG·안전 규칙·실행 우선순위·HOLD를 직접 결정한다. EAI에서 가져온 CPU 분석기는 유용한 작업 순위/근거를 제안하는 **선택적 advisor**일 뿐, 필수 의존성이나 최종 승인자가 아니다. 원본 EAI 자체의 INPUT-only 설계는 해당 제품에만 적용한다.
3. AX: 단일 로컬 Qwen 코딩 모델, Ollama localhost, OpenCode 허용된 편집 도구, 격리 Worktree, source/read-only preflight.
4. 모델 비신뢰 결과 → 정확 diff/변경 경로·출처 검사 → **모델과 분리된 신뢰 검증기**가 검증. 인증 경계 불충분 시 CODE_CANDIDATE/HOLD.
5. 실패 1회 개선 재시도 후 HOLD; 무관 작업은 계속, 의존 작업은 보류.
6. SQLite WAL 작업 상태/lease/fencing/idempotency, checkpoint/resume, crash/restart/전원 중단 증거와 보존.
7. 시간/RAM/VRAM/CPU/토큰·성공률/실패 원인·비용 측정; 장시간 운영감시. 1 모델 동시 상주, 자원 초과·발열·절전 안전 중지.
8. CLI: doctor, plan validate/approve, queue status/start/stop/resume, benchmark, evidence export. FE는 사용성 중심 로컬 최소 상태판(후순위), 자동 브라우저 운영 기본 OFF.
9. 사용자 GO 없이는 GitHub remote write/PR, OS startup 등록, 외부 API, 고객 원본 수정, 결제/배포/판매 불허.

## D. 실행 데이터 흐름
`High Plan(immutable SHA) → Owner Scope GO → My Local AI Controller(필요하면 EAI advisor의 제안 참고) → validated WorkOrder → lock/lease → isolated Git worktree → Ollama/OpenCode coder → untrusted candidate diff → trusted independent review → verified isolated local ref OR HOLD → evidence ledger → next READY`.
모델/게스트가 생성한 `VERIFIED` 문구를 신뢰하지 않는다. 독립 reviewer가 명세/테스트/원본 SHA를 별도 권한 경계에서 검증한 뒤에만 승인 가능한 결과가 된다.

## E. BE/FE/DB/API/보안 범위
- BE: Python3.11 모듈 `contracts/controller/advisors/ax_runtime/runner/review/state/git/adapters`. EAI 유래 코드만 `advisors/eai`처럼 선택적 경계에 격리하고, EAI 실행 없이 기본 경로를 유지한다. 외부 HTTP 포트 필요 없음. 예외적으로 로컬 상태 대시보드는 별도 Host/CSRF/권한 통제.
- FE: 먼저 사용자용 CLI/터미널 출력(REQ 진행, HOLD, 남은 READY, CPU/RAM, model 상태, 수동 승인, stop/resume); GUI는 기본 기능 정상 후 별도 Astra 심사. 서버 UI는 예쁜 디자인보다 원본 보호와 상태 진실성 우선.
- DB: 로컬 SQLite one-writer/WAL, `plans/tasks/runs/leases/attempts/reviews/integration/events/owner_consents`. 사전 백업 없는 migration 금지. 고객 자료·모델 프롬프트 원본 DB/원격 저장 금지.
- API 계약: versioned PlanSpec→optional AdvisorProposal(EAI 포함, 비권한)→My Local AI WorkOrder(approved scope immutable)→CandidateDiff(untrusted)→TrustedReceipt(independent)→Git local ref. SHA-256+RunID+lease epoch+허용경로로 전수 확인.
- 보안: 공개 repo 비밀 zero; Git hooks/filter/reparse/symlinks/ignored path/TOCTOU, 격리/환경변수, 프롬프트 주입, 위조 영수증, 외부 egress, 중복 작업/원본 훼손, 비용과 no-admin 원칙 전수.
- 시간: 한 작업이 너무 오래 걸리지 않도록 wall-time, model call, diff/파일 수·컨텍스트 예산을 per task로 설정하되 실제 1050Ti 성능은 실측 전 고정 보장하지 않는다.

## F. P0→P5
- **P0 HIGH** (설계 정본): 기존 REQ-01~32 체계·수용표·브랜치·안전/기술선택 및 승인된 V1.3 CodeShield 경량 운영을 보존한다. 현재 P1 분모는 기존 30 REQ / 39 SWU이며, 설계 문구를 구현 또는 사용자 실운영 승인으로 간주하지 않는다.
- **P1 웹 GPT-6 Sol High (현재 구현 담당)**: 해총 §0J/§0E CPAA→WE로 실제 READY 1~6 SWU 단위 기능 소스 구현·필수 국소검사·GitHub 커밋 수행. 2026년 12월 정책의 실제 적용과 사용자 전환 결정 전에는 Instant로 자동 변경하지 않는다. 현재 dev 기준 35/39 후보, 네 필수 신뢰 SWU 008/015/021/031은 BLOCKED_TRUST 및 READY 0개이며, 인가 없는 원본/OS 변경·가짜 READY 금지. P2 전체 검증은 후행.
- **P2**: 후보 구현 전수 후 전체 CI·통합·회귀·권한·Windows 11 Pro 실기기·실 Qwen/OpenCode·격리·24h 안정/복구 검증 및 결함 수정.
- **P3**: 같은 exact SHA의 Codex Sol Max 기술/보안 + Astra Max 사용성/FE 독립 검수(실행 없으면 NOT_RUN).
- **P4**: High 전수 인수, BLOCKER/HIGH 해결. 안전한 개인 실사용은 사용자 GO.
- **P5**: 이후 별도 승인된 상품 생산 워크플로 확장. 크몽 등록/상용화는 본 도구의 자동 GO가 아니다.

## F-1. 브라우저·Playwright 검증 후행 실행 정책 — 2026-11-17 사용자 확정

목표: P1은 BE/FE 실제 구현완료율 100% 후보 확보에 집중하고, 브라우저·Playwright 전수 검증은 P2에서 한 번에 수행한다. Codex/Instant/Qwen/OpenCode/선택 Hydrogen 구현 워커 모두 동일하게 적용한다.

| 항목 | P1 구현 | P2 검증 |
|---|---|---|
| BE/DB/API 및 FE | 필수 코드·계약·연결·상태/사용 흐름·테스트 하네스 작성, 정확 SHA 근거 | 실제 기능·통합·회귀 실행 PASS 판정 |
| 빠른 검사 | 문법·타입, 필요 최소 빌드, 변경 범위의 국소 스모크, 필수 보안 즉시 검사 | 전체 빌드/CI·보안·통합/회귀 |
| 브라우저/Playwright | 기본 `DEFERRED_TO_P2`; 반복 클릭/E2E/스크린샷/다해상도/접근성·반응형 전수 검증 보류 | 웹 UI가 있을 때 실제 브라우저 E2E, 핵심 버튼/폼, Console/Network, 키보드/a11y·반응형 검사 |
| 증거 | `IMPLEMENTED_UNVERIFIED`, 브라우저 미실행은 `NOT_RUN` | 실행 환경·정확 SHA·PASS/FAIL/SKIP/NOT_RUN/비대상 근거 |

예외: 인증/인가·결제·권한·고객/원본/DB 손실·비밀·외부 전송·F18 경계 등 고위험 변경 또는 실제 브라우저가 없으면 필수 구현 자체를 확인할 수 없는 상황에서는 그 위험/기능을 확인하는 최소 시나리오만 P1에서 즉시 수행한다. 예외의 사유·범위·명령/시나리오·정확 SHA·실행 결과를 기록하며, 이를 전체 브라우저 PASS로 승격하지 않는다.

브라우저가 미가용이면 `NOT_RUN/BLOCKED`로 두고, CLI-only 기능은 브라우저 검증 비대상임을 증명해야 한다. Playwright나 브라우저 검사 때문에 P1 구현을 반복 정지시키지 않는다. **기존 필수 CI/브랜치 보호는 해제·우회 금지**이며, 문법/타입/국소 스모크와 인증·권한·데이터 손실·F18 보안 즉시 검사는 유지한다. P2 진입은 기존 `WORK_PHASE_GATES.json` 잠금/High/정확 코드 SHA 조건 충족 후에만 가능하다. 기존 P1 30 REQ·28 작업/P2 8 작업 및 선택형 Hydrogen 큐의 분모와 승인 상태는 변하지 않는다.

## G. 일정 목표 및 현시점
2026-11-17: 설계/브랜치 세팅. 11/18~20: 승인 후 P1 코딩. 11/21~22 주말: 합성 통합 시험 및 기기 실측을 **목표**로 함. PC/격리/모델 접근이 막히면 부분완료+HOLD로 정직하게 보고. 24시간 성공·상품화 속도·추론 품질은 실측 전 미확정.

**완성률:** 구현 후보 = 최종설계 전체 REQ에 해당 코드/근거 존재, 공식 검증률 = 승인 가중치별 실제 수용조건 PASS, RELEASE GO = 운영/권리/실기기/보안과 사용자 별도 승인. 이 설계 작성만으로 수치 상승 없음. 현재 새 repo는 구현 및 검증 `UNASSESSED`.

32개 요구사항은 REQUIREMENTS, 테스트/증거는 ACCEPTANCE_MATRIX, 안전은 SECURITY_MODEL, 데이터/버전은 별도 docs, P1 원자 구현은 INSTANT_TASK_QUEUE.json, P2 전체 검증/후행 검수는 VERIFICATION_TASK_QUEUE.json, 실제 진행 허용은 WORK_PHASE_GATES.json 정본.


---

## H. V1.1 확장 확정 설계 — 탈부착형 Hydrogen 병렬 구현 워커 (2026-11-17 KST)

**사용자 신규 결정 반영:** My Local AI는 Qwen 로컬 기본 코딩 + 선택형 Hydrogen API 병렬 코딩을 지원하도록 **ProviderPort 플러그인 설계**를 채택한다. Hydrogen을 수동 챗봇/단순 검증 도구로 한정하지 않으며, 별도 독립 READY의 **BE/FE 구현 후보를 실제로 생성**할 수 있는 코딩 워커로 설계한다. 기존 High 설계 → Instant 구현 → 후행 P2 전체 검증 → Codex Sol Max/Astra Max 독립 감사 → High 인수 순서는 유지한다.

### H-1. 구성과 대안
- **채택 C:** My Local AI 자체 Controller → 승인된 DAG/allowed_paths/approval SHA → capability/privacy/budget scheduler → (A) 로컬 Qwen/OpenCode + (B) 원격 Hydrogen ProviderAdapter(기본 OFF) → 워커별 분리 Git worktree/lease → untrusted patch → F18 신뢰 독립 검증 → 격리 로컬 ref/HOLD → SQLite.
- 기각 A: Hydrogen 필수 엔진(무료 종료·네트워크 장애 때 전체 개발 중단). 기각 B: n8n/각 상품별 Hydrogen 직접 연결(승인·비용·비밀 분산). 별도 n8n 서버는 필수가 아니며 Python/SQLite 큐로 우선 구현.
- 웹 GPT-6 Instant는 외부 API에서 자동 호출할 수 있다고 가정하지 않음: 현재 GitHub 큐를 따라 사람이 별도 개발하는 lane. Codex는 이 ProviderPort·안전 실행기를 **개발할 수 있는 도구**이나 Codex CLI가 Hydrogen 모든 tool capability를 네이티브로 지원한다는 보장 없음.

### H-2. 목표 동작
1. High 설계의 `plan_sha256`, source SHA, task/REQ, owner scope 검증. EAI advisor는 non-authoritative 추천만; EAI 원본 INPUT-only/13 goals와 혼동 금지.
2. Qwen은 로컬에서 계속 구현. Hydrogen은 **별도 API 호출 승인이 있고** 정확한 비민감 공개/합성 입력, 무료 티어/프로젝트 쿼터, 독립 작업 경로, 격리 runner, 데이터 정책이 모두 통과할 때만 동시 READY에 배정.
3. 모델과 무관하게 각 워커는 같은 `WorkerRequestV1`/ `WorkerResponseV1` 비신뢰 계약을 따른다. 모델이 파일이나 셸/원격 GitHub/테스트 PASS·권한 승격을 직접 수행하지 않으며, 로컬 executor와 별도 trusted reviewer만 적용/판정.
4. API 키 없음, 유료 전환, 무료 한도 429, owner OFF, 401/403, 보안 정책 실패 → Hydrogen만 OFF/HOLD. 중단 체크포인트·source SHA/epoch 대조 후 로컬 Qwen에 **재배정 가능 후보** 생성. 새 로컬 모델까지 자동·중복 실행 금지; 웹 Instant는 큐 제안만.
5. Hydrogen 후보는 **안전한 분리 브랜치/로컬 ref에 통합되어 실제 source SHA와 구현 근거가 확인될 때만** 기존 30 REQ 구현 분자에 기여. P2 전체 CI/보안·실기기는 P1 100% 후보 후 별도. Hydrogen이 Codex·Astra의 독립 감사 역할을 대체하지 않는다.

### H-3. 데이터·안전·비용
- `remote_enabled=false`, `network_egress=deny`, `max_spend_usd=0` 초기값. 비용 미확인·무료 자격 미확인 시 **FAIL CLOSED**, 무료 티어가 있더라도 무상·무제한·고객 자료 업로드를 허용하는 것으로 보지 않는다. 계정별 실제 rate limit과 모델 ID/SDK 동작은 별도 확인.
- 승인 없는 외부 API 호출, 고객/비공개 저장소·토큰·.env/개인경로/프롬프트 원본·DB·해커톤 비공개 자료 외부 송신 금지. 키는 공개 GitHub·SQLite·로그에 저장 금지.
- 워커별 격리·경로 충돌/공통 파일 잠금·Git lease/fencing·멱등 복구·1회 개선 재시도/독립 HOLD, F18 forged receipts 차단. 유료 결제/권한·보안 설정/원본/remote PR·main/Production/실사용은 사용자 별도 GO.

### H-4. BE/FE/DB/API·수용·단계
- BE: `providers/base.py,registry.py,policy.py,local_qwen.py,hydrogen.py` ProviderPort, capability/eligibility/budget guard, parallel scheduler, isolated runner, failure circuit breaker, checkpoint; 실제 dev 코드와 충돌 없는 이름으로 구현 전 재검토.
- DB 확장안: `provider_registry/provider_quota/worker_assignments/provider_calls/provider_approvals` (로컬 SQLite, 백업·안전 migration 필수). UI/CLI: 읽기전용 provider 상태·OFF/429/무료 자격·작업/비용 상한 표시; 별도 GO 없는 원격 ON 금지.
- API: `WorkerRequestV1`(immutable plan/source SHA, owner scope, req_ids, allowed_paths, worker epoch, budget, data_class) → `WorkerResponseV1`(untrusted candidate diff, SHA, model, usage) → **독립** `TrustedReceiptV1` → local protected ref/HOLD.
- 수용: HYD-AC-01~10 (오프라인 회귀, 허용 독립 병렬, 429/유료 자동 OFF, 비밀 송신 차단, F18, 복구/중복, 12 합성 작업 성능 비교); 정확 조건은 [탈부착형 워커 정본](DETACHABLE_MULTI_MODEL_WORKERS.md).
- **기존 REQ-01~30 / P1 28 작업·REQ-31~32 후행 / P2 8검증 불변.** 확장 `EXT-01~08`은 [별도 선택형 큐](OPTIONAL_PROVIDER_TASK_QUEUE.json)의 설계 항목이며 실 API 호출이나 P1 분모 변경은 별도 승인/기준선 개정 전 금지. 기존 Instant 구현은 계속.
- P1 기본 구현·즉시 안전 검사 우선; 확장 모듈은 mock/contract부터 별도 작업으로 검토 가능. P2 LOCKED, 라이브 Hydrogen API/계정 권한/돈/원격 전송/개발 브랜치 자동 병합은 아직 **NOT_RUN/NOT_APPROVED**.

Google 공개 2026-11-12 모델 카드: https://deepmind.google/models/model-cards/gemini-4-hydrogen/ ; Gemini API 무료/유료 가격: https://ai.google.dev/gemini-api/docs/pricing ; 모델별·프로젝트별 변동 한도: https://ai.google.dev/gemini-api/docs/rate-limits . 무료/유료·기능 지원은 실제 계정 사용 전에 다시 확인한다.

**전체 세부설계:** `docs/DETACHABLE_MULTI_MODEL_WORKERS.md` · **작업큐:** `docs/OPTIONAL_PROVIDER_TASK_QUEUE.json`. 이 확장은 문서 설계만 반영한 것으로, 구현완료율·검증완료율을 상승시키지 않는다.

---

## I. V1.2 Experience Learning Engine — 경험 기반 적응형 개발 시스템 (2026-11-17 사용자 확정)

**확정 설계 방향:** My Local AI는 매 상황의 수백·수천 변수를 하드코딩하거나 Sol Max의 대량 답변을 모델 학습용으로 축적하지 않는다. 자신의 합법적·비민감 개발 작업에서 발생한 실제 오류, 선택한 수정, 독립 테스트 결과, 재작업·복구 기록을 분석해 **재사용 가능한 SKILL.md·자체 코드 템플릿·작업 분할/도구 선택의 추천**을 점진적으로 개선한다. 학습은 **MLA의 SQLite 기반 외부 경험 메모리/선택 정책**을 뜻하며 Qwen·기타 모델의 가중치 수정이 아니다.

**대안:** A 많은 고정 규칙/AXNODE 우선(조합 폭발), B Sol Max 답변 대량 수집·대체 모델 학습(비용·오염·권리/정책 위험), **C 실제 자기 개발 경험→독립 검증→지식 선별→가역적 스킬 추천(선택)**. 초기 실행은 Python3.11/SQLite·FTS5 가능 시 선택형 검색, 템플릿·SKILL.md 버전 관리. AXNODE는 검증된 뒤에만 선택적 graph/export adapter로 사용하며 독자 바이너리 런타임을 필수로 만들지 않는다.

**흐름:** approved PlanSpec/DAG/owner GO → read-only ExperienceSelector(권리/민감도/환경/버전·안전 필터, 근거 있는 사례 top3) → Qwen/OpenCode 또는 승인된 선택형 워커 → 격리 CandidateDiff → **독립 F18 수용 결과** → redacted 자기 경험 이벤트 → quarantine/curation → synthetic A/B 및 owner 승인 → versioned skill 활성·취소. 어떤 모델의 답변도 test PASS·안전 승인·원격 송신 권한이 아니다. 경험 없는 상태/오염·충돌/DB 오류에도 기존 로컬 Controller와 Qwen이 정상 동작한다.

**필수 안전:** 소스/계획 SHA·REQ/allowed_paths·권리·고객/비공개·비밀 데이터 차단, 원본·승인·돈0·GitHub 브랜치 보호/F18 검증 경계 우선. 외부 Sol Max/API의 출력은 허가된 소프트웨어 개발 과정의 참고사항일 수 있으나 대체 AI 모델 훈련용 데이터·선호 라벨·보상/평가 과제의 대량 선별·생성이나 비공개 reasoning 추출을 하지 않는다. 공개 GitHub에는 코드·합성 스키마만; 실제 기록/프롬프트/고객·개인 로그는 로컬. 장기보존/삭제·사용 목적·서비스별 약관·승인은 별도 검증.

**수용·단계:** `EXP-AC-01..10`, 별도 선택형 `EXT-EXP-01..07` 큐. 처음에는 기본 OFF와 합성·읽기전용 관찰만 후보, 성능 실측 전 지능 향상·Codex 대체율·검증 PASS 주장 금지. **기존 P1 30 REQ·28 구현작업, P2 8검증/LOCKED, Hydrogen EXT-HYD-01..08, P1 브라우저 DEFERRED_TO_P2 모두 불변**. 이 확장은 이번 사용자 요청으로 **설계 반영**한 것이며 즉시 새로운 P1 READY/분모 변경/실사용 데이터 수집 승인이 아니다.

**정본:** `docs/EXPERIENCE_LEARNING_ENGINE.md` · `docs/OPTIONAL_EXPERIENCE_TASK_QUEUE.json`.

---

## J. V1.3 CodeShield — 경량 사전검수 기본 아키텍처 (사용자 2026-11-17 확정)

**확정:** 모든 VM/Windows Sandbox/Hyper-V/WSL2/Docker 및 Windows 컨테이너/AppContainer 실행·가동·fallback 의존성을 **0**으로 배제한다. EAI의 CPU-first Pure Player 원칙을 MLA 자체 Controller/검증된 Typed Operator registry로 재구성한다. 호스트 Qwen 단일 모델은 코드/패치를 **비신뢰 데이터로 작성**하고, Python AST·경로/Git guard·Ruff S·로컬 Semgrep CE·선택적 오프라인 Gitleaks/OSV·기존 Defender의 읽기/범위 제한 보조 검사를 **코드 비실행 상태로 순차 수행**한다. 추가 GPU 상주 모델/두 번째 백신/원격 유료 서비스 없음. 기술·위험 범위는 docs/CODE_SHIELD_LIGHTWEIGHT_SECURITY_V1_3.md를 따른다.

**절대 불변:** CodeShield PASS는 생성 코드·테스트·설치 훅·외부 실행 파일·셸을 실행해도 된다는 뜻이 아니다. VM/컨테이너 fallback이 없으므로 **임의 생성 코드 실행은 현재 아키텍처 범위에서 HOLD**이며 검증 전 호스트 직접 실행으로 대체할 수 없다. 검증된 자사 Typed Operator만 별도 승인된 권한 범위·고정 argv·무동적 스크립트에서 수행한다. 보호된 소유자 서명, 독립 F18, nonce/lease/CAS, 원본/비밀·Defender CFA/ACL/Windows 보안/방화벽·Git main/Production 안전 게이트는 보존한다.

**단계/지표(2026-11-18 기준):** 기존 **30 REQ / 39개 P1 SWU(완료 후보 35/39) / 28개 legacy 작업**, P2 8개 검증 LOCKED 및 V1.1 Hydrogen/V1.2 경험학습을 보존한다. `CS-01..08`은 과거 CodeShield **8개 설계 작업군**이며 최신 SWU 재분할 기준은 **16개 SWU, 별도 `feature/code-shield-lightweight-v1`에서 소스 구현 후보 13/16**이다. 나머지 `CS-SWU-007/012/014`는 미완료이며 실제 Windows OS 브로커/F18/egress는 NOT_RUN/HOLD다. **별도 feature 구현은 dev 브랜치에 자동 통합된 것이 아니며**, 원래 35/39 분자와 혼산하거나 소스 기능·P2 검증 PASS·실운용 허가로 인정하지 않는다. CodeShield 큐와 기술설계는 해당 기능 브랜치와 본 설계 브랜치에서 구분하여 관리한다.

---

## K. 2026-11-18 최종 실행·검수 경로 — VM/Windows 컨테이너 의존성 0, Pure Player 기본

**임무·기기 잠금:** MLA는 EAI의 후속 제품이 아닌 독립 로컬 개발 시스템이다. 대상은 Windows 11 Pro, GTX 1050 Ti, RAM 16GB, Python 3.11, 기존 Ollama Qwen3-4B 1개. VM/Windows Sandbox/Hyper-V/WSL2/Docker, Windows 컨테이너/AppContainer를 **필수·선택·fallback 모두에서 배제**한다. 해당 기능 설치/활성화 요구는 0. 추가 GPU 모델 0, 상주 가상화 0. 실측 성능은 `UNMEASURED`.

**기본 비실행 경로 (독립 실행 권한을 생성하지 않음):**
1. 승인된 계획과 `plan_sha256`, 소스 SHA, REQ/SWU, `allowed_paths`, lease/epoch, 데이터 분류·자원 예산 확인 → **로컬 Qwen 한 개**가 untrusted candidate를 격리된 일회용 worktree/scratch에 제안. Hydrogen 및 외부 공급자는 기본 OFF, 별도 명시 승인만.
2. MLA 자체 경로·Git diff·원본/비밀 차단 → Python AST/tokenize **비실행 파싱** → 서명·버전·규칙을 확인한 로컬 **Ruff(S)** → 승인된 오프라인 규칙의 **Semgrep CE**. 추가 Gitleaks/OSV 오프라인은 조건부, Defender는 기존 상태 읽기/명시적 보조 검사만. 검사기는 순차 호출, 추가 상주 GPU 모델 **0**.
3. 검사기 누락/실패·위험 신호·경로/권리 불명확하면 **HOLD**. 모든 검사 PASS도 **코드 후보/비실행 검토**만 허용하며 테스트 실행, import, 설치 훅, 빌드/셸·Python·PowerShell 실행, 원본 쓰기 또는 보호 Git ref 승격 권한은 **부여하지 않는다**.

**EAI식 CPU-first 안전 실행 경로(새 정본):** MLA 자체 Controller가 소유자 승인 PlanSpec·scope/원본 SHA·lease·예산을 확인한 뒤, 개발자가 작성하고 출처/해시·입출력 스키마를 검증한 **고정 Typed Operator 허용목록**만 실행한다. `PURE/READ_LOCAL`·비실행 AST/정적 검사·동결된 argv의 검사기 호출·검증된 결정론적 CPU 연산을 기본으로 한다. 모델 출력을 작업 명령·shell·Python import/exec/eval·플러그인·빌드·설치 훅에 연결하지 않는다. Qwen이 만든 코드/테스트/EXE/PowerShell/JS는 워크트리에 텍스트/패치 후보로 남기며 **실행은 HOLD**. VM 및 컨테이너를 대체한다는 이유로 이 보호를 우회하지 않는다. **불가피한 임의 생성 코드 실행은 현행 V1.3 범위 밖 별도 사용자 설계·권한 승인·안전 증거가 필요한 미승인 기능**이며 현재 P1/P2 자동 실행 수용으로 간주하지 않는다.

**EAI 재사용 범위:** `hibi89/EAI@feature/kmong-eai-85-p31-20261112`의 `docs/EAI_FINAL_BLUEPRINT.md`가 정의한 `separately authorized plan → allowlisted typed operations → bounded observe/verify → HOLD/rollback`, `no arbitrary import/exec/eval`, CPU-first 검증 방식을 **설계 패턴으로만** 채택한다. EAI 소스/원본 변경·이식은 별도 작업이며, EAI INPUT-only Qwen 규칙을 MLA 코드 제안·편집 기능에 강제하지 않는다. 제안·실행·독립 검증 신뢰 주체를 구분한다.

**작업 브랜치 및 진척 분리:** `design/final-blueprint-v1`은 설계 정본, `dev/instant-implementation-v1`은 기존 39 SWU/30 REQ 제품 소스 정본, `feature/code-shield-lightweight-v1`은 분리된 CodeShield 소스 구현 정본이다. 현재 관측: 기본 P1 구현 후보 **35/39(89.74%)**, 기존 인정 REQ **5/30**, CodeShield 별도 후보 **13/16(81.25%)** — **서로 더하지 않는다.** 기능 통합은 실제 diff·allowed_paths·안전/CI·코드 SHA 확인 후 별도 수행; 이 설계 갱신만으로 구현률 **+0**, 검증률 `UNASSESSED`, P2 `LOCKED`, F18/OS 안전 증명 `NOT_RUN`, owner GO 없음. 보호 원본·비밀·main/Production·Windows 보안 정책·비용·외부 전송은 별도 사용자 승인 필요.

**다음 P1 임계경로:** dev의 `MLA-SWU-008 → {015,021} → 031`은 보호된 owner signer / 실제 coder / 독립 reviewer-F18 / no-egress가 해결되지 않아 `BLOCKED_TRUST`; `first_ready=[]`. feature CodeShield의 `CS-SWU-007/012/014` 역시 미완료. 새 채팅은 최신 양쪽 SHA/큐와 설계 K항을 읽고, 하위 설계·코드 상태를 섞어 100%로 주장하지 않는다. 무진전만 2+2로 집계하고 필요한 경우 솔맥스 기술 지원을 별도 요청한다.


## L. 2026-11-18 최종 정책 오버라이드 — Zero VM / Zero Windows Container

**정책 불변식:** `VM_REQUIRED=false`, `VM_FALLBACK=false`, `WINDOWS_CONTAINER_REQUIRED=false`, `WINDOWS_CONTAINER_FALLBACK=false`, `APPCONTAINER_ENABLED=false`, `UNTRUSTED_CODE_AUTORUN=false`. Hyper-V, Windows Sandbox, WSL2, Docker 및 Windows/기타 컨테이너를 설치·시작·전제·예비경로로 사용하지 않는다. 과거 문서의 VM fallback/AppContainer 후보 문장은 **폐기된 역사적 설계**이며 현재 기능 요구가 아니다.

1. **코딩 흐름:** 로컬 Qwen → 격리된 임시 worktree에 비신뢰 텍스트 패치 → SHA/경로/원본/비밀 검사 → 비실행 AST/Ruff(S)/오프라인 Semgrep CE → 실패 시 HOLD → 독립 승인·F18·Git CAS 없이는 보호 ref/원본 자동 반영 금지. Worktree는 OS 격리나 네트워크 차단 증거가 아니다.
2. **실행 허용목록:** EAI 패턴을 MLA 고유 구현으로 재구성한 CPU-first Pure Player는 **미리 설치/검증된 제품 소유 정형 명령**(스키마/범위/예산/권한, 고정 argv, no shell, no dynamic module)을 처리한다. AI 생성 코드, 생성 테스트, 외부 패키지, 임의 스크립트·빌드 훅·네트워크 송신은 실행 대상이 아니다.
3. **독립 신뢰:** protected owner consent + separate F18 verifier + nonce/lease + Git CAS + 원본/비밀 보호는 제거하지 않는다. 정적 결과는 실제 프로그램 실행/보안 통과 영수증이 아니다. 미확보 기능은 HOLD, P2 검증은 여전히 LOCKED/UNASSESSED다.
4. **기존 SWU 보존:** V1.3 55개 SWU와 원래 REQ/allowed_paths/2+2 이력은 임의 삭제·재번호 금지. `MLA-SWU-015`의 AI 생성 코드 실행/OS 격리 목표 및 `MLA-SWU-031`의 게스트 no-egress 목표는 **본 비실행 아키텍처와 충돌**한다. 이를 달성한 것으로 위장하지 말고, 동일 ID로 비실행 candidate worker/Typed Operator 기본 네트워크 거부의 실제 caller→callee를 재설계하여 수용조건·의존성을 명시적으로 대조한다. 설계 변경이 안전·기능 범위를 축소하는 경우 코드 작업자 임의 PASS가 아니라 High 수용 검토와 소유자 승인 경계 유지.
5. **Codex 경합:** Codex가 이미 수정 중인 `dev/instant-implementation-v1`의 `isolation_runner.py` 및 6개 SWU 소스는 이번 설계 커밋에서 **수정하지 않는다**. 최신 dev HEAD 대비 설계 드리프트 및 기존 VM 프로파일 제거/비활성화는 Codex 결과 인수 후 **별도 안전한 코드 변경**으로 처리한다. 원격 코드에 남은 VM/profile 진단은 제거 완료가 아님.
6. **기기 성능:** VM/컨테이너 제외는 자원 절약 목적이나 VRAM·RAM 절감량은 `UNMEASURED`; Windows 컨테이너가 반드시 GPU VRAM을 많이 점유한다고 가정하지 않는다. GTX 1050 Ti에서 Qwen 1개 우선.

## M. My Local AI V2.0 최종 통합 아키텍처 — 2026-11-18 사용자 승인

**현재 승인된 P0 설계:** [MLA V2.0 MESA + Evidence Gate + AXZERO 정본](MLA_V2_FINAL_ARCHITECTURE_MESA_AXZERO_20261118.md). 본 M절은 V1.2 경험학습·V1.1 Hydrogen의 **호환 상위 설계**이고 §L Zero-VM 절대 불변·V1.3 보호 Owner/F18·CodeShield·nonce/lease/Git CAS와 기존 고유 REQ/SWU를 축소·대체하지 않는다. 이전 H/I/J/K절의 날짜별 구현 건수는 역사적 스냅샷이며, 현재 구현 상황은 실제 개발 브랜치 HEAD와 큐로 판단한다.

1. **MLA Controller**만 Plan SHA/REQ/DAG/READY/예산/권한 및 보호 Git 반영을 지휘한다. 모델, MESA, AXZERO, Hydrogen, AXNODE가 이를 대체하지 않는다.
2. **Evidence Gate**는 환경·의존성 지문·정확 SHA·소유자 범위·증거 발급 주체·검수 규칙/유효기간을 비교하여 추천 재사용 가능 여부를 판정한다. 이전 독립 영수증을 새 SHA에 재발급/승격하지 않는다.
3. **MESA**는 기존 V1.2 Experience Learning Engine 및 기존 **EXT-EXP-01..07**을 재사용해 관측·실패 원인·유사 사례·전략 추천·사용자 제안·A/B 효과 측정을 구현한다. 기존 EAI 선택 어댑터와 원본 EAI는 개명·변경하지 않는다. MESA는 비권한 AdvisorProposal만 반환하며 별도 GPU 모델을 상주시키지 않는다.
4. **AXZERO**는 별도 repo/branch의 REQ 36/18 SWU를 보존한다. MLA는 증거가 있는 capability 참조/검증·고정 Typed Operator 호출만 선택형 어댑터로 연결한다. AXZERO 부재 시 Qwen/MLA 정상, 임의 생성 스크립트는 실행하지 않는다.
5. **Hydrogen**은 기존 EXT-HYD-01..08을 보존한 기본 OFF 선택형 Advisor+독립 후보 코딩 워커다. 계정별 무료·실제 모델 ID·외부 송신/비밀·별도 Owner GO 미확인 시 실제 호출 DENY. **AXNODE**는 후속 선택적 패키징이며 필수 의존성이 아니다.
6. **Owner UI 대안:** 기존 Windows WTSSendMessageW 오류 5를 포괄 권한 부여로 덮지 않는다. 별도 보호된 인터랙티브 Owner 세션의 명시적 승인 UI와 서명된 challenge/response를 비교 설계한다. 독립 SID/TPM 키/서비스 인증/nonce/lease·거절 기본값 및 복구·현장 별도 GO 필수. 관련 작업은 **기존 MLA-SWU-008/021 범위에 귀속**하며 새 SWU를 만들어 기존 완료율을 조작하지 않는다.
7. **변경된 설계의 별도 신규 연결 작업은 5 SWU**([V2 추가 큐](OPTIONAL_V2_INTEGRATION_TASK_QUEUE.json)): Gate, AXZERO 읽기전용 어댑터, 적격성·효과 범위 판정, 제한 고정 연산 호출, 효과 측정. V1.2 경험학습 7 SWU와 함께 별도 **V2 확장 계획 12 SWU**, 기존 P1 **39 MLA + 16 CodeShield = 55 SWU** 분모와 섞지 않는다. Hydrogen 8개, AXZERO 18개는 각자 기존 큐 유지.
8. **현재 확인된 개발 상태(관측):** dev/instant-implementation-v1@7ffd12c190392c6db675a69a5f5b54ff8ffb6f4a의 기본 구현 후보 52/55(94.55%), 보호 서버 소스 존재, Owner 대화형 승인 오류 5, 실제 F18/Defender 실기기 미확인, P2 LOCKED/UNASSESSED. 이 설계 변경은 **코드 기능 +0, 신규 실행/설치/OS 권한/외부 송신 승인 없음**이다.

**구현 순서:** 기존 V1.3 완성·인수 → MESA V1.2 승계 최소판 → 별도 AXZERO 핵심 → Evidence Gate/AXZERO V2 브리지 → 선택 Hydrogen → 선택 AXNODE. 일부 서로 독립적인 개발 작업은 별도 브랜치·책임자·충돌 없는 경로 확인 시 병행 가능. 기능·시간 개선은 실측 전 UNMEASURED. 임의 코드 자동실행 금지와 보호 OS 승인/F18 안전 경계는 어느 단계에서도 완화하지 않는다.


## N. Owner 자체 세션 승인 및 F18 정적/실행 분리 (2026-11-18 사용자 승인)

기존 §L Zero-VM·기본 30 REQ/55 SWU·독립 보호 및 P2/GO를 보존하며, Owner UI를 별도 로그인 세션의 고정 EXE로 옮긴다. 상세 수용·Windows 사전 구성·서명/nonce/lease·F18-A/B 분리는 [승인 정본](OWNER_SESSION_F18_APPROVED_REDESIGN_20261118.md)을 따른다. REQ-14 독립 실행 테스트는 미실행/UNSATISFIED, 정적 검사만으로 합격·Git 승격 불가.


## M. 2026-11-19 Owner-approved additive feature — Windows Local Operator

Approved no-Codex copy/paste workflow with **strictly fixed read-only Windows diagnostics**; not an arbitrary shell or Windows administrative service. Canonical interface/safety/REQ/SWU and combined 55+3 denominator: [Windows Local Operator design](WINDOWS_LOCAL_OPERATOR_FINAL_DESIGN_20261119.md). This additive module preserves every Zero-VM, F18, Owner trust, OS rights, P2 and release HOLD. A valid request is not Owner GO; untrusted ChatGPT text never becomes execution authority. No automatic privileged execution is authorized.


## O. 2026-11-19 — Owner-approved conditional no-TPM CNG signer redesign

The owner's Windows preflight reports no accessible TPM; this **does not** prove hardware absence. Canonical **additive** approved design: [TPM-less protected signer with explicit pinned software KSP](TPMLESS_CNG_OWNER_SIGNER_REDESIGN_20261119.md). TPM-first remains default; software CNG is an explicit pre-provisioned HKLM protected profile, never automatic fallback. Software KSP is lower assurance and cannot attest TPM hardware key protection. Existing MLA-SWU-008/021, CS-SWU-012 and all F18/Zero-VM, owner OS-change GO, P2 LOCKED, release HOLD remain. No change to 55+3 SWU denominator, P1 55/58, formal P2 UNASSESSED until actual evidence.

## P. 2026-11-20 Owner-approved execution topology — Linux-first / Windows Early CI / Windows Final Acceptance

**결정 ID:** MLA-LINUX-FIRST-WINDOWS-BOUNDARY-20261120. **상태:** P0 설계 변경 확정·소스/CI 실행 변경은 별도. 이 P절은 기존 §J~O, MLA V2.0 MESA/AXZERO, OwnerUI·F18·CodeShield·Software CNG 서명자 설계를 **대체하지 않는 실행 환경/검증 라우팅 상위 보완 규칙**이다. 해총 중앙 정책 §0J/§0E 및 사용자 현재 지시가 우선한다. 최종 판매·실사용 제품은 기존대로 **Windows 11**이며 별도 Linux 제품·노트북 듀얼부팅·WSL2/Docker/VM 설치 의무가 없다.

### P-1. 목적과 확정안
- **목표:** P1 구현 후보와 P2 실제 수용까지의 총 경과시간, 사용자 PC 자원 경합, 관리자 승인·브라우저 클릭·반복 CI 대기를 줄인다. 개선 배수/절감율은 비교 측정 전 **UNMEASURED**.
- **선정:** B+C 절충형. **Ubuntu 24.04 LTS GitHub-hosted CI를 공통 로직·허가된 합성 검사 중심**, **Windows GitHub-hosted CI를 네이티브 API·패키징·일부 조기 호환성 검사 중심**, **사용자 실제 Windows 11을 보호 신뢰·OS 권한·실사용 최종 수용 중심**으로 구분한다. 현재 GitHub Actions의 표준 러너만 재사용하며 새 서버·유료 서비스가 기본 요건이 아니다.
- **MLA 로컬:** Python 3.11/Controller/고정 typed operator/CodeShield/Qwen3 4B 한 모델/SQLite/Windows UI 유지. Windows 사용자 보호 주체와 브로커를 Linux 코드로 대체하지 않는다. 외부 모델·네트워크·원격 쓰기·비용은 기존 OFF/Owner GO가 우선한다.
- **이미 있는 기반 재사용:** 개발 브랜치의 \`.github/workflows/ci.yml\`(Ubuntu 합성 Python) 및 \`.github/workflows/mla-windows-workbench-exe.yml\`(Windows 빌드·EXE loopback smoke), \`.github/workflows/windows-protected-bundle.yml\` 등 기존 필수 CI를 보존한다. 추가 워크플로는 실제 미충족 수용 경로가 확인될 때 최소 증분으로 작성; 기존 CI 중단/우회·대규모 재개발 금지.

### P-2. 계층별 실행 위치와 신뢰 범위
| 레인 | 우선 실행 대상 | 정식 PASS가 뜻하는 범위 | 정식 PASS로 주장할 수 없는 것 |
|---|---|---|---|
| \`LINUX_SAFE\` — \`ubuntu-24.04\` | 고정·검토된 Python/TS/React, API/DB/SQLite 합성·유닛·일부 통합, AST/REQ 정적 분석, 허용된 로컬 전용 보안 계약 검사; P2의 합법적 headless Playwright | 정확 소스·시험·환경 SHA에 한정된 합성/정적 또는 실제 브라우저 결과 | Windows IPC·SCM·CNG/Defender·Owner/F18 실증, Windows EXE, 전체 실기기 기능 수용 |
| \`WINDOWS_CI\` — 고정 Windows 러너(기존 \`windows-2022\` 우선) | OS 경계 파일/잠금·경로·인코딩·프로세스·loopback, 정해진 EXE 패키징/기동, Windows 자체 회귀·좁은 필수 보안 smoke | CI 러너 Windows 환경에서 수행된 기능·패키징 결과 | 실제 Owner SID·UAC·TPM/KSP·SCM/ACL·Defender 보호 서비스·노트북 실기기 또는 사용자 승인 |
| \`WINDOWS_OWNER\` — 실제 사용자 Windows 11 | 별도 Owner 세션·서명된 challenge/reply·F18 독립 리뷰어·실 Defender scan 증거·CNG 키/ACL/SCM, 설치/삭제/복구, 한국어 IME/DPI·오프라인, CPU/RAM/VRAM·실모델 | 대상 장치/계정·입력·검증자·승인 범위의 명시적 실제 수용 근거 | 아직 수행되지 않은 독립 보안 감사/상용 GO |
| \`SECURITY_HOLD\` — 실행 레인 아님 | 승인 미확보, 미신뢰 생성 코드/테스트, 원본·비밀/외부송신·관리자권한·신뢰 분리 미증명 | \`NOT_RUN/HOLD\` 및 구체 차단 사유 | 어떠한 보안·P2·독립 검증 PASS |

- 태그는 기존 SWU/REQ/Phase Gate를 **대체하지 않는 시험환경 분류 메타데이터**다. 실제 명령의 \`os_lane\`과 독립된 \`trust_state/approval_state\`를 기록한다. 해당 레인에서 실행 가능해도 신뢰·권한이 없으면 \`SECURITY_HOLD\`가 우선한다.
- 동일 코드·테스트·정책 SHA에 Linux 결과가 있어도 Windows native 요구의 수용 증거로 승격 금지. 브라우저 Linux 렌더링이 Windows WebView2·폰트·IME·DPI에 대한 증거가 되는 것도 금지.
- \`SQLite/WAL\`은 Linux crash/recovery·idempotency 검사 뒤 Windows 파일 잠금/권한/백신 경합을 별도로 검사. Windows 명명 파이프·보호 네이티브 서비스는 Linux mock/unit과 실제 Windows native 증거를 명확히 분리.

### P-3. Zero-VM / F18 / 신뢰 경계의 해석 및 안전 금지선
- 기존 \`VM_REQUIRED=false\`, \`VM_FALLBACK=false\`, \`WINDOWS_CONTAINER_REQUIRED=false\`, \`APPCONTAINER_ENABLED=false\`, 사용자 PC WSL2/Docker/Hyper-V/Windows Sandbox 미사용 및 **생성 코드·테스트 자동 실행 HOLD**는 그대로 유지한다.
- GitHub-hosted Ubuntu/Windows 러너가 내부적으로 VM 기반일 수 있다는 사실을 숨기지 않는다. 본 사용자 결정으로 허용되는 것은 **외부 GitHub Actions의 이미 검토·버전 고정된 제품 소유 테스트와 비민감 합성 자료를 사용하는 CI 오프로드**에 한정된다. 이를 MLA의 미신뢰 생성 코드 격리 기능이나 F18 보호 리뷰어로 사용하지 않는다. **AI가 방금 만든 임의 코드/테스트·스크립트·동적 설치 훅·서브프로세스를 단지 Linux 러너라는 이유로 자동 실행하도록 승격 금지.**
- 생성된 PR/브랜치가 workflow 변경, job script, dependency install/postinstall, 테스트 import side effect를 통해 임의 실행을 유발할 수 있으므로 신뢰된 코드/의존성/워크플로와 미신뢰 후보를 구분한다. 최초 실행은 명시된 검토된 경로와 현재 승인 범위에만 허용한다. 자동 실행 주체·데이터 등급·workflow SHA가 불확실하면 HOLD.
- 공개 저장소에 고객·개인·비공개 소스, .env/토큰/키, 원본 DB/로그, 모델 가중치·비밀 프롬프트를 올리지 않는다. CI는 합성/공개 허용 자료만 쓰고 작업 기본 권한은 read-only \`contents: read\`, \`persist-credentials: false\`, 권한 최소화, 이벤트/외부 PR의 secret·쓰기 실행 차단, action/dependency 공급망 pin, 로그·아티팩트 비밀 제거/짧은 보존을 적용한다. 임의 \`pull_request_target\` 권한승격·untrusted checkout 뒤 write token 사용 금지.
- Windows 실제 사용자 승인·OS 보호 주체의 독립 증명·기존 F18-A/B 분리·REQ-14 실행 테스트 미충족 문제는 Linux CI로 해결됐다고 기록하지 않는다. 필요한 OS 계정/키/ACL/SCM/HKLM·보호 서비스 변경은 기존 별도 사용자 사전 GO 유지. 정적 F18=STATIC_ONLY이며 독립 기능 실행 테스트 PASS 아님.

### P-4. P1/P2 실행 규칙과 조기 Windows 검사
1. **P1:** 실제 BE/FE/DB/API/CLI 정상·핵심 오류 경로 구현, 국소 syntax/type/smoke와 고위험 즉시 안전검사, 기존 필수 CI만 유지. 테스트 환경 매핑은 준비하되 매 SWU 전체 Linux+Windows+브라우저 E2E를 수동 기다리는 규칙을 만들지 않는다. P1의 브라우저 전수 검증은 기존 §F-1대로 후행 P2.
2. **조기 Windows 예외:** 변경이 경로·reparse/symlink·SQLite 잠금·Win32 IPC·CNG/SCM·Defender·권한·EXE 부트/종료·보호 경계를 직접 건드리거나 안전 위험이 즉시 확인되어야 하면 **해당 정확 SHA·최소 검사를 Windows CI에서 빠르게 수행**한다. 검증 생략으로 발생할 수 있는 안전 결함은 P2로 무조건 이월하지 않는다. 현장 Owner 실권한이 필요한 경우 임의 대체하지 않고 해당 항목만 HOLD하며 다른 READY 지속.
3. **P2:** P1 100% 구현 후보·High 정확 SHA Gate 후 승인된 전체 소스·CI·보안·통합·Playwright·복구·실 Windows·실모델 및 결함 수정·재검증을 레인별로 일괄 수행한다. 이미 통과한 범위의 실제 근거는 보존하되 환경·소스 SHA가 달라지면 영향 범위 재검증. P3 독립 코드·보안/UI 감사, P4 High 인수, 사용자 GO와 출시 여부는 별개.
4. 기존 **P1 58 SWU(MLA 39 + CodeShield 16 + Windows Local Operator 3)**, REQ/allowed_paths/2+2/DAG/이력 및 **P2 8 Gate** 분모 변경 금지. 다른 구형 28-task/30-REQ 지표·V2 선택 확장 지표와 중복 집계 금지. 문서/CI 분류만으로 새 SWU 완료 또는 P2 PASS 주장 금지.

### P-5. 증거 계약, 오류 처리, 실제 효율 계측
- 검증 영수증 최소 항목: \`repo,branch,source_sha,design_sha,workflow_sha,test_suite_sha,runner_os,runner_image,os_lane,run_id,run_url,trigger,scope,data_class,approval_state,trust_state,test_counts,result(PASS|FAIL|SKIP|NOT_RUN|HOLD),artifact_digest,independence,started_at,finished_at\`. Linux·Windows CI·실사용자 Windows 영수증을 반드시 구분해 저장하고 정확 SHA 불일치·증거 유실·취소·타임아웃·다른 runner는 \`UNKNOWN/HOLD\`로 다룬다.
- 사용자가 실제로 체감할 **총 경과시간**을 동일한 시작 코드/REQ/SWU·리스크 수준·결함 재수정 범위로 비교한다. 측정값: P1 source-candidate 도달시간, P2 완성시간, 수동 클릭/Owner 승인 횟수, CI 큐·실행·재시도 시간, Windows 회귀 결함, GPU/RAM·비용·유료 API 0 유지 여부. 비교 샘플·결과 없으면 \`UNMEASURED\`; 2배·3배 등 배수·절감률 확정 금지.
- 러너 큐 적체·패키지 설치 반복·OS 차이로 오히려 느려지면 캐시 검증/기능별 job 선택/중복 취소 등 **검증 범위·안전조건을 줄이지 않는** 최적화를 먼저 검토한다. CI 상태 \`queued\`/\`success\`를 실기기 기능 PASS라고 표시하지 않는다.
- GitHub Actions 사용량·무료 공개 저장소 조건·계정·정책이 바뀔 수 있으므로 현행 과금/쿼터를 실행 전 확인한다. 유료 러너/민감 데이터 송신/외부 API·remote write 자동화/Production/main 병합·OS 권한 변경은 별도 GO.

### P-6. 구현 적용 순서·현재 상태
1. 현재 dev 워크플로/코드/실제 완료 SHA·러너를 먼저 매핑. 기존 Ubuntu 합성 테스트와 Windows EXE 빌드 성공 이력의 범위 확인, 누락된 수용 게이트 분리. 설계 변경으로 정상 CI를 다시 만드는 작업 금지.
2. 기존 테스트·SWU에 \`os_lane\` + 독립 \`trust_state\`를 선택형 메타데이터로 추가. 첫 후보는 현재 허용된 read-only REQEA/MLA 고정 workflow 경로처럼 **검토된 명령**을 사용한다. \`WORK_PHASE_GATES\`/기존 보안 승인 규칙을 변경하지 않음.
3. P1 실제 독립 READY 진행; OS 전용 코드 변경 때만 필요한 조기 Windows smoke를 연결하고 P2에서 전체 레인 검증을 재사용한다. 사용자의 1050 Ti 노트북은 실 Windows Owner·GPU·최종 UX에 집중하고 Ubuntu 듀얼부팅·상시 VM을 요구하지 않는다.
4. 사용자 기기에서만 가능한 신뢰/권한 검증을 독립 목록으로 유지하고 필요 승인·실행자·정확 SHA 없으면 \`NOT_RUN/HOLD\`. 기술 설계 도입 자체는 Owner runtime GO, 실행권한, 크몽 등록, 배포 승인 아님.

**2026-11-20 설계 반영 범위:** 문서·워크플로 라우팅 정책만 확정. **현재 제품 코드·GitHub Actions YAML·테스트 실행/실기기 Owner·F18/보호 서비스·외부모델/결제·Production·main 변경 없음.** 기준 개발 브랜치 최신 STATUS/HEAD가 구현 진행의 정본이며 본 P0 설계 문서 수정으로 구현률·검증률 상승 **0**.


## Q. 2026-11-20 Owner-approved long-running workbench and GTX 1050 Ti efficiency policy

**Goal:** Minimize P1 source-candidate and P2 overall elapsed time on Windows 11 Pro / GTX 1050 Ti 4GB / RAM 16GB. Do not install Ubuntu locally; use existing GitHub-hosted Ubuntu/Windows CI for already trusted synthetic/packaging tests. No measured speed multiplier yet (`UNMEASURED`). This complements §P Linux-first lanes and all prior Zero-VM, Owner, REQ-14, F18, CodeShield and phase gates.

**CLI-like user prompt, not arbitrary shell:** MLA.exe's workbench accepts a development instruction and explicit multi-part queue (each source file, intended change, dependencies, allowed_paths). It **does not** execute pasted Windows cmd.exe/PowerShell commands or AI-generated test/code as a shell. It creates source candidates in a separate local draft folder; neither local originals nor Git protected refs are automatically modified. The text alone is not operating-system authorization or P2 verification evidence.

**Continuous bounded job model:** While MLA.exe remains running, process one eligible safe item at a time with bounded Qwen3-4B/model budget and bounded retries. After each durable local SQLite checkpoint, advance to other independent READY drafts or read-only source inspections. Add `PAUSE_REQUESTED` (stop after current bounded step), `PAUSED`, `WORKING`, `READY_TO_CONTINUE`, `AWAITING_REVIEW_OR_APPROVAL` status and explicit UI pause/resume. Restart on the same local draft root restores the queue; interrupted in-flight attempts become HOLD rather than rerun; exact previously dispatched remote workflow is never resent. No busy polling when only approvals/verification remain. Closing the browser tab does not end an open EXE process; closing EXE/power-off stops processing until resumed. No unattended Windows service/autostart or sleep/power-policy changes.

**Low-VRAM policy:** One resident Qwen model, no competing GPU inference. Prefer pinned source/REQ excerpts, narrow file-scoped modifications, deterministic typed operators and existing source/error evidence over full-context regeneration. Optional high-capacity AI providers require independent user approval for actual API access, data transmission and charges; a web ChatGPT session is not an automatically callable local API. Reuse already existing synthetic Ubuntu CI and Windows EXE CI; prohibit generated-code execution without independently established trust. Track elapsed P1/P2 time, manual intervention, CI queue latency, token/call and power/VRAM observations before claiming gains.

**Actual completion policy:** A queue with draft candidates still needs review, integration, P2 tests, protected Owner/F18/Defender native evidence, independent audit and GO. It must not display P2/production COMPLETE. Unknown, unsupported or OS-privileged operations remain HOLD; do not loop for days waiting on them. P1 baseline 55/58 candidates and 0/8 P2 gates **unchanged** by this optional capability.

**Separate SWU scope:** `docs/OPTIONAL_LONGRUN_TASK_QUEUE.json` defines MLA-LR-001 continuous workbench UI/API/SQLite recovery, LR-002 trusted CI offload, LR-003 low-VRAM role router/cache, LR-004 real Windows EXE and multi-day recovery acceptance. Keep this extension separate from the existing 58 P1 source SWUs. The first feature is source candidate only until exact-SHA CI; the extended multi-day Windows soak remains NOT_RUN. No new system-level approval or remote dispatch permission was granted.


**Q-5. Cross-process SQLite queue lease (2026-11-20 safety addendum):** Exactly one running MLA.exe may own one local draft-root; before reopening/resuming queue, acquire an OS-held exclusive file lease on a regular local path, rejecting symlinks, hardlinks, corrupted lock payload and second EXE. Release on normal exit; the OS releases on process death. This is process coordination only, **not** Windows protected Owner/F18 authority. Same-root collision must show an error, never run Qwen twice or overwrite SQLite queue checkpoints. Real Windows fault/restart/long-duration acceptance remains P2 NOT_RUN.


### Q-6. Safe recovery of already approved remote CI + bounded model residency (2026-11-21 KST)
- New `MLA-LR-002` read-only partial implementation: following one explicit Owner-initiated pinned REQEA workflow dispatch, the local workbench may compare a saved run ID or a *unique* pinned revision+dispatch timestamp to GitHub Actions metadata via GET only. A restart/timeout must never send a second POST. If the identity or workflow path conflicts, more than one run matches, no trustworthy dispatch timestamp exists or the source drifts: HOLD. Remote smoke PASS is never P2 full acceptance or independent verification. Prevent racing read-only reconciliation with a live dispatch worker. Additional CI adapters must get separate allowlist+trust review.
- New `MLA-LR-003` low-memory partial implementation: local-only Qwen `/api/generate` requests from *multi-part* drafting may reuse the single model for a **fixed maximum 90 seconds** between serial jobs. Standalone requests retain immediate unload, and keep_alive values are integer validated in 0..90 seconds. No new GPU model, authority, extra API or model invocation concurrency. Measure VRAM/RAM and elapsed SWU costs before asserting improvement or expanding to additional models.
- Neither partial feature changes MLA base P1 58 SWUs, Owner OS approvals, F18, security HOLD, P2 locked or commercial GO. Actual multi-day Windows workstation behavior and requested all-the-way-through verified implementation remain NOT_RUN/PENDING.


### Q-7. 2026-11-21 low-resource task safety and immutable-source reuse
- Prevent **cross-SWU same-file divergence**: for one pinned branch SHA, a previously scheduled/attempted source path is a conflict. Case-fold paths conservatively for Windows local targets; preserve manual path claims in the existing SQLite checkpoint; show explicit HOLD for later same-file parts while independent READY continues. No automatic draft merging, source promotion, test execution or treating conflicting drafts as verified. Even a regenerated draft is never the GitHub HEAD without separate review and authorization.
- Reuse previously validated `read_github_file` UTF-8/Git blob content only when **repository+full 40-character SHA+path** match exactly. Bound process-only LRU to 8 records/512KB; no error/404 caching, no local-folder originals caching, no disk copy or cross-restart persistence. Show only reuse count in local workbench; full source remains protected from UI metrics.
- For `.json` and `.toml` source proposals, run built-in Python syntax **parsers only**, reject duplicate keys/non-standard numeric constants, and request bounded correction within the existing max 3 attempts. This does not execute generated code, verify runtime semantics, or count as P2 security acceptance.
- Keep `MLA-LR-003` SOURCE_PARTIAL pending explicit model-role selection, trustworthy live GTX1050Ti time/VRAM/response measurements, and full source-to-accepted behavior. Current source/candidate count, P2 LOCK, independent trust and Owner GO remain unchanged.


### Q-8. 2026-11-21 typed single-model route and local benchmark receipt
- Controller selects a **typed local-only** resource path for source drafting: exactly one loopback Qwen provider with 4,096 or 8,192 context according to conservative prompt+output allocation. Requests that cannot fit HOLD before contacting the model; they must not fall back to another model or external API.
- Warm Qwen residency is capped at 90 seconds **only if** another independently READY unattempted SWU remains; the last, paused or standalone job sends keep_alive 0. This is a performance candidate, not a guaranteed GPU memory-release receipt, and never widens the model/budget/OS authority.
- On completed local responses the provider optionally reads only validated nonnegative Ollama timing/token counters (total/load/prompt/eval ms, prompt/eval token counts, generated tok/s), never prompts/source/credentials. The local workbench shows them per completed draft and preserves them in existing SQLite queue state. Missing/malformed/implausible counters are omitted, not invented; no hidden network endpoint or extra model calls are introduced.
- P1 source candidate acceptance can use synthetic provider and Windows EXE CI; **GTX 1050 Ti real measured before/after same-SWU timing, GPU VRAM, battery/thermal effects and 24h recovery acceptance remain P2 NOT_RUN until Owner Windows proof**. These stats do not prove F18, Defender, CI general verification, or commercial release.
