> **[2026-11-20 KST · MLA Q DESIGN HANDOFF]** 사용자 확정: GTX 1050Ti 저사양에서 원본 소스/실패 증거 재활용·Qwen 하나·고성능 외부 AI 별도 승인·기존 Ubuntu/Windows CI를 활용하고, Windows MLA.exe에 구조화된 개발 지시문을 넣어 안전한 독립 초안들을 SQLite checkpoint/stop-resume으로 계속 처리한다. §Q 정본. `MLA-LR-001` source candidate dev `9e7c68fea15da2c6afe24a449bf7022009225e31`, synthetic test corrected `4827510fc95f802d4b3355302b5ce6abd6f79a45`, CI PASS #44751448525, Windows build PASS #44751337489. 장시간 실 Windows 11과 완전 코드 구현/검증 자동화는 미완/NOT_RUN; 다음 LR-002 고정 신뢰 CI, LR-003 부하 최적화, LR-004 실기기 다일 P2 별도. AI 생성 코드·테스트 실행/Owner/F18/비밀·외부 전송/유료/Production/OS/원본 보호 게이트 불변. 

> **[2026-11-20 KST · P0 LINUX-FIRST/WINDOWS-BOUNDARY DESIGN LOCK]** 사용자 승인으로 `docs/FINAL_BLUEPRINT.md` §P를 설계 정본에 반영했다. 정본 최초 설계 커밋 `e435b45e134649a60855cf9b416b3b235b2249e2`; 동일 §P 개발 브랜치 선택 반영 커밋 `1ab4ea684bfe700c3e954c4c1bb35fd7542a53f2`. Ubuntu 24.04 LTS 공통/합성 CI + 기존 Windows CI 조기 네이티브·EXE 검사 + 실제 Windows 11 Owner/F18·보호 신뢰 최종 인수. Linux/GitHub CI는 미신뢰 생성 코드 실행 허가가 아니며 MLA Zero-VM, F18, 승인, 기존 P1/P2 단계·REQ/SWU 분모 불변. 실 코드·Actions 워크플로·실기기 검사·독립 감사 이번 변경 NOT_RUN; P1/P2 신규 수용 0, 출시 HOLD. 다음 개발자는 실 dev HEAD/큐/코드를 다시 확인하고 안전한 기존 CI 재사용부터 적용한다.**

