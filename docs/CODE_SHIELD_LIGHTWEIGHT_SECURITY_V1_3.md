# MLA V1.3: CodeShield 경량 사전검수 최종 기술설계

**최종설계 변경 승인: 2026-11-18 KST (OWNER NO-VM NO-CONTAINER OVERRIDE).**
대상: hibi89/my_local_ai 전용 / Windows 11 Pro, GTX 1050 Ti, RAM 16GB, Python 3.11, 기존 Ollama Qwen3 4B.
상태(2026-11-18): HIGH_DESIGN_APPROVED / FEATURE_SOURCE_PARTIAL_13_OF_16_IMPLEMENTED_UNVERIFIED / DEV_CODE_NOT_MERGED / F18_SECURITY_HOLD / P2_LOCKED / OWNER_RUNTIME_GO_FALSE. 과거 본 기술설계 작성 시점의 CODE_NOT_IMPLEMENTED는 역사적 상태다.

## A. 최종 선택과 설계 대안

| 안 | 성능·무료 운영 | 보안·유지보수 | 판단 |
|---|---|---|---|
| A: VM/Windows Sandbox/Hyper-V/WSL2/Docker | 의존성을 0으로 제한 | 사용자 확정 범위에서 설치·실행·fallback 금지 | **전면 비채택** |
| B: 코드체커·백신 PASS → 호스트에서 AI 코드 즉시 실행 | 빠르고 저렴 | 정적 미탐·import/패키지 훅·간접 삭제·외부 송신 | **거부** |
| **C: CPU-first Pure Player + CodeShield 비실행 검사 + 독립 F18** | **Qwen 1개·순차 CPU 검증** | typed operator 허용목록만 실행, 생성물은 데이터/패치로 취급 | **채택** |
| D: Windows 컨테이너/AppContainer | 컨테이너 및 격리 엔진 의존성 배제 | 현행 기본·대안·fallback 어느 경로에서도 사용하지 않음 | **전면 비채택** |

**핵심:** **VM 0, Windows 컨테이너 0, AppContainer 0 (fallback도 0)**. EAI의 CPU-first Pure Player + 고정 Typed Operator 원칙을 MLA에 독립 구현한다. 모델 생성 코드/테스트/설치·빌드 훅·셸 실행은 HOLD이며 비실행 검사가 PASS해도 실행 권한은 없다. 독립 F18·원본 보호·소유자 서명·nonce/lease·Git CAS는 보존한다.

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
| Windows 컨테이너/AppContainer | 사용 금지 | 사용자 확정 Zero Container 정책으로 설치·사용·fallback 제외 | 실행으로 안전 증명 또는 P1 수용 불가 |
| VM/Windows Sandbox/Hyper-V/WSL2/Docker | 사용 금지 | 모든 실행·fallback 의존성 0 | 런타임 경계 대안으로 재도입 금지 |

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
- Windows 컨테이너/AppContainer/VM은 본 설계에서 **비채택**이며 관련 과거 링크는 실행 수단을 승인하지 않는다.
- 해총 GitHub Trending 아이디어: alibaba/open-code-review, cloudflare/security-audit-skill, NVIDIA/SkillEvaluator. arXiv 2611.16289 SatisFix는 요구 누락·자가 합리화 방어 아이디어만 사용. 소스 자동 복사/효과 실증 주장 금지.

## C. 안전 실행 데이터 흐름

High 승인 Plan/REQ/SHA → Controller → disposable worktree → 로컬 Qwen 1개(생성물 비신뢰 텍스트) → AST/path/Git diff/source SHA (생성 코드 실행 없음) → 검증된 Ruff(S)·오프라인 Semgrep CE → 조건부 Gitleaks/OSV/Defender → RiskGate(비실행 후보/HOLD) → Pure Player 고정 typed operator만 실행 → 독립 보호 F18·owner consent·CAS → 승인 가능한 비실행 패치 후보/격리 로컬 ref 또는 HOLD.

