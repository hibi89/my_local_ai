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
