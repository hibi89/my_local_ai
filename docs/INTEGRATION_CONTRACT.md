# My Local AI — 자체 Controller ↔ 선택적 EAI advisor ↔ AX 코딩 실행기 계약 v1 (설계)

## 입력
`PlanSpec`: `version=1`, `plan_id`, `blueprint{repo,branch,sha}`, `tasks[]`, `approval{status,scope,digest}`. SHA256은 canonical UTF-8 JSON 중복 키 거부, 정렬 키·정규화 정책을 먼저 고정하여 계산한다. 모델이 필드를 수정하거나 승인할 수 없다.

`TaskSpec`: `task_id`(ASCII 3~64), `req_ids`, `depends_on`, `goal`(최대4000자), `allowed_paths`(1~16, exact 상대 경로), `acceptance`, `checks`(허용 argv 배열), `risk`, `resource_budget`, `safety_checks`, `plan_sha`, `source_sha`. 절대·상위·글롭 경로/비정상 Unicode/symlink/reparse/ignored 경로 거부. 바뀐 PlanSpec은 새 승인/새 ID가 필요하다.

## 통합 포트
1. **My Local AI Controller (필수):** 승인된 immutable PlanSpec, sanitised READY 목록, DAG/자원/권한/단계 Gate를 자체 검증하고 안전한 WorkOrder를 선정한다. EAI가 꺼져 있어도 동일한 결정·상태 전이가 가능해야 한다.
2. **EAI-derived AdvisorPort (선택):** task_id + priority_reason의 `AdvisorProposalV1`만 출력한다. 명령·경로·테스트·권한·VERIFIED 추가 금지. advisor 장애/비활성 시 Controller deterministic baseline으로 계속한다.
3. **AX 실행기:** `WorkOrderV1`의 plan/task SHA, owner approval, DAG prerequisite, baseline, allowed paths, lease generation을 재확인한 뒤 로컬 코드 생성만 수행한다.
4. Qwen 코딩: `CodeRequestV1`에 한정된 작업·허용 파일만 노출. 모델 반환은 `CandidateDiffV1`이며 항상 UNTRUSTED.
5. 리뷰: `TrustedReceiptV1`에서 trust_boundary_id, reviewer_tool_sha, exact candidate_sha, approved_plan_sha, checks[{argv_id,environment,exit_code,result}], fencing_token 기록. 게스트 서명/영수증만으로 PASS 금지.
6. Git 통합: `IntegrationRecordV1`은 valid reviewer receipt와 동일 SHA/lease/원본 파일 identity/plan 승인확인 후 격리 local ref만 변경.
7. evidence: `EvidenceSummaryV1`은 req_id, status, feature SHA, test scopes/counts, environment, NOT_RUN 및 HOLD만 공개 가능. raw prompt/고객 경로/토큰/파일 내용은 제외.

## 状態 전이
`QUEUED → READY → LEASED → CODING → REVIEW_PENDING → VERIFIED` 또는 `REPAIR_ONCE → REVIEW_PENDING → HOLD`. `AWAITING_OWNER`/`INTERRUPTED`/`BLOCKED_DEPENDENCY` 독립 표현. `VERIFIED`는 모델 주장 아닌 trust verifier의 권한 결과만. lease generation이 다르거나 이전 run_id인 결과는 자동 승격 거부.

## 합성 스펙 예시 — 실행 승인 아님
```json
{
  "version": 1, "plan_id": "SYNTHETIC-EXAMPLE",
  "blueprint": {"repo": "hibi89/my_local_ai", "branch": "dev/instant-implementation-v1", "sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
  "approval": {"status": "NOT_APPROVED", "scope": "SYNTHETIC_ONLY", "digest": null},
  "tasks": [{
    "task_id": "SYNTH-001", "req_ids": ["REQ-04"], "depends_on": [],
    "goal": "Modify only an artificial demo function",
    "allowed_paths": ["examples/synthetic/demo.py"],
    "acceptance": ["Synthetic unit test returns expected output"],
    "checks": [["python", "-m", "unittest", "tests.test_synthetic"]],
    "risk": "LOW", "resource_budget": {"max_calls": 2, "max_seconds": 120},
    "safety_checks": ["DISPOSABLE_WORKTREE", "NO_REMOTE"],
    "plan_sha": null, "source_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }]
}
```
Fake SHA + NOT_APPROVED intentional. Never accept this example as a real signed task.

## 정책
No arbitrary shell. No auto PR/remote push, payment, Windows startup, external Hydrogen/cloud request or original repo write from any model/advisor/controller without distinct owner GO. Actual implementation must pin schemas with tests and include explicit rollback.
