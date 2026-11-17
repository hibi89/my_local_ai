"""Local dashboard synthetic HTTP smoke, no browser or public network."""
import json
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from my_local_ai.ui.status_view import load_snapshot, StatusSnapshot
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

    def test_accessible_static_html_has_no_script_or_actions(self):
        html = render_html(load_snapshot(ROOT)).decode("utf-8")
        self.assertIn('lang="ko"', html)
        self.assertIn('aria-label=', html)
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

    def test_invalid_status_file_fails_closed(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp:
            self.assertRaises((OSError, ValueError),load_snapshot,temp)

if __name__ == "__main__":
    unittest.main()
