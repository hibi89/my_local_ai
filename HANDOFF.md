> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

> **[PRODUCT IDENTITY LOCK · OWNER CLARIFICATION · 2026-11-17]** `my_local_ai`는 **EAI의 후속 버전/확장판/완성판이 아니다.** EAI는 선택적으로 재사용할 알고리즘·CPU 분석·도구의 **기술 제공원**일 뿐이다. `my_local_ai`의 고유 목적은 **로컬 모델로 소프트웨어 구현을 지속 자동화하는 개인용 개발 시스템**이며, 정책·스케줄·실행/검증 게이트·진척 기준은 `my_local_ai`가 자체 소유한다. 원본 EAI ADR-0002(Qwen INPUT-only)는 EAI 원본의 아키텍처 지침이지 `my_local_ai`의 코딩 워커 사용 제한이 아니다. EAI 전체 13개 목표·자체 모델 연구의 100% 완료는 `my_local_ai`의 필수 조건이 아니다. 자세한 내용 `docs/PRODUCT_IDENTITY.md`. **P1 구현 우선/P2 검증 잠금 정책은 그대로 유지.**

# My Local AI — High 통합 최종설계 신규 채팅 인수인계 (2026-11-17 KST)

1. **목표/기술:** My Local AI는 EAI의 후속판이 아닌 독립 개인용 로컬 자율 소프트웨어 개발 엔진. 자체 Controller/승인·작업 큐 + 선택적 EAI 유래 분석 기술 + AX Dev Factory Qwen/OpenCode 코딩·격리/복구 참조. Windows 11 Pro / GTX1050Ti / 16GB. 무료·오프라인 우선, 사용자 승인한 큐의 24h 자동작업 지향.
2. **완료·근거:** EAI↔My Local AI 제품 정체성/정책 혼동을 분리 설계로 정정. 빈 새 PUBLIC repo main 최초 README 초기화. `design/final-blueprint-v1`에 High 요구 32개/아키텍처/SQLite/API/신뢰 경계/수용표/30개 원자큐+5개 첫 READY 설계. **제품 코드 미구현**. EAI/AX 원본을 마이그레이션하지 않음.
3. **테스트:** GitHub 문서 생성·파일 확인 별도; 실제 Python/CI/Windows/실 Ollama/OpenCode/실기기/24h: NOT_RUN. 과거 EAI/AX CI 통과는 새 repo 증거 아님.
4. **상태:** P0 High 설계 후보, 사용자 최종설계 승인 대기. 구현률 UNASSESSED, 공식 검증률 UNASSESSED, REAL-USE HOLD, RELEASE HOLD. F18 독립검증 신뢰 경계 CRITICAL HOLD.
5. **위험/실패/대안:** A EAI 단독 후 병합 / B 두 repo 런타임 결합 / C 새 repo에 provenance pinned 선별 이식 비교 후 C 선택. F18 게스트가 PASS 위조 가능하므로 trusted reviewer 없으면 승격 금지, 위험한 host fallback 금지.
6. **GitHub:** `hibi89/my_local_ai@design/final-blueprint-v1`, 정확 HEAD는 GitHub에서 재조회. main baseline `960621d6207e6beb22a7e9480e524988196f3d44`. EAI 참조 `5186cb1aa...`, AX `5ab9418047...`. 개발 목표 브랜치 `dev/instant-implementation-v1`. 
7. **운영/Production:** 로컬 제품, Production URL/Vercel 미적용. 사용자 Windows 설치·Sandbox 가용성/기기 실모델 미확인, 외부 API/paid OFF.
8. **원본/보안/복구:** EAI/AX 원본 repo/main 보존, 고객 DB/.env/모델/프롬프트/토큰 Git 업로드 0. Git history로 문서 rollback; 향후 SQLite·실기기 백업은 설계만.
9. **다음 READY:** 승인 시 MLA-001(원본/라이선스), MLA-002(contract schemas), MLA-003(F18 threat/reviewer), MLA-004(synthetic tests/CI), MLA-005(local benchmark schema)를 묶어 수행. 그 후 각 depends_on/allowed_paths/acceptance/safety_checks로 다음 작업. 코드/수용 SHA 없으면 VERIFIED 금지.
10. **갱신:** 2026-11-17 KST; 설계 기반 검토/문서 저장만, 실기기·모델·독립 감사 NOT_RUN. 최신 디자인 docs/FINAL_BLUEPRINT·REQUIREMENTS·INSTANT_TASK_QUEUE가 작업 정본이며 이 HANDOFF는 이전 정책을 덮지 않는다.

---

# 2026-11-17 KST P1 구현 실적 — 최신 인수인계 (위 P0 이력보다 우선)

