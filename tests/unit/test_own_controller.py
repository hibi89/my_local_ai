"""Controller pure synthetic unit tests; no original EAI import or task launch."""
import json
import unittest

from my_local_ai.controller.decision import Controller
from my_local_ai.contracts.plan import PlanSpec

BASE = "a" * 40


def plan():
    def task(task_id, risk, depends_on=()):
        return {
            "task_id": task_id, "req_ids": ["REQ-05"],
            "depends_on": list(depends_on), "goal": "synthetic-local-controller",
            "allowed_paths": [f"src/{task_id}.py"],
            "acceptance": ["synthetic contract"], "checks": [],
            "risk": risk, "resource_budget": {"max_calls": 1, "max_seconds": 10},
            "safety_checks": ["NO_REMOTE"], "plan_sha": None, "source_sha": BASE,
        }
    value = {
        "version": 1, "plan_id": "CONTROLLER-SYNTH-001",
        "blueprint": {"repo": "hibi89/my_local_ai", "branch": "dev/instant-implementation-v1", "sha": BASE},
        "approval": {"status": "NOT_APPROVED", "scope": "SYNTHETIC_ONLY", "digest": None},
        "tasks": [task("TASK-A", "HIGH"),
                  task("TASK-B", "LOW"),
                  task("TASK-C", "LOW"),
                  task("TASK-D", "LOW", ("TASK-A",))],
    }
    return PlanSpec.parse_json(json.dumps(value))


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = Controller(plan())
        self.states = {name: "READY" for name in ("TASK-A", "TASK-B", "TASK-C", "TASK-D")}

    def test_base_controller_independent_of_eai(self):
        result = self.controller.propose(self.states)
        self.assertEqual([d.task_id for d in result.decisions], ["TASK-B", "TASK-C", "TASK-A"])
        self.assertEqual(result.advisory_status, "DISABLED")
        self.assertFalse(result.execution_allowed)
        self.assertTrue(all(not d.runnable for d in result.decisions))

    def test_advisor_cannot_override_immutable_risk_order(self):
        hint = json.dumps({"version": 1, "hints": [
            {"task_id": "TASK-C", "rank": 0}, {"task_id": "TASK-B", "rank": 3},
            {"task_id": "TASK-A", "rank": 0},
        ]})
        result = self.controller.propose(self.states, advisory_json=hint)
        self.assertEqual([d.task_id for d in result.decisions], ["TASK-C", "TASK-B", "TASK-A"])
        self.assertFalse(result.owner_go)
        self.assertFalse(result.verified)

    def test_injected_permission_in_advisor_is_ignored(self):
        for hint in (
            '{"version":1,"hints":[],"owner_go":true}',
            '{"version":1,"hints":[{"task_id":"TASK-B","rank":0,"allowed_paths":[".env"]}]}',
            '{"version":1,"hints":[{"task_id":"TASK-D","rank":0}]}',
            '{"version":1,"hints":[{"task_id":"TASK-B","rank":0}],"version":1}',
            '{"version":1,"hints":[{"task_id":"TASK-B","rank":true}]}',
        ):
            with self.subTest(hint=hint):
                result = self.controller.propose(self.states, advisory_json=hint)
                self.assertEqual(result.advisory_status, "INVALID_HINTS_IGNORED")
                self.assertEqual([d.task_id for d in result.decisions], ["TASK-B", "TASK-C", "TASK-A"])

    def test_guest_verified_label_does_not_unlock_dependencies(self):
        self.states["TASK-A"] = "VERIFIED"
        result = self.controller.propose(self.states)
        self.assertNotIn("TASK-D", [d.task_id for d in result.decisions])
        protected = self.controller.propose(self.states, independently_verified={"TASK-A"})
        self.assertIn("TASK-D", [d.task_id for d in protected.decisions])
        self.assertTrue(all(not d.runnable for d in protected.decisions))

    def test_active_lease_prevents_duplicate_candidate(self):
        result = self.controller.propose(self.states, active_leases={"TASK-B"})
        self.assertEqual([d.task_id for d in result.decisions], ["TASK-C", "TASK-A"])

    def test_wrong_states_fail_closed(self):
        with self.assertRaises(ValueError):
            self.controller.propose({})
        self.states["TASK-A"] = "SELF_VERIFIED"
        with self.assertRaises(ValueError):
            self.controller.propose(self.states)

    def test_plan_claim_not_authoritative(self):
        p = plan()
        self.assertFalse(p.approved)
        result = self.controller.propose({t.task_id: "READY" for t in p.tasks})
        self.assertFalse(result.owner_go)
        self.assertFalse(result.execution_allowed)


