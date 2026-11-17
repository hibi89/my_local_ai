"""Synthetic approval adversarial tests. No secrets, owner records or real GO."""
from contextlib import closing
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from my_local_ai.contracts.approval import OwnerGrant, authorize_claim
from my_local_ai.state.consent import ConsentLedger
from my_local_ai.state.sqlite_store import initialize_state

KEY = b"synthetic-owner-key-not-for-production-" + bytes(range(16))
PLAN = "a" * 64
SOURCE = "b" * 40

def make_claim(**changes):
    obj = {"version":1,"grant_id":"SYNTH-GRANT-0001","plan_sha256":PLAN,
           "source_git_sha":SOURCE,"scope":"LOCAL_PLAN","issued_at":100,
           "expires_at":200,"nonce":"synthetic-nonce-1","signature":"0"*64}
    obj.update(changes)
    parsed = OwnerGrant.parse_json(json.dumps(obj))
    obj["signature"] = hmac.new(KEY, b"mla-owner-go/v1|" + parsed.payload(), hashlib.sha256).hexdigest()
    return OwnerGrant.parse_json(json.dumps(obj))

def check(claim, ledger, **updates):
    options = dict(trusted_hmac_key=KEY, expected_plan_sha=PLAN,
                   expected_source_sha=SOURCE, required_scope="LOCAL_PLAN",
                   now_seconds=150, trusted_live_consent_check=ledger.is_live)
    options.update(updates)
    return authorize_claim(claim, **options)

class ConsentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "only_synthetic.sqlite3"
        initialize_state(self.path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO owner_consents(consent_id,plan_sha,scope,state) VALUES(?,?,?,?)",
                       ("SYNTH-GRANT-0001",PLAN,"LOCAL_PLAN","APPROVED"))
        self.ledger = ConsentLedger(self.path)
        self.claim = make_claim()
        # An initial SQLite read may create WAL/SHM sidecars. ConsentLedger
        # correctly HOLDs that first read rather than trusting new files.
        # Prime the synthetic fixture; positive checks require stable identity.
        self.ledger.is_live("SYNTH-GRANT-0001", PLAN, "LOCAL_PLAN")

    def test_signed_and_unrevoked_synthetic_claim(self):
        self.assertTrue(check(self.claim,self.ledger))
        self.assertFalse(check(self.claim,self.ledger,trusted_hmac_key=None))

    def test_revocation_immediately_denies(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE owner_consents SET state='REVOKED' WHERE consent_id=?",("SYNTH-GRANT-0001",))
        self.assertFalse(check(self.claim,self.ledger))

    def test_forged_signature_does_not_authorize(self):
        tampered = OwnerGrant.parse_json(json.dumps({**json.loads(self.claim_json()), "signature":"0"*64}))
        self.assertFalse(check(tampered,self.ledger))

    def claim_json(self):
        return json.dumps({**json.loads(self.claim.payload()), "signature":self.claim.signature})

    def test_high_risk_action_scope_never_authorized_by_reusable_plan_grant(self):
        for scope in ("REMOTE_PR", "OS_CHANGE", "PAID_API", "CUSTOMER_DATA",
                      "PRODUCTION", "NETWORK_EGRESS"):
            obj = {"version": 1, "grant_id": "SYNTH-GRANT-0001",
                   "plan_sha256": PLAN, "source_git_sha": SOURCE,
                   "scope": scope, "issued_at": 100, "expires_at": 200,
                   "nonce": "synthetic-nonce-1", "signature": "0"*64}
            claimed = OwnerGrant.parse_json(json.dumps(obj))
            signature = hmac.new(KEY, b"mla-owner-go/v1|" + claimed.payload(), hashlib.sha256).hexdigest()
            actual = OwnerGrant.parse_json(json.dumps({**obj, "signature": signature}))
            self.assertFalse(check(actual, self.ledger, required_scope=scope))
            self.assertFalse(self.ledger.is_live(actual.grant_id, PLAN, scope))

    def test_malformed_or_moved_state_file_does_not_authorize(self):
        other = Path(self.tmp.name) / "replacement.sqlite3"
        initialize_state(other)
        with closing(sqlite3.connect(other)) as db, db:
            db.execute("INSERT INTO owner_consents(consent_id,plan_sha,scope,state) VALUES(?,?,?,?)",
                       ("SYNTH-GRANT-0001", PLAN, "LOCAL_PLAN", "NOT_APPROVED"))
        original_is_live = self.ledger.is_live
        # A replaced DB can never retain stale in-memory approval.
        self.assertTrue(original_is_live("SYNTH-GRANT-0001", PLAN, "LOCAL_PLAN"))
        import os
        os.replace(other, self.path)
        self.assertFalse(original_is_live("SYNTH-GRANT-0001", PLAN, "LOCAL_PLAN"))

    def test_symlinked_wal_or_shared_memory_sidecar_denied(self):
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(self.path) + suffix)
            if sidecar.exists():
                sidecar.unlink()
            try:
                sidecar.symlink_to(self.path)
            except OSError:
                self.skipTest("symlink permissions not available")
            self.assertFalse(self.ledger.is_live("SYNTH-GRANT-0001", PLAN, "LOCAL_PLAN"))
            sidecar.unlink()

    def test_deleted_or_renamed_state_is_fail_closed(self):
        moved = Path(self.tmp.name) / "old.sqlite3"
        self.path.rename(moved)
        self.assertFalse(check(self.claim, self.ledger))
        self.assertFalse(self.ledger.is_live("SYNTH-GRANT-0001", PLAN, "LOCAL_PLAN"))

    def test_scope_and_sha_mismatch_denied(self):
        self.assertFalse(check(self.claim,self.ledger,required_scope="REMOTE_PR"))
        self.assertFalse(check(self.claim,self.ledger,expected_plan_sha="c"*64))
        self.assertFalse(check(self.claim,self.ledger,expected_source_sha="d"*40))

    def test_expiry_and_clock_denied(self):
        self.assertFalse(check(self.claim,self.ledger,now_seconds=200))
        self.assertFalse(check(self.claim,self.ledger,now_seconds=99))

    def test_guest_claim_alone_cannot_authorize(self):
        self.assertFalse(check(self.claim,self.ledger,trusted_live_consent_check=None))
        self.assertFalse(check(self.claim,self.ledger,trusted_live_consent_check=lambda *_: "APPROVED"))
        self.assertFalse(check(self.claim,self.ledger,trusted_live_consent_check=lambda *_: (_ for _ in ()).throw(RuntimeError())))

    def test_unknown_credential_and_schema_rejected(self):
        with self.assertRaises(ValueError):
            OwnerGrant.parse_json('{"version":1,"version":1}')
        with self.assertRaises(ValueError):
            OwnerGrant.parse_json(json.dumps({**json.loads(self.claim_json()),"scope":"ROOT_ADMIN"}))

    def test_unowned_database_refused(self):
        other = Path(self.tmp.name) / "other.sqlite3"
        with closing(sqlite3.connect(other)) as db, db:
            db.execute("CREATE TABLE private(payload TEXT)")
        with self.assertRaises(ValueError):
            ConsentLedger(other)

if __name__ == "__main__":
    unittest.main()
