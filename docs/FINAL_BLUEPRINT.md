> **[2026-11-18 KST · LOW-VRAM HARDWARE + HIGH-P1 CANONICAL ALIGNMENT]** 현재 사용자 확정 기본 경로는 **VM/Sandbox 상시 실행 OFF · CodeShield 경량 비실행 사전검수 ON · 호스트 Qwen 단일 모델 · 기존 Defender 유지**다. 원본 EAI 순수 메모리 Player는 임의 AI 코드 격리 실행기의 대체물이 아니다. CodeShield 정적 검사 PASS만으로 AI 생성 코드·테스트·설치 훅·PowerShell 등을 호스트에서 실행·Git 승격하지 않으며, 실제 코드 실행에는 승인된 보호 OS 경계와 독립 F18이 필요하다. 불가능하면 해당 실행만 HOLD하고 안전한 비실행 개발은 지속한다. 이 지침은 기존 REQ/SWU·F18·P2 LOCK·소유자 GO를 축소하지 않는다. 해총 §0J/§0E에 따라 12월 실제 전환·사용자 결정 전 P1 담당은 웹 GPT-6 Sol High다. 세부: 아래 K항.

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

**확정:** Windows Sandbox/VM 상시는 중단하고, 호스트 Qwen 단일 모델 + 비실행 Python AST/MLA 경로·Git guard + Ruff S + native Windows Semgrep CE 로컬 규칙 + 조건부 Gitleaks/OSV offline + 기존 Defender 상태 점검을 기본 CodeShield로 선택한다. 검사기 GPU 상주/두 번째 백신 엔진/원격 paid 의존은 없다. 사용 기술·구체 실행 조건·위험 등급·Windows 실기기 검증·성능/수용은 docs/CODE_SHIELD_LIGHTWEIGHT_SECURITY_V1_3.md를 따른다.

**절대 불변:** 정적 검사 PASS는 임의 모델 생성 코드/테스트/설치 script/외부 executable을 호스트 PC에서 실행하는 권한이 아니다. 실제 실행은 보호된 OS 격리+F18 별도 독립 검수 입증이 필요하며 실패·미구현은 HOLD. AppContainer/Job Object는 P2 실기기 호환성·보안 후보, Windows Sandbox는 필요시 승인된 fallback; 무조건 VM 제거 아님. Defender CFA/ACL/Windows 보안/방화벽 변경은 소유자 별도 GO. 원본·비밀·Git main·고객·Production 접근과 F18/CAS 보호 불변.

**단계/지표(2026-11-18 기준):** 기존 **30 REQ / 39개 P1 SWU(완료 후보 35/39) / 28개 legacy 작업**, P2 8개 검증 LOCKED 및 V1.1 Hydrogen/V1.2 경험학습을 보존한다. `CS-01..08`은 과거 CodeShield **8개 설계 작업군**이며 최신 SWU 재분할 기준은 **16개 SWU, 별도 `feature/code-shield-lightweight-v1`에서 소스 구현 후보 13/16**이다. 나머지 `CS-SWU-007/012/014`는 미완료이며 실제 Windows OS 브로커/F18/egress는 NOT_RUN/HOLD다. **별도 feature 구현은 dev 브랜치에 자동 통합된 것이 아니며**, 원래 35/39 분자와 혼산하거나 소스 기능·P2 검증 PASS·실운용 허가로 인정하지 않는다. CodeShield 큐와 기술설계는 해당 기능 브랜치와 본 설계 브랜치에서 구분하여 관리한다.

---

## K. 2026-11-18 저자원 실행·검수 경로 최종 적용 — 기본 VM OFF, CodeShield ON

**임무·기기 잠금:** My Local AI는 EAI와 독립된 로컬 코딩 자동화 제품이다. 현재 대상은 Windows 11 Pro / GTX 1050 Ti / RAM 16GB / Python 3.11 / 기존 Ollama Qwen3-4B. 모델 추가 다운로드·동시 상주 또는 두 번째 백신/상시 VM을 기본 요건으로 만들지 않는다. VM의 주 병목은 게스트 RAM·CPU·시작 비용이며 VRAM 증가는 GPU 구성에 따라 다르므로, GPU·RAM·시간 절감 배수는 실측 전 `UNMEASURED`다.

