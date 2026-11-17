# Worker startup protocol — mandatory for High / Instant / Codex / Astra / OpenCode

> **[PRODUCT IDENTITY LOCK · OWNER CLARIFICATION · 2026-11-17]** `my_local_ai`는 **EAI의 후속 버전/확장판/완성판이 아니다.** EAI는 선택적으로 재사용할 알고리즘·CPU 분석·도구의 **기술 제공원**일 뿐이다. `my_local_ai`의 고유 목적은 **로컬 모델로 소프트웨어 구현을 지속 자동화하는 개인용 개발 시스템**이며, 정책·스케줄·실행/검증 게이트·진척 기준은 `my_local_ai`가 자체 소유한다. 원본 EAI ADR-0002(Qwen INPUT-only)는 EAI 원본의 아키텍처 지침이지 `my_local_ai`의 코딩 워커 사용 제한이 아니다. EAI 전체 13개 목표·자체 모델 연구의 100% 완료는 `my_local_ai`의 필수 조건이 아니다. 자세한 내용 `docs/PRODUCT_IDENTITY.md`. **P1 구현 우선/P2 검증 잠금 정책은 그대로 유지.**

1. Confirm this chat is for `hibi89/my_local_ai` and GitHub branch HEAD (design vs dev). **This is NOT the EAI product:** My Local AI owns its own coding-agent purpose/controller and uses EAI only as an optional source of algorithms; do not import EAI's original full goal/ADR scope. Do not jump to other projects.
2. Read the **topmost** AGENTS.md phase directive, docs/PHASE_GATES.md and WORK_PHASE_GATES.json. Gate is CLOSED while P1 is incomplete.
3. Read HANDOFF/STATUS → REQUIREMENTS/FINAL_BLUEPRINT → real source + tests + **current phase queue only**.
4. When current phase P1: work only on `INSTANT_TASK_QUEUE.json` in bundles of 3–10 independent READY; do not perform full P2 verification manually or call P3 review. Build all real source and acceptance test harness code. Mandatory CI remains enabled, safety-sensitive immediate checks required.
5. When P1 source REQ-01..30 fully candidate implemented, High (not coding model alone) records exact SHA + evidence and explicitly opens P2 gate. A simulated/old SHA CI PASS is not permission to skip the gate.
6. When current phase P2: use `VERIFICATION_TASK_QUEUE.json` only, run full exact-SHA tests, integrate fixes, log PASS/FAIL/SKIP/NOT_RUN, owner Windows/real model/24h separately. Then P3 independent Codex/Astra, P4 High acceptance/OWNER GO.
7. Stop if the wrong phase queue is READY, evidence is forged, F18 trust boundary or original/source integrity is at risk. For such findings report blocker; other non-risk READY P1 work may proceed.

Report each session in format: `PHASE | REQ DONE / REQUIRED REQ | P1 TASK DONE / P1 TOTAL | P2 TASK VERIFIED / P2 TOTAL | implementation SHA | verification SHA | PASS/FAIL/SKIP/NOT_RUN | blockers | next READY`. If verification weights were never approved, display `UNASSESSED` instead of a fabricated percentage.
