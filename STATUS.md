> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

> **[PRODUCT IDENTITY LOCK · OWNER CLARIFICATION · 2026-11-17]** `my_local_ai`는 **EAI의 후속 버전/확장판/완성판이 아니다.** EAI는 선택적으로 재사용할 알고리즘·CPU 분석·도구의 **기술 제공원**일 뿐이다. `my_local_ai`의 고유 목적은 **로컬 모델로 소프트웨어 구현을 지속 자동화하는 개인용 개발 시스템**이며, 정책·스케줄·실행/검증 게이트·진척 기준은 `my_local_ai`가 자체 소유한다. 원본 EAI ADR-0002(Qwen INPUT-only)는 EAI 원본의 아키텍처 지침이지 `my_local_ai`의 코딩 워커 사용 제한이 아니다. EAI 전체 13개 목표·자체 모델 연구의 100% 완료는 `my_local_ai`의 필수 조건이 아니다. 자세한 내용 `docs/PRODUCT_IDENTITY.md`. **P1 구현 우선/P2 검증 잠금 정책은 그대로 유지.**

# My Local AI — STATUS (2026-11-17 KST)

## 현재 상태
- repo: `hibi89/my_local_ai`, PUBLIC, 사용자 생성 empty repo 확인, `main`에 README 최초 baseline SHA `960621d6207e6beb22a7e9480e524988196f3d44`.
- 설계 브랜치: `design/final-blueprint-v1`. P0 High 통합설계 V1, **My Local AI 자체 Controller**, EAI 유래 선택적 분석/AX 로컬 실행·독립 검증, REQ-01~REQ-32, P1 코드 구현 큐 28개 / P2 전체 검증 큐 8개 + 독립 감사/인수 2개, 첫 P1 READY 5개, 위협모델/DB/BE/FE/수용 매트릭스 문서화.
- **실제 my_local_ai 제품 소스 구현 0건 / 구현완성률 UNASSESSED / 공식 검증완성률 UNASSESSED / 전체 CI NOT_RUN / owner Windows11/Ollama 실기기 NOT_RUN / 24h 시험 NOT_RUN.** 현재 문서만 존재하고 코드 이식/모델 호출/배포/PR/권한 변경 없음.
- 위험 게이트: AX F18 guest receipt trust boundary CRITICAL HOLD. 기존 source의 CI 성공은 새 통합 repo 완료 증거 아님.
- 코드 참조(읽기 전용): EAI source HEAD `5186cb1aa7928054d56b1cd0a40ea5943a5b3892`; AX source HEAD `5ab94180471c7ea86344b691fc77ad5c29989071`. 해당 원본 변경 없음.
- 다음 실행: 사용자 최종설계 확인/GO 후 `dev/instant-implementation-v1`의 MLA-001/002/003/004/005. 설계만으로 READY를 VERIFIED로 기록 금지.
- 2026-11-21~22 주말 통합은 목표일, PC/독립 보안 경계·실모델 접근으로 막힐 수 있음. 개인 실사용 및 출시 HOLD.
- 인수인계 기준 설계 소스 커밋/이후 HEAD는 실제 GitHub 브랜치를 재확인. 디자인 문서 커밋의 Python 테스트 PASS 없음.

---

## P1 구현 최신 상태 — 2026-11-17 KST (이하가 위 P0 설계 당시 상태를 갱신)

