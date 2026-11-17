> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

# REQUIREMENTS — My Local AI 최종설계 REQ-01~REQ-32

2026-11-17 KST. **새 저장소는 문서 설계만 수행.** 아래는 전체 목표 및 실제 수용을 위한 추적 ID이며, 파일 존재만으로 완료가 아니다. 기초 구현완성률/공식 검증완성률 모두 UNASSESSED. 원본 EAI·AX 요구를 임의 축소하지 않고 새 통합 요구로 매핑한다.

| REQ-ID | 요구사항 | 수용조건(간략) | 단계/검증 | 위험 | 상태 |
|---|---|---|---|---|---|
| REQ-01 | 원본 provenance | EAI·AX 정확 브랜치/소스·라이선스·파일 SHA manifest 생성 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-02 | 최종설계 전수 추적 | High REQ-ID→소스→테스트→증거 SHA 전수 매핑 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-03 | 불변 High 작업 승인 | PlanSpec 버전+SHA+승인 scope 강제, 갱신 시 재승인 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-04 | 계약 유효성 | TaskSpec ID/allowed_paths/checks/예산/출처 스키마 검증 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-05 | My Local AI 고유 Controller 및 선택적 EAI 재사용 | 자체 DAG·선택·안전 판단이 EAI 없이 가능하고, 필요할 때 일부 EAI 유래 분석을 **advisory**로 사용 | P1 코드 구현 → P2 실제 검증 | MEDIUM | DESIGNED_NOT_IMPLEMENTED |
| REQ-06 | 원본 EAI와 독립된 모델 역할 | EAI 제품 제한은 EAI 원본에 유지, My Local AI Qwen coder는 코드 생성·수정 가능; 모델 승인권 불허 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-07 | 사용자 승인 경계 | 위험/원본/원격/비용/데이터/OS 변경별 별도 GO | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-08 | DAG READY 작업 | 선행 VERIFIED만 착수, 순환/부재 ID 거부 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-09 | 단일 모델/실행 잠금 | 동시 추론 1개, lock/worker fencing, 자원 과부하 방지 | P1 코드 구현 → P2 실제 검증 | MEDIUM | DESIGNED_NOT_IMPLEMENTED |
| REQ-10 | Ollama 로컬 모델 | localhost-only Qwen provider, 오프라인 기본, 불능 시 HOLD | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-11 | OpenCode 격리 호출 | 허용 편집 도구/argv/환경변수/모델 설정 검증 | P1 코드 구현 → P2 실제 검증 | CRITICAL | DESIGNED_NOT_IMPLEMENTED |
| REQ-12 | 안전한 Git worktree | 원본 checkout·main 불변, disposable 작업트리·baseline SHA | P1 코드 구현 → P2 실제 검증 | CRITICAL | DESIGNED_NOT_IMPLEMENTED |
| REQ-13 | 파일 변경 가드 | exact 경로, symlink/reparse/ignored/hook/filter/TOCTOU 차단 | P1 코드 구현 → P2 실제 검증 | CRITICAL | DESIGNED_NOT_IMPLEMENTED |
| REQ-14 | 독립 테스트 실행 | 고정 허용 명령과 테스트 대상 SHA/환경/exit 기록 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-15 | F18 검증 신뢰 경계 | 코딩 게스트가 인증할 수 없는 독립 reviewer/승격 정책 | P1 코드 구현 → P2 실제 검증 | CRITICAL | DESIGNED_NOT_IMPLEMENTED |
| REQ-16 | 1회 결함 수정 | 원인 개선된 재시도 정확 1회, 이후 중단 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-17 | HOLD와 큐 지속 | 차단 작업 격리, 독립 READY 계속, 의존 작업 보류 | P1 코드 구현 → P2 실제 검증 | MEDIUM | DESIGNED_NOT_IMPLEMENTED |
| REQ-18 | SQLite 상태 정본 | WAL/단일 writer/백업/스키마 migration·일관성 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-19 | 중단·복구 | 강제 종료/재시작/전원 중단 후 worktree·DB·Git 상호 복원 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-20 | 중복 실행 방지 | plan+task+baseline SHA idempotency/lease generation CAS | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-21 | Git 근거 로컬 통합 | 정확 검증 SHA만 승인된 격리 local ref에 승격 | P1 코드 구현 → P2 실제 검증 | CRITICAL | DESIGNED_NOT_IMPLEMENTED |
| REQ-22 | 원격 PR 승인 | remote 기본 OFF, owner GO 시 draft PR only, main 병합 금지 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-23 | 비밀·외부 통신 차단 | 키/프롬프트/고객자료 Git/클라우드 외부 전송 거부 | P1 코드 구현 → P2 실제 검증 | CRITICAL | DESIGNED_NOT_IMPLEMENTED |
| REQ-24 | 모델 주입/권한 검증 | 모델이 임의 셸·작업/승인·테스트 축소 못함 | P1 코드 구현 → P2 실제 검증 | CRITICAL | DESIGNED_NOT_IMPLEMENTED |
| REQ-25 | 예산/상한 | 모델 호출/시간/context/RAM/파일 변경/디스크 상한 | P1 코드 구현 → P2 실제 검증 | MEDIUM | DESIGNED_NOT_IMPLEMENTED |
| REQ-26 | 24시간 실행 복구 | 장기 실행 안전정지·재시작·열·메모리·OS 절전 조건 실증 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-27 | 처리량 증거 | 수용 REQ/시간, 실패율, 재시도, 메모리/전력 계측 | P1 코드 구현 → P2 실제 검증 | MEDIUM | DESIGNED_NOT_IMPLEMENTED |
| REQ-28 | 필수 CLI | doctor/plan/queue/status/stop/resume/evidence 구현 | P1 코드 구현 → P2 실제 검증 | MEDIUM | DESIGNED_NOT_IMPLEMENTED |
| REQ-29 | 최소 FE 상태 보드 | 로컬 읽기전용 상태/승인·HOLD·진척·접근성/보안 | P1 코드 구현 → P2 실제 검증 | MEDIUM | DESIGNED_NOT_IMPLEMENTED |
| REQ-30 | 전수 테스트 게이트 | 국소→전체 CI→실 Win11/Ollama→보안→24h 구분 | P1 코드 구현 → P2 실제 검증 | HIGH | DESIGNED_NOT_IMPLEMENTED |
| REQ-31 | 독립 감사/High 인수 | Codex 보안·Astra UX 실제 검수/최종 결함 해결 | P3 독립 감사 | HIGH | POST_P2_NOT_RUN |
| REQ-32 | 실사용/출시 승인 | REAL-USE HOLD, 제품 출시/권한/원격 쓰기 별도 사용자 GO | P4 최종 인수/GO | CRITICAL | POST_P2_NOT_RUN |