1. **목표·확정 요구:** My Local AI 독립 고유 Controller + 선택 EAI advisor + 격리 코딩 워커. REQ-01~30 구현 분모, REQ-31/32 후행 감사/GO. P1 구현 우선, P2 전체 검증 잠금 유지.
2. **완료 코드:** `MLA-002` TaskSpec/PlanSpec/계획 SHA256·DAG·경로·예산·scope claimed 승인 구분; `MLA-004` Python 3.11 합성 CI scaffold; `MLA-005` 명시적 SYNTHETIC 모델 성능 placeholder 및 테스트; `MLA-001` 원본별 5개 blob SHA manifest+오프라인 읽기 전용 감사 코드 (원본 이식은 BLOCKED_PROVENANCE). 실제 source 최종 SHA `7814996f9ee0f8e6243be38a5a63284665227c85`.
3. **테스트 명령·증거:** `python -m compileall -q src scripts tests`; `PYTHONPATH=src python -m unittest discover -s tests/unit -p 'test_*.py' -v`; GitHub Actions `44003823329` at `7814996...` **21 PASS / 0 FAIL / 0 SKIP, syntax PASS**. 직전 `44003728366` **FAIL** (64자리 plan SHA vs 40자리 Git SHA), 수정으로 재검증 성공. P2 풀 CI/Windows/실모델/24h **NOT_RUN**.
4. **진행·차단:** 소스 구현 완료 3개 P1 task/28개 (`MLA-002/004/005 IMPLEMENTED_UNVERIFIED`). **구현완료율 1/30=3.33%** (`REQ-04` 전체 스키마 코딩 완료로 산입). `MLA-001` provenance/라이선스 **BLOCKED**; F18 independent reviewer **SECURITY_HOLD**. P2 `LOCKED`, 공식 검증률 `UNASSESSED`, 실사용 `HOLD`.
5. **오류·시도·대안:** 1회 synthetic CI 실패의 원인은 SHA 유형 혼동; `task.plan_sha`는 SHA256 64 hex, `source_sha`는 Git commit 40 hex로 수정. EAI/AX 루트 LICENSE 부재 → 권리 미확정; 원본 복사 금지, 별도 자체 코드 구현.
6. **저장소·브랜치·SHA:** `hibi89/my_local_ai@dev/instant-implementation-v1`, 코드 `7814996...`; 큐 진행 기록 `acaf61e1195168220d349e03ca5946933cf1a542`; 단계 잠금 `bac35a249a081a4098ab5416c6ae35e1f54d77ae`. HEAD는 재개 시 재조회. `main`, EAI, AX Dev Factory 원본 변경 없음.
7. **Production/환경:** 로컬 개발 도구, Production/Vercel 없음. GitHub Actions Ubuntu Python3.11 합성 테스트만 실행; 실제 사용자 Windows11 GTX1050Ti/Ollama/Qwen/OpenCode **NOT_RUN**.
8. **보안·권한·복구:** 공개 repo에 비밀/고객 DB·모델 가중치/개인 경로 업로드 없음. Git 이력 보존; 원격 PR/merge, OS startup, 유료 API, 외부 전송/실운영 권한 별도 GO. F18 self-receipt 절대 신뢰 금지.
9. **다음 READY 및 인수 기준:** `MLA-003` F18 fail-closed 구분, `MLA-006` CLI dry-run 및 `MLA-007` SQLite 합성 기반. `MLA-001`은 출처/라이선스 해결 전 원본 이식 불허. 추가 REQ 전체 코딩 경로 완성 시에만 완료 분자 증가. 전체 CI 수동 반복 대기 금지, 위험 경계 즉시검사는 유지.
10. **갱신·검증 범위:** 2026-11-17 KST. 소스 근거 `7814996...`, PASS는 `44003823329` synthetic scope. P2 공식 검증·보안 OS 경계·운영/출시 `NOT_RUN/HOLD`. 후속 채팅은 이 문단 및 실제 HEAD/현행 AGENTS·PHASE_GATES를 우선하며 구형 P0 `코드 미구현` 스냅샷을 그대로 신뢰하지 않는다.

---

## 2026-11-17 KST 최신 구현 인수인계 — P1 10.00% (위 3.33% 이력 이후)

1. **목표/확정 요구:** My Local AI 자체 Controller 중심, EAI advisor 선택형, 원본 소스 권리 확인 후만 이식. P1 REQ-01~30, P2 검증 별도 LOCKED.
2. **코드 기능:** MLA-007 SQLite 소유 파일 제한/백업/WAL/FK, MLA-006 CLI read-only doctor/plan validate/status/queue, MLA-010 순수 DAG/READY 후보 큐, MLA-003 F18 계약/적대 fixture. 이전 MLA-001/002/004/005 유지.
3. **실제 실행 테스트:** GitHub Actions `44004810339` 코드 SHA `4bdff24db9d2a0a3ab37036225df1ff0aa6fe846`. Python 3.11 compile PASS; unit **41/41 PASS**, synthetic F18 security **5/5 PASS**. 전체 P2 CI/Windows 실기기/실 Ollama/Qwen/OpenCode/24h **NOT_RUN**.
4. **진행/차단:** P1 완료 REQ **3/30=10.00%** (REQ-04/08/18, 검증 전 코드 구현만); 구현 task 6/28 SOURCE_IMPLEMENTED_UNVERIFIED; MLA-003 PARTIAL F18 HOLD, MLA-001 BLOCKED_PROVENANCE. REQ-28은 CLI 일부만, 완료로 산입하지 않음.
5. **위험/대안:** F18 guest forged PASS/receipt는 증거 아님, 독립 OS reviewer 필요; 고객 DB·원본 손상 방지를 위해 SQLite APP_ID 거부/backup. EAI/AX 원본 루트 LICENSE 미확인 상태이므로 소스 이식 유보.
6. **브랜치·정확 SHA:** `hibi89/my_local_ai@dev/instant-implementation-v1`. 작업 코드 SHA `4bdff24db9d2a0a3ab37036225df1ff0aa6fe846`, 큐·상태 문서 커밋은 최신 HEAD 재확인. Main EAI AX 무변경.
7. **Production/환경:** 배포 미적용, 사용자 PC 사용 불필요. 합성 GitHub Actions Ubuntu Python 3.11만 PASS.
8. **보안·복구:** 원격 publish/OS startup/유료/고객원본 사용 없음. 미검증 코드 자동 승격 금지, SQLite 임시 데이터 기반 테스트뿐. P2 LOCKED/검증률 UNASSESSED.
9. **다음 READY:** MLA-009 owner GO/consent revocation, MLA-011 1 model lock/resource fencing, MLA-021 로컬 상태 보드. MLA-010 pure scheduler 실제 dispatch/검증 연동은 MLA-019 등 후행.
10. **갱신 기준:** 2026-11-17 KST, `44004810339` synthetic scope, F18 실제 OS 검증 NOT_RUN. 위 P0 및 구현 3.33% 스냅샷보다 최신 실행 이력을 우선.