- **현재 단계:** P1 구현 진행. 사용자의 반복 `ㄱ` 명령에 따라 준비된 코드 작업을 실행했으며, P2 FULL VERIFICATION은 **LOCKED**로 보존.
- **완료 REQ 기준 구현완료율:** **1/30 = 3.33%**, `REQ-04` (TaskSpec ID·경로·검사 argv·예산·source baseline 스키마) 소스 구현 완료 **후행 공식 검증 전**. REQ-03 등 다른 REQ는 전수 구현 완료로 계산하지 않음.
- **구현 큐:** MLA-002/004/005 `IMPLEMENTED_UNVERIFIED` 3/28개, MLA-001 출처 감사 코드+5개 blob PIN 작성했으나 권리/라이선스 미확정으로 `BLOCKED_PROVENANCE`; MLA-003/006/007 다음 READY. 이 숫자는 전체 REQ 구현률과 별도.
- **실제 Python 소스·테스트 근거:** 마지막 코드 수정 커밋 `7814996f9ee0f8e6243be38a5a63284665227c85`. `src/my_local_ai/contracts/task.py`, `plan.py`, `tests/unit/test_contracts.py`; audit `scripts/audit_sources.py`·`docs/IMPORT_MANIFEST.json`·synthetic bench·CI scaffold도 신규 작성.
- **국소 합성 CI:** GitHub Actions `44003823329` (코드 SHA `7814996f9ee0f8e6243be38a5a63284665227c85`) Python 3.11 syntax compile PASS, 21 synthetic unit tests PASS/0 FAIL. 그 직전 run `44003728366`은 계획 SHA-256 64자리 vs Git SHA 40자리 혼동 오류로 FAIL, 코드 수정 후 PASS. **이는 P2 전체 검증, Windows 실모델 검증이 아님.**
- **경계:** 라이선스 확인 전 EAI/AX 소스 이식 없음, 원본 repo 무변경. 모델 생성 영수증 인증·F18 독립 verifier 실 OS 검증 `NOT_RUN/SECURITY_HOLD`; Git 원격 게시·시작프로그램·Production·고객 원본·유료 API 변경 없음.
- **P2/P3/P4:** P2 `LOCKED`, 공식 검증률 `UNASSESSED`, Windows/Ollama/OpenCode 실측 `NOT_RUN`, 24h `NOT_RUN`, 외부 감사 `NOT_RUN`, 운영 `HOLD`.
- **다음 구현 묶음:** MLA-003(F18 fail-closed 경계 설계/적대 테스트), MLA-006(로컬 CLI read-only/dry-run), MLA-007(SQLite 합성 DB·백업/마이그레이션). 계약 source SHA를 참조하고 새 REQ는 실제 전체 경로가 완성될 때만 분자에 산입.
- **기준:** 본 갱신은 이전 `제품 코드 미구현` 문장의 P0 역사적 스냅샷을 대체한다. 사용자 승인된 고정 분모 30, 검증 가중치 미승인 `UNASSESSED`.

---

## P1 2026-11-17 KST 구현 5차 결과 (이전 1/30 상태를 대체)