**공식 상태:** 이 전체 집합(32개)이 신규 통합 제품의 목표 분모다. 각 REQ의 코드 경로·실제 수용 테스트·검증 SHA는 [ACCEPTANCE_MATRIX](docs/ACCEPTANCE_MATRIX.md) / [INSTANT_TASK_QUEUE](INSTANT_TASK_QUEUE.json)에서 추적한다. 32건을 같게 나눈 임의 공식 점수는 없다. 사용자 승인 가중치 확정 전 퍼센트 대신 구현된 REQ수/32 및 검증 PASS개수/32, UNASSESSED를 보고한다.

### AX F01–F20 역사적 기준과의 매핑
F01→REQ-02/03/04, F02→08, F03→09, F04→10, F05→12, F06→13, F07→14/15, F08→16/17, F09→18, F10→19/20, F11→21, F12→22, F13→01/03, F14→05/06, F15(AXNODE optional)→03/08 인터페이스 후순위, F16→25/27, F17→26/27, F18→11/13/15/23/24, F19→14/15, F20→17/22/28/29. 기존 F-ID 결과를 새 REQ의 PASS로 이월하지 않는다.

### EAI 역사적 기준과의 매핑
EAI 독립 CPU Cognition/Intent/ResultSpec 및 bounded typed goals = REQ-05/06/14. P24/P26 SHA-pinned allowlist/owner execution = REQ-03/04/07. EAI P38 Hydrogen 벤치마크는 선택적 실험이며 필수 기능 아님; 실제 모델 결과 미검증. 기존 13종 모든 목표의 호환성은 원본 이식 단계에서 별도 테스트하고, 검증 없이 지원한다고 주장하지 않는다.


---

## 기존 REQ-14/29/30의 브라우저 실행 시점 — 2026-11-17 사용자 확정
`REQ-29`(FE 상태판)·`REQ-30`(전수 검증 하네스)·`REQ-14`(독립 테스트)의 **P1 구현 코드 작성과 P2 전체 검증 실행**을 분리한다. P1은 BE+FE 코드·API·상태 전이·UI 구성·테스트 하네스 작성과 문법/타입·필요 최소 빌드/국소 스모크, 인증/권한/비밀/원본/DB 손실/F18 즉시 검사로 구현 100% 후보를 판단한다. 반복 브라우저·Playwright E2E·클릭·스크린샷·반응형/접근성 전체 검증은 P2 `MLA-V007` 이후 실시한다. 고위험 또는 구현 상태 확인에 불가결한 최소 브라우저 스모크만 예외. 미실행은 `NOT_RUN`이며 P1 `IMPLEMENTED_UNVERIFIED`는 브라우저/검증 PASS 아님. 기존 필수 CI·P2 LOCKED·30 REQ 분모 및 Hydrogen 선택형 확장 분모 불변.

## V1.1 선택형 확장 REQ-EXT-01~08 — 공식 기존 REQ-01~32 분모 불변

2026-11-17 사용자 요청에 따라 최종설계의 **선택형 Hydrogen 병렬 개발 워커**를 구조에 반영했다. 이 항목은 원래 확정된 `REQ-01~30` P1 구현완료율 분자/분모와 `REQ-31~32` 후행 감사/GO, `VERIFICATION_TASK_QUEUE.json`의 8개 P2 게이트를 **변경·축소하지 않는다.** 신규 확장 구현을 필수로 재분류하려면 별도 전체 REQ 기준선/가중치/작업 큐와 사용자 GO가 필요하다. 이번 변경은 외부 API 호출·송신 승인이 아니다.

