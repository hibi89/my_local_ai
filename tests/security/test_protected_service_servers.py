"""Authorized narrow server regression: synthetic inputs, no native services.

Test transport signatures intentionally use a synthetic HMAC backend. They are
never TPM/ECDSA/OS-principal evidence and cannot authenticate production IPC.
No candidate code, candidate test, Git process or Defender scan is executed.
"""
import base64
import hashlib
import hmac
import json
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

    def test_pipe_client_has_duplex_access_without_server_creation(self):
        # Generic write includes FILE_CREATE_PIPE_INSTANCE. The client must
        # request exactly the narrower rights granted by the server pipe DACL.
        self.assertEqual(c._BROKER_PIPE_CLIENT_ACCESS & 3, 3)
        self.assertEqual(c._BROKER_PIPE_CLIENT_ACCESS & 4, 0)
        self.assertEqual(c._BROKER_PIPE_CLIENT_ACCESS & 0xC0000000, 0)


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

    def test_file_hash_policy_and_bool_count_spoofs_rejected(self):
        for changed in ({"content_sha256": "0" * 64}, {"content_size": 11},
                        {"policy_changed": True}, {"remediation": "ENABLED"},
                        {"finding_count": False}, {"engine_exit_code": False}):
            with self.subTest(changed=changed):
                self.assertEqual(self.classify(**changed).state, "RESULT_REJECTED_HOLD")

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
