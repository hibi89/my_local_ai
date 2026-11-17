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
