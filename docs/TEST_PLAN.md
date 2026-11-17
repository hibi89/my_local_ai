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