---

## 2026-11-17 KST 최신 P1 인수인계 — 구현 13.33%, 브랜치 보존

1. **목표/설계:** My Local AI 자체 Controller + AX-유래 로컬 Qwen 기본 워커, 선택형 EAI advisor, 별도 Hydrogen OFF-by-default provider lane (High V1.1). P1 REQ-01~30/28 원자 작업; EXT-HYD-01..08은 별도 선택형 설계이며 필수 분모 불변.
2. **실제 변경:** High SHA `0de11f63c3ae795e1ed9ec1ec016ac38b864e1d4`에서 12개 관련 설계 문서만 dev에 동기화; STATUS/HANDOFF/queue/gates/source 이력 덮어쓰기 금지. MLA-009 별도 owner claim 검증·live revocation check, MLA-011 모델 OS lock/fencing·budget, MLA-021 redacted loopback read-only dashboard와 HTTP synthetic smoke 구현. 핵심 코드 SHA `75d441ed163b3d91b271653c5e3fc5dae40ece96`.
3. **테스트 명령/증거:** Python3.11 `compileall`, `PYTHONPATH=src python -m unittest discover -s tests/unit -p 'test_*.py' -v`, 별도 `tests/security` 동일. GitHub Actions `44008410953` SHA `75d441ed163b3d91b271653c5e3fc5dae40ece96` **54 unit PASS + 13 synthetic security PASS**, syntax PASS/0 FAIL. Browser/Playwright `DEFERRED_TO_P2`, 실 Windows/실 Qwen/OpenCode/24h/F18 독립 OS reviewer `NOT_RUN`.
4. **구현상태/차단:** REQ-04/08/18/29 코드 구현 후보 **4/30=13.33%**. REQ-07는 보호된 실제 owner signer 미연결, REQ-09는 모델 executor 통합 미완 → 둘 다 분자 제외. P1 작성 후보 task **8/28**. MLA-001 provenance 권리 보류, MLA-003 F18 security HOLD, MLA-009 partial signer HOLD. P2/공식 검증률 `LOCKED/UNASSESSED`, 실운용/출시 HOLD.
5. **실패·개선:** source/plan approval 자체 선언, 타인 grant/철회/만료/다른 scope·SHA는 합성 부정 테스트 차단. OS lock 초기화 동시 시작 경합 위험을 수정하여 잠금 획득 *후* epoch 0→1 기록. 실제 Windows 파일 잠금, signer ACL 검증은 P2 보류. UI no-CORS; GET only, GET/HEAD Host+Origin 검증, POST/OPTIONS 405.
6. **GitHub:** `hibi89/my_local_ai@dev/instant-implementation-v1` 작업 코드 SHA `75d441ed163b3d91b271653c5e3fc5dae40ece96`, 본 상태/인수 기록 커밋 이후 HEAD는 재조회. `main` / 원본 EAI / AX 변경 없음.
7. **Production/환경:** public GitHub 소스/합성 Actions만, Windows11 GTX1050Ti 실실행/실기기/유료서비스/Production 미적용. read-only server는 코드상 존재하나 자동 실행/OS 등록 없음.
8. **원본·비밀·복구:** 고객자료/.env/키/모델 가중치 업로드 없음. owner HMAC 키의 실제 저장/발급 절대 GitHub 금지, 소스는 별도 OS protected trust root 전까지 HOLD. HMAC test key는 공개 합성 fixture 뿐이며 운영 키가 아님. main/원본 불변.
9. **다음 READY:** `MLA-012` Ollama loopback-only connector/local coder availability and failure HOLD; 계획된 MLA-013 OpenCode runner, provider 사전 승인/비밀/경계 확인. Hydra 확장 8개는 선택형·범위 GO 전 구현 큐에 자동 편입 금지.
10. **갱신:** 2026-11-17 KST. 설계 HEAD `0de11f63...`, dev 코드 `75d441ed163b3d91b271653c5e3fc5dae40ece96`, 실 PASS 근거 Actions `44008410953` synthetic. P2 검증·현장/보안/브라우저/독립 감사가 완료됐다고 주장하지 말 것.

---

# My Local AI — 2026-11-17 KST 모바일 `ㄱ` 다음 채팅 인수인계 (최신)

