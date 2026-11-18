"""Synthetic P1 checks of MESA's non-authoritative event contract."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import unittest

from my_local_ai.experience.policy import parse_observation
from my_local_ai.experience.schema import ExperienceEventV1, ExperienceSuggestionV1

_BASE = {
    "event_id": "event-001", "project_id": "project-001",
    "run_id": "run-001", "task_id": "task-001",
    "plan_sha256": "a" * 64, "source_git_sha": "b" * 40,
    "scope_ref": "scope-001", "rights_tag": "PUBLIC_SYNTHETIC",
    "outcome": "FAILED", "error_fingerprint": "c" * 64,
    "environment_digest": "d" * 64, "observed_at": 1795000000,
}


def _parse(values: dict) -> ExperienceEventV1:
    return parse_observation(
        json.dumps(values), expected_project="project-001",
        expected_plan_sha="a" * 64, expected_source_sha="b" * 40,
        allowed_scope_refs=frozenset({"scope-001"}),
    )


class ExperienceContractTest(unittest.TestCase):
    def test_owned_synthetic_read_only_event(self):
        event = _parse(_BASE)
        self.assertEqual(event.outcome, "FAILED")
        self.assertFalse(event.to_redacted_dict()["independent_f18_verified"])
        self.assertFalse(event.to_redacted_dict()["execution_allowed"])
        with self.assertRaises(FrozenInstanceError):
            event.outcome = "OBSERVED"

    def test_scope_rights_and_digest_fail_closed(self):
        for key, bad in [
            ("project_id", "other-project"), ("scope_ref", "scope-999"),
            ("source_git_sha", "0" * 40), ("plan_sha256", "0" * 64),
            ("rights_tag", "CUSTOMER_PRIVATE"),
            ("error_fingerprint", "raw secret and path"),
            ("outcome", "VERIFIED"), ("observed_at", True),
        ]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                _parse({**_BASE, key: bad})

    def test_cannot_forge_owner_or_f18(self):
        for extra in ("owner_approved", "evidence_stage", "test_pass",
                      "independent_f18_verified", "command", "raw_prompt"):
            with self.subTest(field=extra), self.assertRaises(ValueError):
                _parse({**_BASE, extra: True})
        with self.assertRaises(ValueError):
            ExperienceEventV1(**_BASE, owner_approved=True)

    def test_duplicate_key_and_oversize_rejected(self):
        raw = json.dumps(_BASE)
        raw = raw[:-1] + ', "event_id": "event-002"}'
        with self.assertRaises(ValueError):
            parse_observation(
                raw, expected_project="project-001",
                expected_plan_sha="a"*64, expected_source_sha="b"*40,
                allowed_scope_refs=frozenset({"scope-001"}),
            )
        with self.assertRaises(ValueError):
            _parse({**_BASE, "raw_diff": "x" * 9000})

    def test_suggestion_never_permission(self):
        suggestion = ExperienceSuggestionV1(
            "strategy-001", ("event-001",), "reason-001")
        self.assertFalse(suggestion.approved)
        with self.assertRaises(ValueError):
            ExperienceSuggestionV1(
                "strategy-001", ("event-001",), "reason-001", approved=True)
        with self.assertRaises(ValueError):
            ExperienceSuggestionV1(
                "strategy-001", ("event-001",)*4, "reason-001")


if __name__ == "__main__":
    unittest.main()
