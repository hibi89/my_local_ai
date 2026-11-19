# MLA Windows Local Operator — approved add-on design (2026-11-19 KST)

## User-approved scope and boundary
The owner requested copy/paste from web ChatGPT into local MLA, without requiring Codex. This is an **additive P1 Windows read-only operator**; never reinterpret a natural-language command as a shell command. The existing Zero-VM/no generated-code execution, F18, protection against OS/ACL/TPM changes, Git/original rights, owner GO, P2 lock and launch hold remain unchanged.

**End-to-end path:** user copies a bounded alias or versioned JSON command into `python -m my_local_ai local-op run --request "MLA 보안 환경 진단"`; CLI parses an exact allowlist -> calls fixed trusted local diagnostic -> emits redacted status JSON. It cannot run arbitrary scripts, filesystem paths, installer, WinRM, network, Git writes, service administration, or approval. The operator runs as the current unprivileged user; it does not self-elevate.

### Contract
- `mla-local-operator/v1` exactly `{"schema":"mla-local-operator/v1","action":"windows-preflight"}` (or action one of `tpm-status`, `defender-status`, `protected-path-presence`); duplicate/unknown keys and unknown names HOLD. Exact Korean fixed phrases are optional aliases, not fuzzy NLP. `catalog` is nonexecuting.
- TPM: only fixed built-in `Get-Tpm` query using trusted System32 PowerShell, no profile, bounded output/timeout, fixed command and sanitized child environment. Defender: reuse existing read-only protected status probe. Protected directory: check only fixed `C:\ProgramData\MyLocalAI\Protected\v1` presence; no content read, ACL mutation or provisioning.
- Redacted output identifies query success/failure, TPM ready/present/enabled, Defender health, fixed folder existence. This does not attest Owner SID, TPM keys, F18, signed receipts or availability for P1 completion.
- Windows unsupported, malformed requests, missing PowerShell, invalid output, timeout, missing privileges, aliases/reparse, and read failures result in bounded HOLD; no fallback to free-form commands.
- Phase: P1 source implementation + mandatory syntax/read-only/deny tests, followed by P2 Windows/permissions/negative-path/CI/UX verification; independent audit and user GO still required.
- Future **privileged executor** is explicitly **OUT OF SCOPE** and requires its own security final design + independent trust + scoped owner approval. Do not reuse read-only operator as an authorization path.

### REQ and SWU (new add-on, no rewriting historical IDs)
| New REQ | SWU | Function, paths | P1 acceptance |
|---|---|---|---|
| REQ-OP-01 | MLA-OP-SWU-001 | exact alias + JSON contract in `src/my_local_ai/ops/windows_local_operator.py` | rejects injection, unknown/duplicate fields, oversized requests; catalog gives exact allowed actions |
| REQ-OP-02 | MLA-OP-SWU-002 | fixed TPM/Defender/folder read-only operators in same module | caller -> bounded fixed callee -> sanitized results and HOLD, no OS mutation or network |
| REQ-OP-03 | MLA-OP-SWU-003 | `src/my_local_ai/cli.py`, `docs/WINDOWS_LOCAL_OPERATOR_SWU_QUEUE.json` | CLI run/catalog/status exposes combined P1 and independent P2 counts, does not grant authority |

**Accounting:** preserve existing V1.3 `MLA 37/39 + CodeShield 15/16 = 52/55` and their complete retry/evidence histories; these 3 **new** SWUs add to the explicit new `55 + 3 = 58` P1 source-candidate denominator. Add-on and aggregate are reported side-by-side, never retroactively backfill legacy counts. Verification SWU PASS only on actual accepted P2 evidence; without P2 evidence `0/58 PASS recorded` and **official verified rate `UNASSESSED`**, not an invented certification percentage. The source-completed flag is not P2 verified.
