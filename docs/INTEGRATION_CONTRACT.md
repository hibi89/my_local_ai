# My Local AI — CPU EAI ↔ AX 실행기 계약 v1 (설계)

## 입력
`PlanSpec`: `version=1`, `plan_id`, `blueprint{repo,branch,sha}`, `tasks[]`, `approval{status,scope,digest}`. SHA256은 canonical UTF-8 JSON 중복 키 거부, 정렬 키·정규화 정책을 먼저 고정하여 계산한다. 모델이 필드를 수정하거나 승인할 수 없다.

`TaskSpec`: `task_id`(ASCII 3~64), `req_ids`, `depends_on`, `goal`(최대4000자), `allowed_paths`(1~16, exact 상대 경로), `acceptance`, `checks`(허용 argv 배열), `risk`, `resource_budget`, `safety_checks`, `plan_sha`, `source_sha`. 절대·상위·글롭 경로/비정상 Unicode/symlink/reparse/ignored 경로 거부. 바뀐 PlanSpec은 새 승인/새 ID가 필요하다.

## 통합 포트
1. EAI 입력: 승인된 immutable PlanSpec과 sanitised READY 상태. CPU는 작업 ID + 설명 사유의 `WorkProposalV1`만 출력. 명령·경로·허용범위·테스트·권한 추가 금지.
2. AX 컨트롤러: `WorkOrderV1`에 plan/task SHA, owner approval, DAG prerequisite, source baseline, allowed path digest, lease generation을 재검증. EAI 제안은 advisory이며 최종 스케줄링은 컨트롤러가 검증.
3. Qwen 코딩: `CodeRequestV1`에 한정된 작업·허용 파일만 노출. 모델 반환은 `CandidateDiffV1`이며 항상 UNTRUSTED.
4. 리뷰: `TrustedReceiptV1`에서 trust_boundary_id, reviewer_tool_sha, exact candidate_sha, approved_plan_sha, checks[{argv_id,environment,exit_code,result}], fencing_token 기록. 게스트 서명/영수증만으로 PASS 금지.
5. Git 통합: `IntegrationRecordV1`은 valid reviewer receipt와 동일 SHA/lease/원본 파일 identity/plan 승인확인 후 격리 local ref만 변경.
6. evidence: `EvidenceSummaryV1`은 req_id, status, feature SHA, test scopes/counts, environment, NOT_RUN 및 HOLD만 공개 가능. raw prompt/고객 경로/토큰/파일 내용은 제외.

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
No arbitrary shell. No auto PR/remote push, payment, Windows startup, external Hydrogen/cloud request or original repo write from an EAI proposal. Actual implementation must pin schemas with tests and include explicit rollback.
