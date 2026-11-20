> **[2026-11-20 KST · MLA V2 Q LOW-VRAM LONG-RUN EXECUTION DESIGN / DEV IMPLEMENTATION]** §Q와 `docs/OPTIONAL_LONGRUN_TASK_QUEUE.json`이 신규 별도 확장 범위 정본이다. dev `dev/instant-implementation-v1@140a60faa11ad8cef1eff1f270a8fd4c4253e090`에 첫 `MLA-LR-001` 실제 소스 후보(기능 SHA `9e7c68fea15da2c6afe24a449bf7022009225e31`, 테스트 SHA `4827510fc95f802d4b3355302b5ce6abd6f79a45`) 반영; Ubuntu 합성 295+124+304 PASS #44751448525, Windows unsigned EXE build/loopback PASS #44751337489. 실제 Owner Win11/멀티데이/실모델·독립 F18·Defender 보호 실행 NOT_RUN. 설계 브랜치 자체 제품 코드 없음; P1 기본 55/58, P2 0/8 UNASSESSED/LOCKED, 별도 확장 1/4 source candidates/실제 검증 0, RELEASE HOLD. 

> **[2026-11-20 KST · P0 PLATFORM/CI TOPOLOGY DESIGN UPDATE ONLY]** `docs/FINAL_BLUEPRINT.md` §P(디자인 SHA `e435b45e134649a60855cf9b416b3b235b2249e2`)에 Linux-first/Windows Early CI/Owner Windows 최종 인수 아키텍처 추가, 개발 브랜치 문서에 `1ab4ea684bfe700c3e954c4c1bb35fd7542a53f2`로 동일 적용. 신규 제품 기능·CI 수정·실행 테스트·OS 권한·보호 서비스·배포 0; 구현/검증 개선 0. 현재 실제 개발 진척은 dev STATUS/최신 HEAD가 정본이며 과거 설계 브랜치 진척 스냅샷과 혼동 금지. Zero-VM/F18/Owner와 P2 LOCKED, RELEASE HOLD 보존.**

> **[2026-11-18 KST · V2.0 P0 DESIGN APPROVED / DESIGN BRANCH ONLY]** V2.0 MESA/Evidence Gate/AXZERO architecture: docs/FINAL_BLUEPRINT.md §M + docs/MLA_V2_FINAL_ARCHITECTURE_MESA_AXZERO_20261118.md. Existing EXT-EXP-01..07 / EXT-HYD-01..08 preserved; 5 new optional integration SWU in docs/OPTIONAL_V2_INTEGRATION_TASK_QUEUE.json. Existing V1.3 base 55 SWU unmodified. Dev observed @7ffd12c190392c6db675a69a5f5b54ff8ffb6f4a: 52/55 source candidates, Owner WTSSendMessageW error 5, F18/Defender live acceptance HOLD; P2 LOCKED/UNASSESSED. No source/CI/Windows/AXZERO/Hydrogen runtime change in this design commit; checks DESIGN_SCHEMA_ONLY (locally checked in authoring), full CI NOT_RUN. Design branch current commit SHA = GitHub branch HEAD; older P1 states below historical.

> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

> **[PRODUCT IDENTITY LOCK · OWNER CLARIFICATION · 2026-11-17]** `my_local_ai`는 **EAI의 후속 버전/확장판/완성판이 아니다.** EAI는 선택적으로 재사용할 알고리즘·CPU 분석·도구의 **기술 제공원**일 뿐이다. `my_local_ai`의 고유 목적은 **로컬 모델로 소프트웨어 구현을 지속 자동화하는 개인용 개발 시스템**이며, 정책·스케줄·실행/검증 게이트·진척 기준은 `my_local_ai`가 자체 소유한다. 원본 EAI ADR-0002(Qwen INPUT-only)는 EAI 원본의 아키텍처 지침이지 `my_local_ai`의 코딩 워커 사용 제한이 아니다. EAI 전체 13개 목표·자체 모델 연구의 100% 완료는 `my_local_ai`의 필수 조건이 아니다. 자세한 내용 `docs/PRODUCT_IDENTITY.md`. **P1 구현 우선/P2 검증 잠금 정책은 그대로 유지.**

# My Local AI — STATUS (2026-11-17 KST)

