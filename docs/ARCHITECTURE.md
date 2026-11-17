# My Local AI — BE/FE/AI/데이터 통합 아키텍처 V1 (design)

```text
High approved PlanSpec (source_sha, plan_sha, owner scope)
    |
    v
My Local AI Controller (owns DAG/schedule/approval verification)
      optional EAI-derived AdvisorPort (proposals only; OFF is valid)
    |
    v
AX QueueController (single writer, dependency DAG, WAL, lease epoch)
    |--> ModelPolicy --> localhost Ollama --> OpenCode coder (ONE model)
    |                                  |
    |                           disposable Git worktree
    |                                  |
    |                         CandidateDiff [UNTRUSTED]
    |                                  v
    |                     Trusted Review Boundary (F18)
    |                       /                  \
    |                 PASS verified          HOLD/fix-once
    |                     |                       |
    +<---- safe isolated local ref             next independent READY
    |
Evidence Ledger (SHA/checks/NOT_RUN/redacted) -> local CLI Status
                                  -> optional secure loopback dashboard
Remote GitHub PR/OS startup/Production: separate owner GO, default OFF
```

## 목표 모듈 경로 (아직 미구현)
- `src/my_local_ai/contracts`: v1 Task/Plan/WorkProposal/Candidate/TrustedReceipt schema, SHA/allowlist.
- `src/my_local_ai/controller`: My Local AI 자체 DAG/scheduling/approval policy/decision (필수).
- `src/my_local_ai/advisors/eai`: 선택적 EAI 출처의 CPU 분석 보조 모듈 (기본 fallback 가능, 실행·승인·VERIFIED 권한 없음). EAI 원본 ADR은 원본에만 영향.
- `src/my_local_ai/ax_runtime`: AX 큐·로컬 coder·worktree·checkpoints·모델 제한, 기존 코드를 출처·검증 추적해 안전 이식.
- `src/my_local_ai/review`: 신뢰 검증기, 실제 OS 분리, 위조 결과 거부, 모델 자가 PASS 금지.
- `src/my_local_ai/state`: SQLite WAL, one-writer, interrupted recovery, 복구 원장.
- `src/my_local_ai/gitops`: remote 기본 OFF, worktree CAS, local ref, scope diff.
- `src/my_local_ai/ui`: CLI 우선, 로컬 상태보드 후순위.
- `tests/unit,integration,security,e2e,windows`: 합성/호스트/실모델 증거 구분.
- `scripts`: 모델 비교·출처 감사·안전 설치 계획; 고객자료 전송 금지.

## 컴포넌트 책임
| 범위 | My Local AI Controller | EAI 유래 선택적 advisor | AX 로컬 실행기 | 독립검증 |
|---|---|---|---|---|
| 작업 후보/순서 | 정본 DAG/승인·실행 정책 | CPU 분석·우선순위 제안만 | 승인된 WorkOrder 처리 | PASS 권한 독립 유지 |
| 코딩 | 작업/파일 제한 집행 | 코딩 금지/필수 아님 | Ollama/Qwen 코드·수정 생성 | 코드/영수증 불신 |
| 데이터 수정 | 승인 범위 재확인 | 없음 | 격리 allowed_paths만 | trusted independent tests |
| 상태 정본 | 자체 SQLite/run/ref | 없음 | controller 상태 보고 | trusted receipt |
| 모델 접근 | 자원·권한 가드 | 필요시 로컬 분석 | 한 번에 1개 local coder | no model self-certification |
| 공개 증빙 | 불확실성 표기 | redacted SHA/status | exact environment result |

## OS 및 안전
Windows Sandbox 게스트의 outbox 값만으로 PASS 인증 금지; reviewer 스크립트/실행 환경/검증 권한이 untrusted coder/테스트와 **별도**여야 한다. 불가능하면 자동 원본 병합 중단. 원격 CI는 별도 승인된 코드만, private data 없음. 최소 16GB로 1 모델, 8K 초기 context는 시험 후보값이며 성능 약속 아님.

