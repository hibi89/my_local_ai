# My Local AI — 최소 FE/CLI 상태·승인 사용자 흐름

UI는 제품 기능/보안 이후. Windows 11 Pro 개인용이라 CLI → 최소 loopback 대시보드의 순서로 개발한다. Astra Max는 구현 후보 이후 사용성·반응형·접근성 독립 검수.

## 첫 화면/상태 정보
1. **Dashboard:** 현재 실행 모델/작업 한 건, plan SHA, source SHA, 실행 시간, 작업상태별 개수: READY, CODING, CANDIDATE_UNVERIFIED, VERIFIED, HOLD, BLOCKED_DEPENDENCY, AWAITING_OWNER. 공식 구현률/검증률은 각각 증거 기반 표시, 분모 불명은 UNASSESSED.
2. **Queue:** REQ-ID, 선행조건, 허용 파일 수, risk, 시작 가능 여부, 실패 사유, 현재 reviewer trust level.
3. **Safety HOLD:** F18 미해결, 외부 전송 차단, 고객 원본/권한 승인 필요를 눈에 띄게 표시. 진행률 100%나 녹색 성공으로 숨기지 않음.
4. **Runtime:** CPU/RAM/VRAM 사용 관측 및 모르는 값은 NOT_MEASURED; 24h 진행 시간과 예상 비용(계측값만), 모델 로그 원문/secret 비표시.
5. **Evidence:** Git 커밋/기능/테스트 exact SHA, host Windows vs CI vs fake 분리, redacted export.
6. **Owner controls:** stop, resume, plan review, risk approval는 명확한 승인·재확인; 원격 PR/권한/OS 변경은 기본 UI에 자동 활성화하지 않음.

## FE 보안/사용성
- no external port; 필요 시 loopback + Host 검증, same-origin CSRF, local OS owner auth, no static shared token in repo.
- action endpoint는 JSON body strict schema/nonce; 로그/파일경로·민감 데이터 숨김. GET은 읽기 전용.
- 키보드/스크린리더, 오류 메시지 명확성, 작은 화면에서 HOLD/GO 오인 방지.
- 단일 사용자/단일 머신 초기 설계, 외부 접근/모바일 클라우드 접속은 별도 승인 전 불허.
- frontend 예쁨을 구현률/검증률과 혼동하지 않음.