- **ALLOW_NON_EXECUTING**: 설계, 문서, 텍스트 코드 생성, AST/파일/규칙 정적 읽기와 안전 후보 diff만 허용. "SAFE_TO_EXECUTE"라는 판정 상태는 **만들지 않는다**.
- **UNTRUSTED_EXECUTION_HOLD**: 생성 Python/JS/PowerShell/EXE·테스트·패키지/빌드 훅·임의 셸은 실행 불가. VM이나 Windows 컨테이너 fallback은 없다. 정적 검사 PASS/모델의 판단/일반 승인으로 해제 불가.
- **HOLD_HIGH_RISK**: 고객/개인 비밀·외부 전송, recursive delete·임의 원본 쓰기, Git main/push, 프로덕션, OS/Defender·ACL/네트워크/레지스트리/스케줄러/방화벽 변경, 지갑/결제. action-bound owner GO+SHA+F18 필요.
- **UNKNOWN**: 도구/규칙 누락·종료/timeout 오류·버전/hash 불일치, stale DB, agent-injected 검사 축소, 오탐 논란. 불명확한 실행·승격은 HOLD, 다른 독립 비실행 READY는 계속.
- 외부 설치 파일/README/보안 규칙·Skill은 비신뢰. 서명·결과·LLM 판단으로 owner 권한, 테스트 PASS, reviewer signature를 생성하지 못함. 검사기의 정상 리턴코드도 독립 F18 증거가 아님.
- Scanner는 고정 argv, 고정 경로, 환경변수/credential 제거, no shell, 리소스 상한, 로컬 rule pin, 비민감 이벤트만 상태 기록. GitHub 공개 저장소에 프롬프트·고객 자료·토큰·원본 로그 불허.
- Experience Learning V1.2 positive label은 독립 검수된 SHA/수용 증거만 사용. CodeShield 정적 결과로 성공 학습 자동 승격 금지.

## D. P1·P2 인수 조건 및 성능

**P1:** 별도 CodeShield 8 SWU 큐 CS-01..08은 설계·소스 구현 후보 범위. 첫 READY는 경량 policy/schema/AST/allowed_paths부터. 기존 P1 39 source SWU/30 REQ/28 legacy 작업/8 P2 검증, 현재 35 source candidates와 P2 LOCKED는 변동 금지. 별도 CS 진행 0/8, 설계 문서 커밋으로 기존 구현률 상승 금지. 변경된 최종설계 전체 인수 때 CodeShield 기능을 별도로 평가하여 scope 기준선 명확히 보고.

**P2:** Windows 11 실기기에서 Ruff/Semgrep CLI 해시·옵션, 합성 오탐/미탐, Defender 상태/OSV DB, 경로 재분석/NTFS, **허용목록 Typed Operator와 독립 reviewer/소유자 동의·CAS**, 기본 네트워크 차단·복구·24h를 별도 검증. **VM/컨테이너 호환성 또는 실행 시험은 P2 수용 조건에서 제외**; 임의 생성 코드 실행/안전 PASS는 현재 수용하지 않는다. P2 현재 LOCKED/UNASSESSED.

**성능 목표 (미실측):** VM·Windows 컨테이너·AppContainer 추가 상주 프로세스 0, 추가 GPU 모델 0, idle scanner extra RAM ≤200MB(Qwen 제외), Python 10파일/1MB 순차 정적 검사 ≤90초, owner/F18 우회 0. 효과·VRAM 절감량 `UNMEASURED`; 미달 시 실행 허가가 아니라 개선/HOLD.

## E. 분리 브랜치·롤백

- main: 안정, 승인 없는 merge/Production 금지.
- design/final-blueprint-v1: V1.3 최종설계·기술/안전/queue의 **High 정본**.
- dev/instant-implementation-v1: 기존 코딩/상태/39-SWU 정본. 과거 design 큐·STATUS 덮어쓰기 금지; 최신 설계·CS queue는 선별 복제/주석으로 동기화.
- feature/code-shield-lightweight-v1: dev와 분리된 CodeShield P1 소스 브랜치. 2026-11-18 확인 기준 HEAD `06a704016eb5ab0cc59c0e705b49d5908ffd08e3`, 구현 후보 13/16, 나머지 007/012/014 부분 구현·OS/F18 HOLD; dev 코드 자동 반영 아님.
- experiment/local-model-benchmarks: 합성 벤치마크, 제품 자동 병합 금지.
- review/codex-solmax-<exactSHA> 및 review/astra-max-<exactSHA>: 실제 구현 후보 정확 SHA에서만 추후 생성.
- 본 변경은 GitHub 설계 변경만; Windows 설정, PC care/백신 설정, 외부 전송, 유료 설치, 제품 실행/검증 인수는 실행하지 않았다.