## 현재 상태
- repo: `hibi89/my_local_ai`, PUBLIC, 사용자 생성 empty repo 확인, `main`에 README 최초 baseline SHA `960621d6207e6beb22a7e9480e524988196f3d44`.
- 설계 브랜치: `design/final-blueprint-v1`. P0 High 통합설계 V1, **My Local AI 자체 Controller**, EAI 유래 선택적 분석/AX 로컬 실행·독립 검증, REQ-01~REQ-32, P1 코드 구현 큐 28개 / P2 전체 검증 큐 8개 + 독립 감사/인수 2개, 첫 P1 READY 5개, 위협모델/DB/BE/FE/수용 매트릭스 문서화.
- **실제 my_local_ai 제품 소스 구현 0건 / 구현완성률 UNASSESSED / 공식 검증완성률 UNASSESSED / 전체 CI NOT_RUN / owner Windows11/Ollama 실기기 NOT_RUN / 24h 시험 NOT_RUN.** 현재 문서만 존재하고 코드 이식/모델 호출/배포/PR/권한 변경 없음.
- 위험 게이트: AX F18 guest receipt trust boundary CRITICAL HOLD. 기존 source의 CI 성공은 새 통합 repo 완료 증거 아님.
- 코드 참조(읽기 전용): EAI source HEAD `5186cb1aa7928054d56b1cd0a40ea5943a5b3892`; AX source HEAD `5ab94180471c7ea86344b691fc77ad5c29989071`. 해당 원본 변경 없음.
- 다음 실행: 사용자 최종설계 확인/GO 후 `dev/instant-implementation-v1`의 MLA-001/002/003/004/005. 설계만으로 READY를 VERIFIED로 기록 금지.
- 2026-11-21~22 주말 통합은 목표일, PC/독립 보안 경계·실모델 접근으로 막힐 수 있음. 개인 실사용 및 출시 HOLD.
- 인수인계 기준 설계 소스 커밋/이후 HEAD는 실제 GitHub 브랜치를 재확인. 디자인 문서 커밋의 Python 테스트 PASS 없음.


---

## 2026-11-17 KST High V1.1 — 탈부착형 Hydrogen 병렬 구현 설계 반영 (최신 설계 기록)
- **임무:** 사용자 지시로 My Local AI 전체 설계에 원격 Hydrogen을 독립 병렬 BE/FE 코딩 워커로 추가할 수 있는 **OFF-by-default ProviderPort 구조**를 확정. 로컬 Qwen/AX Dev Factory 기반 경로 및 선택형 EAI advisor는 유지. Hydrogen은 Codex/Astra 검증 또는 원본 EAI를 대체하지 않는다.
- **설계 변경:** `docs/FINAL_BLUEPRINT.md H`, `docs/DETACHABLE_MULTI_MODEL_WORKERS.md`, `docs/OPTIONAL_PROVIDER_TASK_QUEUE.json`, `docs/ARCHITECTURE.md`, `docs/INTEGRATION_CONTRACT.md`, `REQUIREMENTS.md`, `docs/ACCEPTANCE_MATRIX.md`, `docs/SECURITY_MODEL.md`, `docs/PHASE_GATES.md`, `AGENTS.md`, `docs/BRANCHING_AND_HANDOFF.md`, `INSTANT_RUNBOOK.md`에 별도 확장 정책/수용을 연결.
- **필수 범위·진척 불변:** 기존 `REQ-01~30` 구현 분모 30/ `INSTANT_TASK_QUEUE.json` 28개, `REQ-31~32` 후행, `VERIFICATION_TASK_QUEUE.json` P2 8개, `WORK_PHASE_GATES.json` 잠금 불변. `EXT-01~08`은 **별도 선택형 설계/큐**(실행·완료 증거 없음), 기존 구현완료율·검증완료율 상승 **0**.
- **개발 브랜치와 구분:** 2026-11-17 조회 당시 `dev/instant-implementation-v1` HEAD `e6af762a5d4e7f61d18fee1ae2ba55df423cc443`; 해당 브랜치의 기존 STATUS 최신 기록은 REQ 3/30=10.00%와 정확 코드 SHA `4bdff24db9d2a0a3ab37036225df1ff0aa6fe846`의 합성 테스트 41+5 PASS. 이후 코드 실제 추가 구현/전체 검증은 별도 HEAD 검사 필요. 설계 브랜치의 위 P0 `0 구현`은 **과거 설계 시점 스냅샷**이지 현재 dev 실적이 아니다.
- **실행/비용/권한:** 외부 Hydrogen API 실제 호출 0, 모델 자격/사용량 계정 미검증, Key 미요청/미저장, 외부 송신·GitHub PR/권한·Production·main 병합 0, Python/전체 CI/Windows/실모델/24h/독립 F18 reviewer 추가 실행 0. `remote_enabled=false`, `max_spend_usd=0`, 비용/개인정보 승인 전 OFF. 원본 EAI/AX 미수정.
- **차단:** 외부 API·무료 티어/가격/데이터 전송·자격·확장 구현/동기화 필요 시 별도 사용자 GO 및 High 실제 dev HEAD/allowed_paths 충돌 검사. F18 trust boundary CRITICAL HOLD, P2 LOCKED 유지.
- **다음:** Instant는 본래 P1 READY 지속. 향후 High가 신규 확장 mock/contract 작업의 적용 범위·경로를 승인하고 **동일 SHA의 설계 문서만** dev에 동기화(진행 중 P1 STATUS/queue 덮어쓰기 금지). 실제 live Hydrogen 호출은 별도 사용자 승인이 있어야 한다.
- **근거:** 설계 브랜치 정확 최종 HEAD는 GitHub 조회; 제품 코드·계정 실연동·가속 실측 `NOT_RUN` / provider extension `DESIGN_ONLY` / 공식 검증률 `UNASSESSED`.


