# My Local AI V1.3 — Zero-VM P1 remaining three SWUs, Codex Sol Max technical handoff

**기준:** 2026-11-18 KST  
**Repo/branch:** `hibi89/my_local_ai@dev/instant-implementation-v1`  
**인수 기준 정확 HEAD:** `f6610ebfca806f1efb923fadd2b8bd3a868e4215` (시작 직전 원격 HEAD 재확인 필수)  
**최종설계:** `design/final-blueprint-v1@05f51849c0efe7303bf57cb78dff576e441063f5`, `docs/FINAL_BLUEPRINT.md` §L  
**중앙 정책:** `hibi89/hackathon-command-center-2026@kmong-productization`, `OWNER_DEV_EXECUTION_CANONICAL_20261116.md` §0J, `GPT6_HIGH_STANDARD_WORK_UNIT_20261117.md` §0E.  
**수단 권장:** **Codex** (인증·서명/DB·소스 보안 코드 구현·검수); 실제 Windows 관리 화면이나 설치/OS ACL 변경은 별도 Owner GO 후 ChatGPT Work/소유자 현장 검증. **실제 호출 모델 가용성: MODEL_UNVERIFIED**; 모델 이름에 근거한 검증 주장 금지.

## 공식 구현 후보 및 불변조건

- **P1 소스 구현 후보 52/55 = 94.55%** (MLA 37/39 + CodeShield 15/16); 독립 P2 검증완성률은 **LOCKED / UNASSESSED**. 이번 마지막 코드 변경에서 완료 후보 +0.
- **남은 3개:** `MLA-SWU-008`, `MLA-SWU-021`, `CS-SWU-012`. 과거 2+2·SWU/REQ/allowed_paths/선행 DAG·SHA 이력 보존. 실패 없는 조회/합성검사는 실패 횟수로 세지 않음.
- **VM·Windows Sandbox·Hyper-V·WSL2·Docker·Windows 컨테이너·AppContainer는 필수/옵션/fallback 의존성 0**. 호스트 Qwen 한 개, CPU-first Pure Player, fixed Typed Operator, 비실행 CodeShield. **AI 생성 Python/JS/셸/테스트·외부 임의 코드는 실행하지 않는다.**
- 정적 스캐너 PASS는 F18 서명·owner 권한·OS 네트워크 격리·Git CAS·원본 쓰기 허가가 아니다. Windows 별도 계정·키·ACL·보안 정책 설치/변경, 사용자 원본·Production/main·유료·외부 민감 데이터 전송·상용 출시에는 **사용자 사전 승인 필수**.
- Owner GO=false, independent F18 NOT_VERIFIED, OS-wide egress NOT_RUN, P2 LOCKED. CI synthetic SUCCESS ≠ real Windows security PASS. 한 번의 Codex 실행이 독립 감사까지 대체하지 않음.

## 지금까지 P1에서 완료한 실제 코드 — 중복 재작업하지 말 것

- `2509904c772b4151797a05d4a077d4151af1dfeb`: Controller/Orchestrator Windows Sandbox preview port 삭제 및 fixed Pure Player route.
- `930174209e5085c3acd7e3f23880b27e476f2181`: CS-007 Semgrep pinned public/synthetic-only static operator, WSB fallback generator 제거.
- `6e6f3d2adc679407f25aabf9ba29a850d64f72f2`: `ax_runtime/isolation_runner.py` 구형 73KB VM/AppContainer 코드를 대체한 19KB zero-VM data-only host Qwen & CPU Pure Player.
- `f53e33af1a3b4bdd527fdc45e6c6c9e817c06162`: Controller→OneModelLock→local Ollama→bounded untrusted source→Pure Player→HOLD 실제 연결.
- `ffb5b6e794d3990f6d231439d1de582b8f87b937`: `opencode_worker.run_in_sandbox` dynamic invoke 경로 항상 HOLD.
- `29cd5163fa8d96fe5cdd093625badb9fc7c732d7`: 공식 P1 52/55 (94.55%) 소스 진척 계산 반영.
- `f6610ebfca806f1efb923fadd2b8bd3a868e4215`: dev 최종설계/CodeShield 문서 디자인 브랜치 정본 동기화, Windows P2 사전조건에서 구형 Sandbox 필수 제거.
- CI evidence: `44156852708`, `44157145064`, `44157411342`, `44157657691`, `44157967462` SUCCESS (syntax + synthetic; Windows live, real F18 NOT_RUN).

## 잔여 단위와 실제 완료 차단

### MLA-SWU-008 — REQ-07 / protected owner signer and grant issuer

