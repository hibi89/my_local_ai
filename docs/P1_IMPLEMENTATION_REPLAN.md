# My Local AI P1 Implementation Replan — 2026-11-17 KST

## Decision
The former queue used a single dependency edge for (1) safe source authoring and (2) actual operating authority. This starved P1 READY after partial code was written. We now track **two separate dependency graphs** without changing the original 28 tasks, 30 REQs, design or actual security acceptance:

- `depends_on` plus `status` are **unchanged runtime/full-acceptance prerequisites**. The existing F18, owner GO, source rights, Windows isolated executor, original SHA/CAS, paid/network/offsite data gates and P2 remain on HOLD. No executable work order comes from this JSON.
- `p1_code_depends_on` + `p1_code_status` + `first_ready` schedule **code-only implementation** with synthetic data, no dangerous run/host command. `first_ready` only includes `READY_CODE_ONLY` tasks; runtime status stays `BLOCKED_DEPENDENCY`. Finished code returns `IMPLEMENTED_UNVERIFIED`, never `VERIFIED`.
- Source reuse: `MLA-001 BLOCKED_PROVENANCE` and imports list unchanged. Own clean-room modules are allowed to be authored and unit-tested as separate code work, not credited as license clearance.

## Competing solutions considered
| Plan | Throughput | Cost | Safety & upkeep | Decision |
|---|---|---|---|---|
| A: require original full-acceptance/F18 for every P1 source module | idle queue; serial bottlenecks | free but slow | strongest apparent check, wrongly couples coding and operation | reject |
| B: remove blockers/set all tasks executable | fast but unsafe | uncontrolled | violates F18, consent, source rights, protection | reject |
| **C: dual code-only and runtime DAG with explicit HOLD** | parallel source BE/FE/security tests | free | separate source scheduler and operations; no gate bypass | **adopt** |

## Batch and dependency map
| Wave | P1 code tasks | Preconditions | P1 acceptance boundary | Execution restrictions |
|---|---|---|---|---|
| 1 | MLA-017, MLA-028, MLA-030 | existing 007/010/014/008/004/015 code evidence | lease/reconciliation, optional EAI adapter, security scenarios on synthetic data | no protected DB writes/owner originals, external EAI import, real shell |
| 2 | MLA-018, MLA-019, MLA-022 | prior code evidence + 013/016/020/006 | integration CAS contract; controller orchestration; supervisor/resource monitoring | Git local ref must remain unchanged, no unattended run/production |
| 3 | MLA-023, MLA-025, MLA-029, MLA-024 | 018,019,022 output | remote preview, E2E fixtures, reviewer Windows harness, publish gate | no remote push/PR, no browser run before P2, no owner OS policy changes |

**Safety still to implement** before real owner use: Windows sandbox + protected owner signer; accurate Git worktree creation with ignored/hooks/filter controls; independent reviewer executable and receipt issuance; Git CAS integration; trusted restart/lease state. Tests in CI are synthetic code-level checks, not OS proof.

## Mechanism
1. Run `python scripts/p1_queue_replan.py`: verify 28 task IDs, exact 30 REQ denominator, dual dependencies and the presence of source evidence, all 28 runtime authorization fields set HOLD, original provenance/F18 blockers intact, P2 locked and code-only READY consistent.
2. One or more `p1_code_status=READY_CODE_ONLY` tasks may produce owned-source files within `allowed_paths`; write synthetic tests, syntax and immediate security checks. Their original task `status` stays as-blocked until *all* full acceptance conditions are separately met.
3. Commit code and attach SHA to task evidence, then re-evaluate for next batch. Record exact tested SHA, names and PASS/FAIL/SKIP/NOT_RUN. Never infer % from task count or partial code.
4. Owner/High must explicitly assess rights, independent F18, Windows trust-root, user consent and final scope to remove full-acceptance blockers. `WORK_PHASE_GATES.json` P2 only unlocks at evidenced 30/30 implementation + High SHA.

