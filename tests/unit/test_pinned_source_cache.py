"""Safe, read-only SHA-pinned source caching. Network and GPU are mocked."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from my_local_ai.ax_runtime.draft_documents import DraftDocument, DraftError
from my_local_ai.ax_runtime.draft_intake import parse_handoff
from my_local_ai.ax_runtime.manual_draft import LocalDrafts
from my_local_ai.ax_runtime.pinned_source_cache import PinnedSourceCache

A, B = "a" * 40, "b" * 40


class CacheTests(unittest.TestCase):
    def test_same_exact_sha_hits_and_different_sha_refetches(self):
        cache = PinnedSourceCache(max_entries=2, max_bytes=1280)
        calls = []
        def fetch(repo, sha, path, *, allow_missing=False):
            calls.append((repo, sha, path))
            return DraftDocument("line=1\n", "fixture", sha)
        for sha in (A, A, B):
            result = cache.read("test/repo", sha, "src/thing.py",
                                allow_missing=True, fetch=fetch)
            self.assertEqual(result.revision, sha)
        self.assertEqual(len(calls), 2)
        self.assertEqual((cache.hits, cache.misses), (1, 2))
        self.assertEqual(cache.entries, 2)
        cache.clear()
        self.assertEqual(cache.entries, 0)

    def test_not_found_oversized_and_invalid_sha_are_never_cached(self):
        cache = PinnedSourceCache(max_entries=2, max_bytes=1024)
        calls = []
        def missing(repo, sha, path, *, allow_missing=False):
            calls.append(path)
            return None
        for _ in range(2):
            self.assertIsNone(cache.read("test/repo", A, "src/missing.py",
                                         allow_missing=True, fetch=missing))
        self.assertEqual(len(calls), 2)
        self.assertEqual(cache.entries, 0)
        def large(repo, sha, path, *, allow_missing=False):
            return DraftDocument("x" * 1200, "fixture", sha)
        for _ in range(2):
            cache.read("test/repo", A, "src/large.py", allow_missing=True, fetch=large)
        self.assertEqual(cache.entries, 0)
        with self.assertRaises(DraftError):
            cache.read("test/repo", A, "src/bad.py", allow_missing=False,
                       fetch=lambda *a, **k: DraftDocument("x", "fixture", B))
        with self.assertRaises(DraftError):
            cache.read("test/repo", "main", "src/bad.py", allow_missing=False, fetch=large)

    def test_lru_keeps_memory_and_entry_bounds(self):
        cache = PinnedSourceCache(max_entries=2, max_bytes=1024)
        def fetch(repo, sha, path, *, allow_missing=False):
            return DraftDocument("p" * 430, "fixture", sha)
        for path in ("a.py", "b.py", "c.py"):
            cache.read("test/repo", A, path, allow_missing=False, fetch=fetch)
        self.assertEqual(cache.entries, 2)
        self.assertLessEqual(cache.bytes_used, 1024)

    def test_workbench_reuses_only_immutable_pinned_github_sources(self):
        scope = parse_handoff("Repository: test/repo\nBranch: main\n")
        with TemporaryDirectory() as folder:
            app = LocalDrafts(Path(folder) / "drafts")
            original = DraftDocument("GOOD = True\n", "fixture", A)
            with patch("my_local_ai.ax_runtime.manual_draft.read_github_file",
                       return_value=original) as fetch:
                for _ in range(2):
                    sources, docs = app._read_sources(scope, A, ("src/thing.py",),
                                                      allow_missing=True)
                    self.assertEqual(sources["src/thing.py"], "GOOD = True\n")
                self.assertEqual(fetch.call_count, 1)
                self.assertEqual(app._source_cache.hits, 1)
            changed = DraftDocument("NEW = True\n", "fixture", B)
            with patch("my_local_ai.ax_runtime.manual_draft.read_github_file",
                       return_value=changed) as fetch:
                app._read_sources(scope, B, ("src/thing.py",), allow_missing=True)
                fetch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
