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
                   ("INTEGRATE-002","REVIEW-002","refs/heads/mla/isolated/TASK-017",CANDIDATE))
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


# P1-only semantic transaction checks on in-memory SQLite, not owner files.
import hashlib
import hmac
from my_local_ai.contracts.approval import OwnerGrant
from my_local_ai.ax_runtime.leases import claim_synthetic_lease


class SyntheticLeaseTransactionTests(unittest.TestCase):
    def setUp(self):
        CrashResumeContractTests.setUp(self)
        self.db.execute("PRAGMA query_only=OFF")
        self.db.execute("UPDATE tasks SET state='READY' WHERE plan_id='PLAN-017'")
        self.db.execute(
            "INSERT INTO owner_consents(consent_id,plan_sha,scope,state) VALUES(?,?,?,?)",
            ("SYNTH-OWNER-017",PLAN,"LOCAL_PLAN","APPROVED"),
        )
        self.db.commit()
        self.key=b"synthetic-owner-consent-unit-tests-32"
        unsigned=OwnerGrant("SYNTH-OWNER-017",PLAN,SRC,"LOCAL_PLAN",100,500,
                            "nonce0001","0"*64)
        signature=hmac.new(self.key,b"mla-owner-go/v1|"+unsigned.payload(),hashlib.sha256).hexdigest()
        from dataclasses import replace
        self.grant=replace(unsigned,signature=signature)

    def issue(self, **change):
        props=dict(
            db=self.db,proposal=propose_lease(
                snapshot(existing_epoch=0),trusted_plan_sha=PLAN,
                trusted_baseline_sha=SRC),
            run_id="RUN-017",plan_sha256=PLAN,source_sha=SRC,
            owner_grant=self.grant,trusted_test_key=self.key,
            trusted_live_consent_check=lambda *_:True,
            now_seconds=150,
        )
        props.update(change)
        return claim_synthetic_lease(**props)

    def test_synthetic_transaction_persists_fenced_lease_without_exec(self):
        claim=self.issue()
        self.assertEqual(claim.lease_epoch,1)
        self.assertFalse(claim.can_run_coder)
        self.assertFalse(claim.can_update_original)
        self.assertEqual(
            self.db.execute("SELECT state FROM tasks WHERE task_id='TASK-017'").fetchone()[0],
            "LEASED",
        )
        self.assertEqual(
            self.db.execute("SELECT count(*) FROM runs WHERE run_id='RUN-017'").fetchone()[0],1,
        )

    def test_duplicate_and_stale_replay_rollback(self):
        self.issue()
        with self.assertRaises(LeaseHold):
            self.issue()
        self.assertEqual(self.db.execute("SELECT count(*) FROM runs").fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM leases").fetchone()[0],1)

    def test_unsigned_wrong_plan_or_revoked_consent_rejected(self):
        with self.assertRaises(LeaseHold):
            self.issue(owner_grant=None)
        with self.assertRaises(LeaseHold):
            self.issue(plan_sha256="f"*64)
        self.db.execute("UPDATE owner_consents SET state='REVOKED'")
        self.db.commit()
        with self.assertRaises(LeaseHold):
            self.issue()
        self.assertEqual(self.db.execute("SELECT count(*) FROM runs").fetchone()[0],0)

    def test_wrong_expected_generation_rolls_back(self):
        stale=propose_lease(
            snapshot(existing_epoch=5),trusted_plan_sha=PLAN,trusted_baseline_sha=SRC,
        )
        with self.assertRaises(LeaseHold):
            self.issue(proposal=stale)
        self.assertEqual(self.db.execute("SELECT state FROM tasks WHERE task_id='TASK-017'").fetchone()[0],"READY")
        self.assertEqual(self.db.execute("SELECT count(*) FROM leases").fetchone()[0],0)

    def test_forged_database_identity_does_not_issue_lease(self):
        self.db.execute("PRAGMA application_id=12345")
        with self.assertRaises(LeaseHold):
            self.issue()


class RestartReconcileSecurityTests(CrashResumeContractTests):
    def test_guest_claimed_verified_without_integration_is_rejected(self):
        self.write(
            "UPDATE tasks SET state='VERIFIED' WHERE plan_id=? AND task_id=?",
            ("PLAN-017","TASK-017"),
        )
        with self.assertRaises(ReconcileHold) as x:
            self.run_reconcile()
        self.assertEqual(x.exception.code,"UNTRUSTED_VERIFIED")

    def test_orphan_run_without_lease_is_not_auto_resumed(self):
        self.write(
            "INSERT INTO runs(run_id,plan_id,task_id,baseline_sha,lease_epoch,state) "
            "VALUES(?,?,?,?,?,?)",
            ("RUN-ORPHAN","PLAN-017","TASK-017",SRC,1,"CODING"),
        )
        out=self.run_reconcile()
        self.assertEqual(out.status,"HOLD_ORPHAN_RUN_REQUIRES_FENCE")
        self.assertFalse(out.new_lease_allowed)

    def test_revoked_plan_never_returns_approved_state(self):
        self.write("UPDATE plans SET state='STOPPED' WHERE plan_id=?",("PLAN-017",))
        out=self.run_reconcile()
        self.assertEqual(out.status,"HOLD_PLAN_NOT_APPROVED")
        self.assertFalse(out.executable)

    def test_fake_trusted_review_status_or_sha_cannot_preserve_ref(self):
        self.write(
            "INSERT INTO runs(run_id,plan_id,task_id,baseline_sha,lease_epoch,"
            "state,candidate_sha) VALUES(?,?,?,?,?,?,?)",
            ("RUN-OLD","PLAN-017","TASK-017",SRC,1,"REVIEW_PENDING",CANDIDATE),
        )
        self.write(
            "INSERT INTO reviews(review_id,run_id,candidate_sha,result)"
            "VALUES(?,?,?,?)",
            ("REVIEW-OLD","RUN-OLD",CANDIDATE,"UNTRUSTED"),
        )
        self.write(
            "INSERT INTO integrations(integration_id,review_id,local_ref,integrated_sha)"
            "VALUES(?,?,?,?)",
            ("INTEGRATE-OLD","REVIEW-OLD",
             "refs/heads/mla/isolated/TASK-017",CANDIDATE),
        )
        with self.assertRaises(ReconcileHold) as x:
            self.run_reconcile(protected_ref_sha=CANDIDATE)
        self.assertEqual(x.exception.code,"UNTRUSTED_VERIFIED")
        self.write("UPDATE reviews SET result='TRUSTED_PASS', candidate_sha=?",
                   ("f"*40,))
        with self.assertRaises(ReconcileHold):
            self.run_reconcile(protected_ref_sha=CANDIDATE)

    def test_active_lease_and_integration_conflict(self):
        self.write(
            "INSERT INTO runs(run_id,plan_id,task_id,baseline_sha,lease_epoch,"
            "state,candidate_sha) VALUES(?,?,?,?,?,?,?)",
            ("RUN-OLD","PLAN-017","TASK-017",SRC,1,"REVIEW_PENDING",CANDIDATE),
        )
        self.write(
            "INSERT INTO leases(plan_id,task_id,generation,run_id) VALUES(?,?,?,?)",
            ("PLAN-017","TASK-017",1,"RUN-OLD"),
        )
        self.write(
            "INSERT INTO reviews(review_id,run_id,candidate_sha,result)"
            "VALUES(?,?,?,?)",
            ("REVIEW-OLD","RUN-OLD",CANDIDATE,"TRUSTED_PASS"),
        )
        self.write(
            "INSERT INTO integrations(integration_id,review_id,local_ref,integrated_sha)"
            "VALUES(?,?,?,?)",
            ("INTEGRATE-OLD","REVIEW-OLD",
             "refs/heads/mla/isolated/TASK-017",CANDIDATE),
        )
        with self.assertRaises(ReconcileHold) as x:
            self.run_reconcile(protected_ref_sha=CANDIDATE)
        self.assertEqual(x.exception.code,"INCOMPLETE_TRUST_EVIDENCE")

    def test_duplicate_run_epochs_fail_closed_even_if_schema_allows(self):
        self.write(
            "INSERT INTO runs(run_id,plan_id,task_id,baseline_sha,lease_epoch,state)"
            "VALUES(?,?,?,?,?,?)",
            ("RUN-ONE","PLAN-017","TASK-017",SRC,1,"REVIEW_PENDING"),
        )
        # Unique(plan,task,baseline,epoch) enforces duplicates at SQL boundary.
        self.db.execute("PRAGMA query_only=OFF")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "INSERT INTO runs(run_id,plan_id,task_id,baseline_sha,lease_epoch,state)"
                "VALUES(?,?,?,?,?,?)",
                ("RUN-TWO","PLAN-017","TASK-017",SRC,1,"REVIEW_PENDING"),
            )
        self.db.rollback()
        self.db.execute("PRAGMA query_only=ON")