## F. 2026-11-18 실제 브랜치·저자원 실행 기준 업데이트

- **VM/Windows Sandbox/Hyper-V/WSL2/Docker·Windows 컨테이너/AppContainer 전부 비채택, fallback도 없음**. 로컬 Qwen 한 개, 비실행 CodeShield와 CPU-first 허용 연산. 실측 VRAM/RAM 절감치는 `UNMEASURED`.
- `feature/code-shield-lightweight-v1` HEAD `06a704016eb5ab0cc59c0e705b49d5908ffd08e3`의 별도 source queue는 **13/16 구현 후보**, 미완료 `CS-SWU-007/012/014`; 원래 8개 CS-01..08은 역사적 설계 작업군. dev의 **35/39(89.74%)**와 독립이며 커밋 병합/통합 검증은 `NOT_RUN`.
- AppContainer·Windows 컨테이너 및 VM은 옵션도 fallback도 아니다. 임의 생성 코드/테스트/설치 훅은 실행 HOLD; F18·owner signature·nonce/lease/Git CAS 실패 시 보호 ref 자동 승격 불가.
- EAI V3.1 CPU-first 순수 메모리 Player는 **계획/허용 연산 원칙 참고용**이다. 실제 AI 생성 코드의 안전 실행 경계로 사용하면 안 된다. P1 구현과 P2 독립 검증, 각자의 REQ·SWU 분모 및 2+2 이력은 유지.
- 개발/상용·권한·방화벽·Defender·원본/비밀·외부 API/유료는 별도 승인 전 변경 금지. 본 갱신은 오직 설계/상태의 동기화이며 실제 모델/Windows 코드 실행과 P2 검증은 하지 않았다.


## G. 2026-11-18 최종 변경 — EAI Pure Player 기반 Zero VM / Zero Container

- **삭제된 설계 의존성:** VM, Windows Sandbox, Hyper-V, WSL2, Docker, Windows 컨테이너, AppContainer 전부 기본·선택·예비 경로에서 제외. 설치·권한 변경·가상화 활성화 없음.
- **구성 확정:** 호스트 Ollama/Qwen 한 개 → 비신뢰 코드 후보를 일회용 worktree에 텍스트로 저장 → MLA 고유 Controller/Plan SHA/scope·원본/비밀 guard → AST + Ruff(S) + 고정 오프라인 Semgrep CE(조건부 Gitleaks/OSV/Defender) → CPU-first 허용목록 Typed Operator(제품 소유·검증된 고정 함수와 고정 argv만) → 별도 F18/owner approval/CAS 검토. 생성 코드 실행기·테스트 런너·임의 셸/설치/빌드는 공급하지 않는다.
- **EAI 참조:** `hibi89/EAI@feature/kmong-eai-85-p31-20261112/docs/EAI_FINAL_BLUEPRINT.md`의 allowlisted operator, scoped plan, quota, observe/verify, fail-closed 패턴만 참조. MLA의 Qwen은 코드 **제안·작성**에 사용할 수 있으나 생성물 **실행** 권한은 없다.
- **기존 소스 드리프트:** 개발 브랜치의 Windows Sandbox WSB/no-egress profile/AppContainer 진단 관련 기능은 역사적 코드일 수 있으므로 설계만 바꿔 완전 제거됐다고 주장하지 않는다. Codex와 파일 충돌 없이 결과 인수 때 제거/차단 여부를 검수한다.
- **수용·신뢰:** 기존 55 SWU/REQ ID·allowed_paths·2+2 이력 보존. VM 기반 MLA-SWU-015/031 기존 수용조건은 새 정책과 충돌하므로 완료로 세지 않고 동일 ID에서 Pure Player 비실행 후보와 native typed operation no-network 계약으로 재설계·검수. F18/원본/owner/CAS/외부전송/보안/유료/Production GO는 이전대로 보존. P2 여전히 LOCKED/UNASSESSED.