1. **임무/범위 고정:** `hibi89/my_local_ai`의 P1 BE/FE 실제 구현만 수행. 제품은 독립 로컬 자율개발 Controller + 로컬 Ollama/Qwen/OpenCode + optional EAI advisor. Hydrogen provider는 V1.1 설계 확장/별도 `EXT-HYD-01..08` 큐로 기본 OFF, 외부 API·데이터 송신 별도 승인.
2. **변경 완료:** 브라우저/Playwright/시각/a11y·반응형·Console/Network 검증을 P1 `MLA-019/021/025`에서 P2 `MLA-V007`로 큐 수준 명시 이관. P1에서는 FE/BE 코드·화면·API·테스트 fixture 및 syntax/type/국소 smoke 작성 유지. CLI-only는 브라우저 비대상.
3. **검증:** 최신 코드 고정 SHA `75d441ed163b3d91b271653c5e3fc5dae40ece96`; Actions `44008410953` Python 3.11 syntax PASS, 54 unit PASS, 13 synthetic security PASS. 실제 Playwright/브라우저·Win11/Ollama/OpenCode/24h/F18 독립 reviewer 전수 `NOT_RUN`. 이 문서/큐만 변경한 SHA의 CI 실행은 별도 확인.
4. **완료·진척:** 구현완료율 **4/30 = 13.33%** (REQ-04/08/18/29 코드 구현 후보), P1 코드 작업 8/28 `IMPLEMENTED_UNVERIFIED`. 공식 검증완료율 `UNASSESSED`; P2 `LOCKED`. `MLA-001` provenance/라이선스 차단; `MLA-003` F18 신뢰 경계 HOLD; `MLA-009` protected signer 미구현.
5. **실패/차단/대안:** EAI·AX 고정 SHA 원본 루트 LICENSE 미확인→원본 코드 복사 없이 자체 구현 계속. F18 코딩 모델의 위조 PASS/영수증 신뢰 금지; 사용자 PC 보안 경계 미실증→중요 원본 자동 승격 HOLD. GitHub Actions 합성 테스트는 OS·브라우저 P2 증거 아님.
6. **repo/branch/SHA:** `hibi89/my_local_ai@dev/instant-implementation-v1`; 가장 최근 제품 소스 SHA `75d441ed163b3d91b271653c5e3fc5dae40ece96`. 최신 HEAD는 GitHub에서 재조회. 설계 브랜치 `design/final-blueprint-v1` 기준 `0de11f63c3ae795e1ed9ec1ec016ac38b864e1d4`(새 커밋 존재 시 재조회). main·EAI·AX 원본 불변.
7. **Production/환경:** 로컬 개인용 대상, 배포/Production 미적용. 테스트는 GitHub Actions 합성 환경만 실제 PASS. 사용자 Windows11 GTX1050Ti/16GB Windows 실기기 없음, 유료 결제·외부 전송·키 업로드 없음.
8. **백업/권한:** Git 이력 원본 보존, .env/키/고객자료/모델 가중치 public repo 업로드 금지. 모델/Hydrogen/remote PR/OS startup/상용/고객 원본 파괴·Production 별도 GO. 원본 EAI/AX source read-only.
9. **다음 READY/완료기준:** 다음 `ㄱ`은 최신 HEAD→`AGENTS.md`→`HANDOFF.md`→`STATUS.md`→`REQUIREMENTS.md`/Final Blueprint→P1 큐/실제 코드 확인 후 `MLA-012` 로컬 Ollama loopback provider부터 실제 구현; 가능한 독립 READY 묶음. 변경 SHA·문법/국소 보안 체크 근거, REQ 분자 엄격 산정. 전체 CI 수동 대기·실브라우저 검사 반복 금지.
10. **갱신:** 2026-11-17 KST, 브라우저 검증 이관은 설계·큐 **작업 분류 수정**, 코드 기능 진척 0. P2 브라우저 `MLA-V007`는 High 100% 후보 승인+정확 SHA 게이트 전 `BLOCKED_BY_P1_GATE`. 최신 기준 HEAD와 실제 CI는 다음 채팅에서 확인.

---

## 2026-11-17 KST P1 MLA-012 실구현 완료 — 다음 모바일 재개 인수인계

