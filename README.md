> **[OWNER-ENFORCED PHASE SPLIT · 2026-11-17 KST · FIRST READ]** 본 프로젝트는 **P1 구현완료율 우선**, **P2 검증완료율 후행**이다. P1=`INSTANT_TASK_QUEUE.json`의 28개 실제 BE/FE 코드 작업(REQ-01~30). P2=`VERIFICATION_TASK_QUEUE.json`의 8개 전체 CI/보안/통합/실기기 검증 작업이며 **`WORK_PHASE_GATES.json`의 P1 구현 100% 후보 + High 인수 + 정확 SHA 게이트 전 LOCKED**. P3 독립 Codex/Astra 감사·P4 High 인수/사용자 GO는 검증 이후 별도. P1 중 전체 CI 수동 반복 대기 금지. **기존 필수 CI는 계속 활성화**, 문법/국소 스모크·인증/권한/비밀/데이터 손실/원본/F18 보안 즉시검사는 절대 생략 금지. `IMPLEMENTED_UNVERIFIED` ≠ `VERIFIED`. 가중치 승인 전 공식 검증완료율 UNASSESSED. **모든 GPT High/Instant, Codex, Astra, OpenCode·후속 채팅은 이 규칙과 `docs/PHASE_GATES.md`를 먼저 읽는다.**

> **[PRODUCT IDENTITY LOCK · OWNER CLARIFICATION · 2026-11-17]** `my_local_ai`는 **EAI의 후속 버전/확장판/완성판이 아니다.** EAI는 선택적으로 재사용할 알고리즘·CPU 분석·도구의 **기술 제공원**일 뿐이다. `my_local_ai`의 고유 목적은 **로컬 모델로 소프트웨어 구현을 지속 자동화하는 개인용 개발 시스템**이며, 정책·스케줄·실행/검증 게이트·진척 기준은 `my_local_ai`가 자체 소유한다. 원본 EAI ADR-0002(Qwen INPUT-only)는 EAI 원본의 아키텍처 지침이지 `my_local_ai`의 코딩 워커 사용 제한이 아니다. EAI 전체 13개 목표·자체 모델 연구의 100% 완료는 `my_local_ai`의 필수 조건이 아니다. 자세한 내용 `docs/PRODUCT_IDENTITY.md`. **P1 구현 우선/P2 검증 잠금 정책은 그대로 유지.**

# My Local AI (`my_local_ai`)

**목표:** EAI에서 유용한 일부 분석 기술과 AX Dev Factory의 Ollama/OpenCode 실행 기술을 선택적으로 재사용해 **My Local AI 고유의 독립적인 24시간 로컬 자율개발 시스템**을 만든다. EAI 자체를 완성·복제·통합 제품으로 이름만 바꾸는 작업이 아니다. 대상: Windows 11 Pro / GTX1050Ti / RAM 16GB. 비용 0원·오프라인 우선, 24시간 승인 작업 큐 처리 지향.

**현재:** `dev/instant-implementation-v1`에서 로컬 운영 대시보드와 구현 후보를 확인할 수 있습니다. 공식 검증률은 미산정이며 Windows 보호 환경과 독립 실행 검증은 보류 상태입니다.

## 로컬 Qwen 작업대

이 PC에서 Ollama를 실행한 상태로 저장소 폴더에서 작업대를 엽니다.

```powershell
$env:PYTHONPATH = 'src'
python -m my_local_ai workbench --open --draft-root '..\mla-drafts'
```

1. 웹 GPT의 작업명령문과 최종설계도를 각 칸에 넣습니다. 텍스트, GitHub의 파일 주소 또는 이슈 주소를 사용할 수 있습니다. 비공개 문서는 이 PC의 `gh` 로그인에 읽기 권한이 필요합니다.
2. 기존 파일을 바꾸려면 프로젝트의 로컬 폴더와 상대 파일 경로를 한 줄에 하나씩 넣습니다. 새 파일이라면 두 칸 모두 비워도 됩니다. 처음에는 **예제 넣기**로 시험할 수 있습니다.
3. **로컬 작업 시작**을 누르면 설치된 `qwen3:4b-instruct`가 파일 초안을 만들고 별도 작업 폴더에 저장합니다. 결과 화면에서 파일, diff, 저장 경로, 사용한 GitHub 커밋을 볼 수 있습니다. 긴 설계도는 작업과 관련된 부분을 발췌하고 사용한 분량을 표시합니다.

작업대는 사용자가 시작하는 초안 생성 경로입니다. Qwen 출력은 텍스트로 저장하며 Python 파일은 구문만 검사합니다. 코드 실행과 GitHub 반영은 별도입니다. 기본 화면은 작업대형이며 상단에서 검토형과 순서형으로 전환할 수 있습니다.

## 로컬 운영 대시보드

작업 브랜치를 내려받은 폴더에서 PowerShell로 실행합니다.

```powershell
$env:PYTHONPATH = 'src'
python -m my_local_ai dashboard --open
```

이 PC의 브라우저에서 구현 후보, 실행 차단 이유, 검증 장부와 리소스 상태를 확인합니다. Python 3.11 이상이 필요합니다. 콘솔에서 `Ctrl+C`로 종료합니다.

## 시작 문서
- [AGENTS.md](AGENTS.md): 역할·정본·안전
- [docs/PRODUCT_IDENTITY.md](docs/PRODUCT_IDENTITY.md): EAI와 완전히 다른 제품 정의·권한·완성 기준
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
