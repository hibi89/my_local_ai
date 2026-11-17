# 원본 코드 출처·라이선스·이식 경계 — 2026-11-17

| 참조 원본 | 기준 정확 HEAD | 최초 재사용 계획 |
|---|---|---|
| `hibi89/EAI@feature/kmong-eai-85-p31-20261112` | `5186cb1aa7928054d56b1cd0a40ea5943a5b3892` | CPU input/plan/receipt, 13 typed goals 호환성 |
| `hibi89/Freelancer@tools/ax-dev-factory-local` | `5ab94180471c7ea86344b691fc77ad5c29989071` | AX runtime/SQLite/queue/Worktree/OpenCode/F18 안전장치 |
| `hibi89/my_local_ai@main` | `960621d6207e6beb22a7e9480e524988196f3d44` | 빈 repo 초기 README baseline |

기존 EAI·AX 저장소 파일, feature/main, 고객 원본, 모델 설치/가중치, DB, Git 히스토리는 보존하고 새 저장소에서만 파일별 소스 이식. 이식하는 각 파일마다 provenance(manifest){source_repo,branch,commit_sha,blob_sha,target_path,license,adaptation_diff,test_map,reviewer} 기록. 라이선스·3rd party NOTICE·권리 확인 후 복사. 원본 라이선스 미검토 시 `BLOCKED_PROVENANCE`; 사용자 소유 코드라도 외부 의존성 재배포권 자동 보장 금지. 성공한 기존 CI를 새 repo PASS로 이월하지 않음.

최종 목표는 실행 때 기존 EAI/Freelancer repo 동시 설치를 요구하지 않는 **단일 코드베이스/단일 실행 패키지**, 임시 어댑터/선별 이식으로 점진 완성. 외부 런타임 도구 Ollama/OpenCode와 로컬 모델은 OS 별도 의존성으로 표기하고 자동 무단 설치하지 않는다.
