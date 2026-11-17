"""P1 synthetic CodeShield Controller-stage integration; no process execution."""
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from my_local_ai.contracts.plan import PlanSpec
from my_local_ai.security.codeshield_contracts import (
    ActionKind, CodeShieldContext, CodeShieldHold, DataClass, RiskOutcome,
)
from my_local_ai.controller.codeshield import (
    LocalStaticAudit, deny_codeshield_controller_plan_action,
)
from my_local_ai.orchestrator import inspect_codeshield_controller_action_scoped

SOURCE = "a" * 40
CANDIDATE = "b" * 40
TASK = "TASK-014"


def make_fixture():
    task = {
        "task_id": TASK, "req_ids": ["REQ-01"], "depends_on": [],
        "goal": "Synthetic CodeShield fixed scanner and Controller HOLD",
        "allowed_paths": ["src/sample.py"],
        "acceptance": ["No guest execution without real protected F18"],
        "checks": [], "risk": "HIGH",
        "resource_budget": {"max_calls": 1, "max_seconds": 30},
        "safety_checks": [], "plan_sha": None, "source_sha": SOURCE,
    }
    payload = {
        "version": 1, "plan_id": "PLAN-014",
        "blueprint": {"repo": "hibi89/my_local_ai",
                      "branch": "dev/instant-implementation-v1", "sha": SOURCE},
        "approval": {"status": "NOT_APPROVED", "scope": "LOCAL_PLAN", "digest": None},
        "tasks": [task],
    }
    raw = json.dumps(payload)
    plan = PlanSpec.parse_json(raw)
    context = CodeShieldContext(
        repository="hibi89/my_local_ai", task_id=TASK,
        run_id="RUN-014", owner_consent_ref="SYNTH-CONSENT",
        plan_sha256=plan.digest, source_git_sha=SOURCE,
        candidate_git_sha=CANDIDATE, lease_epoch=1,
        nonce_sha256="c" * 64, allowed_paths=("src/sample.py",),
        data_class=DataClass.PUBLIC_SYNTHETIC, scanner_pins=(),
    )
    audit = LocalStaticAudit(
        context.fingerprint_sha256, CANDIDATE,
        RiskOutcome.ALLOW_NON_EXECUTING,
        (("ast", "ALLOW_NON_EXECUTING"),),
        ("STATIC_CHECK_ONLY",),
        (("src/sample.py", "d" * 64),),
    )
    return raw, plan, context, audit


class ControllerCodeShieldDispatchTests(unittest.TestCase):
    def test_real_controller_path_holds_even_with_static_pass(self):
        raw, plan, ctx, audit = make_fixture()
        for action in ActionKind:
            decision = deny_codeshield_controller_plan_action(
                plan, ctx, states={TASK: "READY"},
                audit=audit, action=action,
            ).to_redacted_dict()
            self.assertEqual(decision["stage"], "P1_CONTROLLER_DISPATCH_DENIED")
            self.assertFalse(decision["execution_allowed"])
            self.assertFalse(decision["owner_consent_verified"])
            self.assertFalse(decision["f18_independently_verified"])
            self.assertFalse(decision["can_promote_git"])
            self.assertEqual(decision["checks"]["OWNER_ACTION_GRANT"], "HOLD")

    def test_actual_scanner_caller_to_controller_denial(self):
        raw, _plan, ctx, audit = make_fixture()
        with patch("my_local_ai.orchestrator._audit_scoped_sources", return_value=audit) as scanner:
            result = inspect_codeshield_controller_action_scoped(
                plan_json=raw, context=ctx, protected_states={TASK: "READY"},
                worktree="/synthetic", original_checkout="/other",
                changed_python_paths=("src/sample.py",),
            )
        scanner.assert_called_once()
        self.assertEqual(result["static_audit"]["outcome"], "ALLOW_NON_EXECUTING")
        self.assertEqual(result["controller_dispatch"]["stage"], "P1_CONTROLLER_DISPATCH_DENIED")
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(result["protected_os_broker"], "HOLD")
        self.assertEqual(result["independent_f18"], "HOLD")

    def test_stale_plan_or_source_blocks_before_scanner(self):
        raw, plan, ctx, audit = make_fixture()
        for corrupted in (
            replace(ctx, plan_sha256="f" * 64),
            replace(ctx, source_git_sha="e" * 40),
            replace(ctx, allowed_paths=("src/elsewhere.py",)),
        ):
            with patch("my_local_ai.orchestrator._audit_scoped_sources") as scanner:
                with self.assertRaises((CodeShieldHold, ValueError)):
                    inspect_codeshield_controller_action_scoped(
                        plan_json=raw, context=corrupted,
                        protected_states={TASK: "READY"},
                        worktree="/synthetic", original_checkout="/other",
                        changed_python_paths=("src/sample.py",),
                    )
                scanner.assert_not_called()

    def test_invalid_lease_and_unknown_state_hold(self):
        _raw, plan, ctx, audit = make_fixture()
        for leases, states in (
            ((TASK, TASK), {TASK: "READY"}),
            (("OTHER",), {TASK: "READY"}),
            ((), {"WRONG": "READY"}),
            ((), {TASK: "UNSAFE"}),
        ):
            with self.assertRaises((CodeShieldHold, ValueError)):
                deny_codeshield_controller_plan_action(
                    plan, ctx, states=states, active_leases=leases, audit=audit,
                )


if __name__ == "__main__":
    unittest.main()
