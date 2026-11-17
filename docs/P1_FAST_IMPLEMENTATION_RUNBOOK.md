# My Local AI P1 — One-pass implementation fast track

Adopted 2026-11-17 KST by the owner. Applies to `hibi89/my_local_ai@dev/instant-implementation-v1` **P1 source authoring only**. It does not modify `docs/FINAL_BLUEPRINT.md`, the 30-REQ denominator, F18 trust boundaries, mandatory CI, or owner/Production permissions.

## Batch and attempt policy

- **One real coding attempt per task is the target.** Batch **4–6 independent code-READY tasks per `ㄱ`** where the DAG and `allowed_paths` support it. When fewer than four remain safely ready, process that smaller batch and record why; never invent dependency bypasses.
- A *counted attempt* is a distinct source implementation or materially improved fix addressing a documented missing P1 feature. Reading code, planning, queue status, CI waiting, documentation changes and repeat identical edits are **not** successful attempts. Existing historical hardening rounds are not retroactively counted.
- **Default ceiling: two attempts per task**, including one initial implementation and one cause-driven repair. An explicitly recorded High-risk structural exception may allow **three** attempts with a concrete reason, not an automatic third try. Two consecutive failures without improvement STOP that task earlier.
- On source-code completion: mark `IMPLEMENTED_UNVERIFIED`, record changed paths and source SHA, and remove it from code READY; do not re-add merely to increase synthetic test counts. For an existing source-complete task blocked only by **P2 real Windows/browser/model, independent F18, protected signer, remote GO, source provenance**, mark the blocker clearly and move to a different independent source gap.
- When exhausted: record `HOLD_CODE_ATTEMPTS`, original blocker and escalation to High. Never mark a failed task VERIFIED or set `operational_ready`. Continue other independent READY.
- P1 executes **real BE/FE coding** plus syntax, targeted smoke, and immediate high-risk security/authorization/data-loss guards. Preserve mandatory GitHub CI, but do **not** repeatedly wait for full CI on each task. Full Playwright, real Windows/model, 24h, F18 acceptance and broad regression belong to **P2**, locked until all candidate/High/SHA gates.
- Four statuses are different: actual code feature candidate; source REQ accepted for P1 numerator (explicit per-REQ evidence/High decision); P2 official verification; owner runtime or publication GO. Never promote one to another.
- The queue's `p1_fast_track` and per-task `p1_fast_track_attempts` are counted **from this policy's adoption forward**, not a claim about old attempts. `scripts/p1_queue_replan.py` enforces static budget and safety invariants; the coordinator must increment the counter only with a material coding commit and retain the actual source SHA.

## Current blockers are outside a simple re-edit loop

The prior three READY tasks had sources already: `MLA-006` lacked required CLI command routes, now implemented as safe read-only/HOLD responses; `MLA-013` OpenCode effective OS sandbox confirmation and `MLA-018` owner-controlled F18 Git CAS are **runtime/protected-trust blockers**, not reasons to code the same previews repeatedly. They remain `IMPLEMENTED_UNVERIFIED` and are **not** counted as verified/operable.

Next P1 authoring wave: `MLA-012/016/017/020/022` — discover specific implementation gaps in local model adapter, one-repair scheduler, recovery, benchmark, and supervisor; if only P2 proof remains, record as such without adding no-op code. Original `MLA-001/003/009` HOLD untouched.
