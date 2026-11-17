# MLA — 해총 SWU 전수 재산정 (2026-11-17 KST)

**정본:** [OWNER-SWU-HIGH-20261117](https://github.com/hibi89/hackathon-command-center-2026/blob/kmong-productization/docs/strategy/GPT6_HIGH_STANDARD_WORK_UNIT_20261117.md) blob `f7005d73...`; **소스 감사 HEAD `bc28dfee99fecd16180d8a16c54a0adb95420658`**. `docs/FINAL_BLUEPRINT.md`, `src/`, `tests/`, `WORK_PHASE_GATES.json` 무변경.

## 집계

- 28 기존 구현 태스크 / 30 REQ → **39 P1 소스 SWU** (High 한 코딩 회차 기준 0~3 복잡도점). 기존 5개 검증·하네스 전용 `MLA-004/005/025/029/030` P2 이관. 기존 소스 재사용 + 실행 연결의 실제 미구현 경계를 분할.
- 실소스 경로가 작성된 후보 **18개 `SOURCE_COMPLETE_P2_PENDING`**. 실제 코드 간극·계약 대기·보호 신뢰/GO 차단 **21개**. SWU 후보 건수는 REQ 수용 건수나 실운용 허가가 아니다.
- REQ 구현 게이트 **5/30 = 16.67% 유지** (코드 무변경). P2 `LOCKED`, 공식 검증률 `UNASSESSED`, owner GO false.
- 첫 독립 READY **MLA-SWU-002, MLA-SWU-011, MLA-SWU-023, MLA-SWU-032, MLA-SWU-034**. source path disjoint; 각 선행 코드 후보 존재. 1회 구현 목표, 기본 2회 상한, 특별 3회 사전 승인, 같은 원인 진전 없는 2회 즉시 HOLD.

| SWU 상태 | 수 |
|---|---:|
| BLOCKED_PROVENANCE | 1 |
| READY | 5 |
| SOURCE_COMPLETE_P2_PENDING | 18 |
| BLOCKED_TRUST | 4 |
| BACKLOG_READY | 2 |
| PENDING_CODE_DEPENDENCY | 8 |
| BLOCKED_APPROVAL | 1 |

## 기존 28 task 전수 매핑

| 레거시 ID | REQ | 신규 SWU 또는 P2 | 기존 소스 증거 SHA | 남은 간극 |
|---|---|---|---|---|
| MLA-001 | REQ-01,REQ-02 | S001, S002 | `aa626dc11c96` | external EAI/AX license unresolved; no REQ live coverage CLI |
| MLA-002 | REQ-03,REQ-04 | S003, S004 | `045c3959dca0` | 기존 소스 후보 / P2 보류 |
| MLA-003 | REQ-15,REQ-23,REQ-24 | S015, S020, S021, S030, S031 | `56c7b2f53a38` | Windows isolated OS runner not implemented; no separated OS reviewer or protected issuer |
| MLA-004 | REQ-30 | P2: MLA-V001 | `1ee35c878465` | 기존 소스 후보 / P2 보류 |
| MLA-005 | REQ-25,REQ-27 | P2: MLA-V003 | `6c74b6910894` | 기존 소스 후보 / P2 보류 |
| MLA-006 | REQ-28 | S002, S035, S036, S039 | `0cdb85475141` | no REQ live coverage CLI; stub HOLD does not route protected action |
| MLA-007 | REQ-18 | S010, S011, S025 | `675a7c772866` | schema exists but no state writer |
| MLA-008 | REQ-05,REQ-06 | S005, S006, S038 | `920b66750832` | preview/handoff only, no state transition |
| MLA-009 | REQ-07 | S007, S008, S029, S036 | `d0cc3a6005de` | owner key and protected OS identity missing; only intent, remote action unavailable |
| MLA-010 | REQ-08,REQ-17 | S009, S023, S038 | `675a7c772866` | only pure retry proposal, no queue transition; preview/handoff only, no state transition |
| MLA-011 | REQ-09,REQ-25 | S012, S032, S034 | `fbea29f35a47` | only injected synthetic sample; no platform read; tokens RAM observation discarded; real run P2 |
| MLA-012 | REQ-10,REQ-23 | S013, S030 | `fbea29f35a47` | 기존 소스 후보 / P2 보류 |
| MLA-013 | REQ-11,REQ-24 | S014, S015, S030, S031 | `fbea29f35a47` | Windows isolated OS runner not implemented; no host-attested network isolation |
| MLA-014 | REQ-12,REQ-13 | S016, S017, S018, S019 | `d15485dab9bd` | only preview and metadata audit; cleanup preview only, no Git cleanup |
| MLA-015 | REQ-14,REQ-15 | S020, S021, S027 | `306a01ef634e` | no separated OS reviewer or protected issuer; synthetic memory CAS only |
| MLA-016 | REQ-16,REQ-17 | S009, S022, S023 | `1bf6a17ec562` | only pure retry proposal, no queue transition |
| MLA-017 | REQ-19,REQ-20 | S011, S024, S025, S026 | `1bf6a17ec562` | schema exists but no state writer; in-memory intent but no durable CAS |
| MLA-018 | REQ-21 | S027 | `9933c4f591a7` | synthetic memory CAS only |
| MLA-019 | REQ-05,REQ-09,REQ-17,REQ-28 | S005, S038, S039 | `d15485dab9bd` | preview/handoff only, no state transition; static phase JSON only |
| MLA-020 | REQ-25,REQ-27 | S034 | `675a7c772866` | tokens RAM observation discarded; real run P2 |
| MLA-021 | REQ-29 | S037 | `045c3959dca0` | 기존 소스 후보 / P2 보류 |
| MLA-022 | REQ-26 | S032, S033 | `306a01ef634e` | only injected synthetic sample; no platform read; pure assessment, no durable state |
| MLA-023 | REQ-22 | S028 | `045c3959dca0` | 기존 소스 후보 / P2 보류 |
| MLA-024 | REQ-22,REQ-07 | S007, S029 | `045c3959dca0` | only intent, remote action unavailable |
| MLA-025 | REQ-30 | P2: MLA-V001,MLA-V007 | `d15485dab9bd` | 기존 소스 후보 / P2 보류 |
| MLA-028 | REQ-05,REQ-14 | S006 | `920b66750832` | 기존 소스 후보 / P2 보류 |
| MLA-029 | REQ-15,REQ-26 | P2: MLA-V004 | `8f565feb0e69` | 기존 소스 후보 / P2 보류 |
| MLA-030 | REQ-13,REQ-23,REQ-24 | P2: MLA-V002 | `8f565feb0e69` | 기존 소스 후보 / P2 보류 |

## 신규 39 SWU — 실제 호출 경로·소스 수용 / 규모

| SWU | REQ | caller→callee→결과 | 미구현 또는 보류 | S/C/I/D/U 합 | 코드 선행 | 분류 |
|---|---|---|---|---|---|---|
| MLA-SWU-001 | REQ-01,REQ-02 | audit_sources.main>audit_manifest>source manifest→pinned source rights decision | external EAI/AX license unresolved | 0/0/0/1/2=3 | — | BLOCKED_PROVENANCE |
| MLA-SWU-002 | REQ-02 | mla evidence>REQ inventory>redacted rows→per-REQ source coverage visible | no REQ live coverage CLI | 1/0/1/0/1=3 | S003,S004 | READY |
| MLA-SWU-003 | REQ-03 | PlanSpec.parse_json>digest/DAG→reject invalid plan SHA | NONE | 0/1/0/0/0=1 | — | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-004 | REQ-04 | TaskSpec.parse>safe_path/budget→bounded validated task | NONE | 0/1/0/0/0=1 | — | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-005 | REQ-05,REQ-06 | Controller.propose>QueuePolicy→native scheduling without EAI | NONE | 1/0/1/0/0=2 | S003,S004 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-006 | REQ-05,REQ-06 | inspect_optional_eai>pinned hints→priority hints only | NONE | 1/0/1/0/0=2 | S005 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-007 | REQ-03,REQ-07 | authorize_claim>scope expiry revocation→reject invalid owner claim | NONE for claim guard; protected signer separate | 0/0/0/2/0=2 | S003 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-008 | REQ-07 | trusted owner store>protected signature>current grant→protected signer usable by Controller | owner key and protected OS identity missing | 0/0/0/2/1=3 | S007 | BLOCKED_TRUST |
| MLA-SWU-009 | REQ-08,REQ-17 | QueuePolicy.propose_ready>verified deps→unblocked READY with blocked child HOLD | NONE | 0/1/0/0/0=1 | S004 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-010 | REQ-18 | initialize_state>WAL/schema/backup→owned SQLite initialized or rejected | NONE | 0/1/0/1/0=2 | — | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-011 | REQ-18,REQ-20 | protected run writer>SQLite tasks/runs/events→durable task event commit | schema exists but no state writer | 1/0/1/1/0=3 | S010 | READY |
| MLA-SWU-012 | REQ-09,REQ-25 | OneModelLock+BudgetGuard>bounded call→one-model resource guard | NONE | 1/0/1/0/0=2 | — | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-013 | REQ-10,REQ-23 | OllamaProvider.generate>loopback HTTP→untrusted local model output or HOLD | NONE; real Qwen P2 NOT_RUN | 0/0/1/0/1=2 | S012 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-014 | REQ-11,REQ-24 | prepare_opencode_run>fixed argv and config→bounded no-shell coder request | NONE for request contract; actual OS isolation separate | 0/0/0/2/0=2 | S004,S013 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-015 | REQ-09,REQ-11,REQ-24 | trusted controller>isolated runner>untrusted candidate→isolated coder result | Windows isolated OS runner not implemented | 0/0/0/2/1=3 | S014,S008 | BLOCKED_TRUST |
| MLA-SWU-016 | REQ-12 | protected source>pinned git worktree create→isolated checkout without changing main | only preview and metadata audit | 0/0/0/2/1=3 | S017,S003 | BACKLOG_READY |
| MLA-SWU-017 | REQ-13 | preflight_paths>alias and path checks→unsafe checkout path denied | NONE; OS attack P2 NOT_RUN | 0/0/0/2/0=2 | S004 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-018 | REQ-12 | fresh worktree snapshot>protected cleanup→only owned clean tree removed | cleanup preview only, no Git cleanup | 0/0/0/2/1=3 | S016 | PENDING_CODE_DEPENDENCY |
| MLA-SWU-019 | REQ-12,REQ-13 | protected Git read>inventory snapshot>audit→fresh actual tracked and dirty inventory | caller-provided snapshot only | 0/0/0/2/1=3 | S016,S017 | PENDING_CODE_DEPENDENCY |
| MLA-SWU-020 | REQ-14,REQ-15 | reviewer policy>fixed check request→approved argv and request bounded | NONE for pre-execution policy | 0/0/0/2/0=2 | S003,S004 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-021 | REQ-14,REQ-15 | independent principal>fixed tests>trusted receipt→guest-unforgeable signed review result | no separated OS reviewer or protected issuer | 0/0/0/2/1=3 | S020,S008 | BLOCKED_TRUST |
| MLA-SWU-022 | REQ-16 | plan_improved_repair>bounded strategy→one repair intent or HOLD | NONE for proposal, durable transition separate | 0/0/0/0/0=0 | S009 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-023 | REQ-16,REQ-17 | review failure>repair policy>next READY→persist retry/HOLD decision path | only pure retry proposal, no queue transition | 1/0/1/1/0=3 | S009,S022 | READY |
| MLA-SWU-024 | REQ-20 | lease proposal>SQLite CAS epoch>receipt→stale duplicate workers fenced | in-memory intent but no durable CAS | 0/1/0/1/1=3 | S011,S009 | PENDING_CODE_DEPENDENCY |
| MLA-SWU-025 | REQ-18,REQ-19 | read_reconcile_state>SQLite read-only readback→contradictory DB ref state HOLD | NONE for safe read-only decision | 0/0/1/1/0=2 | S010 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-026 | REQ-19,REQ-20 | startup reconcile>durable checkpoint→safe recovery without replay | read-only decision only, no protected transaction | 0/1/0/1/1=3 | S024,S025 | PENDING_CODE_DEPENDENCY |
| MLA-SWU-027 | REQ-15,REQ-21 | trusted F18+readback>isolated ref CAS→only independently verified ref promoted | synthetic memory CAS only | 0/0/0/2/1=3 | S019,S021,S024 | PENDING_CODE_DEPENDENCY |
| MLA-SWU-028 | REQ-22 | draft preview>scope inventory>redacted card→owner sees remote intent no push | NONE | 0/0/1/0/0=1 | S003 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-029 | REQ-07,REQ-22 | separate owner grant>draft GitHub PR→approved draft only, never main merge | only intent, remote action unavailable | 0/0/0/2/1=3 | S008,S027,S028 | BLOCKED_APPROVAL |
| MLA-SWU-030 | REQ-23,REQ-24 | fixed env and output constraints>guest→no secret env and self-verified receipts | NONE for policy, actual OS egress separate | 0/0/0/2/0=2 | S014 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-031 | REQ-23,REQ-24 | protected sandbox>deny public network→guest/reviewer no egress | no host-attested network isolation | 0/0/0/2/1=3 | S015,S021 | BLOCKED_TRUST |
| MLA-SWU-032 | REQ-25,REQ-26 | bounded sampler>ResourceReading>limits→local RAM CPU thermal VRAM or NOT_AVAILABLE | only injected synthetic sample; no platform read | 0/0/0/0/1=1 | S012 | READY |
| MLA-SWU-033 | REQ-26 | resource state>supervisor>durable pause→safe unattended checkpoint/HOLD | pure assessment, no durable state | 0/0/1/1/1=3 | S032,S026 | PENDING_CODE_DEPENDENCY |
| MLA-SWU-034 | REQ-25,REQ-27 | local generation>observation>redacted metrics→bounded model throughput fields not fabricated | tokens RAM observation discarded; real run P2 | 0/0/1/0/1=2 | S012,S013 | READY |
| MLA-SWU-035 | REQ-28 | mla main>plan/queue/status>redacted JSON→safe user read-only CLI response | NONE for read-only CLI | 0/0/1/0/0=1 | S003,S004,S009 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-036 | REQ-07,REQ-28 | mla start stop>typed owner Controller request→CLI request routed but not self-approved | stub HOLD does not route protected action | 0/0/1/0/1=2 | S008,S023,S024 | PENDING_CODE_DEPENDENCY |
| MLA-SWU-037 | REQ-29 | load_snapshot>LocalStatusServer>HTML GET→loopback status board | NONE; real browser P2 | 1/0/1/0/0=2 | S010 | SOURCE_COMPLETE_P2_PENDING |
| MLA-SWU-038 | REQ-05,REQ-09,REQ-17 | Controller>coder>F18>task state→safe one-cycle result and HOLD | preview/handoff only, no state transition | 1/1/1/0/0=3 | S011,S015,S021,S023,S027 | PENDING_CODE_DEPENDENCY |
| MLA-SWU-039 | REQ-02,REQ-30 | protected evidence>REQ map>phase candidate→immutable 30-REQ candidate decision | static phase JSON only | 1/0/1/0/0=2 | S002,S003,S004 | BACKLOG_READY |

## 첫 5 READY 소스 범위

- **MLA-SWU-002** REQ source evidence CLI: `src/my_local_ai/cli.py`; no REQ live coverage CLI. 입력→실제 출력·오류까지 코딩하고 P2 검증/새 테스트 하네스는 후행.
- **MLA-SWU-011** Durable task run event writer: `src/my_local_ai/state/sqlite_store.py`; schema exists but no state writer. 입력→실제 출력·오류까지 코딩하고 P2 검증/새 테스트 하네스는 후행.
- **MLA-SWU-023** Retry HOLD queue state transition: `src/my_local_ai/ax_runtime/recovery.py`, `src/my_local_ai/ax_runtime/queue.py`; only pure retry proposal, no queue transition. 입력→실제 출력·오류까지 코딩하고 P2 검증/새 테스트 하네스는 후행.
- **MLA-SWU-032** Owner-local resource sampler: `src/my_local_ai/ops/resource_monitor.py`; only injected synthetic sample; no platform read. 입력→실제 출력·오류까지 코딩하고 P2 검증/새 테스트 하네스는 후행.
- **MLA-SWU-034** Local benchmark observed metrics: `scripts/benchmark_real_local.py`; tokens RAM observation discarded; real run P2. 입력→실제 출력·오류까지 코딩하고 P2 검증/새 테스트 하네스는 후행.

## 분리와 보존

- `MLA-004/005/025/029/030`은 P1에서 오직 테스트·fixture·CI·문서 용도였으므로 **SWU 미산입**, P2 `VERIFICATION_TASK_QUEUE.json`에 기존 검증 책임으로 연결. 기존 자동 필수 CI와 즉시 보안 검사는 계속 작동.
- 과대 결합: `MLA-014` worktree 생성/삭제/Git readback/FS 경계, `MLA-015` 고정 reviewer 정책과 보호된 OS F18, `MLA-017` 읽기 reconciliation과 지속 lease/복구, `MLA-019` Controller preview와 실제 상태 전이, `MLA-024` draft intent와 원격 발행을 독립 기능으로 분할. 기존 완성된 소스와 한 단위로 중복 구현하지 않는다.
- `INSTANT_TASK_QUEUE.json` 기존 28 `tasks`/코딩 증거/시도 이력과 기존 Python CLI/guard는 **호환성 유지**, `first_ready`는 legacy 전용. 실제 새 P1 `ㄱ` 일정 정본은 `P1_SWU_TASK_QUEUE.json.first_ready`; 오래된 CLI `queue next` 화면을 새 SWU READY로 오인하지 않는다.
- 파생 SWU는 원본 task ID, 정확 SHA, 이전 시도, 의존성 및 차단을 `legacy_mapping`과 `inherited_attempts_by_legacy`에 보존. `MLA-006`의 실제 CLI 작업 1회를 관련 파생 단위에 **보수적 승계**함. 새 ID로 횟수 리셋 금지.
- D=2는 High 즉시 안전 검토 대상, F18/원본/권한/비밀/OS/원격은 원래 승인·보호 경계 풀지 않음. 독립 실제 OS reviewer/owner signer/원격 발행은 BLOCKED, P2 검증 시험은 `NOT_RUN`.

**다음 `ㄱ`**: 새 SWU 5개 실제 기능 소스 코딩. 문서·테스트 하네스·합성 검증 반복으로 P1 구현률 올리지 않음.
