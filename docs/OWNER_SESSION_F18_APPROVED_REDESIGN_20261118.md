# MLA V1.3/V2.0 — Owner 자체 세션 승인 + F18 분리 검증 승인 설계

**승인:** 2026-11-18 KST, 사용자 명시적 재설계 및 P1 소스 구현 승인.
**제품:** `hibi89/my_local_ai`, 코드 브랜치 `dev/instant-implementation-v1`, 설계 정본 `design/final-blueprint-v1`.
**변경 성격:** 기존 MLA-SWU-008·MLA-SWU-021 내부 구현 교체 및 수용조건 분리. 신규 SWU 추가, 기존 30 REQ/55 기본 SWU 삭제·축소, OS 권한 GO, P2 통과, 상용 출시는 아님.

## 1. 왜 재설계했나

기존 보호 Owner 서비스는 `WTSSendMessageW`로 다른 Windows 세션에 승인 메시지를 보내도록 설계되어 현장 오류 5(접근 거부)가 발생했다. 그것을 관리자 권한 확대나 동일 Controller 계정 승인으로 우회하지 않는다. 유효한 Owner 승인, 보호 서비스 ECDSA/TPM 서명 및 독립 F18은 **서로 다른 신뢰 주체**여야 한다.

기존 REQ-14는 '독립적인 단위/보안 테스트 실행'을 요구하지만, Zero-VM 최신 정책은 AI 생성 코드·테스트 실행을 금지한다. 단순 정적 검사 PASS를 실행 테스트 PASS로 승격하면 안 된다. 이 상충은 수용조건이 아직 해결되지 않았다는 뜻이다.

## 2. 승인된 Owner 자체 세션 경로 (MLA-SWU-008)

```text
Controller (비신뢰 요청) → 보호 Owner Windows 서비스
  → 보호 authority DB live scope + exact action/SHA/lease 확인
  → protected journal에 nonce RESERVE, 재사용 차단
  → 서비스 전용 비수출 TPM/CNG ECDSA 키로 challenge/작업 전체 서명
  → 사전 운영자 구성한 OwnerExchange 고정 경로에 O_EXCL 파일
  → 별도 SID/세션의 MyLocalAI.OwnerUI.exe
    → 설치 EXE SHA·공급 파일·Owner SID/Session ID·HKLM 고정 공용키 검사
    → 서비스 서명 검증 → 작업 전체/범위/SHA/nonce/TTL 표시
    → MessageBoxW (자기 세션, 기본 거절, WTS 타 세션 메시지 없음)
    → 별도 Owner 비수출 TPM/CNG ECDSA 키로 정확한 결정 서명
  → 응답 파일 원자적 게시 → 보호 서비스의 pinned Owner 공용키 검증
  → 정확한 ticket SHA/action SHA/binding/nonce/SID/만료 확인
  → authority 재조회·revocation 확인 → 서비스 자체 서명된 1회 승인 영수증
  → 독립 Reviewer runtime permit → 고정 정적 또는 허용 Defender 작업
```

**사전 별도 Windows 운영 구성 필수(이 문서와 코드로 자동 생성하지 않음):**

- 로그인 가능한 `InteractiveOwnerSid`와 고정 `OwnerSessionId`; Controller SID와 세 보호 서비스 SID와 모두 서로 달라야 한다.
- 고정 명칭 `MyLocalAI.OwnerUI.exe`, `_internal`을 가진 보호된 one-folder frozen 설치. 프로세스 SID·세션·실행 이미지 SHA256·비신뢰 쓰기 ACL은 OS에서 검사한다. EXE 이름만으로는 권한이 부여되지 않는다.
- 서비스와 Owner UI에 각기 다른 비수출 ECDSA P-256 TPM 키 및 OS ACL. 기존 서비스 키는 Owner UI에 전달 금지. Owner UI 공개키는 HKLM 보호된 `SOFTWARE\MyLocalAI\ProtectedBrokers\v1`의 `OwnerUiKeyName`, `OwnerUiPublicKeyBlob`, `OwnerUiImageSha256`에 고정한다. 실제 키, 비밀키 및 사용자 데이터는 저장소에 넣지 않는다.
- 사전 보호 디렉터리 `C:\ProgramData\MyLocalAI\OwnerExchange\v1`: Owner 서비스 SID와 Interactive Owner SID만 쓰기 권한, SYSTEM/Administrators 보호. 중간 디렉터리 재파스/약한 ACL 불허. 개발 코드가 디렉터리·계정·키·ACL을 생성하거나 권한을 확대하지 않는다.
- Owner UI는 요청 파일과 서명을 검증한 후에만 표시하며, 거절/닫기/키 없음/앱 부재/타임아웃/신원 불일치/nonce 재사용은 HOLD.
- 서비스는 서명된 외부 결정을 확인한 후에만 기존 서비스-서명된 응답을 반환하고, 항상 보호 DB의 현재 lease/revoke를 다시 확인한다.
- 승인 교환 기한 120초, IPC 소유자 요청 상한 150초, 최종 broker signed response TTL 최대 30초. 실제 기기에서 타임아웃/복구/취소 정책 검증 필요.

