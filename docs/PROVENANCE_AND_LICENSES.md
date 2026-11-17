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