---

## 2026-11-17 KST 최신 설계 추가 — 브라우저 전수 검증 P2 후행
- 사용자 확정: P1(Instant/Codex/Qwen/Hydrogen)은 BE/FE 코드 구현과 syntax/type/최소 build/국소 smoke에 집중한다. 반복 브라우저/Playwright E2E·시각/반응형/a11y 검증은 P2까지 `DEFERRED_TO_P2`.
- 예외: 인증/인가·데이터 손실·비밀·권한/F18 등 즉시 안전 검사는 P1 유지; 실제 브라우저 필수인 좁은 핵심 확인만 사유·SHA·실행 결과 기록 후 수행.
- 반영 파일: `docs/FINAL_BLUEPRINT.md F-1`, `docs/PHASE_GATES.md`, `AGENTS.md`, `INSTANT_RUNBOOK.md`, `REQUIREMENTS.md`, `docs/ACCEPTANCE_MATRIX.md`, `VERIFICATION_TASK_QUEUE.json MLA-V007`, `docs/DETACHABLE_MULTI_MODEL_WORKERS.md`.
- 이번 변경은 **설계·문서/P2 큐 수용조건만 수정**, GitHub에 소스 실행/브라우저 테스트/CI 재실행은 하지 않았다. 구현완료율 상승 0, 공식 검증률 `UNASSESSED`, P2 `LOCKED`, F18 `SECURITY_HOLD`. 기존 dev Instant 작업 결과·진척은 현재 dev HEAD를 다시 읽어야 정확하며 이 설계 브랜치 기록은 실적 대체가 아니다.
- 개발 브랜치 코드/큐/STATUS, main, EAI, AX 원본, 유료/외부 API·권한·원격 PR/Production 미변경. 다음: 설계 SHA 기준 dev에 안전 동기화 후 기존 P1 READY 지속; P2 실제 브라우저 검증은 P1 100% 후보와 High 판정 이후.

---