- **allowed_paths:** `src/my_local_ai/state/consent.py`. Existing `_WindowsBrokerAPI` verifies fixed named pipe server PID/SID/image/ACL and CNG ECDSA response signature; `exchange_protected_broker` generates challenge, SHA/lease/nonce/expiry binding. Client-side contract and fail-closed path exist.
- **Missing:** The **separately protected owner-signing service SERVER**, custody of a non-exportable private key, authenticated owner action approval and atomic single-use nonce/lease grant database. Windows service SCM principal/ACL, HKLM root, key authorization must be designed and eventually installed only with separate owner GO. A same-process Python HMAC or model-supplied owner boolean is categorically insufficient.
- **P1 acceptance candidate:** real Controller caller→signed owner action service contract→typed action-bound one-shot grant, timeout/replay/key/identity mismatch HOLD, no guest self-signing; exact code SHA + minimal safety checks. Runtime service installation / Windows native end-to-end, owner privilege still NOT_RUN until authorization.
- **Status:** BLOCKED_TRUST; no automatic GO or source completion until actual server implementation available.

### MLA-SWU-021 — REQ-14/15 / independent F18 reviewer trust root

- **allowed_paths:** `src/my_local_ai/review/protected_reviewer.py`. Existing `review_protected_candidate` / receipt parser / fixed policy SHA / nonce/lease/source/result binding, fake-result denial and no-protection-HOLD are reusable.
- **Missing:** Protected **reviewer SERVER separate from the owner/model/controller principal**, trusted candidate source Git readback/immutable scanner evidence, atomic nonce consumption, trusted signed receipt, nonexecuting verifier replacing deprecated untrusted test/guest runtime. No VM/containers, generated tests EXECUTION HOLD.
- **P1 acceptance candidate:** actual source/readback→independent fixed-reviewer dispatch→authenticated signed F18 report and all failure branches; protocol must distinguish `STATIC_ONLY` from `EXECUTED_TESTS` and not assert unexecuted tests PASS. In-process self-review, signed object from user input, or mock signer does not meet trust boundary.
- **Status:** BLOCKED_TRUST, depends on MLA-008. Actual Windows reviewer OS principal/ACL/keys and cross-process tests remain separate GO/P2.

### CS-SWU-012 — REQ-CS-08 / owner-scoped native Defender file scan

- **allowed_paths:** `src/my_local_ai/security/defender_status.py`. Existing file SHA/ancestry/path scope checks, `run_owner_scoped_defender_scan` broker caller, result completion/detection/error/timeout/postscan rehash are reusable.
- **Missing:** Protected scanner broker SERVER using owner action authorization, exact staged-file hash/locked handles and native Defender scanner invocation with explicit no-remediation. It must not silently change Defender settings/exclusions/CFA or remediate.
- **Microsoft documented fixed command** for protected service design: pinned `MpCmdRun.exe -Scan -ScanType 3 -File <exact private staged file> -DisableRemediation`. `MpCmdRun.exe` requires vendor authenticity/installed image identity and **the exit code alone does not authenticate a clean scan**; verify completed scan record, detection and post-scan SHA under separate protected principal. Do not accept self-reported clean results or download/update/policy mutations. Windows Defender cloud behavior / offline egress must be examined; non-approved external source transmission is prohibited. Official docs: https://learn.microsoft.com/en-us/defender-endpoint/command-line-arguments-microsoft-defender-antivirus
- **P1 acceptance candidate:** actual signed owner-action→fixed scoped Defender scan backend→bounded authenticated result→post-run SHA/timeout/cancellation/failure HOLD. Real Windows/engine/OS policy/ACL changes require explicit owner GO; fake bridge remains HOLD.
- **Status:** SOURCE_PARTIAL_HOLD; CS-011 read-only Defender health is implemented, owner scan is incomplete.

## Execution strategy / escalation

1. Re-read remote HEAD and latest final design; do not branch from historical SHA if advanced. Preserve original 52/55 source and safety smoke, avoid blind main merge/force push.
2. Work **one security boundary at a time**. Design protected signer trust root (008) → independent F18 read-only report (021) → optional scoped Defender scanner (012). These share trust structures; avoid conflicting simultaneous writes. Separate branch if an actual multi-worker agent design is approved and non-conflicting.
3. If independent Windows protected identities cannot be produced under current tool/permissions, **do not fabricate completion**. Write sufficient source with interfaces and tests, report actual remaining OS/user authorization; protect everything as HOLD. Do not ask user to provision keys/ACL/service just to obtain a P1% increase.
4. Only count SWU implemented when code provides actual caller→callee→observable result + core failure path + exact SHA + required local syntax/smoke and CI. A client stub/preview/Mock/CI alone does not count. Preserve original SWU/REQ/2+2 history and P2 gates.
5. If bounded changes cannot safely implement all three, return one batched evidence-backed technical finding for GPT-6 High to decide redesign vs explicit owner GO, rather than repeating old AppContainer/VM direction.

**High review status:** This document is an implementation handoff, not independent Codex security approval or P2 final acceptance.
