"""Read clipboard text and GitHub documents for the local draft tool."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from hashlib import sha1, sha256
from http.client import HTTPSConnection, HTTPException
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import quote, unquote, urlsplit


DOCUMENT_LIMIT = 262_144
_API_LIMIT = 500_000
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
_REF = re.compile(r"[A-Za-z0-9_.@/+%-]{1,180}\Z")


class DraftError(ValueError):
    """An error safe to display in the local workbench."""


@dataclass(frozen=True)
class DraftDocument:
    text: str
    origin: str
    revision: str = ""

    def evidence(self, used: int) -> dict:
        return {"origin": self.origin, "revision": self.revision,
                "sha256": sha256(self.text.encode()).hexdigest(),
                "characters": len(self.text), "characters_used": used}


def _public_get(endpoint: str, accept: str) -> bytes | None:
    conn = HTTPSConnection("api.github.com", timeout=12)
    try:
        conn.request("GET", endpoint, headers={"Accept": accept, "User-Agent": "my-local-ai"})
        response = conn.getresponse()
        if response.status in (404, 409, 422):
            return None
        if response.status != 200:
            raise DraftError("GitHub 문서를 읽지 못했습니다. 주소, 로그인 권한과 API 제한을 확인하세요.")
        data = response.read(_API_LIMIT + 1)
        if len(data) > _API_LIMIT:
            raise DraftError("GitHub 문서가 너무 큽니다. 필요한 문서를 나누어 넣으세요.")
        return data
    except (OSError, HTTPException) as exc:
        raise DraftError("GitHub에 연결할 수 없습니다. 네트워크를 확인하세요.") from exc
    finally:
        conn.close()


def _github_get(endpoint: str, accept: str = "application/vnd.github+json") -> bytes | None:
    gh = (r"C:\Program Files\GitHub CLI\gh.exe" if os.name == "nt"
          else shutil.which("gh"))
    if gh and Path(gh).is_file():
        try:
            result = subprocess.run(
                [gh, "api", "--hostname", "github.com", "--method", "GET", "-H",
                 f"Accept: {accept}", endpoint],
                cwd=Path(gh).parent, stdin=subprocess.DEVNULL, capture_output=True,
                env={**os.environ, "GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1",
                     "GH_PAGER": "", "NO_COLOR": "1"},
                timeout=14, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                if len(result.stdout) > _API_LIMIT:
                    raise DraftError("GitHub 문서가 너무 큽니다. 필요한 문서를 나누어 넣으세요.")
                return result.stdout
            if re.search(rb"\bHTTP (404|409|422)\b", result.stderr):
                return None
        except (OSError, subprocess.TimeoutExpired):
            pass  # The same document may be publicly readable.
    return _public_get(endpoint, accept)


def _api_object(raw: bytes | None) -> dict:
    if raw is None:
        raise DraftError("GitHub 문서를 찾을 수 없습니다. 주소와 이 PC의 GitHub 읽기 권한을 확인하세요.")
    try:
        data = json.loads(raw)
    except (UnicodeError, ValueError, RecursionError):
        raise DraftError("GitHub 문서 응답을 읽을 수 없습니다.") from None
    if not isinstance(data, dict):
        raise DraftError("GitHub 파일 또는 이슈 한 개의 주소를 넣으세요.")
    return data


def _read_github(url: str, refs: dict[tuple[str, str], str]) -> DraftDocument:
    site = urlsplit(url)
    if (site.scheme != "https" or site.netloc not in ("github.com", "raw.githubusercontent.com")
        or len(url) > 2048):
        raise DraftError("GitHub의 HTTPS 파일 주소 또는 이슈 주소를 넣으세요.")
    bits = [unquote(part, errors="strict") for part in site.path.strip("/").split("/")]
    if (len(bits) < 3 or not all(_NAME.fullmatch(part) for part in bits[:2])
        or any(part in ("", ".", "..") or "/" in part or "\\" in part
               or any(ord(ch) < 32 for ch in part) for part in bits)):
        raise DraftError("GitHub 문서 주소 형식을 확인하세요.")
    owner, repo, *parts = bits
    root = f"/repos/{owner}/{repo}"
    origin = f"https://{site.netloc}" + site.path
    if site.netloc == "github.com":
        if len(parts) == 2 and parts[0] == "issues" and re.fullmatch(r"[0-9]{1,10}", parts[1]):
            item = _api_object(_github_get(f"{root}/issues/{parts[1]}"))
            if not isinstance(item.get("body"), str) or not item["body"].strip():
                raise DraftError("GitHub 이슈 본문이 비어 있습니다.")
            return DraftDocument(item["body"], origin)
        if not parts or parts[0] != "blob":
            raise DraftError("GitHub에서 문서를 열고 파일 주소를 복사해 주세요.")
        parts = parts[1:]
    if len(parts) < 2:
        raise DraftError("GitHub 주소에 브랜치와 파일 이름이 필요합니다.")
    ref, local_path = (parts[0], parts[1:]) if _SHA.fullmatch(parts[0]) else ("", [])
    if not ref:
        for index in range(1, min(len(parts), 9)):
            candidate = "/".join(parts[:index])
            if not _REF.fullmatch(candidate):
                raise DraftError("GitHub 브랜치 형식을 확인하세요.")
            cache_key = (root, candidate)
            if cache_key not in refs:
                raw = _github_get(f"{root}/commits/{quote(candidate, safe='')}", "application/vnd.github.sha")
                resolved = raw.decode("ascii", errors="ignore").strip() if raw else ""
                if _SHA.fullmatch(resolved):
                    refs[cache_key] = resolved
            if cache_key in refs:
                ref, local_path = refs[cache_key], parts[index:]
                break
        else:
            raise DraftError("GitHub 브랜치 또는 커밋을 찾을 수 없습니다.")
    path = "/".join(local_path)
    doc = _api_object(_github_get(f"{root}/contents/{quote(path, safe='/')}?ref={ref}"))
    if (doc.get("type") != "file" or doc.get("encoding") != "base64"
        or doc.get("path") != path or type(doc.get("size")) is not int
        or not 1 <= doc["size"] <= DOCUMENT_LIMIT or not isinstance(doc.get("content"), str)):
        raise DraftError("GitHub에서는 크기 제한 안의 텍스트 파일을 선택하세요.")
    try:
        content = base64.b64decode("".join(doc["content"].split()), validate=True)
        git_id = sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
        if doc["size"] != len(content) or doc.get("sha") != git_id:
            raise ValueError
        text = content.decode("utf-8-sig")
    except (UnicodeError, ValueError):
        raise DraftError("GitHub 파일의 UTF-8 내용 또는 해시를 확인할 수 없습니다.") from None
    return DraftDocument(text, origin, ref)


def read_document(value: str, refs: dict[tuple[str, str], str]) -> DraftDocument:
    source = value.strip()
    if source.startswith(("https://", "http://")) and not any(c.isspace() for c in source):
        try:
            result = _read_github(source, refs)
        except UnicodeError:
            raise DraftError("GitHub 문서 주소의 문자를 확인하세요.") from None
    else:
        result = DraftDocument(source, "붙여넣기")
    if "\0" in result.text or len(result.text.encode()) > DOCUMENT_LIMIT:
        raise DraftError("입력 문서는 작은 UTF-8 텍스트로 나누어 넣으세요.")
    return result
