# My Local AI — 위협 모델/안전 승인/독립 검증 경계

## 현재 알려진 HIGH BLOCKER
기존 AX Dev Factory F18에서 같은 격리 게스트가 수정 코드와 `VERIFIED` 영수증을 모두 생성할 수 있는 신뢰 결함이 발견되어 자동 승격을 HOLD했다. 해시 일치 = 내용 무결성이지 **독립 검증 실행 증거가 아니다**. 새 통합 구현에서 이 결함을 복사하거나 지우지 않는다.

## 대안
- A: 같은 게스트가 코드 작성/검증/영수증까지 제출 → 위조 가능하므로 **REJECT**.
- B: Windows 호스트에서 미신뢰 모델 코드·테스트를 직접 실행 → 원본/비밀 유출·실행 위험으로 **REJECT**.
- **C: 코딩 영역과 검증 영역 분리** + 외부(코딩 모델이 못 쓰는) 리뷰 정책·출력 검증 + host 측 정적 경로/hash 가드 → **선택 목표**. 실제 OS 신뢰 경계와 적대적 위조 테스트를 통과하지 못하면 자동 verified/승격 금지.
- D: GitHub-hosted CI로 추가 신뢰: 공개·승인된 비민감 코드만, remote push 별도 GO이며 사용자의 실제 Windows 검증 대체 불가.

## 위협별 필수 차단
1. 수정 경로 탈출: exact allowlist, path canonicalization, symlink/reparse/NTFS alternate data/ignored-files 검사, before/after Git SHA.
2. Git hooks/filter 실행: 시스템/global/local 효과와 attributes 분석, 위험 필터 차단; 추측으로 원본 설정 변경 금지.
3. 코드/테스트 위조: guest/model logs와 receipts 전부 UNTRUSTED. 별도 trusted reviewer가 독립 자료로 판정.
4. Prompt injection: 모델은 새 task/명령/권한/원본 접근을 요청할 수 없으며 스키마 불일치는 HOLD.
5. 비밀 유출: .env, 토큰, credentials, 고객 코드/개인 경로, prompt/log 원본을 public repo 또는 외부 모델로 업로드 금지. Sandbox network egress default deny.
6. 중복·경합: task+plan+baseline SHA idempotency key; SQLite lease generation, atomic state/ref reconciliation.
7. 비용/성능: 유료 모델 OFF; GPU/RAM/context 예산, 타임아웃, 1회 수정, 중단/재개.
8. 위험한 OS 변경: 관리자 권한 불필요, OS 정책/Sandbox 기능 활성화/시작프로그램·스케줄 등록은 사용자 별도 GO.
9. 원격 GitHub: read-only 기본, 별도 승인된 scope/브랜치에만 push/PR. main merge/force push 금지.
10. 대시보드: localhost 바인딩만으로 충분하지 않음. Host/CSRF·인가·자료 출력 최소화 및 쓰기 승인 구분.

## 검증 수준
`DESIGNED` (현재), `IMPLEMENTED_UNVERIFIED`, `SYNTHETIC_CI_PASS`, `OWNER_WINDOWS_REAL_MODEL_PASS`, `ISOLATION_SECURITY_PASS`, `UNATTENDED_24H_PASS`, `OWNER_REAL_USE_GO`는 각각 독립 증거여야 한다.

실제로 구현한 뒤 F18 trusted reviewer가 막히면 다른 안전한 READY는 진행 가능하지만 **중요 원본에 대한 자동 통합/무인 적용은 HOLD**다. 유료·외부 전송·권한/보안 변경·고객 원본·상용 출시 모두 사전 승인.


## F18 P1 MLA-003 보안 계약 갱신

