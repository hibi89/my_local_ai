# My Local AI (`my_local_ai`)

**목표:** EAI의 독립 CPU 작업 판단·근거 검증 + AX Dev Factory의 Ollama/OpenCode 로컬 코딩·격리·테스트·복구를 **하나의 독립 실행 가능한 개인용 자동개발 시스템**으로 통합한다. 대상: Windows 11 Pro / GTX1050Ti / RAM 16GB. 비용 0원·오프라인 우선, 24시간 승인 작업 큐 처리 지향.

**현재:** 2026-11-17 설계 V1 후보. 코드 구현 0건, 신규 저장소 테스트 NOT_RUN, 구현률·공식 검증률 UNASSESSED, REAL-USE HOLD. 문서만으로 완성 주장 금지.

## 시작 문서
- [AGENTS.md](AGENTS.md): 역할·정본·안전
- [docs/FINAL_BLUEPRINT.md](docs/FINAL_BLUEPRINT.md): 통합 전체 설계
- [REQUIREMENTS.md](REQUIREMENTS.md): REQ-01~REQ-32 전수
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): BE/FE·API·데이터 흐름
- [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md): F18 격리/위협 모델
- [docs/INTEGRATION_CONTRACT.md](docs/INTEGRATION_CONTRACT.md): 버전 고정 인터페이스
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md): 로컬 SQLite·복구
- [docs/ACCEPTANCE_MATRIX.md](docs/ACCEPTANCE_MATRIX.md): 수용조건
- [INSTANT_TASK_QUEUE.json](INSTANT_TASK_QUEUE.json) + [INSTANT_RUNBOOK.md](INSTANT_RUNBOOK.md): 실행 작업 큐
- [STATUS.md](STATUS.md) + [HANDOFF.md](HANDOFF.md): 증거·현재 상태·재개

## 브랜치
- `main`: 최초 안내 baseline, 승인 없이 제품 구현/병합 금지
- `design/final-blueprint-v1`: High 설계 정본
- `dev/instant-implementation-v1`: 설계 승인 후 Instant 구현
- `experiment/local-model-benchmarks`: 합성 모델 성능 실험 격리
- 독립 감사 브랜치는 미래 동일 구현 SHA에서 분기

## 절대 보안
**이 저장소는 PUBLIC.** 고객 자료, 토큰, 개인 프롬프트, 원본 비공개 코드, 모델 파일, 로컬 SQLite/로그·백업, 비밀키 업로드 금지. 기존 EAI·AX 저장소/main·GitHub 권한·Vercel Production·결제/상용화·OS 보안 설정 변경 없음. 실제 원격 push, OS 자동시작, 실프로젝트 적용은 별도 사용자 GO.
