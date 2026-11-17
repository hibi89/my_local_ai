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
- **P0 HIGH** (지금): 최종설계·REQ 32·작업 큐·수용표·브랜치·보안/기술선택 확정, 사용자 설계 승인 대기.
- **P1 Instant**: 독립 ready 3~10개 묶음, BE/FE 코드 구현 후보까지 지속. 최소 문법/계약/보안 국소검사 외 전체 CI 수시 대기 금지.
- **P2**: 후보 구현 전수 후 전체 CI·통합·회귀·권한·Windows 11 Pro 실기기·실 Qwen/OpenCode·격리·24h 안정/복구 검증 및 결함 수정.
- **P3**: 같은 exact SHA의 Codex Sol Max 기술/보안 + Astra Max 사용성/FE 독립 검수(실행 없으면 NOT_RUN).
- **P4**: High 전수 인수, BLOCKER/HIGH 해결. 안전한 개인 실사용은 사용자 GO.
- **P5**: 이후 별도 승인된 상품 생산 워크플로 확장. 크몽 등록/상용화는 본 도구의 자동 GO가 아니다.

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
1. High 설계의 \`plan_sha256\`, source SHA, task/REQ, owner scope 검증. EAI advisor는 non-authoritative 추천만; EAI 원본 INPUT-only/13 goals와 혼동 금지.
2. Qwen은 로컬에서 계속 구현. Hydrogen은 **별도 API 호출 승인이 있고** 정확한 비민감 공개/합성 입력, 무료 티어/프로젝트 쿼터, 독립 작업 경로, 격리 runner, 데이터 정책이 모두 통과할 때만 동시 READY에 배정.
3. 모델과 무관하게 각 워커는 같은 \`WorkerRequestV1\`/ \`WorkerResponseV1\` 비신뢰 계약을 따른다. 모델이 파일이나 셸/원격 GitHub/테스트 PASS·권한 승격을 직접 수행하지 않으며, 로컬 executor와 별도 trusted reviewer만 적용/판정.
4. API 키 없음, 유료 전환, 무료 한도 429, owner OFF, 401/403, 보안 정책 실패 → Hydrogen만 OFF/HOLD. 중단 체크포인트·source SHA/epoch 대조 후 로컬 Qwen에 **재배정 가능 후보** 생성. 새 로컬 모델까지 자동·중복 실행 금지; 웹 Instant는 큐 제안만.
5. Hydrogen 후보는 **안전한 분리 브랜치/로컬 ref에 통합되어 실제 source SHA와 구현 근거가 확인될 때만** 기존 30 REQ 구현 분자에 기여. P2 전체 CI/보안·실기기는 P1 100% 후보 후 별도. Hydrogen이 Codex·Astra의 독립 감사 역할을 대체하지 않는다.

### H-3. 데이터·안전·비용
- \`remote_enabled=false\`, \`network_egress=deny\`, \`max_spend_usd=0\` 초기값. 비용 미확인·무료 자격 미확인 시 **FAIL CLOSED**, 무료 티어가 있더라도 무상·무제한·고객 자료 업로드를 허용하는 것으로 보지 않는다. 계정별 실제 rate limit과 모델 ID/SDK 동작은 별도 확인.
- 승인 없는 외부 API 호출, 고객/비공개 저장소·토큰·.env/개인경로/프롬프트 원본·DB·해커톤 비공개 자료 외부 송신 금지. 키는 공개 GitHub·SQLite·로그에 저장 금지.
- 워커별 격리·경로 충돌/공통 파일 잠금·Git lease/fencing·멱등 복구·1회 개선 재시도/독립 HOLD, F18 forged receipts 차단. 유료 결제/권한·보안 설정/원본/remote PR·main/Production/실사용은 사용자 별도 GO.

### H-4. BE/FE/DB/API·수용·단계
- BE: \`providers/base.py,registry.py,policy.py,local_qwen.py,hydrogen.py\` ProviderPort, capability/eligibility/budget guard, parallel scheduler, isolated runner, failure circuit breaker, checkpoint; 실제 dev 코드와 충돌 없는 이름으로 구현 전 재검토.
- DB 확장안: \`provider_registry/provider_quota/worker_assignments/provider_calls/provider_approvals\` (로컬 SQLite, 백업·안전 migration 필수). UI/CLI: 읽기전용 provider 상태·OFF/429/무료 자격·작업/비용 상한 표시; 별도 GO 없는 원격 ON 금지.
- API: \`WorkerRequestV1\`(immutable plan/source SHA, owner scope, req_ids, allowed_paths, worker epoch, budget, data_class) → \`WorkerResponseV1\`(untrusted candidate diff, SHA, model, usage) → **독립** \`TrustedReceiptV1\` → local protected ref/HOLD.
- 수용: HYD-AC-01~10 (오프라인 회귀, 허용 독립 병렬, 429/유료 자동 OFF, 비밀 송신 차단, F18, 복구/중복, 12 합성 작업 성능 비교); 정확 조건은 [탈부착형 워커 정본](DETACHABLE_MULTI_MODEL_WORKERS.md).
- **기존 REQ-01~30 / P1 28 작업·REQ-31~32 후행 / P2 8검증 불변.** 확장 \`EXT-01~08\`은 [별도 선택형 큐](OPTIONAL_PROVIDER_TASK_QUEUE.json)의 설계 항목이며 실 API 호출이나 P1 분모 변경은 별도 승인/기준선 개정 전 금지. 기존 Instant 구현은 계속.
- P1 기본 구현·즉시 안전 검사 우선; 확장 모듈은 mock/contract부터 별도 작업으로 검토 가능. P2 LOCKED, 라이브 Hydrogen API/계정 권한/돈/원격 전송/개발 브랜치 자동 병합은 아직 **NOT_RUN/NOT_APPROVED**.

Google 공개 2026-11-12 모델 카드: https://deepmind.google/models/model-cards/gemini-4-hydrogen/ ; Gemini API 무료/유료 가격: https://ai.google.dev/gemini-api/docs/pricing ; 모델별·프로젝트별 변동 한도: https://ai.google.dev/gemini-api/docs/rate-limits . 무료/유료·기능 지원은 실제 계정 사용 전에 다시 확인한다.

**전체 세부설계:** \`docs/DETACHABLE_MULTI_MODEL_WORKERS.md\` · **작업큐:** \`docs/OPTIONAL_PROVIDER_TASK_QUEUE.json\`. 이 확장은 문서 설계만 반영한 것으로, 구현완료율·검증완료율을 상승시키지 않는다.