## 2026-11-17 KST — V1.2 Experience Learning Engine 설계 변경
- **사용자 의사결정:** 변수 수백·수천 개 하드코딩 또는 Sol Max 답변 대량 수집/모델 증류 대신, **MLA 자신이 승인받아 수행한 개발 작업의 실패·수정·독립 테스트·복구 결과를 분석하여 적응형 스킬/전략 추천을 구축**한다. Model-output 자체가 실검증 PASS/학습 정답이 아님.
- **설계 반영 파일:** `docs/EXPERIENCE_LEARNING_ENGINE.md`(대안 비교/BE·FE/API/DB/보안/F18/기억 검색·선별·평가·rollback/EXP-AC-01..10), `docs/OPTIONAL_EXPERIENCE_TASK_QUEUE.json`(EXT-EXP-01..07 설계 only), `docs/FINAL_BLUEPRINT.md I`, `docs/ARCHITECTURE.md`, `REQUIREMENTS.md`, `docs/INTEGRATION_CONTRACT.md`, `docs/SECURITY_MODEL.md`, `docs/ACCEPTANCE_MATRIX.md`, `docs/PHASE_GATES.md`, `AGENTS.md`, `INSTANT_RUNBOOK.md`, `HANDOFF.md`.
- **강제 불변:** 원래 P1 REQ-01..30/28 작업·P2 8검증/LOCKED·F18 CRITICAL HOLD·브라우저 후행, Hydrogen extension 기본 OFF, EAI/AX 원본 보존. 실제 P1 구현완료율/공식 검증률 상승 **0**(이번 설계 변경 기준); 경험학습 구현·실모델·실Windows·소유자 데이터 수집·A/B·CI/브라우저 테스트 **NOT_RUN**.
- **dev 브랜치:** 확인 당시 `dev/instant-implementation-v1@51f4885a44540890996943bc058621d747325c50`. 이 설계 브랜치 변경으로 dev의 코드·큐·진척·STATUS를 덮지 않는다. 가장 최근 실적은 dev HEAD/코드/증거 재조회 필요. AXNODE는 미래 typed-graph export 대상이지 최초 구현 필수 아님.
- **차단/다음:** 확장 큐는 `DESIGN_ONLY_NOT_READY`; 별도 구현 범위·source path 충돌·적법 데이터 권리/동의·F18 신뢰/owner GO 확인 전 실행 안 함. 기존 dev `MLA-012` 등 본선 안전 READY 계속.


---

## V1.3 High final design update (2026-11-17 KST)

- User-authorized source design change: default host Qwen 1 + CodeShield static audit; permanent VM/Sandbox dependency removed from nonexecuting work. Untrusted executable code must still use attested OS isolation + independent F18 before any actual run/promotion; no unisolated host fallback.
- New base design: docs/FINAL_BLUEPRINT.md J, docs/CODE_SHIELD_LIGHTWEIGHT_SECURITY_V1_3.md, docs/OPTIONAL_CODESHIELD_TASK_QUEUE.json (CS-01..08, 0/8 design only).
- This design commit does not ship scanners, install Defender tools, provision AppContainer, execute untrusted code, issue protected signed F18 or change protected Git refs. P1 baseline history 35/39 candidates in dev at the reviewed SHA; formal REQ 5/30, P2 LOCKED, official verification UNASSESSED. No implementation rate increase.
- Dev file sync must preserve dev actual HEAD, 39 source queue/WORK_PHASE_GATES, existing F18 security design and status. Feature branch starts from dev after selective docs sync; owner runtime GO is still false. Reference branch HEAD in exact corresponding implementation handoff rather than a stale design SHA.


---

## 2026-11-17 V1.3 Design final branch topology confirmed

- High design base updated at c9eb919bab83e782e53f8d4d6bf3e5f179715e27, 9c416a22aa061aa9bdb2641713b9d3c3a924aa15, 0ea09e21fa560575d2c5126c240c586d60ed4417. Exact current HEAD must be fetched before additional writes.
- Dedicated feature/code-shield-lightweight-v1 branch was actually created from existing dev commit **59caaf21625e8c06affb824b15f0ca0cb306e61c**; it contains selectively synced V1.2 Experience and V1.3 CodeShield design. Source code, original queues, mandatory CI, existing SWU evidence and P2/owner gates left unchanged.
- Core design: docs/FINAL_BLUEPRINT.md J + docs/CODE_SHIELD_LIGHTWEIGHT_SECURITY_V1_3.md; queue 8 source CS tasks; acceptance docs/CODE_SHIELD_ACCEPTANCE_MATRIX.md. Actual CodeShield core implement 0/8, tests NOT_RUN, Windows/AppContainer/Defender actual configuration unchanged.
- **Active dev/instant-implementation-v1 had concurrent HEAD movement twice** while attempting an exact-lease documentation sync. No overwritten/misaligned commits; selective design sync made on isolated feature instead. Dev branch retains its own latest code and status. Never overwrite dev history or import stale design STATUS/HANDOFF. Subsequent integration requires exact latest SHA and conflict-aware review; main untouched.
- Owner 2+2 retry rule is current, initial 2 failures isolate/replan, second improved attempts 2, cumulated 4 unresolved to Sol Max, critical trust blocker immediate owner request. Existing historical code attempts are not automatically failures.
