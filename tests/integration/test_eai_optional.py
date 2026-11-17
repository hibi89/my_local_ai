"""Adapter off/invalid/malicious hints uses native Controller; no original EAI import."""
import json
import unittest

from my_local_ai.advisors.eai import inspect_optional_eai
from my_local_ai.controller.decision import Controller
from my_local_ai.contracts.plan import PlanSpec

SOURCE="a"*40
PLAN="b"*64


def make_env(hints=(), **overrides):
    env={
        "version": 1,
        "origin": "OPTIONAL_EAI_ADVISOR_DATA",
        "source_git_sha": SOURCE,
        "plan_sha256": PLAN,
        "non_authoritative": True,
        "hints": list(hints),
    }
    env.update(overrides)
    return json.dumps(env)


class OptionalEaiEnvelopeTests(unittest.TestCase):
    def inspect(self, payload=None):
        return inspect_optional_eai(
            envelope_json=payload,
            eligible_ids=frozenset({"TASK-A","TASK-B"}),
            trusted_source_sha=SOURCE, trusted_plan_sha=PLAN,
        )

    def test_off_no_engine_import_no_authority(self):
        result=self.inspect()
        self.assertEqual(result.status,"OFF")
        self.assertFalse(result.executable)
        self.assertFalse(result.original_eai_imported)
        self.assertEqual(result.hints,())

    def test_bound_payload_is_data_only(self):
        result=self.inspect(make_env([
            {"task_id":"TASK-B","rank":0},
            {"task_id":"TASK-A","rank":5},
        ]))
        self.assertEqual(result.hints,(("TASK-A",5),("TASK-B",0)))
        self.assertTrue(result.independent_controller_required)
        self.assertFalse(result.executable)

    def test_forged_approval_commands_and_source_sha_are_not_hints(self):
        variants=(
            {"owner_go":True},
            {"commands":["powershell -nop"]},
            {"non_authoritative":False},
            {"origin":"EAI_IS_CONTROLLER"},
            {"source_git_sha":"f"*40},
            {"plan_sha256":"f"*64},
            {"hints":[{"task_id":"TASK-A","rank":0,"allowed_paths":[".env"]}]},
            {"hints":[{"task_id":"UNKNOWN","rank":0}]},
            {"hints":[{"task_id":"TASK-A","rank":0},{"task_id":"TASK-A","rank":1}]},
        )
        for change in variants:
            with self.subTest(change=change):
                r=self.inspect(make_env(**change))
                self.assertEqual(r.status,"INVALID_OR_UNAVAILABLE_FALLBACK")
                self.assertEqual(r.hints,())

    def test_duplicate_json_key_and_nonfinite_fallback(self):
        for value in ('{"version":1,"version":1}', '{"hints":NaN}', "x"*4100):
            self.assertEqual(self.inspect(value).status,"INVALID_OR_UNAVAILABLE_FALLBACK")

    def test_wrong_trusted_pins_denied_even_if_off(self):
        with self.assertRaises(ValueError):
            inspect_optional_eai(envelope_json=None,eligible_ids=frozenset(),
                                 trusted_source_sha="invalid",trusted_plan_sha=PLAN)

    def test_fallback_does_not_change_controller_or_approval(self):
        task={
            "task_id":"TASK-A", "req_ids":["REQ-05"], "depends_on":[],
            "goal":"synthetic", "allowed_paths":["src/demo.py"],
            "acceptance":["synthetic"], "checks":[], "risk":"LOW",
            "resource_budget":{"max_calls":1,"max_seconds":30},
            "safety_checks":["NO_REMOTE"], "plan_sha":None,
            "source_sha":SOURCE,
        }
        obj={
            "version":1,"plan_id":"SYNTH-028",
            "blueprint":{"repo":"hibi89/my_local_ai",
                         "branch":"dev/instant-implementation-v1","sha":SOURCE},
            "approval":{"status":"NOT_APPROVED","scope":"SYNTHETIC_ONLY","digest":None},
            "tasks":[task],
        }
        c=Controller(PlanSpec.parse_json(json.dumps(obj)))
        s={"TASK-A":"READY"}
        before=c.propose(s)
        advisor=self.inspect(make_env(owner_go=True))
        self.assertEqual(advisor.status,"INVALID_OR_UNAVAILABLE_FALLBACK")
        after=c.propose(s,advisory_json=None)
        self.assertEqual(before.decisions,after.decisions)
        self.assertFalse(after.execution_allowed)


if __name__=="__main__":
    unittest.main()



class OptionalEaiControllerIntegrationTests(unittest.TestCase):
    def test_real_controller_contract_can_consume_pinned_data_without_eai_import(self):
        from my_local_ai.controller.decision import Controller
        from my_local_ai.contracts.plan import PlanSpec
        tasks = [
            {"task_id": name, "req_ids": ["REQ-05"], "depends_on": [],
             "goal": "offline synthetic", "allowed_paths": [f"src/{name}.py"],
             "acceptance": ["offline"], "checks": [], "risk": "LOW",
             "resource_budget": {"max_calls": 1, "max_seconds": 5},
             "safety_checks": ["NO_REMOTE"], "plan_sha": None,
             "source_sha": SOURCE}
            for name in ("TASK-A", "TASK-B")
        ]
        obj = {
            "version": 1, "plan_id": "EAI-SYNTH-001",
            "blueprint": {"repo": "hibi89/my_local_ai",
                          "branch": "dev/instant-implementation-v1", "sha": SOURCE},
            "approval": {"status": "NOT_APPROVED", "scope": "SYNTHETIC_ONLY", "digest": None},
            "tasks": tasks,
        }
        controller = Controller(PlanSpec.parse_json(json.dumps(obj)))
        states = {"TASK-A": "READY", "TASK-B": "READY"}
        original = controller.propose(states)
        payload = make_env(
            [{"task_id":"TASK-B","rank":0},{"task_id":"TASK-A","rank":5}],
            plan_sha256=controller._plan.digest,
        )
        selected = controller.propose(states, optional_eai_envelope_json=payload)
        self.assertEqual([x.task_id for x in original.decisions], ["TASK-A", "TASK-B"])
        self.assertEqual([x.task_id for x in selected.decisions], ["TASK-B", "TASK-A"])
        self.assertFalse(selected.verified)
        self.assertFalse(selected.owner_go)
        self.assertFalse(selected.execution_allowed)