## 3. F18 이원화 수용조건 (MLA-SWU-021, REQ-14)

| 차원 | 실제 산출물 | 상태/권한 |
|---|---|---|
| F18-A 코드 정적 보호 검수 | 보호된 별도 Reviewer 서비스에서 불변 Git 후보 readback, source SHA, AST, CodeShield 정적 규칙 확인; `STATIC_ONLY`, `execution_count=0` 보고 | 코드 후보 근거 전용. P2 OS 서명/독립성 실증 전 `UNASSESSED`. 생성 코드 실행·Git 승격·REQ-14 실행 테스트 합격 금지 |
| F18-B REQ-14 독립 실행 테스트 | 독립 주체의 실제 단위/보안 테스트 실행, 정확 SHA/범위/원본/권리 검증과 서명된 결과 | 최신 Zero-VM/무자동실행 정책에서는 `NOT_RUN_ZERO_VM_POLICY_HOLD`, `UNSATISFIED`. 소유자가 별도 검증 환경/수용조건을 승인하고 실제 E2E PASS 전에는 미완 |

보호 정적 보고를 구형 `TrustedReceiptV1`이나 `VERIFIED`로 변환하지 않는다. 별도 검수자 Codex와 UI/UX Astra는 코드 독립 감사 대상일 뿐 OS 보호 Owner 또는 F18 실제 발급 주체를 자동으로 대신하지 않는다.

## 4. 수용 및 차단 표

- **P1 소스 구현 후보:** callable service→native Owner UI→signed decision 검증, 정상/거절/위조/재생/만료/서비스 부재 경로, 정적/실행 검수 상태의 분리가 코드로 연결되고 필수 국소 synthetic CI PASS면 코드 후보 진전 증거다. 이것만으로 SWU 완료, Owner GO, 실기기 PASS가 성립하지 않는다.
- **Windows 신뢰 기기 최소 시험:** 별도 계정·프로세스 토큰/세션·SCM 고정 이미지/ACL·TPM 키; Owner UI 보임/거절/승인/취소/만료/재사용/권한 오류; 서비스 서명 상호 검증; Windows Defender 실제 파일 검사와 롤백·복구. 승인된 안전한 합성 데이터로만 실시.
- **P2 전체 검증 및 출시:** P1 소스 후보 및 고유 게이트 이후 별도 담당자의 Win11 실기기/통합/보안/복구 검증과 독립 감사, Owner 최종 GO 필수. CodeShield PASS만으로 실행 불허.
- 실제 운영 키·계정·키 저장소·ACL·프로그램 설치·Windows 보안설정 변경·Production/main/외부·유료 실행은 이 문서 저장 또는 P1 코드 커밋만으로 자동 승인되지 않는다. **실제 OS 환경 변경은 별도 작업 내용·계정·복구 계획을 제시하고 사용자 승인 후 수행한다.**
- 사용자의 PC에서 실측되지 않은 모든 항목: `NOT_RUN`, 구현률 공식 `UNASSESSED`, P2 `LOCKED`. 계획/속도 개선 효과 `UNMEASURED`.

## 5. 구현 위치와 진행 증거

- `src/my_local_ai/state/consent.py`: native Owner service, signed challenge/reply contract, Owner self-session frozen entry, crypto pins, exchange and live authority gate.
- `src/my_local_ai/review/protected_reviewer.py`: signed STATIC_ONLY source review, legacy executed-test 수용과 분리한 `to_acceptance_status`.
- `tests/security/test_protected_service_servers.py`: 안전한 synthetic OS-boundary fixture, nonce/replay/forgery/expiry/scope, 고정 경로·서명 왕복·정적/실행 구분 회귀.
- 최초 소스 반영: `c7071abbe0e44dec408d640c41315ddfc800625c` ~ `0125dc778f7959fd7f1e5f2a3abce8f305b4c163`. 실제 Windows 보호/Owner 계정/실명 서명/Defender/E2E는 `NOT_RUN`.
- 기존 55개 기본 SWU, 30 REQ, 허용 경로·DAG·2+2·History·원본/복구 및 선택 V2 범위 GO는 변경 없음. 과거 참고치 52/55는 동결된 **소스 후보 장부**일 뿐 본 재설계가 새 SWU 완료를 증명하지 않는다.
