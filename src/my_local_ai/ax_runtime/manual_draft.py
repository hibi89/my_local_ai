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
import tomllib
from threading import Lock, Thread
from time import monotonic, sleep

from ..state.local_files import local_path_stat, read_bounded_regular
from .budgets import BudgetGuard, ModelBudget
from .draft_documents import (
    DOCUMENT_LIMIT, DraftDocument, DraftError, github_files, read_document, read_github_ci, read_github_file,
)
from .draft_evidence import PinnedEvidence
from .approved_workflow import ExecutionHold, WORKFLOW, eligible_profile, execute_once, initial_receipt, reconcile_existing
from .draft_intake import Handoff, HandoffTask, handoff_tasks, parse_handoff, read_handoff_documents, text_path
from .draft_recovery import GeminiDraftAdvisor, MAX_DRAFT_ATTEMPTS, RECOVERY_ACTIONS
from .draft_timing import estimated_duration, load_work_queue, recorded_time, save_work_queue
from .ollama_provider import OllamaProvider, STRUCTURED_OUTPUT_TOKENS
from .pinned_source_cache import PinnedSourceCache
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
    "DRAFT_FORMAT": ("Qwen 초안의 파일 또는 수정 위치를 확인할 수 없었습니다.",
                     "파일과 해당 파일에서 바꿀 내용을 구체적으로 적어 주세요."),
    "DRAFT_SYNTAX": ("Qwen 초안이 Python 구문 검사에 실패했습니다.",
                     "검사에서 실패한 파트의 수정 범위를 좁혀 주세요."),
}