| 확장 REQ | 설계 대상 | 수용 기준 | 추적 작업 | 상태 |
|---|---|---|---|---|
| EXT-01 | ProviderPort/capability/immutable worker contract | Qwen-only 동작·비신뢰 요청 응답·SHA/승인 검증 | EXT-HYD-01 | DESIGNED_NOT_IMPLEMENTED |
| EXT-02 | 0원/프라이버시/쿼터 정책 | 기본 OFF; 무료 미확인/유료/429/비밀 자료 전송 거부 | EXT-HYD-02 | DESIGNED_NOT_IMPLEMENTED |
| EXT-03 | 독립 병렬 스케줄링 | 서로 다른 READY, 격리 worktree, 경로·lease 충돌 차단 | EXT-HYD-03 | DESIGNED_NOT_IMPLEMENTED |
| EXT-04 | Hydrogen API 탈부착 adapter | mock만 기본, 정확 API 계약·라이브 사용 별도 GO | EXT-HYD-04 | DESIGNED_NOT_IMPLEMENTED |
| EXT-05 | 장애·fallback·SQLite checkpoint | 429/타임아웃/owner OFF 시 중복 없이 Qwen 재배정 후보 | EXT-HYD-05 | DESIGNED_NOT_IMPLEMENTED |
| EXT-06 | FE/CLI provider 상태판 | 가용성/차단 이유/비용 0원·소진 표시, 비밀 미노출 | EXT-HYD-06 | DESIGNED_NOT_IMPLEMENTED |
| EXT-07 | 합성/보안·F18 수용 검증 | HYD-AC-01~10, 모델 자기 PASS 차단, P2 별도 | EXT-HYD-07 | DESIGNED_NOT_IMPLEMENTED |
| EXT-08 | 라이브 무료 tier 선택형 시험 | 해당 계정·model ID·ToS·허용 데이터 scope 별도 owner GO | EXT-HYD-08 | BLOCKED_OWNER_APPROVAL |

**상세 구조:** `docs/DETACHABLE_MULTI_MODEL_WORKERS.md`; **독립 작업 큐:** `docs/OPTIONAL_PROVIDER_TASK_QUEUE.json`; **완료율:** 기존 30 필수 REQ에 미산입, 별도 선택형 설계 상태만 보고.

---

## V1.2 선택형 경험학습 확장 요구사항 EXT-EXP-01~07 (설계만)
2026-11-17 사용자 최종설계 변경: 모델 Q&A를 대량 암기·학습시키기보다는 **자기 개발 작업의 독립 검증된 실패/수정/복구/테스트 증거**로부터 안전한 스킬·계획·도구 추천을 개선한다. 기존 `REQ-01~30` 필수 P1 구현 100% 후보와 `REQ-31/32` 후행, P2 8검증 분모를 소급 변경하지 않는다.

| ID | 개발 범위 | 수용 조건 | 작업 | 상태 |
|---|---|---|---|---|
| EXP-01 | immutable Event/Suggestion 권리·SHA/비신뢰 계약 | 위조 trusted/owner GO 거부 | EXT-EXP-01 | DESIGN_ONLY |
| EXP-02 | SQLite redacted 경험 수집과 backup/migration | private/secret 외부·로그 0, APP_ID 원본 보존 | EXT-EXP-02 | DESIGN_ONLY |
| EXP-03 | local search/FTS5 optional + 안전·충돌 필터 | 근거 높은 관련 top3, no-match 정상 | EXT-EXP-03 | DESIGN_ONLY |
| EXP-04 | 후보 skill 버전·검증/승인/격리/롤백 | 모델 자기 PASS로 활성 불가 | EXT-EXP-04 | DESIGN_ONLY |
| EXP-05 | Controller 읽기전용 추천 연결 | 계획·allowed_paths·F18 우회 0, OFF 회귀 | EXT-EXP-05 | DESIGN_ONLY |
| EXP-06 | read-only 경험 상태 UI·CLI | 비밀/원본 미노출, 학습/삭제/승인은 별도 | EXT-EXP-06 | DESIGN_ONLY |
| EXP-07 | 합성 own-data A/B·전체 수용 | accepted REQ/hour/안전/재작업 동일 SHA 비교, P2 별도 | EXT-EXP-07 | DESIGN_ONLY |

외부 Sol Max 출력 대량 수집·모델 가중치 학습·비공개 추론 추출은 설계 범위 외. 합성/mock 범위 외의 실제 사용자 데이터 자동 수집, 외부송신·유료/계정 승인, 권한·GitHub 원격 변경은 명시적 사용자 GO 전 금지. 세부 `docs/EXPERIENCE_LEARNING_ENGINE.md` 및 `docs/OPTIONAL_EXPERIENCE_TASK_QUEUE.json`.
