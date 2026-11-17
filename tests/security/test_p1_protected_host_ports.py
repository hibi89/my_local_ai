"""P1 immediate safety guards: Windows trust root is not guest-forgeable.

All inputs are synthetic; no Git mutation, Windows process, model, network,
protected key provisioning, owner grant issuance or independent F18 occurs.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from my_local_ai.ax_runtime.isolation_runner import (
    WindowsIsolationHold, prepare_windows_no_egress_profile,
    prepare_offline_coder_transport, decode_untrusted_coder_outbox,
    require_host_isolated_coder_runner,
)
from my_local_ai.ax_runtime.opencode_worker import PreparedOpenCodeRun
from my_local_ai.contracts.approval import OwnerGrant
from my_local_ai.review.trusted_runner import (
    build_reviewer_policy, prepare_review_request, plan_isolated_reviewer,
)
from my_local_ai.review.protected_reviewer import (
    HostCheckObservation, ProtectedReviewerHold,
    canonicalize_fixed_review_observations, require_protected_reviewer_issuer,
)
from my_local_ai.state.consent import (
    inspect_owner_local_plan_consent, require_protected_owner_identity,
)
from my_local_ai.state.sqlite_store import initialize_state

A="a"*40
B="b"*40
F="f"*64


class ProtectedOwnerConsentSafetyTests(unittest.TestCase):
    def test_claim_with_guest_supplied_hmac_key_is_not_owner_os_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"owned.sqlite3"
            initialize_state(db)
            grant=OwnerGrant(
                "synthetic001",F,A,"LOCAL_PLAN",1,1000,
                "nonce00001","0"*64,
            )
            out=inspect_owner_local_plan_consent(
                json.dumps({"version":1,
                            "grant_id":grant.grant_id,
                            "plan_sha256":grant.plan_sha256,
                            "source_git_sha":grant.source_git_sha,
                            "scope":grant.scope,
                            "issued_at":grant.issued_at,
                            "expires_at":grant.expires_at,
                            "nonce":grant.nonce,
                            "signature":grant.signature}),
                owned_state=db,expected_plan_sha256=F,
                expected_source_sha=A,now_seconds=10,
                protected_key_reader=lambda _id,_scope:b"x"*32,
            )
            self.assertFalse(out.signature_matches_and_live)
            self.assertFalse(out.protected_owner_principal_verified)
            self.assertFalse(out.can_start_worker)
            with self.assertRaises(PermissionError):
                require_protected_owner_identity(
                    out, protected_os_session={"is_owner":True}
                )


class ProtectedReviewTranscriptSafetyTests(unittest.TestCase):
    def _intent_and_checks(self):
        policy=build_reviewer_policy()
        request=prepare_review_request(
            task_id="TEST-001",run_id="RUN-001",candidate_sha=B,
            source_sha=A,plan_sha256=F,lease_epoch=1,
            trusted_required_argv_ids=tuple(x.check_id for x in policy.checks),
        )
        intent=plan_isolated_reviewer(
            request,policy,protected_reviewer_binary_sha256=F,
            trusted_source_sha=A,trusted_plan_sha256=F,
            trusted_candidate_sha=B,
        )
        checks=tuple(HostCheckObservation(x.check_id,0,20,False,F)
                     for x in policy.checks)
        return intent,checks

    def test_fixed_success_observations_are_still_unsigned_untrusted(self):
        intent,checks=self._intent_and_checks()
        transcript=canonicalize_fixed_review_observations(intent,checks)
        self.assertFalse(transcript.reviewer_os_attested)
        self.assertFalse(transcript.trusted_receipt_issued)
        self.assertFalse(transcript.may_promote)
        with self.assertRaises(ProtectedReviewerHold):
            require_protected_reviewer_issuer(
                transcript,independent_os_principal_evidence=True,
                owner_signer_evidence=True,
            )

    def test_missing_failed_or_mutated_checks_rejected(self):
        intent,checks=self._intent_and_checks()
        variants=(
            checks[:-1],
            (replace(checks[0],exit_code=1),)+checks[1:],
            (replace(checks[0],timed_out=True),)+checks[1:],
            (replace(checks[0],check_id="CUSTOM-000"),)+checks[1:],
            (replace(checks[0],elapsed_ms=61000),)+checks[1:],
        )
        for observations in variants:
            with self.subTest(observations=observations), self.assertRaises(
                ProtectedReviewerHold
            ):
                canonicalize_fixed_review_observations(intent,observations)


class WindowsOfflineCoderSafetyTests(unittest.TestCase):
    def _transport(self):
        profile=prepare_windows_no_egress_profile(
            task_id="TEST-001",run_id="RUN-001",
            role="CODER",source_sha=A,plan_sha256=F,
        )
        prepared=PreparedOpenCodeRun(
            task_id="TEST-001",plan_sha256=F,source_sha=A,
            allowed_paths=("src/demo.py",),worktree="C:/mlaguest/scratch",
            argv=("opencode","run","--standalone","--archived",
                  "--agent","build","--model","ollama/qwen3:4b-instruct",
                  "--format","json","SYNTHETIC"),
            environment=(("OLLAMA_HOST","http://127.0.0.1:11434"),),
            prompt="SYNTHETIC",
        )
        return prepare_offline_coder_transport(profile=profile,prepared=prepared)

    def test_guest_outbox_valid_shape_never_promotes(self):
        transport=self._transport()
        raw=json.dumps({
            "version":1,"task_id":"TEST-001","run_id":"RUN-001",
            "transport_sha256":transport.request_sha256,
            "output_sha256":F,"declared_paths":["src/demo.py"],"exit_code":0,
        }).encode()
        result=decode_untrusted_coder_outbox(raw,transport)
        self.assertEqual(result.state,"UNTRUSTED_CODER_OUTBOX_F18_REQUIRED")
        self.assertFalse(result.candidate_independently_verified)
        self.assertFalse(result.may_promote)
        self.assertFalse(transport.model_executed)
        with self.assertRaises(WindowsIsolationHold):
            require_host_isolated_coder_runner(
                transport,protected_broker={"owner":True}
            )

    def test_guest_cannot_expand_path_or_forge_transport_sha(self):
        transport=self._transport()
        payload={
            "version":1,"task_id":"TEST-001","run_id":"RUN-001",
            "transport_sha256":transport.request_sha256,
            "output_sha256":F,"declared_paths":["src/demo.py"],"exit_code":0,
        }
        for override in (
            {"declared_paths":["../owner/.env"]},
            {"transport_sha256":A},
            {"exit_code":1},
            {"declared_paths":["src/demo.py","src/demo.py"]},
        ):
            mutated={**payload,**override}
            with self.subTest(override=override), self.assertRaises(
                WindowsIsolationHold
            ):
                decode_untrusted_coder_outbox(
                    json.dumps(mutated).encode(),transport,
                )
        with self.assertRaises(WindowsIsolationHold):
            decode_untrusted_coder_outbox(
                b'{"version":1,"version":1}',transport,
            )


if __name__=="__main__":
    unittest.main()
