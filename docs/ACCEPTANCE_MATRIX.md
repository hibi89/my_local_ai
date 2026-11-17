# My Local AI — REQ-01~32 수용 매트릭스 (전수, 설계 시점)

모든 REQ는 현재 **DESIGNED_NOT_IMPLEMENTED / PASS NOT_RUN**. 아래는 계획된 검증 방법이며 실행 결과가 아니다. 승인 가중치 미정이므로 공식 검증률 UNASSESSED. 본 표가 전체 최종설계 범위 기준이며 누락·축소 금지.

| REQ | 구체 수용 대상 | 최소 증거 수준 | 설계 작업 ID | 실제 결과 |
|---|---|---|---|---|
| REQ-ID | 요구사항: 수용조건(간략) | 정확 SHA 합성+연동 증거 |  | NOT_RUN |
| REQ-01 | 원본 provenance: EAI·AX 정확 브랜치/소스·라이선스·파일 SHA manifest 생성 | 정확 SHA 합성+연동 증거 | MLA-001 | NOT_RUN |
| REQ-02 | 최종설계 전수 추적: High REQ-ID→소스→테스트→증거 SHA 전수 매핑 | 정확 SHA 합성+연동 증거 | MLA-001 | NOT_RUN |
| REQ-03 | 불변 High 작업 승인: PlanSpec 버전+SHA+승인 scope 강제, 갱신 시 재승인 | 정확 SHA 합성+연동 증거 | MLA-002 | NOT_RUN |
| REQ-04 | 계약 유효성: TaskSpec ID/allowed_paths/checks/예산/출처 스키마 검증 | 정확 SHA 합성+연동 증거 | MLA-002 | NOT_RUN |
| REQ-05 | EAI CPU 기획: 허가된 READY만 근거 제안, CPU 독립 판단 유지 | 정확 SHA 합성+연동 증거 | MLA-008, MLA-019, MLA-028 | NOT_RUN |
| REQ-06 | 입력 모델 역할 분리: EAI Qwen=입력분류, AX Qwen=코딩, 모델의 승인 금지 | 정확 SHA 합성+연동 증거 | MLA-008 | NOT_RUN |
| REQ-07 | 사용자 승인 경계: 위험/원본/원격/비용/데이터/OS 변경별 별도 GO | 정확 SHA 합성+연동 증거 | MLA-009, MLA-024 | NOT_RUN |
| REQ-08 | DAG READY 작업: 선행 VERIFIED만 착수, 순환/부재 ID 거부 | 정확 SHA 합성+연동 증거 | MLA-010 | NOT_RUN |
| REQ-09 | 단일 모델/실행 잠금: 동시 추론 1개, lock/worker fencing, 자원 과부하 방지 | 정확 SHA 합성+연동 증거 | MLA-011, MLA-019 | NOT_RUN |
| REQ-10 | Ollama 로컬 모델: localhost-only Qwen provider, 오프라인 기본, 불능 시 HOLD | 정확 SHA 합성+연동 증거 | MLA-012 | NOT_RUN |
| REQ-11 | OpenCode 격리 호출: 허용 편집 도구/argv/환경변수/모델 설정 검증 | 독립 보안·실 Windows 필요 | MLA-013 | NOT_RUN |
| REQ-12 | 안전한 Git worktree: 원본 checkout·main 불변, disposable 작업트리·baseline SHA | 독립 보안·실 Windows 필요 | MLA-014 | NOT_RUN |
| REQ-13 | 파일 변경 가드: exact 경로, symlink/reparse/ignored/hook/filter/TOCTOU 차단 | 독립 보안·실 Windows 필요 | MLA-014, MLA-030 | NOT_RUN |
| REQ-14 | 독립 테스트 실행: 고정 허용 명령과 테스트 대상 SHA/환경/exit 기록 | 정확 SHA 합성+연동 증거 | MLA-015, MLA-028 | NOT_RUN |
| REQ-15 | F18 검증 신뢰 경계: 코딩 게스트가 인증할 수 없는 독립 reviewer/승격 정책 | 독립 보안·실 Windows 필요 | MLA-003, MLA-015, MLA-029 | NOT_RUN |
| REQ-16 | 1회 결함 수정: 원인 개선된 재시도 정확 1회, 이후 중단 | 정확 SHA 합성+연동 증거 | MLA-016 | NOT_RUN |
| REQ-17 | HOLD와 큐 지속: 차단 작업 격리, 독립 READY 계속, 의존 작업 보류 | 정확 SHA 합성+연동 증거 | MLA-010, MLA-016, MLA-019 | NOT_RUN |
| REQ-18 | SQLite 상태 정본: WAL/단일 writer/백업/스키마 migration·일관성 | 정확 SHA 합성+연동 증거 | MLA-007 | NOT_RUN |
| REQ-19 | 중단·복구: 강제 종료/재시작/전원 중단 후 worktree·DB·Git 상호 복원 | 정확 SHA 합성+연동 증거 | MLA-017 | NOT_RUN |
| REQ-20 | 중복 실행 방지: plan+task+baseline SHA idempotency/lease generation CAS | 정확 SHA 합성+연동 증거 | MLA-017 | NOT_RUN |
| REQ-21 | Git 근거 로컬 통합: 정확 검증 SHA만 승인된 격리 local ref에 승격 | 독립 보안·실 Windows 필요 | MLA-018 | NOT_RUN |
| REQ-22 | 원격 PR 승인: remote 기본 OFF, owner GO 시 draft PR only, main 병합 금지 | 정확 SHA 합성+연동 증거 | MLA-023, MLA-024 | NOT_RUN |
| REQ-23 | 비밀·외부 통신 차단: 키/프롬프트/고객자료 Git/클라우드 외부 전송 거부 | 독립 보안·실 Windows 필요 | MLA-003, MLA-012, MLA-030 | NOT_RUN |
| REQ-24 | 모델 주입/권한 검증: 모델이 임의 셸·작업/승인·테스트 축소 못함 | 독립 보안·실 Windows 필요 | MLA-003, MLA-013, MLA-030 | NOT_RUN |
| REQ-25 | 예산/상한: 모델 호출/시간/context/RAM/파일 변경/디스크 상한 | 정확 SHA 합성+연동 증거 | MLA-005, MLA-011, MLA-020 | NOT_RUN |
| REQ-26 | 24시간 실행 복구: 장기 실행 안전정지·재시작·열·메모리·OS 절전 조건 실증 | 독립 보안·실 Windows 필요 | MLA-022, MLA-029 | NOT_RUN |
| REQ-27 | 처리량 증거: 수용 REQ/시간, 실패율, 재시도, 메모리/전력 계측 | 정확 SHA 합성+연동 증거 | MLA-005, MLA-020 | NOT_RUN |
| REQ-28 | 필수 CLI: doctor/plan/queue/status/stop/resume/evidence 구현 | 정확 SHA 합성+연동 증거 | MLA-006, MLA-019 | NOT_RUN |
| REQ-29 | 최소 FE 상태 보드: 로컬 읽기전용 상태/승인·HOLD·진척·접근성/보안 | 정확 SHA 합성+연동 증거 | MLA-021 | NOT_RUN |
| REQ-30 | 전수 테스트 게이트: 국소→전체 CI→실 Win11/Ollama→보안→24h 구분 | 독립 보안·실 Windows 필요 | MLA-004, MLA-025 | NOT_RUN |
| REQ-31 | 독립 감사/High 인수: Codex 보안·Astra UX 실제 검수/최종 결함 해결 | 정확 SHA 합성+연동 증거 | MLA-026 | NOT_RUN |
| REQ-32 | 실사용/출시 승인: REAL-USE HOLD, 제품 출시/권한/원격 쓰기 별도 사용자 GO | 정확 SHA 합성+연동 증거 | MLA-027 | NOT_RUN |

