# 원본 코드 출처·라이선스·이식 경계 — 2026-11-17

| 참조 원본 | 기준 정확 HEAD | 최초 재사용 계획 |
|---|---|---|
| `hibi89/EAI@feature/kmong-eai-85-p31-20261112` | `5186cb1aa7928054d56b1cd0a40ea5943a5b3892` | 유용한 일부 CPU 분석·분류/근거 유틸만 선택적 재사용; 원본 13 goals 이식은 필수 아님 |
| `hibi89/Freelancer@tools/ax-dev-factory-local` | `5ab94180471c7ea86344b691fc77ad5c29989071` | AX runtime/SQLite/queue/Worktree/OpenCode/F18 안전장치 |
| `hibi89/my_local_ai@main` | `960621d6207e6beb22a7e9480e524988196f3d44` | 빈 repo 초기 README baseline |

기존 EAI·AX 저장소 파일, feature/main, 고객 원본, 모델 설치/가중치, DB, Git 히스토리는 보존하고 새 저장소에서만 파일별 소스 이식. 이식하는 각 파일마다 provenance(manifest){source_repo,branch,commit_sha,blob_sha,target_path,license,adaptation_diff,test_map,reviewer} 기록. 라이선스·3rd party NOTICE·권리 확인 후 복사. 원본 라이선스 미검토 시 `BLOCKED_PROVENANCE`; 사용자 소유 코드라도 외부 의존성 재배포권 자동 보장 금지. 성공한 기존 CI를 새 repo PASS로 이월하지 않음.

최종 목표는 실행 때 기존 EAI/Freelancer repo 동시 설치를 요구하지 않는 **단일 코드베이스/단일 실행 패키지**, 임시 어댑터/선별 이식으로 점진 완성. 외부 런타임 도구 Ollama/OpenCode와 로컬 모델은 OS 별도 의존성으로 표기하고 자동 무단 설치하지 않는다.

## 2026-11-17 — MLA-001 실제 읽기 전용 원본 조사

- EAI 기준 commit `5186cb1aa7928054d56b1cd0a40ea5943a5b3892` 루트 contents 조회: `LICENSE` 없음. 후보 `eai/decision_engine.py` blob `119d112d7d756dc320adfcda9e12214b6c534fb2`, `eai/resource_schedule.py` blob `1324f96da2f20ded0c2903bc24e3619537c72f4c`.
- AX 기준 commit `5ab94180471c7ea86344b691fc77ad5c29989071` 루트 contents 조회: `LICENSE` 없음. 후보 `axdev/core.py` blob `c4fc2f4c5f5547e7225566a1baa9ee0e3ccada07`, `axdev/opencode_guard.py` blob `170478dd45e97f809ed11085b295f9528005df2f`, `axdev/windows_sandbox_runtime.py` blob `421951b3658a7f72e2889ded6a54c1f5bfacb02f`.
- 위 결과는 **해당 루트의 파일명과 후보 blob 확인**만 의미한다. 전체 서브트리의 NOTICE/라이선스·제3자 권리·소유자 재사용 권한은 미확인. `LICENSE` 부재가 자동으로 이용 금지를 확정하는 것은 아님.
- `docs/IMPORT_MANIFEST.json`은 원본 복사 없이 출처만 기록하고, `scripts/audit_sources.py`의 오프라인 읽기 전용 검사에서 `BLOCKED_PROVENANCE` 유지. `tests/unit/test_source_audit.py`는 합성 변조 차단만 검사.
- 해당 5개 후보 원본 소스 코드의 실제 이식/수정/배포는 **미실시**. EAI와 AX 원본 저장소 및 브랜치 무변경.

## 2026-11-17 MLA-001 고정 전체트리 감사 보강

- GitHub 읽기전용 재귀 tree 조회: EAI 고정 SHA `5186cb1a...` → tree `0144655d7e7fd837e9f5efef7d91d5c489467f48`, **191개 항목**, truncated=false. AX 고정 SHA `5ab94180...` → tree `abbf9dd919f91f1b6e9566e7d582988c6ba32b73`, **123개 항목**, truncated=false.
- 통상적인 `LICENSE/LICENCE/NOTICE/COPYING/COPYRIGHT` 기반 이름을 포함하는 파일명은 두 고정 트리에서 찾지 못했다. **파일명 검사만 수행**했으므로 코드 내부 권리 고지나 실제 소유·재사용권에 관한 결론 아님. 후보 5개 원본 blob SHA를 고정 트리에서 일치 확인했으며 제3자 코드 권리/라이선스와 소유자 권한은 여전히 미확인이다.
- EAI 대상 브랜치 현재 HEAD `af57af08e0d71fb656c76be241944e8cf232a57a`는 기존 고정 SHA와 다름. AX 브랜치 HEAD는 고정 SHA 일치. 새 SHA로 임의 재고정하지 않음.
- `audit_sources.py`는 고정 tree/blob·목록 완전성 진술 변조, 숨겨진 항목 삭제 및 자체 허가 주장 차단. 오프라인 스크립트 자체는 실 GitHub API를 조회하지 않으므로 원격 현재 SHA 검증 아님.
- **`BLOCKED_PROVENANCE` 유지, 소스 이식 0건.** 복사 없이 신규 My Local AI 자체 코드를 작성하는 것은 가능하지만, High의 명시적 의존성/권리 재판정 없이 MLA-008·014 READY 해제 또는 새 P1 완료 REQ 산입 금지.


## 2026-11-17 MLA-028 optional EAI data-only adapter (clean-room)

- `src/my_local_ai/advisors/eai.py` contains native original JSON boundary code, **no EAI module imported or source copied**. External optional EAI analysis may later pass bounded hints through a separate isolated adapter; its source-pin and plan digest are compared but not accepted as legal provenance or owner approval.
- `inspect_optional_eai` returns `OFF` or `INVALID_OR_UNAVAILABLE_FALLBACK` on empty/malformed/authority-bearing input. It returns only allowed READY task IDs and integer rank hints with `executable=false`. My Local AI's native Controller always retains DAG/risk/approval judgment.
- No external API, user original input, private source, actual model execution or Windows isolation test in this P1 patch. Original source reuse remains **BLOCKED_PROVENANCE** and the full MLA-028 runtime dependency is not waived.


## 2026-11-17 P1 source-only Controller integration (MLA-008/028)

The native \`Controller.propose(..., optional_eai_envelope_json=...)\` consumes the
existing bounded offline EAI *data envelope* only after independent plan/DAG/
lease candidate selection. The envelope's exact plan SHA256, blueprint Git SHA
and eligible task set must match. Rank hints can only reorder eligible tasks
within native immutable risk priorities. Invalid, stale, forged, unavailable,
or disabled EAI hints fall back to the native controller. Passing both a raw
hint and a pinned EAI envelope is refused as ambiguous. The optional adapter
does not import EAI code, run its process, or transmit data.

**No EAI source was copied or relicensed.** MLA-001 remains
\`BLOCKED_PROVENANCE\`; SHA-pinned data is not evidence of copyright license,
F18 review, protected owner consent, real Git authority or runtime approval.
