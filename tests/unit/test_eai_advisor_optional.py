"""Advisor payload is data, not EAI process code or authority."""
import json
import unittest

from my_local_ai.advisors.eai import parse_advisory


class AdvisorBoundaryTests(unittest.TestCase):
    def test_empty_advisor_is_valid_and_non_authoritative(self):
        self.assertEqual(parse_advisory('{"version":1,"hints":[]}', frozenset()), {})

    def test_ranking_only(self):
        data = {"version": 1, "hints": [{"task_id": "TASK-A", "rank": 3}]}
        self.assertEqual(parse_advisory(json.dumps(data), frozenset({"TASK-A"})), {"TASK-A": 3})

    def test_unknown_ids_scope_changes_and_repeats_rejected(self):
        for raw in (
            '{"version":1,"hints":[{"task_id":"OTHER","rank":1}]}',
            '{"version":1,"hints":[{"task_id":"TASK-A","rank":0},{"task_id":"TASK-A","rank":2}]}',
            '{"version":1,"hints":[{"task_id":"TASK-A","rank":1,"verified":true}]}',
            '{"version":1,"hints":[{"task_id":"TASK-A","rank":-1}]}',
            '{"version":1,"hints":[{"task_id":"TASK-A","rank":NaN}]}',
            '{"version":1,"hints":[],"command":"rm -rf /"}',
            '{"version":1,"version":1,"hints":[]}',
            '{"version":1,"hints":[{"task_id":"TASK-A","rank":1.5}]}',
            "x" * 4097,
        ):
            with self.subTest(raw=raw[:70]), self.assertRaises(ValueError):
                parse_advisory(raw, frozenset({"TASK-A"}))


if __name__ == "__main__":
    unittest.main()