> **[2026-11-18 KST · MLA V2.0 P0 FINAL DESIGN HANDOFF]** User approved V2.0 architecture in docs/FINAL_BLUEPRINT.md §M + docs/MLA_V2_FINAL_ARCHITECTURE_MESA_AXZERO_20261118.md. Reuse V1.2 Experience Learning (7 EXT-EXP SWU) as MESA and existing Hydrogen V1.1 (8 EXT-HYD SWU); add 5 distinct optional integration SWUs, do not alter original 55 (39+16) P1 denominator or security. AXZERO is separately owned by Freelancer/product/ax-zero-local, no implemented product code observed at initial design; AXNODE optional. Owner UI alternative is a redesign candidate of existing MLA-SWU-008, not a completion or new baseline. Base dev observed @7ffd12c190392c6db675a69a5f5b54ff8ffb6f4a: 52/55, live Owner error 5, real F18/Defender HOLD, P2 LOCKED/UNASSESSED. No dev push, OS permissions, external calls or source testing from this design update. Next implementer checks newest HEAD and AGENTS/HANDOFF/STATUS then real source, preserves old history and obtains scope/OS GO when necessary.

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
2. **완료 변경:** `FINAL_BLUEPRINT H` 및 `DETACHABLE_MULTI_MODEL_WORKERS`에 3개 설계안 비교/ProviderPort/scheduler/isolated worktree/F18/circuit/quota/fallback/DB·FE/API 계약/12작업 합성 비교 수용 반영. 선택형 `OPTIONAL_PROVIDER_TASK_QUEUE.json` 8개(EXT-HYD-01..08) 생성. 기존 AGENTS, PHASE_GATES, REQUIREMENTS, ARCHITECTURE, SECURITY, INTEGRATION, ACCEPTANCE, RUNBOOK 및 branch policy에 일관 참조 추가. **제품 구현 코드는 이번 변경에 포함되지 않음**.
3. **테스트:** GitHub 문서/커밋 확인만. Python·전체 CI·Windows·실 Qwen/Hydrogen·API/쿼터·비밀 차단 실험·24h/진짜 F18 경계·독립 감사 모두 이번 변경에서 `NOT_RUN`. 기존 dev의 합성 PASS를 새 설계 검증으로 승격하지 않음.
4. **진행/대기/차단:** 원래 P1 28 작업/REQ-01~30 기준선 불변, dev 최신 기록 3/30=10.00% (코드 근거 `4bdff24d...`, 더 최신 코드가 있으면 실제 소스 확인). 기존 P2 `LOCKED`; F18 `SECURITY_HOLD`. EXT-HYD-01..07 설계/의존성과 구현 범위 승인 대기, EXT-HYD-08 라이브 API는 명시적 owner GO 전 `BLOCKED`.
5. **오류/대안:** 무료 Hydrogen을 필수 엔진으로 강제하거나 각 도구별 분산 연동하면 제품 중단·요금/비밀 정책 분산. 채택안은 common ProviderPort와 0원 비용/데이터 guard. 무료 소진 429/유료/키 없음/OFF이면 queue checkpoint/lease fencing, 로컬 Qwen 재배정 후보. Qwen 불가 시 HOLD. 웹 Instant는 별도 사람이 진행하는 lane이며 자동 API 실행 가능하다고 주장하지 않음.
6. **repo/branch/SHA:** `hibi89/my_local_ai@design/final-blueprint-v1` (이 인수인계 편집 직전 설계 HEAD `a2219d0218b4909477265ecf46c5cf49af3402e7`; 이 파일 커밋 후 최종 SHA는 반드시 GitHub 재조회). 2026-11-17 확인 `dev/instant-implementation-v1@e6af762a5d4e7f61d18fee1ae2ba55df423cc443`, `main@960621d6207e6beb22a7e9480e524988196f3d44`. 원본 EAI/Freelancer untouched.
7. **Production/환경:** 로컬 도구 설계만, 배포·고객 환경·실 GPU/RAM/유료 API 미적용. LIVE HYDROGEN account tier/쿼터·실모델·SDK tool calling `UNVERIFIED`.
8. **원본·백업/인증:** 원본 Git 이력 불변, 새 문서 commit으로 rollback 가능. 고객/개인 자료·비밀·.env/GitHub 토큰 0 업로드. DB migration/OS 권한/실 테스트 수행 안 함. `remote_enabled=false`, network deny, spend cap 0 유지.
9. **다음 READY·완료 기준·승인:** Instant는 개발 브랜치 기존 안전 P1 큐를 계속 수행. High는 선택형 큐 EXT-HYD-01 mock contract부터 정확 source SHA·허용 경로·타 작업 충돌 없는 계획을 별도 인수한 뒤 착수 가능. dev 동기화 시 설계 docs만 신중하게 적용하고 기존 dev STATUS/큐/코드를 통째로 덮어쓰지 않는다. 원격 송신·계정/비용·GitHub PR/권한/원본·Production·main은 **별도 사용자 GO 필수**.
10. **갱신·범위·기준:** 2026-11-17 KST, `design/final-blueprint-v1` 설계 문서만 실제 반영. 구현/검증률 추가 상승 0, 공식 검증완료율 `UNASSESSED`, Hydrogen 실제 운용 `NOT_RUN`. 최종 설계 브랜치 SHA는 반드시 재조회하고 dev는 실제 최신 HEAD를 다시 읽는다.


---

# 2026-11-17 KST 최신 인수인계 — P1 브라우저 후행 정책
1. **추가 사용자 확정:** Codex·Instant·Qwen/Hydrogen이 P1에서 BE/FE 모두 구현하되, 반복 브라우저·Playwright E2E/시각·반응형·접근성 검사는 P2에 집중. 문법·타입·필요 최소 빌드·국소 smoke와 인증/권한/원본/비밀/F18 위험 즉시 검사는 P1 유지.
2. **설계 변경:** `docs/FINAL_BLUEPRINT.md F-1`, `docs/PHASE_GATES.md`, `AGENTS.md`, `INSTANT_RUNBOOK.md`, `REQUIREMENTS.md`, `docs/ACCEPTANCE_MATRIX.md`, `VERIFICATION_TASK_QUEUE.json MLA-V007`, `docs/DETACHABLE_MULTI_MODEL_WORKERS.md`, `STATUS.md` 반영.
3. **P1/P2 경계:** 브라우저 확인이 필수적인 구현/위험 변경에 한정해 최소 스모크 허용하고 이유·정확 SHA·결과 기록. 전체 브라우저 검증 미실행은 `NOT_RUN/DEFERRED_TO_P2`; `IMPLEMENTED_UNVERIFIED`는 검증 PASS가 아님.
4. **인수 상태:** 이 변경은 문서·P2 큐 수용조건 갱신뿐. P1 30 REQ/28 구현 task, P2 8 verification task 및 P2 LOCKED/High 정확 SHA 게이트 불변. Hydrogen live API 기본 OFF/별도 GO, F18 HOLD 유지.
5. **실행 증거/차단:** 이번 변경으로 Python/CI/브라우저/Windows/실 Qwen/Hydrogen/24h/독립감사 테스트 **NOT_RUN**. 외부 송신/권한/결제/remote PR/main·Production 변경 없음. 실제 dev 구현률은 dev HEAD·코드·큐 확인 후 별도 보고.
6. **다음 READY:** 설계 브랜치 최신 SHA/AGENTS/FINAL_BLUEPRINT→dev HEAD·진행 중 수정 경로 비교→설계 문서만 안전 동기화. 기존 P1 구현 계속, P1 구현 100% 후보+High 인수 후 P2 브라우저/Playwright 전체 검증.
7. **기준:** 2026-11-17 KST; `hibi89/my_local_ai@design/final-blueprint-v1`. 최신 commit SHA는 GitHub 재조회. 기존 dev 이력은 보존하고 이 인수인계가 과거 수치나 Code PASS를 소급 갱신하지 않는다.

