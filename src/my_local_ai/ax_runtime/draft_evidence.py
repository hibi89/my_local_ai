"""Inspect sources and existing CI records pinned to the workbench queue's commit."""
from __future__ import annotations

import ast
import json
from pathlib import PurePosixPath
import re
import tomllib

from .draft_documents import DraftDocument, DraftError, github_files, read_github_ci, read_github_file
from .draft_intake import HandoffTask, text_path


_TOPICS = (
    (r"actions|workflow|워크플로", "actions", (), "승인된 환경에서의 수동 워크플로 실제 실행과 결과 확인"),
    (r"\bcli\b|통합\s*검증|backend integration", "cli", ("cli", "oracle", "acceptance", "contract", "integration"),
     "통합·회귀 테스트 실제 실행"),
    (r"github.*소스|read.only source|source acquisition", "source", ("github", "snapshot", "source", "discovery"),
     "소스 수집과 장애 응답을 실행 환경에서 확인"),
    (r"감시|\bwatch", "watch", ("watch", "recovery", "snapshot"),
     "감시와 장애 복구의 실제 동작 확인"),
    (r"저장|원본 보호|storage|recovery", "storage", ("output", "history", "registry", "recover", "atomic", "lock"),
     "동시 실행, 중단 및 복구 시험"),
    (r"종합|보안 검증|기술.*검증|regression|security", "suite", ("security", "acceptance", "integration", "safety"),
     "전체 테스트와 독립 기술 검증"),
)
_WORKFLOW = re.compile(r"\.github/workflows/[\w.-]+\.ya?ml\Z", re.ASCII)
_DISPATCH = re.compile(r"(?m)^(?:[ \t]*workflow_dispatch[ \t]*:|on[ \t]*:[ \t]*(?:workflow_dispatch\b|\[[^\r\n]*\bworkflow_dispatch\b))")
_CODE_PATH = re.compile(r"(?<![\w./])(?:src|tests)/[A-Za-z0-9_./-]+\.(?:py|json|toml)\b")
_INSPECTABLE = (".py", ".json", ".toml")


class PinnedEvidence:
    def __init__(self, repository: str, revision: str):
        self.repository = repository
        self.revision = revision
        self._inventory: dict[str, int] | None = None
        self._inventory_unavailable = False
        self._files: dict[str, dict] = {}
        self._ci: dict | None = None

    @property
    def current_ci(self) -> dict | None:
        return self._ci or None

    def _paths(self, item: HandoffTask, topic: str, keywords: tuple[str, ...]) -> list[str]:
        paths = self._inventory or {}
        if topic == "actions":
            workflows = [path for path in paths if _WORKFLOW.fullmatch(path)]
            return sorted(workflows, key=lambda path: ("audit" not in path, path))[:4]
        named = set(_CODE_PATH.findall(item.detail))
        candidates = []
        for path in paths:
            if not path.startswith(("src/", "tests/")) or not path.endswith(_INSPECTABLE):
                continue
            try:
                text_path(path)
            except DraftError:
                continue
            stem = PurePosixPath(path).stem.casefold()
            if stem == "__init__":
                continue
            relevance = sum(2 if stem == word else 1 for word in keywords if word in stem or word in path.casefold())
            if relevance or path in named:
                candidates.append((path not in named, -relevance, path))
        ranked = [path for _, _, path in sorted(candidates)]
        sources = [path for path in ranked if path.startswith("src/")]
        tests = [path for path in ranked if path.startswith("tests/")]
        manifest = ["pyproject.toml"] if topic == "suite" and "pyproject.toml" in paths else []
        return manifest + sources[:1] + tests[:2]

    def _file(self, path: str) -> dict:
        if path not in self._files:
            try:
                document = read_github_file(self.repository, self.revision, path)
                if document is None:
                    raise DraftError("파일을 읽지 못했습니다.")
                entry = _describe_file(path, document)
            except DraftError:
                entry = {"path": path, "observed": False, "result": "파일 읽기 실패"}
            self._files[path] = entry
        return self._files[path]

    def inspect(self, item: HandoffTask) -> dict:
        topic, keywords, requirement = next(
            ((topic, words, need) for pattern, topic, words, need in _TOPICS if re.search(pattern, item.title, re.I)),
            ("general", (), "작업 결과의 실제 동작 검증"),
        )
        if self._inventory is None and not self._inventory_unavailable:
            try:
                self._inventory = github_files(self.repository, self.revision)
            except DraftError:
                self._inventory_unavailable = True
        checks = [self._file(path) for path in self._paths(item, topic, keywords)]
        notes = []
        if self._inventory_unavailable:
            notes.append("기준 커밋의 파일 목록을 읽지 못했습니다.")
        elif not checks:
            notes.append("기준 커밋의 파일 목록을 조회했습니다. 이 파트의 검사 대상을 찾을 단서가 부족합니다.")
        if topic in ("actions", "suite"):
            if self._ci is None:
                try:
                    self._ci = read_github_ci(self.repository, self.revision)
                except DraftError:
                    self._ci = {}
            if "runs" in self._ci:
                runs = self._ci["runs"]
                if topic == "actions":
                    runs = [run for run in runs if run.get("event") == "workflow_dispatch"]
                label = "수동 실행" if topic == "actions" else "CI 실행"
                notes.append(f"이 기준 커밋에서 확인한 {label} 기록 {len(runs)}건")
            else:
                notes.append("이 기준 커밋의 CI 기록을 조회하지 못했습니다.")
        hours = item.observation_hours()
        if hours:
            window = str(hours[0]) if hours[0] == hours[1] else f"{hours[0]}~{hours[1]}"
            requirement += f"과 {window}시간 실측"
        readable = any(check["observed"] for check in checks) or topic in ("actions", "suite") and bool(self._ci)
        return {"revision": self.revision, "state": "observed" if readable else "limited",
                "files": checks, "notes": notes, "remaining": requirement}


def _describe_file(path: str, document: DraftDocument) -> dict:
    result = "파일 읽기 확인"
    try:
        if path.endswith(".py"):
            tree = ast.parse(document.text, filename=path)
            result = "Python 구문 확인"
            if path.startswith("tests/"):
                tests = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
                            for node in ast.walk(tree))
                result += f" · 테스트 정의 {tests}개"
        elif path.endswith(".toml"):
            tomllib.loads(document.text)
            result = "TOML 구문 확인"
        elif path.endswith(".json"):
            json.loads(document.text)
            result = "JSON 구문 확인"
        elif _WORKFLOW.fullmatch(path):
            result = "워크플로 파일 읽음"
            if _DISPATCH.search(document.text):
                result += " · 수동 실행 선언 발견"
    except (SyntaxError, ValueError, RecursionError) as exc:
        line = getattr(exc, "lineno", 0)
        result = "구문 확인 실패" + (f" · {line}행" if line else "")
    return {"path": path, "result": result, "observed": True, "sha256": document.evidence(0)["sha256"]}