1. **목표/기술:** 독립 My Local AI Controller + 로컬 Ollama/Qwen/OpenCode worker, EAI advisor 선택형. P1 REQ-01..30 분모 30, P2 별도 LOCKED. High V1.2 경험 기반 학습은 **설계만**, 별도 optional queue/기본 P1에 미포함.
2. **변경/기능:** `MLA-012`의 Ollama provider와 strict loopback endpoint policy, hostile network/secret/model absence synthetic tests 구현. 생성 기본 OFF, local Qwen allowlist, no automatic pulls, model lock+budget, output untrusted. 새 코드 `1d29951f5a0b0fdbb0585a98b523842a917df6e8`.
3. **테스트:** Python compile + isolated mocked 10/10 security PASS; GitHub Actions `44012906535` at exact `1d29951f5a0b0fdbb0585a98b523842a917df6e8` status **SUCCESS** (syntax/unit/security synthetic). 개발 컨테이너에서 기존 lock/budget은 test stub 사용, **Actions에서는 repository 실제 모듈 실행**. Windows/Ollama/OpenCode real, browser/Playwright, OS F18 independent review, 24h: `NOT_RUN`.
4. **상태:** 구현완료율 **5/30 = 16.67%**, 완료 코드 REQ-04/08/10/18/29. REQ-23 등은 부분이며 분자 제외. P1 code task MLA-012 `IMPLEMENTED_UNVERIFIED`, P2 `LOCKED`, 공식 검증률 `UNASSESSED`, 실사용 `HOLD`.
5. **위험/대안:** F18 guest-self-receipt CRITICAL HOLD, protected owner signer 미연결, provenance/license 해결 전 원본 코드 이식 금지. Python connector의 literal-loopback 제한은 **OS 전체 네트워크 격리 실증 아님**. 실모델 태그/성능 미확인, 설치/다운로드 금지. 독립 READY 계속 처리.
6. **repo/branch/SHA:** `hibi89/my_local_ai@dev/instant-implementation-v1`; 신규 소스 commit `1d29951f5a0b0fdbb0585a98b523842a917df6e8`. STATUS/HANDOFF/queue/gate 기록 commit 이후 HEAD는 실시간 재조회. `design/final-blueprint-v1` 재조회 시 `e08e127dc372023d4ece477b176b99ac3b9d6412`, 이 설계 브랜치의 구형 소스/queue는 dev에 통째 병합하지 않는다.
7. **운영:** 로컬 Windows 11 PC 실기기 시험 `NOT_RUN`, Production/유료/클라우드/remote PR/자동 시작 `NOT_APPLICABLE or HOLD`. Python 합성 GitHub Actions만 성공.
8. **원본/보안:** .env/고객 자료/토큰/모델/비공개 소스 GitHub 미반영. 로컬 HTTP 경로 `/api/tags`, `/api/generate` 외 차단. 사용자 승인 없는 OS 권한·원격 사용·main 병합 금지. 변경 취소는 기존 Git history에서 가능.
9. **다음 READY:** `MLA-013` OpenCode worker 실행계약/권한/argv·environment·격리 fail-closed, `MLA-020` local benchmark **하네스만**; dependency/allowed_paths 재확인 후 독립 작업 묶음. 완료 후보의 정직한 REQ 단위 산정 및 고위험 국소 검사 필수.
10. **갱신/검증 경계:** 2026-11-17 KST, source SHA `1d29951f5a0b0fdbb0585a98b523842a917df6e8`, GitHub Actions `44012906535`; P2/Windows/브라우저/실 OS F18는 미검증. 다음 `ㄱ`에서 최신 HEAD→AGENTS→queue→원본 코드 후 실제 구현 수행.

---

## 2026-11-17 KST P1 최신 실행 인수인계 — MLA-013+020

1. 임무/기술: My Local AI 독자 로컬 Controller+Qwen/Ollama/OpenCode P1. 선택형 Hydrogen/Experience는 설계만, 기존 REQ 분모 30 불변.
2. 완료 작업: MLA-013 security-gated OpenCode launch request/policy/attested sandbox port with guest self-PASS refusal (SHA `748caecf30e680b2794fde287bbf674801c88079`), MLA-020 mocked local benchmark harness/P2 real-call gate/evidence schema (SHA `63995bfaa0d425d3b361cc9462bbdf37b8b63f5c`). 새 소스·테스트·문서 5파일만 추가.
3. 테스트: GitHub Actions `44014035939` @ `63995bfaa0d425d3b361cc9462bbdf37b8b63f5c` syntax PASS / unit 54 PASS / security 32 PASS. `tests/integration/test_real_model_gate.py`는 **작성만, NOT_RUN**; actual OpenCode/Ollama/Windows/independent F18/24h/Playwright NOT_RUN. 전체 P2 수용은 미실시.
4. 구현완료율 **5/30 = 16.67% (변동 없음)**. MLA-013+020은 각각 `IMPLEMENTED_UNVERIFIED` 코드 후보, REQ-11/24/27 전수 구현 조건은 sandbox·전체 계측/실통합 부재로 완료 분자 제외. P1 code task 11/28 작성후보. P2 LOCKED, 공식 검증률 UNASSESSED.
5. BLOCKER: F18 독립 OS 격리 및 forged receipt CRITICAL HOLD; owner protected signer/GO issuance HOLD; EAI/AX 원본 라이선스 권리 불명 BLOCKED_PROVENANCE. OpenCode native permission policy만으로 실제 host confinement 불가. `run_in_sandbox`는 기본 no-run, 외부 attested runner 없으면 HOLD.
6. Repo `hibi89/my_local_ai`, branch `dev/instant-implementation-v1`; 소스 SHA `63995bfaa0d425d3b361cc9462bbdf37b8b63f5c`; 상태/큐/문서 갱신 이후 HEAD 재확인. Design `design/final-blueprint-v1` last observed `e08e127dc372023d4ece477b176b99ac3b9d6412`.
7. Windows device/실모델/배포: NOT_RUN/HOLD. Production 미적용. 합성 CI 통과만 확인.
8. 비밀/원본/보안: no external API, no model pull, no main merge, no remote PR/permission changes. 원본 EAI/AX 미수정. Model prompt/output 원문은 benchmark evidence에 저장하지 않음.
9. 다음 작업: 큐 `first_ready=[]` (2 READY 소진). 기존 `MLA-001` provenance·LICENSE 블록 및 `MLA-003`/009 F18/trust-root 블록을 High 설계 판단과 연결한 뒤 실제 의존성 해소 및 MLA-014 등 다음 READY 수행. 새 `ㄱ`마다 GitHub 최신 정책/HEAD와 blocked dependencies 확인; 사용자 PC 작업 금지.
10. KST 2026-11-17, exact evidence sources 위 2 SHA, P1 소스 후보, P2 독립 검증 미실시. 과거 문서의 구형 READY 우선순위 대신 실제 최신 큐를 사용.

