# My Local AI — BE/FE/AI/데이터 통합 아키텍처 V1 (design)

```text
High approved PlanSpec (source_sha, plan_sha, owner scope)
    |
    v
EAI CPU PlanningPort (read-only proposal, NO Git/shell/approval)
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
- `src/my_local_ai/eai_core`: EAI CPU 기획/판정/증빙을 버전 고정하여 선별 통합, 원래 EAI 모델 Qwen INPUT-only 불변.
- `src/my_local_ai/ax_runtime`: AX 큐·로컬 coder·worktree·checkpoints·모델 제한, 기존 코드를 출처·검증 추적해 안전 이식.
- `src/my_local_ai/review`: 신뢰 검증기, 실제 OS 분리, 위조 결과 거부, 모델 자가 PASS 금지.
- `src/my_local_ai/state`: SQLite WAL, one-writer, interrupted recovery, 복구 원장.
- `src/my_local_ai/gitops`: remote 기본 OFF, worktree CAS, local ref, scope diff.
- `src/my_local_ai/ui`: CLI 우선, 로컬 상태보드 후순위.
- `tests/unit,integration,security,e2e,windows`: 합성/호스트/실모델 증거 구분.
- `scripts`: 모델 비교·출처 감사·안전 설치 계획; 고객자료 전송 금지.

## 컴포넌트 책임
| 범위 | EAI | AX | 독립검증 |
|---|---|---|---|
| 작업 후보/순서 | CPU 제안·근거 | 실제 승인 DAG 검증 | 판단에 PASS 권한 없음 |
| 코딩 | 모델 생성 금지(입력 분류만) | Ollama/Qwen 코드 생성 | 코드/영수증 불신 |
| 데이터 수정 | 없음 | 격리 allowed_paths만 | trusted independent tests |
| 상태 정본 | 계획 제안만 | SQLite/run/ref | verification receipt |
| 모델 접근 | optional localhost classifier | local coder one-at-a-time | no model self-certification |
| 공개 증빙 | 불확실성 표기 | redacted SHA/status | exact environment result |

## OS 및 안전
Windows Sandbox 게스트의 outbox 값만으로 PASS 인증 금지; reviewer 스크립트/실행 환경/검증 권한이 untrusted coder/테스트와 **별도**여야 한다. 불가능하면 자동 원본 병합 중단. 원격 CI는 별도 승인된 코드만, private data 없음. 최소 16GB로 1 모델, 8K 초기 context는 시험 후보값이며 성능 약속 아님.

## CLI 목표 (미구현)
`mla doctor`, `mla plan validate`, `mla plan approve`, `mla queue status`, `mla queue start`, `mla queue stop`, `mla queue resume`, `mla benchmark --synthetic`, `mla evidence export --redacted`. 임의 셸 명령 금지, 테스트 argv allowlist. 중요한 repo 대상으로 항상 사전 승인.