class _DraftOutputError(DraftError):
    def __init__(self, message: str, code: str = "DRAFT_FORMAT"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _DraftRequest:
    instruction: str
    design: str
    paths: tuple[str, ...]
    workspace: str
    handoff: bool
    replies: tuple[str, ...] = ()
    item: HandoffTask | None = None
    inspect_only: bool = False


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
    planned_paths: dict[str, tuple[str, ...]] = field(default_factory=dict)
    forecast: dict | None = None
    inspections: dict[str, dict] = field(default_factory=dict)
    rechecks: set[str] = field(default_factory=set)
    evidence_reader: PinnedEvidence | None = None
    auto_drafts: bool = True
    paused: bool = False
    failures: dict[str, dict] = field(default_factory=dict)
    recovery: dict[str, dict] = field(default_factory=dict)
    executions: dict[str, dict] = field(default_factory=dict)


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
                    replies: tuple[str, ...] = (), compact: bool = False) -> tuple[str, dict | None, list]:
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
    if compact:
        preamble += " Return only the required JSON fields and the smallest exact edit."
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
        if compact:
            document_room = min(document_room, 200)
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
        per_document = min(180 if compact else 2300, room // len(documents))
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
        raise _DraftOutputError("Qwen이 제안한 수정 위치를 원본에서 정확히 확인할 수 없습니다. 수정 대상을 더 좁혀 주세요.") from None


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
            elif path.lower().endswith(".json"):
                try:
                    json.loads(source, object_pairs_hook=_unique_fields,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                    syntax = "JSON 문법 확인"
                except (ValueError, RecursionError):
                    syntax = "JSON 문법 확인 필요"
            elif path.lower().endswith(".toml"):
                try:
                    tomllib.loads(source)
                    syntax = "TOML 문법 확인"
                except (ValueError, RecursionError):
                    syntax = "TOML 문법 확인 필요"
            diff = "\n".join(unified_diff(before.splitlines(), source.splitlines(),
                "원본/" + path, "초안/" + path, lineterm=""))
            files.append({"path": path, "content": source, "diff": diff, "syntax": syntax})
    except (UnicodeError, ValueError, RecursionError):
        raise _DraftOutputError("Qwen 응답의 파일 목록을 확인할 수 없습니다. 작업 범위를 줄여 다시 시작하세요.") from None
    if not files:
        if not data["files"] and data["summary"].strip():
            raise DraftError("만들 수 있는 수정이 확인되지 않았습니다. Qwen 설명 · " + data["summary"].strip()[:240])
        raise DraftError("Qwen이 변경된 파일을 내놓지 않았습니다. 원하는 변경을 구체적으로 적어 주세요.")
    return data["summary"].strip()[:1200], files


class LocalDrafts:
    def __init__(self, output: Path, *, provider: OllamaProvider | None = None,
                 advisor: GeminiDraftAdvisor | None = None):
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
        self._source_cache = PinnedSourceCache()
        # Only live, current-process workers justify continuous UI polling.
        # Reopen/restored receipts are not silently treated as running threads.
        self._remote_active: set[str] = set()
        self._started = None
        self._elapsed_ms = self._total_ms = 0
        self.advisor = GeminiDraftAdvisor() if advisor is None else advisor
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
            queue.inspections = {item.key: report for item in items
                                 if isinstance(report := saved.get("inspections", {}).get(item.key), dict)}
            queue.rechecks = {item.key for item in items if item.key in saved.get("rechecks", ())}
            for name in ("failures", "recovery"):
                records = saved.get(name, {})
                setattr(queue, name, {item.key: records[item.key] for item in items
                                      if type(records.get(item.key)) is dict})
            queue.executions = {item.key: saved.get("executions", {})[item.key]
                                for item in items if type(saved.get("executions", {}).get(item.key)) is dict}
            # The network dispatch may already have succeeded before a crash.
            # Never silently send it again on restore.
            for report in queue.executions.values():
                if report.get("state") in ("INTENT_RECORDED", "DISPATCHING", "RUNNING", "RECONCILING"):
                    report.update(state="HOLD", code="HOLD_INTERRUPTED_NO_REDISPATCH",
                                  p2_gate_accepted=False)
            # An interrupted unit is marked HOLD below, never replayed automatically.
            queue.auto_drafts = saved.get("continuous_enabled") is True
            queue.paused = saved.get("paused") is True
            if saved.get("active") and not saved.get("active_inspection"):
                active = saved["active"]
                queue.interrupted.add(active)
                queue.failures[active] = {"message": "MLA가 닫히면서 초안 시도가 중단됐습니다.",
                                          "hint": "저장된 결과를 확인한 뒤 이 파트에 추가 지시를 보내세요."}
            queue.elapsed_ms = max(0, int(saved["elapsed_ms"]))
            queue.item_elapsed_ms = {item.key: max(0, int(saved["item_elapsed_ms"].get(item.key, 0)))
                                     for item in items}
            queue.scheduled = self._scheduled_items(items, scope)
            stored_paths = saved.get("planned_paths", {})
            if type(stored_paths) is not dict:
                return
            for item in items:
                record = stored_paths.get(item.key)
                if record is None:
                    continue
                if (type(record) is not list or not 1 <= len(record) <= 8
                    or any(type(path) is not str for path in record)):
                    return
                selected = _draft_paths("\n".join(record))
                if len(selected) != len(record) or any(not scope.permits(p) for p in selected):
                    return
                queue.planned_paths[item.key] = selected
            queue.forecast = estimated_duration(self.root, "focused") if queue.scheduled else None
        except (ValueError, OverflowError, TypeError, KeyError, AttributeError):
            return
        self._queue = queue
        self._state.update(state="ready", message=f"작업표 {len(items)}개 파트와 진행 기록을 복구했습니다.", plan=plan)
        with self._lock:
            self._start_next_item_locked()

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
                "inspections": queue.inspections,
                "rechecks": sorted(queue.rechecks),
                "failures": queue.failures, "recovery": queue.recovery,
                "executions": queue.executions,
                "continuous_enabled": queue.auto_drafts, "paused": queue.paused,
                "planned_paths": {key: list(paths) for key, paths in queue.planned_paths.items()},
                "active_inspection": bool(active and self._request.inspect_only),
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
            working = self._state["state"] == "working"
            active = self._request.item if self._request and working else None
            current_ms = elapsed if working else 0
            worklist = {"id": queue.key, "ready": queue.baseline is not None,
                        "active": active.key if active else "",
                        "active_mode": ("inspection" if self._request.inspect_only else "draft") if active else "",
                        "gemini_configured": self.advisor.configured,
                        "verified_count": 0,  # An audit smoke cannot accept a P2 gate.
                        "executed_count": sum(record.get("state") == "PASS"
                                              for record in queue.executions.values()),
                        "executing": bool(self._remote_active),
                        "elapsed_ms": queue.elapsed_ms + current_ms,
                        "items": [
                            {"id": item.key, "title": item.title, "detail": item.detail,
                             "draft": queue.drafts.get(item.key),
                             "inspection": queue.inspections.get(item.key),
                             "execution": queue.executions.get(item.key),
                             "can_execute": self._can_execute(queue, item),
                             "can_reconcile": self._can_reconcile(queue, item),
                             "failure": queue.failures.get(item.key),
                             "recovery": queue.recovery.get(item.key),
                             "hold": self._item_hold(queue, item) if item != active else None,
                             "auto_inspection": not queue.paused and self._can_inspect(queue, item),
                             "scheduled": item.key in queue.scheduled,
                             "observation_hours": item.observation_hours(),
                             "elapsed_ms": queue.item_elapsed_ms.get(item.key, 0) + (current_ms if item == active else 0),
                             "state": ("working" if item == active
                                       else "error" if item.key in queue.interrupted
                                       else "draft" if item.key in queue.drafts
                                       else "inspected" if item.key in queue.inspections else "pending")}
                            for item in queue.items
                        ]}
            pending_drafts = sum(self._can_draft(queue, item) for item in queue.items)
            pending_reads = sum(self._can_inspect(queue, item) for item in queue.items)
            stage = ("PAUSE_REQUESTED" if queue.paused and working else "PAUSED"
                     if queue.paused else "WORKING" if working else "READY_TO_CONTINUE"
                     if pending_reads or (queue.auto_drafts and pending_drafts)
                     else "AWAITING_REVIEW_OR_APPROVAL")
            messages = {
                "PAUSE_REQUESTED": "현재 유한 단계가 끝나면 자동 진행을 일시정지합니다.",
                "PAUSED": "자동 진행이 일시정지됐습니다. 진행 기록은 저장했습니다.",
                "WORKING": "장시간 작업 중 · 각 단계의 결과를 별도로 저장합니다.",
                "READY_TO_CONTINUE": "다음 안전 파트의 초안 또는 자료 확인을 진행합니다.",
                "AWAITING_REVIEW_OR_APPROVAL": "자동 진행 가능한 파트가 없습니다. 검토·검증·승인을 확인하세요.",
            }
            worklist["continuous"] = {
                "enabled": queue.auto_drafts, "paused": queue.paused, "stage": stage,
                "message": messages[stage], "pending_drafts": pending_drafts,
                "pending_reads": pending_reads, "draft_candidates": len(queue.drafts),
                "verified": False,
            }
            worklist["can_pause"] = queue.auto_drafts and not queue.paused
            worklist["can_continue"] = queue.paused or not queue.auto_drafts
            if queue.forecast:
                worklist["forecast"] = queue.forecast
                worklist["automated_count"] = len(queue.scheduled)
            worklist["can_resume"] = (
                queue.baseline is not None and not working
                and any(self._can_draft(queue, item) for item in queue.items)
            )
            worklist["can_refresh"] = not working and any(
                item.key in queue.inspections and self._can_inspect(queue, item, recheck=True)
                for item in queue.items
            )
            if queue.baseline and not working and not worklist["can_resume"]:
                held = [row for row in worklist["items"] if row["hold"]]
                next_row = next((row for row in held if row["hold"]["kind"] != "dependency"), None)
                worklist["blocked"] = (next_row or (held[0] if held else None) or {}).get("id", "")
        return {**self._state, "elapsed_ms": elapsed, "work_queue": worklist,
                "total_ms": self._total_ms + (elapsed if self._started is not None else 0),
                "timing_saved": not self._timing_error,
                "can_reply": self._state["state"] == "error" and bool(self._request and self._request.handoff)}

    def _set(self, state: str, message: str, *, sample: tuple[str, int] | None = None,
             inspection: dict | None = None, **values) -> None:
        with self._lock:
            self._state.update(state=state, message=message, **values)
            item = self._request.item if self._request else None
            if self._queue and item:
                if inspection is not None:
                    queue = self._queue
                    if queue.baseline is not None and "plan" in values:
                        queue.baseline = replace(queue.baseline, plan=values["plan"])
                    before = queue.inspections.get(item.key)
                    if (item.key in queue.rechecks and before and before.get("state") == "observed"
                        and inspection["state"] == "limited"):
                        inspection = {**before, "recheck_note": "이번 재확인에서 자료를 읽지 못해 이전 읽기 결과를 표시합니다."}
                    queue.inspections[item.key] = inspection
                    queue.rechecks.discard(item.key)
                elif state == "done":
                    self._queue.drafts[item.key] = {"summary": values["summary"], "folder": values["folder"]}
                    self._queue.interrupted.discard(item.key)
                    self._queue.failures.pop(item.key, None)
                elif state == "error":
                    self._queue.interrupted.add(item.key)
                    self._queue.failures[item.key] = {"message": message, **values.get("error", {})}
            if state in ("ready", "done", "error"):
                self._elapsed_ms = int((monotonic() - self._started) * 1000)
                self._started = None
                if self._queue:
                    self._queue.elapsed_ms += self._elapsed_ms
                    if item:
                        elapsed = self._queue.item_elapsed_ms.get(item.key, 0)
                        self._queue.item_elapsed_ms[item.key] = elapsed + self._elapsed_ms
                self._refresh_total(self._elapsed_ms, sample=sample)
                self._checkpoint_locked(replace=state == "ready" and item is None)
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
            names, {"message"}, {"reply", "attempt"}, {"queue", "item", "paths", "change"},
            {"queue", "resume"}, {"queue", "refresh"},
            {"queue", "execute", "item"}, {"queue", "reconcile", "item"}, {"queue", "continuous"},
        )
            or any(type(text) is not str or "\0" in text for text in payload.values())):
            raise DraftError("입력값의 형식을 확인하세요.")
        if "continuous" in payload:
            with self._lock:
                queue = self._queue
                if (not queue or not queue.baseline or payload["queue"] != queue.key
                    or payload["continuous"] not in ("pause", "resume")):
                    raise DraftError("유효한 작업표와 자동 진행 요청을 확인해 주세요.")
                old = (queue.auto_drafts, queue.paused)
                if payload["continuous"] == "pause":
                    queue.paused = True
                else:
                    queue.auto_drafts, queue.paused = True, False
                self._state.pop("checkpoint_error", None)
                self._checkpoint_locked()
                if self._state.get("checkpoint_error"):
                    queue.auto_drafts, queue.paused = old
                    raise DraftError("자동 진행 설정을 안전하게 저장하지 못했습니다.")
                if not queue.paused and self._state["state"] != "working":
                    self._start_next_item_locked()
                return self._snapshot_locked()
        if "execute" in payload:
            return self._start_approved_execution(payload)
        if "reconcile" in payload:
            return self._start_reconcile_execution(payload)
        if "resume" in payload:
            with self._lock:
                if (payload["resume"] != "remaining" or not self._queue or not self._queue.baseline
                    or payload["queue"] != self._queue.key or self._state["state"] == "working"):
                    raise DraftError("작업표에서 재개할 수 있는 자동 초안을 확인해 주세요.")
                self._queue.auto_drafts = True
                self._queue.paused = False
                if not self._start_next_item_locked():
                    raise DraftError("파일과 변경 내용이 정해진 다음 파트가 없습니다.")
                return self._snapshot_locked()
        if "refresh" in payload:
            with self._lock:
                queue = self._queue
                if (payload["refresh"] != "evidence" or not queue or not queue.baseline
                    or payload["queue"] != queue.key or self._state["state"] == "working"):
                    raise DraftError("읽기 결과를 다시 확인할 작업표를 열어 주세요.")
                queue.evidence_reader = None
                queue.rechecks = {item.key for item in queue.items if self._can_inspect(queue, item, recheck=True)}
                self._start_next_item_locked()
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
                return self._resubmit_queue_locked(self._queue)
            self._queue = _WorkQueue(secrets.token_hex(12), items) if items else None
            return self._begin(_DraftRequest(instruction, design, paths, folder, handoff), None)

    def _resubmit_queue_locked(self, queue: _WorkQueue) -> dict:
        queue.auto_drafts = True
        queue.paused = False
        if not self._start_next_item_locked():
            self._state["submission_notice"] = "같은 지시문을 받았습니다. 지금 바로 시작할 수 있는 파트가 없습니다."
        return self._snapshot_locked()

    @staticmethod
    def _can_execute(queue: _WorkQueue, item: HandoffTask) -> bool:
        baseline = queue.baseline
        return (baseline is not None and item.key not in queue.executions
                and item.key in queue.inspections
                and eligible_profile(baseline.scope.repository, baseline.scope.branch,
                                     baseline.plan.get("revision", ""), item.title))

    def _can_reconcile(self, queue: _WorkQueue, item: HandoffTask) -> bool:
        if item.key in self._remote_active:
            return False
        baseline = queue.baseline
        receipt = queue.executions.get(item.key)
        if not baseline or not receipt or receipt.get("state") in ("PASS", "FAIL", "RECONCILING"):
            return False
        if not eligible_profile(baseline.scope.repository, baseline.scope.branch,
                                baseline.plan.get("revision", ""), item.title):
            return False
        run_id = receipt.get("run_id")
        return (receipt.get("source_sha") == baseline.plan.get("revision")
                and receipt.get("workflow") == WORKFLOW
                and (type(run_id) is int and run_id > 0
                     or run_id is None and type(receipt.get("dispatched_at")) is str))

    def _start_reconcile_execution(self, payload: dict[str, str]) -> dict:
        """Explicit read-only reconciliation; original dispatch is never repeated."""
        with self._lock:
            queue = self._queue
            if (payload["reconcile"] != "existing" or not queue or not queue.baseline
                or payload["queue"] != queue.key or self._state["state"] == "working"):
                raise DraftError("확인할 고정 작업표와 기존 실행을 선택해 주세요.")
            item = next((item for item in queue.items if item.key == payload["item"]), None)
            if item is None or not self._can_reconcile(queue, item):
                raise DraftError("이 파트에는 다시 읽을 승인 실행 기록이 없습니다.")
            if self._remote_active or any(r.get("state") == "RECONCILING" for r in queue.executions.values()):
                raise DraftError("앞선 실행 기록의 읽기 확인이 끝날 때까지 기다려 주세요.")
            previous = dict(queue.executions[item.key])
            queue.executions[item.key] = {**previous, "state": "RECONCILING"}
            self._state.pop("checkpoint_error", None)
            self._checkpoint_locked()
            if self._state.get("checkpoint_error"):
                queue.executions[item.key] = previous
                raise DraftError("실행 기록 조회 의도를 저장하지 못했습니다.")
            self._remote_active.add(item.key)
            try:
                Thread(target=self._reconcile_execution,
                       args=(queue.key, item.key, queue.baseline.plan["revision"], previous),
                       daemon=True).start()
            except RuntimeError:
                self._remote_active.discard(item.key)
                queue.executions[item.key] = previous
                self._checkpoint_locked()
                raise DraftError("이전 실행 결과 조회 작업자를 시작하지 못했습니다.") from None
            return self._snapshot_locked()

    def _reconcile_execution(self, key: str, item_key: str, revision: str, receipt: dict) -> None:
        try:
            report = reconcile_existing(revision, receipt)
        except ExecutionHold as error:
            report = {"state": "HOLD", "code": error.code, "p2_gate_accepted": False,
                      "independent_verified": False}
        except Exception:
            report = {"state": "HOLD", "code": "HOLD_RECONCILE_UNAVAILABLE",
                      "p2_gate_accepted": False, "independent_verified": False}
        with self._lock:
            self._remote_active.discard(item_key)
            queue = self._queue
            if not queue or queue.key != key or item_key not in queue.executions:
                return
            # Model/data supplied fields never replace the approved receipt identity.
            updates = {k: v for k, v in report.items()
                       if k not in ("source_sha", "test_id", "workflow")}
            queue.executions[item_key] = {**queue.executions[item_key], **updates}
            self._checkpoint_locked()

    def _start_approved_execution(self, payload: dict[str, str]) -> dict:
        """A deliberate owner click authorizes only the single pinned manual workflow."""
        with self._lock:
            queue = self._queue
            if (payload["execute"] != "reqea-manual" or not queue or not queue.baseline
                or payload["queue"] != queue.key or self._state["state"] == "working"):
                raise DraftError("실행할 작업표와 승인된 실행 범위를 확인해 주세요.")
            item = next((item for item in queue.items if item.key == payload["item"]), None)
            if item is None or not self._can_execute(queue, item):
                raise DraftError("이미 실행했거나 고정된 승인 대상이 아닙니다. 다시 제출해도 재실행하지 않습니다.")
            if self._remote_active or any(entry.get("state") in ("INTENT_RECORDED", "DISPATCHING", "RUNNING", "RECONCILING")
                   for entry in queue.executions.values()):
                raise DraftError("앞선 승인 실행 결과를 확인해 주세요.")
            revision = queue.baseline.plan["revision"]
            queue.executions[item.key] = initial_receipt(revision)
            self._state.pop("checkpoint_error", None)
            self._checkpoint_locked()
            if self._state.get("checkpoint_error"):
                del queue.executions[item.key]
                raise DraftError("실행 의도를 저장하지 못했습니다. 외부 실행을 시작하지 않습니다.")
            self._remote_active.add(item.key)
            try:
                Thread(target=self._execute_approved, args=(queue.key, item.key, revision),
                       daemon=True).start()
            except RuntimeError:
                self._remote_active.discard(item.key)
                queue.executions[item.key] = {**queue.executions[item.key], "state": "HOLD",
                                              "code": "HOLD_WORKER_START_FAILED",
                                              "p2_gate_accepted": False}
                self._checkpoint_locked()
                raise DraftError("승인 실행 작업자를 시작하지 못했습니다.") from None
            return self._snapshot_locked()

    def _execute_approved(self, key: str, item_key: str, revision: str) -> None:
        def persist(report: dict) -> None:
            with self._lock:
                queue = self._queue
                if not queue or queue.key != key or item_key not in queue.executions:
                    return
                previous = queue.executions[item_key]
                # Immutable identity; no status response may change target SHA/test ID.
                cleaned = {k: v for k, v in report.items()
                           if k not in ("source_sha", "test_id", "workflow")}
                queue.executions[item_key] = {**previous, **cleaned}
                self._checkpoint_locked()
        try:
            execute_once(revision, persist)
        except Exception:
            # A network dispatch may have succeeded. Never automatically retry.
            persist({"state": "HOLD", "code": "HOLD_EXECUTION_UNCERTAIN_NO_REDISPATCH",
                     "p2_gate_accepted": False})
        finally:
            with self._lock:
                self._remote_active.discard(item_key)

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
        if item.dependencies():
            raise DraftError("이 파트의 필수 선행 검증을 먼저 완료해 주세요.")
        scope = queue.baseline.scope
        if any(not scope.permits(path) or (scope.paths and path not in scope.paths) for path in paths):
            raise DraftError("작업 파일이 원래 인수인계에 적힌 수정 범위를 벗어납니다.")
        conflicts = self._file_conflicts(queue, item, paths)
        if conflicts:
            raise DraftError("같은 파일을 수정할 다른 파트가 있습니다. 먼저 결과를 검토·통합해야 합니다: "
                             + ", ".join(title for title, _ in conflicts))
        queue.planned_paths[item.key] = paths
        queue.attempted.add(item.key)
        queue.recovery.pop(item.key, None)
        return self._begin(_DraftRequest(f"{item.title}\n{item.detail}", "", paths, scope.workspace,
                                         True, (change,), item), None)

    def _start_next_item_locked(self) -> bool:
        queue = self._queue
        if queue is None or queue.paused or self._state.get("checkpoint_error"):
            return False
        for item in queue.items:
            if queue.auto_drafts and self._can_draft(queue, item):
                paths, change = queue.scheduled[item.key]
                self._begin_item_locked(queue, item, paths, change)
                return True
            if self._can_inspect(queue, item):
                self._begin(_DraftRequest(item.title, "", (), "", True, item=item, inspect_only=True),
                            queue.baseline)
                return True
        return False

    @staticmethod
    def _file_conflicts(queue: _WorkQueue, item: HandoffTask,
                        paths: tuple[str, ...]) -> list[tuple[str, str]]:
        """Do not draft from the same pinned original over another SWU's draft.

        Earlier declared source claims win; later claims block only if already
        attempted. No candidate is silently promoted to a new source HEAD.
        """
        target = {path.casefold(): path for path in paths}
        if not target:
            return []
        position = next((i for i, row in enumerate(queue.items) if row.key == item.key), -1)
        conflicts = []
        for i, row in enumerate(queue.items):
            if row.key == item.key:
                continue
            if i > position and row.key not in queue.attempted and row.key not in queue.drafts:
                continue
            previous = queue.planned_paths.get(row.key)
            if previous is None:
                previous = queue.scheduled.get(row.key, ((), ""))[0]
            overlaps = sorted(target[p.casefold()] for p in previous if p.casefold() in target)
            if overlaps:
                conflicts.append((row.title, overlaps[0]))
        return conflicts

    @staticmethod
    def _can_draft(queue: _WorkQueue, item: HandoffTask) -> bool:
        return (item.key in queue.scheduled and item.key not in queue.attempted
                and item.key not in queue.drafts and not item.dependencies()
                and not LocalDrafts._file_conflicts(queue, item, queue.scheduled[item.key][0]))

    def _item_hold(self, queue: _WorkQueue, item: HandoffTask) -> dict | None:
        if not queue.baseline or self._can_draft(queue, item) or self._can_inspect(queue, item):
            return None
        scoped = queue.planned_paths.get(item.key) or queue.scheduled.get(item.key, ((), ""))[0]
        conflicts = self._file_conflicts(queue, item, scoped)
        if conflicts:
            return {"kind": "conflict", "label": "동일 소스 파일 충돌 보류",
                    "detail": "다른 파트의 같은 파일 초안과 덮어쓰기 충돌 위험이 있습니다. "
                              "검토·통합 및 검증 전 자동 진행하지 않습니다: "
                              + ", ".join(f"{title} ({path})" for title, path in conflicts)}
        if execution := queue.executions.get(item.key):
            return {"kind": "execution", "label": "실제 실행 " + execution["state"],
                    "detail": "원격 CLI 감사 결과입니다. 전체 P2 검증이나 독립 감사가 아닙니다."}
        if self._can_execute(queue, item):
            return {"kind": "execution", "label": "승인된 실제 실행 대기",
                    "detail": "확인된 GitHub Actions 수동 CLI 감사를 한 번 실행할 수 있습니다. 사용자 확인이 필요합니다."}
        if dependencies := item.dependencies():
            return {"kind": "dependency", "label": "선행 검증 보류",
                    "detail": "필수 선행 파트의 실행 결과가 필요합니다. " + ", ".join(dependencies)}
        if failure := queue.failures.get(item.key):
            return {"kind": "failed", "label": "초안 작업 보류", "detail": failure["message"]}
        if item.key in queue.interrupted:
            return {"kind": "failed", "label": "초안 작업 보류", "detail": "이 파트의 수정 지시를 확인해 주세요."}
        if item.key in queue.drafts:
            return {"kind": "verification", "label": "초안 검증 보류",
                    "detail": "초안이 저장됐습니다. 실제 검증에는 보호 실행기가 필요합니다."}
        if inspection := queue.inspections.get(item.key):
            if inspection["state"] == "limited":
                return {"kind": "source", "label": "읽기 자료 확인 필요",
                        "detail": "저장소 접근과 검사할 파일을 확인한 뒤 읽기 결과를 새로 조회할 수 있습니다."}
            return {"kind": "verification", "label": "실행 검증 보류",
                    "detail": f"남은 검증은 {inspection['remaining']}입니다. 현재 작업대에 보호된 테스트 실행 경로가 없습니다."}
        return {"kind": "input", "label": "작업 범위 확인 필요",
                "detail": "초안을 시작하려면 작업 파일과 구체적인 변경 내용이 필요합니다."}

    @staticmethod
    def _can_inspect(queue: _WorkQueue, item: HandoffTask, *, recheck: bool = False) -> bool:
        return (queue.baseline is not None and bool(queue.baseline.scope.repository)
                and item.key not in queue.scheduled and item.key not in queue.drafts
                and (recheck or item.key in queue.rechecks or item.key not in queue.inspections))

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
        if request.inspect_only:
            message = ("기준 커밋의 읽기 검사와 기존 기록을 다시 확인 중입니다."
                       if request.item.key in queue.rechecks
                       else "기준 커밋에서 이 파트의 소스와 기존 기록을 확인 중입니다.")
        plan = context.plan if context else queue.baseline.plan if queue and queue.baseline else None
        if request.inspect_only:
            plan = {**plan, "work_item": request.item.title}
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
                document = self._source_cache.read(handoff.repository, revision, path,
                                                   allow_missing=allow_missing, fetch=read_github_file)
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
        if request.inspect_only:
            self._inspect_item(request.item, queue)
            return
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
            summary, files, evidence, sample = self._generate_draft(
                request, queue, prepared, plan, focused, originals, prompt, fragments, evidence,
            )
            self._set("working", "변경 내용을 정리해 별도 폴더에 저장 중입니다.", saving=True)
            saving = True
            destination = self._save(files, summary, evidence, plan)
            message = "첫 작업의 로컬 초안을 저장했습니다." if plan and plan["narrowed"] else "초안 파일을 저장했습니다."
            self._set("done", message, summary=summary, sample=sample,
                      folder=str(destination / "files"), files=files, sources=evidence)
        except _DraftOutputError as exc:
            self._set("error", str(exc), error={"code": exc.code, "hint": _MODEL_ERRORS[exc.code][1]})
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

    def _generate_draft(self, request: _DraftRequest, queue: _WorkQueue | None,
                        prepared: _HandoffContext | None, plan: dict | None, focused: bool,
                        originals: dict[str, str], prompt: str, fragments: dict | None, evidence: list):
        limit = MAX_DRAFT_ATTEMPTS if request.item else 1
        output_tokens = _FOCUSED_OUTPUT_TOKENS if focused else STRUCTURED_OUTPUT_TOKENS
        compact = False
        for number in range(1, limit + 1):
            context = _SHORT_CONTEXT if len(prompt.encode()) <= _SHORT_CONTEXT - output_tokens else _CONTEXT
            kind = "focused" if focused else ("short" if context == _SHORT_CONTEXT else "long")
            forecast = estimated_duration(self.root, kind)
            model_started = monotonic()
            forecast["from_elapsed_ms"] = int((model_started - self._started) * 1000)
            message = "로컬 Qwen이 파일 초안을 작성 중입니다."
            if number > 1:
                message = f"로컬 Qwen이 파일 초안을 다시 작성 중입니다. ({number}/{limit}회)"
            self._set("working", message, plan=plan, forecast=forecast, recovering=False)
            try:
                generation = self.provider.generate(
                    prompt, model_lock=OneModelLock(self.root),
                    budget=BudgetGuard(ModelBudget(max_calls=1, max_seconds=270,
                        max_context_tokens=context, max_output_bytes=_OUTPUT_LIMIT)),
                    allow_generation=True, structured=True, structured_tokens=output_tokens,
                    # A bounded warm model avoids repeated HDD model loads across
                    # sequential SWU drafts. Standalone requests still unload immediately.
                    keep_alive_seconds=90 if queue and request.item else 0,
                )
                if generation.untrusted is not True:
                    raise DraftError("Qwen 초안의 출처를 확인할 수 없습니다.")
                reply = (_apply_model_edits(generation.text, originals, fragments)
                         if fragments is not None else generation.text)
                summary, files = _model_files(reply, originals)
                if request.item and any(file["syntax"].endswith("문법 확인 필요") for file in files):
                    raise _DraftOutputError("Qwen 초안의 소스·설정 구문 검사에 실패했습니다.", "DRAFT_SYNTAX")
                sample = kind, int((monotonic() - model_started) * 1000)
                return summary, files, evidence, sample
            except (ProviderHold, _DraftOutputError) as exc:
                code = (exc.detail or exc.code) if isinstance(exc, ProviderHold) else exc.code
                if not request.item or code not in RECOVERY_ACTIONS:
                    raise
                self._record_failure(queue, request.item, code, number)
                if number == limit:
                    raise
                if self.advisor.configured:
                    self._set("working", f"Gemini에 복구 방법을 확인 중입니다. ({number}/{limit}회 실패)",
                              forecast=None, recovering=True)
                advice = self.advisor.advise(code, number)
                choices = RECOVERY_ACTIONS[code]
                accepted = advice in choices
                action = advice if accepted else choices[0]
                self._record_failure(queue, request.item, code, number, action=action,
                                     advisor="gemini" if accepted else "local")
                if action == "compact" and not compact and prepared:
                    prompt, fragments, evidence = _handoff_prompt(
                        prepared.task, prepared.documents, originals, prepared.source_docs, plan["narrowed"],
                        replies=request.replies, compact=True,
                    )
                    compact = True
                if code in {"OLLAMA_UNAVAILABLE", "MODEL_BUSY"}:
                    self._set("working", "로컬 Qwen 연결을 잠시 기다린 뒤 재시도합니다.",
                              forecast=None, recovering=True)
                    sleep(number * 5)
        raise RuntimeError("draft attempt limit exhausted")

    def _record_failure(self, queue: _WorkQueue, item: HandoffTask, code: str, number: int, *,
                        action: str = "", advisor: str = "") -> None:
        with self._lock:
            previous = queue.recovery.get(item.key, {})
            queue.recovery[item.key] = {**previous, "code": code, "failed_attempts": number,
                                        "limit": MAX_DRAFT_ATTEMPTS}
            if action:
                queue.recovery[item.key].update(action=action, advisor=advisor)
            self._checkpoint_locked()

    def _inspect_item(self, item: HandoffTask, queue: _WorkQueue) -> None:
        plan = queue.baseline.plan
        if queue.evidence_reader is None:
            queue.evidence_reader = PinnedEvidence(queue.baseline.scope.repository, plan["revision"])
        try:
            report = queue.evidence_reader.inspect(item)
        except (DraftError, OSError, ValueError, RecursionError):
            report = {"revision": plan["revision"], "state": "limited", "files": [],
                      "notes": ["자료를 읽는 중 오류가 발생했습니다."], "remaining": "실행 검증"}
        ci = queue.evidence_reader.current_ci
        if ci is not None:
            plan = {**plan, "baseline_ci": ci, "ci_unavailable": False}
        count = len(queue.inspections.keys() | {item.key})
        message = f"{count}개 파트의 읽기 검사 결과를 기록했습니다."
        self._set("ready", message, plan=plan, inspection=report)

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