if __name__=="__main__":
    unittest.main()


class ReconcileDatabaseIdentityTests(unittest.TestCase):
    setUp = CrashResumeContractTests.setUp
    run_reconcile = CrashResumeContractTests.run_reconcile

    def test_attached_database_is_never_a_trusted_recovery_source(self):
        self.db.execute("PRAGMA query_only=OFF")
        self.db.execute("ATTACH DATABASE ':memory:' AS shadow")
        self.db.execute("PRAGMA query_only=ON")
        with self.assertRaises(ReconcileHold) as exc:
            self.run_reconcile()
        self.assertEqual(exc.exception.code, "BAD_STATE")

    def test_temp_table_shadowing_is_rejected(self):
        self.db.execute("PRAGMA query_only=OFF")
        self.db.execute("CREATE TEMP TABLE plans(plan_id TEXT)")
        self.db.execute("PRAGMA query_only=ON")
        with self.assertRaises(ReconcileHold) as exc:
            self.run_reconcile()
        self.assertEqual(exc.exception.code, "BAD_STATE")

    def test_schema_drift_cannot_be_used_for_recovery(self):
        self.db.execute("PRAGMA query_only=OFF")
        self.db.execute("ALTER TABLE plans ADD COLUMN attacker_claim TEXT")
        self.db.execute("PRAGMA query_only=ON")
        with self.assertRaises(ReconcileHold) as exc:
            self.run_reconcile()
        self.assertEqual(exc.exception.code, "BAD_STATE")

    def test_unsafe_triggers_are_not_trusted(self):
        self.db.execute("PRAGMA query_only=OFF")
        self.db.execute("CREATE TRIGGER sneaky AFTER INSERT ON plans BEGIN SELECT 1; END")
        self.db.execute("PRAGMA query_only=ON")
        with self.assertRaises(ReconcileHold) as exc:
            self.run_reconcile()
        self.assertEqual(exc.exception.code, "BAD_STATE")