## 게이트 정의
- G0 설계: REQ + 코드 경로 + 승인된 계획 + rollback 확인. **지금 이 단계**.
- G1 국소: syntax/type/단위 test 및 private leakage scan. 변경 파일 SHA·명령 기록; 구현 후보 전에 위험 변경 즉시 검사.
- G2 구현 후보: 전체 32 REQ가 실제 코드로 구현된 BE/FE 후보, 계약·실제 파일·feature SHA 전수. 미검증은 IMPLEMENTED_UNVERIFIED.
- G3 GitHub CI: Linux/hosted Windows Python3.11 전체 test+security & package, 결과 정확 SHA; 필수 CI bypass 금지.
- G4 사용자 Win11 Pro: 실제 Ollama Qwen/OpenCode / 경로 한국어·공백 / Windows Sandbox / no-egress / memory·VRAM / stop/resume / adversarial F18.
- G5 24h 무인: 실제 24시간 run+복구/중복 없는 체크포인트, 중단/전력/발열 안정성. 단순 CI 모의=실기기 통과 아님.
- G6 독립 검수/High 인수: Codex Sol Max 보안·코드와 Astra Max UX 평가, 동일 SHA, BLOCKER/HIGH 해결.
- G7 운영 GO: 사용자 명시 승인, 고객자료·GitHub 원격/OS시작/상용은 별도 권한.

출시·상용화·모든 상품 자동 완성 보장은 이번 프로젝트 범위 밖이다. 숫자 근거 없이 완성률 100%·검증 100% 금지.
