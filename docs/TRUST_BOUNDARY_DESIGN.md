# F18 — independent trusted reviewer and receipt trust-boundary contract (P1, MLA-003)

**Status: IMPLEMENTED_DESIGN_AND_ADVERSARIAL_FIXTURES_ONLY. No trusted reviewer executable, OS separation, or independent PASS has been demonstrated.** This design is not an authorization to run guest code or to promote a Git ref.

## Non-negotiable architecture

1. **Owner/Controller trusted side** loads the immutable owner consent from separately protected storage, pins exact plan digest, scoped repository/worktree/baseline SHA, run_id, nonce and lease epoch. The coding worker has zero write access to owner consent, the reviewer binary/config, reviewer output channel, or local protected Git refs.
2. **Coder guest** may only write candidate diff and its *untrusted* outbox under a disposable, explicitly allowed worktree. Guest output including JSON, logs, exit codes, SHA, signatures using guest-visible keys, test reports and a field saying VERIFIED are all untrusted and must never be fed directly into a promote operation.
3. **Trusted reviewer environment** is independent from the coder and has its own protected inputs, fixed tool/image digest, policy-versioned allowlisted argv and denied egress. It must *not* execute untrusted tests/scripts on an unisolated host or under the host's secrets-bearing principal. If independent isolation cannot be established on Windows, return HOLD. A GitHub Actions run is not a substitute for the user's independent Windows security boundary.
4. The trusted side computes candidate hash and changed-path set from its own preserved baseline, validates symlinks/reparse points/ignored paths/hooks/filters and approved scope, and runs only fixed checks in the isolated verifier. A model-supplied argv, test count, test reduction, or change of required checks is always denied.
5. **TrustedReceiptV1** may be issued only by a reviewer principal inaccessible to the coder. It binds: schema_version, trust_boundary_id, exact candidate_sha, approved_plan_sha, source/baseline_sha, owner_consent_id, task_id, run_id, lease_epoch, nonce, reviewer_tool_sha, checks (argv_id, environment, exit_code, result) and policy digest. Attestation and storage must be protected from guest writes and replay. Hashes alone provide integrity, not provenance/independence.
6. **Local integration** (separate MLA-018) must check current live owner consent, plan/SHA/branch/worktree, lease generation, reviewer-issued attestation, candidate SHA, trusted readback and CAS against the *same* pinned source. It may update only an isolated local ref, never main/original or a remote branch without separate owner GO. Missing verification, mismatched SHA, stale epoch, missing checks, forged output or changed approval => HOLD.
7. Failed checks allow at most one improved correction; then HOLD that task while unrelated READY continues. Never use host fallback or bypass a mandatory test to make progress.

## Threat → mandated denial

| Attacker attempt | Result |
|---|---|
| guest writes {"result":"PASS","issuer":"trusted"} | HOLD; guest-controlled claim not evidence |
| guest copies known candidate or reviewer SHA | HOLD; cannot establish independently protected signer/process |
| guest changes plan/allowed_paths/checks/approval | HOLD; stale plan digest/consent |
| guest writes a forged reviewer receipt file | HOLD; unprotected artifact has no attestation |
| prior run receipt replay or lease epoch mismatch | HOLD; nonce, run_id, epoch are bound and consumed |
| reviewer executable/config is mounted writable into guest | HOLD; separation violated |
| mandatory fixed check fails or cannot execute in isolated verifier | HOLD; no fallback |
| path escapes worktree/symlink/reparse/hook/filter invocation | HOLD; no source/Git promotion |
| no supported independent OS boundary on user's Windows | HOLD; manual disposition needed |

## P1 scope vs P2 proof

MLA-003 adds this security contract and synthetic adversarial inputs, **not a working trusted reviewer**. The runtime verifier/receipt guard is queued at MLA-015; integration gate at MLA-018. Until P2 proves actual separation against adversarial Windows tests, any code-generated PASS remains UNTRUSTED, no integration/real-use GO.

Only fake synthetic plans/diffs are allowed for P1 tests; no paid models, actual customer data, Git protected refs, Windows security policy changes, or network access. All owner secrets/attestation private material must remain outside GitHub and outside the coder guest.

## P1 2026-11-17 보안 경계 국소 보강 — 자동 검증/승격 아님

- `test_receipt_forgery.py`에 선행 작업 상태의 **게스트 자체 VERIFIED 주장만으로 READY 후속이 실행되지 않는 검사**와 위조/재생 영수증의 PlanSpec 필드 주입 거부를 추가한다.
- `QueuePolicy.propose_ready`는 외부 trusted evidence ID가 일치해도 `runnable=false`인 후보만 생성한다. F18 독립 reviewer가 OS 경계에서 서명·검증 전에는 실제 실행 권한이나 Git ref 승격이 아니다.
- 원본 소스 파일 경로·후속 SHA·lease epoch·nonce·owner grant 등은 protected side로부터 재계산되어야 한다. 현재 어떤 격리 프로세스도 보호된 독립 신뢰 서명자가 되었음을 입증하지 않았다.
- `MLA-009`는 `LOCAL_PLAN` reusable grant만 최소 검증 가능; 다른 원격/지불/권한 scope는 Action별 1회 GO/trust root 설계 전 강제 DENY. `ConsentLedger`의 SQLite main inode·WAL/SHM sidecar도 변조/교체 검사하나 이것은 Windows ACL 보호 실증이 아니다.
- 시스템은 F18 `SECURITY_HOLD` 및 P2 `LOCKED` 유지, 실제 실 Windows/격리/24h `NOT_RUN`.

---

## 2026-11-17 P1 High-review candidate: host Ollama vs disconnected Windows guest

This candidate does **not** alter the frozen `docs/FINAL_BLUEPRINT.md` or approve Windows OS changes.

| Option | Performance/cost on GTX 1050 Ti / RAM 16GB | Security/maintainability | Decision |
|---|---|---|---|
| A. Host Qwen inference only, sealed untrusted file proposal, read-only disposable WSB guest import, separate independent reviewer | Reuses installed host Qwen; no second model copy; zero paid API, additional temporary WSB RAM | Keeps guest networking disabled; needs protected OS principal, scratch ACL+reparse checks, separate guest generation and safe result broker | **Preferred implementation candidate**, source transport authored, Windows execution HOLD |
| B. Qwen/OpenCode copied into standalone network-disabled Sandbox | Extra guest RAM/storage, potentially heavy for current laptop and model packaging rights | Avoids host inference broker but doubles runtime; still needs independent OS reviewer and result bridge | Alternative only; unverified |
| C. Enable Sandbox virtual network route to host Ollama | Avoids model duplication, network path simpler | Violates default no-egress; Windows firewall/network policy changes and external reachability assessment | **REJECT before separate owner GO**, not implemented |

Current source functions cannot launch WSB, run untrusted code in guest, attest network denial or issue signed F18 PASS. Microsoft docs report WinApp CLI Sandbox provisioning can add Developer Mode and inbound firewall rule; that is a separate OS security change needing explicit owner approval. Do not install or run it by default. Existing default Python/SQLite review and protected grant HOLD remain as-is.
