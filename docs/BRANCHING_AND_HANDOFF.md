> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

# My Local AI — 브랜치/병렬 개발/인수인계

## 제품 독립성
My Local AI는 EAI 자체를 개발하는 저장소가 아니다. EAI의 제한된 분석 알고리즘과 AX 실행기를 선택적으로 참고하며 자체 Controller/정본을 갖는다. 제품 코드 구현·검증률은 원본 프로젝트와 절대 합산하지 않는다. 자세한 내용 `docs/PRODUCT_IDENTITY.md`.

## 브랜치 구성
`main` = 사용자 생성 empty repo를 위한 최초 README bootstrap SHA `960621d6207e6beb22a7e9480e524988196f3d44`. 기존 소스 없는 안정 기준. 승인 없는 병합·force push·직접 소스 변경 금지.
`design/final-blueprint-v1` = High 전체 설계·정본. 본 폴더 문서의 최신 HEAD가 기준. 승인된 설계가 변경되면 새 SHA를 dev에 명시적으로 동기화.
`dev/instant-implementation-v1` = High 문서 기반 Instant 구현. 3~10 독립 READY 묶음, 기존 필수 CI·보안 검사 보존, 구현 후보 후 전수 검증.
`experiment/local-model-benchmarks` = 합성 모델/하드웨어 관련 코드·벤치마크 분리; 제품 코드 자동 병합 금지.
`review/codex-solmax-<SHA>` 및 `review/astra-max-<SHA>`는 실제 구현 후보 동일 SHA에서만 향후 생성, 지금은 미생성.

## 커밋/동기화
- 프롬프트/토큰·개인 repo 원본은 public 저장소에 넣지 않음. 원본 EAI·Freelancer 읽기 전용.
- Commit Author/Committer는 연결 계정 기준, 임의 이메일 대체/이력 변경 금지.
- 구현 PR은 정확 SHA·허용 경로·REQ·국소 PASS/FAIL/NOT_RUN·보안/복구를 기록. independent audit의 실행 증거 없으면 review UNVERIFIED.
- Release/main/Production·remote push/권한/고객 자료는 별도 사용자 GO.

## 재개 시 읽기
repo+branch+최신 HEAD→AGENTS→HANDOFF→STATUS→REQUIREMENTS+FINAL_BLUEPRINT→소스/테스트/INSTANT_TASK_QUEUE→next READY. 구형 개발 지침이나 문서-only SHA가 현재 안전 정책/기능 증거를 덮지 않음.


---

## V1.1 설계의 dev 안전 동기화
- 설계 브랜치 \`design/final-blueprint-v1\`의 Hydrogen 탈부착 워커 **설계 문서와 확장 큐**를 기준으로 한다. \`dev/instant-implementation-v1\`는 P1 소스를 구현 중이므로 기존 P1 큐·STATUS/HANDOFF·코드를 설계 브랜치의 구형 스냅샷으로 덮어쓰지 않는다.
- dev 담당자는 최신 design HEAD의 \`docs/FINAL_BLUEPRINT.md H\`, \`docs/DETACHABLE_MULTI_MODEL_WORKERS.md\`, \`docs/OPTIONAL_PROVIDER_TASK_QUEUE.json\`을 참조하고, High가 정확 SHA·allowed_paths·의존성을 확인한 뒤에만 확장 작업을 시작한다. 문서 동기화 시 dev HEAD와 파일 충돌 점검.
- Hydrogen은 별도의 API 개발 워커로서 **수동 웹 Instant 세션을 자동 구동한다고 가정하지 않는다**. 원격 API·외부 데이터/결제·PR/권한 변경은 계속 별도 GO.
