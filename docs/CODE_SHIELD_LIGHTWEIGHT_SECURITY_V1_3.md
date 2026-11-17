# MLA V1.3: CodeShield 경량 사전검수 최종 기술설계

**최종설계 변경 승인: 2026-11-17 KST.**
대상: hibi89/my_local_ai 전용 / Windows 11 Pro, GTX 1050 Ti, RAM 16GB, Python 3.11, 기존 Ollama Qwen3 4B.
상태: HIGH_DESIGN_APPROVED / CODE_NOT_IMPLEMENTED / F18_SECURITY_HOLD / P2_LOCKED / OWNER_RUNTIME_GO_FALSE.

## A. 최종 선택과 설계 대안

| 안 | 성능·무료 운영 | 보안·유지보수 | 판단 |
|---|---|---|---|
| A: Windows Sandbox/VM 항상 실행 | Qwen 외 guest RAM·기동 지연; 16GB에 부담 | OS 격리 증명은 별도, host Ollama 접속 병목 | 기본에서 제외 |
| B: 코드체커·백신 PASS → 호스트에서 AI 코드 즉시 실행 | 빠르고 저렴 | 정적 미탐·import/패키지 훅·간접 삭제·외부 송신 | **거부** |
| **C: CodeShield 사전검수 + 필요시 OS 격리 + 독립 F18** | **Qwen 호스트 1개; 검사기는 순차 실행** | 사전검사 PASS는 실행 권한 아님; 실제 위험 작업에만 보호된 실행기 | **채택** |
| D: AppContainer+Job Object 단독 | VM 대비 경량 가능 | Win32/Python/OpenCode 호환성, egress·ACL·F18 미검증 | P2 경량 옵션 후보 |

**핵심:** 기본 VM OFF, CodeShield ON, 기존 Windows Defender 유지. 이는 VM 전면 폐지가 아니다. AI 생성 코드·테스트·pip/npm 설치 훅·빌드 스크립트·PowerShell처럼 실행 부작용이 있는 작업은 호스트에서 바로 실행하지 않는다. 실제 OS 경계가 입증될 때까지 해당 작업만 HOLD. 원본 파일 변경/보호된 Git ref 승격은 독립 F18 및 owner scope/CAS 필요. 원래 격리/서명/무결성 안전 목표를 축소하지 않는다.

## B. 도입 기술: 사용 범위·라이선스·운영

| 기술 | 우선순위 | 목적과 동작 정책 | 실패/비고 |
|---|---|---|---|
| MLA 내장 path_guard, safe_path, pinned SHA, lease, Git diff | P0 필수 | 원본과 disposable worktree 분리, allowlist, symlink/reparse, ADS, hooks/filter, gitignore, secret path, 삭제·원격·OS 권한 검사 | 원본/DB 손실 위험 시 무조건 HOLD; worktree 자체는 sandbox 아님 |
| Python 3.11 AST + tokenizing | P0 필수 | ast.parse 등 **비실행 파싱**; 파일 크기/AST 노드 수/시간 상한, 악성 구문·동적 import·shell 위험 표시. import/eval/exec/unittest discover/생성 스크립트 실행 금지 | 문법·파싱 실패=HOLD (실행/승격); 정상 AST도 안전하다는 보장은 없음 |
| Ruff (S=flake8-bandit 포함) | P1 기본 | Windows 네이티브 바이너리·버전/해시 검증, 고정 규칙 E4,E7,E9,F,S; 외부 config/플러그인 미신뢰. --isolated, --no-cache, JSON 출력, 검사기 종료코드·파일 SHA 기록 | 자동 설치 금지; 미설치 시 비실행 생성만, 실행/승격 HOLD |
| Semgrep Community Edition | P1 기본 보강 | native Windows 지원. 승인된 **로컬 규칙 YAML만** pin/해시, 파일 삭제·서브프로세스·네트워크·동적 로더·파괴적 SQL 탐지; registry rules, 로그인, telemetry, 원격 업로드, 자동 업데이트 차단 | P1 경량 규칙; 비호환/timeout/미탐/규칙 변조 시 실행 게이트 HOLD |
| Gitleaks CLI | 조건부 필수 | Git commit/remote 전 secret/token 패턴 검사, 로컬만. 정규식 탐지값은 공개 로그/리포트에 미표시 | scanner 미설치·오류=외부 송신 HOLD, 0 findings ≠ 유출 부재 |
| OSV-Scanner | 조건부 필수 | dependency/lock 변경 시만 실행. **사전 승인 취득한 로컬 취약점 DB의 --offline 모드**, cache 날짜/해시 관리. 설치 스크립트는 실행하지 않음 | DB 오래됨/없음=패키지 실행/설치 HOLD; 네트워크 DB 갱신 별도 승인 |
| Windows Defender Antivirus | 기존 OS 선택형 보조 | Get-MpComputerStatus 읽기전용 상태확인. 새 EXE/DLL/ZIP/다운로드 설치파일은 상태·명시적 scan 가능 여부 검토 | 백신 검사 결과는 F18 아님. CFA/예외/정책/백신 중복 설치·실시간 설정 변경은 owner GO |
| Windows AppContainer + 제한 토큰/Job Object | 향후 P2 실제 OS 실험 | 실제 OS 경량 격리 후보. 별도 security principal, 파일 DACL, CPU/RAM/time bound, network egress 차단을 Windows 11 실기기에서 적대적으로 검증 | 이를 검증하기 전 호스트 untrusted code 자동실행 금지 |
| Windows Sandbox | fallback on-demand | AppContainer 불가/고위험 실행에만 선택. guest no-egress/F18, 원본·비밀 접근 거부, 사용자 OS 기능 변경 승인 필요 | 상시 가동·두 번째 Qwen 모델 복사 금지 |

