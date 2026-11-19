"""Authorized narrow server regression: synthetic inputs, no native services.

Test transport signatures intentionally use a synthetic HMAC backend. They are
never TPM/ECDSA/OS-principal evidence and cannot authenticate production IPC.
No candidate code, candidate test, Git process or Defender scan is executed.
"""
import base64
import hashlib
import hmac
import json
import inspect
import types
from pathlib import Path
import secrets
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from contextlib import contextmanager

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from my_local_ai.state import consent as c
from my_local_ai.review import protected_reviewer as r
from my_local_ai.security import defender_status as d


@contextmanager
def database(path):
    db = sqlite3.connect(path)
    try:
        with db:
            yield db
    finally:
        db.close()


class SyntheticAPI:
    def __init__(self, role, authority, ledger, roots, approve=True):
        self.role, self.authority_path, self.ledger_path = role, authority, ledger
        self.roots, self.approve = roots, approve
        self.prompts = []

    def confirm_owner(self, action, scope):
        self.prompts.append((action, scope))
        return self.approve

    def sign(self, body):
        return hmac.new(self.roots[self.role][2], c._broker_canonical(body), hashlib.sha512).digest()

    def verify_signature(self, public, body, signature):
        if not hmac.compare_digest(hmac.new(public, body, hashlib.sha512).digest(), signature):
            raise c.ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")