**기본 비실행 경로 (독립 실행 권한을 생성하지 않음):**
1. 승인된 계획과 `plan_sha256`, 소스 SHA, REQ/SWU, `allowed_paths`, lease/epoch, 데이터 분류·자원 예산 확인 → **로컬 Qwen 한 개**가 untrusted candidate를 격리된 일회용 worktree/scratch에 제안. Hydrogen 및 외부 공급자는 기본 OFF, 별도 명시 승인만.
2. MLA 자체 경로·Git diff·원본/비밀 차단 → Python AST/tokenize **비실행 파싱** → 서명·버전·규칙을 확인한 로컬 **Ruff(S)** → 승인된 오프라인 규칙의 **Semgrep CE**. 추가 Gitleaks/OSV 오프라인은 조건부, Defender는 기존 상태 읽기/명시적 보조 검사만. 검사기는 순차 호출, 추가 상주 GPU 모델 **0**.
3. 검사기 누락/실패·위험 신호·경로/권리 불명확하면 **HOLD**. 모든 검사 PASS도 **코드 후보/비실행 검토**만 허용하며 테스트 실행, import, 설치 훅, 빌드/셸·Python·PowerShell 실행, 원본 쓰기 또는 보호 Git ref 승격 권한은 **부여하지 않는다**.

**실제 실행이 필요한 경우 (별도 필수 경계):** 먼저 독립된 Windows OS 보안 주체·소유자 서명자 및 키 보관·보호된 파일/프로세스 접근통제·CPU/RAM/시간 제한·호스트 검증 네트워크 egress 거부·별도 F18 reviewer/서명/nonce/lease/CAS를 **실제로 구현·입증**해야 한다. **AppContainer + 제한 토큰 + Job Object는 VM보다 가벼울 수 있는 검증 후보이지 현재 PASS/안전성 보증이 아니다.** 실제 Windows 11의 Python/OpenCode/네트워크/NTFS 권한 및 독립 reviewer 분리를 검증하기 전 임의 생성 코드를 실행하지 않는다. Windows Sandbox는 사용자 별도 승인 후 필요한 실행에만 켜는 fallback이며 상시 기동, guest Qwen 중복 적재, 고객·원본 공유는 기본 금지다. 위험 작업만 HOLD하고 비실행 작업은 계속한다.

**EAI 재사용 범위:** EAI의 CPU-first 순수 메모리 Player·typed operator allowlist·무효작업 HOLD 원칙은 분석·계획·자원 제어에 선택적으로 참조한다. 순수 메모리 실행은 임의 모델 생성 코드/테스트를 안전하게 실행할 수 있다는 증거가 아니다. **EAI의 INPUT-only Qwen 규칙은 EAI 고유**이며 MLA의 승인된 Qwen 코딩 워커 범위를 임의 축소하지 않는다.

**작업 브랜치 및 진척 분리:** `design/final-blueprint-v1`은 설계 정본, `dev/instant-implementation-v1`은 기존 39 SWU/30 REQ 제품 소스 정본, `feature/code-shield-lightweight-v1`은 분리된 CodeShield 소스 구현 정본이다. 현재 관측: 기본 P1 구현 후보 **35/39(89.74%)**, 기존 인정 REQ **5/30**, CodeShield 별도 후보 **13/16(81.25%)** — **서로 더하지 않는다.** 기능 통합은 실제 diff·allowed_paths·안전/CI·코드 SHA 확인 후 별도 수행; 이 설계 갱신만으로 구현률 **+0**, 검증률 `UNASSESSED`, P2 `LOCKED`, F18/OS 안전 증명 `NOT_RUN`, owner GO 없음. 보호 원본·비밀·main/Production·Windows 보안 정책·비용·외부 전송은 별도 사용자 승인 필요.

**다음 P1 임계경로:** dev의 `MLA-SWU-008 → {015,021} → 031`은 보호된 owner signer / 실제 coder / 독립 reviewer-F18 / no-egress가 해결되지 않아 `BLOCKED_TRUST`; `first_ready=[]`. feature CodeShield의 `CS-SWU-007/012/014` 역시 미완료. 새 채팅은 최신 양쪽 SHA/큐와 설계 K항을 읽고, 하위 설계·코드 상태를 섞어 100%로 주장하지 않는다. 무진전만 2+2로 집계하고 필요한 경우 솔맥스 기술 지원을 별도 요청한다.