**비채택 기본:** 상주 PC Care 준백신/두 번째 백신 엔진, WSL2/Docker 상시 VM, CodeQL 거대 로컬 상시 검사, Qwen 중복 로딩, 외부 paid 스캔, GitHub trending repo 스킬 자동 실행, 자동 Windows Defender CFA 활성/예외, 무승인 OS/네트워크/방화벽 변경. Microsoft Defender는 위험 패턴 분석/권한 제한의 보조 수단이지 자체 보호 경계가 아님.

**CLI 출처/의존성과 배포권리:** 실제 배포 전 각 binary release SHA/signature, Windows x64 동작, LICENSE/NOTICE, 종속 라이선스 확인. 릴리스 버전/옵션은 P1 도구 설치 여부와 실제 --help 검증 후 pin; 검증하지 않은 릴리스 번호를 정본에 고정하지 않는다. auto pip install, 웹에서 셸 스크립트 받기, remote config, 관리자 권한은 사용하지 않는다.

### 공식 기술 근거
- Python AST: https://docs.python.org/3.11/library/ast.html
- Ruff: https://docs.astral.sh/ruff/rules/ | https://docs.astral.sh/ruff/installation/
- Semgrep native Windows 2025: https://semgrep.dev/blog/2025/semgrep-community-edition-fall-release-2025
- Gitleaks: https://github.com/gitleaks/gitleaks
- OSV offline: https://github.com/google/osv-scanner/blob/main/docs/offline-mode.md
- Windows Defender: https://learn.microsoft.com/en-us/powershell/module/defender/get-mpcomputerstatus | https://learn.microsoft.com/en-us/powershell/module/defender/start-mpscan
- Defender CFA: https://learn.microsoft.com/en-us/defender-endpoint/controlled-folder-access-overview
- AppContainer: https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer
- 해총 GitHub Trending 아이디어: alibaba/open-code-review, cloudflare/security-audit-skill, NVIDIA/SkillEvaluator. arXiv 2611.16289 SatisFix는 요구 누락·자가 합리화 방어 아이디어만 사용. 소스 자동 복사/효과 실증 주장 금지.

## C. 안전 실행 데이터 흐름

High 승인 Plan/REQ/SHA → Controller + live owner plan scope → disposable worktree → Qwen 1개 (호스트, 모델 출력 비신뢰) → AST/path/changed files SHA (실행 없음) → Ruff(S) → 승인된 로컬 Semgrep 규칙 (순차) → 필요 시 Gitleaks/OSV offline/Defender read-only 상태 → RiskGate → (1) ALLOW_NON_EXECUTING 또는 (2) REQUIRES_ISOLATION+HOLD 또는 (3) HOLD_HIGH_RISK → 독립 보호된 reviewer F18/소유자 consent/CAS → isolated local ref 또는 HOLD.

