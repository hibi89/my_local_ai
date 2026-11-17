> **[OWNER-SWU-P1-CODE-ONLY-20261117 · REESTIMATE OVERRIDE]** 이번 SWU 재산정은 **웹 GPT-6 Sol High의 기능 코딩 1회**만 기준으로 하라. **SWU에는 BE/FE/DB/API/CLI/실제 호출·상태 처리 소스만 포함**한다. 기존 큐에서 CI/문법·타입 전수/보안 종합/브라우저/테스트 하네스·합성 테스트·회귀·실기기·보고 등의 별도 검증 노력을 끌어온 것은 **P2 검증완료율 큐로 이관**하라. P1 SWU 완료의 필수 경로가 이미 코딩되어 있다면 미실행 P2 테스트 때문에 재코딩하거나 분자를 0으로 두지 말고 `IMPLEMENTED_UNVERIFIED`로 판정. 단위·테스트 전용·문서 전용 항목을 SWU로 세지 말 것. 실제 기능 코드에 필요한 최소 syntax/type/smoke·고위험 인증/권한/비밀/원본/F18 즉시 안전 확인과 기존 필수 CI·브랜치 보호/GO는 절대로 해제하지 않는다. 해당 위험 실행은 HOLD 가능하나 나머지 코딩은 계속. 전체 프로젝트 확정설계·REQ 분모·코드/이력·P2 잠금/안전 조건을 유지. [해총 공통 표준 §0A](https://github.com/hibi89/hackathon-command-center-2026/blob/kmong-productization/docs/strategy/GPT6_HIGH_STANDARD_WORK_UNIT_20261117.md)을 우선한다.

> **[OWNER-SWU-P1-ONLY-UNIVERSAL · 2026-11-17 KST]** 이번 재산정은 각 제품만의 임시 최적화가 아니라 **향후 모든 프로젝트에 공통 적용되는 P1 구현단위(SWU)**의 첫 적용이다. **웹 GPT-6 Sol High 1회의 실제 코딩으로 기능 경로가 연결될 수 있는 크기**를 정한다. 브라우저/전체 CI/보안 종합검수/통합/E2E/회귀/실기기 등은 **P2 검증완료율 큐**이므로 SWU 크기·시도횟수·P1 구현완료 조건에서 **제외**한다. P1의 필수 syntax/type/minimal smoke, 인증·권한/비밀/원본·데이터손실·F18 즉시 위험검사 및 기존 필수 CI·GO는 그대로 적용. 1회 완성 목표/일반 최대2회/High 특수 최대3회와 ㄱ당 독립 4~6 SWU는 **P1 코딩 작업에만** 적용되며 P2 작업단위/반복횟수의 한도로 사용하지 않는다.

# My Local AI — 웹 GPT-6 Sol High 기준 P1 작업단위 전수 재산정 지시 (2026-11-17 KST)

**WORK ORDER:** MLA-SWU-HIGH-REESTIMATE-20261117
**대상:** `hibi89/my_local_ai@dev/instant-implementation-v1`
**담당:** MLA 최종설계/작업계획 담당 웹 GPT-6 Sol High. Instant 담당자는 승인된 SWU 큐를 실행.
**기존 분모:** **REQ-01~30 = 구현 REQ 30개**, **현행 구현 태스크 28개**. 28개/30개로 새 SWU를 억지로 맞추지 않는다.
**임무:** 28개 task를 High의 1회 구현 능력에 맞게 **처음부터 실소스·연결·누락을 기준으로 재산정**. 단순 1~3회 시도 예산 적용이나 READY 4~6개 표시는 재산정 완료가 아니다.

## 표준 기준과 즉시 실행 순서
- [해총 OWNER-SWU-HIGH-20261117 표준작업단위 정본](https://github.com/hibi89/hackathon-command-center-2026/blob/kmong-productization/docs/strategy/GPT6_HIGH_STANDARD_WORK_UNIT_20261117.md)이 이번 **작업 분해/크기** 판단에 우선한다. **기준 모델은 웹 GPT-6 Sol High**. `1 SWU`는 High 작업 회차 한 번의 의미 있는 코딩 시도로 **실제 호출자→모듈→상태/출력까지 구현 코드 완성 후보**를 만들 수 있는 1개의 독립 수직 기능. Instant/개별 GitHub API 호출/LOC 수/REQ 개수 기준으로 분해 금지.
- 점수 축 5개 `S(표면), C(계약), I(통합), D(데이터/보안), U(불확실성)`, 각각 0/1/2점. **0–3 표준 1회 목표**, 4–5 우선 분할 또는 근거 있는 High 원자적 예외, 6–10 반드시 High 재분할/고위험 분리(불가피한 경우 사전 High 판단·사용자 승인 아래 3회 예외). D=2/U=2는 점수와 무관하게 위험 검토. 고위험/미승인 실행을 소스 코딩 큐와 섞어 READY로 해제 금지.
- 1 SWU마다 일반 **1회**, 수정 허용 **최대 2회**, 승인된 원자적 고난도 **최대 3회**. `ㄱ` 횟수·CI polling·조회·문서 커밋이 아니라 **실제 기능 소스 구현 회차**를 누적. 같은 원인으로 진전 없는 실패 2회면 즉시 해당 SWU HOLD/High 이관·독립 READY 계속. 모바일 `ㄱ`당 충돌 없는 SWU 4~6개 묶음 시도를 **목표**로만 사용.
- 실제 코드/REQ 경로를 감사하고 `Preview/Intent`, 합성 테스트, 문서·evidence SHA만 있는 단위를 **구현완료로 인정하지 않는다**. 이미 기능 소스 경로가 완성된 것은 별도 표시해 재구현하지 않는다. P1 코드/국소 검사와 P2 실브라우저/전체 CI/실기기 검증, 실운용/외부전송/권한 GO를 구분한다.
- 기존 REQ-ID·확정 설계·원본 안전 제한·브랜치·Git 이력·검증 큐·P2 LOCK을 변경하지 않는다. 작업 수는 **산정 결과**이지 목표값이 아니다. **현재 단계는 재산정**, 구현률 변경 0.

## 산출 요구사항
기존 `legacy_task_id` 전항목을 아래 구조로 전수 매핑하고, 이미 충족된 코드와 실제 미구현 호출경로를 가려 새 SWU 분할·병합안을 제시한다.

```text
legacy_task_id | req_ids | existing_source_paths | caller_to_callee | unimplemented_function |
S,C,I,D,U,total_score | proposed_swu_id | observable_outcome |
code_depends_on | runtime_security_dependencies | allowed_paths |
p1_source_acceptance | p2_deferred_tests | task_attempts (inherited) |
max_attempts | status | evidence_sha | blockers
```

**완료 조건:** (1) 기존 작업/REQ 매핑 누락·중복 0, (2) 각 SWU 관찰 가능한 실제 기능 1개/합리적 크기 점수·근거, (3) 기존 시도·SHA·실패·권리/신뢰 경계 보존, (4) 변경 전후 항목 수·점수 분포·원인별 분할/병합 목록, (5) 첫 독립 READY 4~6개 및 왜 단일 High 회차 내 코드 완성 후보가 가능한지 설명, (6) 위험한 코딩·실운용 게이트 별도 유지, (7) 원격 HEAD/반영 SHA·검증 사실/미실시 구분.

단순 정책 문서 기록으로 완료를 선언할 수 없다. 실제 최종설계/요구사항/소스 전수를 읽고 **기존 정본 큐와 연결된 재산정안**을 확정해야 한다. 재산정 결과로 작업 카운트를 조정할 때는 이전 인수인계/구현 SHA·시도 횟수를 승계하고 기존 큐의 고유 안전 상태와 검증 잠금 필드를 보존한다. 사용자 승인 최종설계는 변경하지 않는다.

## MLA 특별 보존 및 통합 지시
1. 현재 `docs/P1_FAST_IMPLEMENTATION_RUNBOOK.md`, `docs/P1_IMPLEMENTATION_REPLAN.md`, `INSTANT_TASK_QUEUE.json`, `WORK_PHASE_GATES.json`, `scripts/p1_queue_replan.py`, `docs/FINAL_BLUEPRINT.md`, 실제 `src/`와 `tests/`를 전수 대조한다.
2. `p1_code_depends_on`과 원래 `depends_on`/실운영 허가는 **별개 그래프**다. 기존 28 task와 30 REQ에 고정된 큐 무결성 guard가 있으므로 **고유 작업 번호를 강제로 개정하거나 guard를 끄지 않는다**. 먼저 대응표와 새 SWU 계획을 제시하고 승인된 분해가 확정되면 guard·큐·수용행렬을 **함께 일관되게** 개정한다. 기존 28 IDs·evidence SHA·시도 이력은 legacy mapping으로 영구 유지.
3. **Controller→Qwen/OpenCode 코딩 워커→Git worktree→독립 reviewer→결과/상태 UI**의 실제 미구현 연결을 소스 기준으로 우선순위화한다. 순수 Intent/Preview, mock receipt, 28개 source-evidence만으로 자율개발 루프 완성 인정 금지. **F18 독립 신뢰 검증, owner signer, Windows sandbox, 원본 보호, 권리/출처 미해결 부분은 실운영 HOLD**를 유지한 상태로 P1 코드 작성과 분리한다.
4. 최종설계·P1 구현 REQ 분모 30, P2 LOCK, 외부 API/원본/깃 원격/Production·보안/유료 GO는 절대 변경하지 않는다. 이전 `5/30` 같은 과거 진척 수치는 최신 소스/REQ 감사로 재평가하되 증거 없는 분자 증가는 금지. 최신 SHA와 실제 코드 상태가 기준.
5. **변경 예정 files:** 기존 `INSTANT_TASK_QUEUE.json`/현행 Runbook에 대한 SWU 매핑 및 이후 안전한 queue migration, 필요시 `docs/PHASE_GATES.md`의 **작업단위만** 정정. 제품 최종설계의 기능/보안 수용 조건 수정 금지.

**다음 MLA `ㄱ` 실행 첫 단계:** 이 재산정 대응표와 High 1회 구현 용량 검사 → 정합성 확인 후 첫 READY 4~6개 실제 미완성 기능 코드 구현. 단순 상태 공지만 반복하지 않는다.
