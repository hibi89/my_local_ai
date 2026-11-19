"""Owner-invoked local source drafting. Model replies are handled as text."""
from __future__ import annotations

import ast
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
    DOCUMENT_LIMIT, DraftDocument, DraftError, github_files, read_document, read_github_file,
)
from .draft_intake import parse_handoff, read_handoff_documents, text_path
from .draft_timing import recorded_time
from .ollama_provider import OllamaProvider
from .provider_policy import ProviderHold
from .worker_lock import ModelLockUnsafe, OneModelLock


REQUEST_LIMIT = 1_800_000  # Space for JSON escaping of two UTF-8 documents.
_CONTEXT = 8192
_INPUT_LIMIT = _CONTEXT - 1536
_CHAT_INPUT_LIMIT = 10_400
_OUTPUT_LIMIT = 60_000
_KEYWORDS = re.compile(r"[A-Za-z0-9_\uac00-\ud7a3]{2,}")


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


def _design_excerpt(text: str, query: str, limit: int) -> str:
    if len(text.encode()) <= limit:
        return text
    if limit < 500:
        raise DraftError("작업명령문과 기존 파일을 줄여 모델이 설계도를 읽을 공간을 확보하세요.")
    sections = [part.strip() for part in re.split(r"\n{2,}|(?=^#{1,4} )", text, flags=re.M) if part.strip()]
    keywords = set(_KEYWORDS.findall(query.casefold()))
    ranked = sorted(range(len(sections)), key=lambda i: (
        -len(keywords.intersection(_KEYWORDS.findall(sections[i].casefold()))), i,
    ))
    selected = {}
    for index in ranked:
        if limit < 120:
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
    if len(source.encode()) <= limit:
        return source
    keywords = set(_KEYWORDS.findall(query.casefold()))
    lines = source.splitlines(keepends=True)
    best = (-1, "")
    # Score overlapping windows of whole lines so Qwen can copy exact anchors.
    for start in range(0, len(lines), 12):
        excerpt = _clip("".join(lines[start:start + 110]), limit)
        if excerpt and not excerpt.endswith("\n"):
            excerpt = excerpt.rpartition("\n")[0] + "\n" if "\n" in excerpt else ""
        score = len(keywords.intersection(_KEYWORDS.findall(excerpt.casefold())))
        if excerpt and score > best[0]:
            best = (score, excerpt)
    if not best[1]:
        raise DraftError("작업 파일에 모델이 인용할 수 있는 코드 구간을 찾지 못했습니다.")
    return best[1]