## CLI 목표 (미구현)
`mla doctor`, `mla plan validate`, `mla plan approve`, `mla queue status`, `mla queue start`, `mla queue stop`, `mla queue resume`, `mla benchmark --synthetic`, `mla evidence export --redacted`. 임의 셸 명령 금지, 테스트 argv allowlist. 중요한 repo 대상으로 항상 사전 승인.


---

## V1.1 보조 병렬 coder lane (설계만, 기본 OFF)

원래 단일 로컬 Qwen 상주(1050Ti/16GB)는 **그대로**다. 추가 remote Hydrogen lane은 독립 승인된 작업만 처리하며 로컬 GPU 동시상주 요구를 늘리지 않는다.

```text
My Local AI Controller [owner/plan SHA, DAG/READY, status authority]
  |-- EAI AdvisorPort [non-authoritative]
  +-- ProviderRegistry + PrivacyBudgetGuard + LeaseScheduler
       |-- LOCAL Qwen + OpenCode [DEFAULT ON when approved/local configured]
       |-- REMOTE Gemini 4 Hydrogen API [DEFAULT OFF; explicit egress/tier GO]
       +-- WEB Instant [EXTERNAL HUMAN LANE; not API-invocable]
              each coding worker => own disposable worktree, disjoint paths
              => untrusted CandidateDiff
              => independently trusted reviewer (F18)
              => guarded local ref / HOLD / SQLite checkpoint
```

계획 경로: `src/my_local_ai/providers/{base,registry,policy,hydrogen}.py`, `src/my_local_ai/controller/provider_scheduler.py`, `src/my_local_ai/state/provider_recovery.py`, `tests/security/test_provider_*.py`. **기존 dev 소스/파일명 점검 후 최소 변경**한다. Hydrogen은 코딩과 수정 후보 생성; API 응답 자체는 신뢰 검증이 아니다. 서로 다른 allowed_paths여도 lockfile/공유 스키마/종속 변경 충돌 시 병렬 실행 금지. 429/paid/no key/off -> local-only; safe checkpoint + lease fencing + source SHA 대조 후에만 재배정, 독립 READY는 계속.

전체 BE/API/DB/FE/안전/수용 명세는 `docs/DETACHABLE_MULTI_MODEL_WORKERS.md`. 선택적 확장 큐는 `docs/OPTIONAL_PROVIDER_TASK_QUEUE.json`; **P1 30개 REQ·기존 phase gate 불변**.

---

## V1.2 ExperienceSelector — 사용자 소유 개발경험 학습 (선택형 설계)
`My Local AI Controller`의 PlanSpec/TaskSpec SHA·DAG·권한/자원·F18 판단은 최종 권위로 유지한다. 하위 `ExperienceSelector`는 **승인된 READY에 적용 가능한 스킬/템플릿/수정 전략을 추천만** 한다. Qwen/OpenCode·Hydrogen과 자동 실행 승격 권한을 공유하지 않는다.

`Observed(redacted run/test/sha) → Candidate → TrustedReviewBoundary → Synthetic A/B → Owner-Approved Versioned Skill → read-only retrieval top3`. 독립 검증 실패 또는 출처·계정/데이터 권리 위반은 QUARANTINE. SQLite/FTS5 불능·no-match·conflict 상태에는 기억 미적용 기존 Qwen baseline으로 정상 fallback. EAI AdvisorPort는 계속 비권한 선택형, AXNODE도 선택적 typed graph/portable export 후보이며 신규 바이너리 런타임 선행 필수 아님.

예상 경로 `src/my_local_ai/experience/{schema,collector,retrieval,curator,policy,skills}.py`, `controller/experience_selector.py` 및 SQLite own DB/CLI read-only. 실제 dev 경로/라이선스·PR 충돌 조사 뒤 별도 구현. 전체 스키마·위험/acceptance는 `docs/EXPERIENCE_LEARNING_ENGINE.md`, 작업 큐 `docs/OPTIONAL_EXPERIENCE_TASK_QUEUE.json`. 별도 사용자 구현 범위 승인 전 기존 P1/P2 분모/READY 불변.