class CodeBatchPlanningTests(unittest.TestCase):
    def setUp(self):
        self.states={name:"READY" for name in ("TASK-A","TASK-B","TASK-C","TASK-D")}
        self.controller=Controller(plan())

    def batch(self, **change):
        values=dict(max_tasks=8,max_total_calls=8,max_total_seconds=200)
        values.update(change)
        return self.controller.propose_code_batch(self.states,**values)

    def test_independent_tasks_can_be_selected_in_one_code_batch(self):
        result=self.batch()
        self.assertEqual(result.task_ids,("TASK-B","TASK-C","TASK-A"))
        self.assertEqual(result.reserved_calls,3)
        self.assertEqual(result.reserved_seconds,30)
        self.assertFalse(result.runnable)
        self.assertEqual(result.model_calls_executed,0)
        self.assertFalse(result.independent_f18_verified)
        self.assertNotIn("TASK-D",result.task_ids)

    def test_max_slots_and_model_budget_are_non_authoritative(self):
        limited=self.batch(max_tasks=2)
        self.assertEqual(limited.task_ids,("TASK-B","TASK-C"))
        self.assertEqual(limited.deferred,(("TASK-A","SLOT_BUDGET"),))
        calls=self.batch(max_total_calls=1)
        self.assertEqual(calls.task_ids,("TASK-B",))
        self.assertEqual([x[1] for x in calls.deferred],
                         ["RESOURCE_BUDGET","RESOURCE_BUDGET"])
        time=self.batch(max_total_seconds=10)
        self.assertEqual(time.task_ids,("TASK-B",))

    def test_exact_casefold_path_conflicts_defers_the_second_task(self):
        raw=json.loads(json.dumps({
            "version":1,"plan_id":"BATCH-SYNTH",
            "blueprint":{"repo":"hibi89/my_local_ai",
                         "branch":"dev/instant-implementation-v1","sha":BASE},
            "approval":{"status":"NOT_APPROVED","scope":"SYNTHETIC_ONLY","digest":None},
            "tasks":[],
        }))
        sample=plan()
        for task in sample.tasks:
            raw["tasks"].append({
                "task_id":task.task_id,"req_ids":list(task.req_ids),
                "depends_on":list(task.depends_on),
                "goal":task.goal,"allowed_paths":list(task.allowed_paths),
                "acceptance":list(task.acceptance),"checks":[],
                "risk":task.risk,"resource_budget":{
                    "max_calls":task.resource_budget.max_calls,
                    "max_seconds":task.resource_budget.max_seconds,
                },"safety_checks":list(task.safety_checks),
                "plan_sha":None,"source_sha":BASE,
            })
        for task in raw["tasks"]:
            if task["task_id"]=="TASK-C":
                task["allowed_paths"]=["src/TASK-B.py"]
        controller=Controller(PlanSpec.parse_json(json.dumps(raw)))
        result=controller.propose_code_batch(
            self.states,max_tasks=4,max_total_calls=4,max_total_seconds=40,
        )
        self.assertEqual(result.task_ids,("TASK-B","TASK-A"))
        self.assertIn(("TASK-C","PATH_CONFLICT"),result.deferred)

    def test_advisor_can_only_reorder_same_risk_code_candidates(self):
        hints=json.dumps({"version":1,"hints":[
            {"task_id":"TASK-C","rank":0},{"task_id":"TASK-A","rank":0}
        ]})
        result=self.batch(advisory_json=hints)
        self.assertEqual(result.task_ids,("TASK-C","TASK-B","TASK-A"))
        self.assertFalse(result.owner_go_verified)

    def test_untrusted_dependency_and_lease_are_excluded(self):
        active=self.batch(active_leases={"TASK-B"})
        self.assertEqual(active.task_ids,("TASK-C","TASK-A"))
        self.states["TASK-A"]="VERIFIED"
        no_evidence=self.batch()
        self.assertNotIn("TASK-D",no_evidence.task_ids)
        # Even supplying a claimed trusted ID only creates a code proposal.
        protected=self.batch(independently_verified={"TASK-A"})
        self.assertIn("TASK-D",protected.task_ids)
        self.assertFalse(protected.runnable)

    def test_invalid_budgets_rejected_before_planning(self):
        for kwargs in (
            {"max_tasks":0},{"max_tasks":True},
            {"max_total_calls":0},{"max_total_seconds":0},
            {"max_total_seconds":True},{"max_tasks":33}
        ):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                self.batch(**kwargs)



if __name__ == "__main__":
    unittest.main()
