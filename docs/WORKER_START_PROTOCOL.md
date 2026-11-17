# Worker startup protocol — mandatory for High / Instant / Codex / Astra / OpenCode

1. Confirm this chat is for `hibi89/my_local_ai` and GitHub branch HEAD (design vs dev). Do not jump to other projects.
2. Read the **topmost** AGENTS.md phase directive, docs/PHASE_GATES.md and WORK_PHASE_GATES.json. Gate is CLOSED while P1 is incomplete.
3. Read HANDOFF/STATUS → REQUIREMENTS/FINAL_BLUEPRINT → real source + tests + **current phase queue only**.
4. When current phase P1: work only on `INSTANT_TASK_QUEUE.json` in bundles of 3–10 independent READY; do not perform full P2 verification manually or call P3 review. Build all real source and acceptance test harness code. Mandatory CI remains enabled, safety-sensitive immediate checks required.
5. When P1 source REQ-01..30 fully candidate implemented, High (not coding model alone) records exact SHA + evidence and explicitly opens P2 gate. A simulated/old SHA CI PASS is not permission to skip the gate.
6. When current phase P2: use `VERIFICATION_TASK_QUEUE.json` only, run full exact-SHA tests, integrate fixes, log PASS/FAIL/SKIP/NOT_RUN, owner Windows/real model/24h separately. Then P3 independent Codex/Astra, P4 High acceptance/OWNER GO.
7. Stop if the wrong phase queue is READY, evidence is forged, F18 trust boundary or original/source integrity is at risk. For such findings report blocker; other non-risk READY P1 work may proceed.

Report each session in format: `PHASE | REQ DONE / REQUIRED REQ | P1 TASK DONE / P1 TOTAL | P2 TASK VERIFIED / P2 TOTAL | implementation SHA | verification SHA | PASS/FAIL/SKIP/NOT_RUN | blockers | next READY`. If verification weights were never approved, display `UNASSESSED` instead of a fabricated percentage.
