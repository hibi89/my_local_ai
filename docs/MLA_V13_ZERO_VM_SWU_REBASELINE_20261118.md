> **[2026-11-18 KST · IMPLEMENTATION WAVE UPDATE]** Current final-design P1 **50/55 = 90.91%** (MLA 35/39; CodeShield 15/16); remaining **5 SWU** (MLA-SWU-008/015/021/031, CS-SWU-012). Implemented `MLA-038/CS-014` at `2509904c` and `CS-007` at `93017420`; exact-SHA GitHub CI `44152457880`, `44153119018` PASS. Semgrep fixed native scanner is **source candidate only**; actual Windows scanning, no-egress, independent F18, owner grant, original/Git promotion remain NOT_RUN/HOLD. Prior 47/55 table below is the **historical rebaseline snapshot**, not today's current score. No VM/container fallback. SWU IDs/REQ/DAG/2+2 preserved.

# My Local AI V1.3 — Zero VM/Windows container P1 SWU rebaseline

**기준:** 2026-11-18 KST. **설계 SHA:** `05f51849c0efe7303bf57cb78dff576e441063f5`; **실제 검토한 개발 소스 SHA:** `e09b72c9b4cf1ad1ed23312662c655b70446d455`. P1 기능 코드 후보만 판정했으며 P2/실운영을 검증한 것이 아니다.

## 공식 재산정

| 범위 | 과거 설계 기준 | 현재 최종설계 기준 | 남은 SWU |
|---|---:|---:|---:|
| MLA | 35/39 | **34/39** | 5 |
| CodeShield | 14/16 | **13/16** | 3 |
| **합계** | **49/55 (89.09%)** | **47/55 (85.45%)** | **8** |

**2 SWU 차감은 구현 코드 삭제나 실패 횟수 증가가 아니라 설계 변경으로 인한 완료 자격 회수**다. 과거 소스 근거 및 49/55 역사적 기록 유지. Codex 새 커밋 `e09b72c9b4cf1ad1ed23312662c655b70446d455`의 6개 부분 구현은 추가 완료 0이다.

## 잔여 8개: 코드 재사용과 실제 일감

| SWU | 종류 | 해야 할 실제 P1 기능 및 코드 경로 | 조건 |
|---|---|---|---|
| **CS-SWU-007** | 독립 안전 소스 후보 | `security/semgrep_adapter.py`: 오프라인 고정 argv/규칙·바이너리 pin, coverage·SHA 재검사 재사용; WSB fallback 대신 승인된 고정 Typed Operator→검사 결과·오류/HOLD 연결 | CS-003/006 완료. Windows scanner 실실행·no-egress는 별도 검증 |
| **CS-SWU-012** | 독립 안전 소스 후보 | `security/defender_status.py`: 파일 SHA·소유자 범위·결과/완료 재검사 보존, 정책 변경 없는 고정 파일검사 연산자 및 핵심 실패 처리 | CS-011 완료. 실제 Defender 스캔/소유자 액션은 승인·검증 전 HOLD |
| **MLA-SWU-038** | 기존 완료 자격 회수, 설계 재작업 | `orchestrator.py`·`app.py`: `preview_codeshield_sandbox_fallback` 제거, Controller→Pure typed/nonexecuting candidate→CodeShield→F18 대기→HOLD/SQLite 연결 | MLA-011/023/027 소스 완료. source-only 작업 후보 |
| **CS-SWU-014** | 기존 완료 자격 회수, 설계 재작업 | `controller/codeshield.py`·`orchestrator.py`: `preview_semgrep_sandbox_fallback` 및 WSB 계획 API 제거; 기존 CodeShield dispatch/hard-stop 복구 | CS-007 이후. MLA-038과 `orchestrator.py` 동시 쓰기 금지 |
| **MLA-SWU-015** | Pure Player 실행 경로 재설계 | `ax_runtime/isolation_runner.py`: AppContainer 워커 대신 로컬 Qwen 텍스트 패치, 안전 path/SHA 검토, 고정 Typed Operator만 허용, 원본/실행 차단 유지 | 원래 MLA-008→015 DAG·수용조건/GO 보존. 생성 코드 실행은 미허용 |
| **MLA-SWU-031** | 네트워크 정책 재설계 | `ax_runtime/isolation_runner.py`: AppContainer SID·capability·loopback 검사 제거, 명시적 no-network typed operator 선택과 외부 호출 거부/HOLD. 실제 OS egress attestation을 달성한 것으로 주장 금지 | MLA-015·021 이후. 015와 같은 파일, 순차 |
| **MLA-SWU-008** | 보호 owner 신뢰 차단 | `state/consent.py`: CNG·PID/SID·SHA/nonce/lease 검증 클라이언트 보존, 보호된 owner signer/key/승인 발급 주체 연결 미완 | 실제 OS 계정·ACL·키/서비스 변경 별도 GO |
| **MLA-SWU-021** | 독립 F18 신뢰 차단 | `review/protected_reviewer.py`: 정책·서명·nonce·lease 검증 보존, 독립 보호 검수 주체/영수증 미구현. 같은 프로세스 self-review/모델 PASS 불인정 | MLA-008 및 MLA-020 선행, 실제 독립 보안 증거 HOLD |

