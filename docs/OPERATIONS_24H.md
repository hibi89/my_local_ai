# My Local AI — 24시간 무인 운영·예산/성능·실패 복구 설계

## 운영 원칙
실기기 24시간 자율 코딩 성공은 **목표**이지 현재 결과가 아니다. 일정과 실행은 사용자가 명시 승인한 합성 프로젝트에서 시작한다. 개인 PC를 모델과 무리하게 공유하지 않으며, 높은 부하가 안전하지 않을 때 STOP/HOLD한다. 별도 유료 클라우드·외부 LLM API가 반드시 필요하지 않은 구조.

## 기본 예산(초기 후보값, 실측 후 조정)
- Windows 11 Pro, GTX1050Ti/16GB RAM, 기존 Qwen3 4B 설치. 모델 하나만 상주, 동시 OpenCode 작업 1개. CPU 기반 검증과 모델 추론의 메모리 충돌은 순차로 회피.
- 8K 컨텍스트는 **비교 출발점**, 모델별 최적값·VRAM allocation·추론 속도 미측정. 3B coder 후보 vs 4B candidate를 **수용된 REQ/시간**·실패율·RAM·전력으로 평가. 작은/중간/큰 작업 단위 벤치마크.
- TaskSpec에 max_model_calls, max_wall_seconds, max_changed_files, max_changed_bytes, max_context_tokens, max_repair_attempts=1 지정. 유효 값은 실제 워커/Windows 시스템 계측 후 사용자 승인.
- 모델 불능/OOM/리소스 임계 초과/지나친 발열/온도 측정 불가 시 작업 단위 일시정지. 전체 계획/원본 불변 유지.
- 시스템 절전·Windows Update·잠자기 중 자동 기동은 OS 권한/설정 변경이므로 **자동 활성화 금지**. 재개 가능한 큐만 먼저 설계.

## Supervisory loop
1. owner-approved PlanSpec digest와 source SHA preflight; 모델/provider/보안 도구 설치판 확인, 알 수 없으면 HOLD.
2. single-process lock, SQLite lease generation; READY 중 자원/위험/의존성 조건에 맞는 task 선택.
3. CODING heartbeat + provider token/time/CPU/MEM 관측; write scope 위반·네트워크 escape 발견 즉시 stop.
4. 별도 trusted reviewer 경계에서 검증 가능한 경우에만 VERIFIED, 불가하면 CANDIDATE_UNVERIFIED.
5. 실패 사유 분석 + 개선된 1회 수정, 두 번째 진전 없는 실패는 해당 task HOLD, 다른 READY로.
6. 이벤트·SHA/정본 reflog 기록, redacted summary 생성. 원본 프롬프트/코드 미업로드.
7. Graceful STOP은 임대 종료와 checkpoint, 강제 종료는 다음 실행에 의해 reconciliation 및 이중 실행 금지.
8. 24시간 실제 시험 전 원본 PC 전원/냉각/저장공간·사용자 Windows 기기 안전조건 점검.

## 재시작 시나리오 검증
- 정상 정지/재개: 이미 VERIFIED된 작업 중복 실행 금지.
- 코딩 중 kill: PREPARED worktree를 미승인으로 보류하고 안전한 lease reconciliation.
- 리뷰 중 kill: 임시 후기 영수증 임의 PASS 금지.
- DB 저장 후 Git ref 업데이트 전 crash: exact SHA와 ref reconciliation, 불명확하면 manual HOLD.
- 대기 시간/모델 응답 중 네트워크 오류(로컬): 무한 반복 금지.
- 원본 디스크/고객파일 비정상 상태: 자동 정리 금지·원본 보존.

## 성능 측정
값: 실제 수용 REQ/hour, 구현 후보 task pass/attempt, median/95th task latency, local inference tokens/s (실측 경우), CPU/RAM peak/VRAM usage if available, retries/HOLD, zero unapproved writes, crash recovery success, 24h stable run evidence. 시간이 오래 걸려도 스스로 허위 PASS를 만드는 것보다 HOLD를 우선한다.

## 실측/비용 조건
모델 무료 여부·라이선스는 각 배포 버전 기준 확인; 전력 소모는 0원이 아님. 실측 없는 '하루 몇 SKU'·24h 무정지/100% 검증 약속 금지.
