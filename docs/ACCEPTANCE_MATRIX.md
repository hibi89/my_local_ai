> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

# My Local AI — REQ-01~32 수용 매트릭스 (전수, 설계 시점)

모든 REQ는 현재 **DESIGNED_NOT_IMPLEMENTED / PASS NOT_RUN**. 아래는 계획된 검증 방법이며 실행 결과가 아니다. 승인 가중치 미정이므로 공식 검증률 UNASSESSED. 본 표가 전체 최종설계 범위 기준이며 누락·축소 금지.

| REQ | 구체 수용 대상 | 최소 증거 수준 | 설계 작업 ID | 실제 결과 |
|---|---|---|---|---|
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

## P1/P2 브라우저 수용조건 분리 — 2026-11-17
- `REQ-29` FE 최소 상태판 및 `REQ-30` 검증 하네스 구현: P1은 실제 기능 코드·연결/테스트 하네스, 문법/타입/최소 빌드·국소 스모크만 구현 증거로 인정; 반복 브라우저/Playwright 검증은 `DEFERRED_TO_P2`.
- `MLA-V007` P2에서 웹 상태판이 실제 존재할 때 브라우저/Playwright 핵심 흐름(상태·승인·HOLD·진척, 버튼/폼), 키보드·접근성·반응형, Console/Network, Host/CSRF를 실제 실행하여 PASS/FAIL/NOT_RUN을 남긴다. CLI-only면 `NOT_APPLICABLE` 증거를, 실제 브라우저가 없으면 `NOT_RUN`을 기록한다.
- 고위험 인증·권한·데이터 손실·비밀·F18 등은 P1에서 즉시 필요한 안전 검사 예외. 꼭 브라우저가 필요한 경우 좁은 시나리오만 실행하고 정확 SHA·이유/결과 기록한다. P1 국소 PASS는 P2 브라우저 PASS가 아니다.
- 기존 P1 30 REQ·28작업/P2 8작업·P2 LOCKED 및 필수 CI/브랜치 보호 변경 없음.

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

> **단계 분리:** 위 REQ-01~REQ-30 수용 조건은 P1 중에는 테스트·코드 작성 여부로만 구현 근거를 기록하고, **P2에서 실제로 통과**해야 검증 근거가 된다. REQ-31은 P3 독립 감사, REQ-32는 P4 High 최종 인수/사용자 GO이며 P1 코드 분모가 아니다. 각 P2 작업 ID 및 정확 SHA는 `VERIFICATION_TASK_QUEUE.json`에서 확인한다. `INSTANT_TASK_QUEUE.json`의 P1 `status`를 P2 PASS로 해석 금지.


---

## V1.1 확장 수용표 — Hydrogen 탈부착 병렬 워커 (별도, 기존 32 REQ/P2 LOCK 불변)
이 확장은 기존 P1 30 REQ·28 작업 또는 P2 8 검증의 완료 근거가 아니다. 2026-11-17 현재 모든 아래 HYD-AC는 **NOT_RUN**, 외부 API/사용자 Windows/인증·권한은 **NOT_APPROVED**.

| AC-ID | 독립 수용 조건 | 방법/필수 증거 | 결과 |
|---|---|---|---|
| HYD-AC-01 | 기본 OFF에서 outbound 0, 로컬 Qwen만 정상 | socket denial + local synthetic exact SHA | NOT_RUN |
| HYD-AC-02 | 다른 독립 READY 2개 격리 실행·경로 충돌 없음 | mock coder + disposable worktree | NOT_RUN |
| HYD-AC-03 | shared lockfile/DB/schema/API contract와 경로 중첩 병렬 거부 | adversarial scheduler tests | NOT_RUN |
| HYD-AC-04 | 429/401/403/paid/unknown tier/no key/OFF 모두 API stop | fake transport + request counter | NOT_RUN |
| HYD-AC-05 | epoch invalidation, 중단/재시작 중복 patch 0, Qwen 안전 재배정 | injected crash + SQLite/Git SHA reconciliation | NOT_RUN |
| HYD-AC-06 | private repo/고객 DB/token/.env egress 0 | synthetic canary/scope classifier tests | NOT_RUN |
| HYD-AC-07 | Hydrogen 위조 PASS/receipt/approval 거부 | F18 independent reviewer exact SHA; owner Win11 OS boundary | NOT_RUN |
| HYD-AC-08 | 12 합성 작업의 accepted REQ/hour · 정확성 · 비용/시간 비교 | fixed baseline SHA, separate worker reports | NOT_RUN |
| HYD-AC-09 | remote API·비용·권한·GitHub PR/고객 자료 각각 별도 GO | denied-policy tests, redacted ledger | NOT_RUN |
| HYD-AC-10 | Provider OFF 이후 기존 30 REQ/원래 기능 보존 | exact-SHA regression tests (P2 후행) | NOT_RUN |

