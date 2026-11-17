# V1.3 CodeShield — Acceptance Matrix (design only)

**Basis:** 2026-11-17, hibi89/my_local_ai, design/final-blueprint-v1.
**Status:** ALL NOT_RUN, acceptance weight UNASSESSED, no runtime GO. This file does not add 12 accepted REQ to the historical 30-REQ or 39-SWU denominator. CS requirements are separately tracked against docs/OPTIONAL_CODESHIELD_TASK_QUEUE.json (8 source tasks).
**Tooling:** no outside source copying, no unapproved binary install, no Windows security configuration change.

| REQ-CS | P1 source SWU | Scope / observable evidence | P1 immediate guard | P2 independently verified acceptance |
|---|---|---|---|---|
| 01 | CS-01 | exact plan/SHA/lease/owner/data_class/allowlist tool hash contract | malformed/duplicate/untrusted scanner decision rejected | replay/collision/stale SHA and mutated scanner policy never authorize |
| 02 | CS-01,07 | risk outputs exclusively ALLOW_NON_EXECUTING / REQUIRES_ISOLATION_HOLD / HOLD_HIGH_RISK / UNKNOWN_HOLD | no SAFE_TO_EXECUTE/VERIFIED from scanners | adversarial lower-risk coercion fails closed |
| 03 | CS-02 | Python AST and lexical code scanner with size/time/node limits | ast.parse without imports/exec, no generated tests | 20 synthetic dangerous/benign Python samples and resource measurements |
| 04 | CS-02 | disposable worktree/file scope/hash/FS protections | symlink, NTFS reparse/ADS, Git hook/filter, metadata, data deletion HOLD | Windows 11 ACL/ADS/TOCTOU, exact Git baseline snapshot tests |
| 05 | CS-03 | pinned Ruff Windows tool with E4/E7/E9/F/S | no shell, no project-config injection, bounded JSON failure to HOLD | real native Windows binary hash/version, missing/exit/timeout behavior |
| 06 | CS-04 | pinned Semgrep CE Windows local YAML + no registry/upload | local rule hash, metrics/version-check OFF; no remote config | actual CLI --help/version, egress probe, rule tampering, resource cap |
| 07 | CS-05 | Gitleaks before any code share, OSV offline on lockfile changes | detector unavailable/stale offline DB = HOLD | benign/secret fixtures, no token in report, DB freshness and known CVE samples |
| 08 | CS-06 | Defender read-only status, optional owner-scope download scan | no silent CFA/AV exception, no second resident AV, Defender unavailable=HOLD for risky binaries | Defender active/passive, EICAR-safe documented test if owner approves, scan/alert evidence |
| 09 | CS-07 | Controller stage ordering and independent READY isolation | scanner PASS cannot run untrusted scripts or alter owner grants | cross-stage cold-start, fail-open attempt, unexpected call, watchdog recovery |
| 10 | CS-07 | OS execution + independent F18/CAS boundaries untouched | no guest self-signed PASS, same-principal issuer, fake OS attestation | real Windows OS principal, egress deny, nonce replay, tool/check pin, protected CAS |
| 11 | CS-08 | redacted UI/CLI status and manual choice clarity | no private code, credential, model prompt or inert approve control | accessibility/Windows CLI interaction, role/owner-only action, evidence mapping |
| 12 | CS-08,07 | 16GB resource budgeting, Qwen one model, scanner sequential | no auto install/remote upload/VM default, one retry + 2+2 SWU operational policy | real GPU/RAM/CPU/scan latency; 10 files/1MB <=90 seconds, idle extra RAM <=200MB as goals, not guarantees |

## Defined risk outcomes (not security clearance)

**ALLOW_NON_EXECUTING:** text/code generation, strictly read-only AST/static scans, scope-bound diff only. Does not authorize new unit test, Python module import, shell/PowerShell script, pip/npm hooks, or EXE execution.

**REQUIRES_ISOLATION_HOLD:** executable/untrusted input requires proven AppContainer/other OS confinement plus independent signed F18. If no approved Windows attestation, no host fallback.

**HOLD_HIGH_RISK:** deletion, credentials, owner checkout, Git remote/main, paid/external network, OS/Defender/CFA ACL/firewall/task schedule, customer source/secret. Separate owner action grant and independent review mandatory.

**UNKNOWN_HOLD:** missing/stale tool, invalid version/hash, incomplete parser, DB unavailable, alert result ambiguous or no fresh evidence. Continue only unrelated nonexecuting READY; never force a PASS.

## P1 & P2 scope

P1 authors actual back-end and CLI/FE path and local syntax/targeted security smoke; source-only completion is not accepted F18 or product deployment. Existing 39 SWUs and 30 REQ remain separately reported, CodeShield CS-01..08 0/8 design-only until actual coding.

P2 starts only after pinned full implementation candidate and High gates: real Windows 11 Pro, Qwen, native Semgrep/Ruff, antivirus status, offline vulnerability cache, security lab / adversarial OS tests, full CI, integration and recovery. P3 real Codex Sol Max/Astra Max independent audits remain NOT_RUN. P4 owner real-use GO separate. No official CodeShield success metrics are asserted by this design.