- 구현완료율: **3/30 = 10.00%**. P1 소스 구현 후보의 분자: REQ-04 (TaskSpec 계약), REQ-08 (결정론적 DAG/READY 후보 필터), REQ-18 (SQLite WAL/FK/원본 보호/마이그레이션 백업). 이 수치는 P2 검증완료율이 아님.
- 신규 구현 경로: `src/my_local_ai/state/{migrations.py,sqlite_store.py}`, `src/my_local_ai/{cli.py,__main__.py}`, `src/my_local_ai/ax_runtime/queue.py`; `tests/unit/{test_state.py,test_cli.py,test_queue_dag.py}`. F18 디자인 `docs/TRUST_BOUNDARY_DESIGN.md`, `tests/security/test_receipt_forgery.py`, 제한된 security synthetic runner 추가.
- MLA-006 CLI doctor/plan validate/status/queue status는 **읽기 전용**으로만 구현. 실제 start/stop/resume/evidence CLI 및 REQ-28 전체는 후속 MLA-019 등에서 구현.
- MLA-007 SQLite는 **자체 APP_ID 파일만** 허용, WAL/FK, 0→1 migration 시 먼저 자체 DB 백업, 알 수 없는 고객 DB/심볼릭 링크 거부. 사용자 실제 DB 접근 및 OS 원자성/Windows reparse 테스트는 NOT_RUN.
- MLA-010 큐 순환·부재 의존성 거부, `VERIFIED` 라벨만으로 READY 승인 금지, 별도 trusted verifier가 제공한 검증 집합을 필수로 요구하며 **후보만 출력**. 실제 디스패치·승격은 미구현, 보안 HOLD.
- MLA-003 F18 불신 경계 디자인/게스트 위조 합성 테스트만 구현; 독립 reviewer host·실 격리 미구현/CRITICAL SECURITY_HOLD. REQ-15/23/24 완료 카운트 제외.
- **합성 GitHub Actions 증거:** `44004810339` at code SHA `4bdff24db9d2a0a3ab37036225df1ff0aa6fe846`: Python3.11 syntax PASS, unit **41 PASS**, security contract **5 PASS**, FAIL 0. 이는 P2 전체 검증·실 Windows·실 Ollama/Qwen/OpenCode·24h 증거가 아님.
- P1 task 작성 완료 후보: MLA-002/004/005/006/007/010 **6/28**, MLA-003 `PARTIAL_F18_SECURITY_HOLD`, MLA-001 `BLOCKED_PROVENANCE`. 다음 READY: MLA-009, MLA-011, MLA-021.
- P2 공식 검증완료율 UNASSESSED, P2 LOCKED, F18 HOLD, Windows/실모델/24h NOT_RUN, 사용자 실운용 GO 없음. 원본 EAI·AX Dev Factory/main 무변경.

---

## P1 2026-11-17 KST 구현 6차 결과 — High V1.1 설계 동기화 후

- **구현완료율 4/30 = 13.33%** (코드 구현 후보만, 기존 REQ-04/08/18 + 이번 REQ-29 읽기전용 로컬 FE 상태 보드). P2 검증완료율 `UNASSESSED`; `IMPLEMENTED_UNVERIFIED` ≠ 검증 완료.
- 설계 동기화 SHA `1e6f0b17c838a70243a72caaa0a694c8a78ab7af`: High design SHA `0de11f63c3ae795e1ed9ec1ec016ac38b864e1d4`에서 Hydrogen OFF-by-default ProviderPort + browser E2E `DEFERRED_TO_P2` 관련 **12문서만 선별 반영**. dev STATUS/HANDOFF/큐/게이트/실제 소스 보존; `docs/SECURITY_MODEL.md`의 신규 Hydrogen 위험 단락은 별도 append.
- MLA-009: plan/source SHA, scope/TTL/HMAC 합성 검증 및 현재 consent DB 상태/철회 확인 코드 작성. **실제 사용자 grant 발급·OS 보호 서명자·Windows 권한 분리 미구현**으로 REQ-07 완료에 산입하지 않음.
- MLA-011: Windows/POSIX OS 파일 잠금·원자적 첫 epoch 초기화·펜싱 카운터·호출/시간/RAM/context/file/disk 예산 코드 작성. **실제 Qwen/OpenCode 실행기에 아직 통합되지 않아 REQ-09 완료에 산입하지 않음.**
- MLA-021: `status_view.py`, `local_dashboard.py` 및 tests; loopback `127.0.0.1` 전용, GET 조회만 허용, Host/Origin/FETCH_SITE/헤더 가드, HTML 정적 접근성, 소유자 승인 미부여·중지 제어 미연결 표시. 상태/작업 수와 구현 진척 redacted; 고객자료/키/원본 출력 없음. **REQ-29 P1 코드 후보로 산입**, 실제 브라우저/UX/a11y 전수 `NOT_RUN`(P2).
- 코드 최신 SHA `75d441ed163b3d91b271653c5e3fc5dae40ece96`, GitHub Actions 합성 실행 `44008410953`: Python 3.11 syntax PASS, **54 unit PASS, 13 synthetic security PASS, FAIL 0**. 이 범위는 P2 전체 CI/Windows/실모델/실 F18/24h 검증이 아님.
- P1 소스 구현 작성 후보 MLA-002/004/005/006/007/010/011/021 = **8/28 작업**. MLA-001 `BLOCKED_PROVENANCE`; MLA-003 `PARTIAL_F18_SECURITY_HOLD`; MLA-009 `PARTIAL_TRUST_ROOT_HOLD`.
- 다음 READY `MLA-012` 로컬 Ollama provider. 네트워크 기본 OFF / loopback-only / Qwen 모델 auto-download 없음. Extension `EXT-HYD-01..08`은 High 별도 설계 큐·기본 OFF, 외부 API 호출/데이터 전송/결제/원격 승인 없음, 30 REQ 분모에서 제외. P2 LOCKED, F18 CRITICAL HOLD, 실제 Windows NOT_RUN.

