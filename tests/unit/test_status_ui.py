"""Local dashboard synthetic HTTP smoke, no browser or public network."""
import json
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from my_local_ai.ui.status_view import load_snapshot, load_synthetic_evidence, StatusSnapshot
from my_local_ai.ui.local_dashboard import LocalStatusServer, host_allowed, origin_allowed, render_html

ROOT = Path(__file__).resolve().parents[2]

class StatusUiTests(unittest.TestCase):
    def test_public_snapshot_redacted(self):
        public = load_snapshot(ROOT).to_public_dict()
        self.assertEqual(public["total_req"], 30)
        self.assertTrue(public["p2_locked"])
        self.assertEqual(public["verification"], "UNASSESSED")
        self.assertFalse(public["operation_allowed"])
        self.assertEqual(public["provider_remote"], "OFF_NOT_APPROVED")
        self.assertNotIn("secret", json.dumps(public).lower())

    def test_code_only_ready_is_distinct_from_runtime_ready(self):
        result=load_snapshot(ROOT).to_public_dict()
        queue=json.loads((ROOT/"INSTANT_TASK_QUEUE.json").read_text(encoding="utf-8"))
        self.assertEqual(result["p1_code_ready_ids"], queue["first_ready"])
        self.assertEqual(result["p1_code_ready_tasks"], len(queue["first_ready"]))
        self.assertEqual(result["ready_tasks"], 0)
        self.assertFalse(result["operation_allowed"])

    def test_dashboard_does_not_confuse_p1_code_ready_and_execution(self):
        html=render_html(load_snapshot(ROOT)).decode("utf-8")
        self.assertIn("코드 작성 READY",html)
        self.assertIn("실행 READY",html)
        self.assertIn(load_snapshot(ROOT).to_public_dict()["p1_code_ready_ids"][0],html)
        self.assertIn("실행 허가 아님",html)
        self.assertNotIn("<script",html)

    def test_accessible_static_html_has_no_script_or_actions(self):
        html = render_html(load_snapshot(ROOT)).decode("utf-8")
        self.assertIn('lang="ko"', html)
        self.assertIn('aria-label=', html)
        self.assertIn("실사용 승인:", html)
        self.assertIn("중지·재개 제어:", html)
        self.assertIn("<progress", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("<form", html)
        self.assertNotIn("name=\"password\"", html)

    def test_host_and_origin_guards(self):
        self.assertTrue(host_allowed("127.0.0.1:41234",41234))
        self.assertTrue(origin_allowed("http://localhost:41234",41234))
        self.assertFalse(host_allowed("attacker.invalid:41234",41234))
        self.assertFalse(host_allowed("127.0.0.1:41234.evil",41234))
        self.assertFalse(origin_allowed("https://localhost:41234",41234))

    def test_http_read_only_loopback(self):
        with LocalStatusServer(ROOT, 0) as server:
            thread = threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urlopen(base + "/status.json", timeout=2) as r:
                    self.assertEqual(r.status,200)
                    self.assertEqual(r.headers["X-Frame-Options"],"DENY")
                    data = json.loads(r.read())
                    self.assertFalse(data["operation_allowed"])
                for request in (
                    Request(base + "/status.json", headers={"Host":"attacker.invalid"}),
                    Request(base + "/status.json", headers={"Origin":"http://attacker.invalid"}),
                    Request(base + "/", data=b"write_attempt", method="POST"),
                ):
                    with self.subTest(url=request.full_url), self.assertRaises(HTTPError) as e:
                        urlopen(request,timeout=2)
                    self.assertIn(e.exception.code,(403,405))
            finally:
                server.shutdown()
                thread.join(timeout=2)

    def test_evidence_endpoint_is_redacted_and_not_owner_proof(self):
        evidence=load_synthetic_evidence(ROOT).to_public_dict()
        self.assertEqual(evidence["status"],
                         "REPORTED_P1_SYNTHETIC_CI_NOT_INDEPENDENTLY_ATTESTED")
        self.assertEqual(evidence["f18"],"SECURITY_HOLD")
        self.assertEqual(evidence["real_windows"],"NOT_RUN")
        self.assertFalse(evidence["execution_allowed"])
        with LocalStatusServer(ROOT,0) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base=f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urlopen(base+"/evidence.json",timeout=2) as response:
                    self.assertEqual(response.status,200)
                    self.assertEqual(response.headers["Cache-Control"],"no-store, max-age=0")
                    body=json.loads(response.read())
                    self.assertEqual(body,evidence)
                    self.assertFalse(body["owner_go"])
                with urlopen(base+"/",timeout=2) as response:
                    html=response.read().decode("utf-8")
                    self.assertIn("/evidence.json",html)
                    self.assertIn("합성 CI 보고",html)
                    self.assertNotIn("<script",html)
            finally:
                server.shutdown()
                thread.join(timeout=2)

    def test_evidence_metadata_never_claims_windows_or_real_audit(self):
        evidence=load_synthetic_evidence(ROOT)
        self.assertEqual(evidence.p2,"LOCKED")
        self.assertFalse(evidence.owner_go)
        self.assertTrue(evidence.run_id>0)
        self.assertEqual(
            evidence.unit_tests + evidence.mock_integration_tests + evidence.security_tests,
            evidence.to_public_dict()["synthetic_total"],
        )

    def test_invalid_status_file_fails_closed(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp:
            self.assertRaises((OSError, ValueError),load_snapshot,temp)

if __name__ == "__main__":
    unittest.main()


class UiPhaseConsistencyTests(unittest.TestCase):
    def test_queue_and_gate_req_counters_must_agree_before_render(self):
        import shutil
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            for name in ("WORK_PHASE_GATES.json", "INSTANT_TASK_QUEUE.json"):
                shutil.copy2(ROOT / name, directory / name)
            qpath = directory / "INSTANT_TASK_QUEUE.json"
            queue = json.loads(qpath.read_text(encoding="utf-8"))
            queue["code_completed_req"] += 1
            qpath.write_text(json.dumps(queue), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "inconsistent"):
                load_snapshot(directory)

    def test_runtime_ready_in_source_queue_fails_closed(self):
        import shutil
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            for name in ("WORK_PHASE_GATES.json", "INSTANT_TASK_QUEUE.json"):
                shutil.copy2(ROOT / name, directory / name)
            qpath = directory / "INSTANT_TASK_QUEUE.json"
            queue = json.loads(qpath.read_text(encoding="utf-8"))
            queue["operational_ready"] = ["MLA-019"]
            qpath.write_text(json.dumps(queue), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_snapshot(directory)



class OptionalAdvisorStatusTests(unittest.TestCase):
    def test_dashboard_discloses_eai_off_default_without_execution_claim(self):
        result = load_snapshot(ROOT).to_public_dict()
        self.assertEqual(result["optional_eai_default"], "OFF")
        self.assertFalse(result["optional_eai_can_grant_authority"])
        html = render_html(load_snapshot(ROOT)).decode("utf-8")
        self.assertIn("EAI 선택형 분석", html)
        self.assertIn("기본 OFF", html)
