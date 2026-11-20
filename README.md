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

1. 웹 GPT가 준 지시를 **웹 GPT 지시문**에 그대로 붙여넣고 **보내고 작업 시작**을 누릅니다. 메시지의 GitHub 파일·이슈 주소나 저장소·브랜치·문서 경로를 읽습니다. 비공개 문서는 이 PC의 `gh` 로그인에 읽기 권한이 필요합니다. **예제 넣기**로 먼저 시험할 수 있습니다.
2. 인수인계의 **작업 목록** 아래에 파트 제목을 넣으면 MLA가 순서대로 표시합니다. 파트에 `작업 파일: src/date_tools.py`와 `변경 내용: 원하는 동작`이 모두 있으면 `qwen3:4b-instruct`가 해당 파트의 초안을 순서대로 작성합니다. 검증 중심 파트는 실제 오류나 변경 조건을 확인한 뒤 선택해 초안을 요청할 수 있습니다. 로컬 파일을 기준으로 작업하려면 `기존 작업 폴더: C:\Projects\my-app`을 함께 적습니다.
3. 결과에서 변경 비교, 전체 파일, 저장 경로와 사용 문서를 확인합니다. 긴 문서는 작업과 관련된 부분을 발췌하고 사용한 분량을 표시합니다. **이번 작업 시간**은 자료를 읽기 시작할 때부터 저장 또는 오류까지 걸린 시간입니다. **누적 작업 시간**은 초안 저장 폴더 단위로 이 버전부터 자동 기록됩니다.

작업표에는 전체와 현재 파트의 예상·경과 시간이 표시됩니다. 실행 검증 시간을 추정할 수 없는 항목은 미산정으로 표시합니다. 앱을 다시 열면 같은 초안 저장 폴더에서 파트 목록과 진행 기록을 불러옵니다. 작업대 상단의 **음악 켜기**와 **다음 곡**으로 오리지널 배경음악 세 곡을 들을 수 있습니다.

GitHub 저장소의 검증 파트는 기준 커밋에서 관련 파일, 구문, 수동 실행 선언과 기존 CI 기록을 읽고 다음 파트로 이동합니다. 각 파트의 **읽기 검사 결과**에서 확인한 자료와 실제 실행이 필요한 단계를 볼 수 있습니다. 구체적인 수정이 필요할 때는 해당 파트의 **직접 수정 초안 요청**을 엽니다.

같은 지시문을 다시 보내면 저장된 작업표와 남은 단계가 나타납니다. **읽기 결과 다시 조회**로 기준 커밋의 파일과 CI 기록을 새로 조회할 수 있습니다. 실행 검증이 아직 필요한 때에는 작업대의 **작업 보류** 카드에서 해당 파트와 필요한 조건을 확인할 수 있습니다.

파트 초안을 만들 때 Qwen 연결이나 출력 형식 문제는 파트당 최대 세 번 시도합니다. 실패한 파트의 기록을 남기고 다음 독립 파트를 진행합니다. `선행 작업: P2-A` 또는 `Depends on: P2-A`가 붙은 파트는 해당 선행 작업의 실행 검증 결과를 기다립니다. **MLA.exe 프로세스가 계속 실행되는 동안** 브라우저 탭만 닫아도 독립 초안/읽기 확인은 이어집니다. **현재 단계 뒤 일시정지**를 누르면 실행 중인 유한 단계가 끝난 뒤 추가 파트를 시작하지 않으며, **장시간 자동 진행 재개**로 다시 이어갑니다. 같은 로컬 저장 폴더에서 재실행하면 이전에 활성화된 자동 진행 설정과 완료된 파트를 복구합니다. 중단 도중 완료 여부가 불확실한 파트는 `HOLD`로 남겨 자동 중복 실행하지 않습니다.

### 여러 시간·여러 날 작업 지시문 예시

다음처럼 **작업 목록** 아래에 실제 파일/변경 내용을 별도 파트로 적습니다. 파일 경로는 해당 프로젝트의 `allowed_paths`와 일치해야 합니다. 단일 일반 질문은 한 번의 초안 생성으로 끝날 수 있습니다.

```text
## 작업 목록
### SWU-01. 첫 파일 수정
작업 파일: src/example_a.py
변경 내용: 입력값의 형식을 검사하는 validate 함수를 구현한다.
### SWU-02. 독립된 두 번째 파일 수정
작업 파일: src/example_b.py
변경 내용: 잘못된 입력의 오류 메시지를 반환하도록 구현한다.
```

같은 파일을 바꾸는 SWU가 여러 개 있으면 충돌하는 뒤쪽 파트만 **검토·통합 보류**로 표시하고 다른 독립 파트는 계속합니다. 저장한 초안을 GitHub 원본으로 자동 반영하지 않습니다. 정확한 GitHub 커밋 SHA가 같은 원본 파일은 제한된 메모리 캐시에서 재사용하며, 작업대에 재사용 횟수를 표시합니다. JSON/TOML 초안은 구문만 검사해 오류 시 제한적으로 다시 작성합니다. 실제 성능 향상은 아직 미측정입니다.

서버가 열려 있는 동안 Qwen 한 모델이 순차적으로 **별도 폴더에 초안만 생성**하고, 실제 테스트 실행/코드 승격·P2·Windows Owner/F18/Defender·유료 외부 API는 자동 승인하지 않습니다. 처리 가능한 파트가 없으면 `검토·검증·승인 대기`로 멈춥니다. 같은 초안 저장 폴더로 MLA.exe 두 개를 열면 로컬 OS 잠금으로 **두 번째 실행을 거부**합니다. Windows 절전·전원 꺼짐·프로세스 종료 중에는 자동 작업이 진행되지 않으며, OS 서비스/시작프로그램/절전 정책을 임의 변경하지 않습니다. 실제 Windows 11의 수일 연속 시험은 아직 수행하지 않았습니다.

Gemini 조언을 쓰려면 MLA를 실행하는 환경에 `MLA_GEMINI_API_KEY`를 설정합니다. Gemini 3.5 Flash-Lite에는 정해진 오류 코드와 몇 번째 시도인지 전달합니다. 연결할 수 없는 경우 MLA가 로컬 재시도를 이어갑니다.

Qwen 출력은 별도 폴더에 텍스트로 저장하며 Python 파일은 구문을 검사합니다. GitHub Actions 기록은 해당 커밋의 기존 결과를 읽습니다. 명시적으로 승인해 실행한 고정 REQEA 수동 워크플로는 **기존 실행 결과 다시 확인(읽기 전용)** 버튼으로 종료 후에도 중복 실행 없이 재조회할 수 있습니다. 로컬 다중 SWU 초안은 Qwen 모델을 최대 90초 재사용할 수 있으나 실제 VRAM·속도 향상은 미측정입니다. 실제 실행 검증과 GitHub 반영은 보호 실행 환경과 별도 승인에 따라 진행합니다.

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