---

## 2026-11-17 KST P1 9차 모바일 `ㄱ` 인수인계 — MLA-001 provenance deep audit

1. 임무: `hibi89/my_local_ai` 자체 로컬 Controller 중심 P1 소스 구현. EAI/AX 원본 읽기 전용, Main/Production/Hydrogen 외부 API 변경 금지.
2. 완료: pinned Git trees EAI(191 items, tree `0144655d7e7fd837e9f5efef7d91d5c489467f48`)/AX(123 items, tree `abbf9dd919f91f1b6e9566e7d582988c6ba32b73`) complete verified; source candidates 5 blobs anchored; provenance manifest, offline audit and adversarial tests 강화. 변경 소스 SHA `ffea825ba253b2b12246d3c36f63fb2642215e1d`.
3. 테스트: GitHub Actions `44014692103` (exact `ffea825ba253b2b12246d3c36f63fb2642215e1d`) SUCCESS — Python syntax PASS, unit 56/56 PASS, security 32/32 PASS; Windows/Ollama/OpenCode/OS F18/24h/Playwright/권리 법적 승인 NOT_RUN.
4. 진척: 구현완료율 **5/30=16.67%**, REQ 5개는 기존 코드 완료 후보, 신규 REQ completion 0. MLA-001 상태 `BLOCKED_PROVENANCE`; code task candidate count 변화 없음(11/28 기존).
5. 장애/대안: pinned source full tree에서 LICENSE/NOTICE 등 관례적 파일명 0건, 실제 재사용권/제3자 통합 라이선스 미확정. 선택지 A 독립 새 코드(clean-room)로 재구현 시 HIGH 설계·계약/큐 의존성 변경 명시 승인 필요. B 소유/제3자 권리 문서 확인 후만 원본 이식. F18 독립 OS 신뢰 경계와 protected owner-signer 계속 HIGH/CRITICAL HOLD.
6. Repo/branch: `hibi89/my_local_ai@dev/instant-implementation-v1`; 감사 소스 SHA `ffea825ba253b2b12246d3c36f63fb2642215e1d`. 현재 문서 증거 갱신 이후 HEAD는 다시 조회. 설계 `design/final-blueprint-v1` 마지막 확인 `e08e127dc372023d4ece477b176b99ac3b9d6412`, 구형 queue/STATUS 덮어쓰기 금지.
7. Runtime: 개인용 Windows 앱 대상, 실제 원격 배포/모델/하드웨어 평가 NOT_RUN; PUBLIC repo 정책·고객 원본·키 보호.
8. 원본/보안: EAI 현재 브랜치 관측 SHA `af57af08e0d71fb656c76be241944e8cf232a57a` (기존 pinned SHA와 다름), AX HEAD 고정 일치, 원본 쓰기 0. SHA/license scan만으로 라이선스 승인하지 않음; Git 이력 롤백 경로 보존.
9. Next: P1 queue `first_ready=[]`. High 설계 판단 전 MLA-008/014 의존성 강제 READY 전환/외부 소스 복사 금지. 차단 없는 실제 작업이 생기면 새 `ㄱ`에서 dependency·allowed_paths 확인 후 구현. F18 및 signer는 별도 불변 안전 게이트.
10. 갱신 2026-11-17 KST, exact evidence source `ffea825ba253b2b12246d3c36f63fb2642215e1d`, Actions `44014692103`. P2 `LOCKED`, 검증률 `UNASSESSED`, 실사용 `HOLD`.

---

# 2026-11-17 KST — 긴 묶음작업 새 채팅 인수인계 (현재 최신)

