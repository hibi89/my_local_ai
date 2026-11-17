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
