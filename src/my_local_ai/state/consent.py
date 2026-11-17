"""Read-only local consent ledger. Never issues grants or accepts guest approvals.

Actual Windows protected-store/owner signer integration is pending. This module
cannot by itself prove the SQLite file is protected against an untrusted worker.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
import stat

from .migrations import APP_ID, SCHEMA_VERSION

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

def _check_safe_owned_file(path: Path) -> None:
    if path.suffix != ".sqlite3" or not path.is_file():
        raise ValueError("not an existing SQLite state")
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) & _REPARSE):
            raise ValueError("untrusted symlink/reparse")
    with path.open("rb") as f:
        head = f.read(100)
    if len(head) < 100 or head[:16] != b"SQLite format 3\x00":
        raise ValueError("not SQLite state")
    if int.from_bytes(head[68:72], "big") != APP_ID or int.from_bytes(head[60:64], "big") != SCHEMA_VERSION:
        raise ValueError("not a current My Local AI state")

class ConsentLedger:
    def __init__(self, owned_path: str | Path):
        self._path = Path(owned_path).absolute()
        _check_safe_owned_file(self._path)

    def is_live(self, grant_id: str, plan_sha256: str, scope: str) -> bool:
        """Fresh read-only lookup; revocation wins. Caller still verifies signature."""
        if not isinstance(grant_id, str) or not isinstance(plan_sha256, str) or not isinstance(scope, str):
            return False
        _check_safe_owned_file(self._path)
        uri = self._path.as_uri() + "?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True, timeout=1.0) as db:
                db.execute("PRAGMA query_only=ON")
                db.execute("PRAGMA busy_timeout=1000")
                if db.execute("PRAGMA application_id").fetchone()[0] != APP_ID:
                    return False
                matches = db.execute(
                    "SELECT state FROM owner_consents WHERE consent_id=? AND plan_sha=? AND scope=?",
                    (grant_id, plan_sha256, scope),
                ).fetchall()
                return len(matches) == 1 and matches[0][0] == "APPROVED"
        except (OSError, sqlite3.Error, ValueError):
            return False