---

## 2026-11-17 KST 최신 실행 지침 — P1 브라우저 검증 P2로 명시적 이전

- **이전 상태/코드 SHA 보존:** P1 구현완료율 **4/30 = 13.33%**, 코드 SHA `75d441ed163b3d91b271653c5e3fc5dae40ece96`, 합성 GitHub Actions `44008410953` 54 unit + 13 security PASS. 위 수치는 브라우저/실 Windows 검증 근거가 아니다.
- **이번 변경:** `INSTANT_TASK_QUEUE.json` `MLA-019/021/025`의 브라우저/Playwright E2E·시각·키보드/a11y·반응형·Console/Network 전수 검증을 `VERIFICATION_TASK_QUEUE.json` `MLA-V007` P2에 연결. `MLA-006` CLI-only 브라우저 비대상. 실 브라우저 테스트 실행은 `NOT_RUN`.
- P1은 실제 BE/FE 소스·HTML/API·test fixture·구현 수용코드까지 작성하고 Python 문법/type·최소 빌드·국소 합성 HTTP smoke·보안 즉시검사만 실행. 기존 GitHub 필수 CI/branch protection 유지. 보안 고위험 시 최소 브라우저 예외 가능(근거 기록).
- **다음 `ㄱ`:** `MLA-012` localhost-only Ollama provider 구현, 다른 독립 READY는 실제 큐에서 확인 후 묶음 실행. 사용자 PC 작업 금지, EAI/AX 원본 수정 금지. 비인가 Hydrogen/결제/외부전송 금지. SHA·실제 완료 REQ/30 백분율·NOT_RUN/SECURITY_HOLD·다음 READY 보고.
- **P2:** `WORK_PHASE_GATES.json` `LOCKED`, 공식 검증완료율 `UNASSESSED`, F18 실기기 분리 `SECURITY_HOLD`, Windows/Ollama/OpenCode/24h `NOT_RUN`. 브라우저 관련 편의 검증을 P1 진행 차단으로 사용하지 않는다.

---

## P1 2026-11-17 KST 구현 7차 — MLA-012 Ollama 로컬 모델 포트

