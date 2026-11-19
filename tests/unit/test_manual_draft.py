"""Regression coverage for the draft workspace. No real models or GitHub writes."""
from __future__ import annotations

import base64
from hashlib import sha1
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from my_local_ai.ax_runtime.draft_documents import DraftError, read_document
from my_local_ai.ax_runtime.manual_draft import LocalDrafts
from my_local_ai.ax_runtime.ollama_provider import UntrustedGeneration


class DraftDocumentsTests(unittest.TestCase):
    def test_branched_document_is_read_at_resolved_commit(self):
        original = "# Local design\nReturn a sorted list.\n".encode()
        blob_id = sha1(f"blob {len(original)}\0".encode() + original).hexdigest()
        commit = "1" * 40
        exact = "/repos/example/project/contents/docs/final.md?ref=" + commit
        responses = {
            "/repos/example/project/commits/design": None,
            "/repos/example/project/commits/design%2Fphase-1": commit.encode(),
            exact: json.dumps({
                "type": "file", "encoding": "base64", "path": "docs/final.md",
                "content": base64.b64encode(original).decode(), "size": len(original), "sha": blob_id,
            }).encode(),
        }
        with patch("my_local_ai.ax_runtime.draft_documents._github_get",
                   side_effect=lambda endpoint, *args: responses[endpoint]) as get:
            result = read_document(
                "https://github.com/example/project/blob/design/phase-1/docs/final.md?token=omit", {},
            )
            get.assert_called_with(exact)
        self.assertEqual(result.revision, commit)
        self.assertEqual(result.text.encode(), original)
        self.assertNotIn("token", result.origin)

    def test_document_host_and_file_hash_are_validated(self):
        with patch("my_local_ai.ax_runtime.draft_documents._github_get") as get:
            with self.assertRaises(DraftError):
                read_document("https://github.com.unexpected.invalid/user/project/blob/main/file.md", {})
            get.assert_not_called()
            raw = b"bad marker"
            get.return_value = json.dumps({
                "type": "file", "encoding": "base64", "path": "file.md", "size": len(raw),
                "content": base64.b64encode(raw).decode(), "sha": "2" * 40,
            }).encode()
            with self.assertRaises(DraftError):
                read_document("https://github.com/example/project/blob/" + "1" * 40 + "/file.md", {})


class FixtureProvider:
    def __init__(self, path, text):
        self.path = path
        self.text = text
        self.prompt = ""

    def generate(self, prompt, **options):
        self.prompt = prompt
        assert options["allow_generation"] and options["structured"]
        return UntrustedGeneration(json.dumps({
            "summary": "prepared draft", "files": [{"path": self.path, "content": self.text}],
        }), "qwen3:4b-instruct")


class LocalDraftsTests(unittest.TestCase):
    def await_result(self, app):
        deadline = time.monotonic() + 3
        state = app.snapshot()
        while state["state"] == "working" and time.monotonic() < deadline:
            time.sleep(.01)
            state = app.snapshot()
        return state

    def payload(self, workspace=""):
        return {"instructions": "Add date sorting.", "blueprint": "Input type is a list.",
                "paths": "src/dates.py", "workspace": str(workspace)}

    def test_real_output_folder_excludes_originals_and_writes_source_and_evidence(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            before = root / "project" / "src" / "dates.py"
            before.parent.mkdir(parents=True)
            original = "MARKER = 7\n"
            before.write_bytes(original.encode())
            candidate = original + "def sorted_dates(dates):\n    return sorted(dates)\n"
            provider = FixtureProvider("src/dates.py", candidate)
            app = LocalDrafts(root / "drafts", provider=provider)
            self.assertEqual(app.start(self.payload(before.parents[1]))["state"], "working")
            result = self.await_result(app)
            self.assertEqual(result["state"], "done", result["message"])
            self.assertIn(original.strip(), provider.prompt)
            self.assertIn("Input type is a list.", provider.prompt)
            self.assertEqual(before.read_bytes(), original.encode())
            target = Path(result["folder"]) / "src/dates.py"
            self.assertEqual(target.read_bytes(), candidate.encode())
            self.assertIn("+def sorted_dates", result["files"][0]["diff"])
            self.assertEqual(result["files"][0]["syntax"], "Python 문법 확인")
            self.assertEqual(len(result["sources"]), 2)

    def test_unsafe_model_path_never_leaves_a_published_draft(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = LocalDrafts(root / "drafts", provider=FixtureProvider("../other.py", "pass\n"))
            with self.assertRaises(DraftError):
                app.start({**self.payload(), "paths": ".env.json"})
            app.start(self.payload())
            result = self.await_result(app)
            self.assertEqual(result["state"], "error")
            self.assertFalse((root / "other.py").exists())
            self.assertEqual(list((root / "drafts").iterdir()), [])

    def test_new_file_can_be_drafted_from_documents_alone(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            provider = FixtureProvider("report.py", "READY = True\n")
            app = LocalDrafts(root / "drafts", provider=provider)
            app.start({**self.payload(), "paths": ""})
            result = self.await_result(app)
            self.assertEqual(result["state"], "done", result["message"])
            self.assertIn("New files only", provider.prompt)
            self.assertTrue((Path(result["folder"]) / "report.py").is_file())


if __name__ == "__main__":
    unittest.main()
