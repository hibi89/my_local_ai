"""Read-only local consent ledger. Never issues grants or accepts guest approvals.

Actual Windows protected-store/owner signer integration is pending. This module
cannot by itself prove the SQLite file is protected against an untrusted worker.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing as _closing
from pathlib import Path
import stat

from .migrations import APP_ID, SCHEMA_VERSION

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

def _check_safe_owned_file(path: Path) -> tuple[int, int, int, int]:
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
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
        or getattr(info, "st_file_attributes", 0) & _REPARSE):
        raise ValueError("state must be a unique regular file")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)

def _safe_sidecar_identity(path: Path) -> tuple[tuple[str, int, int, int, int], ...]:
    """Check WAL and SHM alongside the owner DB, not just its main inode.

    A symlinked WAL can spoof current consent even when the main DB is pinned.
    Both sidecar files must be ordinary unique local files if present.
    """
    result = []
    for suffix in ("-wal", "-shm"):
        sibling = Path(str(path) + suffix)
        try:
            info = sibling.lstat()
        except FileNotFoundError:
            continue
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & _REPARSE):
            raise ValueError("unsafe SQLite sidecar")
        result.append((suffix, info.st_dev, info.st_ino,
                       info.st_size, info.st_mtime_ns))
    return tuple(result)


class ConsentLedger:
    def __init__(self, owned_path: str | Path):
        self._path = Path(owned_path).absolute()
        # Pin the inode/file-id at ledger creation. A replacement at the same
        # pathname is NEVER the same protected grant store even if old WAL
        # sidecars make it appear to contain prior approved rows.
        identity = _check_safe_owned_file(self._path)
        self._origin_identity = identity[:2]

    def is_live(self, grant_id: str, plan_sha256: str, scope: str) -> bool:
        """Fresh read-only lookup; revocation wins. Caller still verifies signature."""
        # Other scopes need per-action grant replay protection and are HOLD.
        if (scope != "LOCAL_PLAN" or not isinstance(grant_id, str)
            or not isinstance(plan_sha256, str) or len(grant_id) > 128
            or len(plan_sha256) != 64):
            return False
        try:
            before = _check_safe_owned_file(self._path)
            if before[:2] != self._origin_identity:
                return False
            sidecars_before = _safe_sidecar_identity(self._path)
            uri = self._path.as_uri() + "?mode=ro"
            # sqlite3.Connection.__exit__ commits/rolls back but does NOT
            # close the connection. Explicit closing releases read locks,
            # DB/WAL handles and potential resource leakage on every path.
            with _closing(sqlite3.connect(uri, uri=True, timeout=1.0)) as db:
                db.execute("PRAGMA query_only=ON")
                db.execute("PRAGMA busy_timeout=1000")
                if (db.execute("PRAGMA application_id").fetchone()[0] != APP_ID
                    or db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION):
                    return False
                # SQLite data_version changes on commits by OTHER
                # connections. Check it before and after the read as a second
                # revocation-race signal; absence of change is not OS trust.
                version_before = db.execute("PRAGMA data_version").fetchone()[0]
                matches = db.execute(
                    "SELECT state FROM owner_consents WHERE consent_id=? AND plan_sha=? AND scope=?",
                    (grant_id, plan_sha256, scope),
                ).fetchall()
                version_after = db.execute("PRAGMA data_version").fetchone()[0]
            # Detect file replacement or mutation during a consent decision.
            # This is defense in depth, NOT a substitute for protected ACLs.
            after = _check_safe_owned_file(self._path)
            sidecars_after = _safe_sidecar_identity(self._path)
            # Reject any WAL file added/replaced/appended during the read,
            # including a same-inode WAL modification (possible revocation).
            # Query-only SQLite may create a new -shm reader index; permit
            # this *only* when a stable WAL already existed at the start.
            # The before/after identity tuples include size and mtime_ns,
            # not just device/inode. Guest-writable ACLs remain untrusted.
            side_before = {entry[0]: entry[1:] for entry in sidecars_before}
            side_after = {entry[0]: entry[1:] for entry in sidecars_after}
            existing_sidecars_stable = all(
                side_after.get(suffix) == identity
                for suffix, identity in side_before.items()
            )
            new_sidecars = set(side_after) - set(side_before)
            allowed_shm_creation = (
                not new_sidecars
                or (new_sidecars == {"-shm"} and "-wal" in side_before)
            )
            return (
                before == after
                and existing_sidecars_stable
                and allowed_shm_creation
                and type(version_before) is int
                and version_before == version_after
                and len(matches) == 1
                and matches[0][0] == "APPROVED"
            )
        except (OSError, sqlite3.Error, ValueError):
            return False


# SWU-008: owner-consent inspection adapter. A valid MAC only means the
# supplied key can validate the claim. It does not prove protected OS key
# custody, a separate principal, or current P2/owner execution approval.
from dataclasses import dataclass as _dataclass
from my_local_ai.contracts.approval import (
    OwnerGrant as _OwnerGrant, authorize_claim as _authorize_claim,
)


@_dataclass(frozen=True)
class OwnerConsentInspection:
    """Read-only scope and live-store inspection with no minted capability."""

    grant_id: str
    plan_sha256: str
    source_sha: str
    scope: str
    signature_matches_and_live: bool
    status: str = "LOCAL_PLAN_SIGNATURE_CHECKED_OS_PROTECTION_UNVERIFIED"
    protected_owner_principal_verified: bool = False
    independent_f18_verified: bool = False
    can_issue_owner_grant: bool = False
    can_start_worker: bool = False
    can_change_os: bool = False
    can_publish_remote: bool = False

    def __post_init__(self) -> None:
        # A parsed grant or local HMAC check can never fabricate the OS,
        # signer, F18 or publication authority of a protected owner service.
        if (type(self.signature_matches_and_live) is not bool
            or self.status != "LOCAL_PLAN_SIGNATURE_CHECKED_OS_PROTECTION_UNVERIFIED"
            or any(getattr(self, field) is not False for field in (
                "protected_owner_principal_verified",
                "independent_f18_verified", "can_issue_owner_grant",
                "can_start_worker", "can_change_os", "can_publish_remote",
            ))):
            raise ValueError("UNTRUSTED_OWNER_CONSENT_INSPECTION")


def inspect_owner_local_plan_consent(
    raw_grant_json: str, *, owned_state: str | Path,
    expected_plan_sha256: str, expected_source_sha: str,
    now_seconds: int, protected_key_reader=None,
) -> OwnerConsentInspection:
    """Read existing owner consent and verify LOCAL_PLAN MAC using a key port.

    The caller MUST supply a truly protected broker, otherwise this result
    remains advisory only. There is no key creation, storage, migration,
    signing, write access, OS identity assertion or remote permission here.
    Sensitive key bytes and raw grant never appear in returned metadata.
    """
    import re
    from my_local_ai.contracts.approval import OwnerGrant
    if (not isinstance(expected_plan_sha256,str)
        or re.fullmatch(r"[0-9a-f]{64}",expected_plan_sha256) is None
        or not isinstance(expected_source_sha,str)
        or re.fullmatch(r"[0-9a-f]{40}",expected_source_sha) is None
        or type(now_seconds) is not int or now_seconds <= 0
        or protected_key_reader is not None and not callable(protected_key_reader)):
        raise ValueError("invalid owner consent read scope")
    grant=OwnerGrant.parse_json(raw_grant_json)
    if (grant.scope != "LOCAL_PLAN"
        or grant.plan_sha256 != expected_plan_sha256
        or grant.source_git_sha != expected_source_sha):
        raise ValueError("out-of-scope or stale owner consent")
    ledger=ConsentLedger(owned_state)
    key=None
    if protected_key_reader is not None:
        try:
            key=protected_key_reader(grant.grant_id,grant.scope)
        except Exception:
            key=None
    if not isinstance(key,bytes) or len(key)!=32:
        key=None
    valid=_authorize_claim(
        grant, trusted_hmac_key=key,
        expected_plan_sha=expected_plan_sha256,
        expected_source_sha=expected_source_sha,
        required_scope="LOCAL_PLAN", now_seconds=now_seconds,
        trusted_live_consent_check=ledger.is_live,
    )
    return OwnerConsentInspection(
        grant.grant_id,expected_plan_sha256,expected_source_sha,
        grant.scope,valid,
    )


def require_protected_owner_identity(inspection: OwnerConsentInspection,
                                     *, protected_os_session=None):
    """P1 fails closed until an installed, separately owned signer is proven.

    A caller-supplied session boolean/callback is not OS attestation. The
    actual gate must live in an independently protected owner process.
    """
    if not isinstance(inspection,OwnerConsentInspection):
        raise ValueError("invalid owner consent inspection")
    raise PermissionError("OWNER_OS_PROTECTED_SIGNER_NOT_ATTESTED")



# SWU-008: genuine Windows current-user DPAPI read -> existing MAC/ledger
# verifier, never a protected-owner OS-principal or execution attestation.
# No registry creation, key provisioning, signature minting or privilege
# changes. This works only with an independently provisioned existing value.
def _read_existing_current_user_dpapi_key() -> bytearray:
    """Read an existing DPAPI-encrypted LOCAL_PLAN HMAC key without exporting it.

    The fixed owner registry key is a *location*, not an ACL/security boundary.
    Same-user untrusted host processes may also access HKCU/DPAPI. A native
    protected owner service must still prove separate process identity and
    authority before issuing grants or starting any worker.
    """
    import os
    if os.name != "nt":
        raise PermissionError("OWNER_DPAPI_WINDOWS_REQUIRED")
    try:
        import winreg
        import ctypes
        from ctypes import wintypes

        # No guest-selected path, environment, external keystore or network.
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\MyLocalAI\OwnerKeys",
            0, winreg.KEY_READ,
        ) as registry:
            sealed, kind = winreg.QueryValueEx(
                registry, "LocalPlanHmacCurrentUser",
            )
        if (kind != winreg.REG_BINARY or type(sealed) is not bytes
            or not 32 <= len(sealed) <= 8192):
            raise ValueError("invalid sealed key")

        class _DataBlob(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
            ]

        encrypted = (ctypes.c_ubyte * len(sealed)).from_buffer_copy(sealed)
        input_blob = _DataBlob(len(sealed), encrypted)
        output_blob = _DataBlob()
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(_DataBlob), ctypes.c_void_p,
            ctypes.POINTER(_DataBlob), ctypes.c_void_p,
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob),
        ]
        crypt32.CryptUnprotectData.restype = wintypes.BOOL
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        try:
            if not crypt32.CryptUnprotectData(
                ctypes.byref(input_blob), None, None, None, None,
                0x1, ctypes.byref(output_blob),  # CRYPTPROTECT_UI_FORBIDDEN
            ):
                raise ValueError("DPAPI unprotect denied")
            if (output_blob.cbData != 32 or not output_blob.pbData):
                raise ValueError("unexpected key size")
            # Move the key directly into a mutable bytearray, avoiding an
            # extra immutable Python bytes object at the native copy boundary.
            # The existing HMAC API still makes an ephemeral Python bytes
            # copy; that memory cannot be guaranteed zeroed by Python.
            candidate = bytearray(32)
            ctypes.memmove(
                (ctypes.c_ubyte * 32).from_buffer(candidate),
                output_blob.pbData, 32,
            )
            return candidate
        finally:
            if output_blob.pbData:
                if 0 < output_blob.cbData <= 8192:
                    ctypes.memset(output_blob.pbData, 0, output_blob.cbData)
                kernel32.LocalFree(ctypes.cast(
                    output_blob.pbData, ctypes.c_void_p,
                ))
            ctypes.memset(encrypted, 0, len(sealed))
    except (OSError, ValueError, TypeError, AttributeError):
        raise PermissionError("OWNER_DPAPI_KEY_NOT_AVAILABLE") from None


def inspect_owner_local_plan_windows_dpapi(
    raw_grant_json: str, *, owned_state: str | Path,
    expected_plan_sha256: str, expected_source_sha: str,
    now_seconds: int,
) -> OwnerConsentInspection:
    """Real DPAPI key decrypt -> live SQLite grant MAC check (advisory only).

    Success means current Windows logon credentials could decrypt the
    pre-provisioned key and its grant MAC matches a live LOCAL_PLAN row.
    It DOES NOT prove a separate protected Windows principal, an owner-signed
    action-specific GO, independently issued F18, or any executable right.
    """
    # Validate structural inputs before touching the Windows credential store.
    import re
    if (not isinstance(raw_grant_json, str)
        or len(raw_grant_json.encode("utf-8")) > 8192
        or not isinstance(expected_plan_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_plan_sha256) is None
        or not isinstance(expected_source_sha, str)
        or re.fullmatch(r"[0-9a-f]{40}", expected_source_sha) is None
        or type(now_seconds) is not int or now_seconds <= 0):
        raise ValueError("invalid DPAPI owner grant inspection scope")
    key = _read_existing_current_user_dpapi_key()
    try:
        result = inspect_owner_local_plan_consent(
            raw_grant_json, owned_state=owned_state,
            expected_plan_sha256=expected_plan_sha256,
            expected_source_sha=expected_source_sha,
            now_seconds=now_seconds,
            protected_key_reader=lambda grant_id, scope: (
                bytes(key) if scope == "LOCAL_PLAN" else None
            ),
        )
        if (not isinstance(result, OwnerConsentInspection)
            or result.can_issue_owner_grant or result.can_start_worker
            or result.can_change_os or result.can_publish_remote
            or result.protected_owner_principal_verified
            or result.independent_f18_verified):
            raise PermissionError("OWNER_PROTECTED_PRINCIPAL_NOT_ATTESTED")
        return result
    finally:
        for i in range(len(key)):
            key[i] = 0