1. **목표/기술:** My Local AI 독립 Controller·Qwen/Ollama/OpenCode 개인용 로컬 자율개발; optional EAI advisory/Hydrogen/Experience는 기존 P1 분모 무변경. P1 30 REQ, P2 8 전체 검증 LOCKED.
2. **코드 변경:** MLA-009 HMAC plan 승인 범위를 LOCAL_PLAN으로 제한, high-risk reusable grant fail-closed; SQLite DB main inode pin + WAL/SHM sidecar safety + fail-closed replacement detection (`src/my_local_ai/contracts/approval.py`, `state/consent.py`). MLA-013 OpenCode `run_in_sandbox`가 controller trusted_task/path/model/env/argv와 request를 재계산 대조. MLA-003 F18 forged/replayed receipts·guest VERIFIED DAG 범위 합성 거부. MLA-004/020 P1 benchmark mock-only CI smoke 실행.
3. **테스트/증거:** 최신 코드+CI SHA `ad224cfb59d30ed8c87bfc524976c02662ed7592`, Actions `44015752835`: Python3.11 compile PASS, 56 synthetic unit PASS, 8 mock benchmark integration PASS, 43 synthetic security PASS, FAIL 0. 중간 `44015195788` SQLite WAL stale-approval 재현 FAIL→`4d665297` 수정 PASS; `44015580712` overstrict SHM 생성 검사 FAIL→`d0cc3a60` 수정 PASS. 실제 Windows/Ollama/OpenCode/F18 protected OS/24h/real browser/independent audit NOT_RUN.
4. **진척/잔여:** 구현완료율 **5/30=16.67%**, 코딩 완료 후보 MLA-002/004/005/006/007/010/011/012/013/020/021=11/28. 고위험 강화는 과장된 신규 완료 REQ 0. P2 `LOCKED`, 공식 검증률 `UNASSESSED`, 실사용 `HOLD`.
5. **오류/복구:** WAL 사이드카를 재사용한 파일 교체 시 stale approval 허용 회귀를 테스트로 재현·고정 파일 identity 대조로 해결. SQLite 정상 SHM 생성까지 거부하던 검사 수정. 원본/고객 데이터 미수정. 자동 원본 적용은 계속 금지.
6. **repo/branch/SHA:** `hibi89/my_local_ai@dev/instant-implementation-v1`, 최신 기술코드 SHA `ad224cfb59d30ed8c87bfc524976c02662ed7592`; 현 STATUS/HANDOFF+큐 갱신 커밋 이후 실제 HEAD는 재조회. 최종설계 브랜치 `design/final-blueprint-v1` 관측 SHA `e08e127dc372023d4ece477b176b99ac3b9d6412` (전수 read-only 확인 필요).
7. **운영/Production:** 로컬 개인용, 실제 Windows 검증/모델 벤치마크/OS 격리 NOT_RUN. Production 없음. 실제 비용 0(유료 호출 안 함).
8. **보안/원본:** EAI/AX 정확 source SHA/license 미확정, **MLA-001 BLOCKED_PROVENANCE**. F18 코드 생성 게스트 서명/자가 PASS 불신, owner protected signer 미연결. remote, customer, paid, OS 권한, main 변경 금지. Github 코드·정책/합성 테스트 외 비밀 업로드 금지.
9. **다음 READY/사용자 승인:** 현재 큐 `first_ready=[]`. 핵심 차단 `MLA-001` provenance, `MLA-003` F18 trust boundary, `MLA-009` owner identity. High가 `MLA-008/014` clean-room 신규 자체 코드 vs original source import 설계·의존성/allowed_paths·acceptance를 명시적 판단하고 READY 할당해야 구현 흐름을 계속할 수 있음. 임의 status/phase unlock 금지. 사용자 PC 작업 요구 불필요.
10. **기준/검증:** KST 2026-11-17, exact SHA `ad224cfb59d30ed8c87bfc524976c02662ed7592`, run `44015752835`. User mobile `ㄱ` 반복 시 여러 독립 READY 묶음, 국소 보안 즉시검사 후 소스/테스트/커밋·실제 SHA·완료 REQ/30 보고. 브라우저/전체 CI·실 Win11/F18/24h P2에 후행, 기존 필수 CI 유지.

---

## 2026-11-17 KST P1 10차 장시간 묶음 구현 인수인계 — 최신

1. **목표/기술:** `hibi89/my_local_ai` 독자 local Controller+Qwen/OpenCode P1; EAI advisor optional, original code not copied; Hydrogen default OFF. P1 REQ01..30 구현 후보 100% 목표, P2 별도 잠금.
2. **완료 소스:** MLA-008 Controller+advisory safe non-executing logic `a4b37009`, MLA-014 read-only Git worktree path guard `b6bb6bb4`, MLA-016 once-repair+fenced interruption `66f0a244`, MLA-015 F18 signed receipt parser/nonce/check anti-forgery `705a139d`. **총 11개 추가 코드·테스트 파일**. 직접 실행·원본 승격 없음, 원본 EAI/AX 코드 복사 0.
3. **테스트:** GitHub Actions `44016649399` @ code SHA `705a139d5ed8a3f363eb58c4c12a31e71b761542`: Python 3.11 compile PASS, synthetic unit 75/75, mock benchmark 8/8, synthetic security 61/61, total **144 PASS**. Windows/OpenCode/Ollama 실기기·독립 OS 격리·F18 실제 verifier·브라우저/24h/최종 검수 `NOT_RUN`.
4. **진척:** 최종 코드 구현완료율 **5/30 = 16.67%** (REQ-04/08/10/18/29), 전회 동일. blocked 4개 task 구현의 **부분 코드** 근거가 있어도 최종 REQ/프로젝트 100% 후보로 산입하지 않는다. 공식 검증률 UNASSESSED, P2 LOCKED, 실사용 HOLD.
5. **차단:** MLA-001 EAI/AX 출처·권리 미해결; MLA-003 F18 standalone real OS isolation/issuer 미검증; MLA-009 owner protected signer 미구현. MLA-008/014/015/016은 미완 의존성/실행기 남음. 코드만으로 OS 격리·보호된 영수증 증명 불가.
6. **Repo/branch/SHA:** `hibi89/my_local_ai@dev/instant-implementation-v1`, 최신 실제 소스 SHA `705a139d5ed8a3f363eb58c4c12a31e71b761542`; 이 HANDOFF/STATUS/큐 반영 뒤 HEAD 재조회. Design branch `design/final-blueprint-v1` 마지막 `e08e127dc372023d4ece477b176b99ac3b9d6412`.
7. **실서비스:** 개인용 로컬 Windows 목표, 현 GitHub Actions synthetic only. Production 없음, Windows owner 실모델/24h 증거 없음, 외부 전송/결제/원본 쓰기 없음.
8. **원본·보안:** 원본 비공개/고객 파일/토큰/모델 가중치 GitHub 미저장. HMAC MAC matching ≠ independent F18 PASS, all reviewer results `may_promote_git_ref=false`; privileged scopes remote/OS/paid/customer/production denied by default. Hooks/filter/ignored paths independent Git checks 추후 필요.
9. **다음 실행:** 최신 `AGENTS.md`→큐/원본→F18 안전 대조 후 실제 차단되지 않는 독립 READY 발굴. 큐 READY 0, status 강제 READY 금지. High가 clean-room 신규 코드 의존성 재배정 및 protected Windows trusted executor/owner signer 설계·실제 구현 결정; 다음 최소 실행 코드 후보는 MLA-017 atomic lease/reconcile 및 MLA-019 FE/BE 통합의 **독립 비실행 하네스** 단위, 단 큐·경로·안전 확인 후. 실 owner GO 전 실제 self-running 원본 수정 금지.
10. **갱신:** KST 2026-11-17, code SHA `705a139d5ed8a3f363eb58c4c12a31e71b761542`, run `44016649399` PASS. P1 소스/합성 evidence ≠ P2/실기기 완료.

