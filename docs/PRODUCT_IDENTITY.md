# My Local AI — 독립 제품 정체성·EAI 기술 활용 원칙 (OWNER CLARIFICATION, 2026-11-17 KST)

## 반드시 기억할 구분
- **EAI (기존 별도 프로젝트):** 자체 지능·CPU 인지/문제 해결 및 그 고유 목표를 개발하는 **원래 EAI 제품**. 원본 EAI ADR-0002 등은 해당 repo에만 적용되며 원본 작업·브랜치·13 goal/진척률을 변경하지 않는다.
- **My Local AI (별도 새 프로젝트):** **Windows 노트북에서 24시간 승인된 소프트웨어 개발 작업을 수행**하여 GPT 사용량 병목을 줄이는 로컬 자율개발 제품. 자체 요구사항·일정·책임·데이터·권한·CPU/LLM orchestration·검증/복구 시스템을 갖는다. EAI와 동일한 인지 연구나 EAI의 13 goals 100%는 필수가 아니다.
- **AX Dev Factory:** 개발 자동화 실행기(작업 큐, 안전한 Git worktree, OpenCode/Ollama, SQLite 복구)의 기술/구현 출처. AX Dev Factory 원본을 My Local AI의 곧바로 검증된 결과로 인정하지 않는다.

## 고유 목적
High 설계·승인 → My Local AI Controller가 자체적으로 승인 계약/의존성/작업 순서를 선택 → 제한된 Qwen/OpenCode coder가 실제 코드·테스트를 작성 → 격리된 별도 신뢰 검증 경계가 근거 확인 → 1회 복구/HOLD 및 독립 READY 진행 → 정확 SHA·상태 인계. P1 구현 100% 후보, P2 공식 검증은 별개. 외부 GPU/유료 API/GPT급 성능은 필수가 아니다.

## 기술 활용과 의존성
1. My Local AI는 EAI를 **사용/참고**하지만 **EAI 자체를 완성하기 위해 만드는 것이 아니다**. EAI 전체 저장소 복사/실행을 필수 요건으로 삼지 않는다.
2. EAI 유래 기능(예: CPU 분석·작업 순위·근거 요약)은 라이선스/출처 확인 후 선택적 AdvisorPort로 쓸 수 있다. 끄거나 실패해도 My Local AI의 자체 결정론적 Controller/안전 기능이 동작해야 한다.
3. EAI advisor는 후보/분석만 제공한다. 사용자 GO, 승인 범위, 검증 PASS, 도구 실행, 권한 확장, 중요 Git 반영은 고유 컨트롤러/독립 trusted reviewer의 책임이다.
4. 원본 EAI 안에서 Qwen은 INPUT-only로 유지한다는 제약을 수정할 이유가 없다. 이 제약을 **My Local AI의 로컬 코딩 모델에 적용하면 안 된다**. 여기서는 Qwen/OpenCode가 코드 생성·수정·테스트 파일 작성에 활용된다.
5. AX Dev Factory의 보안/F18 결함은 역사적으로 발견한 위협을 재사용한 것일 뿐, My Local AI의 기능 완료 증거가 아니다. 안전한 독립 검증 경계는 새 제품 자체의 기준으로 실증해야 한다.
6. My Local AI의 구현/검증 분모·RELEASE GO·상업화 권한은 EAI/AX와 별개로 관리한다. 제품을 묶더라도 원본의 개발률·검증률·완성 주장을 합산하지 않는다.

## 금지 오해
- “EAI를 100% 만든 다음 My Local AI를 구현해야 한다” → **아니다**.
- “My Local AI가 EAI CPU 엔진의 하위 제품이므로 EAI가 모든 결정의 주체다” → **아니다**.
- “EAI의 원본 Qwen INPUT-only 제약이 My Local AI coder까지 금지한다” → **아니다**.
- “EAI의 13개 typed goals 전부 지원해야 My Local AI가 100%다” → **아니다**.
- “다른 repo가 합성 CI PASS였으므로 My Local AI도 PASS다” → **아니다**.

## 역할·보안 불변
User-approved High contract > My Local AI Controller policy > optional EAI advisor hints (non-binding) > AX-style local coding worker (untrusted code) > independently trusted reviewer for certification > local protected ref. 원본 EAI·AX 저장소는 읽기 전용. 고객 자료/원본/권한/유료/외부 전송·운영 출시 별도 승인. 현재 P1 작업 우선·P2 Gate LOCKED 보존.

**상태:** 설계 정체성 정정만 완료. My Local AI 제품 소스는 여전히 미구현이며 실제 CPU/LLM/Windows 통합 테스트 NOT_RUN.
