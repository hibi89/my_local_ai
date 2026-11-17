# 구현완료율 P1 / 검증완료율 P2 강제 분리 (사용자 최신 확정, 2026-11-17 KST)
**이 규칙이 기존 "매 커밋 전체 CI 확인" 및 혼재된 작업 큐 지시를 대체한다.**
| | P1 **구현완료율** | P2 **검증완료율** |
|---|---|---|
| 목적 | 최종설계 실제 BE/FE 구현 코드 100% **후보** | 전체 CI·기능·통합·보안·회귀·Windows/실모델·24h 실제 검증 및 결함 수정 |
| 대상 | REQ-01~REQ-30 실제 구현/코드·테스트 **작성** | 위 REQ의 수용조건 실제 **실행/통과** 및 근거 |
| 큐 | `INSTANT_TASK_QUEUE.json` (P1 전용 28 작업) | `VERIFICATION_TASK_QUEUE.json` (P2 8 검증 + P3 감사/P4 인수 2 단계) |
| 단계 시작 | 사용자 High 설계 GO 후 | **P1 구현후보 100% 근거 + High 검토 + 정확 코드 SHA** |
| 완료 | `IMPLEMENTATION_100_CANDIDATE`, 검증 완료 아님 | 승인된 가중치 수용조건 실제 PASS, 미실시 NOT_RUN |
| 현행 | 승인 전/코드 작성 0/30, UNASSESSED | **LOCKED**, NOT_RUN / UNASSESSED |
### 필수 게이트
1. P1 작업자는 오직 구현 큐의 READY(독립 묶음 3~10)를 실행. 설계·기능 코드·테스트 하네스 작성, 문법·타입·국소 스모크를 수행하되 전체 CI 수동 반복 조회·대기, 전체 회귀/실기기/24h P2 작업은 착수하지 않는다.
2. **기존 필수 GitHub CI를 끄거나 우회하지 않는다.** 인증·권한·데이터 손실·비밀·원본 보호·보안/F18 위험은 P1에서도 **즉시 검사/FAIL-CLOSED**. P1 테스트 일부 실행했다고 P2 공식 검증 완료로 표시 금지.
3. P1 구현 100% 후보 진입에는 REQ01~30(실제 코드 범위)의 전체 경로/테스트/기능 SHA 근거, P1 작업 전수 상태, 고위험/보안 결함 처리, High 명시 판정이 필요하다. REQ31 독립감사 및 REQ32 운영GO는 구현 분모가 아니라 후행 게이트로 별도 기록.
4. 위 조건과 사용자 승인 설계의 정확 SHA를 확인하기 전에는 `WORK_PHASE_GATES.json`의 P2 LOCKED를 해제하거나 verification task를 READY로 바꾸지 않는다. 파일에 수동으로 100%만 적는 것은 게이트 통과가 아니다.
5. P2에서는 전체 CI/보안/실 Windows 11·Qwen/Ollama/OpenCode/검증기/24시간 테스트를 묶어 시행하고 결함을 고친다. P3 Codex Sol Max·Astra Max 실제 독립 검수와 P4 High 최종 인수/사용자 GO는 P2 이후에 각각 별도 판정한다.
6. 공식 검증완료율의 **승인 가중치가 없으면 UNASSESSED**. 구현완료율은 완료된 코드 REQ/30과 그 SHA를 함께 보고하고, 검증률·출시/운영 허가와 혼동하지 않는다.
### 모든 담당자 필독
**High**: P0 설계/큐·P1 인수 Gate·P4 최종 책임. **Instant**: P1 구현 코드(전체 CI 수동 대기 금지)·국소 안전검사. **Codex Sol Max**: P2 완료 후 동일 SHA 독립 코드/보안 감사. **Astra Max**: 같은 SHA UX/a11y 감사. 새 채팅/자동 에이전트/모바일 `ㄱ` 모두 AGENTS 최상단→WORK_PHASE_GATES→현재 단계 큐를 먼저 확인한다.


---

## V1.1 선택형 ProviderPort 범위 잠금
2026-11-17 설계 개선에 따라 Hydrogen/다른 무료 모델의 **탈부착형 병렬 구현 워커** 설계가 추가되었다. **기존 P1 28 작업/필수 REQ-01~30, 공식 검증 P2 8 작업, 구현률 분모 30, P2 LOCKED, Codex·Astra 후행 검수 불변.**

확장 작업은 `docs/OPTIONAL_PROVIDER_TASK_QUEUE.json` 별도 보관: 명시적 High 설계 동기화·작업 범위 승인 이후 mock/ProviderPort 구현을 별도로 착수할 수 있으나 원래 필수 P1 READY를 중단시키거나 확장 실적을 기존 구현 분자로 합산하지 않는다. 실제 외부 Hydrogen API 호출·데이터 송신·유료/권한은 추가 사용자 GO 및 비용·프라이버시·quota gate 없이 불허. 실 Hydrogen과 Windows/F18/24h 전수 검증은 적절한 P2·후행 승인까지 NOT_RUN 유지.