## 진행 순서 및 경계

**CPAA 1차 안전 소스 후보:** CS-007, CS-012, MLA-038. 기존 큐의 `first_ready=[]`는 강제 변경하지 않고 다음 실행 때 HEAD·실제 allowed_paths·의존 DAG를 점검한다. 이후 MLA-038 → CS-014(공통 `orchestrator.py`), MLA-015 → MLA-031(공통 `isolation_runner.py`) 순차 작업. 보호 owner/F18은 독립 위험 차단으로 처리.

**기존 완료 후보 47개:** MLA: MLA-SWU-001, MLA-SWU-002, MLA-SWU-003, MLA-SWU-004, MLA-SWU-005, MLA-SWU-006, MLA-SWU-007, MLA-SWU-009, MLA-SWU-010, MLA-SWU-011, MLA-SWU-012, MLA-SWU-013, MLA-SWU-014, MLA-SWU-016, MLA-SWU-017, MLA-SWU-018, MLA-SWU-019, MLA-SWU-020, MLA-SWU-022, MLA-SWU-023, MLA-SWU-024, MLA-SWU-025, MLA-SWU-026, MLA-SWU-027, MLA-SWU-028, MLA-SWU-029, MLA-SWU-030, MLA-SWU-032, MLA-SWU-033, MLA-SWU-034, MLA-SWU-035, MLA-SWU-036, MLA-SWU-037, MLA-SWU-039. CodeShield: CS-SWU-001, CS-SWU-002, CS-SWU-003, CS-SWU-004, CS-SWU-005, CS-SWU-006, CS-SWU-008, CS-SWU-009, CS-SWU-010, CS-SWU-011, CS-SWU-013, CS-SWU-015, CS-SWU-016. 기존 코드 중 관련 설명·비실행 호출의 오염이 발견되면 다시 보수적으로 판정한다.

**기능 한계:** EAI식 CPU-first Pure Player의 고정 Typed Operator는 임의 생성 Python/JS/PowerShell·생성 테스트·패키지 훅을 안전하게 실행시키는 OS 샌드박스가 아니다. 전체 임의 실행을 제거한 설계에서는 과거 MLA-015의 실행 기능, MLA-031의 실제 OS no-egress, F18 동적 실행 수용 조건을 자동 달성으로 처리할 수 없다. 기존 REQ/수용·허용경로·2+2를 보존하고 `DESIGN_REPLACEMENT_PENDING_HIGH_ACCEPTANCE`로 추적하며, 범위 변경/실서비스 GO는 별도 승인.

**검증·안전:** P2 `LOCKED/UNASSESSED`. owner signer, 독립 F18, 실 네트워크 송신 차단, 원본 Git CAS, Windows 실기기: `NOT_RUN/HOLD`. 기존 CI `44147705467` (Codex 코드 SHA) 성공은 비실행 합성 범위다. 이번 재산정은 계산기 기대값·큐·인수인계만 갱신했으며 Windows OS·main·Production·원본·보안 권한은 변경하지 않았다.
