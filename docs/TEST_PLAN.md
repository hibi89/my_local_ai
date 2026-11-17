> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

# My Local AI — 검증 계획 / 근거 격리

## P1 국소 검사(모델 코드 구현 중)
- Python compileall/타입·해시된 스키마 입력, pure unit tests, file path/net/auth/SQLite 위험 변경의 즉시검사
- 필수 GitHub CI 비활성화/우회 금지, 그러나 모든 커밋마다 전체 CI 수동 대기하지 않음
- 손상/과금/보안 위험 수정은 단독 국소·regression 증거 필수

## P2 전체 회귀
- Python3.11 Linux / hosted Windows 전체 tests/unit/integration/security/e2e; 실제 CI 실행 URL+SHA+PASS/FAIL/SKIP
- EAI CPU 계획 ↔ AX queue ↔ local model mock ↔ isolated Git checkout ↔ reviewer integration
- 예외: symlink/reparse/ignored, shell/filter/hooks, prompt injection, forged receipt, wrong id/sha, race, duplicate lease, model down, journal/crash, unexpectedly modified source
- signed/offline package & dependency license review; no private payload or hosted Windows charges without approval

## 실제 Windows11 Pro
- 실제 Python/Git/Ollama/OpenCode versions, Windows Sandbox support/virtualization, non-admin/no-egress, actual 3B vs 4B Qwen run, RAM/VRAM, Unicode+space path, stop/resume and F18 attacker tests
- GitHub-hosted Windows ≠ 사용자의 Windows 장비. fake HTTP/model ≠ 실제 추론.
- UX: real browser/desktop/accessibility if present; otherwise NOT_RUN.

## 장시간
승인된 합성 disposable project에서 24h source/plan unchanged, temperature/memory/resource logs local, lock/lease crash/recover, verified task nonduplicate, fail/hang independent READY continue. Hardware safety pending; prohibit unsafe unattended test without preflight.

## 독립 감사/운영
P3 Codex Sol Max 코드/보안, Astra Max UI/사용성 실검수 동일 SHA; P4 High final acceptance; 별도 owner GO. 모든 미실행 명령 NOT_RUN, 새 REQ 공식 검증률 UNASSESSED.
