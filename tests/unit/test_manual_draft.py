"""Regression coverage for the draft workspace. No real models or GitHub writes."""
from __future__ import annotations

import base64
from hashlib import sha1
from itertools import count
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from my_local_ai.ax_runtime.draft_documents import DraftDocument, DraftError, read_document
from my_local_ai.ax_runtime.draft_recovery import GeminiDraftAdvisor
from my_local_ai.ax_runtime.draft_timing import estimated_duration, recorded_time
from my_local_ai.ax_runtime.manual_draft import LocalDrafts
from my_local_ai.ax_runtime.ollama_provider import OllamaProvider, UntrustedGeneration
from my_local_ai.ax_runtime.provider_policy import ProviderHold
from my_local_ai.ax_runtime.worker_lock import OneModelLock


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
        original = "OPTION = 7\r\n" + ('# keep the "remaining" \\ server configuration as-is\r\n' * 100)
        document = "The server should default to OPTION = 8.\n\n"
        document_paths = [f"docs/design-{index}.md" for index in range(8)]
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
        for name, text in [(path, original), *((name, document * 170) for name in document_paths)]:
            content = text.encode()
            responses[f"{repo}/contents/{name}?ref={revision}"] = json.dumps({
                "type": "file", "encoding": "base64", "path": name, "size": len(content),
                "content": base64.b64encode(content).decode(),
                "sha": sha1(f"blob {len(content)}\0".encode() + content).hexdigest(),
            }).encode()
        message = (
            "Repository: example/project\nBranch: integration/one\n"
            "## 읽을 문서\n" + "\n".join(f"- {name}" for name in document_paths)
            + "\n## 작업 우선순위\nChange the server default option to 8.\n"
            + "## 제외\n- src/gui/**\n"
            + "## 범위\n수정 허용 대상:\n\n- src/**\n"
            + "## 배경\n" + "기존 구현과 문서의 나머지 항목을 유지합니다.\n" * 180
        )
        provider = OllamaProvider()
        reply = {"summary": "prepared draft", "edits": [
            {"path": path, "before": "OPTION = 7\n", "after": "OPTION = 8\n"},
        ]}
        ollama_responses = [{"models": [{"name": "qwen3:4b-instruct"}]},
                            {"done": True, "response": json.dumps(reply)}]
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "drafts"
            with patch("my_local_ai.ax_runtime.draft_documents._github_get",
                       side_effect=lambda endpoint, *args: responses[endpoint]), patch(
                       "my_local_ai.ax_runtime.manual_draft.monotonic", side_effect=count(50)), patch.object(
                       provider, "_request", side_effect=ollama_responses) as transport:
                app = LocalDrafts(root, provider=provider)
                started = app.start({"message": message})
                result = self.await_result(app)
            self.assertEqual(started["state"], "working")
            self.assertEqual(result["state"], "done", result["message"])
            self.assertEqual(result["plan"]["paths"], [path])
            self.assertTrue(result["plan"]["narrowed"])
            self.assertEqual(result["plan"]["revision"], revision)
            commands = [call.args for call in transport.call_args_list]
            self.assertEqual(commands, [("GET", "/api/tags"), ("POST", "/api/generate")])
            request = transport.call_args.kwargs["payload"]
            self.assertIn(document.strip(), request["prompt"])
            self.assertLessEqual(len(request["prompt"].encode()),
                                 request["options"]["num_ctx"] - request["options"]["num_predict"])
            self.assertEqual(result["plan"]["documents"], 8)
            self.assertTrue(all(source["characters_used"] for source in result["sources"]))
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

    def test_busy_provider_reports_specific_action_without_sending_generation_request(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "drafts"
            provider = OllamaProvider()
            app = LocalDrafts(root, provider=provider)
            with OneModelLock(root), patch.object(provider, "_request", return_value={
                "models": [{"name": "qwen3:4b-instruct"}],
            }) as request:
                app.start({"message": "Draft a readiness flag."})
                result = self.await_result(app)
            self.assertEqual(result["state"], "error")
            self.assertEqual(result["error"]["code"], "MODEL_BUSY")
            self.assertIn("끝나면", result["error"]["hint"])
            request.assert_called_once_with("GET", "/api/tags")

    def test_reply_after_timeout_reuses_pinned_inputs_and_receives_its_own_budget(self):
        revision = "2" * 40
        path = "src/server.py"
        source = "LABEL = 'old'\n" + "# Keep the surrounding configuration.\n" * 100
        doc = DraftDocument("Keep the module's public interface.", "https://github.com/example/project/spec.md", revision)
        original = DraftDocument(source, "https://github.com/example/project/server.py", revision)
        repo = "Repository: example/project\nBranch: stable\n"
        initial = repo + f"작업 파일: {path}\n" + "작업에 참고할 기존 설명입니다.\n" * 140
        reply = "Change LABEL to 'new' and preserve the surrounding configuration."
        result_body = {"done": True, "response": json.dumps({
            "summary": "updated label",
            "edits": [{"path": path, "before": "LABEL = 'old'\n", "after": "LABEL = 'new'\n"}],
        })}
        tags = {"models": [{"name": "qwen3:4b-instruct"}]}
        provider = OllamaProvider()
        with TemporaryDirectory() as directory:
            draft_root = Path(directory).resolve() / "drafts"
            app = LocalDrafts(draft_root, provider=provider)
            with patch("my_local_ai.ax_runtime.manual_draft.read_handoff_documents",
                       return_value=(revision, [doc])) as read_docs, patch(
                           "my_local_ai.ax_runtime.manual_draft.read_github_file",
                           return_value=original) as read_source, patch.object(
                               provider, "_request", side_effect=[
                                   tags, ProviderHold("OLLAMA_UNAVAILABLE", detail="TIMEOUT"),
                                   tags, result_body,
                               ]) as transport:
                app.start({"message": initial})
                failure = self.await_result(app)
                self.assertEqual(failure["error"]["code"], "TIMEOUT")
                self.assertTrue(failure["can_reply"])
                self.assertGreater(failure["forecast"]["upper_ms"], failure["forecast"]["lower_ms"])
                with self.assertRaises(DraftError):
                    app.start({"reply": reply, "attempt": "stale"})
                app.start({"reply": reply, "attempt": failure["attempt"]})
                result = self.await_result(app)
            self.assertEqual(result["state"], "done", result["message"])
            self.assertEqual(result["replies"], [reply])
            self.assertEqual(result["plan"]["revision"], revision)
            self.assertEqual(result["files"][0]["content"], source.replace("'old'", "'new'"))
            self.assertFalse(result["can_reply"])
            read_docs.assert_called_once()
            read_source.assert_called_once_with("example/project", revision, path, allow_missing=True)
            first, second = (transport.call_args_list[index].kwargs["payload"] for index in (1, 3))
            self.assertIn(reply, second["prompt"])
            self.assertLess(second["options"]["num_predict"], first["options"]["num_predict"])
            self.assertLessEqual(len(second["prompt"].encode()),
                                 second["options"]["num_ctx"] - second["options"]["num_predict"])

    def test_forecast_reads_only_recent_success_timings_for_the_matching_kind(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            recorded_time(root, 3500)
            self.assertEqual(estimated_duration(root, "focused")["runs"], 0)
            recorded_time(root, 60000, sample=("focused", 55000))
            recorded_time(root, 250000)
            recorded_time(root, 77000, sample=("focused", 70000))
            recorded_time(root, 195000, sample=("long", 180000))
            self.assertEqual(recorded_time(root), 585500)
            self.assertEqual(estimated_duration(root, "focused"),
                             {"lower_ms": 41250, "upper_ms": 97500, "runs": 2})
            self.assertEqual(estimated_duration(root, "long")["runs"], 1)

    def test_work_queue_keeps_verification_pending_and_restores_completed_draft_parts(self):
        message = (
            "## 잔여 작업 우선순위\n"
            "### P2-A. 초안 상태 추가\n작업 파일: src/queued.py\n변경 내용: Set QUEUED to True.\n"
            "### P2-B. 완료 상태 추가\n작업 파일: src/done.py\n변경 내용: Set DONE to True.\n"
            "### P2-C. 관찰 검증\n실제 시간 기반 24시간·48시간 감시\n"
        )

        class Model:
            def __init__(self):
                self.inputs = []

            def generate(self, prompt, **kwargs):
                self.inputs.append(prompt)
                path, content = (("src/queued.py", "QUEUED = True\n") if "Set QUEUED" in prompt
                                 else ("src/done.py", "DONE = True\n"))
                return UntrustedGeneration(json.dumps({
                    "summary": "state added", "files": [{"path": path, "content": content}],
                }), "qwen3:4b-instruct")

        with TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "drafts"
            model = Model()
            app = LocalDrafts(root, provider=model)
            app.start({"message": message})
            status = self.await_result(app)
            worklist = status["work_queue"]
            self.assertEqual(status["state"], "done", status["message"])
            self.assertEqual([item["state"] for item in worklist["items"]], ["draft", "draft", "pending"])
            self.assertEqual(worklist["items"][2]["observation_hours"], (24, 48))
            self.assertEqual(len(model.inputs), 2)
            self.assertIn("Set QUEUED", model.inputs[0])
            self.assertIn("Set DONE", model.inputs[1])
            self.assertGreaterEqual(worklist["elapsed_ms"], sum(item["elapsed_ms"] for item in worklist["items"]))
            restored = LocalDrafts(root, provider=model).snapshot()
            self.assertEqual(restored["state"], "ready")
            self.assertEqual(restored["work_queue"]["items"], worklist["items"])
            self.assertEqual(restored["work_queue"]["elapsed_ms"], worklist["elapsed_ms"])
            self.assertEqual(len(model.inputs), 2)

    def test_continuous_pause_checkpoint_and_resume_after_relaunch(self):
        from threading import Event

        message = (
            "## 작업 목록\n"
            "### P2-A. First draft\n작업 파일: src/first.py\n변경 내용: Set FIRST to True.\n"
            "### P2-B. Second draft\n작업 파일: src/second.py\n변경 내용: Set SECOND to True.\n"
        )
        entered, release = Event(), Event()

        class Model:
            def __init__(self):
                self.calls = []

            def generate(self, prompt, **options):
                self.calls.append(prompt)
                if len(self.calls) == 1:
                    entered.set()
                    if not release.wait(2):
                        raise RuntimeError("test fixture timed out")
                name, output = (("first", "FIRST = True") if "Set FIRST" in prompt
                                else ("second", "SECOND = True"))
                return UntrustedGeneration(json.dumps({
                    "summary": "draft ready",
                    "files": [{"path": "src/" + name + ".py", "content": output + "\n"}],
                }), "qwen3:4b-instruct")

        with TemporaryDirectory() as folder:
            root = Path(folder) / "drafts"
            provider = Model()
            app = LocalDrafts(root, provider=provider)
            app.start({"message": message})
            self.assertTrue(entered.wait(2), "first stage did not start")
            key = app.snapshot()["work_queue"]["id"]
            paused = app.start({"queue": key, "continuous": "pause"})
            self.assertEqual(paused["work_queue"]["continuous"]["stage"], "PAUSE_REQUESTED")
            release.set()
            stopped = self.await_result(app)
            self.assertEqual(len(provider.calls), 1)
            self.assertEqual(stopped["work_queue"]["continuous"]["stage"], "PAUSED")
            self.assertEqual(stopped["work_queue"]["items"][1]["state"], "pending")
            reopened = LocalDrafts(root, provider=provider)
            self.assertTrue(reopened.snapshot()["work_queue"]["continuous"]["paused"])
            self.assertEqual(len(provider.calls), 1)
            reopened.start({"queue": key, "continuous": "resume"})
            finished = self.await_result(reopened)
            self.assertEqual(len(provider.calls), 2)
            self.assertEqual([row["state"] for row in finished["work_queue"]["items"]],
                             ["draft", "draft"])
            self.assertEqual(finished["work_queue"]["verified_count"], 0)
            self.assertEqual(finished["work_queue"]["continuous"]["stage"],
                             "AWAITING_REVIEW_OR_APPROVAL")
            with self.assertRaises(DraftError):
                reopened.start({"queue": "0" * 24, "continuous": "pause"})

    def test_verification_brief_does_not_manufacture_a_change(self):
        message = "## 작업 목록\n### P2-A. 통합 검사\n기존 테스트 결과 확인\n### P2-B. 실행 검증\nCI 확인\n"
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "drafts"
            provider = FixtureProvider("arbitrary.py", "PASS = True\n")
            app = LocalDrafts(root, provider=provider)
            app.start({"message": message})
            result = self.await_result(app)
            self.assertEqual(result["state"], "ready", result["message"])
            self.assertEqual(provider.prompt, "")
            self.assertEqual([item["state"] for item in result["work_queue"]["items"]], ["pending", "pending"])
            with self.assertRaises(DraftError):
                app.start({"queue": result["work_queue"]["id"], "item": "1", "paths": "src/cli.py", "change": "ㄱ"})
            repeat = app.start({"message": message})
            self.assertIn("같은 지시문을 받았습니다", repeat["submission_notice"])
            self.assertEqual(repeat["work_queue"]["id"], result["work_queue"]["id"])
            self.assertFalse(any(path.is_dir() for path in root.iterdir()))

    def test_repository_inspections_advance_without_model_or_manual_input(self):
        revision = "a" * 40
        source = {
            "src/demo/cli.py": "raise SystemExit(17)\n",
            "tests/test_cli.py": "def test_command_line():\n    assert False\n",
            "tests/test_watch.py": "def test_watch():\n    assert False\n",
            ".github/workflows/audit.yml": "name: Audit\non:\n  workflow_dispatch:\n",
        }
        ci = {"repo": "example/project", "revision": revision, "runs": [
            {"id": 19, "name": "Audit", "event": "push", "status": "completed", "conclusion": "success"},
        ]}
        message = (
            "Repository: example/project\nBranch: stable\n## 작업 목록\n"
            "### P2-A. CLI 통합 검증\n실제 동작 확인.\n"
            "### P2-B. 감시·복구\n실제 시간 기반 24시간·48시간 관찰.\n"
            "### P2-C. GitHub Actions 실행\n수동 워크플로 확인.\n"
        )
        with TemporaryDirectory() as directory, patch(
            "my_local_ai.ax_runtime.manual_draft.read_handoff_documents", return_value=(revision, [])
        ), patch(
            "my_local_ai.ax_runtime.manual_draft.read_github_ci", return_value=ci
        ), patch(
            "my_local_ai.ax_runtime.draft_evidence.read_github_ci", return_value=ci
        ), patch(
            "my_local_ai.ax_runtime.draft_evidence.github_files",
            return_value={path: len(text) for path, text in source.items()},
        ) as inventory, patch("my_local_ai.ax_runtime.draft_evidence.read_github_file") as read:
            rechecking = False

            def read_file(repo, ref, path):
                if (path == "tests/test_watch.py" and not rechecking) or (rechecking and "cli" in path):
                    raise DraftError("fixture read error")
                return DraftDocument(source[path], f"https://github.com/{repo}/blob/{ref}/{path}", ref)

            read.side_effect = read_file
            root = Path(directory).resolve() / "drafts"
            provider = FixtureProvider("arbitrary.py", "READY = True\n")
            app = LocalDrafts(root, provider=provider)
            app.start({"message": message})
            result = self.await_result(app)
            self.assertEqual(result["state"], "ready", result["message"])
            rows = result["work_queue"]["items"]
            self.assertEqual([row["state"] for row in rows], ["inspected"] * 3)
            self.assertEqual([row["inspection"]["state"] for row in rows], ["observed", "limited", "observed"])
            cli, watch, actions = (row["inspection"] for row in rows)
            self.assertTrue(any("테스트 정의 1개" in file["result"] for file in cli["files"]))
            self.assertIn("24~48시간 실측", watch["remaining"])
            self.assertIn("이 기준 커밋에서 확인한 수동 실행 기록 0건", actions["notes"])
            self.assertTrue(any("수동 실행 선언 발견" in file["result"] for file in actions["files"]))
            inventory.assert_called_once_with("example/project", revision)
            self.assertTrue(all(call.args[1] == revision for call in read.call_args_list))
            reopened = LocalDrafts(root, provider=provider)
            restored = reopened.snapshot()
            self.assertEqual(restored["work_queue"]["items"], rows)
            self.assertEqual(restored["work_queue"]["blocked"], "1")
            self.assertEqual(restored["work_queue"]["active"], "")
            self.assertEqual(rows[0]["hold"]["kind"], "verification")

            submitted = reopened.start({"message": message})
            self.assertEqual(submitted["state"], "ready")
            self.assertEqual(submitted["work_queue"]["blocked"], "1")
            inventory.assert_called_once()

            rechecking = True
            submitted = reopened.start({"queue": restored["work_queue"]["id"], "refresh": "evidence"})
            self.assertEqual(submitted["work_queue"]["id"], result["work_queue"]["id"])
            self.assertEqual(submitted["state"], "working")
            self.assertIn("다시 확인 중", submitted["message"])
            self.assertEqual(submitted["work_queue"]["items"][0]["inspection"], cli)
            repeat = self.await_result(reopened)
            past, now, _ = [item["inspection"] for item in repeat["work_queue"]["items"]]
            self.assertEqual(repeat["state"], "ready", repeat["message"])
            self.assertIn("3개 파트", repeat["message"])
            self.assertEqual(past["files"], cli["files"])
            self.assertIn("이전 읽기 결과", past["recheck_note"])
            self.assertEqual(now["state"], "observed")
            self.assertEqual(inventory.call_count, 2)
            self.assertEqual(provider.prompt, "")
            self.assertFalse(any(path.is_dir() for path in root.iterdir()))

    def test_draft_recovery_holds_one_part_and_advances_independent_work(self):
        message = (
            "## 작업 목록\n"
            "### P2-A. Slow draft\n작업 파일: src/slow.py\n변경 내용: Add SLOW.\n"
            "### P2-B. Dependent draft\n선행 작업: P2-A\n작업 파일: src/next.py\n변경 내용: Add NEXT.\n"
            "### P2-C. Independent draft\n작업 파일: src/fast.py\n변경 내용: Add FAST.\n"
        )
        calls = []
        advice_calls = []

        class Model:
            def generate(self, prompt, **options):
                calls.append(prompt)
                if "Add SLOW." in prompt:
                    raise ProviderHold("OLLAMA_UNAVAILABLE", detail="TIMEOUT")
                if sum("Add FAST." in received for received in calls) == 1:
                    return UntrustedGeneration("bad JSON", "qwen3:4b-instruct")
                return FixtureProvider("src/fast.py", "FAST = True\n").generate(prompt, **options)

        class Advisor:
            configured = True

            def advise(self, code, attempt):
                advice_calls.append((code, attempt))
                return "compact"

        with TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "drafts"
            app = LocalDrafts(root, provider=Model(), advisor=Advisor())
            app.start({"message": message})
            result = self.await_result(app)
            worklist = result["work_queue"]
            self.assertEqual(len(calls), 5)
            self.assertIn("smallest exact edit", calls[1])
            self.assertIn("smallest exact edit", calls[4])
            self.assertFalse(any("Add NEXT." in prompt for prompt in calls))
            self.assertEqual(advice_calls, [("TIMEOUT", 1), ("TIMEOUT", 2), ("DRAFT_FORMAT", 1)])
            first, dependent, independent = worklist["items"]
            self.assertEqual(first["recovery"]["failed_attempts"], 3)
            self.assertEqual(first["hold"]["kind"], "failed")
            self.assertEqual(dependent["hold"]["kind"], "dependency")
            self.assertEqual(independent["state"], "draft")
            self.assertEqual(worklist["blocked"], first["id"])
            self.assertEqual(worklist["active"], "")
            self.assertFalse(worklist["can_resume"])
            reopened = LocalDrafts(root, provider=Model(), advisor=Advisor())
            self.assertEqual(reopened.start({"message": message})["work_queue"]["items"], worklist["items"])
            self.assertEqual(len(calls), 5)
            with self.assertRaisesRegex(DraftError, "선행 검증"):
                reopened.start({"queue": worklist["id"], "item": dependent["id"],
                                "paths": "src/next.py", "change": "Add NEXT."})

    def test_gemini_advisor_sends_failure_codes_and_accepts_only_valid_choices(self):
        with patch.dict(os.environ, {"MLA_GEMINI_API_KEY": "fixture-" + "a" * 27}), patch(
            "my_local_ai.ax_runtime.draft_recovery.HTTPSConnection"
        ) as connection:
            advisor = GeminiDraftAdvisor()
            response = connection.return_value.getresponse.return_value
            response.status = 200

            def answer(action):
                response.read.return_value = json.dumps({"candidates": [{"finishReason": "STOP", "content": {
                    "parts": [{"text": json.dumps({"action": action})}],
                }}]}).encode()

            self.assertIsNone(advisor.advise("F18_HOLD", 1))
            connection.assert_not_called()
            answer("compact")
            self.assertEqual(advisor.advise("TIMEOUT", 1), "compact")
            connection.assert_called_with("generativelanguage.googleapis.com", timeout=10)
            args, kwargs = connection.return_value.request.call_args
            self.assertEqual(args, ("POST", "/v1beta/models/gemini-3.5-flash-lite:generateContent"))
            self.assertIn(b"Failure code: TIMEOUT. Failed attempt: 1.", kwargs["body"])
            self.assertNotIn(b"fixture-", kwargs["body"])
            answer("run_command")
            self.assertIsNone(advisor.advise("TIMEOUT", 2))
            response.status = 429
            self.assertIsNone(advisor.advise("TIMEOUT", 2))
            prior_calls = connection.call_count
            self.assertIsNone(advisor.advise("TIMEOUT", 1))
            self.assertEqual(connection.call_count, prior_calls)


if __name__ == "__main__":
    unittest.main()
