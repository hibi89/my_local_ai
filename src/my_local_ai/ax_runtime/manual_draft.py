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
import stat
import tempfile
from threading import Lock, Thread

from ..contracts.task import safe_path
from ..state.local_files import local_path_stat, read_bounded_regular
from .budgets import BudgetGuard, ModelBudget
from .draft_documents import DOCUMENT_LIMIT, DraftError, read_document
from .ollama_provider import OllamaProvider
from .provider_policy import ProviderHold
from .worker_lock import ModelLockUnsafe, OneModelLock


REQUEST_LIMIT = 1_800_000  # Space for JSON escaping of two UTF-8 documents.
_CONTEXT = 8192
_INPUT_LIMIT = _CONTEXT - 1536
_OUTPUT_LIMIT = 60_000
_TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt", ".sql", ".go", ".rs",
    ".java", ".cs", ".c", ".cpp", ".h", ".svelte", ".vue", ".swift", ".kt", ".sh", ".ps1",
}
_PRIVATE_NAMES = {"secrets", "credentials", "tokens", "certificate", "private_key"}
_KEYWORDS = re.compile(r"[A-Za-z0-9_\uac00-\ud7a3]{2,}")


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _text_path(path: str) -> str:
    try:
        safe_path(path)
        leaf = Path(path)
        if (leaf.suffix.lower() not in _TEXT_EXTENSIONS
            or any(part.casefold().split(".")[0] in _PRIVATE_NAMES
                   or part.startswith(".") for part in leaf.parts)):
            raise ValueError
    except ValueError:
        raise DraftError("작업 파일에는 프로젝트 안의 일반 텍스트 소스 상대 경로를 넣으세요.") from None
    return path


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
            path, source = _text_path(row["path"]), row["content"]
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

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._state)

    def _set(self, state: str, message: str, **values) -> None:
        with self._lock:
            self._state = {"state": state, "message": message, **values}

    def start(self, payload: object) -> dict:
        names = {"instructions", "blueprint", "paths", "workspace"}
        if (type(payload) is not dict or set(payload) != names
            or any(type(text) is not str or "\0" in text for text in payload.values())):
            raise DraftError("입력값의 형식을 확인하세요.")
        instruction = payload["instructions"].strip()
        design = payload["blueprint"].strip()
        spec = payload["paths"].strip()
        folder = payload["workspace"].strip()
        if not instruction:
            raise DraftError("작업명령문을 넣으세요.")
        if folder and not spec:
            raise DraftError("기존 프로젝트를 바꿀 때는 작업할 파일 경로를 지정하세요.")
        if (any(len(value.encode()) > DOCUMENT_LIMIT for value in (instruction, design))
            or len(spec) > 3000 or len(folder) > 1024):
            raise DraftError("입력 문서나 파일 목록을 나누어 넣으세요.")
        paths = tuple(_text_path(line.strip()) for line in spec.splitlines() if line.strip())
        if len(paths) > 8 or len({path.casefold() for path in paths}) != len(paths):
            raise DraftError("서로 다른 작업 파일을 한 번에 1~8개 넣으세요.")
        if folder:
            folder = folder.removeprefix('"').removesuffix('"')
            _local_absolute(folder)
        with self._lock:
            if self._state["state"] == "working":
                raise DraftError("현재 작업이 끝나면 다음 작업을 시작할 수 있습니다.")
            self._state = {"state": "working", "message": "작업 자료를 읽는 중입니다."}
            worker = Thread(target=self._run, args=(instruction, design, paths, folder), daemon=True)
            try:
                worker.start()
            except RuntimeError:
                self._state = {"state": "error", "message": "작업을 시작하지 못했습니다."}
            return dict(self._state)

    def _run(self, instruction: str, design: str, paths: tuple[str, ...], folder: str) -> None:
        try:
            refs = {}
            task = read_document(instruction, refs)
            blueprint = read_document(design, refs) if design else None
            originals = _existing_sources(folder, paths, self.root)
            prompt, used = _create_prompt(task.text, blueprint.text if blueprint else "", originals)
            evidence = [task.evidence(len(task.text))]
            if blueprint:
                evidence.append(blueprint.evidence(used))
            self._set("working", "로컬 Qwen이 파일 초안을 작성 중입니다.")
            context = 4096 if len(prompt.encode()) <= 2560 else _CONTEXT
            generate = self.provider.generate(
                prompt, model_lock=OneModelLock(self.root),
                budget=BudgetGuard(ModelBudget(max_calls=1, max_seconds=270,
                    max_context_tokens=context, max_output_bytes=_OUTPUT_LIMIT)),
                allow_generation=True, structured=True,
            )
            if generate.untrusted is not True:
                raise DraftError("Qwen 초안의 출처를 확인할 수 없습니다.")
            summary, files = _model_files(generate.text, originals)
            self._set("working", "변경 내용을 정리해 별도 폴더에 저장 중입니다.")
            destination = self._save(files, summary, evidence)
            self._set("done", "초안 파일을 저장했습니다.", summary=summary,
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
        except (OSError, ValueError, OverflowError, ModelLockUnsafe):
            self._set("error", "작업 자료나 초안 저장 폴더를 확인하세요.")

    def _save(self, files: list[dict], summary: str, sources: list[dict]) -> Path:
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
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            stage.rename(target)
        return target
