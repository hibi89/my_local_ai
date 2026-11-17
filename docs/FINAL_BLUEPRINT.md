# My Local AI — High 전체 최종설계 V1 후보
**작성 2026-11-17 KST. 사용자 요청에 따른 새 저장소 설계 정본; 구현/검증 완료 주장 아님.**

## A. 비전·성공조건
GPT-6 High가 한 번 작성한 최종설계의 전체 REQ-ID/의존성/허용 경로/수용조건을 PC가 지속적으로 처리한다. 하나의 Qwen 로컬 코딩 워커가 구현·1회 수정하고, 독립 검증기가 안전 여부를 결정한다. 실패 작업은 HOLD하고 독립 READY를 계속 진행하며 재부팅 후 중복 작업 없이 복구한다. 목표는 **BE/FE 구현완성률 100% 후보까지 로컬 AI가 수행**; 전체 검증률 100% 자동화는 확장 목표. UI 디자인은 외부 Astra 검수로 보완할 수 있다.

초기 기기: Windows 11 Pro/GTX1050Ti/RAM16GB, 기존 Ollama Qwen3 4B. CPU 중심 EAI, Python3.11/SQLite, Git worktree, OpenCode 연계. 무료·오프라인 기본; 외부 모델/유료 API 기본 OFF.

## B. 아키텍처 대안(비용·성능·유지보수)
| 방식 | 성능/속도 | 비용 | 위험 | 결론 |
|---|---|---|---|---|
| A EAI 단독 100% 완성한 다음 AX 병합 | 중복 개발로 통합 늦음 | 무료지만 모델 코딩기 재구축 | 변경 많음 | 제외 |
| B 두 기존 repo를 런타임 필수 의존성으로 연결 | 빠른 임시 시범 | 무료 | 버전/설치/복구 복잡 | 초기 비교 실험에 한정 |
| **C 새 repo에 검증·라이선스 확인한 모듈만 선별 이식** | 기존 코딩기 재사용, 최종 단일 실행 | 무료 중심 | 이식 경계 검수 필요 | **선택** |

결론: 원본 EAI/AX repo·브랜치/main은 보존, 새 `my_local_ai`에 독립 실행을 위한 CPU PlanningPort, AX 큐/코딩기, TrustedReviewBoundary, SQLite, CLI를 통합. 소스별 출처/테스트/권리 확인 후 이식. 기존 13 EAI typed CPU 목표를 임의 삭제하거나 20 AX F-ID를 임의 축소하지 않는다. 하지만 모든 EAI 목표 코드를 주말까지 맹목 복사하는 대신 핵심 연결부터 증거 기반 점진 이식.

## C. 기능 범위
1. High 최종설계/REQ-ID·작업 스펙 검증, 정확 Git SHA/문서 SHA 고정, DAG/READY 스케줄.
2. EAI CPU: 작업 선정·우선순위·근거·모호성/위험 HOLD, 모델 제안은 불신. Qwen의 EAI 용도는 INPUT classification만.
3. AX: 단일 로컬 Qwen 코딩 모델, Ollama localhost, OpenCode 허용된 편집 도구, 격리 Worktree, source/read-only preflight.
4. 모델 비신뢰 결과 → 정확 diff/변경 경로·출처 검사 → **모델과 분리된 신뢰 검증기**가 검증. 인증 경계 불충분 시 CODE_CANDIDATE/HOLD.
5. 실패 1회 개선 재시도 후 HOLD; 무관 작업은 계속, 의존 작업은 보류.
6. SQLite WAL 작업 상태/lease/fencing/idempotency, checkpoint/resume, crash/restart/전원 중단 증거와 보존.
7. 시간/RAM/VRAM/CPU/토큰·성공률/실패 원인·비용 측정; 장시간 운영감시. 1 모델 동시 상주, 자원 초과·발열·절전 안전 중지.
8. CLI: doctor, plan validate/approve, queue status/start/stop/resume, benchmark, evidence export. FE는 사용성 중심 로컬 최소 상태판(후순위), 자동 브라우저 운영 기본 OFF.
9. 사용자 GO 없이는 GitHub remote write/PR, OS startup 등록, 외부 API, 고객 원본 수정, 결제/배포/판매 불허.

