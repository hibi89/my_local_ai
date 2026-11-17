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
