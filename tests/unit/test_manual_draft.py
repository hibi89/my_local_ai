"""Regression coverage for the draft workspace. No real models or GitHub writes."""
from __future__ import annotations

import base64
from hashlib import sha1
from itertools import count
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
    def __init__(self, path, text, before=None):
        self.path = path
        self.text = text
        self.before = before
        self.prompt = ""

    def generate(self, prompt, **options):
        self.prompt = prompt
        assert options["allow_generation"] and options["structured"]
        reply = {"summary": "prepared draft"}
        if self.before is None:
            reply["files"] = [{"path": self.path, "content": self.text}]
        else:
            reply["edits"] = [{"path": self.path, "before": self.before, "after": self.text}]
        return UntrustedGeneration(json.dumps(reply), "qwen3:4b-instruct")


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
            self.assertFalse(any(path.is_dir() for path in (root / "drafts").iterdir()))

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

    def test_pasted_handoff_resolves_docs_and_updates_original_from_an_exact_anchor(self):
        revision = "2" * 40
        path = "src/server.py"
        original = "OPTION = 7\r\n" + ("# keep the remaining file as-is\r\n" * 100)
        document = "The server should default to OPTION = 8."
        repo = "/repos/example/project"
        responses = {
            f"{repo}/commits/integration%2Fone": revision.encode(),
            f"{repo}/git/trees/{revision}?recursive=1": json.dumps({
                "tree": [
                    {"path": name, "size": size, "mode": "100644", "type": "blob"}
                    for name, size in ((path, len(original)), ("src/gui/server.py", 20))
                ],
            }).encode(),
        }
        for name, text in ((path, original), ("docs/final.md", document)):
            content = text.encode()
            responses[f"{repo}/contents/{name}?ref={revision}"] = json.dumps({
                "type": "file", "encoding": "base64", "path": name, "size": len(content),
                "content": base64.b64encode(content).decode(),
                "sha": sha1(f"blob {len(content)}\0".encode() + content).hexdigest(),
            }).encode()
        message = (
            "Repository: example/project\nBranch: integration/one\n"
            "## 읽을 문서\n- docs/final.md\n"
            "## 작업 우선순위\nChange the server default option to 8.\n"
            "## 제외\n- src/gui/**\n"
            "## 범위\n수정 허용 대상:\n\n- src/**\n"
        )
        provider = FixtureProvider(path, "OPTION = 8\n", "OPTION = 7\n")
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "drafts"
            with patch("my_local_ai.ax_runtime.draft_documents._github_get",
                       side_effect=lambda endpoint, *args: responses[endpoint]), patch(
                       "my_local_ai.ax_runtime.manual_draft.monotonic", side_effect=count(50)):
                app = LocalDrafts(root, provider=provider)
                started = app.start({"message": message})
                result = self.await_result(app)
            self.assertEqual(started["state"], "working")
            self.assertEqual(result["state"], "done", result["message"])
            self.assertEqual(result["plan"]["paths"], [path])
            self.assertTrue(result["plan"]["narrowed"])
            self.assertEqual(result["plan"]["revision"], revision)
            self.assertIn(document, provider.prompt)
            self.assertEqual(result["sources"][-1]["revision"], revision)
            expected = original.replace("OPTION = 7", "OPTION = 8")
            self.assertEqual((Path(result["folder"]) / path).read_bytes(), expected.encode())
            self.assertGreater(result["elapsed_ms"], 0)
            self.assertEqual(result["total_ms"], result["elapsed_ms"])
            self.assertEqual(LocalDrafts(root).snapshot()["total_ms"], result["total_ms"])

    def test_pasted_message_can_create_a_file_and_a_failed_job_keeps_total(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "drafts"
            provider = FixtureProvider("src/report.py", "READY = True\n")
            clock = count(50)
            with patch("my_local_ai.ax_runtime.manual_draft.monotonic", side_effect=clock):
                app = LocalDrafts(root, provider=provider)
                app.start({"message": "Create a local readiness module.\n작업 파일: src/report.py"})
                first = self.await_result(app)
                self.assertEqual(first["state"], "done", first["message"])
                app.start({"message": "작업 파일: ../unsafe.py"})
                second = self.await_result(app)
            self.assertEqual(second["state"], "error")
            self.assertEqual(second["total_ms"], first["elapsed_ms"] + second["elapsed_ms"])
            self.assertEqual(LocalDrafts(root).snapshot()["total_ms"], second["total_ms"])


if __name__ == "__main__":
    unittest.main()