---

## 2026-11-17 KST — P1 source-queue replan & multiple code waves completed

- GitHub target `hibi89/my_local_ai@dev/instant-implementation-v1`, initial HEAD `7909a9ce9427852485385d7f852a102f5cfa56e8`. User explicitly requested queue optimization and real code progress. Designed dual **P1 code-only** vs **original runtime/full-acceptance** dependency graphs; preserved original `depends_on`/28 tasks/30 REQs and P2 LOCKED, `operational_ready=[]`. Added automated `scripts/p1_queue_replan.py`, P1 queue tests, `docs/P1_IMPLEMENTATION_REPLAN.md`, AGENTS/RUNBOOK newest override. Runtime auth fixed HOLD across all tasks. Any original runtime dependency change, source import clearance, F18/owner scope/P2 forged GO is rejected by replan guard.
- **Wave 1:** MLA-017 lease fence/read-only SQLite crash reconcile `c792bbeaf6fd14d1415943e6398f8251b17d680f`; MLA-028 optional EAI data-only input/fallback `5ac1b6ec5ab3f8cb80c9c999c6a343aebca37e64`; MLA-030 no-egress/Git hook/prompt-injection security fixtures `9d6e63a3bf7f5fa274eb7b00e61df2e9f50c465e`.
- **Wave 2:** MLA-018 protected-ref-only CAS intent with no Git write `46f6995ea7456f77632826712247ec099aa2582e`.
- **Wave 3:** MLA-019 native Controller→read-only App/BE-FE redacted synthetic journey `5b6f5c83d2c3dae51db8a103422d952a4e58138d`; MLA-023 remote preview fail-closed `efc2f33713ed4c3af77583b2d276cf601615f12e` (initial CI exposed `../repo` injection, fixed strict repo component parsing); P1 dashboard source updated `3dda3ab28c29e6ed208babcd14e450126fd9439a` to clearly show code authoring READY vs runtime READY and protect from mismatched queue status.
- **Wave 4:** MLA-022 resource/thermal/one model supervisor with no automatic OS actions `8996b5bb56188a3fcc132f0bf87b43af9e6e6b33`; MLA-024 remote publish action-bound GO refusal `4fe0adc1b8c1e54ea358ce311c88550cd548de1a`; MLA-029 Windows F18 independent test source/evidence `a426c690d25c29c6e96fff7e2d226e23a75de51a`.
- **Wave 5:** MLA-025 owner browser/Windows E2E scenario source and P2 gate `20e81dea7abb78769a3311f378f43f7e96b9273a`. No real browser/owner Windows or 24h test executed. Acceptance evidence doc `docs/ACCEPTANCE_EVIDENCE.md`.
- **Exact latest source SHA `20e81dea7abb78769a3311f378f43f7e96b9273a`, Actions `44018595764` SUCCESS:** Python3.11 syntax PASS; synthetic unit **88/88 PASS**; synthetic integration **36/36 PASS**; synthetic security **85/85 PASS**, **209/209 PASS**. Prior remote preview traversal test failed once; patched/reverified in later latest PASS. P2 full CI/manual Windows/real model/browser/independent audit `NOT_RUN`. This CI does not imply external safety or product verification.
- **P1 work-evidence:** all **28/28** queue entries now have non-null `evidence_sha` (path/code **partial source presence only**, not 28 finished tasks). **Official implementation completion stays 5/30 = 16.67%**, completed code REQ-04/08/10/18/29, because actual Windows OS-isolated execution, owner signer issuance, F18 independent reviewer, Git worktree creation/filter/ignored checks, atomic protected CAS and several BE/FE integrations remain incomplete. P2 `LOCKED`, official verification `UNASSESSED`, real use `HOLD`.
- **Next READY_CODE_ONLY hardening** MLA-014 real disposable worktree safety/authoring, MLA-015 protected reviewer/independent issuance path, MLA-017 protected SQLite lease CAS/restart recovery. They return to code-only READY for **round 2 hardening** with original runtime `BLOCKED_DEPENDENCY` and F18/source/owner safety holds preserved. Later MLA-008/016/018 deeper full completion. No original EAI/AX copy, remote publish, main/prod merge, user device change, paid calls or private files uploaded.
