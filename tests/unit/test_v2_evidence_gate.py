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
