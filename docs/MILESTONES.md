> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

# My Local AI — 목표일 및 게이트 (약속 납기 아님)

| 시점 | 목표 | 수용 조건 | 차단 |
|---|---|---|---|
| 2026-11-17(화) | 새 repo/High 설계/브랜치/원자 queue | GitHub 정확 HEAD·REQ32 전수·READY5 | 사용자 최종설계 GO |
| 11/18~20 | Instant P1 BE/FE 후보 코드 묶음 | F18 안전 차단 무력화 없이 실제 변경·국소 검사 | 원본 license/소스 이식 검토 |
| 11/21(토) | 통합 합성 E2E | on-device if possible, Qwen 실제 local coding + isolated review | PC/도구 접근, F18 |
| 11/22(일) | stop/resume/장시간 시험 진입 | 실제 실행 증거/안전 중단 및 복구, 24h는 별도 완료 증거 | 발열/메모리/권한/운영 승인 |
| 이후 | P2 전수 CI/보안/실기기 → P3 독립 감사 → P4 High 인수 | REQ/수용근거, 미검증 구분 | 사용자 GO |

개발 중 우선 목표는 실사용 가능한 개인용 자동개발 기능이며 완성률 100%·24시간 무정지·일주일 SKU 수익화 보장은 금지한다.