- **ALLOW_NON_EXECUTING**: 설계, 문서, 텍스트 코드 생성, AST/파일/규칙 정적 읽기와 안전 후보 diff만 허용. "SAFE_TO_EXECUTE"라는 판정 상태는 **만들지 않는다**.
- **REQUIRES_ISOLATION**: AI 생성 Python/JS/PowerShell/EXE·테스트·패키지 hook/빌드/외부 의존 코드 실행. AppContainer의 실제 OS 보호 + 독립 verifier가 증명되지 않으면 HOLD. Sandbox 가동도 별도 owner OS scope/기능 사용 허가.
- **HOLD_HIGH_RISK**: 고객/개인 비밀·외부 전송, recursive delete·임의 원본 쓰기, Git main/push, 프로덕션, OS/Defender·ACL/네트워크/레지스트리/스케줄러/방화벽 변경, 지갑/결제. action-bound owner GO+SHA+F18 필요.
- **UNKNOWN**: 도구/규칙 누락·종료/timeout 오류·버전/hash 불일치, stale DB, agent-injected 검사 축소, 오탐 논란. 불명확한 실행·승격은 HOLD, 다른 독립 비실행 READY는 계속.
- 외부 설치 파일/README/보안 규칙·Skill은 비신뢰. 서명·결과·LLM 판단으로 owner 권한, 테스트 PASS, reviewer signature를 생성하지 못함. 검사기의 정상 리턴코드도 독립 F18 증거가 아님.
- Scanner는 고정 argv, 고정 경로, 환경변수/credential 제거, no shell, 리소스 상한, 로컬 rule pin, 비민감 이벤트만 상태 기록. GitHub 공개 저장소에 프롬프트·고객 자료·토큰·원본 로그 불허.
- Experience Learning V1.2 positive label은 독립 검수된 SHA/수용 증거만 사용. CodeShield 정적 결과로 성공 학습 자동 승격 금지.

## D. P1·P2 인수 조건 및 성능

**P1:** 별도 CodeShield 8 SWU 큐 CS-01..08은 설계·소스 구현 후보 범위. 첫 READY는 경량 policy/schema/AST/allowed_paths부터. 기존 P1 39 source SWU/30 REQ/28 legacy 작업/8 P2 검증, 현재 35 source candidates와 P2 LOCKED는 변동 금지. 별도 CS 진행 0/8, 설계 문서 커밋으로 기존 구현률 상승 금지. 변경된 최종설계 전체 인수 때 CodeShield 기능을 별도로 평가하여 scope 기준선 명확히 보고.

**P2:** 실제 Windows 11 Pro/16GB에서 Ruff·Semgrep native 설치·필수 CLI 옵션 검사, 유효/악성 합성 40종 오탐/미탐, 신뢰된 binary SHA/license, Defender 감지 상태, OSV offline DB, 비밀 로그 마스킹, Git path reparse/ADS/NTFS, OS egress/AppContainer 호환/권한/리뷰어 분리 실측, 24h 재기동/복구. P2 시작 전 High exact SHA 게이트 필수, Codex Sol Max 기술 감사·Astra Max FE 감사를 별도로 수행.

**성능 목표 (미실측):** 추가 GPU 모델 0, 기본 OS sandbox 상주 0, idle scanner extra RAM ≤200MB (Qwen 제외), Python 파일 10개/1MB static audit ≤90초 (순차·기기 실측), 중요한 owner/F18 bypass 0. 목표 미달 시 측정·최적화 후 High 판단, 위험 차단 해제 금지.

## E. 분리 브랜치·롤백

- main: 안정, 승인 없는 merge/Production 금지.
- design/final-blueprint-v1: V1.3 최종설계·기술/안전/queue의 **High 정본**.
- dev/instant-implementation-v1: 기존 코딩/상태/39-SWU 정본. 과거 design 큐·STATUS 덮어쓰기 금지; 최신 설계·CS queue는 선별 복제/주석으로 동기화.
- feature/code-shield-lightweight-v1: dev의 최신 정확 SHA에서 생성하는 분리 CodeShield P1 구현 브랜치; 현 단계 기능 코드 NOT_STARTED.
- experiment/local-model-benchmarks: 합성 벤치마크, 제품 자동 병합 금지.
- review/codex-solmax-<exactSHA> 및 review/astra-max-<exactSHA>: 실제 구현 후보 정확 SHA에서만 추후 생성.
- 본 변경은 GitHub 설계 변경만; Windows 설정, PC care/백신 설정, 외부 전송, 유료 설치, 제품 실행/검증 인수는 실행하지 않았다.
