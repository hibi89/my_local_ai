# MLA 작업대 실행 검증 인수인계

## 2026-11-20 KST — 실제 실행 브리지 및 Windows EXE 증거 (최신)

- 구현/빌드 기준 SHA: `7e20f77a3318c76e6c5befdd078a156633425e0d` on `dev/instant-implementation-v1`; Windows unsigned packaged EXE, actual runner-hosted loopback workbench HTML request: [Actions #44569179722](https://github.com/hibi89/my_local_ai/actions/runs/44569179722) **SUCCESS**; synthetic CI [#44569179564](https://github.com/hibi89/my_local_ai/actions/runs/44569179564) **SUCCESS**. Windows build artifact: `MLA-Windows-workbench-unsigned-EXE`, ID `14554595730` (GitHub Actions run artifacts; retention 7 days). Actual owner Windows 11 test: **NOT_RUN**.
- 실제 backend: `approved_workflow.py` adds a fixed public read-only GitHub Actions `REQEA-P2-E-MANUAL-CLI-AUDIT-SMOKE` execution path for `hibi89/REQ-Evidence-Auditor-A-@integration/reqea-p1-20261118`, `reqea-audit.yml` (`fc98f672173926b0364b472235d7ba1593a1efeb`), only `docs/FINAL_BLUEPRINT.md`. GitHub CLI and its existing local authentication required. The initial owner click records an intent first, sends one workflow_dispatch, then observes the remote Actions run SHA, ID, timestamp, conclusion and link, with explicit PASS/FAIL/HOLD and no automatic re-dispatch after crash or ambiguous result. Manual click is required, not arbitrary clipboard execution.
- Workbench UI: P2-E inspection-selected item shows an explicit `승인된 REQEA 수동 CLI 감사 실제 실행 (1회)` button, result/trace, and P2 acceptance remains 0. Recorded `PASS` is only the particular remote CLI audit smoke and **not** P2-A/entire REQEA 14-gate verification, independent security audit, F18 or automatic source defect correction. Generated code/tests execution remains blocked under existing protected-execution rules.
- Owner next action: download/use the EXE from Actions artifact, on own Windows 11 run in writable folder, with existing authenticated GitHub CLI authorized for the target REQEA repository's Actions workflow dispatch; paste original instruction; select inspected P2-E and click once. Preserve the displayed exact target SHA/run ID/outcome. No permission/secret/OS provisioning or commercial GO is implied. **Actual workflow_dispatch execution with existing owner auth NOT_RUN**, current model environment lacks the owner's Windows GitHub CLI token; full P2-A suite and the other five parts are **NOT_IMPLEMENTED/HOLD**.
- The original 2026-11-19 below documents the **prior missing execution scheduler** as historical context; it is not the current state for the one approved P2-E smoke. Canonical MLA P1 source candidate 55/58, P2 accepted 0/8, official UNASSESSED/LOCKED, release HOLD.


작업 브랜치는 `dev/instant-implementation-v1`입니다. 아래 확인 결과는 작업대 소스 커밋 `02a47de9bd6632fc81f2804647e35580a5e72494`에 해당합니다. 재개할 때는 브랜치 최신 HEAD에서 저장소 지침과 단계 잠금을 먼저 확인합니다. 작업대에 제출된 지시문의 `P2-A`는 대상 프로젝트의 파트 이름입니다. MLA 자체 검증 단계는 별도 게이트에 따릅니다. [저장소 지침](../AGENTS.md) · [MLA 단계 게이트](PHASE_GATES.md)

## 구현 및 확인한 범위

- 작업대는 붙여넣은 인수인계에서 파트를 분리하고 GitHub 문서와 CI 기록을 기준 커밋에 고정해 읽습니다. 명시된 파일과 변경 내용은 로컬 Qwen이 초안으로 작성합니다. 브라우저 결과는 진행, 저장, 보류를 표시합니다.
- 초안의 일시적 실패는 파트당 첫 시도를 포함해 최대 3번 시도합니다. 실패 이력을 저장하고 진행 가능한 독립 파트를 처리합니다. Gemini 3.5 Flash-Lite는 키 설정 시 정해진 오류 코드와 시도 번호만 받아 복구 방법을 제안합니다. 이 경로는 모의 호출로 확인했습니다. 실제 API 호출은 `NOT_RUN`입니다.
- Windows에서 MLA 자체 테스트 700개가 통과했고 25개가 건너뛰어졌으며 하위 테스트 801개가 통과했습니다. Chrome에서 저장된 지시 재제출, 보류 안내, 파트 이동, 실제 GitHub 읽기 재조회를 확인했습니다. 별도의 합성 작업에서 실제 Qwen이 작은 Python 초안을 생성하고 저장했습니다.
- 문제가 된 작업표는 6개 파트의 읽기 확인을 마쳤고 실제 테스트 실행은 0건입니다. 당시 대상 기준 커밋에는 조회된 CI 실행 기록이 없었습니다. 실제 검증과 독립 검증의 결과는 `NOT_RUN`입니다.

## 현재 멈추는 위치

`LocalDrafts._start_next_item_locked()`에는 자료 읽기와 초안 작성 경로가 있습니다. 실제 테스트를 예약하고 결과를 받는 경로가 빠져 있습니다. 상태 응답의 `verified_count`가 `0`으로 고정되어 있고, 읽기 확인을 마친 파트는 `실행 검증 보류`를 반환합니다. 따라서 같은 지시를 보내도 저장된 파트의 실행은 시작되지 않습니다. [작업대 스케줄러와 상태 응답](../src/my_local_ai/ax_runtime/manual_draft.py) · [읽기 증거](../src/my_local_ai/ax_runtime/draft_evidence.py)

Pure Player는 후보를 비실행 상태로 검사합니다. 승인된 실행 범위와 결과를 확인할 수 있는 실행 환경이 필요합니다. 기존 Zero-VM 정책과 보호 소유자 승인, 독립 F18, 단계 게이트를 적용합니다. 보호 실행 환경이 확인되지 않으면 구체적인 사유와 함께 `HOLD` 및 `NOT_RUN`을 기록합니다. [최종 설계](FINAL_BLUEPRINT.md) · [보호 경계](SECURITY_MODEL.md) · [Pure Player 구현](../src/my_local_ai/ax_runtime/isolation_runner.py)

## 첫 구현 목표

1. **P2-A의 승인된 백엔드·CLI 통합 테스트 한 건을 실행하고 작업대에 실결과를 표시합니다.** 사용자가 승인한 저장소·기준 SHA·검토된 테스트 ID에 실행 요청을 묶습니다. 기존 실행 계약과 승인 경로를 확인한 뒤 범위가 고정된 테스트만 실제 실행 환경에 넘깁니다.
2. **결과를 실행과 연결합니다.** 기준 SHA, 테스트 ID, 실행 ID, 시작·종료 시각, 종료 코드, 근거 로그나 CI 링크를 기록합니다. 작업대에서 `대기`, `실행 중`, `PASS`, `FAIL`, `HOLD`, `NOT_RUN`을 구분합니다. 통과 결과의 독립 검증 여부에는 별도 근거를 적용합니다.
3. **재시작과 후속 진행을 연결합니다.** 같은 실행이 중복 시작되지 않도록 요청과 결과를 저장합니다. 선행 결과가 실제로 충족된 파트를 이어서 처리하고, 복구 가능한 오류는 파트당 최대 세 번 시도합니다. 막힌 파트의 이유를 남겨도 독립 파트는 진행합니다. 승인이나 실행 환경이 필요한 보류는 작업대에서 즉시 볼 수 있어야 합니다.

완료 근거는 P2-A 한 건의 실제 실행 결과입니다. 테스트 성공과 실패가 상태에 반영되는지, 권한이 빠진 경우 `NOT_RUN`으로 남는지, 같은 지시 재제출과 작업대 재시작이 실행을 중복하지 않는지 확인합니다. 다음 파트의 실제 실행과 장시간 관찰은 각각의 테스트와 근거가 준비되면 이어서 진행합니다.

## Windows 테스트 전달물

P2-A 실행 기능을 구현한 커밋으로 Windows x64용 `MLA.exe`를 빌드해 다운로드 가능한 파일로 첨부합니다. 빌드 기준 SHA와 Windows 확인 결과를 함께 전달합니다. Windows에서 실행 파일을 열어 작업대가 뜨는지 확인한 뒤, 그 실행 파일에서 승인된 P2-A를 실행해 종료 결과와 로그가 표시되는지 확인합니다.

빌드 환경은 Windows x64, Python 3.11, PyInstaller 6.22.3입니다. 저장소 루트에서 다음 명령을 실행하면 `dist/mla-workbench/MLA.exe`가 생성됩니다.

    py -3.11 -m PyInstaller --distpath dist/mla-workbench --workpath build/mla-workbench scripts/mla_workbench_windows.spec

사용자는 `MLA.exe`를 쓰기 가능한 폴더에 저장하고 더블클릭해 작업대를 엽니다. Python은 실행 파일에 포함됩니다. Qwen 초안을 쓰려면 같은 PC에서 Ollama와 `qwen3:4b-instruct`가 필요합니다. 진행 기록과 초안은 기본적으로 실행 파일 옆의 `mla-drafts`에 저장됩니다. 기존 작업은 `--draft-root`로 저장 폴더를 지정해 열 수 있습니다.

## 실행과 확인에 참고할 코드

작업대 실행 명령은 README에 있습니다. 진행 표시와 버튼 처리, 초안 실패 복구의 구현과 기존 테스트는 다음 파일에 있습니다. [실행 안내](../README.md#로컬-qwen-작업대) · [작업대 화면](../src/my_local_ai/ui/workbench.js) · [Gemini 복구 조언](../src/my_local_ai/ax_runtime/draft_recovery.py) · [회귀 테스트](../tests/unit/test_manual_draft.py)
