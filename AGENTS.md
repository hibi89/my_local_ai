> **[OWNER SWU REESTIMATE · 2026-11-17 · ACTIVE P1]** Read `P1_SWU_TASK_QUEUE.json` and `docs/SWU_REESTIMATION_20261117.md` first. **28 legacy tasks → 39 High-sized P1 source SWUs; 18 existing source candidates, 5 first READY.** `INSTANT_TASK_QUEUE.json.tasks/first_ready` exists only for old CLI/guard and evidence history. `ㄱ` executes new `P1_SWU_TASK_QUEUE.json.first_ready` instead. All test/fixture/full CI/browser/E2E/F18/real model validation belongs P2 (old mandatory CI and immediate high-risk safety checks remain). Product code, final blueprint, 30-REQ denominator, trust/owner/remote hold and P2 lock unchanged.

> **[OWNER-SWU-P1-CODE-ONLY-20261117 · LATEST DIRECT ORDER]** 앞으로 모든 프로젝트의 **P1 표준작업단위는 웹 GPT-6 Sol High의 실제 기능 코딩 1회 완료 후보 크기**만으로 산정한다. P1은 BE/FE·DB/API·CLI/Controller의 **실제 실행 로직·호출 연결·핵심 실패 경로 구현**에 집중. 전체 문법/타입/빌드/CI 확인, 종합 테스트 코드·픽스처 작성, 단위/통합/E2E·회귀·브라우저/접근성/반응형·보안/DB복구·Windows/실기기·실모델 검증, 반복 검증 보고는 **P2 검증완료율에서 Codex GPT-6.1 Sol Max가 묶어 실행·결함 수정·재검증**한다. **P2 업무를 P1 SWU 수·작업당 시도 횟수·구현률로 산정하지 않는다.** 다만 P1 실제 코딩에 필요한 최소 syntax/type/smoke 및 인증/비밀/권한/원본·DB 손실/F18 고위험 변경의 즉시 필수 안전 확인, 기존 필수 CI·브랜치 보호, 외부전송/실운용 사용자 GO는 유지한다. 안전 확인 불가 시 위험 실행만 HOLD하고 다른 독립 코드 SWU 작성 계속. SWU는 1회 목표·일반 최대 2회·High 사전 판단 특수 최대 3회, 같은 원인 무진전 2회 HOLD, `ㄱ`당 독립 SWU 4~6개 시도 목표. [해총 공통 SWU §0A](https://github.com/hibi89/hackathon-command-center-2026/blob/kmong-productization/docs/strategy/GPT6_HIGH_STANDARD_WORK_UNIT_20261117.md); 본 최신 배너는 과거 '매번 합성 테스트/CI/문서 보강'과 상충하는 개발량 규칙을 대체한다. 최종설계·제품 고유 안전·P2 LOCK/검증률은 불변.

> **[LOCAL LOCK]** MLA Controller/F18/권리·원본 보존.

> **[OWNER-SWU-P1-ONLY-UNIVERSAL · 2026-11-17 KST · LATEST OWNER RULE]** [공통 High-SWU 표준](https://github.com/hibi89/hackathon-command-center-2026/blob/kmong-productization/docs/strategy/GPT6_HIGH_STANDARD_WORK_UNIT_20261117.md)의 적용 범위는 **MLA/EAI뿐 아니라 향후 모든 프로젝트의 P1 구현완료율 작업**이다. 1 SWU는 **웹 GPT-6 Sol High의 의미 있는 코딩 1회**에 단일 BE/FE/CLI/DB/API/Controller 기능을 caller→callee→상태/결과까지 구현하는 크기다. 0–3점 기본·4–5 분할·6+ High 재설계, 일반 1회/최대 2회·특수 사전 판단 최대 3회, 동일 원인 무진전 2회 HOLD, 독립 SWU 4~6개/`ㄱ` 구현 목표. **브라우저·Playwright·전체 CI/통합/E2E/회귀·보안 종합검수·실기기/실모델/24h 검증은 P1 SWU의 크기/완료 산정에서 제외하고 오직 P2 별도 검증 큐로 이관**한다. 단 P1 문법/타입/국소 스모크 및 인증·권한·원본/DB 손실·비밀·F18 등 고위험 즉시 안전검사, 필수 자동 CI·브랜치 보호·사용자 GO는 보존한다. MLA의 고유 Controller/F18/30 REQ와 P2 LOCK, 실제 보안·권한 승인 HOLD는 유지. 이 배너는 **P1 작업량 기준**만 정정하며 최종설계·기존 코드/이력/공식 검증·출시 상태는 변경하지 않는다.

> **[OWNER-SWU-HIGH-20261117 · REESTIMATE FIRST]** 사용자 직접 명령: **웹 GPT-6 Sol High의 한 번의 실제 코딩 작업 회차**를 1개 표준작업단위(SWU) 산정 기준으로 삼는다. 기존 28 구현 작업/30 REQ를 임의 숫자에 맞추지 말고 **실제 호출자→기능→결과가 한 회차에 완성 가능한 독립 수직 기능 단위**로 전수 분할·병합 재산정한다. 필독 `docs/HIGH_STANDARD_WORK_UNIT_REESTIMATION.md` / [해총 공통 SWU 규격](https://github.com/hibi89/hackathon-command-center-2026/blob/kmong-productization/docs/strategy/GPT6_HIGH_STANDARD_WORK_UNIT_20261117.md) / [담당 실행 Issue](https://github.com/hibi89/my_local_ai/issues/1). S/C/I/D/U 각 0–2점, 0–3점 일반 1회 목표(최대 2회), 불가피한 High 승인 고난도 최대 3회; 동일 원인 무진전 2회면 HOLD. `ㄱ`당 독립 SWU 4~6개 묶음 목표. **현재 순서는 우선 전수 재산정/큐 정합성 확보**이며 단순 시도 예산만 수정하는 것으로 끝내지 않는다. REQ·최종설계·기존 코드/이력·원본 안전·실운영 GO·필수 CI/P2 LOCK 보존. 이 문서 등록 자체는 제품 구현률 +0.

> **[OWNER P1 FAST-TRACK · 2026-11-17]** `docs/P1_FAST_IMPLEMENTATION_RUNBOOK.md` and `INSTANT_TASK_QUEUE.json.p1_fast_track`: one coding attempt target, two default maximum, third only documented High-risk exception, 4–6 independent code READY per `ㄱ`; no redundant hardening or synthetic CI counting as implementation. Stop after two non-improving failures, continue independent READY. No P2/F18/owner runtime unlock. This policy governs task scheduling; the frozen blueprint and required safety gates remain authoritative.

> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

> **[PRODUCT IDENTITY LOCK · OWNER CLARIFICATION · 2026-11-17]** `my_local_ai`는 **EAI의 후속 버전/확장판/완성판이 아니다.** EAI는 선택적으로 재사용할 알고리즘·CPU 분석·도구의 **기술 제공원**일 뿐이다. `my_local_ai`의 고유 목적은 **로컬 모델로 소프트웨어 구현을 지속 자동화하는 개인용 개발 시스템**이며, 정책·스케줄·실행/검증 게이트·진척 기준은 `my_local_ai`가 자체 소유한다. 원본 EAI ADR-0002(Qwen INPUT-only)는 EAI 원본의 아키텍처 지침이지 `my_local_ai`의 코딩 워커 사용 제한이 아니다. EAI 전체 13개 목표·자체 모델 연구의 100% 완료는 `my_local_ai`의 필수 조건이 아니다. 자세한 내용 `docs/PRODUCT_IDENTITY.md`. **P1 구현 우선/P2 검증 잠금 정책은 그대로 유지.**

# AGENTS — My Local AI 통합 프로젝트 (2026-11-17 KST)

## 임무 잠금
유일 대상: `hibi89/my_local_ai`. **독자적인 자율 개발 운영 엔진**을 만들며 EAI의 일부 알고리즘/분석 도구 및 AX Dev Factory의 로컬 코딩 구현을 재사용한다. 다른 크몽 상품·중앙 GitHub App·해커톤으로 전환 금지. 기존 두 레포 코드는 원본 보존; 새 레포에서만 선택적으로 이식하고 변경한다.

## 정본 확인 순서
1. repo / branch / 실제 HEAD 확인
2. `AGENTS.md`
3. `HANDOFF.md` → `STATUS.md`
4. `REQUIREMENTS.md` → `docs/FINAL_BLUEPRINT.md` → `docs/INTEGRATION_CONTRACT.md` 및 `docs/SECURITY_MODEL.md`
5. `WORK_PHASE_GATES.json`→현재 단계 전용 큐(`INSTANT_TASK_QUEUE.json` 또는 `VERIFICATION_TASK_QUEUE.json`)→실제 코드/테스트→첫 READY

## 사용자가 확정한 작업 순서
High: 최초 전체 설계·REQ 전수·보안·BE/FE·DB/API·비용/복구·작업 큐 → Instant: 여러 READY 묶음 구현 후보 100%까지 코드 작성 → 구현 완료 후보 후 전체 CI·통합/보안·결함 수정 → Codex Sol Max(기술) / Astra Max(UI) 독립 검수 → High 최종 인수 → 사용자 실제 운용 GO. `ㄱ`/`ㄱㄱ`은 현재 프로젝트의 승인된 다음 READY 실제 수행. 설계 승인 전 실행 작업은 설계 수정만 가능.

## 불변 설계
- **My Local AI Controller가 계획/실행 상태·작업 승인 검증·스케줄 정책의 정본**이다. EAI 기반 분석기는 선택 가능한 advisory 플러그인으로만 사용하며 끄거나 교체해도 기본 큐가 작동해야 한다. 실제 통과 판정은 코딩 모델·EAI 플러그인이 아니라 별도 신뢰 검증기만 가능하다.
- **EAI 원본 내부**에서는 해당 저장소의 INPUT-only 모델 제한/ADR-0002를 보존한다. 그러나 **My Local AI 전용 Qwen/OpenCode 코딩 워커는 구현·수정·테스트 코드 작성을 수행**할 수 있다. 두 제품의 목표·모델 사용 원칙을 혼동하지 않는다.
- AX Dev Factory F01–F20의 작업 계약·격리 Git 작업트리·SQLite 복구·1회 수정 후 HOLD·의존성·원본 보호 기준을 누락 없이 마이그레이션한다.
- 모델/게스트가 작성한 테스트 PASS 영수증은 독립 증거 아님. F18 신뢰 경계가 실제 분리/검증되기 전에는 미검증 코드를 원본/중요 브랜치에 자동 승격하지 않는다. 안전 우회·비격리 호스트 fallback 금지.
- 리스크나 데이터권한 변경은 즉시 검사. 개발 중 불필요한 전체 CI 대기 금지하나 기존 필수 CI/브랜치 보호 해제 금지.
- **사용자 확정 브라우저 후행(2026-11-17):** P1 Instant/Codex/Qwen/Hydrogen 구현자는 BE+FE 코드/연결을 모두 작성하지만 반복 브라우저·Playwright E2E·시각/접근성/반응형 전체 검증은 `DEFERRED_TO_P2`. P1은 문법/타입/최소 빌드·국소 smoke 및 인증/권한/비밀/데이터 손실/F18 즉시 위험검사 유지. 브라우저 필수/고위험이면 최소 확인만 예외 허용, 사유·정확 SHA·결과 기록. P1 `IMPLEMENTED_UNVERIFIED`는 브라우저 PASS 아님. P2 전체 브라우저 검증은 High의 정확 구현 후보 SHA 게이트 후 `MLA-V007` 등에서 수행. `docs/PHASE_GATES.md`와 `docs/FINAL_BLUEPRINT.md F-1`을 확인한다.
- 외부 Hydrogen/유료 서비스/고객 자료 외부 전송/GitHub App 권한·remote push/PR/OS startup/Production/배포/보안 정책 변경은 사전 승인. 모델은 자체 권한을 늘릴 수 없다.
- PUBLIC repo: .env, 토큰, 모델 가중치, 비밀 프롬프트/고객 자료·민감 소스/DB/개인 경로·실제 실행 로그 원본 업로드 금지. 외부 데이터 업로드·원본 덮어쓰기 금지.
- 작업 결과는 실제 SHA, PASS/FAIL/SKIP/NOT_RUN, 근거 환경, 차단/복구, 다음 READY로 기록. 공식 검증률은 사용자 승인 가중치 없으면 UNASSESSED. 구현 후보와 검증 완료/출시 승인 구별.
- main 직접 변경·임의 병합·force push·커밋 신원 위조/이메일 임의변경 금지. 두 번 개선 없는 재시도 STOP/PIVOT. 정상 코드·Git 이력 보존.

## 소스 참고점 (원본 수정 불가)
- EAI: `hibi89/EAI@feature/kmong-eai-85-p31-20261112`, 기준 SHA `5186cb1aa7928054d56b1cd0a40ea5943a5b3892`
- AX Dev Factory: `hibi89/Freelancer@tools/ax-dev-factory-local`, 기준 SHA `5ab94180471c7ea86344b691fc77ad5c29989071`
- my_local_ai main 최초 bootstrap SHA `960621d6207e6beb22a7e9480e524988196f3d44`
이 기준 SHA는 설계 확인 기록이며 이식 코드의 검증 SHA가 아니다.


---

## 2026-11-17 High V1.1 설계 확장: 탈부착형 모델 워커 (설계만)
- 필독: `docs/FINAL_BLUEPRINT.md`의 H항, `docs/DETACHABLE_MULTI_MODEL_WORKERS.md`, `docs/OPTIONAL_PROVIDER_TASK_QUEUE.json` — Hydrogen은 **선택형 독립 병렬 코딩 워커**, 단순 검증자도 EAI의 필수 판단 엔진도 아니다.
- 로컬 Qwen/AX Dev Factory 계열 core 우선, 공급자 OFF·무료 quota 종료·유료 전환에도 기존 30 REQ 구현 흐름 유지. 웹 Instant 세션 자동 API 호출을 보장하지 않는다. Codex는 별도 구현/후행 독립 감사.
- 새 ProviderPort는 기본 OFF/네트워크 DENY/비용 0. 실제 API·비공개 코드·고객 자료 전송, SDK 계정 활성화·유료 결제·GitHub PR/main·권한·Production은 별도 사용자 GO. mock만 설계·안전 구현 후보 가능.
- 여러 워커의 동시 코딩은 다른 READY, disjoint `allowed_paths`, exact source/plan SHA, worktree·lease·F18 독립 trust verifier를 지켜야 하며, 모델 셀프 PASS를 VERIFIED로 간주 금지.
- 원래 `INSTANT_TASK_QUEUE.json` 28개/REQ-01~30/P1 구현률 분모 30 및 `WORK_PHASE_GATES.json` P2 LOCKED를 **절대 임의 변경하지 않는다**. 확장은 별도 설계/선택형 큐로 추적. 현재 작업중인 dev Instant 소스·STATUS·큐는 설계 브랜치 파일로 덮어쓰지 않는다.

- **모바일 P1 구현·브라우저 후행 실천(2026-11-17 추가 확정):** `INSTANT_TASK_QUEUE.json`의 `MLA-019/021/025`는 브라우저 검증이 P1 수용조건에 포함되지 않으며 `VERIFICATION_TASK_QUEUE.json` `MLA-V007`에서 P1 100% 후보·High·정확 SHA 후 실행한다. P1 FE/BE·테스트 하네스 작성은 필수, 국소 syntax/type/smoke와 고위험 즉시 안전검사는 유지. CLI-only 대상 브라우저 `NOT_APPLICABLE`. P1 FE 작성 완료 시 `IMPLEMENTED_UNVERIFIED + BROWSER_NOT_RUN`을 기록하고 임의 PASS를 내지 않는다. `ㄱ`은 최신 READY 실제 구현을 재개하라는 뜻이다.


## 2026-11-17 P1 IMPLEMENTATION REPLAN — OWNER DIRECTIVE (non-executing code queue)

**Purpose:** unblock P1 BE/FE *code authoring only* without silently treating license, owner signer, reviewer isolation or verification as complete. `INSTANT_TASK_QUEUE.json.first_ready` now lists **P1_CODE_ONLY** tasks whose `p1_code_status=READY_CODE_ONLY`; it grants **no runtime operation**. All original `depends_on` and `status` remain the full acceptance/runtime dependency graph, including `BLOCKED_PROVENANCE` and `F18_SECURITY_HOLD`. New `p1_code_depends_on` expresses *source module authoring dependencies only*. Changing `p1_code_status` NEVER changes `runtime_authorization=HOLD_UNTIL_OWNER_GO_F18_AND_PHASE_GATES` or grants Git/OS/model/remote execution. For actual executor the only valid route is protected owner consent + original acceptance dependencies + independent F18 + pinned SHA + lease + P2/GO; the queue JSON is never a grant. No untrusted original code copying. Source files may be authored and synthetically tested on safe fixtures in P1, with honest `IMPLEMENTED_UNVERIFIED` even if runtime blocked. `scripts/p1_queue_replan.py` rejects missing runtime holds, loosened constraints, incorrect dependencies and fake 100%. This section replaces the older instruction to only edit tasks with `status=READY` for P1 code authoring, **not** the runtime/safety gate.
