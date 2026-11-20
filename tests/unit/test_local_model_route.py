"""No models, network, external AI, GPU or generated code are executed."""
import unittest

from my_local_ai.ax_runtime.local_model_route import choose_draft_route
from my_local_ai.ax_runtime.provider_policy import ProviderHold


class RouteTests(unittest.TestCase):
    def test_small_serial_tasks_keep_one_local_model_warm(self):
        route = choose_draft_route("tiny task", 448, next_eligible=True,
                                   pause_requested=False)
        self.assertEqual(route.role, "LOCAL_QWEN_DRAFT")
        self.assertEqual(route.source, "LOCAL_LOOPBACK_ONLY")
        self.assertEqual(route.context_tokens, 4096)
        self.assertEqual(route.keep_alive_seconds, 90)

    def test_final_paused_and_standalone_release_model(self):
        for follow, pause in ((False, False), (True, True), (False, True)):
            with self.subTest(follow=follow, pause=pause):
                r = choose_draft_route("task", 448, next_eligible=follow,
                                       pause_requested=pause)
                self.assertEqual(r.keep_alive_seconds, 0)

    def test_larger_task_uses_only_pinned_8192_context(self):
        plan = choose_draft_route("x" * 3700, 448, next_eligible=True,
                                  pause_requested=False)
        self.assertEqual(plan.context_tokens, 8192)
        self.assertEqual(plan.keep_alive_seconds, 90)

    def test_unsafe_or_unbounded_requests_hold_without_model_call(self):
        for prompt, tokens, follow, pause in (
            ("x" * 7900, 448, False, False), ("", 448, False, False),
            ("bad\x00path", 448, False, False), ("task", True, False, False),
            ("task", 1540, False, False), ("task", 448, 1, False),
            ("task", 448, False, "no"),
        ):
            with self.subTest(prompt_len=len(prompt), tokens=tokens, follow=follow,
                              pause=pause), self.assertRaises(ProviderHold):
                choose_draft_route(prompt, tokens, next_eligible=follow,
                                   pause_requested=pause)


if __name__ == "__main__":
    unittest.main()
