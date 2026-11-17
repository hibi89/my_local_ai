"""Adversarial input fixtures for loopback-only policy, no network calls."""
import unittest

from my_local_ai.ax_runtime.provider_policy import LoopbackEndpoint, ProviderHold
from my_local_ai.advisors.eai import inspect_optional_eai

PLAN="b"*64
SRC="a"*40


class NoExfilPolicyTests(unittest.TestCase):
    def test_private_cloud_link_local_and_dns_endpoints_never_allowed(self):
        bad=(
            "https://127.0.0.1:11434",
            "http://localhost:11434",
            "http://169.254.169.254:80",
            "http://10.0.0.1:11434",
            "http://192.168.0.1:11434",
            "http://8.8.8.8:11434",
            "http://127.0.0.1:11434/api/pull",
            "http://127.0.0.1:11434?model=qwen3",
            "http://user:pass@127.0.0.1:11434",
            "http://[::ffff:127.0.0.1]:11434",
            "file:///etc/passwd",
        )
        for endpoint in bad:
            with self.subTest(endpoint=endpoint),self.assertRaises(ProviderHold):
                LoopbackEndpoint.parse(endpoint)

    def test_only_literal_local_ip_supported(self):
        endpoint=LoopbackEndpoint.parse("http://127.0.0.1:11434")
        self.assertEqual(endpoint.host,"127.0.0.1")
        self.assertEqual(endpoint.port,11434)

    def test_advisor_cannot_exfiltrate_via_command_or_private_path(self):
        raw='{"version":1,"origin":"OPTIONAL_EAI_ADVISOR_DATA","source_git_sha":"' + SRC + '","plan_sha256":"' + PLAN + '","non_authoritative":true,"hints":[],"network_url":"https://cloud.example/upload"}'
        value=inspect_optional_eai(
            envelope_json=raw,eligible_ids=frozenset({"TASK-001"}),
            trusted_source_sha=SRC,trusted_plan_sha=PLAN,
        )
        self.assertEqual(value.status,"INVALID_OR_UNAVAILABLE_FALLBACK")
        self.assertFalse(value.executable)

    def test_no_owner_go_from_synthetic_advisor(self):
        result=inspect_optional_eai(
            envelope_json=None,eligible_ids=frozenset(),
            trusted_source_sha=SRC,trusted_plan_sha=PLAN,
        )
        self.assertFalse(result.executable)
        self.assertTrue(result.independent_controller_required)


if __name__=="__main__":
    unittest.main()