- **구현완료율: 5/30 = 16.67%** (기존 REQ-04/08/18/29 + 신규 **REQ-10**). REQ-23은 전체 비밀·외부 통신 보호 전수 미구현으로 분자 제외. 현재 모든 수치는 P1 source implementation candidate이며 검증완료율과 다름.
- **실제 코드 SHA:** `1d29951f5a0b0fdbb0585a98b523842a917df6e8` (`dev/instant-implementation-v1`). 변경 경로: `src/my_local_ai/ax_runtime/provider_policy.py`, `src/my_local_ai/ax_runtime/ollama_provider.py`, `tests/security/test_ollama_loopback.py`.
- **MLA-012:** loopback **literal IP** HTTP만 허용 (DNS `localhost` 포함 호스트명·클라우드·프록시·userinfo·redirect 거부), Qwen 태그 allowlist, `GET /api/tags` 모델 확인·부재/실패 HOLD, `POST /api/generate` 비스트리밍 응답 제한, **`/api/pull` 호출 없음**, 기본 생성 disabled, `OneModelLock`/BudgetGuard 필수, 결과 `UNTRUSTED`. 실제 owner consent issuance·trusted F18·OS-level egress 차단은 별도 게이트이며 이 커넥터만으로 보증 불가.
- **합성 국소:** 별도 개발 컨테이너 Python 문법 검사 PASS, 10/10 mocked security tests PASS (기존 budgets/worker_lock은 로컬 합성 스텁으로 연결 테스트; GitHub CI는 실제 모듈에 실행). **GitHub 필수 CI** `44012906535` @ `1d29951f5a0b0fdbb0585a98b523842a917df6e8` **SUCCESS**, syntax/unit/security synthetic jobs PASS. 실제 Windows/Ollama/Qwen/OpenCode/real browser/independent OS F18/24h `NOT_RUN`.
- 큐: MLA-012 `IMPLEMENTED_UNVERIFIED`; MLA-013 (OpenCode 정책 격리) 및 MLA-020 (benchmark 실행 하네스, 실모델 호출 P2) `READY`. MLA-001 `BLOCKED_PROVENANCE`, MLA-003 F18 `SECURITY_HOLD`, MLA-009 owner signer `HOLD` 유지.
- **공식 검증완료율: UNASSESSED**, P2 `LOCKED`, 사용자 실사용 `HOLD`. 원본 EAI/AX/main 변경 없음. 설계 브랜치 신규 V1.2 경험학습 확장은 별도 설계로 유지하며 P1 30 REQ 분모에 산입하지 않음.

---

## 2026-11-17 KST P1 구현 8차 — MLA-013, MLA-020 (실제 2코드 작업)

- **구현완료율 유지 5/30 = 16.67%** (REQ-04/08/10/18/29). 이번 2개 작업의 코딩 후보는 작성했으나 REQ-11 실 격리 runner·실 OpenCode 경로, REQ-24 F18/주입 전체, REQ-27 독립 계측과 실제 accepted REQ/hour 수용을 채우지 못해 신규 완결 REQ 분자 **0**. P1 과장된 증가 금지.
- **MLA-013 코드 SHA `748caecf30e680b2794fde287bbf674801c88079`:** `src/my_local_ai/ax_runtime/opencode_worker.py`, `tests/security/test_opencode_policy.py`. OpenCode V2 explicit tool deny+allow exact edit/read, no shell/remote/auto privilege, fixed Qwen/Ollama argv, owner HMAC+revocation+plan/source SHA, one model lock/budget, disposable worktree request check. Injected attested sandbox port 외에는 launch 없음, output `REVIEW_PENDING` untrusted. 실제 OpenCode binary/version·protected OS sandbox runtime `NOT_RUN`, F18 security HOLD.
- **MLA-020 코드 SHA `63995bfaa0d425d3b361cc9462bbdf37b8b63f5c`:** `scripts/benchmark_real_local.py`, `tests/integration/test_real_model_gate.py`, `docs/LOCAL_MODEL_EVIDENCE.md`. mock-only evidence `MOCK_ONLY`, real-call path P2 owner grant/high/Windows/exact SHA guard, no live benchmark auto call, raw prompt/response 미저장. RAM/VRAM/power/accepted REQ/hour는 미실측 `null`. **tests/integration** mock tests **작성만, 실행 NOT_RUN**.
- **GitHub 필수 합성 CI PASS** `44013825139` at `748caecf30e680b2794fde287bbf674801c88079`, `44014035939` at `63995bfaa0d425d3b361cc9462bbdf37b8b63f5c`. 최신 CI syntax PASS, unit **54/54 PASS**, security **32/32 PASS**. 이는 브라우저·실 Windows·실 모델·F18/24h/P2 전수 검증이 아님.
- **P1 작업 작성 후보:** 이전 9/28 (MLA-012 포함) + MLA-013, MLA-020 = **11/28**; `MLA-001 BLOCKED_PROVENANCE`, `MLA-003 PARTIAL_F18_SECURITY_HOLD`, `MLA-009 PARTIAL_TRUST_ROOT_HOLD`. 다음 queue READY = 0 (잔여 작업이 의존성/보안 차단). High 판단 필요: 권리 미해결 시 원본 복사 없이 신규 코드 경로 승인, isolated F18 trust boundary 및 protected owner signer 설계·작업 차단 해소. 차단 항목과 무관한 범위만 재개.
- **P2 `LOCKED`, 공식 검증완료율 `UNASSESSED`, 실사용 `HOLD`.** GitHub main, EAI, AX Dev Factory, 사용자 PC/OS/외부 API/Production 미변경.

