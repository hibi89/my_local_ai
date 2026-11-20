"""Bounded SHA-pinned source reuse for local, single-process drafting.

GitHub's existing reader validates blob SHA, content length and UTF-8 before
returning a DraftDocument. Never write cached contents to disk or use a mutable
branch ref as a cache key. Local workspace originals are never cached.
"""
from __future__ import annotations

from collections import OrderedDict
import re
from typing import Callable

from .draft_documents import DraftDocument, DraftError

_SHA = re.compile(r"[0-9a-f]{40}\Z")


class PinnedSourceCache:
    def __init__(self, *, max_entries: int = 8, max_bytes: int = 524288):
        if (type(max_entries) is not int or not 1 <= max_entries <= 64
            or type(max_bytes) is not int or not 1024 <= max_bytes <= 4_194_304):
            raise ValueError("invalid cache bounds")
        self.max_entries, self.max_bytes = max_entries, max_bytes
        self._items: OrderedDict[tuple[str, str, str], tuple[DraftDocument, int]] = OrderedDict()
        self._size = 0
        self.hits = 0
        self.misses = 0

    @property
    def entries(self) -> int:
        return len(self._items)

    @property
    def bytes_used(self) -> int:
        return self._size

    def clear(self) -> None:
        self._items.clear()
        self._size = 0

    def read(self, repository: str, revision: str, path: str, *,
             allow_missing: bool,
             fetch: Callable[..., DraftDocument | None]) -> DraftDocument | None:
        if not isinstance(revision, str) or not _SHA.fullmatch(revision):
            raise DraftError("파일 재사용에는 정확한 원본 GitHub 커밋 SHA가 필요합니다.")
        key = (repository, revision, path)
        if key in self._items:
            doc, length = self._items.pop(key)
            self._items[key] = (doc, length)
            self.hits += 1
            return doc
        self.misses += 1
        doc = fetch(repository, revision, path, allow_missing=allow_missing)
        # Do not remember 404, permissions errors, malformed blobs or network failures.
        if doc is None:
            return None
        if not isinstance(doc, DraftDocument) or doc.revision != revision:
            raise DraftError("파일 근거의 SHA가 작업표와 일치하지 않습니다.")
        size = len(doc.text.encode("utf-8"))
        if size > self.max_bytes:
            return doc
        while self._items and (len(self._items) >= self.max_entries
                               or self._size + size > self.max_bytes):
            _, (_, removed) = self._items.popitem(last=False)
            self._size -= removed
        self._items[key] = (doc, size)
        self._size += size
        return doc
