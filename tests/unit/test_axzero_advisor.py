"""Read-only AXZERO discovery never grants execution or nonfree API use."""
import json
import unittest
from my_local_ai.advisors.axzero import (
    CapabilityQueryV1,inspect_axzero_capability,preflight_controller_axzero,
)

SOURCE="a"*40

def query():
    return CapabilityQueryV1(
        "request-001","static-inspect","b"*64,"c"*64,
        ("STATIC_READ",),SOURCE,"scope-001",
    )

def catalog(**changes):
    item={
        "version":1,"origin":"AXZERO_READ_ONLY_CAPABILITY",
        "capability_id":"capability-001","task_type":"static-inspect",
        "artifact_sha256":"d"*64,"policy_sha256":"e"*64,
        "evidence_ref":"evidence-001",
        "evidence_sha256":"f"*64,
        "input_contract_digest":"b"*64,"environment_fingerprint":"c"*64,
        "allowed_effects":["STATIC_READ"],"source_git_sha":SOURCE,
        "scope_ref":"scope-001","approved_for_execution":False,
    }
    item.update(changes)
    return json.dumps(item)

def synthetic_plan():
    task={
        "task_id":"TASK-A","req_ids":["REQ-05"],"depends_on":[],
        "goal":"synthetic-static","allowed_paths":["src/a.py"],
        "acceptance":["synthetic"],"checks":[],"risk":"LOW",
        "resource_budget":{"max_calls":1,"max_seconds":10},
        "safety_checks":["NO_REMOTE"],"plan_sha":None,"source_sha":SOURCE,
    }
    return json.dumps({
        "version":1,"plan_id":"AXZ-SYNTH-001",
        "blueprint":{"repo":"hibi89/my_local_ai",
                     "branch":"dev/instant-implementation-v1","sha":SOURCE},
        "approval":{"status":"NOT_APPROVED","scope":"SYNTHETIC_ONLY",
                    "digest":None},"tasks":[task],
    })

class AXZEROAdvisorTest(unittest.TestCase):
    def inspect(self,raw=None):
        return inspect_axzero_capability(
            query(),catalog_json=raw,
            pinned_artifact_sha256="d"*64,pinned_policy_sha256="e"*64,
            pinned_evidence_sha256="f"*64,
        )

    def test_missing_defaults_to_qwen_without_execution(self):
        item=self.inspect()
        self.assertEqual(item.decision,"REQUEST_MODEL")
        self.assertEqual(item.selected_provider,"LOCAL_QWEN_CANDIDATE_ONLY")
        self.assertFalse(item.execution_allowed)
        self.assertEqual(item.actual_model_calls,0)

    def test_exact_pins_can_only_request_approval(self):
        item=self.inspect(catalog())
        self.assertEqual(item.decision,"REQUIRE_APPROVAL")
        self.assertFalse(item.f18_verified)
        self.assertFalse(item.owner_go_verified)
        self.assertFalse(item.git_write_allowed)
        self.assertEqual(item.evidence_sha256, "f"*64)

    def test_tampering_unknown_contract_and_effects_fail_closed(self):
        for raw in (
            catalog(artifact_sha256="0"*64),
            catalog(evidence_sha256="0"*64),
            catalog(evidence_sha256="INVALID"),
            catalog(scope_ref="scope-999"),
            catalog(allowed_effects=["SHELL"]),
            catalog(approved_for_execution=True),
            catalog(command="powershell -nop"),
            '{"version":1,"version":1}',
        ):
            with self.subTest(raw=raw):
                self.assertEqual(self.inspect(raw).decision,"REQUEST_MODEL")
        with self.assertRaises(ValueError):
            CapabilityQueryV1(
                "request-001","static-inspect","b"*64,"c"*64,
                ("SHELL",),SOURCE,"scope-001")

    def test_evidence_pin_absent_or_mismatched_cannot_request_execution(self):
        self.assertEqual(
            inspect_axzero_capability(
                query(), catalog_json=catalog(), pinned_artifact_sha256="d"*64,
                pinned_policy_sha256="e"*64,
            ).decision, "REQUEST_MODEL",
        )
        self.assertEqual(
            inspect_axzero_capability(
                query(), catalog_json=catalog(), pinned_artifact_sha256="d"*64,
                pinned_policy_sha256="e"*64,pinned_evidence_sha256="0"*64,
            ).decision, "REQUEST_MODEL",
        )

    def test_controller_refuses_nonready_or_mismatched_source(self):
        off=preflight_controller_axzero(
            plan_json=synthetic_plan(),states={"TASK-A":"READY"},
            task_id="TASK-A",query=query(),catalog_json=None,
        )
        self.assertEqual(off.decision,"REQUEST_MODEL")
        held=preflight_controller_axzero(
            plan_json=synthetic_plan(),states={"TASK-A":"HOLD"},
            task_id="TASK-A",query=query(),catalog_json=catalog(),
        )
        self.assertEqual(held.decision,"BLOCK")


if __name__=="__main__":
    unittest.main()
