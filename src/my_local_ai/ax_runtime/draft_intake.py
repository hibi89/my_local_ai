"""Extract repository, document and file references from a pasted task."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import PurePosixPath
import re

from ..contracts.task import safe_path
from .draft_documents import (
    DraftDocument, DraftError, github_path_info, read_document, read_github_file,
    resolve_github_revision,
)


_NAME = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}"
_REPO = rf"{_NAME}/{_NAME}"
_REPO_REF = re.compile(rf"(?<![\w/])({_REPO})@([A-Za-z0-9_.+/-]+)")
_REPO_HINT = re.compile(rf"(?:GitHub|repo(?:sitory)?|깃헙|깃허브|저장소)[ \t:：`]+({_REPO})(?![\w./-])", re.I)
_URL = re.compile(r"https://(?:github\.com|raw\.githubusercontent\.com)/[^\s<>`\"'()\[\]]+", re.I)
_DOC = re.compile(r"(?<![\w./])(?:[\w.-]+/)*[\w.-]+\.(?:md|txt|rst|adoc|json|ya?ml|toml)(?![\w./-])", re.I)
_PATH = re.compile(r"(?<![\w./\\])(?:[\w.-]+/)+(?:[\w.-]+\.[\w-]+|\*{1,2}(?:\.[\w-]+)?)(?![\w./-])")
_HEADING = re.compile(r"^\s*#{1,6}\s+(.+)")
_FIELD = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*)?([^:：*]+?)(?:\*\*)?[:：][ \t]*(?:\*\*)?(.+)$")
_READ = re.compile(r"정본|참조 문서|읽을 문서|참고 문서|sources? to read|references?", re.I)
_ALLOW = re.compile(r"수정\s*허용|편집\s*허용|허용\s*(?:경로|파일)|allowed\s+(?:paths|files)", re.I)
_EXCLUDE = re.compile(r"제외|수정\s*금지|건드리지|변경\s*금지|do not edit|excluded", re.I)
_TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt", ".sql", ".go", ".rs",
    ".java", ".cs", ".c", ".cpp", ".h", ".svelte", ".vue", ".swift", ".kt", ".sh", ".ps1",
}
_PRIVATE_NAMES = {"secrets", "credentials", "tokens", "certificate", "private_key"}


def text_path(path: str) -> str:
    try:
        safe_path(path)
        leaf = PurePosixPath(path)
        if (leaf.suffix.lower() not in _TEXT_EXTENSIONS
            or any(part.casefold().split(".")[0] in _PRIVATE_NAMES
                   or part.startswith(".") for part in leaf.parts)):
            raise ValueError
    except ValueError:
        raise DraftError("작업 파일에는 프로젝트 안의 일반 텍스트 소스 상대 경로를 넣으세요.") from None
    return path


@dataclass(frozen=True)
class DocumentRef:
    value: str
    repository: str = ""
    branch: str = ""


@dataclass(frozen=True)
class Handoff:
    repository: str
    branch: str
    documents: tuple[DocumentRef, ...]
    paths: tuple[str, ...]
    mentioned: tuple[str, ...]
    allowed: tuple[str, ...]
    excluded: tuple[str, ...]
    workspace: str

    def permits(self, path: str) -> bool:
        return (not self.allowed or any(fnmatchcase(path, rule) for rule in self.allowed)) and all(
            not fnmatchcase(path, rule) for rule in self.excluded
        )

    def pick_file(self, files: dict[str, int], intent: str, documents: list[DraftDocument]) -> str:
        candidates = []
        tokens = set(re.findall(r"[A-Za-z0-9]+", intent.casefold()))
        mentioned = set(self.mentioned)
        referenced = {path for document in documents for path in _PATH.findall(document.text)}
        for path, size in files.items():
            if not size or not self.permits(path):
                continue
            try:
                leaf = PurePosixPath(text_path(path))
            except DraftError:
                continue
            if leaf.name in ("__init__.py", "__main__.py") or leaf.suffix in (".md", ".txt"):
                continue
            name_words = set(re.findall(r"[a-z0-9]+", leaf.stem.casefold()))
            matches = len((name_words - {"test", "tests", "index", "main", "app"}) & tokens)
            exact = path in self.allowed or path in mentioned
            if not (self.allowed or exact or matches or path in referenced):
                continue
            candidates.append((-int(exact), -matches, path not in referenced, leaf.parts[0] == "tests", size, path))
        if not candidates:
            raise DraftError("저장소에서 작업 파일을 좁히지 못했습니다. 메시지에 ‘작업 파일: src/파일명.py’를 적어 주세요.")
        return min(candidates)[-1]


def parse_handoff(message: str) -> Handoff:
    repository = branch = workspace = ""
    scoped = reading = excluding = False
    reference_repo = reference_branch = ""
    documents = []
    paths, mentioned, allowed, excluded = [], [], [], []
    repository_links: dict[str, str] = {}
    document_repos: dict[str, str] = {}
    for line in message.splitlines():
        heading = _HEADING.match(line)
        if heading:
            reading = bool(_READ.search(heading[1]))
            excluding = bool(_EXCLUDE.search(heading[1]))
            reference_repo = reference_branch = ""
            scoped = False
        field = _FIELD.match(line)
        if field:
            key, value = field[1].strip().casefold(), field[2].strip().strip("`\"")
            if key in ("repository", "repo", "저장소", "github 저장소", "깃허브 저장소"):
                hit = re.fullmatch(_REPO, value)
                if hit:
                    if repository and repository != hit[0]:
                        raise DraftError("작업 대상 GitHub 저장소를 하나만 적어 주세요.")
                    repository = hit[0]
            elif key in ("branch", "브랜치", "작업 브랜치"):
                if branch and branch != value:
                    raise DraftError("작업 브랜치를 하나만 적어 주세요.")
                branch = value
            elif key in ("workspace", "로컬 폴더", "기존 작업 폴더", "작업 폴더"):
                workspace = value
            elif key in ("작업 파일", "대상 파일", "target files", "target file", "files"):
                paths.extend(text_path(part.strip().strip("`\""))
                             for part in re.split(r"\s*[,;]\s*|\s+", field[2].strip()) if part)
                continue
        if _ALLOW.search(line) and (line.rstrip().endswith((":", "：")) or heading or _PATH.search(line)):
            scoped = True
        if scoped and not line.strip() and allowed:
            scoped = False
        for match in _URL.finditer(line):
            url = match[0].rstrip(".,:;!?。")
            repo, parts = github_path_info(url)
            if not parts or (parts[0] == "tree" and len(parts) > 1):
                repository_links[repo] = "/".join(parts[1:])
            elif parts[0] in ("blob", "issues") or url.startswith("https://raw.githubusercontent.com/"):
                documents.append(DocumentRef(url))
                document_repos[repo] = ""
        plain = _URL.sub("", line)
        ref = _REPO_REF.search(plain)
        if ref:
            reference_repo, reference_branch = ref.groups()
            if not reading:
                repository_links[reference_repo] = reference_branch
        elif repository_hint := _REPO_HINT.search(plain):
            repository_links.setdefault(repository_hint[1], "")
        doc_line = reading or bool(re.search(r"읽[고어을기]|참고|read\b|(?:설계도|작업지시문|blueprint)\s*[:：]", plain, re.I))
        names = _PATH.findall(plain)
        if not heading and (excluding or _EXCLUDE.search(plain)):
            excluded.extend(names)
        elif scoped:
            allowed.extend(names)
        elif doc_line:
            documents.extend(DocumentRef(doc[0], reference_repo, reference_branch) for doc in _DOC.finditer(plain))
            mentioned.extend(name for name in names if not _DOC.fullmatch(name) and "*" not in name)
        elif not heading:
            mentioned.extend(name for name in names if "*" not in name and not _DOC.fullmatch(name))

    candidates = repository_links or document_repos
    if not repository and len(candidates) > 1:
        raise DraftError("여러 GitHub 저장소가 있습니다. ‘Repository: 소유자/저장소’로 작업 대상을 적어 주세요.")
    repository = repository or next(iter(candidates), "")
    branch = branch or repository_links.get(repository, "")
    if not repository and (documents and any(doc.repository for doc in documents) or branch):
        raise DraftError("GitHub 작업 저장소 주소를 함께 넣어 주세요.")
    return Handoff(repository, branch, tuple(dict.fromkeys(documents)), tuple(dict.fromkeys(paths)),
                   tuple(dict.fromkeys(mentioned)), tuple(dict.fromkeys(allowed)),
                   tuple(dict.fromkeys(excluded)), workspace)


def read_handoff_documents(handoff: Handoff) -> tuple[str, list[DraftDocument]]:
    if len(handoff.documents) > 12:
        raise DraftError("한 작업에 읽을 GitHub 문서를 최대 12개로 좁혀 주세요.")
    refs = {}
    links = {}
    linked_revisions = set()
    for ref in handoff.documents:
        if ref.value.startswith("https://"):
            document = read_document(ref.value, refs)
            links[ref.value] = document
            if document.revision and github_path_info(ref.value)[0] == handoff.repository:
                linked_revisions.add(document.revision)
    if handoff.branch or not linked_revisions:
        revision = resolve_github_revision(handoff.repository, handoff.branch, refs) if handoff.repository else ""
    elif len(linked_revisions) == 1:
        revision = linked_revisions.pop()
    else:
        raise DraftError("같은 저장소의 여러 버전이 있습니다. 메시지에 작업 브랜치를 적어 주세요.")
    if handoff.repository and not revision:
        raise DraftError("작업 브랜치를 찾을 수 없습니다. 브랜치 이름과 GitHub 읽기 권한을 확인하세요.")

    requests = []
    previous_dirs = {}
    for ref in handoff.documents:
        if ref.value in links:
            requests.append((links[ref.value], "", "", ""))
            continue
        repository = ref.repository or handoff.repository
        if not repository:
            raise DraftError(f"{ref.value} 문서를 읽을 GitHub 저장소 주소를 함께 적어 주세요.")
        pinned = resolve_github_revision(repository, ref.branch, refs) if ref.repository else revision
        if not pinned:
            raise DraftError(f"참조 저장소의 브랜치를 찾을 수 없습니다. {repository}")
        folder, _, name = ref.value.rpartition("/")
        key = (repository, pinned)
        sibling = f"{previous_dirs[key]}/{name}" if not folder and key in previous_dirs else ""
        if folder:
            previous_dirs[key] = folder
        requests.append((ref.value, repository, pinned, sibling))

    def read_one(request):
        path, repository, pinned, sibling = request
        if isinstance(path, DraftDocument):
            return path
        document = read_github_file(repository, pinned, path, allow_missing=True)
        if document is None and sibling:
            document = read_github_file(repository, pinned, sibling, allow_missing=True)
        if document is None:
            raise DraftError(f"GitHub에서 {path}를 찾지 못했습니다. 문서 경로와 읽기 권한을 확인하세요.")
        return document

    with ThreadPoolExecutor(max_workers=4) as pool:
        documents = list(pool.map(read_one, requests))
    return revision, list(dict.fromkeys(documents))
