# AGENTS — My Local AI 통합 프로젝트 (2026-11-17 KST)

## 임무 잠금
유일 대상: `hibi89/my_local_ai`. EAI CPU 판단과 AX Dev Factory의 코딩 실행기를 하나의 로컬 개인용 프로그램으로 통합한다. 다른 크몽 상품·중앙 GitHub App·해커톤으로 전환 금지. 기존 두 레포 코드는 원본 보존; 새 레포에서만 선택적으로 이식하고 변경한다.

## 정본 확인 순서
1. repo / branch / 실제 HEAD 확인
2. `AGENTS.md`
3. `HANDOFF.md` → `STATUS.md`
4. `REQUIREMENTS.md` → `docs/FINAL_BLUEPRINT.md` → `docs/INTEGRATION_CONTRACT.md` 및 `docs/SECURITY_MODEL.md`
5. 실제 코드/테스트/`INSTANT_TASK_QUEUE.json` → 첫 READY

## 사용자가 확정한 작업 순서
High: 최초 전체 설계·REQ 전수·보안·BE/FE·DB/API·비용/복구·작업 큐 → Instant: 여러 READY 묶음 구현 후보 100%까지 코드 작성 → 구현 완료 후보 후 전체 CI·통합/보안·결함 수정 → Codex Sol Max(기술) / Astra Max(UI) 독립 검수 → High 최종 인수 → 사용자 실제 운용 GO. `ㄱ`/`ㄱㄱ`은 현재 프로젝트의 승인된 다음 READY 실제 수행. 설계 승인 전 실행 작업은 설계 수정만 가능.

## 불변 설계
- EAI 독립 CPU CognitionEngine이 작업 선택/근거 판단·검증 권한을 갖는다. EAI에서 Qwen은 입력 분류 전용. **AX 코딩 워커 내부 Qwen은 코드 초안 생성 가능**, EAI의 판단권·승인권 소유 금지.
- AX Dev Factory F01–F20의 작업 계약·격리 Git 작업트리·SQLite 복구·1회 수정 후 HOLD·의존성·원본 보호 기준을 누락 없이 마이그레이션한다.
- 모델/게스트가 작성한 테스트 PASS 영수증은 독립 증거 아님. F18 신뢰 경계가 실제 분리/검증되기 전에는 미검증 코드를 원본/중요 브랜치에 자동 승격하지 않는다. 안전 우회·비격리 호스트 fallback 금지.
- 리스크나 데이터권한 변경은 즉시 검사. 개발 중 불필요한 전체 CI 대기 금지하나 기존 필수 CI/브랜치 보호 해제 금지.
- 외부 Hydrogen/유료 서비스/고객 자료 외부 전송/GitHub App 권한·remote push/PR/OS startup/Production/배포/보안 정책 변경은 사전 승인. 모델은 자체 권한을 늘릴 수 없다.
- PUBLIC repo: .env, 토큰, 모델 가중치, 비밀 프롬프트/고객 자료·민감 소스/DB/개인 경로·실제 실행 로그 원본 업로드 금지. 외부 데이터 업로드·원본 덮어쓰기 금지.
- 작업 결과는 실제 SHA, PASS/FAIL/SKIP/NOT_RUN, 근거 환경, 차단/복구, 다음 READY로 기록. 공식 검증률은 사용자 승인 가중치 없으면 UNASSESSED. 구현 후보와 검증 완료/출시 승인 구별.
- main 직접 변경·임의 병합·force push·커밋 신원 위조/이메일 임의변경 금지. 두 번 개선 없는 재시도 STOP/PIVOT. 정상 코드·Git 이력 보존.

## 소스 참고점 (원본 수정 불가)
- EAI: `hibi89/EAI@feature/kmong-eai-85-p31-20261112`, 기준 SHA `5186cb1aa7928054d56b1cd0a40ea5943a5b3892`
- AX Dev Factory: `hibi89/Freelancer@tools/ax-dev-factory-local`, 기준 SHA `5ab94180471c7ea86344b691fc77ad5c29989071`
- my_local_ai main 최초 bootstrap SHA `960621d6207e6beb22a7e9480e524988196f3d44`
이 기준 SHA는 설계 확인 기록이며 이식 코드의 검증 SHA가 아니다.
