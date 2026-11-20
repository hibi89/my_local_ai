"""Static workbench clipboard safety checks; no Owner-device/browser attestation."""
from pathlib import Path
import unittest

from my_local_ai.ui.workbench_page import render_workbench


class ObservationCopyUiTests(unittest.TestCase):
    def test_explicit_disabled_button_and_no_hidden_upload(self):
        page = render_workbench("/work/test-session", "desk").decode("utf-8")
        self.assertIn('id="longrun-window"', page)
        self.assertIn('id="copy-observation" class="quiet-button" disabled', page)
        self.assertIn('id="copy-observation-notice"', page)
        self.assertNotIn('type="file"', page)
        script = (Path(__file__).resolve().parents[2]
                  / "src" / "my_local_ai" / "ui" / "workbench.js").read_text("utf-8")
        self.assertIn("observationCopy.addEventListener('click'", script)
        self.assertIn("navigator.clipboard.writeText", script)
        self.assertIn("UNATTESTED_LOCAL_NUMERIC_RECEIPTS", script)
        self.assertIn("observationCopy.disabled = !observationCopyReceipt", script)
        # Only an explicit click can write to the user's clipboard.
        self.assertEqual(script.count(
            "await navigator.clipboard.writeText(JSON.stringify(observationCopyReceipt, null, 2))"
        ), 1)


if __name__ == "__main__":
    unittest.main()