---

## 2026-11-17 KST — 브라우저 검증 P2 이관 설계 기록
- 개발 브랜치 `dev/instant-implementation-v1`의 P1/P2 큐를 먼저 수정한 커밋 `51f4885a44540890996943bc058621d747325c50`을 참조하여 설계 브랜치 큐에도 검증 이관 ID만 동기화함. P1 `MLA-019/021/025`→P2 `MLA-V007`, CLI-only `MLA-006` 비대상.
- **이 설계 브랜치의 과거 `P0/0 구현` 문장은 개발 현황이 아니다.** dev SHA `51f4885...` 시점 구현률 **4/30=13.33%**; 실제 재개 전에 GitHub에서 최신 HEAD·소스·큐 확인.
- `ㄱ` 다음 READY: dev 큐에서 `MLA-012` loopback Ollama provider 구현 시작. P1 BE/FE 코드 작성, 문법/type·필수 CI·국소 safety 확인만. 전체 browser/Playwright, CI 수동 반복 대기, 실 Win11/24h는 P2. P2 LOCKED/검증률 UNASSESSED/F18 HOLD. 원본 EAI/AX/main·사용자 데이터·유료/remote 손대지 않음.

---

## 2026-11-17 KST — High V1.2 Experience Learning Engine 확정설계 인수인계 (10항)
1. **목표/기술:** MLA의 자체 Controller 및 로컬 Qwen/OpenCode 기반 개발 자동화를 **경험 기반 적응형 시스템**으로 확장한다. 개발 오류/수정/독립 테스트/복구의 실제 own-source 기록을 분석해 스킬·작업 분할·도구/테스트 우선순위를 선택한다. Python3.11·SQLite/FTS5(optional)·SKILL.md·버전 규칙, EAI AdvisorPort/Hydrogen provider/AX 기술 출처/AXNODE optional export 유지.
2. **완료 변경:** `docs/EXPERIENCE_LEARNING_ENGINE.md` 신설(3안 비교, BE/FE/API/DB, 데이터·신뢰/권리, 상황 판단/재현 가능한 A/B, EXP-AC-01..10), `docs/OPTIONAL_EXPERIENCE_TASK_QUEUE.json` 신설(EXT-EXP-01..07), `docs/FINAL_BLUEPRINT.md I`/ARCHITECTURE/REQUIREMENTS/INTEGRATION_CONTRACT/SECURITY_MODEL/ACCEPTANCE_MATRIX/PHASE_GATES/AGENTS/INSTANT_RUNBOOK/STATUS에 설계 연결. **제품 코드 자체 변경/실행 없음**.
3. **검증:** GitHub 문서/큐 커밋과 readback만. 실제 Python·전체 CI·실 Windows/Ollama/OpenCode/Hydrogen/Sol Max API·모델 가중치·브라우저/Playwright·실 프로젝트 자동 학습·A/B·F18 분리 실행 **NOT_RUN**. 이전 P1 소스 성공을 이번 신규 기능 PASS로 소급하지 않는다.
4. **단계:** 기존 P1 필수 REQ-01..30/28 구현작업 및 P2 8검증/LOCKED, F18 CRITICAL HOLD, P1 browser E2E DEFERRED_TO_P2 불변. EXP 확장은 `DESIGN_ONLY_NOT_READY`·원래 구현완료율/공식검증률 수치 상승 0. dev 현재 실적은 정확 HEAD/STATUS 확인 후 보고.
5. **오류/대안:** (A) 다수 hardcode rules는 조합 폭발, (B) Sol Max 답변 수천 건 수집/모델 학습은 증거/권리·공급자 약관 위험. (C) **자기 개발 사례+독립 테스트 증거→권리·안전 필터→read-only 검색→승인된 skill/version** 선택. 모델 self PASS/추론/테스트 위조는 신뢰하지 않음; 오류·환각/부정례 격리, no memory fallback.
6. **repo/branch/SHA:** `hibi89/my_local_ai@design/final-blueprint-v1`. 최초 변경 전 design HEAD `d0fb706a1b4d9f5d108f561f37c837f065c600b4`, 같은 시점 dev `dev/instant-implementation-v1@51f4885a44540890996943bc058621d747325c50`. 이 인수인계 커밋 뒤 최종 HEAD는 GitHub에서 재조회. EAI/AXNODE/AX Dev Factory/main/dev 소스 미수정.
7. **Production/환경:** MLA 로컬 프로그램, Vercel/Production N/A. 경험 수집/실 Windows/실모델/24h 모두 NOT_RUN. LLM 외부 호출/유료/비공개 자료 전송/모델 training 신규 승인 없음.
8. **원본·권리/백업:** 공용 GitHub에는 공개 가능 설계·합성 metadata만; 고객 코드·키/토큰/.env·프롬프트·모델 output 원문, private SQLite/로그·사용자 폴더 경로를 올리지 않음. 원본 Git 이력/기존 기능·DB 원본 보존. 소스 이식은 라이선스/NOTICE/provenance 확인 뒤 별도 실시.
9. **다음 READY/GO:** Instant는 현재 dev의 원래 `MLA-012` 등 본선 P1 구현을 계속. EXP-01..07은 High가 충돌 없는 경로/REQ/허용 범위/의존성을 현재 dev SHA와 검토하고 확장 구현 범위 GO를 받은 뒤 별도 시작. owner 실제 데이터 수집·새 provider·API/billing·AI 모델 학습/소스 송신/원격 push/권한·Production 작업에는 각각 명시적 승인 필요. P2·브라우저/Windows/보안 독립 검수는 100% 구현 후보+High 게이트 후.
10. **기준:** 2026-11-17 KST. 최종설계 V1.2 확장 **DESIGN_ONLY**, 코드/실사용/공식 수용 미검증. 최종설계 브랜치 SHA를 재조회하고 dev STATUS/HANDOFF의 실제 최신 실적을 우선한다.


