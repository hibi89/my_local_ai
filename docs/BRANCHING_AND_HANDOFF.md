# My Local AI — 브랜치/병렬 개발/인수인계

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
