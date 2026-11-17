"""Synthetic SQLite crash/lease protection; no Git or original DB touched."""
import sqlite3
import unittest

from my_local_ai.ax_runtime.leases import (
    LeaseHold, LeaseSnapshot, check_lease_fence, propose_lease,
)
from my_local_ai.state.migrations import DDL, APP_ID, SCHEMA_VERSION
from my_local_ai.state.reconcile import ReconcileHold, read_reconcile_state

PLAN="a"*64
SRC="b"*40
CANDIDATE="c"*40


def snapshot(**kwargs):
    v=dict(plan_id="PLAN-017", task_id="TASK-017", plan_sha=PLAN,
           baseline_sha=SRC, existing_epoch=3)
    v.update(kwargs)
    return LeaseSnapshot(**v)


class CrashResumeContractTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute("PRAGMA foreign_keys=ON")
        for ddl in DDL:
            self.db.execute(ddl)
        self.db.execute(f"PRAGMA application_id={APP_ID}")
        self.db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        self.db.execute(
            "INSERT INTO plans(plan_id,plan_sha,blueprint_sha,state) VALUES(?,?,?,?)",
            ("PLAN-017",PLAN,SRC,"APPROVED"),
        )
        self.db.execute(
            "INSERT INTO tasks(plan_id,task_id,source_sha,state) VALUES(?,?,?,?)",
            ("PLAN-017","TASK-017",SRC,"REVIEW_PENDING"),
        )
        self.db.commit()
        self.db.execute("PRAGMA query_only=ON")

    def run_reconcile(self, **kwargs):
        opts=dict(plan_id="PLAN-017",task_id="TASK-017",
                  trusted_plan_sha=PLAN,trusted_source_sha=SRC,
                  protected_ref_sha=None)
        opts.update(kwargs)
        return read_reconcile_state(self.db,**opts)

    def write(self,sql,params=()):
        self.db.execute("PRAGMA query_only=OFF")
        self.db.execute(sql,params)
        self.db.commit()
        self.db.execute("PRAGMA query_only=ON")

    def test_lease_proposal_never_authorizes_work(self):
        p=propose_lease(snapshot(),trusted_plan_sha=PLAN,trusted_baseline_sha=SRC)
        self.assertEqual(p.proposed_epoch,4)
        self.assertEqual(p.expected_previous_epoch,3)
        self.assertFalse(p.runnable)
        self.assertFalse(p.owner_approved)
        self.assertEqual(p.state,"AWAIT_PROTECTED_TRANSACTION")

    def test_duplicate_active_run_and_old_source_blocked(self):
        for item in (snapshot(active_run_id="RUN-OLD",active_state="CODING"),
                     snapshot(active_run_id="RUN-OLD"),
                     snapshot(baseline_sha="f"*40)):
            with self.subTest(item=item),self.assertRaises(LeaseHold):
                propose_lease(item,trusted_plan_sha=PLAN,trusted_baseline_sha=SRC)

    def test_fencing_refuses_old_lease(self):
        self.assertTrue(check_lease_fence(expected_run_id="RUN-001",expected_epoch=3,
                                          observed_run_id="RUN-001",observed_epoch=3))
        self.assertFalse(check_lease_fence(expected_run_id="RUN-001",expected_epoch=3,
                                           observed_run_id="RUN-001",observed_epoch=2))
        self.assertFalse(check_lease_fence(expected_run_id="RUN-001",expected_epoch=3,
                                           observed_run_id="RUN-002",observed_epoch=3))

    def test_protected_db_has_no_exec_recovery(self):
        decision=self.run_reconcile()
        self.assertEqual(decision.status,"HOLD_NO_ACTIVE_LEASE")
        self.assertFalse(decision.executable)
        self.assertFalse(decision.git_write_allowed)
        self.assertFalse(decision.independently_verified)

    def test_interrupted_lease_does_not_auto_resume(self):
        self.write("INSERT INTO runs(run_id,plan_id,task_id,baseline_sha,lease_epoch,state) VALUES(?,?,?,?,?,?)",
                   ("RUN-001","PLAN-017","TASK-017",SRC,4,"INTERRUPTED"))
        self.write("INSERT INTO leases(plan_id,task_id,generation,run_id) VALUES(?,?,?,?)",
                   ("PLAN-017","TASK-017",4,"RUN-001"))
        self.assertEqual(self.run_reconcile().status,"HOLD_INTERRUPTED_LEASE")

    def test_stale_lease_epoch_denied(self):
        self.write("INSERT INTO runs(run_id,plan_id,task_id,baseline_sha,lease_epoch,state) VALUES(?,?,?,?,?,?)",
                   ("RUN-001","PLAN-017","TASK-017",SRC,4,"REVIEW_PENDING"))
        self.write("INSERT INTO leases(plan_id,task_id,generation,run_id) VALUES(?,?,?,?)",
                   ("PLAN-017","TASK-017",5,"RUN-001"))
        with self.assertRaises(ReconcileHold):
            self.run_reconcile()

    def test_orphan_protected_ref_denied(self):
        with self.assertRaises(ReconcileHold):
            self.run_reconcile(protected_ref_sha=CANDIDATE)

    def test_integrated_candidate_without_matching_ref_denied(self):
        self.write("INSERT INTO runs(run_id,plan_id,task_id,baseline_sha,lease_epoch,state,candidate_sha) VALUES(?,?,?,?,?,?,?)",
                   ("RUN-002","PLAN-017","TASK-017",SRC,4,"REVIEW_PENDING",CANDIDATE))
        self.write("INSERT INTO reviews(review_id,run_id,candidate_sha,result) VALUES(?,?,?,?)",
                   ("REVIEW-002","RUN-002",CANDIDATE,"TRUSTED_PASS"))
        self.write("INSERT INTO integrations(integration_id,review_id,local_ref,integrated_sha) VALUES(?,?,?,?)",
                   ("INTEGRATE-002","REVIEW-002","refs/heads/local-test",CANDIDATE))
        with self.assertRaises(ReconcileHold):
            self.run_reconcile()
        result=self.run_reconcile(protected_ref_sha=CANDIDATE)
        self.assertEqual(result.status,"PRESERVE_PREVIOUS_REF_AWAIT_F18")
        self.assertFalse(result.git_write_allowed)
        self.assertFalse(result.independently_verified)

    def test_wrong_plan_source_and_writeable_db_rejected(self):
        with self.assertRaises(ReconcileHold):
            self.run_reconcile(trusted_plan_sha="f"*64)
        self.db.execute("PRAGMA query_only=OFF")
        with self.assertRaises(ReconcileHold):
            self.run_reconcile()


if __name__=="__main__":
    unittest.main()