---

## V1.3 High final design update (2026-11-17 KST)

- User-authorized source design change: default host Qwen 1 + CodeShield static audit; permanent VM/Sandbox dependency removed from nonexecuting work. Untrusted executable code must still use attested OS isolation + independent F18 before any actual run/promotion; no unisolated host fallback.
- New base design: docs/FINAL_BLUEPRINT.md J, docs/CODE_SHIELD_LIGHTWEIGHT_SECURITY_V1_3.md, docs/OPTIONAL_CODESHIELD_TASK_QUEUE.json (CS-01..08, 0/8 design only).
- This design commit does not ship scanners, install Defender tools, provision AppContainer, execute untrusted code, issue protected signed F18 or change protected Git refs. P1 baseline history 35/39 candidates in dev at the reviewed SHA; formal REQ 5/30, P2 LOCKED, official verification UNASSESSED. No implementation rate increase.
- Dev file sync must preserve dev actual HEAD, 39 source queue/WORK_PHASE_GATES, existing F18 security design and status. Feature branch starts from dev after selective docs sync; owner runtime GO is still false. Reference branch HEAD in exact corresponding implementation handoff rather than a stale design SHA.


---

## 2026-11-17 V1.3 Design final branch topology confirmed

- High design base updated at c9eb919bab83e782e53f8d4d6bf3e5f179715e27, 9c416a22aa061aa9bdb2641713b9d3c3a924aa15, 0ea09e21fa560575d2c5126c240c586d60ed4417. Exact current HEAD must be fetched before additional writes.
- Dedicated feature/code-shield-lightweight-v1 branch was actually created from existing dev commit **59caaf21625e8c06affb824b15f0ca0cb306e61c**; it contains selectively synced V1.2 Experience and V1.3 CodeShield design. Source code, original queues, mandatory CI, existing SWU evidence and P2/owner gates left unchanged.
- Core design: docs/FINAL_BLUEPRINT.md J + docs/CODE_SHIELD_LIGHTWEIGHT_SECURITY_V1_3.md; queue 8 source CS tasks; acceptance docs/CODE_SHIELD_ACCEPTANCE_MATRIX.md. Actual CodeShield core implement 0/8, tests NOT_RUN, Windows/AppContainer/Defender actual configuration unchanged.
- **Active dev/instant-implementation-v1 had concurrent HEAD movement twice** while attempting an exact-lease documentation sync. No overwritten/misaligned commits; selective design sync made on isolated feature instead. Dev branch retains its own latest code and status. Never overwrite dev history or import stale design STATUS/HANDOFF. Subsequent integration requires exact latest SHA and conflict-aware review; main untouched.
- Owner 2+2 retry rule is current, initial 2 failures isolate/replan, second improved attempts 2, cumulated 4 unresolved to Sol Max, critical trust blocker immediate owner request. Existing historical code attempts are not automatically failures.
