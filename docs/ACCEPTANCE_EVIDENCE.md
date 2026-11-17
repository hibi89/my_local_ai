# My Local AI — Acceptance Evidence Ledger (2026-11-17 KST)

## Scope separation
P1 is source implementation candidate; P2 is locked until High exact SHA gate and full REQ-01..30 implementation. A passing GitHub synthetic test does not prove owner Windows F18, protected signer, runtime feature working, 24-hour soak, browser/a11y, real local model or launch approval.

| Verification item | Evidence level | Status | Meaning |
|---|---|---|---|
| Existing Python 3.11 unit/security/GitHub CI | synthetic CI | observed per exact run SHA | compile/pure contract tests, NOT OS test |
| Independent Windows Sandbox reviewer | owner OS | NOT_RUN | no real protected reviewer principal/evidence |
| Owner signer and revocation on Windows | protected owner device | NOT_RUN | model cannot mint operating grant |
| Actual Qwen/Ollama/OpenCode integration | owner Windows | NOT_RUN | no real local code worker execution |
| Actual Git isolated local CAS | trusted owner OS | NOT_RUN | only nonexecuting intent tests written |
| Real Windows hook/filter/NTFS attack | owner OS | NOT_RUN | filename/FS synthetic preflight only |
| Browser/keyboard/accessibility/Console | actual browser | DEFERRED_TO_P2 | code candidate is not browser PASS |
| 24-hour long-run, thermal/power | real Windows hardware | NOT_RUN | resource synthetic readings are not proof |
| Independent Codex/Astra reviews | separate model same SHA | NOT_RUN | cannot self certify |
| Owner real-use GO | owner action | HOLD | no public release or automatic original changes |

## P2 readiness gate
Must have exact code SHA and High candidate 30/30 evidence; owner-protected signer; independent isolated Windows coder/reviewer principals; read-only original SHA and isolated CAS; actual acceptance commands and approved fixture; no secrets transferred; measured hardware/thermal/throughput; distinct reviewer attestation. None can be replaced by a guest JSON file or GitHub synthetic CI.

## Implementation wave notes
The `INSTANT_TASK_QUEUE.json` `p1_code_status` fields track source writing only. `status` and `depends_on` remain full runtime/acceptance gates. `p1_ready_mode=CODE_ONLY_NOT_RUNTIME`, `operational_ready=[]`, `WORK_PHASE_GATES.json` P2=LOCKED.

## 2026-11-17 MLA-025 P1 Test Source Checklist (execution deferred)

- `tests/e2e/test_owner_journey.py` enumerates 10 owner E2E scenarios covering Controller/app/EAI-off/GO/F18/CAS/recovery/remote/keyboard. Its actual test class refuses to run without `p2.status=P2_VERIFICATION`, documented `30/30` code candidate and exact High-approved SHA, and **still requires an independent owner-runner implementation**. Nothing is labeled PASS here.
- `tests/windows/test_windows_acceptance.py` enumerates 10 real Windows checks: genuine Sandbox isolation, protected signer, no egress, lease/crash/original SHA, model, RAM/VRAM/temperature and 24h. All real owner hardware tests are unconditionally skipped in this P1 candidate. `NOT_RUN` is authoritative; passing Python3.11 compile alone does not certify them.
- These two files are authored source only, **not placed in mandatory P1 unit or synthetic integration test discovery**. Full Playwright/browser E2E, Windows hardware, 24h, provider, independent reviewers and operational release remain P2/P3/P4.

## Last P1 synthetic CI evidence

GitHub Actions `44018595764` at `20e81dea7abb78769a3311f378f43f7e96b9273a`: Python compile PASS; unit 88/88 PASS; synthetic integration 36/36 PASS; synthetic security 85/85 PASS. Real owner Windows, P2 browser and 24-hour tests not executed and not implied. The `p1_code_status` dual graph is authoring-only; 5/30 full REQ implementation candidates remain. 