작업 ID·의존성·허용 파일/상태는 `docs/OPTIONAL_PROVIDER_TASK_QUEUE.json`, 상세 수용 정의는 `docs/DETACHABLE_MULTI_MODEL_WORKERS.md`. 선택형 확장을 필수 범위로 재편하면 새로운 승인된 REQ/가중치/acceptance 버전을 만든 뒤에만 분모 변경; 기존 수치 소급 변경 금지.


## 2026-11-17 P1 SWU source mapping only (not P2 acceptance)

| REQ | SWU code owners | P2 verifiers |
|---|---|---|
| REQ-01 | MLA-SWU-001 | MLA-V002, MLA-V008 |
| REQ-02 | MLA-SWU-001, MLA-SWU-002, MLA-SWU-039 | MLA-V001, MLA-V008 |
| REQ-03 | MLA-SWU-003, MLA-SWU-007 | MLA-V008 acceptance sweep |
| REQ-04 | MLA-SWU-004 | MLA-V001 |
| REQ-05 | MLA-SWU-005, MLA-SWU-006, MLA-SWU-038 | MLA-V008 acceptance sweep |
| REQ-06 | MLA-SWU-005, MLA-SWU-006 | MLA-V008 acceptance sweep |
| REQ-07 | MLA-SWU-007, MLA-SWU-008, MLA-SWU-029, MLA-SWU-036 | MLA-V005 |
| REQ-08 | MLA-SWU-009 | MLA-V005 |
| REQ-09 | MLA-SWU-012, MLA-SWU-015, MLA-SWU-038 | MLA-V003 |
| REQ-10 | MLA-SWU-013 | MLA-V003 |
| REQ-11 | MLA-SWU-014, MLA-SWU-015 | MLA-V002, MLA-V003 |
| REQ-12 | MLA-SWU-016, MLA-SWU-018, MLA-SWU-019 | MLA-V004 |
| REQ-13 | MLA-SWU-017, MLA-SWU-019 | MLA-V002 |
| REQ-14 | MLA-SWU-020, MLA-SWU-021 | MLA-V004 |
| REQ-15 | MLA-SWU-020, MLA-SWU-021, MLA-SWU-027 | MLA-V002, MLA-V004 |
| REQ-16 | MLA-SWU-022, MLA-SWU-023 | MLA-V005 |
| REQ-17 | MLA-SWU-009, MLA-SWU-023, MLA-SWU-038 | MLA-V005 |
| REQ-18 | MLA-SWU-010, MLA-SWU-011, MLA-SWU-025 | MLA-V005 |
| REQ-19 | MLA-SWU-025, MLA-SWU-026 | MLA-V005, MLA-V006 |
| REQ-20 | MLA-SWU-011, MLA-SWU-024, MLA-SWU-026 | MLA-V005, MLA-V006 |
| REQ-21 | MLA-SWU-027 | MLA-V004, MLA-V005 |
| REQ-22 | MLA-SWU-028, MLA-SWU-029 | MLA-V008 acceptance sweep |
| REQ-23 | MLA-SWU-013, MLA-SWU-030, MLA-SWU-031 | MLA-V002 |
| REQ-24 | MLA-SWU-014, MLA-SWU-015, MLA-SWU-030, MLA-SWU-031 | MLA-V002, MLA-V004 |
| REQ-25 | MLA-SWU-012, MLA-SWU-032, MLA-SWU-034 | MLA-V003, MLA-V006 |
| REQ-26 | MLA-SWU-032, MLA-SWU-033 | MLA-V006 |
| REQ-27 | MLA-SWU-034 | MLA-V003, MLA-V006 |
| REQ-28 | MLA-SWU-035, MLA-SWU-036 | MLA-V007 |
| REQ-29 | MLA-SWU-037 | MLA-V007 |
| REQ-30 | MLA-SWU-039 | MLA-V001, MLA-V002, MLA-V008 |

Original REQ acceptance criteria remain authoritative. Existing 5/30 implementation count unchanged without fresh per-REQ acceptance.
