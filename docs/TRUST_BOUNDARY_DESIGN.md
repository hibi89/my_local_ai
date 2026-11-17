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
