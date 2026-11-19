"""Owner-invoked local source drafting. Model replies are handled as text."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field, replace
from datetime import datetime
from difflib import unified_diff
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import tempfile
from threading import Lock, Thread
from time import monotonic

from ..state.local_files import local_path_stat, read_bounded_regular
from .budgets import BudgetGuard, ModelBudget
from .draft_documents import (
    DOCUMENT_LIMIT, DraftDocument, DraftError, github_files, read_document, read_github_ci, read_github_file,
)
from .draft_intake import Handoff, HandoffTask, handoff_tasks, parse_handoff, read_handoff_documents, text_path
from .draft_timing import estimated_duration, load_work_queue, recorded_time, save_work_queue
from .ollama_provider import OllamaProvider, STRUCTURED_OUTPUT_TOKENS
from .provider_policy import ProviderHold
from .worker_lock import ModelLockUnsafe, OneModelLock


REQUEST_LIMIT = 1_800_000  # Space for JSON escaping of two UTF-8 documents.
_CONTEXT = 8192
_SHORT_CONTEXT = 4096
_INPUT_LIMIT = _CONTEXT - STRUCTURED_OUTPUT_TOKENS
_FOCUSED_OUTPUT_TOKENS = 448
_FOCUSED_INPUT_LIMIT = _SHORT_CONTEXT - _FOCUSED_OUTPUT_TOKENS
_REPLY_LIMIT = 1400
_OUTPUT_LIMIT = 60_000
_KEYWORDS = re.compile(r"[A-Za-z0-9_\uac00-\ud7a3]{2,}")
_MODEL_ERRORS = {
    "PROMPT_TOO_LARGE": (
        "Qwen에 한 번에 보낼 수 있는 입력 크기를 넘었습니다.",
        "지시문에서 지금 처리할 작업 하나를 남기고, 작업 파일을 한 개 지정해 다시 보내세요.",
    ),
    "MODEL_BUSY": (
        "다른 MLA 작업이 이 Qwen 모델을 사용 중입니다.",
        "실행 중인 MLA 작업이 끝나면 같은 지시문을 다시 보내세요.",
    ),
    "MODEL_LOCK": (
        "초안 저장 폴더의 Qwen 잠금 파일을 열지 못했습니다.",
        "MLA 실행기를 다시 열어 재시도하세요. 같은 문제가 반복되면 아래 오류 코드를 보내 주세요.",
    ),
    "MODEL_ABSENT": (
        "Ollama에 qwen3:4b-instruct 모델이 없습니다.",
        "PowerShell에서 ollama pull qwen3:4b-instruct를 실행한 뒤 다시 보내세요.",
    ),
    "OLLAMA_UNAVAILABLE": (
        "MLA가 이 PC의 Ollama에 연결하지 못했습니다.",
        "Windows에서 Ollama가 실행 중인지 확인하고, 꺼져 있으면 Ollama를 연 뒤 다시 보내세요.",
    ),
    "TIMEOUT": (
        "Ollama가 정해진 시간 안에 Qwen 응답을 반환하지 못했습니다.",
        "이 파일에서 먼저 바꿀 부분 한 가지를 적어 다시 시도해 보세요.",
    ),
    "OUTPUT_TOO_LARGE": (
        "Qwen이 한 작업에서 저장할 수 있는 분량보다 큰 응답을 보냈습니다.",
        "지시문에서 파일이나 변경 항목을 한 개로 좁혀 다시 보내세요.",
    ),
    "RESOURCE_LIMIT": (
        "Qwen 작업이 자원 한도에 도달했습니다.",
        "작업 내용을 한 파일의 작은 변경으로 좁혀 다시 보내세요.",
    ),
}


@dataclass(frozen=True)
class _DraftRequest:
    instruction: str
    design: str
    paths: tuple[str, ...]
    workspace: str
    handoff: bool
    replies: tuple[str, ...] = ()
    item: HandoffTask | None = None


@dataclass(frozen=True)
class _HandoffContext:
    task: DraftDocument
    documents: list[DraftDocument]
    originals: dict[str, str]
    source_docs: dict[str, DraftDocument]
    plan: dict
    scope: Handoff


@dataclass
class _WorkQueue:
    key: str
    items: tuple[HandoffTask, ...]
    baseline: _HandoffContext | None = None
    drafts: dict[str, dict] = field(default_factory=dict)
    interrupted: set[str] = field(default_factory=set)
    elapsed_ms: int = 0
    item_elapsed_ms: dict[str, int] = field(default_factory=dict)
    attempted: set[str] = field(default_factory=set)
    scheduled: dict[str, tuple[tuple[str, ...], str]] = field(default_factory=dict)
    forecast: dict | None = None


def _draft_paths(spec: str) -> tuple[str, ...]:
    if len(spec) > 3000:
        raise DraftError("작업 파일 목록을 나누어 넣으세요.")
    paths = tuple(text_path(line.strip()) for line in spec.splitlines() if line.strip())
    if len(paths) > 8 or len({path.casefold() for path in paths}) != len(paths):
        raise DraftError("서로 다른 작업 파일을 한 번에 1~8개 넣으세요.")
    return paths


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _local_absolute(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or str(path).startswith(("\\\\", "//")) or ".." in path.parts:
        raise DraftError("이 PC의 폴더 전체 경로를 넣으세요.")
    return path


def _existing_sources(folder: str, paths: tuple[str, ...], draft_root: Path) -> dict[str, str]:
    if not folder:
        return dict.fromkeys(paths, "")
    root = _local_absolute(folder)
    if root == draft_root or draft_root in root.parents:
        raise DraftError("기존 작업 폴더에는 원본 프로젝트 또는 별도 검토용 복사본을 선택하세요.")
    try:
        if not stat.S_ISDIR(local_path_stat(root).st_mode):
            raise DraftError("기존 작업 폴더를 찾을 수 없습니다.")
    except (OSError, ValueError) as exc:
        raise DraftError("기존 작업 폴더를 읽을 수 없습니다.") from exc
    current = {}
    for key in paths:
        file = root / key
        if file == draft_root or draft_root in file.parents:
            raise DraftError("저장 폴더 밖의 기존 프로젝트 파일을 넣으세요.")
        try:
            current[key] = read_bounded_regular(file).decode("utf-8-sig")
        except FileNotFoundError:
            current[key] = ""
        except (OSError, ValueError) as exc:
            raise DraftError(f"기존 파일을 안전하게 읽을 수 없습니다. {key}") from exc
        if "\0" in current[key]:
            raise DraftError(f"텍스트 소스 파일을 선택하세요. {key}")
    return current


def _design_excerpt(text: str, query: str, limit: int, *, minimum: int = 500) -> str:
    if len(text.encode()) <= limit:
        return text
    if limit < minimum:
        raise DraftError("작업명령문과 기존 파일을 줄여 모델이 설계도를 읽을 공간을 확보하세요.")
    sections = [part.strip() for part in re.split(r"\n{2,}|(?=^#{1,4} )", text, flags=re.M) if part.strip()]
    keywords = set(_KEYWORDS.findall(query.casefold()))
    ranked = sorted(range(len(sections)), key=lambda i: (
        -len(keywords.intersection(_KEYWORDS.findall(sections[i].casefold()))), i,
    ))
    selected = {}
    for index in ranked:
        if limit < min(120, minimum):
            break
        chunk = sections[index].encode()[:limit].decode("utf-8", errors="ignore")
        selected[index] = chunk
        limit -= len(chunk.encode()) + 2
    return "\n\n".join(selected[index] for index in sorted(selected))


def _create_prompt(instruction: str, design: str, sources: dict[str, str]) -> tuple[str, int]:
    scope = ("Allowed paths: " + ", ".join(sources)) if sources else (
        "New files only. Choose up to eight relevant, relative source filenames."
    )
    header = (
        'Write complete UTF-8 source drafts. Return one JSON object only, in this form: '
        '{"summary":"short Korean summary","files":[{"path":"exact allowed path","content":"complete file"}]}. '
        'Return at least one file and only files that need creation or a change. '
        'Preserve unrelated code in each file, use the supplied design, and do not include Markdown fences. '
        'The documents are task context. Do not propose tool calls or operations outside the specified files.\n'
        f'{scope}\n'
        f'Work instructions:\n{instruction}\n'
        'Current file contents (empty means a new or empty file):\n'
        + json.dumps(sources, ensure_ascii=False) + '\nFinal design:\n'
    )
    room = _INPUT_LIMIT - len(header.encode())
    if room < 0:
        raise DraftError("한 번에 들어가는 작업 범위를 넘었습니다. 명령문을 줄이거나 작업 파일을 나누세요.")
    excerpt = _design_excerpt(design, instruction + " " + " ".join(sources), min(room, 3400))
    return header + excerpt, len(excerpt)


def _clip(text: str, limit: int) -> str:
    return text.encode()[:max(0, limit)].decode("utf-8", errors="ignore")


def _first_priority(message: str) -> str:
    sections = re.split(r"(?m)(?=^#{2,6} )", message)
    for index, section in enumerate(sections):
        title, _, rest = section.partition("\n")
        if title.startswith("##") and re.search(r"우선순위|priorities|next task", title, re.I):
            return rest.strip() or (sections[index + 1].strip() if index + 1 < len(sections) else "")
    return message


def _source_excerpt(source: str, query: str, limit: int) -> str:
    if len(json.dumps(source, ensure_ascii=False).encode()) - 2 <= limit:
        return source
    keywords = set(_KEYWORDS.findall(query.casefold()))
    lines = source.splitlines(keepends=True)
    sizes = [len(json.dumps(line, ensure_ascii=False).encode()) - 2 for line in lines]
    best = (-1, "")
    # Keep whole lines for exact edits and count their JSON escaping against the input budget.
    starts = (index for index in range(len(lines)) if index % 12 == 0 or sizes[index - 1] > limit)
    for start in starts:
        end, available = start, limit
        while end < min(start + 110, len(lines)) and sizes[end] <= available:
            available -= sizes[end]
            end += 1
        excerpt = "".join(lines[start:end])
        score = len(keywords.intersection(_KEYWORDS.findall(excerpt.casefold())))
        if excerpt and score > best[0]:
            best = (score, excerpt)
    if not best[1]:
        raise DraftError("작업 파일에 모델이 인용할 수 있는 코드 구간을 찾지 못했습니다.")
    return best[1]


def _handoff_prompt(task: DraftDocument, documents: list[DraftDocument], originals: dict[str, str],
                    source_docs: dict[str, DraftDocument], narrowed: bool, *,
                    replies: tuple[str, ...] = ()) -> tuple[str, dict | None, list]:
    focused = narrowed or bool(replies)
    input_limit = _FOCUSED_INPUT_LIMIT if focused else _INPUT_LIMIT
    priority = _first_priority(task.text)
    if len(task.text.encode()) > (1150 if focused else 2350):
        begin = _clip(task.text, 370 if focused else 540)
        focus_limit = 640 if focused else 1280
        focus = (_clip(priority, focus_limit) if priority != task.text
                 else _design_excerpt(task.text, " ".join(originals), focus_limit))
        instructions = f"{begin}\n\n{focus}"
        used = len(begin) + len(focus) if priority != task.text else len(focus)
    else:
        instructions, used = task.text, len(task.text)
    query = instructions + " " + " ".join(originals)
    if replies:
        latest = replies[-1]
        query = latest + " " + " ".join(originals)
        # Give the latest reply its own place in the prompt so clipping the original brief cannot drop it.
        context = _clip(instructions, 510)
        prior = _clip("\n".join(replies[:-1]), 180)
        used = len(context)
        if latest in ("ㄱ", "ㄱㄱ"):
            latest = "Continue with one small next change in the same scope."
        instructions = (
            f"Latest user instruction (perform this now within the allowed files):\n{latest}\n"
            f"Earlier user replies:\n{prior}\n"
            f"Original task context:\n{context}"
        )
    evidence = [task.evidence(min(used, len(task.text)))]
    if replies:
        evidence.append(DraftDocument(replies[-1], "추가 지시").evidence(len(replies[-1])))
    encoded = json.dumps(originals, ensure_ascii=False)
    fragments = None
    selection = ("Make the specified change only when supported by the shown code. "
                 "If there is no pertinent change to make, return a short Korean reason and an empty array. "
                 "Keep the reply short. Do not claim to have run checks.\n") if focused else ""
    preamble = selection + "Use the attached document excerpts as context for the change."
    if len(encoded.encode()) > 1900 or (focused and any(originals.values())):
        prompt = (
            'Return one JSON object: {"summary":"short Korean summary","edits":[{"path":"exact path",'
            '"before":"unique exact block from the excerpt, including indentation and line breaks",'
            '"after":"replacement text"}]}. Use whole lines and preserve surrounding code. '
            'For an empty file only, use an empty before and include the whole new file as after. '
            'Use only the listed paths. Do not return Markdown or commands.\n'
            + preamble + '\nWork instructions:\n' + instructions
            + '\nCurrent source excerpts:\n'
        )
        # Leave room for the referenced documents before selecting source excerpts.
        document_room = min(720, 90 * len(documents)) if focused else min(1560, 195 * len(documents))
        source_room = min(1900 if focused else 3000, input_limit - len(prompt.encode()) - document_room)
        paths_size = len(json.dumps(dict.fromkeys(originals, ""), ensure_ascii=False).encode())
        per_file = (source_room - paths_size) // len(originals)
        if per_file < 1:
            raise DraftError("작업 파일 경로가 Qwen 입력 범위를 넘었습니다. 작업 파일을 나누어 주세요.")
        fragments = {path: _source_excerpt(source.replace("\r\n", "\n"), query, per_file)
                     for path, source in originals.items()}
        prompt += json.dumps(fragments, ensure_ascii=False)
    else:
        prompt, _ = _create_prompt(instructions + "\n\n" + preamble, "", originals)
    room = input_limit - len(prompt.encode())
    if room < 0:
        raise DraftError("붙여넣은 작업과 파일을 한 번에 읽기 어렵습니다. 작업 파일을 나누어 주세요.")
    if documents:
        per_document = min(2300, room // len(documents))
        for document in documents:
            name = document.origin.split("/")[-1]
            limit = per_document - len(name.encode()) - 16
            excerpt = (_design_excerpt(document.text, query, limit, minimum=80) if limit >= 80
                       else _clip(document.text, limit))
            if excerpt:
                prompt += f"\n\n[{name}]\n{excerpt}"
            evidence.append(document.evidence(len(excerpt)))
    for path, document in source_docs.items():
        evidence.append(document.evidence(len(fragments[path]) if fragments is not None else len(document.text)))
    return prompt, fragments, evidence


def _apply_model_edits(raw: str, originals: dict[str, str], fragments: dict[str, str]) -> str:
    try:
        data = json.loads(raw, object_pairs_hook=_unique_fields)
        if (type(data) is not dict or set(data) != {"summary", "edits"}
            or type(data["edits"]) is not list or len(data["edits"]) > 8):
            raise ValueError
        changes = {}
        for row in data["edits"]:
            if (type(row) is not dict or set(row) != {"path", "before", "after"}
                or any(type(value) is not str for value in row.values())):
                raise ValueError
            path, before, after = row["path"], row["before"], row["after"]
            if path not in originals:
                raise ValueError
            original = originals[path]
            before = before.replace("\r\n", "\n")
            if (not before and original) or (before and before not in fragments[path]):
                raise ValueError
            if "\r\n" in original:
                before = before.replace("\n", "\r\n")
                after = after.replace("\r\n", "\n").replace("\n", "\r\n")
            offset = original.find(before)
            if offset < 0 or (before and offset != original.rfind(before)):
                raise ValueError
            changes.setdefault(path, []).append((offset, offset + len(before), after))
        files = []
        for path, edits in changes.items():
            source = originals[path]
            boundary = len(source) + 1
            for start, end, replacement in sorted(edits, reverse=True):
                if start >= boundary or end > boundary:
                    raise ValueError
                source = source[:start] + replacement + source[end:]
                boundary = start
            files.append({"path": path, "content": source})
        return json.dumps({"summary": data["summary"], "files": files}, ensure_ascii=False)
    except (ValueError, RecursionError):
        raise DraftError("Qwen이 제안한 수정 위치를 원본에서 정확히 확인할 수 없습니다. 수정 대상을 더 좁혀 주세요.") from None


def _model_files(raw: str, originals: dict[str, str]) -> tuple[str, list[dict]]:
    try:
        data = json.loads(raw, object_pairs_hook=_unique_fields)
        if (type(data) is not dict or set(data) != {"summary", "files"}
            or type(data["summary"]) is not str or type(data["files"]) is not list
            or len(data["files"]) > (len(originals) or 8)):
            raise ValueError
        seen = set()
        files = []
        for row in data["files"]:
            if (type(row) is not dict or set(row) != {"path", "content"}
                or type(row["path"]) is not str or type(row["content"]) is not str):
                raise ValueError
            path, source = text_path(row["path"]), row["content"]
            if ((originals and path not in originals) or path.casefold() in seen or "\0" in source
                or len(source.encode()) > _OUTPUT_LIMIT):
                raise ValueError
            seen.add(path.casefold())
            before = originals.get(path, "")
            if before == source:
                continue
            syntax = ""
            if path.lower().endswith(".py"):
                try:
                    ast.parse(source, filename="<draft>")
                    syntax = "Python 문법 확인"
                except (ValueError, RecursionError, SyntaxError):
                    syntax = "Python 문법 확인 필요"
            diff = "\n".join(unified_diff(before.splitlines(), source.splitlines(),
                "원본/" + path, "초안/" + path, lineterm=""))
            files.append({"path": path, "content": source, "diff": diff, "syntax": syntax})
    except (UnicodeError, ValueError, RecursionError):
        raise DraftError("Qwen 응답의 파일 목록을 확인할 수 없습니다. 작업 범위를 줄여 다시 시작하세요.") from None
    if not files:
        if not data["files"] and data["summary"].strip():
            raise DraftError("만들 수 있는 수정이 확인되지 않았습니다. Qwen 설명 · " + data["summary"].strip()[:240])
        raise DraftError("Qwen이 변경된 파일을 내놓지 않았습니다. 원하는 변경을 구체적으로 적어 주세요.")
    return data["summary"].strip()[:1200], files


class LocalDrafts:
    def __init__(self, output: Path, *, provider: OllamaProvider | None = None):
        root = _local_absolute(os.path.abspath(output))
        local_path_stat(root.parent)
        root.mkdir(exist_ok=True)
        if not stat.S_ISDIR(local_path_stat(root).st_mode):
            raise DraftError("초안 저장 폴더를 확인하세요.")
        self.root = root
        self.provider = provider or OllamaProvider(timeout_seconds=260)
        self._lock = Lock()
        self._state = {"state": "idle", "message": "작업을 시작하면 진행 상황이 표시됩니다."}
        self._request: _DraftRequest | None = None
        self._context: _HandoffContext | None = None
        self._queue: _WorkQueue | None = None
        self._started = None
        self._elapsed_ms = self._total_ms = 0
        self._timing_error = False
        self._refresh_total()
        self._restore_queue()

    def _restore_queue(self) -> None:
        saved = load_work_queue(self.root)
        if not saved:
            return
        try:
            text, key, plan = saved["text"], saved["key"], saved["plan"]
            if (saved["version"] != 1 or type(text) is not str or len(text.encode()) > DOCUMENT_LIMIT + 5000
                or type(key) is not str or not re.fullmatch(r"[a-f0-9]{24}", key) or type(plan) is not dict):
                return
            items, scope = handoff_tasks(text), parse_handoff(text)
            if not items or plan["repository"] != scope.repository or plan["workspace"] != scope.workspace:
                return
            if scope.repository and not re.fullmatch(r"[a-f0-9]{40}", plan["revision"]):
                return
            documents = [DraftDocument(**entry) for entry in saved["documents"][:12]]
            if any(type(doc.text) is not str or len(doc.text.encode()) > DOCUMENT_LIMIT
                   or type(doc.origin) is not str or type(doc.revision) is not str for doc in documents):
                return
            baseline = _HandoffContext(DraftDocument(text, "붙여넣은 작업 지시"), documents,
                                       {}, {}, plan, scope)
            queue = _WorkQueue(key, items, baseline)
            queue.drafts = {item.key: saved["drafts"][item.key] for item in items
                            if item.key in saved["drafts"]}
            queue.interrupted = set(saved["interrupted"])
            queue.attempted = set(saved["attempted"])
            if saved.get("active"):
                queue.interrupted.add(saved["active"])
            queue.elapsed_ms = max(0, int(saved["elapsed_ms"]))
            queue.item_elapsed_ms = {item.key: max(0, int(saved["item_elapsed_ms"].get(item.key, 0)))
                                     for item in items}
            queue.scheduled = self._scheduled_items(items, scope)
            queue.forecast = estimated_duration(self.root, "focused") if queue.scheduled else None
        except (ValueError, OverflowError, TypeError, KeyError, AttributeError):
            return
        self._queue = queue
        self._state.update(state="ready", message=f"작업표 {len(items)}개 파트와 진행 기록을 복구했습니다.", plan=plan)

    def _checkpoint_locked(self, *, replace: bool = False) -> None:
        queue = self._queue
        if not queue or not queue.baseline:
            return
        active = self._request.item if self._request and self._state["state"] == "working" else None
        baseline = queue.baseline
        try:
            save_work_queue(self.root, {
                "version": 1, "key": queue.key, "text": baseline.task.text, "plan": baseline.plan,
                "documents": [{"text": doc.text, "origin": doc.origin, "revision": doc.revision}
                              for doc in baseline.documents],
                "drafts": queue.drafts, "attempted": sorted(queue.attempted),
                "interrupted": sorted(queue.interrupted), "active": active.key if active else "",
                "elapsed_ms": queue.elapsed_ms, "item_elapsed_ms": queue.item_elapsed_ms,
            }, replace=replace)
        except (OSError, ValueError, sqlite3.Error):
            self._state["checkpoint_error"] = "작업표를 이 PC에 저장하지 못했습니다."

    def snapshot(self) -> dict:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> dict:
        elapsed = self._elapsed_ms if self._started is None else int((monotonic() - self._started) * 1000)
        queue = self._queue
        worklist = None
        if queue:
            active = self._request.item if self._request else None
            current_ms = elapsed if self._state["state"] == "working" else 0
            worklist = {"id": queue.key, "ready": queue.baseline is not None,
                        "active": active.key if active else "",
                        "elapsed_ms": queue.elapsed_ms + current_ms,
                        "items": [
                            {"id": item.key, "title": item.title, "detail": item.detail,
                             "draft": queue.drafts.get(item.key),
                             "scheduled": item.key in queue.scheduled,
                             "observation_hours": item.observation_hours(),
                             "elapsed_ms": queue.item_elapsed_ms.get(item.key, 0) + (current_ms if item == active else 0),
                             "state": ("working" if item == active and self._state["state"] == "working"
                                       else "error" if item.key in queue.interrupted
                                       else "draft" if item.key in queue.drafts else "pending")}
                            for item in queue.items
                        ]}
            if queue.forecast:
                worklist["forecast"] = queue.forecast
                worklist["automated_count"] = len(queue.scheduled)
            worklist["can_resume"] = (
                queue.baseline is not None and self._state["state"] != "working"
                and bool(queue.scheduled.keys() - queue.attempted)
            )
        return {**self._state, "elapsed_ms": elapsed, "work_queue": worklist,
                "total_ms": self._total_ms + (elapsed if self._started is not None else 0),
                "timing_saved": not self._timing_error,
                "can_reply": self._state["state"] == "error" and bool(self._request and self._request.handoff)}

    def _set(self, state: str, message: str, *, sample: tuple[str, int] | None = None, **values) -> None:
        with self._lock:
            self._state.update(state=state, message=message, **values)
            item = self._request.item if self._request else None
            if self._queue and item:
                if state == "done":
                    self._queue.drafts[item.key] = {"summary": values["summary"], "folder": values["folder"]}
                    self._queue.interrupted.discard(item.key)
                elif state == "error":
                    self._queue.interrupted.add(item.key)
            if state in ("ready", "done", "error"):
                self._elapsed_ms = int((monotonic() - self._started) * 1000)
                self._started = None
                if self._queue:
                    self._queue.elapsed_ms += self._elapsed_ms
                    if item:
                        elapsed = self._queue.item_elapsed_ms.get(item.key, 0)
                        self._queue.item_elapsed_ms[item.key] = elapsed + self._elapsed_ms
                self._refresh_total(self._elapsed_ms, sample=sample)
                self._checkpoint_locked(replace=state == "ready")
                if self._queue and (item or state == "ready"):
                    self._start_next_item_locked()

    def _refresh_total(self, elapsed_ms: int | None = None, *, sample: tuple[str, int] | None = None) -> None:
        try:
            self._total_ms = recorded_time(self.root, elapsed_ms, sample=sample)
            self._timing_error = False
        except (OSError, ValueError, sqlite3.Error):
            self._total_ms += elapsed_ms or 0
            self._timing_error = True

    def start(self, payload: object) -> dict:
        names = {"instructions", "blueprint", "paths", "workspace"}
        if (type(payload) is not dict or set(payload) not in (
            names, {"message"}, {"reply", "attempt"}, {"queue", "item", "paths", "change"}, {"queue", "resume"},
        )
            or any(type(text) is not str or "\0" in text for text in payload.values())):
            raise DraftError("입력값의 형식을 확인하세요.")
        if "resume" in payload:
            with self._lock:
                if (payload["resume"] != "remaining" or not self._queue or not self._queue.baseline
                    or payload["queue"] != self._queue.key or self._state["state"] == "working"):
                    raise DraftError("작업표에서 재개할 수 있는 자동 초안을 확인해 주세요.")
                if not self._start_next_item_locked():
                    raise DraftError("파일과 변경 내용이 정해진 다음 파트가 없습니다.")
                return self._snapshot_locked()
        if "queue" in payload:
            return self._start_item(payload)
        if "reply" in payload:
            reply = payload["reply"].strip()
            if not reply or len(reply.encode()) > _REPLY_LIMIT:
                raise DraftError("추가 지시를 450자 안팎으로 짧게 적어 주세요.")
            with self._lock:
                request = self._request
                if (self._state["state"] != "error" or not request or not request.handoff
                    or payload["attempt"] != self._state.get("attempt")):
                    raise DraftError("현재 화면에 표시된 중단 작업에서 답장을 보내 주세요.")
                return self._begin(replace(request, replies=(*request.replies[-2:], reply)), self._context)
        handoff = "message" in payload
        instruction = payload["message" if handoff else "instructions"].strip()
        design = payload.get("blueprint", "").strip()
        spec = payload.get("paths", "").strip()
        folder = payload.get("workspace", "").strip()
        if not instruction:
            raise DraftError("작업 지시를 넣으세요.")
        if folder and not spec:
            raise DraftError("기존 프로젝트를 바꿀 때는 작업할 파일 경로를 지정하세요.")
        if (any(len(value.encode()) > DOCUMENT_LIMIT for value in (instruction, design)) or len(folder) > 1024):
            raise DraftError("입력 문서나 파일 목록을 나누어 넣으세요.")
        paths = _draft_paths(spec)
        if folder:
            folder = folder.removeprefix('"').removesuffix('"')
            _local_absolute(folder)
        items = handoff_tasks(instruction) if handoff else ()
        with self._lock:
            if self._state["state"] == "working":
                raise DraftError("현재 작업이 끝나면 다음 작업을 시작할 수 있습니다.")
            if (items and self._queue and self._queue.baseline
                and self._queue.baseline.task.text == instruction):
                return self._snapshot_locked()
            self._queue = _WorkQueue(secrets.token_hex(12), items) if items else None
            return self._begin(_DraftRequest(instruction, design, paths, folder, handoff), None)

    def _start_item(self, payload: dict[str, str]) -> dict:
        paths = _draft_paths(payload["paths"])
        change = payload["change"].strip()
        if not paths:
            raise DraftError("이 항목에서 바꿀 파일의 상대 경로를 적어 주세요.")
        if (not change or change.casefold() in ("ㄱ", "ㄱㄱ", "다음", "계속", "go", "next")
            or len(change.encode()) > _REPLY_LIMIT):
            raise DraftError("이 파일에서 관찰한 문제나 바뀌어야 할 동작을 구체적으로 적어 주세요.")
        with self._lock:
            if self._state["state"] == "working":
                raise DraftError("현재 작업이 끝난 뒤 다른 항목을 시작해 주세요.")
            queue = self._queue
            if not queue or payload["queue"] != queue.key or not queue.baseline:
                raise DraftError("원래 인수인계의 작업 목록을 먼저 열어 주세요.")
            item = next((item for item in queue.items if item.key == payload["item"]), None)
            if item is None:
                raise DraftError("목록에서 작업 항목을 선택해 주세요.")
            return self._begin_item_locked(queue, item, paths, change)

    def _begin_item_locked(self, queue: _WorkQueue, item: HandoffTask, paths: tuple[str, ...], change: str) -> dict:
        scope = queue.baseline.scope
        if any(not scope.permits(path) or (scope.paths and path not in scope.paths) for path in paths):
            raise DraftError("작업 파일이 원래 인수인계에 적힌 수정 범위를 벗어납니다.")
        queue.attempted.add(item.key)
        return self._begin(_DraftRequest(f"{item.title}\n{item.detail}", "", paths, scope.workspace,
                                         True, (change,), item), None)

    def _start_next_item_locked(self) -> bool:
        queue = self._queue
        for item in queue.items:
            if item.key in queue.scheduled and item.key not in queue.attempted:
                paths, change = queue.scheduled[item.key]
                self._begin_item_locked(queue, item, paths, change)
                return True
        return False

    def _begin(self, request: _DraftRequest, context: _HandoffContext | None) -> dict:
        """Start the next attempt while the caller holds the workbench lock."""
        self._request, self._context = request, context
        self._refresh_total()
        self._started = monotonic()
        self._elapsed_ms = 0
        message = "붙여넣은 지시에서 작업 자료를 찾는 중입니다." if request.handoff else "작업 자료를 읽는 중입니다."
        if request.replies:
            message = "추가 지시를 반영해 다음 초안을 준비 중입니다."
        queue = self._queue
        plan = context.plan if context else queue.baseline.plan if queue and queue.baseline else None
        self._state = {"state": "working", "message": message, "attempt": secrets.token_hex(12),
                       "replies": list(request.replies), "plan": plan}
        if request.item:
            self._checkpoint_locked()
        worker = Thread(target=self._run, args=(request, context, queue), daemon=True)
        try:
            worker.start()
        except RuntimeError:
            self._state.update(state="error", message="작업을 시작하지 못했습니다.")
            self._started = None
        return self._snapshot_locked()

    def _prepare_handoff(self, message: str, replies: tuple[str, ...], *, overview: bool = False) -> _HandoffContext:
        combined = "\n\n".join((message, *replies))
        handoff = parse_handoff(combined)
        plan = {"repository": handoff.repository, "branch": handoff.branch,
                "paths": list(handoff.paths), "documents": len(handoff.documents)}
        self._set("working", "작업에 필요한 문서와 원본을 읽는 중입니다.", plan=plan)
        revision, documents = read_handoff_documents(handoff)
        plan = {**plan, "revision": revision, "documents": len(documents), "workspace": handoff.workspace}
        task = DraftDocument(message, "붙여넣은 작업 지시")
        if overview:
            if handoff.repository:
                self._set("working", "고정한 커밋의 GitHub Actions 기록을 확인 중입니다.", plan=dict(plan))
                try:
                    evidence = read_github_ci(handoff.repository, revision)
                    plan["baseline_ci"] = evidence
                    older = re.search(r"검증\s*코드\s*SHA[^\n]*?([a-f0-9]{40})", message, re.I)
                    if not evidence["runs"] and older and older[1].lower() != revision:
                        plan["reference_ci"] = read_github_ci(handoff.repository, older[1].lower())
                except DraftError:
                    plan["ci_unavailable"] = True
            return _HandoffContext(DraftDocument(combined, task.origin), documents, {}, {}, plan, handoff)
        paths = handoff.paths
        mentioned = tuple(path for path in handoff.mentioned if handoff.permits(path))
        if not paths and len(mentioned) == 1:
            paths = (text_path(mentioned[0]),)
        narrowed = not paths and bool(handoff.repository)
        if narrowed:
            files = github_files(handoff.repository, revision)
            candidates = {path: size for path, size in files.items() if size <= _OUTPUT_LIMIT}
            path = handoff.pick_file(candidates, _first_priority(message), documents)
            paths = (path,)
        elif not paths:
            paths = tuple(text_path(path) for path in mentioned)
        if not paths and (handoff.allowed or handoff.excluded):
            paths = tuple(text_path(path) for path in handoff.allowed if "*" not in path and handoff.permits(path))
            if not paths:
                raise DraftError("수정 범위 안에서 ‘작업 파일: 상대경로’ 한 개를 적어 주세요.")
        if len(paths) > 8 or len({path.casefold() for path in paths}) != len(paths):
            raise DraftError("서로 다른 작업 파일을 한 번에 1~8개 넣으세요.")
        if any(not handoff.permits(path) for path in paths):
            raise DraftError("작업 파일이 메시지에 적힌 수정 허용 범위를 벗어납니다.")
        if handoff.workspace and not paths:
            raise DraftError("기존 작업 폴더를 쓸 때는 메시지에 ‘작업 파일: 상대경로’를 적어 주세요.")
        originals, source_docs = self._read_sources(handoff, revision, paths, allow_missing=not narrowed)
        plan = {**plan, "paths": list(paths), "narrowed": narrowed}
        return _HandoffContext(task, documents, originals, source_docs, plan, handoff)

    def _read_sources(self, handoff: Handoff, revision: str, paths: tuple[str, ...], *,
                      allow_missing: bool) -> tuple[dict[str, str], dict[str, DraftDocument]]:
        source_docs = {}
        if handoff.repository and not handoff.workspace:
            for path in paths:
                document = read_github_file(handoff.repository, revision, path, allow_missing=allow_missing)
                if document is not None:
                    source_docs[path] = document
            originals = {path: source_docs[path].text if path in source_docs else "" for path in paths}
        else:
            originals = _existing_sources(handoff.workspace, paths, self.root)
        if any(len(source.encode()) > _OUTPUT_LIMIT for source in originals.values()):
            raise DraftError("작업 파일이 로컬 초안 크기 한도를 넘었습니다. 더 작은 파일을 선택해 주세요.")
        return originals, source_docs

    @staticmethod
    def _scheduled_items(items: tuple[HandoffTask, ...], scope: Handoff) -> dict[str, tuple[tuple[str, ...], str]]:
        scheduled = {}
        for item in items:
            spec = item.draft_spec()
            if spec is None:
                continue
            raw_paths, change = spec
            try:
                paths = _draft_paths("\n".join(re.split(r"\s*[,;]\s*", raw_paths.replace(chr(96), ""))))
            except DraftError:
                continue
            if (paths and len(change.encode()) <= _REPLY_LIMIT
                and all(scope.permits(path) and (not scope.paths or path in scope.paths) for path in paths)):
                scheduled[item.key] = paths, change
        return scheduled

    def _run(self, request: _DraftRequest, prepared: _HandoffContext | None, queue: _WorkQueue | None) -> None:
        saving = False
        try:
            if queue and not request.item:
                baseline = self._prepare_handoff(request.instruction, request.replies, overview=True)
                scheduled = self._scheduled_items(queue.items, baseline.scope)
                forecast = estimated_duration(self.root, "focused") if scheduled else None
                with self._lock:
                    queue.baseline = baseline
                    queue.scheduled = scheduled
                    queue.forecast = forecast
                self._set("ready", f"인수인계에서 작업 {len(queue.items)}개를 찾았습니다.", plan=baseline.plan)
                return
            fragments = None
            plan = None
            focused = False
            if request.handoff:
                if prepared is None:
                    if request.item and queue and queue.baseline:
                        baseline = queue.baseline
                        plan = {**baseline.plan, "paths": list(request.paths), "narrowed": False,
                                "work_item": request.item.title}
                        self._set("working", "선택한 작업의 원본을 읽는 중입니다.", plan=plan)
                        originals, source_docs = self._read_sources(
                            baseline.scope, plan["revision"], request.paths, allow_missing=True,
                        )
                        prepared = _HandoffContext(DraftDocument(request.instruction, "선택한 인수인계 항목"),
                                                   baseline.documents, originals, source_docs, plan, baseline.scope)
                    else:
                        prepared = self._prepare_handoff(request.instruction, request.replies)
                    with self._lock:
                        self._context = prepared
                originals, source_docs, plan = prepared.originals, prepared.source_docs, prepared.plan
                if request.replies:
                    target = parse_handoff(request.replies[-1])
                    if ((target.repository and target.repository != plan["repository"])
                        or (target.branch and target.branch not in (plan["branch"], plan["revision"]))
                        or (target.workspace and target.workspace != plan["workspace"])
                        or any(path not in originals for path in target.paths)):
                        raise DraftError("저장소나 작업 파일을 바꾸려면 왼쪽에서 새 작업을 보내 주세요.")
                    if target.paths:
                        originals = {path: originals[path] for path in target.paths}
                        source_docs = {path: source_docs[path] for path in originals if path in source_docs}
                        plan = {**plan, "paths": list(originals)}
                focused = plan["narrowed"] or bool(request.replies)
                prompt, fragments, evidence = _handoff_prompt(
                    prepared.task, prepared.documents, originals, source_docs, plan["narrowed"],
                    replies=request.replies,
                )
            else:
                refs = {}
                task = read_document(request.instruction, refs)
                blueprint = read_document(request.design, refs) if request.design else None
                originals = _existing_sources(request.workspace, request.paths, self.root)
                prompt, used = _create_prompt(task.text, blueprint.text if blueprint else "", originals)
                evidence = [task.evidence(len(task.text))]
                if blueprint:
                    evidence.append(blueprint.evidence(used))
            output_tokens = _FOCUSED_OUTPUT_TOKENS if focused else STRUCTURED_OUTPUT_TOKENS
            context = _SHORT_CONTEXT if len(prompt.encode()) <= _SHORT_CONTEXT - output_tokens else _CONTEXT
            kind = "focused" if focused else ("short" if context == _SHORT_CONTEXT else "long")
            forecast = estimated_duration(self.root, kind)
            model_started = monotonic()
            forecast["from_elapsed_ms"] = int((model_started - self._started) * 1000)
            self._set("working", "로컬 Qwen이 파일 초안을 작성 중입니다.", plan=plan, forecast=forecast)
            generate = self.provider.generate(
                prompt, model_lock=OneModelLock(self.root),
                budget=BudgetGuard(ModelBudget(max_calls=1, max_seconds=270,
                    max_context_tokens=context, max_output_bytes=_OUTPUT_LIMIT)),
                allow_generation=True, structured=True, structured_tokens=output_tokens,
            )
            if generate.untrusted is not True:
                raise DraftError("Qwen 초안의 출처를 확인할 수 없습니다.")
            reply = _apply_model_edits(generate.text, originals, fragments) if fragments is not None else generate.text
            summary, files = _model_files(reply, originals)
            if request.item and any(file["syntax"] == "Python 문법 확인 필요" for file in files):
                raise DraftError("이 항목의 초안이 Python 구문 검사에서 실패했습니다. 수정 범위를 구체화해 다시 시도해 주세요.")
            self._set("working", "변경 내용을 정리해 별도 폴더에 저장 중입니다.", saving=True)
            saving = True
            destination = self._save(files, summary, evidence, plan)
            message = "첫 작업의 로컬 초안을 저장했습니다." if plan and plan["narrowed"] else "초안 파일을 저장했습니다."
            self._set("done", message, summary=summary,
                      folder=str(destination / "files"), files=files, sources=evidence,
                      sample=(kind, int((monotonic() - model_started) * 1000)))
        except DraftError as exc:
            self._set("error", str(exc))
        except (ProviderHold, ModelLockUnsafe) as exc:
            code = (exc.detail or exc.code) if isinstance(exc, ProviderHold) else "MODEL_LOCK"
            title, hint = _MODEL_ERRORS.get(code, (
                "Ollama에서 받은 Qwen 응답을 처리할 수 없습니다.",
                "같은 지시문을 다시 보내세요. 같은 문제가 반복되면 아래 오류 코드를 보내 주세요.",
            ))
            self._set("error", title, error={"code": code, "hint": hint})
        except (OSError, ValueError, OverflowError, RuntimeError):
            if saving:
                self._set("error", "Qwen의 초안을 파일로 저장하지 못했습니다.", error={
                    "code": "DRAFT_SAVE",
                    "hint": f"탐색기에서 이 폴더에 파일을 만들 수 있는지 확인해 주세요. {self.root}",
                })
            else:
                self._set("error", "작업을 준비하거나 Qwen에 넘기는 중 오류가 발생했습니다.", error={
                    "code": "DRAFT_PROCESSING",
                    "hint": "지시문을 그대로 다시 보내세요. 같은 문제가 반복되면 아래 오류 코드를 보내 주세요.",
                })

    def _save(self, files: list[dict], summary: str, sources: list[dict], plan: dict | None) -> Path:
        local_path_stat(self.root)
        target = self.root / (datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(5))
        with tempfile.TemporaryDirectory(prefix=".mla-draft-", dir=self.root) as temporary:
            stage = Path(temporary) / "draft"
            for file in files:
                path = stage / "files" / file["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(file["content"].encode())
            (stage / "work.json").write_text(json.dumps({
                "summary": summary, "paths": [file["path"] for file in files], "sources": sources,
                **({"plan": plan} if plan else {}),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            stage.rename(target)
        return target
