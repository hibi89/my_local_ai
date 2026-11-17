> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

# My Local AI — High 통합 최종설계 신규 채팅 인수인계 (2026-11-17 KST)

1. **목표/기술:** My Local AI 단일 개인용 로컬 자율 소프트웨어 개발 엔진; EAI CPU 작업 판단 + AX Dev Factory Qwen/OpenCode 자동코딩/검증/복구. Windows 11 Pro / GTX1050Ti / 16GB. 무료·오프라인 우선, 사용자 승인한 큐의 24h 자동작업 지향.
2. **완료·근거:** 빈 새 PUBLIC repo main 최초 README 초기화. `design/final-blueprint-v1`에 High 요구 32개/아키텍처/SQLite/API/신뢰 경계/수용표/30개 원자큐+5개 첫 READY 설계. **제품 코드 미구현**. EAI/AX 원본을 마이그레이션하지 않음.
3. **테스트:** GitHub 문서 생성·파일 확인 별도; 실제 Python/CI/Windows/실 Ollama/OpenCode/실기기/24h: NOT_RUN. 과거 EAI/AX CI 통과는 새 repo 증거 아님.
4. **상태:** P0 High 설계 후보, 사용자 최종설계 승인 대기. 구현률 UNASSESSED, 공식 검증률 UNASSESSED, REAL-USE HOLD, RELEASE HOLD. F18 독립검증 신뢰 경계 CRITICAL HOLD.
5. **위험/실패/대안:** A EAI 단독 후 병합 / B 두 repo 런타임 결합 / C 새 repo에 provenance pinned 선별 이식 비교 후 C 선택. F18 게스트가 PASS 위조 가능하므로 trusted reviewer 없으면 승격 금지, 위험한 host fallback 금지.
6. **GitHub:** `hibi89/my_local_ai@design/final-blueprint-v1`, 정확 HEAD는 GitHub에서 재조회. main baseline `960621d6207e6beb22a7e9480e524988196f3d44`. EAI 참조 `5186cb1aa...`, AX `5ab9418047...`. 개발 목표 브랜치 `dev/instant-implementation-v1`. 
7. **운영/Production:** 로컬 제품, Production URL/Vercel 미적용. 사용자 Windows 설치·Sandbox 가용성/기기 실모델 미확인, 외부 API/paid OFF.
8. **원본/보안/복구:** EAI/AX 원본 repo/main 보존, 고객 DB/.env/모델/프롬프트/토큰 Git 업로드 0. Git history로 문서 rollback; 향후 SQLite·실기기 백업은 설계만.
9. **다음 READY:** 승인 시 MLA-001(원본/라이선스), MLA-002(contract schemas), MLA-003(F18 threat/reviewer), MLA-004(synthetic tests/CI), MLA-005(local benchmark schema)를 묶어 수행. 그 후 각 depends_on/allowed_paths/acceptance/safety_checks로 다음 작업. 코드/수용 SHA 없으면 VERIFIED 금지.
10. **갱신:** 2026-11-17 KST; 설계 기반 검토/문서 저장만, 실기기·모델·독립 감사 NOT_RUN. 최신 디자인 docs/FINAL_BLUEPRINT·REQUIREMENTS·INSTANT_TASK_QUEUE가 작업 정본이며 이 HANDOFF는 이전 정책을 덮지 않는다.
