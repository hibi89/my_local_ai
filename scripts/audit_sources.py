"""Offline, read-only source provenance audit (no Git/network/file copying)."""
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

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1] / "docs" / "IMPORT_MANIFEST.json")
    args = parser.parse_args()
    result = audit_manifest(args.manifest.read_text(encoding="utf-8"))
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