## Current baseline
P1 5/30 = 16.67% completed REQ code candidates (REQ-04/08/10/18/29). Newly authored partial modules must **not** be counted until source/function acceptance fully met. Official verification UNASSESSED. P2 LOCKED. GitHub dev branch only, no original/Production edits.

## Code-only Wave 1 recorded (2026-11-17 KST)

- MLA-017: `c792bbeaf6fd14d1415943e6398f8251b17d680f` — stale/duplicate lease pure fence and read-only SQLite/Git recovery protocol; no protected writes
- MLA-028: `5ac1b6ec5ab3f8cb80c9c999c6a343aebca37e64` — source-pin checked optional EAI advice data, no EAI original source import or execution
- MLA-030: `9d6e63a3bf7f5fa274eb7b00e61df2e9f50c465e` — synthetic adversarial leak/hooks/injection tests
- P1 safe integration CI `44017659318` PASS. Original runtime task statuses still `BLOCKED_DEPENDENCY`; no independent F18 or owner signer GO established. Next `MLA-018` source-only, not ref promotion.

## Wave 2 code evidence (2026-11-17 KST)

- MLA-018 pure isolated local CAS intent `46f6995ea7456f77632826712247ec099aa2582e`; cryptographic inspection alone never permits promotion; all Git writes disabled. Safe synthetic CI on exact source SHA PASS.
- Current P1 code-only READY: MLA-019 BE/FE synthetic integration, MLA-023 **read-only** remote preview. Their original runtime statuses stay `BLOCKED_DEPENDENCY`, with runtime_authorization HOLD; no remote API/PR/actual original changes.

## Wave 3 in progress (2026-11-17 KST)

- MLA-019 Controller→redacted read-only app synthetic journey source `5b6f5c83d2c3dae51db8a103422d952a4e58138d`.
- MLA-023 read-only remote action preview source `efc2f33713ed4c3af77583b2d276cf601615f12e` (fixed rejected traversal-like repo IDs after synthetic regression), no API/push/PR capability.
- Next independent code-only READY: MLA-022 supervisor/resource synthetic policy, MLA-024 action-bound remote publish fail-closed gate, MLA-029 Windows trust-boundary fixture authoring. Runtime task statuses remain BLOCKED and P2 locked. This audit now pins every original runtime `depends_on` edge and tests are dynamic across code-only waves.

## Wave 4 source evidence and wave 5 code-only READY (2026-11-17 KST)

- MLA-022 supervisor resource/thermal/lease policy `8996b5bb56188a3fcc132f0bf87b43af9e6e6b33`; synthetic 24 samples do not simulate 24 real hours.
- MLA-024 denied-by-default action-specific remote publish gate `4fe0adc1b8c1e54ea358ce311c88550cd548de1a`; no network/PR/push.
- MLA-029 Windows F18 owner-test harness and evidence ledger `a426c690d25c29c6e96fff7e2d226e23a75de51a`; actual Windows owner and F18 independent isolation `NOT_RUN`.
- Next P1 code READY MLA-025: write E2E and Windows test **source**, not browser or hardware execution. Full runtime status remains blocked. After this wave, prioritize strengthening real P1 gap modules rather than mistaking file evidence for complete REQs.

## End of first P1 code-only source wave, second hardening wave opened

All 28/28 task entries have code evidence SHAs (not completion). `MLA-025` P2-gated source SHA `20e81dea7abb78769a3311f378f43f7e96b9273a`. Next code READY `MLA-014`, `MLA-015`, `MLA-017` for protected Git worktree, reviewer issuer and SQLite lease transaction hardening. Original runtime status `BLOCKED_DEPENDENCY` and source rights/F18/owner P2 holds remain. See STATUS for exact 209/209 synthetic test breakdown and why REQ implementation is still 5/30.


## 2026-11-17 KST 2차 하드닝 — MLA-017 합성 SQLite 원자 리스