---

## 2026-11-17 KST P1 9차 실제 구현·증거 보강 — MLA-001 (원본 출처·권리)

- 고정 브랜치 HEAD `dev/instant-implementation-v1`에서 **MLA-001 허용된 4개 파일** 감사 기능/합성 테스트/고정 메타데이터 실변경; 소스 SHA **`ffea825ba253b2b12246d3c36f63fb2642215e1d`**. EAI 고정 원본 Git 트리 **191개/완전 목록**, AX 고정 원본 **123개/완전 목록**, 후보 5개 blob SHA 일치, 통상 LICENSE/NOTICE 등 파일명 히트 0. 파일명 0건은 **라이선스·제3자 권리 승인 아님**. 공개 원본 코드 복사·실이식 0.
- `scripts/audit_sources.py`: 핀된 전체 트리 SHA, 후보 blob SHA, tree entry-count, truncation/filename scan 범위 위변조, 누락된 후보 및 자체 라이선스 승인 주장 거부. `docs/IMPORT_MANIFEST.json`에 읽기 전용 증거를 보존. 원격 현재 SHA 실증은 connector 읽기 증거이며 offline audit 스크립트 실행만으로 실 API 확인 불가.
- 원본 EAI 참조 브랜치 현재 SHA `af57af08e0d71fb656c76be241944e8cf232a57a`는 기존 고정 기준 `5186cb1aa7928054d56b1cd0a40ea5943a5b3892`와 다름. 무단 re-pin/원본 수정 금지. AX 고정 브랜치 SHA 일치.
- **GitHub Actions `44014692103` @ `ffea825ba253b2b12246d3c36f63fb2642215e1d` SUCCESS**: Python 3.11 syntax PASS, synthetic unit **56/56 PASS** (기존 54에서 +2), synthetic security **32/32 PASS**. 실제 OS F18/Windows/Ollama/브라우저/24시간, 소스 재사용 법적 검토는 `NOT_RUN/UNRESOLVED`.
- **구현완료율 5/30 = 16.67% (변동 없음)**. 완결 REQ-04/08/10/18/29. MLA-001은 감사 구현 보강이지만 root license/third-party/owner 권리 확인 미해결로 `BLOCKED_PROVENANCE` 유지. 다음 P1 READY 없음; 구조적 의존성 MLA-008·014는 High의 별도 청정 재구현 기준안 승인이 있을 때만 재분류. F18 `SECURITY_HOLD`, MLA-009 보호된 서명자 미구현 유지.
- P2 `LOCKED`, 공식 검증완료율 `UNASSESSED`, 실사용 `HOLD`. main/EAI/AX/Production/OS/remote/유료 API 변경 없음.

---

## P1 2026-11-17 KST 집중 구현·보안 보강 라운드 (owner: 한 회차 묶음작업)