## D. 실행 데이터 흐름
`High Plan(immutable SHA) → Owner Scope GO → EAI CPU WorkProposal → AX WorkOrder validator → lock/lease → isolated Git worktree → Ollama/OpenCode coder → untrusted candidate diff → trusted independent review → verified isolated local ref OR HOLD → evidence ledger → next READY`.
모델/게스트가 생성한 `VERIFIED` 문구를 신뢰하지 않는다. 독립 reviewer가 명세/테스트/원본 SHA를 별도 권한 경계에서 검증한 뒤에만 승인 가능한 결과가 된다.

## E. BE/FE/DB/API/보안 범위
- BE: Python3.11 모듈 `contracts/eai_core/ax_runtime/runner/review/state/git/adapters`. 외부 HTTP 포트 필요 없음. 예외적으로 로컬 상태 대시보드는 별도 Host/CSRF/권한 통제.
- FE: 먼저 사용자용 CLI/터미널 출력(REQ 진행, HOLD, 남은 READY, CPU/RAM, model 상태, 수동 승인, stop/resume); GUI는 기본 기능 정상 후 별도 Astra 심사. 서버 UI는 예쁜 디자인보다 원본 보호와 상태 진실성 우선.
- DB: 로컬 SQLite one-writer/WAL, `plans/tasks/runs/leases/attempts/reviews/integration/events/owner_consents`. 사전 백업 없는 migration 금지. 고객 자료·모델 프롬프트 원본 DB/원격 저장 금지.
- API 계약: versioned PlanSpec→WorkProposal(EAI, advisory)→WorkOrder(AX immutable approved)→CandidateDiff(untrusted)→TrustedReceipt(independent)→Git local ref. SHA-256+RunID+lease epoch+허용경로로 전수 확인.
- 보안: 공개 repo 비밀 zero; Git hooks/filter/reparse/symlinks/ignored path/TOCTOU, 격리/환경변수, 프롬프트 주입, 위조 영수증, 외부 egress, 중복 작업/원본 훼손, 비용과 no-admin 원칙 전수.
- 시간: 한 작업이 너무 오래 걸리지 않도록 wall-time, model call, diff/파일 수·컨텍스트 예산을 per task로 설정하되 실제 1050Ti 성능은 실측 전 고정 보장하지 않는다.

## F. P0→P5
- **P0 HIGH** (지금): 최종설계·REQ 32·작업 큐·수용표·브랜치·보안/기술선택 확정, 사용자 설계 승인 대기.
- **P1 Instant**: 독립 ready 3~10개 묶음, BE/FE 코드 구현 후보까지 지속. 최소 문법/계약/보안 국소검사 외 전체 CI 수시 대기 금지.
- **P2**: 후보 구현 전수 후 전체 CI·통합·회귀·권한·Windows 11 Pro 실기기·실 Qwen/OpenCode·격리·24h 안정/복구 검증 및 결함 수정.
- **P3**: 같은 exact SHA의 Codex Sol Max 기술/보안 + Astra Max 사용성/FE 독립 검수(실행 없으면 NOT_RUN).
- **P4**: High 전수 인수, BLOCKER/HIGH 해결. 안전한 개인 실사용은 사용자 GO.
- **P5**: 이후 별도 승인된 상품 생산 워크플로 확장. 크몽 등록/상용화는 본 도구의 자동 GO가 아니다.

## G. 일정 목표 및 현시점
2026-11-17: 설계/브랜치 세팅. 11/18~20: 승인 후 P1 코딩. 11/21~22 주말: 합성 통합 시험 및 기기 실측을 **목표**로 함. PC/격리/모델 접근이 막히면 부분완료+HOLD로 정직하게 보고. 24시간 성공·상품화 속도·추론 품질은 실측 전 미확정.

**완성률:** 구현 후보 = 최종설계 전체 REQ에 해당 코드/근거 존재, 공식 검증률 = 승인 가중치별 실제 수용조건 PASS, RELEASE GO = 운영/권리/실기기/보안과 사용자 별도 승인. 이 설계 작성만으로 수치 상승 없음. 현재 새 repo는 구현 및 검증 `UNASSESSED`.

32개 요구사항은 REQUIREMENTS, 테스트/증거는 ACCEPTANCE_MATRIX, 안전은 SECURITY_MODEL, 데이터/버전은 별도 docs, 원자 구현은 INSTANT_TASK_QUEUE.json 정본.