- 최초 코드 전용 큐 재편 5개 wave 후, 추가 구현 `src/my_local_ai/ax_runtime/leases.py`, `tests/integration/test_crash_resume.py` 최신 소스 SHA `471e4b601c0cb50fb8b0bd6de71fd79495ee187e`. HMAC `LOCAL_PLAN` owner claim, exact plan/source SHA, user/owner consent rows, `BEGIN IMMEDIATE` task/runs/leases atomic mutation, idempotent epoch fence, duplicate RUN and revocation/rollback HOLD. **테스트 연결은 오직 `:memory:` SQLite로만 허용**; 실제 고객/원본/디스크 DB는 아예 거부. 출력 `can_run_coder=false`이고 OS protected signer/F18/실 Git ref 증거는 없다.
- 큐 `MLA-017`은 2차 **`READY_CODE_ONLY`** 유지: 실제 owner Windows protected SQLite transaction, crash-to-ref reconciliation, real F18 결합이 미구현. `MLA-014`/015도 독립 code-only 보안 하드닝 READY. 원래 `status=BLOCKED_DEPENDENCY`, provenance·owner GO·F18·P2 잠금 불변.
- GitHub Actions `44018982422` @ `471e4b601c0cb50fb8b0bd6de71fd79495ee187e` **SUCCESS**: Python syntax PASS, 합성 단위 **88/88 PASS**, 모의 통합 **41/41 PASS**, 합성 보안 **85/85 PASS**, 총 **214/214 PASS**. 중간 CI `44018723958`, `44018882552`, `44018912841`는 **동적 큐 테스트의 구형 고정 의존성 가정 때문에 FAIL**, `471e4b6`에서 개선 후 재검증 PASS. 미검증 Windows/Ollama/OpenCode/24h/브라우저 `NOT_RUN`.
- *공식 P1 구현완료율* 기존 **5/30=16.67%**, 28/28은 단지 작업별 code-source SHA 증거 존재. P2 LOCKED/검증률 UNASSESSED, 사용자 실사용 HOLD. 이번 라운드에서 main/원본/remote/OS/Production/유료 API 변경 없음.

---

## 2026-11-17 KST 다음 `ㄱ` 회차 — P1 2차 보강 3건 및 OpenCode V2 위험 수정

