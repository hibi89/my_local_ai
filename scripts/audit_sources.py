"""Read-only source provenance audit; default offline, optional pinned public GitHub GET.

Never copies original source into MLA and never approves reuse or a license.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

PINNED = {
    "hibi89/EAI": ("feature/kmong-eai-85-p31-20261112", "5186cb1aa7928054d56b1cd0a40ea5943a5b3892"),
    "hibi89/Freelancer": ("tools/ax-dev-factory-local", "5ab94180471c7ea86344b691fc77ad5c29989071"),
}
SHA = re.compile(r"[0-9a-f]{40}\Z")
SOURCE_TREE_EVIDENCE = {
    "hibi89/EAI": {"tree_sha": "0144655d7e7fd837e9f5efef7d91d5c489467f48", "entry_count": 191, "candidate_files": {"eai/decision_engine.py":"119d112d7d756dc320adfcda9e12214b6c534fb2","eai/resource_schedule.py":"1324f96da2f20ded0c2903bc24e3619537c72f4c"}},
    "hibi89/Freelancer": {"tree_sha": "abbf9dd919f91f1b6e9566e7d582988c6ba32b73", "entry_count": 123, "candidate_files": {"axdev/core.py":"c4fc2f4c5f5547e7225566a1baa9ee0e3ccada07","axdev/opencode_guard.py":"170478dd45e97f809ed11085b295f9528005df2f","axdev/windows_sandbox_runtime.py":"421951b3658a7f72e2889ded6a54c1f5bfacb02f"}},
}
PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")

def _unique_pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("duplicate JSON field")
        out[k] = v
    return out

def audit_manifest(raw: str) -> dict:
    data = json.loads(raw, object_pairs_hook=_unique_pairs)
    if not isinstance(data, dict) or data.get("version") != 1 or type(data["version"]) is not int:
        raise ValueError("unsupported manifest version")
    if data.get("repository") != "hibi89/my_local_ai" or data.get("policy") != "NO_COPY_UNTIL_LICENSE_AND_OWNER_REVIEW":
        raise ValueError("unsupported provenance policy")
    sources = data.get("sources")
    if not isinstance(sources, list) or len(sources) != 2:
        raise ValueError("expected exactly two pinned sources")
    found = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("invalid source")
        name = source.get("source_repo")
        if name not in PINNED or name in found:
            raise ValueError("unexpected or duplicate source")
        found.add(name)
        if (source.get("source_branch"), source.get("commit_sha")) != PINNED[name]:
            raise ValueError("revision drift")
        if source.get("root_license") != "NOT_FOUND_AT_PINNED_ROOT" or source.get("third_party_notice") != "NOT_REVIEWED" or source.get("ownership_review") != "PENDING":
            raise ValueError("license state must remain unresolved until new evidence")
        snapshot = source.get("full_tree_snapshot")
        expected = SOURCE_TREE_EVIDENCE[name]
        if (not isinstance(snapshot, dict) or set(snapshot) != {
            "tree_sha", "entry_count", "tree_listing_truncated",
            "filename_license_notice_hits", "scan_scope"
        } or snapshot["tree_sha"] != expected["tree_sha"]
            or type(snapshot["entry_count"]) is not int
            or snapshot["entry_count"] != expected["entry_count"]
            or snapshot["tree_listing_truncated"] is not False
            or snapshot["filename_license_notice_hits"] != []
            or snapshot["scan_scope"] != "PINNED_RECURSIVE_TREE_FILE_NAMES_ONLY"):
            raise ValueError("pinned full-tree filename audit mismatch")
        files = source.get("candidate_files")
        if not isinstance(files, list) or not files:
            raise ValueError("missing candidate files")
        visited = set()
        for file in files:
            if not isinstance(file, dict) or set(file) != {"path", "blob_sha"}:
                raise ValueError("candidate file schema")
            path, blob = file["path"], file["blob_sha"]
            if not isinstance(path, str) or not PATH.fullmatch(path) or any(s in (".", "..") for s in path.split("/")) or path in visited:
                raise ValueError("invalid or duplicate file path")
            if not isinstance(blob, str) or not SHA.fullmatch(blob):
                raise ValueError("invalid blob sha")
            if expected["candidate_files"].get(path) != blob:
                raise ValueError("candidate blob is not pinned")
            visited.add(path)
        if set(visited) != set(expected["candidate_files"]):
            raise ValueError("candidate inventory drift")
    if data.get("imports") != [] or data.get("import_decision") != "BLOCKED_PROVENANCE":
        raise ValueError("source import must remain blocked")
    return {
        "status": "BLOCKED_PROVENANCE",
        "sources_pinned": len(found),
        "candidate_files_pinned": sum(len(s["candidate_files"]) for s in sources),
        "source_imports": 0,
        "remote_live_sha_verified": False,
        "license_cleared": False,
    }


# Optional source-tree verification is an explicit PUBLIC GitHub read-only
# operation. It does not submit plan/source files, tokens, user prompts,
# credentials, or local source to any remote. The default remains offline.
# A correct SHA/tree or absent LICENSE is NOT legal re-use permission.
_GITHUB_HOST = "api.github.com"
_HTTP_LIMIT = 2_000_000
_LICENSE_NAME = re.compile(
    r"(?:LICENSE|LICENCE|NOTICE|COPYING|COPYRIGHT)(?:[._-].*)?\Z", re.I
)


def _get_public_github_json(repo: str, suffix: str) -> object:
    if repo not in PINNED or not isinstance(suffix, str):
        raise ValueError("public pinned repository only")
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, build_opener, HTTPHandler, HTTPSHandler, HTTPRedirectHandler
    from urllib.parse import urlsplit

    # Prevent transparent redirects to unapproved hosts or signed URLs.
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise ValueError("unapproved redirect from pinned GitHub API")

    path = "/repos/" + repo + "/" + suffix
    if not re.fullmatch(
        r"(?:git/commits/[0-9a-f]{40}|git/trees/[0-9a-f]{40}\?recursive=1|branches/[A-Za-z0-9_./-]{1,128})",
        suffix,
    ):
        raise ValueError("unapproved GitHub API path")
    if suffix.startswith("branches/"):
        branch = suffix[len("branches/"):]
        if (".." in branch or "//" in branch
            or branch.startswith((".", "-", "/"))
            or branch.endswith((".", "/"))):
            raise ValueError("unsafe source branch")
    url = "https://" + _GITHUB_HOST + path
    if urlsplit(url).hostname != _GITHUB_HOST:
        raise ValueError("unapproved source API host")
    opener = build_opener(NoRedirect(), HTTPHandler(), HTTPSHandler())
    req = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "mla-public-source-audit/1",
    }, method="GET")
    try:
        with opener.open(req, timeout=8) as response:
            if response.status != 200:
                raise ValueError("GitHub source API unavailable")
            reported = response.headers.get("Content-Length")
            if reported is not None and int(reported) > _HTTP_LIMIT:
                raise ValueError("source API result too large")
            raw = response.read(_HTTP_LIMIT + 1)
            if len(raw) > _HTTP_LIMIT:
                raise ValueError("source API result too large")
    except (HTTPError, URLError, OSError, TimeoutError, OverflowError) as exc:
        raise ValueError("pinned source API unavailable") from None
    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite source JSON")),
        )
    except (UnicodeError, json.JSONDecodeError, TypeError):
        raise ValueError("untrusted source API response") from None


def audit_live_pinned_github(raw_manifest: str, *,
                             fetch_json=None) -> dict:
    """Fetch immutable GitHub commits/trees and report exact rights HOLD.

    A network failure or branch drift cannot switch license status to PASS.
    Unknown files, rewritten blobs and incomplete trees fail shut. This
    verifies public source identity, NOT source ownership or code license.
    """
    static = audit_manifest(raw_manifest)
    data = json.loads(raw_manifest, object_pairs_hook=_unique_pairs)
    fetch = fetch_json or _get_public_github_json
    if not callable(fetch):
        raise ValueError("invalid pinned-source fetch port")
    sources = []
    for source in sorted(data["sources"], key=lambda x: x["source_repo"]):
        repo, branch, commit_sha = (source["source_repo"],
                                   source["source_branch"],source["commit_sha"])
        pinned = SOURCE_TREE_EVIDENCE[repo]
        try:
            commit = fetch(repo, "git/commits/" + commit_sha)
            tree = fetch(repo, "git/trees/" + pinned["tree_sha"] + "?recursive=1")
            current = fetch(repo, "branches/" + branch)
        except Exception:
            # Treat unavailable remote evidence as a HOLD; do not silently
            # reuse last-run GitHub metadata as a fresh live readback.
            sources.append({
                "source_repo":repo, "pinned_commit_verified":False,
                "pinned_tree_verified":False, "live_branch_matches_pin":False,
                "status":"HOLD_REMOTE_EVIDENCE_UNAVAILABLE",
            })
            continue
        if (not isinstance(commit, dict) or commit.get("sha") != commit_sha
            or not isinstance(commit.get("tree"), dict)
            or commit["tree"].get("sha") != pinned["tree_sha"]
            or not isinstance(tree, dict) or tree.get("sha") != pinned["tree_sha"]
            or tree.get("truncated") is not False
            or not isinstance(tree.get("tree"), list)
            or len(tree["tree"]) != pinned["entry_count"]):
            raise ValueError("pinned GitHub source commit/tree mismatch")
        found_paths = {}
        for entry in tree["tree"]:
            if (not isinstance(entry,dict)
                or not isinstance(entry.get("path"),str)
                or entry["path"] in found_paths
                or not isinstance(entry.get("sha"),str)
                or not SHA.fullmatch(entry["sha"])
                or entry.get("type") not in ("blob","tree")):
                raise ValueError("untrusted recursive source listing")
            found_paths[entry["path"]] = entry
        for path, blob in pinned["candidate_files"].items():
            entry = found_paths.get(path)
            if (entry is None or entry.get("type") != "blob"
                or entry.get("mode") not in ("100644","100755")
                or entry.get("sha") != blob):
                raise ValueError("pinned candidate blob mismatch")
        names = [
            path for path, entry in found_paths.items()
            if entry.get("type") == "blob" and _LICENSE_NAME.fullmatch(
                path.rsplit("/",1)[-1]
            )
        ]
        if names:
            # Filename changes are informational, not automatic clearance.
            # The frozen manifest asserted NONE, so require human re-audit.
            raise ValueError("source NOTICE/license inventory changed")
        if (not isinstance(current,dict)
            or not isinstance(current.get("commit"),dict)
            or not isinstance(current["commit"].get("sha"),str)
            or not SHA.fullmatch(current["commit"]["sha"])):
            raise ValueError("untrusted live source branch")
        matches = current["commit"]["sha"] == commit_sha
        sources.append({
            "source_repo":repo,
            "pinned_commit_verified":True,
            "pinned_tree_verified":True,
            "live_branch_matches_pin":matches,
            "status":"BLOCKED_PROVENANCE_REQUIRES_RIGHTS_REVIEW",
        })
    return {
        **static,
        "source_reads":sources,
        "remote_live_sha_verified":(
            len(sources) == 2 and
            all(s["pinned_commit_verified"] and s["pinned_tree_verified"]
                and s["live_branch_matches_pin"]
                for s in sources)
        ),
        "source_tree_verified_count":sum(
            s["pinned_tree_verified"] for s in sources
        ),
        "license_cleared":False,
        "source_imports":0,
        "status":"BLOCKED_PROVENANCE",
        "decision":"NO_SOURCE_IMPORT_UNTIL_OWNER_AND_THIRD_PARTY_RIGHTS_REVIEW",
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1] / "docs" / "IMPORT_MANIFEST.json")
    parser.add_argument("--live", action="store_true", help="Opt-in GET-only public GitHub source pin audit; cannot grant license rights")
    args = parser.parse_args()
    raw = args.manifest.read_text(encoding="utf-8")
    result = audit_live_pinned_github(raw) if args.live else audit_manifest(raw)
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