\`docs/TRUST_BOUNDARY_DESIGN.md\`가 reviewer principal/비신뢰 게스트/보호된 attestation/lease 재사용 방어와 promotion HOLD 규칙의 상세 정본이다. \`tests/security/test_receipt_forgery.py\`는 **합성 PlanSpec 권한 위조 거부**만 검사하며 실제 trusted reviewer, Windows 격리, independent PASS, 원본 자동 승격의 성공을 주장하지 않는다. 기존 F18 보안 HOLD를 유지하며 다음 구현은 MLA-015·MLA-018에서 수행한다.


---

## Hydrogen 외부 coder 위험 추가 (V1.1 설계)
- **외부 전송 = 별도 승인 위험:** API가 무료여도 클라우드로 보낸 내용은 외부 제공자 정책의 영향을 받는다. PUBLIC_NON_SENSITIVE/SYNTHETIC로 승인된 최소 입력만; 비공개 repo, 고객 원본/계약, 키/.env, 해커톤 비공개 자료, GitHub App 서명, 내부 프롬프트·개인 로그 송신 거부. API 계정·요금 정책 및 데이터 사용 조건은 실제 활성화 전에 재확인.
- **기본 차단:** remote_enabled=false, network_egress=deny, max_spend_usd=0, 무료 tier·실비용 위험 UNKNOWN이면 호출 0. 빈 키·429·401/403·paid-only·timeout/OFF 시 remote를 HOLD하고 다른 안전 READY만 계속.
- **코딩 워커의 권한:** Gemini/Hydrogen 출력은 패치 제안이며 shell/테스트 실행/GitHub commit/approval/owner consent/TrustedReceipt 자체 권한 없음. 실행 경로는 별도 sandbox executor, validation과 file allowlist, SHA/epoch fence, Git worktree isolation을 통과해야 한다.
- **F18 강화:** 다른 모델 사용은 독립 검증이 아니다. 원격 코드+영수증도 동일한 비신뢰 입력으로 처리한다. trusted verifier host OS 경계 실증 전 protected ref 승격 금지.
- **유료·무료 변경:** 0원 약속을 토큰 호출 수만으로 보장 불가, 계정 tier/권한·원격 데이터 계약 확인이 되지 않으면 자체적으로 off. 계정 우회/키 회전/추가 결제 절대 자동 금지.
- **fallback:** quota/장애 발생 중간 worktree는 유효성을 재검증하기 전 승격·재사용 금지. candidate_sha/approval/lease 정확성 대조 후 새 Qwen task epoch만 생성. 완료 이력은 불변.
- 적용 범위는 `docs/DETACHABLE_MULTI_MODEL_WORKERS.md`, 현재 상태는 설계만 / 실제 보안·외부 API 실행 NOT_RUN.

## 2026-11-17 P1 신규 즉시 보안 하네스 범위

- `MLA-009` 라이브 consent checker에 현재 SQLite main DB 파일 정체성 pin 및 WAL/SHM sidecar 검사 추가. 파일 교체와 구 DB WAL 접근이 재사용 가능한 승인으로 연결되지 않도록 실패 닫기. 실제 OS ACL/재시작 동작은 P2 검증 전 미보증.
- 계획 단위 `LOCAL_PLAN` scope 이외 고위험 승인(REMOTE_PR/OS_CHANGE/PAID_API/CUSTOMER_DATA/PRODUCTION/NETWORK_EGRESS)은 **action-bound protected signer** 개발 전 상태로 보류. 일괄 재사용 가능한 plan 서명 하나로 해당 승인 성공 금지.
- `MLA-003` 게스트-자체 VERIFIED 선행 상태 위조, forged lease/receipt schema 삽입, claimed APPROVED 자기 인증을 합성 테스트에서 거부. F18 실제 독립 reviewer 코드·OS 경계는 MLA-015/P2 대기. 수용 증거 과장 금지.

## 2026-11-17 MLA-029 Windows F18 test harness (P1 source only)

- `tests/windows/test_trust_boundary_real.py` stores explicit source/candidate/plan SHA, coder/reviewer/owner signer principal split, sandbox, network egress and signer readback-denial preconditions. **Even all asserted booleans cannot create a TrustedReceipt; real OS evidence and protected issuer are mandatory**. Two actual Windows tests have unconditional `skip` until P2 gate/owner-controlled test runner exists.
- User hardware/Windows Sandbox feature probe, protected signer, 24-hour long-run and independent F18: `NOT_RUN`. No admin/OS policy modifications performed, no host fallback. `MLA-029` implementation-only source candidate and `BLOCKED_DEPENDENCY` runtime remain.

## V1.3 CodeShield: 사전검수와 독립 F18의 분리 (2026-11-17 승인 설계)

- 기본은 호스트 Qwen 1개 + Python AST + pin된 Ruff(S) + 승인된 로컬 Semgrep CE rules + Gitleaks/OSV offline 조건부 + 기존 Windows Defender 상태. 컴퓨터 전체 PC Care 상시 엔진/VM 상시가 기본 아님.
- 정적 검사, Defender PASS, Qwen 코드 리뷰와 GitHub Actions synthetic CI는 **OS 실행 격리의 증거도 F18 독립 검수 영수증도 아니다**. 실행권한이 없는 후보는 파일만 작성·분석하고 생성 코드/생성 테스트/스크립트/패키지/EXE 실행을 HOLD.
- 유효한 AppContainer/제한 Windows principal/Job Object·DACL·egress deny·도구 분리를 실제 Windows에서 입증하기 전에는 VM을 대체하는 실행 게이트로 인정할 수 없다. 실패 시 on-demand Windows Sandbox (별도 owner 승인 및 Windows 기능 사용) 또는 해당 작업 HOLD.
- Defender CFA 활성화/차단 정책 예외/타사 준백신 설치/비밀 업로드/임의 글로벌 npm·pip/OS 방화벽/보호된 키 저장소 변경: 승인 없이 금지. Defender off라면 단순 scanner PASS로 바이너리 실행 허가 금지.
- 정책 결과 상태는 ALLOW_NON_EXECUTING, REQUIRES_ISOLATION_HOLD, HOLD_HIGH_RISK, UNKNOWN_HOLD로 제한. READY/VERIFIED/RECEIPT/PROMOTION은 독립 owner signer/F18/lease/Git readback 게이트가 별도로 판정한다.
- 기술선택·성능/수용·공식 근거는 docs/CODE_SHIELD_LIGHTWEIGHT_SECURITY_V1_3.md. 구현 큐는 docs/OPTIONAL_CODESHIELD_TASK_QUEUE.json의 별도 0/8. 기존 P2 LOCKED/owner GO false를 유지한다.