- **실제 시작 HEAD:** `030e6bb9b970b379273ee13686a134061688dcd3` / `hibi89/my_local_ai@dev/instant-implementation-v1`. 정본 AGENTS, 큐, P2 gate 읽고 READY `MLA-014/015/017` 묶음 구현.
- **MLA-014 worktree/permissions:** `93580dd96b9bd4c634cfbf76d88a08e2a9ef9c09` 추적파일 모드·SHA/dirty/untracked/ignored·hook/filter/custom config·original/main/readback 확인 순수 로직 및 적대적 테스트; `0195984c8d3d5cb2f200b73c462973a563227a18` linked worktree `.git` file ↔ original `.git/worktrees/<id>/gitdir` 양방향 경로 검사, redirect/link 교체 차단. **실제 Windows Git worktree 생성/OS isolation/Git filter 실효 검증 NOT_RUN**, OS 사용권/메인 업데이트 없음.
- **MLA-015 independent reviewer contract:** `4d26317de0fa0cfcd2a8d6d9bf4b54512a740fc8` fixed three check argv/timeout/no-network & sha256 policy, reviewer request source/plan/candidate SHA/trusted binary digest binding, no host fallback; intermediate Actions `44020144931` FAIL revealed `lease_epoch=0` forgery accepted after request dataclass mutation → fixed `5ee8426442d5bffb40c9c46826298540ad40fcb3`, Actions `44020309952` PASS. Signed synthetic receipt replay nonce one-use test. Protected reviewer executable/issuer and Windows independently protected principal STILL HOLD.
- **MLA-017 lease and crash recovery:** `f7074c60e9ab516980be0e02b22cf46bd0d9d080` strict read-only SQLite reconcile for orphan run, VERIFIED without integration, invalid review result, mismatched candidate/review/integrated SHA, active lease/integration conflict, duplicate epochs and STOPPED plan. No DB modifications outside temporary synthetic fixtures; **live protected owner signer/OS and actual crash-to-Git ref verification NOT_RUN**.
- **MLA-013 incidental critical fix:** after confirming current official <https://opencode.ai/docs/permissions>, <https://opencode.ai/docs/policies>, <https://opencode.ai/docs/config>, fixed singular `plugin` key → `plugins:[]`, disabled auto update, OpenCode V2 `tool.use:*` hard deny with exact `read/edit:<allowed_path>` exception, local Ollama only. Source `67152488727fc96c221a2878afc92ea105347c21`, synthetic regression revised `c43169e095d19143fe15d6b51cfa81ced73e8409`. Actions `44020615118` FAIL due previous test's obsolete policy schema expectations; test updated, **latest exact source Actions `44020652516` SUCCESS**. **OpenCode executable/version and actual policy effectiveness in Windows NOT_RUN**.
- **P1 synthetic CI** at tested SHA `c43169e095d19143fe15d6b51cfa81ced73e8409`: Python3.11 syntax PASS; unit **88/88 PASS**, synthetic integration **56/56 PASS**, security **122/122 PASS**; total **266/266 PASS**, prev 214, +52. CI is NOT P2/Windows/F18, full browser/24h and independent Codex/Astra NOT_RUN.
- **Implementation REQ rate remains 5/30 = 16.67%**, 28/28 task source evidence SHAs do not mean 28 tasks accepted. Full runtime blockers for MLA-001 provenance / MLA-003 F18 / MLA-009 protected owner GO and downstream remain HOLD. No user real-device work, main/Production/GitHub App/remote or paid services changed.
- **Next P1 code-only READY (no execution privilege):** MLA-018 actual local CAS protected adapter code, MLA-019 BE/FE controller workflow hardening, MLA-023 safe remote preview. Their original runtime status remains BLOCKED_DEPENDENCY. After these, return to F18/owner signer/Git/worktree true runtime code gap and High re-assessment; P2 stays LOCKED.

## P1 wave transition — 2026-11-17 KST

Finished current **code-only** batch MLA-018/019/023. Synthetic Actions `44021629768` PASS on `9a9305e22cae52dd8f8e82d333b2d86a998b967e`: unit 93, synthetic integration 62, security 128, total 283/283. True real Git CAS, owner OS signer, F18 isolation, OpenCode binary, actual protected remote target and browsers remain **NOT_RUN**. Source evidence SHA is not full REQ implementation acceptance.

Next tasks `MLA-006` (complete CLI surface), `MLA-021` (usable local read-only FE), `MLA-008` (native Controller scheduling) are **P1 source hardening**. These may have an existing original task `status=IMPLEMENTED_UNVERIFIED` — that status grants no execution. Queue auditor and read-only FE now accept `BLOCKED_DEPENDENCY` OR `IMPLEMENTED_UNVERIFIED` for code-only READY, while still refusing `READY`/owner GO/execution. Original design, runtime dependency DAG, and locked P2 unchanged.

---

## 2026-11-17 KST — P1 Instant 6개 소스 작업 묶음 + 코드 큐 전환