Latest P1 synthetic run `44018982422` on `471e4b601c0cb50fb8b0bd6de71fd79495ee187e`: **214/214 PASS** (88 unit, 41 mock integration, 85 security) and syntax PASS. Owner Windows real F18 24h browser full verification NOT_RUN. 

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

---

## 2026-11-17 KST — P1 9-task long batch second wave

- **Repo:** `hibi89/my_local_ai`, branch `dev/instant-implementation-v1`; previous update HEAD `e6b994696c67144314fd325ed5ef3cbd30178e27`. No `docs/FINAL_BLUEPRINT.md` changes, no original EAI/AX or main/prod/remote modifications.
- **MLA-016 retry logic:** `f737e8973c0d01cbf4309b9c1053d7a3b812fdab`, `src/my_local_ai/ax_runtime/recovery.py`, `tests/unit/test_repair_once.py`. A second attempt needs a changed enumerated corrective strategy, safe error fingerprint, exact plan/source/lease epoch, first failure; no same-method retries, second failure HOLD, protected user GO needed. Does not run coder or auto-retry.
- **MLA-022 resource/thermal:** `1c4bddb9fdcd6a0a999f90cec48e24b6b025363b`, `src/my_local_ai/ops/resource_monitor.py`, `tests/integration/test_long_run.py`. Synthetic resource window checks monotonic sample sequence/time, cumulative sensor/memory/thermal anomalies, missing samples. Fake 24h timestamps cannot establish actual hardware readiness; no OS signals, process control or worker restart.
- **MLA-024 one-action remote digest:** `1c4bddb9fdcd6a0a999f90cec48e24b6b025363b`, `src/my_local_ai/gitops/remote_publish.py`, `tests/security/test_publish_approval.py`. A public-synthetic draft PR action has a pinned base/candidate SHA and exact action fingerprint, but no signer, upload, push, PR creation or main merge. Owner GO for each remote action remains HOLD.
- **Latest P1 synthetic CI:** Actions `44022642272` at `1c4bddb9fdcd6a0a999f90cec48e24b6b025363b` SUCCESS; Python 3.11 syntax PASS; unit **110/110**, synthetic integration **66/66**, security **130/130** = **306/306 PASS**. No real Windows/Qwen/OpenCode/F18 OS attestation, 24h owner hardware, or browser P2 run.
- **Overall current user `ㄱ` round:** source commits for MLA-018/019/023 + MLA-006/021/008 + MLA-016/022/024 = nine distinct P1 code-only tasks, 306 synthetic tests (prior 266). This is actual code/test work, but **REQ full-acceptance completed count stays 5/30=16.67%**; 28/28 task code SHA presence is NOT 28 completed. P2 `LOCKED`, verified rate `UNASSESSED`, real-use `HOLD`, all 28 runtime authorization flags still HOLD.
- **Next P1 code-only READY:** `MLA-005` benchmark evidence, `MLA-020` real-model benchmark source/harness (real model runs P2 only), `MLA-007` protected SQLite/schema/backup source hardening. Do not activate model or touch user/customer DB without separate GO. High architect must eventually finalize actual Windows owner signer/F18/worktree protected driver and rights gate before REQ completion.


## 2026-11-17 P1 benchmark/SQLite/recovery synthetic source evidence

At code SHA \`fcdd0371eab25691a9c1e97f1575875f31c5b079\`, mandatory Actions \`44025805677\` SUCCESS: compile, 120 unit, 75 synthetic integration, 130 synthetic security = **325/325 PASS**. Prior \`bc01f347...\` 2 regression errors due empty TEMP metadata were corrected in the next code commit. MLA-005 fake workload cannot prove actual tokens/sec/accepted REQ/hour; MLA-020 real Qwen/Ollama never called; MLA-007/017 checks only disposable SQLite data, not user Windows ACL/physical recovery. Independent OS F18, owner signer, real model, 24h and browser remain NOT_RUN, official verification UNASSESSED, code REQ 5/30.
