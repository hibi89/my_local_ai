"""Metrics are comparable only for identical acceptance/source context."""
import unittest
from dataclasses import replace

from my_local_ai.experience.evaluation import (
    TaskMetricsV1, compare_task_metrics, persist_task_metrics,
    compare_persisted_metrics,
)
import sqlite3
from my_local_ai.state.experience_migrations import initialize_empty_experience_store

BASE = TaskMetricsV1(
    "baseline-001", "BASELINE", "project-001",
    "a"*64, "b"*40, "c"*64, "d"*64, "scope-001",
    "PUBLIC_SYNTHETIC", 120000, 2, 8, 3, 30000, 1000, 2000, None,
    task_id="TASK-001", comparison_id="experiment-001",
)
ASSISTED = replace(
    BASE, observation_id="assisted-001", variant="ASSISTED",
    elapsed_ms=60000, model_calls=4, attempts=2, validation_ms=10000,
)


class V2MetricsTest(unittest.TestCase):
    def test_matching_local_observation_is_not_verified_speedup(self):
        result = compare_task_metrics(BASE, ASSISTED)
        self.assertEqual(result.state, "OBSERVED_UNVERIFIED")
        self.assertEqual(result.baseline_reqs_per_hour, 60)
        self.assertEqual(result.assisted_reqs_per_hour, 120)
        self.assertEqual(result.verified_speedup, "UNMEASURED")
        self.assertFalse(result.independent_evidence)
        self.assertFalse(result.to_redacted_dict()["execution_allowed"])

    def test_exact_baseline_mismatch_is_unmeasured(self):
        for key, value in (
            ("source_git_sha", "e"*40),
            ("plan_sha256", "f"*64),
            ("acceptance_sha256", "0"*64),
            ("scope_ref", "scope-999"),
            ("environment_digest", "1"*64),
        ):
            with self.subTest(field=key):
                result = compare_task_metrics(BASE, replace(ASSISTED, **{key: value}))
                self.assertEqual(result.state, "UNMEASURED")
                self.assertIsNone(result.assisted_reqs_per_hour)
        self.assertEqual(compare_task_metrics(None, ASSISTED).state, "UNMEASURED")

    def test_invalid_forged_data_rejected(self):
        for key, value in (
            ("elapsed_ms", 0), ("model_calls", -1),
            ("attempts", True), ("ram_peak_bytes", -100),
            ("rights_tag", "CUSTOMER_PRIVATE"), ("source_git_sha", "bad"),
        ):
            with self.subTest(field=key), self.assertRaises(ValueError):
                replace(BASE, **{key: value})
        self.assertEqual(compare_task_metrics(
            BASE, replace(BASE, variant="ASSISTED")
        ).state, "UNMEASURED")


if __name__ == "__main__":
    unittest.main()



class V2StoredMetricsTest(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        initialize_empty_experience_store(self.db,explicit_new_owned_store=True)

    def tearDown(self):
        self.db.close()

    def compare(self,**changes):
        scope=dict(
            project_id="project-001",scope_ref="scope-001",plan_sha256="a"*64,
            source_git_sha="b"*40,acceptance_sha256="c"*64,
            environment_digest="d"*64,rights_tag="PUBLIC_SYNTHETIC",
            task_id="TASK-001",comparison_id="experiment-001",
        )
        scope.update(changes)
        return compare_persisted_metrics(self.db,**scope)

    def test_redacted_append_idempotency_and_exact_comparison(self):
        with self.assertRaises(ValueError):
            persist_task_metrics(self.db,BASE)
        self.assertTrue(persist_task_metrics(
            self.db,BASE,explicit_owned_scope=True))
        self.assertFalse(persist_task_metrics(
            self.db,BASE,explicit_owned_scope=True))
        self.assertTrue(persist_task_metrics(
            self.db,ASSISTED,explicit_owned_scope=True))
        observed=self.compare()
        self.assertEqual(observed.state,"OBSERVED_UNVERIFIED")
        self.assertEqual(observed.assisted_calls,4)
        self.assertEqual(observed.verified_speedup,"UNMEASURED")
        self.assertEqual(self.compare(acceptance_sha256="f"*64).state,"UNMEASURED")
        with self.assertRaises(sqlite3.DatabaseError):
            self.db.execute("DELETE FROM experience_metrics")

    def test_cross_task_and_cross_experiment_never_mispaired(self):
        persist_task_metrics(self.db,BASE,explicit_owned_scope=True)
        other=replace(ASSISTED,task_id="TASK-002")
        persist_task_metrics(self.db,other,explicit_owned_scope=True)
        self.assertEqual(self.compare().state,"UNMEASURED")
        self.assertEqual(compare_task_metrics(BASE,other).state,"UNMEASURED")
        with self.assertRaises(ValueError):
            persist_task_metrics(
                self.db,replace(BASE,observation_id="legacy-001",
                                task_id=None,comparison_id=None),
                explicit_owned_scope=True)

    def test_changed_observation_and_cherry_picking_fail_closed(self):
        persist_task_metrics(self.db,BASE,explicit_owned_scope=True)
        persist_task_metrics(self.db,ASSISTED,explicit_owned_scope=True)
        with self.assertRaises(ValueError):
            persist_task_metrics(
                self.db,replace(BASE,model_calls=1),explicit_owned_scope=True)
        persist_task_metrics(
            self.db,replace(ASSISTED,observation_id="assisted-002"),
            explicit_owned_scope=True,
        )
        self.assertEqual(self.compare().state,"UNMEASURED")
