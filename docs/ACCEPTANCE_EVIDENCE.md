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