- **최종 설계·실구현률: 5/30 = 16.67% (변동 없음)**. 완료 코드 REQ-04/08/10/18/29. 새 코드 보강을 실효 REQ 완료로 과대 산입하지 않음. P1 작업 구현 후보 11/28 유지. P2 LOCKED, 공식 검증완료율 UNASSESSED, 실사용 HOLD.
- `MLA-009` 승인 체계 (3개 경로): `src/my_local_ai/contracts/approval.py`, `src/my_local_ai/state/consent.py`, `tests/security/test_approvals.py`. reusable `LOCAL_PLAN` plan consent로 `REMOTE_PR/OS_CHANGE/PAID_API/CUSTOMER_DATA/PRODUCTION/NETWORK_EGRESS`를 발급/실행할 수 없도록 fail-closed. 보호된 action-specific owner signer 미연결 상태는 지속 HOLD.
- SQLite critical bugfix: 승인 DB 파일을 교체했는데 기존 WAL이 연결되어 과거 `APPROVED`를 다시 읽는 재현 사례를 발견 (첫 CI `44015195788` FAIL), 최초 원장 파일 identity를 고정해 수정 (`4d665297...` CI `44015315855` PASS). 추가 WAL/SHM sidecar symlink/reparse·교체 검사 후 정상 SQLite 읽기 중 SHM 생성까지 과도 차단한 회귀를 발견 (중간 CI `44015580712` FAIL), 기존 sidecar identity와 신규 정상 sidecar를 구분해 수정 (`d0cc3a6005de3b084d2954699440cdcfff23f985` CI `44015653878` PASS). OS ACL/F18 독립 신뢰 경계는 증명하지 않음.
- `MLA-013` OpenCode 호출 계약 (`b44312d6dacfdc89d1ff2a57cae37a96626d7d2d`): 호출 직전에 trusted TaskSpec/모델/원본·격리 worktree/argv/환경 설정을 recompute하여 위조된 prepared dataclass(모델 선택·명령 추가·GITHUB_TOKEN·허용경로 확대·원본 경로)를 거부. 공급자 정책은 cloud 전면 deny, Ollama만 명시적 allow; OpenCode의 agent permission보다 강한 provider policy를 추가. OS sandbox 없는 호스트 실행 fallback 계속 차단. 합성 CI `44015440880` PASS, 실제 OpenCode/Windows `NOT_RUN`.
- `MLA-003` F18 보안 계약 (`56c7b2f53a38178bbffe6ddadfe217758c6a69ff`): 위조된 guest VERIFIED 선행 상태가 자체 증거만으로 후속 READY를 열지 못함, forged/stale receipts PlanSpec 삽입 거부, self-approved plan도 실행권 없음. 실제 protected trusted reviewer `NOT_RUN`/HOLD.
- `MLA-020/004` 코드·테스트 하네스: 기존 `scripts/benchmark_real_local.py`, `tests/integration/test_real_model_gate.py`의 mock-only 8개를 기존 read-only synthetic CI에 추가 (`ad224cfb59d30ed8c87bfc524976c02662ed7592`). P1의 실제 모델 다운로드·API/Windows 실행 없음. CI `44015752835` @ exact SHA **SUCCESS**: syntax PASS, unit **56/56**, fake benchmark **8/8**, synthetic security **43/43** (합계 107 PASS). 이 숫자는 P2 검증률 아님.
- **HIGH/BLOCKER:** source provenance `MLA-001 BLOCKED_PROVENANCE` (고정 원본의 라이선스/제3자 권리 미확인·원본 복사 금지), F18 independent Windows trust boundary CRITICAL HOLD, protected owner signer/OS isolation HOLD. 현재 READY=[]; `MLA-008/014/015` 의존성의 임의 해제/고위험 범위 축소 금지. High가 독자 구현 경로와 출처 게이트를 재판정해야 다음 안전 READY 할당 가능.
- main/EAI/AX 원본/Production/계정 권한·유료 API/고객 데이터 변경 없음. 실 Windows Qwen/OpenCode, 독립 감사, 24h, 브라우저 `NOT_RUN`.

---

## P1 2026-11-17 KST 구현 작업 집중 라운드 — 자체 BE·Git 경로·복구·F18 계약 (직접 코드 4종)

