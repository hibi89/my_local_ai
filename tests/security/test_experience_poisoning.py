"""MESA poisoning/revocation cannot become signed authority."""
import unittest
from dataclasses import replace

from my_local_ai.experience.curator import (
    candidate_fingerprint, classify_experience,
)
from my_local_ai.experience.schema import ExperienceEventV1
from my_local_ai.experience.skills import SkillVersionV1, inspect_skill

EVENT = ExperienceEventV1(
    "event-001", "project-001", "run-001", "task-001",
    "a"*64, "b"*40, "scope-001", "PUBLIC_SYNTHETIC", "FAILED",
    "c"*64, "d"*64, 1795000000,
)


class ExperiencePoisoningTest(unittest.TestCase):
    def curate(self, event=EVENT, **options):
        args = dict(
            strategy_digest="1"*64, proposed_action_digest="2"*64,
            expected_source_sha="b"*40, expected_scope="scope-001",
            now=1795000001, expires_at=2000000000,
        )
        args.update(options)
        return classify_experience(event, **args)

    def test_failure_candidate_is_never_auto_approved(self):
        candidate = self.curate()
        self.assertEqual(candidate.state, "CURATION_PENDING")
        self.assertFalse(candidate.verified)
        self.assertFalse(candidate.owner_approved)
        self.assertFalse(candidate.may_run)
        self.assertEqual(len(candidate_fingerprint(EVENT, strategy_digest="1"*64)), 64)

    def test_poisoning_scope_revocation_and_expiry(self):
        for opts, state in (
            ({"expected_source_sha": "f"*40}, "QUARANTINED"),
            ({"expected_scope": "scope-999"}, "QUARANTINED"),
            ({"suspicious_digest_ids": frozenset({"1"*64})}, "QUARANTINED"),
            ({"revoked_event_ids": frozenset({"event-001"})}, "REVOKED"),
            ({"now": 2000000000}, "EXPIRED"),
        ):
            with self.subTest(opts=opts):
                self.assertEqual(self.curate(**opts).state, state)

    def test_success_not_promoted_and_no_bypass_fields(self):
        self.assertEqual(
            self.curate(replace(EVENT, outcome="OBSERVED")).state,
            "QUARANTINED",
        )
        with self.assertRaises(ValueError):
            replace(self.curate(), owner_approved=True)

    def test_shadow_version_rollback_cannot_run_or_reactivate(self):
        from my_local_ai.experience.skills import plan_shadow_rollback
        old = SkillVersionV1(
            "skill-001", 1, "a"*64, None, "scope-001", 2000000000,
        )
        bad = SkillVersionV1(
            "skill-001", 2, "b"*64, "a"*64, "scope-001", 2000000000,
            state="REVOKED",
        )
        plan = plan_shadow_rollback(
            (old,bad), scope_ref="scope-001", now=1795000000,
        )
        self.assertEqual(plan.previous_content_sha256, "a"*64)
        self.assertFalse(plan.activated)
        self.assertFalse(plan.source_written)
        self.assertFalse(plan.owner_go)
        self.assertFalse(plan.code_executed)
        with self.assertRaises(ValueError):
            plan_shadow_rollback((old,), scope_ref="scope-001",
                                 now=1795000000)
        with self.assertRaises(ValueError):
            plan_shadow_rollback((old,replace(bad,parent_content_sha256="c"*64)),
                                 scope_ref="scope-001",now=1795000000)
        expired=replace(old, expiry_at=1795000000)
        no_parent=plan_shadow_rollback(
            (expired,bad),scope_ref="scope-001",now=1795000000,
        )
        self.assertIsNone(no_parent.previous_content_sha256)

    def test_skill_version_is_shadow_only(self):
        skill = SkillVersionV1(
            "skill-001", 1, "a"*64, None, "scope-001", 2000000000,
        )
        good = inspect_skill(
            skill, scope_ref="scope-001", now=1795000000,
            content_sha256="a"*64,
        )
        self.assertEqual(good.status, "SHADOW_ADVICE_ONLY")
        self.assertFalse(good.execution_allowed)
        self.assertEqual(inspect_skill(
            skill, scope_ref="scope-999", now=1795000000,
            content_sha256="a"*64,
        ).status, "QUARANTINED_OR_STALE")
        with self.assertRaises(ValueError):
            replace(good, owner_approved=True)


if __name__ == "__main__":
    unittest.main()
