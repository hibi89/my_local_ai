# My Local AI — P1 30-REQ source mapping / unresolved gates

**Date:** 2026-11-17 KST. **Repo/branch:** `hibi89/my_local_ai@dev/instant-implementation-v1`. **Last tested source SHA:** `675a7c772866709d626bf5e1001b454e98647f9d`; GitHub Actions #44038497545 **460/460 synthetic PASS** (162 unit, 108 integration, 190 security).
**This is an evidence routing report, not a list of accepted REQs.** Source task evidence and code status do not prove F18, owner consent, Windows isolation or full acceptance.
**Formal implementation progress:** 5/30 (16.67%) remains unchanged; the current queue contains no individually approved identifiers for the five completed REQs. The table therefore cannot certify which individual five were accepted. **Formal verification:** UNASSESSED. **P2:** LOCKED.

| P1 REQ | Source task(s) | Queue evidence SHA(s), short | Unresolved or pending assessment |
|---|---|---|---|
| REQ-01 | MLA-001 | aa626dc11c96 | PROVENANCE |
| REQ-02 | MLA-001 | aa626dc11c96 | HIGH_MAPPING |
| REQ-03 | MLA-002 | 1ee35c878465 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-04 | MLA-002 | 1ee35c878465 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-05 | MLA-008, MLA-019, MLA-028 | 920b66750832, e4bab2da8720, 920b66750832 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-06 | MLA-008 | 920b66750832 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-07 | MLA-009, MLA-024 | d0cc3a6005de, 1c4bddb9fdcd | OWNER_SIGNER |
| REQ-08 | MLA-010 | 675a7c772866 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-09 | MLA-011, MLA-019 | fbea29f35a47, e4bab2da8720 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-10 | MLA-012 | fbea29f35a47 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-11 | MLA-013 | fbea29f35a47 | F18_REAL_SANDBOX |
| REQ-12 | MLA-014 | 306a01ef634e | GIT_REAL_WORKTREE |
| REQ-13 | MLA-014, MLA-030 | 306a01ef634e, 8f565feb0e69 | WINDOWS_FS |
| REQ-14 | MLA-015, MLA-028 | 306a01ef634e, 920b66750832 | INDEPENDENT_REVIEW |
| REQ-15 | MLA-003, MLA-015, MLA-029 | 56c7b2f53a38, 306a01ef634e, 8f565feb0e69 | INDEPENDENT_F18 |
| REQ-16 | MLA-016 | 1bf6a17ec562 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-17 | MLA-010, MLA-016, MLA-019 | 675a7c772866, 1bf6a17ec562, e4bab2da8720 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-18 | MLA-007 | 675a7c772866 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-19 | MLA-017 | 1bf6a17ec562 | PHYSICAL_CRASH |
| REQ-20 | MLA-017 | 1bf6a17ec562 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-21 | MLA-018 | 9933c4f591a7 | F18_GIT_CAS |
| REQ-22 | MLA-023, MLA-024 | 8f565feb0e69, 1c4bddb9fdcd | REMOTE_GO |
| REQ-23 | MLA-003, MLA-012, MLA-030 | 56c7b2f53a38, fbea29f35a47, 8f565feb0e69 | NETWORK_EGRESS |
| REQ-24 | MLA-003, MLA-013, MLA-030 | 56c7b2f53a38, fbea29f35a47, 8f565feb0e69 | REAL_GUEST |
| REQ-25 | MLA-005, MLA-011, MLA-020 | 6c74b6910894, fbea29f35a47, 675a7c772866 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-26 | MLA-022, MLA-029 | 306a01ef634e, 8f565feb0e69 | REAL_24H |
| REQ-27 | MLA-005, MLA-020 | 6c74b6910894, 675a7c772866 | REAL_MODEL |
| REQ-28 | MLA-006, MLA-019 | da9174c3d8ac, e4bab2da8720 | HIGH_P1_SOURCE_ACCEPTANCE_REVIEW |
| REQ-29 | MLA-021 | e4bab2da8720 | P2_BROWSER |
| REQ-30 | MLA-004, MLA-025 | 1ee35c878465, e4bab2da8720 | P2_FULL_TESTS |

## Next decision

- **Evidence coverage:** queue records source-evidence SHA pointers for 28/28 tasks; mapping the task count to 30 REQs is invalid. Tests on the two source waves do not prove all 30 REQs independently.
- **High must identify** code requirements truly P1-complete, isolate implementation defects vs P2-only real device tests, and decide the source scope for genuine independent F18 and protected owner signer. The frozen blueprint cannot be silently altered.
- **Current source waves:** MLA-011/012/013 local lock, Ollama response parsing, OpenCode path bounds; MLA-007/010/020 SQLite path/inode, bounded DAG generators, benchmark input/output checks. Actual Windows/owner Qwen/Ollama not run.
- **Next code-only READY:** MLA-002, MLA-021, MLA-024. MLA-024 remote publish and owner-GO blocker remains in original task `blockers` and `runtime_authorization=HOLD`; only source authoring is allowed.
- **No phase, permission, P4 owner GO, real Git PR or paid service authorization changed.**


### P1 2026-11-17 source-only update (no new REQ acceptance)
At code SHA `045c3959dca08a6f2c03ce7655c5c738db82bdd3`, safety hardening for MLA-002/021/023/024 was committed and P1 synthetic Actions run `44056170817` passed 465/465 checks (166 unit, 108 synthetic integration, 191 security, syntax PASS). REQ-03/04/07/22/29 are not newly accepted by these tests. Provenance, action-specific protected signer, F18 OS isolation and P2 browser/Windows remain pending. P1 formal code counter stays **5/30**.