- 시작 실 HEAD `2be64954d24e1a2ded5c98c104fb849505cc4347`, `AGENTS.md`/큐/확정 REQ 확인. **첫 READY=[]**이므로 승인 없는 의존성/권한을 해제하지 않고 후속 작업의 **비실행·무원본수정 안전 부분**만 실제 코드로 구현. 새 소스/테스트 **11개 파일**, 신규 소스 커밋 4건.
- **MLA-008 clean-room Controller** `a4b3700979ba54413f8f284d6d62f67865bfbc84`: `controller/decision.py`, `advisors/eai.py`, `tests/unit/test_own_controller.py`, `test_eai_advisor_optional.py`. 자체 DAG READY ranking, optional trusted-data-only advisor JSON strict schema; 조언은 동일 risk 내부 정렬만 가능·작업/경로/권한 확대 불가. EAI 원본 코드 **복사 없음**, EAI 비설치에도 기본 동작. 모든 후보 `runnable=false`, 실제 owner GO/OS-격리 자동 실행 없음.
- **MLA-014 path preflight** `b6bb6bb4fc1d051187b179e8d7fdc042006b6273`: `gitops/path_guard.py`, `gitops/worktree.py`, `tests/security/test_worktree_scope.py`. symlink/reparse/hardlink/metadata/casefold alias/original checkout overlap 차단·디렉터리 사전 검사, 전부 읽기전용 `PRECHECK_ONLY`; **실제 Git worktree 생성·hook/filter/ignored 파일 검증은 미구현**, P2 이전 실제 원본/중요 ref 승격 금지.
- **MLA-016 repair-once recovery policy** `66f0a244cea78e7fa3bb533dd7fcb36f4a9399b0`: `ax_runtime/recovery.py`, `tests/unit/test_repair_once.py`. stale plan/source/epoch 차단, first review failure에서만 repair 제안, 2차 실패 HOLD, 중단 시 fresh lease/승인 재요구. 실행/SQLite 변경 없음.
- **MLA-015 F18 receipt parsing** `705a139d5ed8a3f363eb58c4c12a31e71b761542`: `review/trusted_runner.py`, `review/receipt_guard.py`, `tests/security/test_independent_verifier.py`. 체크 축소/거짓 PASS/replay nonce/lease·task·run·SHA·HMAC 위변조 거부. MAC 매칭이라도 결과 `SIGNATURE_CHECKED_F18_NOT_PROVEN`이며 `may_promote_git_ref=false`. 보호된 독립 검증 실행기/서명자·실 Windows 경계 미구현 계속 `SECURITY_HOLD`.
- CI `44016649399` at `705a139d5ed8a3f363eb58c4c12a31e71b761542` SUCCESS. Python compile PASS, synthetic unittest **75/75 PASS**, fake-only benchmark **8/8 PASS**, synthetic security **61/61 PASS**, 총 **144/144 PASS**, 이전 107 대비 +37. 실제 Windows/Ollama/OpenCode/OS F18/24h/브라우저 `NOT_RUN`.
- P1 blocked task 코드 부분 증거는 큐 4종의 `evidence_sha`/blockers에 남겼으나 status는 그대로 **`BLOCKED_DEPENDENCY`**. **구현완료율 5/30 = 16.67% 유지**, 기존 완료 코드 REQ-04/08/10/18/29만 분자 인정. 코드 존재 ≠ task 수용조건 전수 완료, P2 검증 완료 아님.
- 남은 핵심 막힘: `MLA-001 BLOCKED_PROVENANCE`(EAI/AX 원본 이식 불허), `MLA-003 F18 SECURITY_HOLD`, `MLA-009` protected owner signer 미구현, 실제 OS isolated trusted runner/P2 증거 부족. 최신 큐 `first_ready=[]`; High 최종설계·의존성 승인 전 **임의 READY·P2 해제·main 병합/Production/원본 쓰기 없음**. 비밀/.env/고객자료/유료 API/외부 전송 없음.
