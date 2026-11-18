"""Evidence Gate: no verification, owner grant, or execute permission."""
import unittest
from dataclasses import replace

from my_local_ai.experience.evidence_gate import (
    EvidenceQueryV1, EvidenceRecordV1, decide_evidence,
)

_SHA = "a"*64
_GIT = "b"*40


def _query():
    return EvidenceQueryV1(
        project_id="project-001", plan_sha256=_SHA, source_git_sha=_GIT,
        dependency_fingerprint="c"*64, input_contract_digest="d"*64,
        output_contract_digest="e"*64, scanner_rules_sha256="f"*64,
        environment_fingerprint="0"*64, rights_tag="PUBLIC_SYNTHETIC",
        scope_ref="scope-001", desired_effects=("STATIC_READ",),
    )


def _record():
    q = _query()
    return EvidenceRecordV1(
        "receipt-001", "issuer-001", q.project_id, q.plan_sha256,
        q.source_git_sha, q.dependency_fingerprint, q.input_contract_digest,
        q.output_contract_digest, q.scanner_rules_sha256,
        q.environment_fingerprint, q.rights_tag, q.scope_ref,
        ("STATIC_READ",), "ACTIVE", 2000000000,
    )


class V2EvidenceGateTest(unittest.TestCase):
    def test_missing_verifier_is_unknown_not_pass(self):
        decision = decide_evidence(_query(), _record(), checked_at=1795000000)
        self.assertEqual(decision.state, "UNKNOWN")
        self.assertEqual(decision.candidate_refs, ())
        self.assertFalse(decision.independent_f18_verified)

    def test_authenticated_reference_is_still_only_advice(self):
        observed = []
        def resolver(ref, issuer):
            observed.append((ref, issuer))
            return True
        decision = decide_evidence(
            _query(), _record(), checked_at=1795000000,
            trusted_receipt_check=resolver,
        )
        self.assertEqual(observed, [("receipt-001", "issuer-001")])
        self.assertEqual(decision.state, "REUSABLE_ADVICE")
        self.assertEqual(decision.permitted_use, "ADVICE_ONLY")
        self.assertFalse(decision.can_execute)
        self.assertFalse(decision.owner_go)
        self.assertFalse(decision.receipt_reissued)

    def test_source_and_rule_drift_require_revalidation(self):
        for field, replacement in (
            ("source_git_sha", "1"*40),
            ("scanner_rules_sha256", "2"*64),
            ("dependency_fingerprint", "3"*64),
            ("plan_sha256", "4"*64),
        ):
            with self.subTest(field=field):
                q = replace(_query(), **{field: replacement})
                result = decide_evidence(q, _record(), checked_at=1795000000,
                                         trusted_receipt_check=lambda *_: True)
                self.assertEqual(result.state, "REVALIDATION_REQUIRED")
                self.assertEqual(result.candidate_refs, ())
                self.assertTrue(result.revalidation_tasks)

    def test_revocation_expiry_privacy_and_effects_fail_closed(self):
        for record in (
            replace(_record(), state="REVOKED"),
            replace(_record(), state="QUARANTINED"),
            replace(_record(), expires_at=1795000000),
        ):
            self.assertEqual(
                decide_evidence(_query(), record, checked_at=1795000000,
                                trusted_receipt_check=lambda *_: True).state,
                "REVOKED",
            )
        for q in (
            replace(_query(), scope_ref="scope-999"),
            replace(_query(), project_id="project-999"),
            replace(_query(), desired_effects=("READ_ONLY_ANALYSIS",)),
        ):
            self.assertEqual(
                decide_evidence(q, _record(), checked_at=1795000000,
                                trusted_receipt_check=lambda *_: True).state,
                "UNKNOWN",
            )

    def test_verifier_errors_and_self_claims_do_not_grant_permission(self):
        def broken(*_):
            raise RuntimeError("offline")
        self.assertEqual(
            decide_evidence(_query(), _record(), checked_at=1795000000,
                            trusted_receipt_check=broken).state, "UNKNOWN",
        )
        with self.assertRaises(ValueError):
            replace(_query(), desired_effects=("SHELL_EXECUTE",))
        with self.assertRaises(ValueError):
            replace(
                decide_evidence(_query(), None, checked_at=1795000000),
                can_execute=True,
            )


if __name__ == "__main__":
    unittest.main()



class V2NativeControllerGateTest(unittest.TestCase):
    def synthetic_plan(self):
        import json
        task={
            "task_id":"TASK-A","req_ids":["REQ-05"],"depends_on":[],
            "goal":"synthetic static","allowed_paths":["src/a.py"],
            "acceptance":["synthetic"],"checks":[],"risk":"LOW",
            "resource_budget":{"max_calls":1,"max_seconds":10},
            "safety_checks":["NO_REMOTE"],"plan_sha":None,
            "source_sha":"b"*40,
        }
        return json.dumps({
            "version":1,"plan_id":"GATE-SYNTH-001",
            "blueprint":{"repo":"hibi89/my_local_ai",
                         "branch":"dev/instant-implementation-v1",
                         "sha":"b"*40},
            "approval":{"status":"NOT_APPROVED",
                        "scope":"SYNTHETIC_ONLY","digest":None},
            "tasks":[task],
        })

    def invoke(self,states=None,**changes):
        from my_local_ai.contracts.plan import PlanSpec
        from my_local_ai.experience.evidence_gate import (
            controller_dependency_digest,preview_controller_evidence,
        )
        plan_json=self.synthetic_plan()
        plan=PlanSpec.parse_json(plan_json)
        q=replace(
            _query(),
            plan_sha256=plan.digest,
            dependency_fingerprint=controller_dependency_digest(plan,"TASK-A"),
        )
        data=dict(
            plan_json=plan_json,
            protected_states=states or {"TASK-A":"READY"},
            task_id="TASK-A",query=q,record=None,
            checked_at=1795000030,expected_project_id="project-001",
            expected_rules_sha256=q.scanner_rules_sha256,
        )
        data.update(changes)
        return preview_controller_evidence(**data)

    def test_ready_decision_is_still_unknown_and_inert(self):
        r=self.invoke()
        self.assertEqual(r.status,"ADVICE_EVALUATED")
        self.assertEqual(r.evidence.state,"UNKNOWN")
        self.assertFalse(r.owner_go)
        self.assertFalse(r.execution_allowed)
        self.assertFalse(r.f18_verified)

    def test_native_hold_does_not_consume_past_evidence(self):
        r=self.invoke(states={"TASK-A":"HOLD"})
        self.assertEqual(r.status,"NOT_READY_HOLD")
        self.assertIsNone(r.evidence)

    def test_source_rule_dependency_drift_is_hard_hold(self):
        for changes in (
            {"expected_rules_sha256":"f"*64},
            {"expected_project_id":"other-project"},
        ):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.invoke(**changes)
