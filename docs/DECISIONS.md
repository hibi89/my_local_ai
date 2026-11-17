# My Local AI 의사결정 로그 — 2026-11-17

- D01 A EAI 완성 후 병합 / B 두 repo 런타임 결합 / **C 새 단일 repo의 provenance-pinned 선별 이식** 중 C 선택: 속도·비용·운영 관리 균형. 원본 repo 0 수정.
- D02 **My Local AI가 독립적인 자율개발 제품이며 자체 Controller가 결정·스케줄·승인 Gate를 소유.** EAI는 재사용하는 일부 기술의 출처이며 선택적 AdvisorPort일 뿐. EAI 원본 INPUT-only 규칙은 원본 EAI에만 해당하고, My Local AI의 로컬 Qwen 코딩 워커는 코드 생성·수정 가능.
- D03 16GB 장비는 1 모델 직렬 실행 시작; 3B/4B, 8K context 초기값을 비교 후 확정, 성능 숫자는 미측정.
- D04 F18 독립 review 신뢰 경계 CRITICAL; 모델/게스트 자기 PASS 거부. guest+host 무분리 reviewer 방식 폐기.
- D05 SQLite one-writer WAL과 git ref SHA CAS, no forced replay, 1 fix/HOLD/다른 독립 READY 수행.
- D06 로컬 CLI/코어 우선, 웹 UI는 후순위. 공개 포트 없음/외부 cloud 기본 OFF.
- D07 안전한 Git worktree, remote push/PR/실프로젝트 적용은 owner GO, main/Production 변경 금지.
- D08 전체 구현 100% 후보 vs 실제 공식 검증% vs 실제 운영 GO 분리. 정본 분모 REQ 32개와 승인 가중치 기반. 미확정은 UNASSESSED.
- D09 2026-11-21~22 주말은 실행 목표일 뿐 납기 약속/완성 증거 아님.
- D10 선택적 Hydrogen 연구는 별도 사용 승인/계정 무료 한도/외부 데이터 보안 게이트. 필수 로컬 코딩 경로에 의존시키지 않음.

모든 결정 변경 시 변경 이유, 대안 비교, 보안/권리 영향, rollback, 사용자 승인 기록을 남긴다.
