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
