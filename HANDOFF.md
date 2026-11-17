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

# My Local AI — 2026-11-17 KST High V1.1 설계 변경 인수인계 (최신 설계, 기존 구현 이력 보존)

1. **목표·기술·확정 범위:** 제품 독립 Controller + AX Dev Factory 유래 로컬 Qwen/OpenCode + 선택 EAI 분석 advisor + **선택적 Hydrogen API 병렬 독립 BE/FE 코딩 워커**. Python3.11/SQLite/Windows11 GTX1050Ti 16GB, 무료·오프라인 기본. 외부 API가 필수 의존성 아님.
2. **완료 변경:** \`FINAL_BLUEPRINT H\` 및 \`DETACHABLE_MULTI_MODEL_WORKERS\`에 3개 설계안 비교/ProviderPort/scheduler/isolated worktree/F18/circuit/quota/fallback/DB·FE/API 계약/12작업 합성 비교 수용 반영. 선택형 \`OPTIONAL_PROVIDER_TASK_QUEUE.json\` 8개(EXT-HYD-01..08) 생성. 기존 AGENTS, PHASE_GATES, REQUIREMENTS, ARCHITECTURE, SECURITY, INTEGRATION, ACCEPTANCE, RUNBOOK 및 branch policy에 일관 참조 추가. **제품 구현 코드는 이번 변경에 포함되지 않음**.
3. **테스트:** GitHub 문서/커밋 확인만. Python·전체 CI·Windows·실 Qwen/Hydrogen·API/쿼터·비밀 차단 실험·24h/진짜 F18 경계·독립 감사 모두 이번 변경에서 \`NOT_RUN\`. 기존 dev의 합성 PASS를 새 설계 검증으로 승격하지 않음.
4. **진행/대기/차단:** 원래 P1 28 작업/REQ-01~30 기준선 불변, dev 최신 기록 3/30=10.00% (코드 근거 \`4bdff24d...\`, 더 최신 코드가 있으면 실제 소스 확인). 기존 P2 \`LOCKED\`; F18 \`SECURITY_HOLD\`. EXT-HYD-01..07 설계/의존성과 구현 범위 승인 대기, EXT-HYD-08 라이브 API는 명시적 owner GO 전 \`BLOCKED\`.
5. **오류/대안:** 무료 Hydrogen을 필수 엔진으로 강제하거나 각 도구별 분산 연동하면 제품 중단·요금/비밀 정책 분산. 채택안은 common ProviderPort와 0원 비용/데이터 guard. 무료 소진 429/유료/키 없음/OFF이면 queue checkpoint/lease fencing, 로컬 Qwen 재배정 후보. Qwen 불가 시 HOLD. 웹 Instant는 별도 사람이 진행하는 lane이며 자동 API 실행 가능하다고 주장하지 않음.
6. **repo/branch/SHA:** \`hibi89/my_local_ai@design/final-blueprint-v1\` (이 인수인계 편집 직전 설계 HEAD \`a2219d0218b4909477265ecf46c5cf49af3402e7\`; 이 파일 커밋 후 최종 SHA는 반드시 GitHub 재조회). 2026-11-17 확인 \`dev/instant-implementation-v1@e6af762a5d4e7f61d18fee1ae2ba55df423cc443\`, \`main@960621d6207e6beb22a7e9480e524988196f3d44\`. 원본 EAI/Freelancer untouched.
7. **Production/환경:** 로컬 도구 설계만, 배포·고객 환경·실 GPU/RAM/유료 API 미적용. LIVE HYDROGEN account tier/쿼터·실모델·SDK tool calling \`UNVERIFIED\`.
8. **원본·백업/인증:** 원본 Git 이력 불변, 새 문서 commit으로 rollback 가능. 고객/개인 자료·비밀·.env/GitHub 토큰 0 업로드. DB migration/OS 권한/실 테스트 수행 안 함. \`remote_enabled=false\`, network deny, spend cap 0 유지.
9. **다음 READY·완료 기준·승인:** Instant는 개발 브랜치 기존 안전 P1 큐를 계속 수행. High는 선택형 큐 EXT-HYD-01 mock contract부터 정확 source SHA·허용 경로·타 작업 충돌 없는 계획을 별도 인수한 뒤 착수 가능. dev 동기화 시 설계 docs만 신중하게 적용하고 기존 dev STATUS/큐/코드를 통째로 덮어쓰지 않는다. 원격 송신·계정/비용·GitHub PR/권한/원본·Production·main은 **별도 사용자 GO 필수**.
10. **갱신·범위·기준:** 2026-11-17 KST, \`design/final-blueprint-v1\` 설계 문서만 실제 반영. 구현/검증률 추가 상승 0, 공식 검증완료율 \`UNASSESSED\`, Hydrogen 실제 운용 \`NOT_RUN\`. 최종 설계 브랜치 SHA는 반드시 재조회하고 dev는 실제 최신 HEAD를 다시 읽는다.