- **Repo/branch:** `hibi89/my_local_ai@dev/instant-implementation-v1`. **시작 HEAD** `91dffc3fb78550dd419d9bacefdbe7b216ddcdd1`; 최신 코딩·CI 기준 SHA `b9a99894ded8fb870973b327252ee77af6403e8c`.
- **MLA-018 REQ-21 부분 구현 보강:** `9073a0c2b845c5d566453e36763abbc67e66aa60` `src/my_local_ai/gitops/local_integration.py`, `tests/security/test_integration_gate.py`: 순수 메모리 isolated local ref CAS, 정확 expected-old SHA·owner original/main·후보 고정, 중복/레이스/위조 권한 거부, original/main 불변. 실제 OS-protected git-ref CAS, 독립 F18, owner approval 미연결. 영구 Git 변경 없음.
- **MLA-019 BE/FE 통합:** `3fdf98cc2468e457054bd44d1371d47d536058c9` `orchestrator.py/app.py/test_synthetic_journey.py`: Controller 자체 DAG READY → Qwen/OpenCode 로컬 요청 준비(`prepare_opencode_run`, 실제 미실행) → 안전하게 redacted FE 카드. 비밀 prompt/원본 경로/실행 명령 무노출, F18 미검증 유지. 실제 Windows/OpenCode 실행 NOT_RUN.
- **MLA-023 read-only draft PR:** `9a9305e22cae52dd8f8e82d333b2d86a998b967e` `gitops/remote_preview.py` 및 단위 테스트: target base branch+SHA pin, 보호 정책 boolean·변경경로 lexical/synthetic 검사, 문자열 외부 노출 금지. 원격 GitHub API·push·PR 실제 동작 없음; 별도 REMOTE_PR GO 요구·HOLD 유지.
- **MLA-006 실제 CLI 코드 보강:** `86d14297824b0220548e27363801b390e6918c1c`: `python -m my_local_ai queue next`는 P1 코드전용 READY/실행권 0을 출력, `evidence`는 합성 CI SHA/counts·실 Windows NOT_RUN, `stop/resume --task-id`는 보호 owner runtime 연결 전 상태 변경 없이 **HOLD(exit 2)**. 모델/OS 실행 없음. 보안/단위 테스트 PASS.
- **MLA-021 FE 보강:** `c1cda91504c137f6e57878bc9d7c949256ff3175`: 기존 127.0.0.1 only 읽기전용 서버에 `/evidence.json`와 합성 CI 표시·소스 검증 P2/실 Windows HOLD 표기. 실제 Playwright/실기기 브라우저 NOT_RUN. 기존 HTTP 국소 smoke는 실행.
- **MLA-008 Controller 병목 완화:** `b9a99894ded8fb870973b327252ee77af6403e8c`: `controller/decision.py`, `test_own_controller.py`에 작업별 허용 파일 overlap, task/max-call/max-seconds 예산, 신뢰 DAG, 독립 lease, EAI 선택형 힌트 동일 risk 정렬을 고려하는 **비실행 배치 계획** 구현. one-model lock/실제 병렬 실행은 별도 보호 OS 경계 대기. 코드 계획을 실행 승인으로 승격하지 않음.
- **GitHub CI 최신 확인:** Actions `44022159155` @ `b9a99894ded8fb870973b327252ee77af6403e8c` **SUCCESS**: Python 3.11 문법 PASS; unit **106/106**, synthetic integration **62/62**, synthetic security **128/128**, 합계 **296/296 PASS**, 기존 266 대비 +30. 실 Windows/Qwen/OpenCode/F18 OS 분리/24h/실브라우저/독립 Codex·Astra 검수 **NOT_RUN**.
- **진척 분모/단계:** `code_req_completed` **5/30 (16.67%) 유지** — 이 회차 코드는 수용조건 전체 완료가 아닌 기존 REQ의 부분 구현 강화. 작업별 28/28 code-evidence SHA 존재 ≠ 28/28 수용 완료. `WORK_PHASE_GATES.json` P2 **LOCKED**, 공식 검증률 UNASSESSED, 원본 라이선스/owner protected signer/F18 실제 OS-security HOLD. `docs/FINAL_BLUEPRINT.md` **변경 없음**.
- **차단 및 다음 READY:** 원본 이식 `MLA-001 BLOCKED_PROVENANCE`, 실제 owner signer `MLA-009 TRUST_ROOT_HOLD`, F18 OS independent reviewer `MLA-003 SECURITY_HOLD`; actual worktree Git/CAS/promote, real owner Windows 검증 NOT_RUN. 다음 **코드 전용 READY** `MLA-016` 1회 개선 후 HOLD/복구, `MLA-022` 자원 감시·감독, `MLA-024` 원격 게시 승인 경계. 원본/정본 변경·main/Production/유료 호출/외부 전송 없음.