class OwnerSessionProtocolTests(unittest.TestCase):
    """Pure source tests: HMAC fixture never substitutes TPM or Windows GO."""

    def setUp(self):
        self.key_service = b"synthetic-service-key"
        self.key_owner = b"synthetic-owner-key"
        self.binding = {
            "task_id": "TASK-001", "run_id": "RUN-001",
            "plan_sha256": "a" * 64, "source_sha": "b" * 40,
            "candidate_sha": "c" * 40, "lease_epoch": 1,
            "nonce_sha256": "d" * 64, "owner_consent_ref": "OWNER-001",
        }
        self.action = {"role": "reviewer", "operation": "review",
                       "binding": self.binding,
                       "payload": {"validation_scope": "STATIC_ONLY"}}
        digest = hashlib.sha256(c._broker_canonical(self.action)).hexdigest()
        self.request = {"schema": "mla-protected-request/v1",
                        "role": "owner", "operation": "authorize",
                        "challenge": "e" * 64, "binding": self.binding,
                        "payload": {"action_sha256": digest,
                                    "action": self.action}}
        self.scope = {
            "repository_path": "C:\\protected\\bare",
            "disposable_root": "C:\\scratch\\candidate",
            "allowed_paths": ["src/demo.py"],
            "operations": ["reviewer:review"],
            "data_class": "PUBLIC_SYNTHETIC",
            "plan_sha256": "a" * 64,
        }

    def signer(self, key):
        return lambda body: hmac.new(key, c._broker_canonical(body),
                                     hashlib.sha512).digest()

    def verifier(self, public, body, signature):
        if not hmac.compare_digest(
            hmac.new(public, body, hashlib.sha512).digest(), signature
        ):
            raise c.ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")

    def ticket(self):
        return c._build_owner_ui_ticket(
            self.request, self.action, self.scope,
            signer=self.signer(self.key_service), issued_at=1000,
        )

    def test_owner_interactive_entry_cannot_run_as_plain_python_on_nonwindows(self):
        import os
        if os.name != "nt":
            with self.assertRaises(c.ProtectedBrokerHold):
                c.owner_session_main()

    def test_owner_dialog_displays_exact_nontruncated_authorized_scope(self):
        ticket=self.ticket()
        payload=c._owner_ui_display_payload(ticket["body"])
        self.assertIn("src/demo.py",payload)
        self.assertIn(self.binding["plan_sha256"],payload)
        self.assertIn(self.binding["nonce_sha256"],payload)
        self.assertIn(ticket["body"]["ticket_nonce"],payload)
        self.assertIn(ticket["body"]["action_sha256"],payload)
        self.assertIn("reviewer",payload)
        oversized={**ticket["body"],"scope":{
            **ticket["body"]["scope"],"oversized":"x"*18000}}
        with self.assertRaises(c.ProtectedBrokerHold):
            c._owner_ui_display_payload(oversized)

    def test_owner_session_signed_one_shot_approval_and_denial(self):
        ticket = self.ticket()
        identity = c._check_owner_ui_ticket(
            ticket, expected_service_public=self.key_service,
            verify_signature=self.verifier, now_seconds=1001,
        )
        self.assertEqual(identity["binding"], self.binding)
        approved = c._make_owner_ui_decision(
            ticket, approved=True, owner_sid="S-1-5-21-OWNER",
            signer=self.signer(self.key_owner), now_seconds=1002,
        )
        self.assertTrue(c._check_owner_ui_decision(
            ticket, approved, expected_owner_sid="S-1-5-21-OWNER",
            expected_owner_public=self.key_owner, verify_signature=self.verifier,
            now_seconds=1003,
        ))
        denied = c._make_owner_ui_decision(
            ticket, approved=False, owner_sid="S-1-5-21-OWNER",
            signer=self.signer(self.key_owner), now_seconds=1002,
        )
        self.assertFalse(c._check_owner_ui_decision(
            ticket, denied, expected_owner_sid="S-1-5-21-OWNER",
            expected_owner_public=self.key_owner, verify_signature=self.verifier,
            now_seconds=1003,
        ))

    def test_owner_service_to_separate_session_signed_file_roundtrip(self):
        """One synthetic service-side exchange + one synthetic Owner process.

        No Windows service, key, EXE, ACL, user dialog or production claim.
        """
        import contextlib
        import time
        class FakeService:
            role="owner"
            def verify_signature(inner, public, body, signature):
                self.verifier(public,body,signature)

        @contextlib.contextmanager
        def fake_preprovisioned_directory(_api, _sid):
            yield

        for decision, expected in ((True,True),(False,False)):
            with self.subTest(approved=decision), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                errors=[]
                stopped=threading.Event()
                def serve_owner_ui():
                    try:
                        filename=None
                        deadline=time.monotonic()+3
                        while time.monotonic()<deadline:
                            found=list(root.glob("*.request.json"))
                            if found:
                                filename=found[0]
                                break
                            time.sleep(0.01)
                        if filename is None:
                            raise AssertionError("service never created its signed challenge")
                        ticket=c._broker_decode(c._owner_ui_read_file(filename))
                        body=c._check_owner_ui_ticket(
                            ticket,expected_service_public=self.key_service,
                            verify_signature=self.verifier,now_seconds=int(time.time()))
                        self.assertEqual(body["action_sha256"],
                            hashlib.sha256(c._broker_canonical(self.action)).hexdigest())
                        reply=c._make_owner_ui_decision(ticket,approved=decision,
                            owner_sid="S-1-5-21-OWNER",
                            signer=self.signer(self.key_owner),now_seconds=int(time.time()))
                        # The actual Owner UI writes .partial and atomically
                        # renames on Windows. Do not expose a half-written
                        # signed response to the reader in this source test.
                        temp=root/(body["ticket_nonce"]+".reply.partial")
                        final=root/(body["ticket_nonce"]+".reply.json")
                        c._owner_ui_write_file(temp,c._broker_canonical(reply))
                        import os
                        os.rename(temp,final)
                    except BaseException as exc:
                        errors.append(exc)
                        stopped.set()  # Short fail, never wait 120s on fixture error.

                with (patch.object(c,"_OWNER_UI_EXCHANGE",root),
                      patch.object(c,"_owner_ui_read_pins",
                          return_value=("S-1-5-21-OWNER",1,
                                        "synthetic",self.key_owner,"e"*64)),
                      patch.object(c,"_owner_ui_locked_directory",
                          fake_preprovisioned_directory)):
                    worker=threading.Thread(target=serve_owner_ui,daemon=True)
                    worker.start()
                    result=c._confirm_owner_session_request(
                        FakeService(),self.request,self.action,self.scope,
                        self.signer(self.key_service),stopped)
                    worker.join(timeout=2)
                    self.assertFalse(worker.is_alive())
                    self.assertEqual(errors,[])
                    self.assertIs(result,expected)
                    self.assertEqual(list(root.iterdir()),[])

    def test_owner_ui_tampering_replay_expiry_and_wrong_identity_hold(self):
        ticket = self.ticket()
        decision = c._make_owner_ui_decision(
            ticket, approved=True, owner_sid="S-1-5-21-OWNER",
            signer=self.signer(self.key_owner), now_seconds=1002,
        )
        other = self.ticket()
        for mutated, owner_sid, now in (
            (decision, "S-1-5-21-FOREIGN", 1003),
            (decision, "S-1-5-21-OWNER", 1121),
            ({**decision, "body": {**decision["body"], "approved": False}},
                "S-1-5-21-OWNER", 1003),
            ({**decision, "body": {**decision["body"],
                "ticket_sha256": "0" * 64}}, "S-1-5-21-OWNER", 1003),
        ):
            with self.subTest(owner=owner_sid, now=now), self.assertRaises(
                c.ProtectedBrokerHold
            ):
                c._check_owner_ui_decision(
                    ticket, mutated, expected_owner_sid=owner_sid,
                    expected_owner_public=self.key_owner,
                    verify_signature=self.verifier, now_seconds=now,
                )
        with self.assertRaises(c.ProtectedBrokerHold):
            c._check_owner_ui_decision(
                other, decision, expected_owner_sid="S-1-5-21-OWNER",
                expected_owner_public=self.key_owner,
                verify_signature=self.verifier, now_seconds=1003,
            )
        tampered = {**ticket, "body": {**ticket["body"],
            "scope": {**ticket["body"]["scope"],
                      "allowed_paths": ["private/secret.py"]}}}
        with self.assertRaises(c.ProtectedBrokerHold):
            c._check_owner_ui_ticket(
                tampered, expected_service_public=self.key_service,
                verify_signature=self.verifier, now_seconds=1002,
            )


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.authority = self.root / "authority.sqlite3"
        with database(self.authority) as db:
            db.executescript(c.PROTECTED_AUTHORITY_SCHEMA)
        self.binding = {"task_id": "TASK-001", "run_id": "RUN-001", "plan_sha256": "a" * 64,
            "source_sha": "b" * 40, "candidate_sha": "c" * 40, "lease_epoch": 1,
            "nonce_sha256": "d" * 64, "owner_consent_ref": "SYNTHETIC-ONLY"}
        self.scope = {"repository_path": str(self.root / "bare"),
            "disposable_root": str(self.root / "scratch"), "allowed_paths": ["src/demo.py"],
            "operations": ["reviewer:review", "scanner:defender"],
            "data_class": "PUBLIC_SYNTHETIC", "plan_sha256": self.binding["plan_sha256"]}
        self.roots = {role: ("synthetic-sid-" + role, str(i) * 64,
                     ("SYNTHETIC-TEST-ONLY-" + role).encode())
                      for i, role in enumerate(c._SERVICE_ROLES, 1)}
        self.apis, self.servers = {}, {}
        for role in c._SERVICE_ROLES:
            ledger = self.root / (role + ".sqlite3")
            with database(ledger) as db:
                db.executescript(c.PROTECTED_SERVICE_LEDGER_SCHEMA)
            api = SyntheticAPI(role, self.authority, ledger, self.roots)
            self.apis[role] = api
            self.servers[role] = c._ProtectedActionServer(api, api.sign, threading.Event())
        self.write_scope()

    def write_scope(self, *, revoked=0, expires=None, binding=None, scope=None):
        with database(self.authority) as db:
            db.execute("INSERT OR REPLACE INTO scopes VALUES(?,?,?,?,?)", (
                self.binding["owner_consent_ref"], c._broker_canonical(binding or self.binding).decode(),
                c._broker_canonical(scope or self.scope).decode(),
                expires if expires is not None else int(time.time()) + 600, revoked))

    def action(self):
        return {"role": "reviewer", "operation": "review", "binding": self.binding,
                "payload": {"validation_scope": "STATIC_ONLY"}}

    def request(self, role, op, payload, *, binding=None, challenge=None):
        return c._broker_canonical({"schema": "mla-protected-request/v1", "role": role,
            "operation": op, "binding": binding or self.binding,
            "challenge": challenge or secrets.token_hex(32), "payload": payload})

    def owner_request(self):
        action = self.action()
        return self.request("owner", "authorize", {
            "action": action, "action_sha256": hashlib.sha256(c._broker_canonical(action)).hexdigest()})

    def call(self, role, raw):
        return c._broker_decode(self.servers[role].process(raw))

    def test_frozen_owner_ui_never_runs_on_nonwindows(self):
        import os
        if os.name != "nt":
            with self.assertRaises(c.ProtectedBrokerHold):
                c.owner_session_main()

    def test_owner_session_file_exchange_is_bounded_and_exclusive(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"ticket.json"
            raw=c._broker_canonical({"fixture":"only"})
            c._owner_ui_write_file(path,raw)
            self.assertEqual(c._owner_ui_read_file(path),raw)
            with self.assertRaises(FileExistsError):
                c._owner_ui_write_file(path,raw)
            with self.assertRaises(c.ProtectedBrokerHold):
                c._owner_ui_read_file(path,max_bytes=3)
            path.unlink()
            os.symlink("absent",path)
            with self.assertRaises((c.ProtectedBrokerHold,FileNotFoundError)):
                c._owner_ui_read_file(path)

    def test_owner_real_request_handler_records_full_action_and_consumes_nonce(self):
        response = self.call("owner", self.owner_request())
        self.assertEqual(response["body"]["status"], "OK")
        self.assertEqual(response["body"]["result"]["nonce_state"], "CONSUMED")
        self.assertEqual(self.apis["owner"].prompts[0][0], self.action())
        with database(self.apis["owner"].ledger_path) as db:
            state, raw = db.execute("SELECT state,response FROM journal").fetchone()
            self.assertEqual(state, "COMPLETED")
            self.assertEqual(c._broker_decode(raw), response)

    def test_replay_never_prompts_or_consumes_twice(self):
        self.assertEqual(self.call("owner", self.owner_request())["body"]["status"], "OK")
        self.assertEqual(self.call("owner", self.owner_request())["body"]["status"], "DENIED")
        self.assertEqual(len(self.apis["owner"].prompts), 1)

    def test_crash_reserved_nonce_stays_burned_after_reopen(self):
        raw = self.owner_request()
        req = c._broker_decode(raw)
        self.servers["owner"].journal.reserve(req, req["payload"]["action_sha256"])
        api = self.apis["owner"]
        self.servers["owner"] = c._ProtectedActionServer(api, api.sign, threading.Event())
        self.assertEqual(self.call("owner", self.owner_request())["body"]["status"], "DENIED")
        self.assertEqual(api.prompts, [])

    def test_duplicated_transport_challenge_rejected(self):
        raw = self.owner_request()
        request = c._broker_decode(raw)
        journal = self.servers["owner"].journal
        journal.reserve(request, "f" * 64)
        request["binding"]["nonce_sha256"] = "e" * 64
        with self.assertRaises(c.ProtectedBrokerHold):
            journal.reserve(request, "f" * 64)

    def test_concurrent_nonce_reservation_is_atomic(self):
        from concurrent.futures import ThreadPoolExecutor
        barrier = threading.Barrier(6)
        def reserve(_):
            request = c._broker_decode(self.owner_request())
            barrier.wait(timeout=5)
            try:
                self.servers["owner"].journal.reserve(request, "f" * 64)
                return "CONSUMED"
            except c.ProtectedBrokerHold:
                return "DENIED"
        with ThreadPoolExecutor(max_workers=6) as pool:
            outcomes = list(pool.map(reserve, range(6)))
        self.assertEqual(outcomes.count("CONSUMED"), 1)
        self.assertEqual(outcomes.count("DENIED"), 5)

    def test_nonce_reused_with_different_action_denied(self):
        self.call("owner", self.owner_request())
        req = c._broker_decode(self.owner_request())
        req["payload"]["action"]["payload"] = {"substitute": True}
        req["payload"]["action_sha256"] = hashlib.sha256(c._broker_canonical(req["payload"]["action"])).hexdigest()
        self.assertEqual(self.call("owner", c._broker_canonical(req))["body"]["status"], "DENIED")

    def test_owner_rejection_is_persistent(self):
        self.apis["owner"].approve = False
        self.assertEqual(self.call("owner", self.owner_request())["body"]["status"], "DENIED")
        with database(self.apis["owner"].ledger_path) as db:
            self.assertEqual(db.execute("SELECT state FROM journal").fetchone()[0], "DENIED")

    def test_revoked_lease_denies_before_prompt(self):
        self.write_scope(revoked=1)
        self.assertEqual(self.call("owner", self.owner_request())["body"]["status"], "DENIED")
        self.assertEqual(self.apis["owner"].prompts, [])

    def test_expired_lease_denies(self):
        self.write_scope(expires=int(time.time()) - 1)
        self.assertEqual(self.call("owner", self.owner_request())["body"]["status"], "DENIED")

    def test_epoch_mismatch_denies(self):
        changed = {**self.binding, "lease_epoch": 2}
        self.write_scope(binding=changed)
        self.assertEqual(self.call("owner", self.owner_request())["body"]["status"], "DENIED")

    def test_revocation_during_owner_prompt_wins(self):
        def revoke(action, scope):
            self.write_scope(revoked=1)
            return True
        self.apis["owner"].confirm_owner = revoke
        self.assertEqual(self.call("owner", self.owner_request())["body"]["status"], "DENIED")

    def test_source_binding_mismatch_denies(self):
        self.write_scope(binding={**self.binding, "source_sha": "0" * 40})
        self.assertEqual(self.call("owner", self.owner_request())["body"]["status"], "DENIED")

    def test_nested_git_mirror_and_disposable_scope_denied_before_owner_prompt(self):
        bare = self.root / "bare"
        scratch = self.root / "scratch"
        for repository_path, disposable_root in (
            (bare, bare),
            (scratch / "bare", scratch),
            (bare, bare / "worktree"),
        ):
            with self.subTest(repository=str(repository_path),
                              disposable=str(disposable_root)):
                self.write_scope(scope={
                    **self.scope,
                    "repository_path": str(repository_path),
                    "disposable_root": str(disposable_root),
                })
                response = self.call("owner", self.owner_request())
                self.assertEqual(response["body"]["status"], "DENIED")
                self.assertEqual(self.apis["owner"].prompts, [])

    def test_private_scope_never_reaches_owner_ui(self):
        self.write_scope(scope={**self.scope, "data_class": "CUSTOMER_SECRET"})
        self.assertEqual(self.call("owner", self.owner_request())["body"]["status"], "DENIED")
        self.assertEqual(self.apis["owner"].prompts, [])

    def test_windows_alias_and_non_plan_paths_never_reach_owner(self):
        # checked_relative_path alone accepted device names, globs and
        # non-ASCII candidates. Signed PlanSpec never does.
        for path in ("src/CON.py", "src/nul.py", "src/[ab].py",
                     "src/한글.py", "src/name?.py", "src/name'.py"):
            with self.subTest(path=path):
                self.write_scope(scope={**self.scope, "allowed_paths": [path]})
                response = self.call("owner", self.owner_request())
                self.assertEqual(response["body"]["status"], "DENIED")
                self.assertEqual(self.apis["owner"].prompts, [])

    def test_static_reviewer_uses_plan_path_contract_for_git_delta(self):
        source = {"src/demo.py": ("100644", "a" * 40)}
        candidate = {"src/demo.py": ("100644", "b" * 40)}
        self.assertEqual(r._bounded_review_changed_paths(
            source, candidate, ["src/demo.py"]), ("src/demo.py",))
        for alias in ("src/CON.py", "src/nul.py", "src/[ab].py",
                      "src/한글.py", "src/aux.py", "src/name?.py"):
            with self.subTest(alias=alias):
                updated = dict(source)
                updated[alias] = ("100644", "c" * 40)
                with self.assertRaises(c.ProtectedBrokerHold):
                    r._bounded_review_changed_paths(source, updated, [alias])
        # The candidate must not gain/remove executable bits through a
        # source-only F18 review. A legacy 100755 file keeps its mode while
        # its text changes; a newly executable path is always denied.
        with self.assertRaises(c.ProtectedBrokerHold):
            r._bounded_review_changed_paths(
                source, {"src/demo.py": ("100755", "b" * 40)},
                ["src/demo.py"],
            )
        with self.assertRaises(c.ProtectedBrokerHold):
            r._bounded_review_changed_paths(
                source, {**source, "src/new.py": ("100755", "b" * 40)},
                ["src/new.py"],
            )
        legacy_source = {"src/demo.py": ("100755", "a" * 40)}
        legacy_candidate = {"src/demo.py": ("100755", "b" * 40)}
        self.assertEqual(r._bounded_review_changed_paths(
            legacy_source, legacy_candidate, ["src/demo.py"]
        ), ("src/demo.py",))
        with self.assertRaises(c.ProtectedBrokerHold):
            r._bounded_review_changed_paths(
                source, {}, ["src/demo.py"]  # Deletion prohibited.
            )
        with self.assertRaises(c.ProtectedBrokerHold):
            r._bounded_review_changed_paths(
                source, candidate, ["src/other.py"]  # Out of scope.
            )

    def test_modified_action_digest_denies(self):
        req = c._broker_decode(self.owner_request())
        req["payload"]["action_sha256"] = "0" * 64
        self.assertEqual(self.call("owner", c._broker_canonical(req))["body"]["status"], "DENIED")

    def test_generated_execution_operation_denies(self):
        req = c._broker_decode(self.owner_request())
        req["payload"]["action"]["role"] = "coder"
        req["payload"]["action"]["operation"] = "run"
        self.assertEqual(self.call("owner", c._broker_canonical(req))["body"]["status"], "DENIED")

    def test_stopped_service_denies(self):
        self.servers["owner"].stopped.set()
        self.assertEqual(self.call("owner", self.owner_request())["body"]["status"], "DENIED")

    def test_protocol_duplicate_keys_and_bool_epoch_rejected(self):
        raw = self.owner_request().replace(b'"schema":', b'"challenge":"duplicate","schema":')
        with self.assertRaises(c.ProtectedBrokerHold):
            self.call("owner", raw)
        req = c._broker_decode(self.owner_request())
        req["binding"]["lease_epoch"] = True
        with self.assertRaises(c.ProtectedBrokerHold):
            self.call("owner", c._broker_canonical(req))

    def test_signature_forgery_and_expired_grant_rejected(self):
        raw = self.servers["owner"].process(self.owner_request())
        envelope = c._broker_decode(raw)
        for mutation in ("signature", "expiration", "binding"):
            changed = json.loads(json.dumps(envelope))
            if mutation == "signature":
                changed["signature"] = base64.b64encode(b"0" * 64).decode()
            elif mutation == "expiration":
                changed["body"]["expires_at"] = 1
            else:
                changed["body"]["binding"]["candidate_sha"] = "0" * 40
            token = base64.b64encode(c._broker_canonical(changed)).decode()
            with self.subTest(mutation=mutation), self.assertRaises(c.ProtectedBrokerHold):
                self.servers["reviewer"].verify_grant(token, "owner", self.binding)

    def test_service_missing_is_fail_closed(self):
        class Missing:
            def load_roots(self):
                raise c.ProtectedBrokerHold("PROTECTED_BROKER_UNAVAILABLE")
        with patch.object(c, "_WindowsBrokerAPI", Missing):
            with self.assertRaises(c.ProtectedBrokerHold):
                c.dispatch_protected_action("reviewer", "review", binding=self.binding,
                    payload={"validation_scope": "STATIC_ONLY"})

    def test_final_transport_failure_is_unknown_not_not_run(self):
        def exchange(role, operation, *, binding, payload, **kwargs):
            if role == "owner":
                return {"result": {"action_sha256": payload["action_sha256"],
                    "decision": "APPROVED_SINGLE_USE", "nonce_state": "CONSUMED",
                    "lease_state": "LIVE_AT_SIGNING"}, "signed_envelope": "SYNTHETIC"}
            if operation == "runtime-permit":
                return {"result": {"action_sha256": payload["action_sha256"],
                    "decision": "RUNTIME_BOUNDARY_APPROVED", "nonce_state": "LIVE_FOR_REVIEW",
                    "lease_state": "LIVE_AT_SIGNING"}, "signed_envelope": "SYNTHETIC"}
            raise c.ProtectedBrokerHold("PROTECTED_BROKER_TIMEOUT")
        with patch.object(c, "exchange_protected_broker", exchange):
            with self.assertRaises(c.ProtectedBrokerHold) as ctx:
                c.dispatch_protected_action("scanner", "defender", binding=self.binding, payload={})
            self.assertEqual(ctx.exception.code, "PROTECTED_ACTION_OUTCOME_UNKNOWN")

    def test_controller_to_owner_to_permit_to_real_static_handler(self):
        outer = self
        class Client:
            def load_roots(self):
                return outer.roots
            def verify_signature(self, public, body, signature):
                outer.apis["owner"].verify_signature(public, body, signature)
            def transact(self, role, roots, request, timeout):
                return outer.servers[role].process(request)
        policy = r.build_reviewer_policy()
        intent = r.IsolatedReviewerIntent(self.binding["task_id"], self.binding["run_id"],
            self.binding["plan_sha256"], self.binding["source_sha"], self.binding["candidate_sha"],
            1, policy.policy_sha256, self.roots["reviewer"][1], r._SOURCE_POLICY_CHECK_IDS)
        with patch.object(c, "_WindowsBrokerAPI", Client), patch.object(r, "_read_protected_git_candidate",
                return_value={"src/demo.py": b"value = 1\n"}):
            result = r.review_protected_candidate(intent, nonce_sha256=self.binding["nonce_sha256"],
                owner_consent_ref=self.binding["owner_consent_ref"])
            self.assertEqual(result.validation_scope, "STATIC_ONLY")
            self.assertEqual(result.execution_count, 0)
            self.assertFalse(result.independently_accepted)
            self.assertFalse(result.may_promote)
            self.assertEqual(result.transcript.check_ids, r._STATIC_CHECK_IDS)
            status = result.to_acceptance_status()
            self.assertEqual(status["static_review_scope"], "STATIC_ONLY")
            self.assertEqual(status["required_executed_tests"],
                             "NOT_RUN_ZERO_VM_POLICY_HOLD")
            self.assertEqual(status["req14_executed_test_acceptance"],
                             "UNSATISFIED")
            self.assertFalse(status["may_promote"])
            self.assertFalse(status["reviewer_executed_tests"])
            with self.assertRaises(r.ProtectedReviewerHold):
                r.review_protected_candidate(intent, nonce_sha256=self.binding["nonce_sha256"],
                    owner_consent_ref=self.binding["owner_consent_ref"])

    def static_payload(self):
        return {"policy_sha256": r.build_reviewer_policy().policy_sha256,
            "static_policy_sha256": r._STATIC_POLICY_SHA256, "reviewer_binary_sha256": self.roots["reviewer"][1],
            "check_ids": list(r._STATIC_CHECK_IDS), "validation_scope": "STATIC_ONLY",
            "execution_count": 0, "execution_permitted": False, "policy": "F18_STATIC_ONLY_V1"}

    def test_static_server_rejects_execution_and_source_error(self):
        api = self.apis["reviewer"]
        for change in ({"execution_permitted": True}, {"execution_count": 1},
                       {"validation_scope": "EXECUTED_TESTS"}, {"check_ids": ["UNIT-001"]}):
            with self.subTest(change=change), self.assertRaises(c.ProtectedBrokerHold):
                r._serve_static_review(api, self.binding, {**self.static_payload(), **change}, self.scope, threading.Event())
        with patch.object(r, "_read_protected_git_candidate", return_value={"src/demo.py": b"import os\nos.remove('x')"}):
            with self.assertRaises(c.ProtectedBrokerHold):
                r._serve_static_review(api, self.binding, self.static_payload(), self.scope, threading.Event())

    def test_protected_git_tree_rejects_duplicate_and_bad_framing(self):
        # Even object-addressed Git trees may contain duplicate names.
        # No entry may overwrite an earlier one before protected scope review.
        def item(path, mode=b"100644", oid=b"a" * 40):
            return mode + b" blob " + oid + b"\t" + path + b"\x00"

        valid = item(b"src/demo.py")
        self.assertEqual(
            r._decode_protected_git_tree_listing(valid),
            {"src/demo.py": ("100644", "a" * 40)},
        )
        # A first commit may have no baseline blobs. This is a normal path,
        # not an incorrectly signed or malformed delta.
        self.assertEqual(r._decode_protected_git_tree_listing(b""), {})
        self.assertEqual(r._bounded_review_changed_paths(
            {}, {"src/demo.py": ("100644", "a" * 40)},
            ["src/demo.py"]), ("src/demo.py",))
        # Independent siblings under an ordinary directory remain valid.
        self.assertEqual(len(r._decode_protected_git_tree_listing(
            valid + item(b"src/other.py", oid=b"b" * 40))), 2)
        for listing in (
            # Both raw Git-tree enumeration orders must fail closed.
            item(b"src") + valid,
            valid + item(b"src"),
            item(b"Src") + item(b"src/demo.py"),
            valid + valid,
            valid + item(b"SRC/DEMO.py", oid=b"b" * 40),
            valid[:-1],
            valid + b"\x00",
            item(b"src/../demo.py"),
            item(b"src/file.py", mode=b"120000"),
            item(b"src/invalid_\xff.py"),
        ):
            with self.subTest(listing=repr(listing[:70])):
                with self.assertRaises(c.ProtectedBrokerHold):
                    r._decode_protected_git_tree_listing(listing)

    def test_static_evidence_cannot_pass_legacy_test_receipt_guard(self):
        from my_local_ai.review.receipt_guard import inspect_receipt, ExpectedReceipt, ReceiptHold
        expected = ExpectedReceipt("TASK-001", "RUN-001", "a" * 64, "b" * 40,
            "c" * 40, "2" * 64, r.build_reviewer_policy().policy_sha256,
            "BOUNDARY-001", 1, "NONCE-001", ("SYNTAX-001", "UNIT-001", "SECURITY-001"))
        with self.assertRaises(ReceiptHold):
            inspect_receipt('{"validation_scope":"STATIC_ONLY","execution_count":0}', expected)

    def test_plain_python_service_entrypoint_denies(self):
        for role in c._SERVICE_ROLES:
            with self.subTest(role=role), self.assertRaises(c.ProtectedBrokerHold):
                c.protected_service_main(role)

    def test_scm_running_waits_for_signer_and_shutdown_is_accepted(self):
        # Static native-entry contract. A synthetic local test cannot prove
        # SCM startup, CNG key custody or protected OS principal readiness.
        code = inspect.getsource(c.protected_service_main)
        self.assertEqual(code.count("with api.signer() as sign_body:"), 1)
        self.assertEqual(code.count("report(4)"), 1)
        self.assertLess(code.index("with api.signer() as sign_body:"),
                        code.index("server = _ProtectedActionServer(api, sign_body, stopped)"))
        self.assertLess(code.index("server = _ProtectedActionServer(api, sign_body, stopped)"),
                        code.index("                    report(4)"))
        self.assertLess(code.index("                    report(4)"),
                        code.index("_serve_named_pipe(api, server, stopped)"))
        self.assertIn("0x5 if state == 4 else 0", code)
        self.assertIn("if code in (1, 5):", code)
        self.assertIn('raise ProtectedBrokerHold("PROTECTED_BROKER_UNAVAILABLE")', code)

    def test_runtime_ipc_never_modifies_live_process_or_token_dacls(self):
        # SCM/Owner UI must fail closed if independently provisioned read-only
        # token query access is missing. P1 code must not fix this by granting
        # rights at service start or during a client transaction.
        import inspect
        broker = inspect.getsource(c._WindowsBrokerAPI.transact)
        service_init = inspect.getsource(c._WindowsProtectedServiceAPI.__init__)
        service_type = inspect.getsource(c._WindowsProtectedServiceAPI)
        for actual in (broker, service_init, service_type):
            self.assertNotIn("SetSecurityInfo", actual)
            self.assertNotIn("SetEntriesInAclW", actual)
            self.assertNotIn("_permit_controller_identity_query", actual)
        # Removing the mutation must not bypass authenticated peer SID and
        # SCM PID/image checks from the independent broker trust boundary.
        auth = inspect.getsource(c._WindowsBrokerAPI.authenticate_pipe)
        # A protected service is now identified by SCM own-process PID,
        # local account SID and pinned image; foreign token access is not
        # required, but the protected server still checks Controller SID.
        self.assertIn("self._scm_account_sid(installed.account)", auth)
        self.assertIn("installed.kind != 0x10", auth)
        self.assertIn("QueryServiceStatusEx", auth)
        self.assertIn("status[7] != pid.value", auth)
        self.assertIn("roots[role][1]", auth)
        self.assertIn("check_acl(service", auth)
        self.assertNotIn("self.process_sid(process)", auth)
        server_pipe = inspect.getsource(c._serve_named_pipe)
        self.assertIn("api.pipe_client_sid_after_read(pipe) != sid", server_pipe)

    def test_pipe_client_has_duplex_access_without_server_creation(self):
        # Generic write includes FILE_CREATE_PIPE_INSTANCE. The client must
        # request exactly the narrower rights granted by the server pipe DACL.
        self.assertEqual(c._BROKER_PIPE_CLIENT_ACCESS & 3, 3)
        self.assertEqual(c._BROKER_PIPE_CLIENT_ACCESS & 4, 0)
        self.assertEqual(c._BROKER_PIPE_CLIENT_ACCESS & 0xC0000000, 0)


class ProtectedPipeClientTokenTests(unittest.TestCase):
    """Synthetic Win32 token-query contract; no real OS impersonation."""

    def fake_api(self, *, refuse_open=False, refuse_read=False, refuse_revert=False):
        import ctypes as C
        from ctypes import wintypes as W
        events = []
        api = object.__new__(c._WindowsBrokerAPI)
        api.c, api.w, api.advapi, api.kernel = C, W, object(), object()
        api.sid_string = lambda sid: ("S-1-5-21-100-200-300-1000"
                                     if sid == 0x1234 else "INVALID")
        def impersonate(pipe):
            events.append("impersonate")
            return True
        def revert():
            events.append("revert")
            return not refuse_revert
        def thread():
            events.append("thread")
            return 111
        def open_token(thread, access, self_identity, target):
            events.append(("open_token", access, self_identity))
            if refuse_open:
                return False
            target._obj.value = 222
            return True
        def get_token(token, level, buffer, max_size, output_size):
            events.append(("token_query", level))
            output_size._obj.value = 64
            if buffer is None:
                return False  # expected initial ERROR_INSUFFICIENT_BUFFER
            if refuse_read:
                return False
            C.cast(buffer, C.POINTER(C.c_void_p))[0] = 0x1234
            return True
        def close(handle):
            events.append("close_token")
            return True
        def exit_process(code):
            events.append(("terminate_service", code))
            return None  # Native ExitProcess does not return.
        funcs = {
            "ImpersonateNamedPipeClient": impersonate,
            "RevertToSelf": revert,
            "GetCurrentThread": thread,
            "OpenThreadToken": open_token,
            "GetTokenInformation": get_token,
            "ExitProcess": exit_process,
        }
        api._bind = lambda lib, name, args, result: funcs[name]
        # Do not expose live kernel handles; fake kernel needs only CloseHandle.
        class Kernel:
            CloseHandle = staticmethod(close)
        api.kernel = Kernel()
        return api, events

    def test_read_only_pipe_token_sid_and_mandatory_revert(self):
        api, events = self.fake_api()
        self.assertEqual(api.pipe_client_sid_after_read(321),
                         "S-1-5-21-100-200-300-1000")
        self.assertEqual(events[0], "impersonate")
        self.assertIn(("open_token", 0x0008, True), events)
        self.assertEqual(events[-2:], ["close_token", "revert"])

    def test_open_or_token_query_failure_always_reverts(self):
        for option in ("refuse_open", "refuse_read"):
            with self.subTest(option=option):
                api, events = self.fake_api(**{option: True})
                with self.assertRaises(c.ProtectedBrokerHold):
                    api.pipe_client_sid_after_read(321)
                self.assertEqual(events[-1], "revert")

    def test_failed_identity_restore_terminates_service_before_next_request(self):
        api, events = self.fake_api(refuse_revert=True)
        with self.assertRaises(c.ProtectedBrokerHold):
            api.pipe_client_sid_after_read(321)
        self.assertEqual(events[-2], "revert")
        self.assertEqual(events[-1], ("terminate_service", 1))
        # The fatal native path is ExitProcess, not ctypes callback
        # exceptions that WINFUNCTYPE might silently swallow.
        import inspect
        source = inspect.getsource(c._WindowsBrokerAPI.pipe_client_sid_after_read)
        self.assertIn('self._bind(self.kernel, "ExitProcess"', source)

    def test_server_authenticates_after_header_and_before_body(self):
        import inspect
        source = inspect.getsource(c._serve_named_pipe)
        first_header = source.index('length = int.from_bytes(exact(4), "little")')
        identity = source.index("api.pipe_client_sid_after_read(pipe)")
        processing = source.index("server.process(exact(length))")
        self.assertLess(first_header, identity)
        self.assertLess(identity, processing)
        self.assertNotIn("api.process_sid(peer)", source)
        client_source = inspect.getsource(c._WindowsBrokerAPI.transact)
        self.assertIn("0x00110000", client_source)  # SQOS IDENTIFICATION


class ProtectedSignerLiveRevocationTests(unittest.TestCase):
    """Protected live pin changes revoke an open signer handle before use.

    Synthetic winreg/OwnerUI only: no native key access or OS writes.
    """
    def setUp(self):
        self.roots = {
            "owner": ("S-1-5-21-1-2-3-1001", "a" * 64, b"A" * 72),
            "reviewer": ("S-1-5-21-1-2-3-1002", "b" * 64, b"B" * 72),
            "scanner": ("S-1-5-21-1-2-3-1003", "c" * 64, b"C" * 72),
        }
        self.key_name = "MyLocalAI.OwnerKey"
        reg = types.ModuleType("winreg")
        reg.HKEY_LOCAL_MACHINE, reg.KEY_READ, reg.KEY_WOW64_64KEY, reg.REG_SZ = 1, 2, 4, 1
        class Key:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def __int__(self): return 123
        self.reg = reg
        self.reads = []
        def open_key(hive, path, reserved, permissions):
            self.reads.append(("open", path))
            return Key()
        def query_value(key, name):
            self.reads.append(("query", name))
            return self.key_name, reg.REG_SZ
        reg.OpenKey, reg.QueryValueEx = open_key, query_value

    def service(self):
        settings = {
            "KeyName": self.key_name,
            "KeyProviderMode": "SOFTWARE_CNG_OWNER_APPROVED_V1",
            "ControllerSid": "S-1-5-21-1-2-3-1005",
            "InteractiveOwnerSid": "S-1-5-21-1-2-3-1004",
            "OwnerSessionId": 2,
        }
        return types.SimpleNamespace(
            role="owner", roots=self.roots.copy(),
            settings=settings,
            _settings=lambda: {**settings, "KeyName": self.key_name},
            load_roots=lambda: self.roots.copy(),
            check_acl=lambda *args: self.reads.append(("acl",)),
        )

    def call(self, api, *, live_mode="SOFTWARE_CNG_OWNER_APPROVED_V1", owner_pins=None):
        with patch.dict(sys.modules, {"winreg": self.reg}), \
             patch.object(c, "_read_pinned_cng_mode", return_value=live_mode), \
             patch.object(c, "_owner_ui_read_pins", return_value=owner_pins):
            c._WindowsProtectedServiceAPI._assert_signer_pins_current(api)

    def test_live_service_pins_pass_then_revoke_on_profile_key_or_other_role(self):
        api = self.service()
        self.call(api)
        self.assertIn(("acl",), self.reads)
        self.assertIn(("query", "KeyName"), self.reads)
        with self.assertRaises(c.ProtectedBrokerHold):
            self.call(api, live_mode="TPM_V1")
        old = self.key_name
        self.key_name = "MyLocalAI.RotatedKey"
        with self.assertRaises(c.ProtectedBrokerHold):
            self.call(api)
        self.key_name = old
        self.roots["reviewer"] = ("S-1-5-21-1-2-3-1002", "e" * 64, b"E" * 72)
        with self.assertRaises(c.ProtectedBrokerHold):
            self.call(api)

    def test_open_service_signer_revoked_by_controller_owner_or_session_rotation(self):
        api = self.service()
        self.call(api)
        live = api._settings
        for field, changed in (
            ("ControllerSid", "S-1-5-21-1-2-3-1999"),
            ("InteractiveOwnerSid", "S-1-5-21-1-2-3-1888"),
            ("OwnerSessionId", 3),
        ):
            api._settings = lambda field=field, changed=changed: {
                **live(), field: changed,
            }
            with self.subTest(field=field), self.assertRaises(c.ProtectedBrokerHold):
                self.call(api)
        api._settings = live
        self.call(api)

    def test_ownerui_rejects_session_key_and_service_root_revocation(self):
        owner = ("S-1-5-21-1-2-3-1004", "d" * 64, b"D" * 72)
        api = types.SimpleNamespace(
            role="owner-ui", roots={"owner-ui": owner},
            service_roots=self.roots.copy(), owner_session_id=2,
            settings={"KeyName":"MyLocalAI.OwnerUiKey",
                      "KeyProviderMode":"SOFTWARE_CNG_OWNER_APPROVED_V1"},
            load_roots=lambda: self.roots.copy(),
        )
        pins=(owner[0],2,"MyLocalAI.OwnerUiKey",owner[2],owner[1])
        self.call(api, owner_pins=pins)
        for changed in (
            (owner[0],3,pins[2],owner[2],owner[1]),
            (owner[0],2,"MyLocalAI.Rotated",owner[2],owner[1]),
            (owner[0],2,pins[2],b"X"*72,owner[1]),
        ):
            with self.subTest(changed=changed), self.assertRaises(c.ProtectedBrokerHold):
                self.call(api, owner_pins=changed)
        self.roots["reviewer"] = ("S-1-5-21-1-2-3-1002","e"*64,b"E"*72)
        with self.assertRaises(c.ProtectedBrokerHold):
            self.call(api, owner_pins=pins)

    def test_live_pin_recheck_is_inside_every_sign_not_only_on_key_open(self):
        source=inspect.getsource(c._WindowsProtectedServiceAPI.signer)
        body=source[source.index("def sign_body(body: dict)"):]
        self.assertIn("self._assert_signer_pins_current()", body)
        self.assertLess(body.index("self._assert_signer_pins_current()"),
                        body.index("sign(key,"))
        self.assertNotIn("NCryptCreatePersistedKey", source)
        self.assertNotIn("NCryptDeleteKey", source)
        self.assertTrue(hasattr(c._OwnerInteractiveAPI, "_assert_signer_pins_current"))

    def test_live_cng_key_acl_export_and_usage_recheck_precedes_signing(self):
        # Source contract only. A real protected Windows CNG handle is P2 HOLD.
        body = inspect.getsource(c._WindowsProtectedServiceAPI.signer)
        body = body[body.index("def sign_body(body: dict)"):]
        signature = body.index("if (sign(key,")
        for guard in (
            "self._assert_signer_pins_current()",
            'prop("Export Policy")',
            'self._key_acl(prop("Security Descr", 5 | 0x40))',
            'dword(key, "Key Type")',
            'dword(key, "Key Usage")',
        ):
            with self.subTest(guard=guard):
                self.assertLess(body.index(guard), signature)
        self.assertLess(body.index('prop("Export Policy")'),
                        body.index('self._key_acl(prop("Security Descr", 5 | 0x40))'))
        self.assertIn('raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")', body)


class SCMPrincipalBindingTests(unittest.TestCase):
    """Pure synthetic SCM name constraints; no Windows account/API changed."""

    def test_only_pinned_local_machine_account_names_are_candidates(self):
        check = c._WindowsBrokerAPI._local_scm_account_name
        self.assertEqual(check(r".\mla_owner", "MY-PC"), r"MY-PC\mla_owner")
        self.assertEqual(check(r"my-pc\mla_review", "MY-PC"), r"MY-PC\mla_review")
        self.assertEqual(check(r"MY-PC\mla-scanner", "MY-PC"), r"MY-PC\mla-scanner")

    def test_domain_builtin_service_group_and_ambiguous_accounts_hold(self):
        check = c._WindowsBrokerAPI._local_scm_account_name
        forbidden = (
            r"DOMAIN\mla_owner", r"NT AUTHORITY\SYSTEM",
            r"NT SERVICE\MyLocalAI.owner.v1", r"OTHER-PC\mla_owner",
            r".\SYSTEM", r".\NetworkService", r".\LocalService",
            ".\\", r".\user\extra", r".\trailing.",
            r".\space name", r"MY-PC\..", "mla_owner", "", None, 1,
        )
        for value in forbidden:
            with self.subTest(value=value), self.assertRaises(c.ProtectedBrokerHold):
                check(value, "MY-PC")

    def test_scm_config_cannot_replace_signed_nonce_and_service_key(self):
        import inspect
        authentication = inspect.getsource(c.exchange_protected_broker)
        self.assertIn("api.verify_signature(roots[role][2]", authentication)
        self.assertIn('body["challenge"] != nonce', authentication)
        self.assertIn('body["request_sha256"] != sha256(request).hexdigest()', authentication)
        self.assertIn('body["binding"] != binding', authentication)
        self.assertIn('body["status"] != "OK"', authentication)
        # Service-side exact Owner and Reviewer leases remain mandatory.
        server = inspect.getsource(c._ProtectedActionServer.process)
        self.assertIn("self.action_from_owner(payload, binding, action)", server)
        self.assertIn("self.live_scope(binding, action)", server)

    def test_invalid_computer_names_never_authorize_service_principal(self):
        for computer in ("", "MY-PC\\DOMAIN", "HOST.OTHER", " " * 5, "x"*16):
            with self.subTest(computer=computer), self.assertRaises(c.ProtectedBrokerHold):
                c._WindowsBrokerAPI._local_scm_account_name(r".\owner", computer)

    def test_service_cross_sid_proof_keeps_exact_pid_image_scm_and_controller_sid(self):
        import inspect
        code = inspect.getsource(c._WindowsBrokerAPI.authenticate_pipe)
        self.assertIn("QueryServiceStatusEx", code)
        self.assertIn("status[7] != pid.value", code)
        self.assertIn("roots[role][1]", code)
        self.assertIn("installed.kind != 0x10", code)
        self.assertIn("self._scm_account_sid(installed.account)", code)
        self.assertIn("open_process(0x1000, False, pid.value)", code)
        self.assertNotIn("open_process(0x1000 | 0x100000", code)
        server_pipe = inspect.getsource(c._serve_named_pipe)
        self.assertIn("open_process(0x1000, False, pid.value)", server_pipe)
        self.assertNotIn("open_process(0x1000 | 0x100000", server_pipe)
        self.assertIn("self.process_sid(current())", code)
        self.assertNotIn("self.process_sid(process)", code)
        self.assertNotIn("SetSecurityInfo", code)
        self.assertNotIn("SetEntriesInAclW", code)




class FrozenProtectedBundleInspectionTests(unittest.TestCase):
    """Synthetic image-tree verification; no Windows/SCM/CNG access."""

    def test_complete_tree_is_pinned_for_services_and_owner_ui(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "_internal"
            root.mkdir()
            (root / "app.pyc").write_bytes(b"trusted fixture only")
            nested = root / "native"
            nested.mkdir()
            (nested / "crypto.pyd").write_bytes(b"trusted fixture only")
            pinned = []
            c._pin_frozen_trust_bundle(root, pinned.append)
            self.assertEqual({p.name for p in pinned}, {"app.pyc", "crypto.pyd"})
        self.assertIn("_pin_frozen_trust_bundle(bundle, self.pin_path)",
                      inspect.getsource(c._WindowsProtectedServiceAPI.__init__))
        self.assertIn("_pin_frozen_trust_bundle(bundle, self.pin_path)",
                      inspect.getsource(c._OwnerInteractiveAPI.__init__))

    def test_unreadable_subdirectory_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.pyc").write_bytes(b"safe fixture")
            def unreadable(*args, **kwargs):
                self.assertFalse(kwargs["followlinks"])
                kwargs["onerror"](PermissionError("synthetic scandir denied"))
                yield from ()
            with patch("os.walk", unreadable):
                with self.assertRaises(c.ProtectedBrokerHold) as caught:
                    c._pin_frozen_trust_bundle(root, lambda _p: None)
            self.assertEqual(caught.exception.code, "PROTECTED_BROKER_IDENTITY")

    def test_directory_fanout_and_empty_bundle_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(c.ProtectedBrokerHold):
                c._pin_frozen_trust_bundle(root, lambda _p: None)
            def excessive_fanout(*args, **kwargs):
                yield str(root), ["dir"] * 2049, []
            with patch("os.walk", excessive_fanout):
                with self.assertRaises(c.ProtectedBrokerHold):
                    c._pin_frozen_trust_bundle(root, lambda _p: None)
            def excessive_depth(*args, **kwargs):
                for _ in range(2049):
                    yield str(root), [], []
            with patch("os.walk", excessive_depth):
                with self.assertRaises(c.ProtectedBrokerHold):
                    c._pin_frozen_trust_bundle(root, lambda _p: None)

    def test_elapsed_bundle_verification_budget_holds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("os.walk", return_value=iter([(str(root), [], [])])):
                with patch("time.monotonic", side_effect=[0.0, 15.0]):
                    with self.assertRaises(c.ProtectedBrokerHold) as caught:
                        c._pin_frozen_trust_bundle(root, lambda _p: None)
            self.assertEqual(caught.exception.code, "PROTECTED_BROKER_IDENTITY")


class ProtectedGitMirrorTraversalTests(unittest.TestCase):
    """Pure synthetic directory traversal: no Git, Windows service or F18 GO."""

    def test_protected_git_mirror_walk_is_complete_or_denies(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "objects"
            directory.mkdir()
            (directory / "safe-object").write_bytes(b"synthetic")
            rows = list(r._walk_verified_protected_git_mirror(Path(root)))
            self.assertEqual(len(rows), 2)
            self.assertTrue(any("safe-object" in names for _, _, names in rows))

        def synthetic_unreadable(*args, **kwargs):
            self.assertFalse(kwargs.get("followlinks"))
            self.assertTrue(callable(kwargs["onerror"]))
            kwargs["onerror"](PermissionError("synthetic unreadable mirror"))
            yield from ()

        with patch.object(r._os, "walk", synthetic_unreadable):
            with self.assertRaises(c.ProtectedBrokerHold) as caught:
                list(r._walk_verified_protected_git_mirror(Path("/synthetic/mirror")))
        self.assertEqual(caught.exception.code, "PROTECTED_BROKER_IDENTITY")
        self.assertIn("_walk_verified_protected_git_mirror(root, stopped=stopped)",
                      inspect.getsource(r._read_protected_git_candidate))

    def test_protected_git_mirror_directory_count_and_fanout_bounded(self):
        # These generators simulate huge protected mirrors; no Git invoked.
        def many_directories(*args, **kwargs):
            for index in range(1025):
                yield str(index), [], []
        with patch.object(r._os, "walk", many_directories):
            with self.assertRaises(c.ProtectedBrokerHold) as caught:
                list(r._walk_verified_protected_git_mirror(Path("/fake")))
        self.assertEqual(caught.exception.code, "PROTECTED_BROKER_IDENTITY")

        def excess_fanout(*args, **kwargs):
            yield "/fake", [str(i) for i in range(1025)], []
        with patch.object(r._os, "walk", excess_fanout):
            with self.assertRaises(c.ProtectedBrokerHold) as caught:
                list(r._walk_verified_protected_git_mirror(Path("/fake")))
        self.assertEqual(caught.exception.code, "PROTECTED_BROKER_IDENTITY")

    def test_protected_git_mirror_deadline_and_stop_denied(self):
        def two_directories(*args, **kwargs):
            yield "/fake", [], []
            yield "/fake/objects", [], []
        with patch.object(r._os, "walk", two_directories):
            with patch.object(r._timeForReview, "monotonic", side_effect=[0.0, 0.0, 10.0]):
                with self.assertRaises(c.ProtectedBrokerHold) as caught:
                    list(r._walk_verified_protected_git_mirror(Path("/fake")))
        self.assertEqual(caught.exception.code, "PROTECTED_BROKER_TIMEOUT")

        stopped = threading.Event()
        stopped.set()
        with patch.object(r._os, "walk", two_directories):
            with self.assertRaises(c.ProtectedBrokerHold) as caught:
                list(r._walk_verified_protected_git_mirror(Path("/fake"), stopped=stopped))
        self.assertEqual(caught.exception.code, "PROTECTED_BROKER_TIMEOUT")



    def test_protected_git_mirror_per_entry_timeout_and_stop_fail_closed(self):
        # The helper also gates child lstat/pinning in _read_protected_git_candidate.
        with patch.object(r._timeForReview, "monotonic", return_value=10.0):
            with self.assertRaises(c.ProtectedBrokerHold) as caught:
                r._guard_protected_mirror_scan_budget(0.0, threading.Event())
        self.assertEqual(caught.exception.code, "PROTECTED_BROKER_TIMEOUT")

        stopped = threading.Event()
        stopped.set()
        with patch.object(r._timeForReview, "monotonic", return_value=0.0):
            with self.assertRaises(c.ProtectedBrokerHold) as caught:
                r._guard_protected_mirror_scan_budget(0.0, stopped)
        self.assertEqual(caught.exception.code, "PROTECTED_BROKER_TIMEOUT")

        source = inspect.getsource(r._read_protected_git_candidate)
        self.assertGreaterEqual(source.count(
            "_guard_protected_mirror_scan_budget(mirror_started, stopped)"), 4)


class DefenderEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.request = d.DefenderOwnerScanRequest("a" * 64, "b" * 40, "SYNTHETIC-ONLY",
            "c" * 64, "d" * 64, 10, "e" * 64, "f" * 40, "1" * 64, 1)
        self.result = {"outcome": "COMPLETED_CLEAN", "content_sha256": "d" * 64,
            "content_size": 10, "scan_completed": True, "timed_out": False,
            "finding_count": 0, "engine_exit_code": 0, "scan_error_code": None,
            "detection_evidence_sha256": None, "remediation": "DISABLED", "policy_changed": False,
            "scan_reference": "SYNTHETIC-REFERENCE"}

    def classify(self, **changes):
        return d._classify_protected_defender_result({**self.result, **changes}, self.request)

    def test_clean_completes_without_execution_authority(self):
        result = self.classify()
        self.assertEqual(result.state, "COMPLETED_CLEAN")
        self.assertFalse(result.execution_allowed)
        self.assertFalse(result.f18_verified)

    def test_exit_two_without_detection_evidence_rejected(self):
        self.assertEqual(self.classify(outcome="MALWARE_DETECTED", finding_count=1,
            engine_exit_code=2).state, "RESULT_REJECTED_HOLD")

    def test_detection_requires_independent_evidence(self):
        self.assertEqual(self.classify(outcome="MALWARE_DETECTED", finding_count=1,
            engine_exit_code=2, detection_evidence_sha256="0" * 64).state, "MALWARE_DETECTED_HOLD")

    def test_error_exit_two_differs_from_malware(self):
        self.assertEqual(self.classify(outcome="SCAN_ERROR", finding_count=None,
            scan_completed=False, engine_exit_code=2, scan_error_code="ENGINE_FAILED").state, "SCAN_ERROR_HOLD")

    def test_timeout_and_unknown_are_distinct(self):
        self.assertEqual(self.classify(outcome="TIMEOUT", finding_count=None, scan_completed=False,
            timed_out=True, engine_exit_code=None, scan_error_code="SCAN_TIMEOUT").state, "SCAN_TIMEOUT_HOLD")
        self.assertEqual(self.classify(outcome="UNKNOWN", finding_count=None, scan_completed=False,
            engine_exit_code=2, scan_error_code="COMPLETION_NOT_PROVEN").state, "UNKNOWN_HOLD")

    def test_scan_id_collision_and_old_detection_are_not_accepted(self):
        target = r"C:\\private\\scan_123.py"
        events = [
            {"record": 5, "id": 1000,
             "fields": {"Scan Resources": "file:_" + target,
                        "Scan ID": "scan-1"}, "evidence_sha256": "a" * 64},
            {"record": 6, "id": 1001,
             "fields": {"Scan ID": "scan-1"}, "evidence_sha256": "b" * 64},
        ]
        unrelated_start = {"record": 7, "id": 1000,
            "fields": {"Scan Resources": r"C:\\private\\other.py",
                       "Scan ID": "scan-1"}, "evidence_sha256": "c" * 64}
        self.assertEqual(
            d._defender_completion_evidence(events + [unrelated_start], target, 4),
            (False, []),
        )
        stale = {"record": 4, "id": 1116, "fields": {
            "Path": target, "Threat ID": "T-1", "Threat Name": "Synthetic",
            "Scan ID": "scan-1"}, "evidence_sha256": "d" * 64}
        self.assertEqual(
            d._defender_completion_evidence([stale] + events, target, 3),
            (True, []),
        )
        foreign = {**stale, "record": 8, "fields": {
            **stale["fields"], "Scan ID": "other-scan"}}
        self.assertEqual(
            d._defender_completion_evidence(events + [foreign], target, 4),
            (True, []),
        )
        same = {**foreign, "fields": {
            **foreign["fields"], "Scan ID": "scan-1"}}
        self.assertEqual(
            d._defender_completion_evidence(events + [same], target, 4),
            (True, ["d" * 64]),
        )

    def test_same_path_detection_without_scan_id_is_ambiguous_hold(self):
        target = r"C:\\private\\scan_123.py"
        events = [
            {"record": 5, "id": 1000, "fields": {
                "Scan Resources": "file:_" + target, "Scan ID": "scan-1"},
             "evidence_sha256": "a" * 64},
            {"record": 6, "id": 1001, "fields": {
                "Scan ID": "scan-1"}, "evidence_sha256": "b" * 64},
        ]
        for suspicious in (
            {"Path": target, "Threat ID": "T-1", "Threat Name": "Synthetic"},
            {"Path": target, "Scan ID": "", "Threat ID": "T-1", "Threat Name": "Synthetic"},
            {"Path": target, "Scan ID": "scan-1", "Threat ID": "T-1"},
            {"Path": target, "Scan ID": "scan-1", "Threat Name": "Synthetic"},
        ):
            with self.subTest(fields=suspicious):
                ambiguous = {"record": 7, "id": 1116, "fields": suspicious,
                             "evidence_sha256": "c" * 64}
                self.assertEqual(
                    d._defender_completion_evidence(events + [ambiguous], target, 4),
                    (False, []),
                )
        # A clearly unrelated explicit scan ID remains unrelated.
        foreign = {"record": 7, "id": 1116, "fields": {
            "Path": target, "Scan ID": "other-scan",
            "Threat ID": "T-1", "Threat Name": "Synthetic"},
            "evidence_sha256": "d" * 64}
        self.assertEqual(d._defender_completion_evidence(events + [foreign], target, 4),
                         (True, []))

    def test_same_scan_detection_missing_or_foreign_resource_blocks_clean(self):
        # Same scan identifier but missing/wrong Path must never be treated
        # as unrelated evidence. This is a synthetic log-only policy test.
        target = r"C:\\private\\scan_123.py"
        events = [
            {"record": 5, "id": 1000, "fields": {
                "Scan Resources": "file:_" + target, "Scan ID": "scan-1"},
             "evidence_sha256": "a" * 64},
            {"record": 6, "id": 1001, "fields": {"Scan ID": "scan-1"},
             "evidence_sha256": "b" * 64},
        ]
        for wrong in (
            {"Scan ID": "scan-1", "Threat ID": "T-1", "Threat Name": "Synthetic"},
            {"Scan ID": "scan-1", "Path": r"C:\\private\\other.py",
             "Threat ID": "T-1", "Threat Name": "Synthetic"},
            {"Scan ID": "scan-1", "Path": target,
             "Threat ID": "T-1", "Threat Name": "Synthetic"},
        ):
            with self.subTest(wrong=wrong):
                detection = {"record": 7, "id": 1116, "fields": wrong,
                             "evidence_sha256": "c" * 64 if "Path" not in wrong else "INVALID"}
                self.assertEqual(
                    d._defender_completion_evidence(events + [detection], target, 4),
                    (False, []),
                )
        matching = {"record": 7, "id": 1116,
            "fields": {"Scan ID": "scan-1", "Path": target,
                       "Threat ID": "T-1", "Threat Name": "Synthetic"},
            "evidence_sha256": "c" * 64}
        self.assertEqual(
            d._defender_completion_evidence(events + [matching], target, 4),
            (True, ["c" * 64]),
        )


    def test_same_scan_detection_requires_exact_scan_id(self):
        target = r"C:\\private\\scan_123.py"
        events = [
            {"record": 5, "id": 1000, "fields": {
                "Scan Resources": "file:_" + target, "Scan ID": "scan-1"},
             "evidence_sha256": "a" * 64},
            {"record": 6, "id": 1001, "fields": {
                "Scan ID": "scan-1"}, "evidence_sha256": "b" * 64},
            {"record": 7, "id": 1006, "fields": {
                "Path": target, "Scan ID": "scan-1",
                "Threat ID": "T-1", "Threat Name": "Synthetic"},
             "evidence_sha256": "c" * 64},
        ]
        self.assertEqual(d._defender_completion_evidence(events, target, 4),
                         (True, ["c" * 64]))
        events[-1]["fields"]["Scan ID"] = None
        self.assertEqual(d._defender_completion_evidence(events, target, 4),
                         (False, []))

    def test_file_hash_policy_and_bool_count_spoofs_rejected(self):
        for changed in ({"content_sha256": "0" * 64}, {"content_size": 11},
                        {"policy_changed": True}, {"remediation": "ENABLED"},
                        {"finding_count": False}, {"engine_exit_code": False}):
            with self.subTest(changed=changed):
                self.assertEqual(self.classify(**changed).state, "RESULT_REJECTED_HOLD")

    def test_defender_event_collection_has_shared_time_and_stop_budget(self):
        # Synthetic budget validation only. No Defender service, event log,
        # Windows policy or file scan is accessed by this test.
        with patch.object(d._defender_time, "monotonic", return_value=19.99):
            d._guard_defender_event_budget(0.0)
        with patch.object(d._defender_time, "monotonic", return_value=20.0):
            with self.assertRaises(c.ProtectedBrokerHold) as caught:
                d._guard_defender_event_budget(0.0)
        self.assertEqual(caught.exception.code, "PROTECTED_BROKER_TIMEOUT")
        stopped = threading.Event()
        stopped.set()
        with patch.object(d._defender_time, "monotonic", return_value=0.0):
            with self.assertRaises(c.ProtectedBrokerHold) as caught:
                d._guard_defender_event_budget(0.0, stopped)
        self.assertEqual(caught.exception.code, "PROTECTED_BROKER_TIMEOUT")
        source = inspect.getsource(d._defender_events_after)
        self.assertGreaterEqual(
            source.count("_guard_defender_event_budget(started, stopped)"), 4
        )


    def test_postscan_event_overflow_fails_closed_without_native_scan(self):
        # Local synthetic policy check only: no Defender, OS services or
        # protected scan executed. Pre-scan cursor discovery is reverse-order
        # bounded; post-scan decision cannot omit an older safety event.
        for count in (0, 1, 255):
            with self.subTest(count=count):
                d._deny_truncated_defender_events(True, count)
        for count in (256, 257):
            with self.subTest(count=count), self.assertRaises(c.ProtectedBrokerHold):
                d._deny_truncated_defender_events(True, count)
        d._deny_truncated_defender_events(False, 256)
        for bad in (-1, 1.5, None):
            with self.subTest(bad=bad), self.assertRaises(c.ProtectedBrokerHold):
                d._deny_truncated_defender_events(bad, 0)
        code = inspect.getsource(d._defender_events_after)
        self.assertIn("range(257 if require_complete else 256)", code)
        self.assertIn("_deny_truncated_defender_events(require_complete, len(result))", code)
        self.assertLess(code.index("_deny_truncated_defender_events(require_complete, len(result))"),
                        code.index("render(None, event, 1, 0"))
        service = inspect.getsource(d._serve_defender_scan)
        self.assertIn("_defender_events_after(api, 0, stopped=stopped)", service)
        self.assertIn("_defender_events_after(api, cursor, require_complete=True, stopped=stopped)", service)

    def test_event_completion_is_exact_scan_and_resource(self):
        target = r"C:\private\scan_123.py"
        events = [
            {"record": 5, "id": 1000, "fields": {"Scan Resources": "file:_" + target, "Scan ID": "scan-1"}, "evidence_sha256": "a" * 64},
            {"record": 6, "id": 1001, "fields": {"Scan ID": "scan-1"}, "evidence_sha256": "b" * 64},
        ]
        self.assertEqual(d._defender_completion_evidence(events, target, 4), (True, []))
        self.assertEqual(d._defender_completion_evidence(events, target + "x", 4), (False, []))
        self.assertEqual(d._defender_completion_evidence(events, target, 6), (False, []))
        events.append({"record": 7, "id": 1002, "fields": {"Scan ID": "scan-1"}, "evidence_sha256": "c" * 64})
        self.assertEqual(d._defender_completion_evidence(events, target, 4), (False, []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