def _handoff_prompt(task: DraftDocument, documents: list[DraftDocument], originals: dict[str, str],
                    source_docs: dict[str, DraftDocument], narrowed: bool) -> tuple[str, dict | None, list]:
    priority = _first_priority(task.text)
    if len(task.text.encode()) > 3500:
        begin = _clip(task.text, 750)
        focus = _clip(priority, 1750) if priority != task.text else _design_excerpt(task.text, " ".join(originals), 1600)
        instructions = f"{begin}\n\n{focus}"
        used = len(begin) + len(focus) if priority != task.text else len(focus)
    else:
        instructions, used = task.text, len(task.text)
    query = instructions + " " + " ".join(originals)
    evidence = [task.evidence(min(used, len(task.text)))]
    encoded = json.dumps(originals, ensure_ascii=False)
    fragments = None
    selection = ("Choose one small source change that advances the first priority and is supported by the shown code. "
                 "Do not mark checks as passed or invent test or execution results.\n") if narrowed else ""
    preamble = selection + "Use the attached document excerpts as context for the change."
    if len(encoded.encode()) > 1900:
        per_file = min(3600, 3800 // len(originals))
        fragments = {path: _source_excerpt(source.replace("\r\n", "\n"), query, per_file)
                     for path, source in originals.items()}
        prompt = (
            'Return one JSON object: {"summary":"short Korean summary","edits":[{"path":"exact path",'
            '"before":"unique exact block from the excerpt, including indentation and line breaks",'
            '"after":"replacement text"}]}. Use whole lines and preserve surrounding code. '
            'For an empty file only, use an empty before and include the whole new file as after. '
            'Use only the listed paths. Return at least one edit. Do not return Markdown or commands.\n'
            + preamble + '\nWork instructions:\n' + instructions
            + '\nCurrent source excerpts:\n' + json.dumps(fragments, ensure_ascii=False)
        )
    else:
        prompt, _ = _create_prompt(instructions + "\n\n" + preamble, "", originals)
    room = _CHAT_INPUT_LIMIT - len(prompt.encode())
    if room < 0:
        raise DraftError("붙여넣은 작업과 파일을 한 번에 읽기 어렵습니다. 작업 파일을 나누어 주세요.")
    if documents:
        per_document = min(2300, room // len(documents))
        for document in documents:
            name = document.origin.split("/")[-1]
            limit = per_document - len(name.encode()) - 16
            excerpt = (_design_excerpt(document.text, query, limit) if limit >= 500
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
            or type(data["edits"]) is not list or not 1 <= len(data["edits"]) <= 8):
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
            or not 1 <= len(data["files"]) <= (len(originals) or 8)):
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
        self._started = None
        self._elapsed_ms = self._total_ms = 0
        self._timing_error = False
        self._refresh_total()

    def snapshot(self) -> dict:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> dict:
        elapsed = self._elapsed_ms if self._started is None else int((monotonic() - self._started) * 1000)
        return {**self._state, "elapsed_ms": elapsed,
                "total_ms": self._total_ms + (elapsed if self._started is not None else 0),
                "timing_saved": not self._timing_error}

    def _set(self, state: str, message: str, **values) -> None:
        with self._lock:
            self._state.update(state=state, message=message, **values)
            if state in ("done", "error"):
                self._elapsed_ms = int((monotonic() - self._started) * 1000)
                self._started = None
                self._refresh_total(self._elapsed_ms)

    def _refresh_total(self, elapsed_ms: int | None = None) -> None:
        try:
            self._total_ms = recorded_time(self.root, elapsed_ms)
            self._timing_error = False
        except (OSError, ValueError, sqlite3.Error):
            self._total_ms += elapsed_ms or 0
            self._timing_error = True

    def start(self, payload: object) -> dict:
        names = {"instructions", "blueprint", "paths", "workspace"}
        if (type(payload) is not dict or set(payload) not in (names, {"message"})
            or any(type(text) is not str or "\0" in text for text in payload.values())):
            raise DraftError("입력값의 형식을 확인하세요.")
        handoff = "message" in payload
        instruction = payload["message" if handoff else "instructions"].strip()
        design = payload.get("blueprint", "").strip()
        spec = payload.get("paths", "").strip()
        folder = payload.get("workspace", "").strip()
        if not instruction:
            raise DraftError("작업 지시를 넣으세요.")
        if folder and not spec:
            raise DraftError("기존 프로젝트를 바꿀 때는 작업할 파일 경로를 지정하세요.")
        if (any(len(value.encode()) > DOCUMENT_LIMIT for value in (instruction, design))
            or len(spec) > 3000 or len(folder) > 1024):
            raise DraftError("입력 문서나 파일 목록을 나누어 넣으세요.")
        paths = tuple(text_path(line.strip()) for line in spec.splitlines() if line.strip())
        if len(paths) > 8 or len({path.casefold() for path in paths}) != len(paths):
            raise DraftError("서로 다른 작업 파일을 한 번에 1~8개 넣으세요.")
        if folder:
            folder = folder.removeprefix('"').removesuffix('"')
            _local_absolute(folder)
        with self._lock:
            if self._state["state"] == "working":
                raise DraftError("현재 작업이 끝나면 다음 작업을 시작할 수 있습니다.")
            self._refresh_total()
            self._started = monotonic()
            self._elapsed_ms = 0
            message = "붙여넣은 지시에서 작업 자료를 찾는 중입니다." if handoff else "작업 자료를 읽는 중입니다."
            self._state = {"state": "working", "message": message}
            worker = Thread(target=self._run, args=(instruction, design, paths, folder, handoff), daemon=True)
            try:
                worker.start()
            except RuntimeError:
                self._state = {"state": "error", "message": "작업을 시작하지 못했습니다."}
                self._started = None
            return self._snapshot_locked()

    def _prepare_handoff(self, message: str) -> tuple[str, dict, dict | None, list, dict]:
        handoff = parse_handoff(message)
        plan = {"repository": handoff.repository, "branch": handoff.branch,
                "paths": list(handoff.paths), "documents": len(handoff.documents)}
        self._set("working", "작업에 필요한 문서와 원본을 읽는 중입니다.", plan=plan)
        revision, documents = read_handoff_documents(handoff)
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
        source_docs = {}
        if handoff.repository and not handoff.workspace:
            for path in paths:
                document = read_github_file(handoff.repository, revision, path, allow_missing=not narrowed)
                if document is not None:
                    source_docs[path] = document
            originals = {path: source_docs[path].text if path in source_docs else "" for path in paths}
        else:
            originals = _existing_sources(handoff.workspace, paths, self.root)
        if any(len(source.encode()) > _OUTPUT_LIMIT for source in originals.values()):
            raise DraftError("작업 파일이 로컬 초안 크기 한도를 넘었습니다. 더 작은 파일을 선택해 주세요.")
        plan = {**plan, "paths": list(paths), "revision": revision, "documents": len(documents),
                "narrowed": narrowed, "workspace": handoff.workspace}
        task = DraftDocument(message, "붙여넣은 작업 지시")
        prompt, fragments, evidence = _handoff_prompt(task, documents, originals, source_docs, narrowed)
        return prompt, originals, fragments, evidence, plan

    def _run(self, instruction: str, design: str, paths: tuple[str, ...], folder: str, handoff: bool) -> None:
        try:
            fragments = None
            plan = None
            if handoff:
                prompt, originals, fragments, evidence, plan = self._prepare_handoff(instruction)
            else:
                refs = {}
                task = read_document(instruction, refs)
                blueprint = read_document(design, refs) if design else None
                originals = _existing_sources(folder, paths, self.root)
                prompt, used = _create_prompt(task.text, blueprint.text if blueprint else "", originals)
                evidence = [task.evidence(len(task.text))]
                if blueprint:
                    evidence.append(blueprint.evidence(used))
            self._set("working", "로컬 Qwen이 파일 초안을 작성 중입니다.", plan=plan)
            context = 4096 if len(prompt.encode()) <= 2560 else _CONTEXT
            generate = self.provider.generate(
                prompt, model_lock=OneModelLock(self.root),
                budget=BudgetGuard(ModelBudget(max_calls=1, max_seconds=270,
                    max_context_tokens=context, max_output_bytes=_OUTPUT_LIMIT)),
                allow_generation=True, structured=True,
            )
            if generate.untrusted is not True:
                raise DraftError("Qwen 초안의 출처를 확인할 수 없습니다.")
            reply = _apply_model_edits(generate.text, originals, fragments) if fragments is not None else generate.text
            summary, files = _model_files(reply, originals)
            self._set("working", "변경 내용을 정리해 별도 폴더에 저장 중입니다.")
            destination = self._save(files, summary, evidence, plan)
            message = "첫 작업의 로컬 초안을 저장했습니다." if plan and plan["narrowed"] else "초안 파일을 저장했습니다."
            self._set("done", message, summary=summary,
                      folder=str(destination / "files"), files=files, sources=evidence)
        except DraftError as exc:
            self._set("error", str(exc))
        except ProviderHold as exc:
            messages = {
                "MODEL_ABSENT": "Ollama에 qwen3:4b-instruct 모델이 설치되어 있어야 합니다.",
                "OLLAMA_UNAVAILABLE": "Ollama에 연결하지 못했거나 응답 시간이 지났습니다.",
                "RESOURCE_LIMIT": "로컬 모델이 사용 중이거나 작업 한도를 넘었습니다.",
            }
            self._set("error", messages.get(exc.code, "Qwen 응답을 다시 확인해 주세요."))
        except (OSError, ValueError, OverflowError, RuntimeError, ModelLockUnsafe):
            self._set("error", "작업 자료나 초안 저장 폴더를 확인하세요.")

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
