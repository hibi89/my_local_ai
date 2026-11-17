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
        crypt32 = ctypes.WinDLL("crypt32.dll", use_last_error=True, winmode=0x00000800)
        crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(_DataBlob), ctypes.c_void_p,
            ctypes.POINTER(_DataBlob), ctypes.c_void_p,
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob),
        ]
        crypt32.CryptUnprotectData.restype = wintypes.BOOL
        kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x00000800)
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


# MLA-SWU-008: actual owner-side Windows token posture observation.
# This is a read-only *diagnostic*, not an owner signer, ACL attestation,
# authenticated role separation, F18 reviewer or capability to run AI code.
@_dataclass(frozen=True)
class WindowsOwnerTokenObservation:
    """Redacted current-process token observations, never trust evidence."""

    source: str
    elevated: bool | None
    appcontainer: bool | None
    restricted: bool | None
    job_member: bool | None
    state: str = "TOKEN_OBSERVATION_NOT_PROTECTED_OWNER_IDENTITY"
    owner_principal_protected: bool = False
    key_custody_attested: bool = False
    coder_reviewer_separated: bool = False
    network_egress_denied: bool = False
    independent_f18_verified: bool = False
    can_issue_owner_grant: bool = False
    can_run_worker: bool = False
    can_modify_os: bool = False

    def __post_init__(self) -> None:
        flags = ("elevated", "appcontainer", "restricted", "job_member")
        if (self.source not in (
                "WINDOWS_TOKEN_QUERIED", "WINDOWS_TOKEN_UNAVAILABLE", "NON_WINDOWS"
            )
            or self.state != "TOKEN_OBSERVATION_NOT_PROTECTED_OWNER_IDENTITY"
            or any(type(getattr(self, key)) not in (bool, type(None))
                   for key in flags)
            or (self.source != "WINDOWS_TOKEN_QUERIED"
                and any(getattr(self, key) is not None for key in flags))
            or any(getattr(self, key) is not False for key in (
                "owner_principal_protected", "key_custody_attested",
                "coder_reviewer_separated", "network_egress_denied",
                "independent_f18_verified", "can_issue_owner_grant",
                "can_run_worker", "can_modify_os",
            ))):
            raise ValueError("UNTRUSTED_OWNER_TOKEN_OBSERVATION")

    def to_redacted_dict(self) -> dict[str, object]:
        """Never reveal SID, logon name, privileges, handles or key material."""
        return {
            "source": self.source,
            "elevated_observed": self.elevated,
            "appcontainer_observed": self.appcontainer,
            "restricted_token_observed": self.restricted,
            "job_membership_observed": self.job_member,
            "owner_principal": "NOT_ATTESTED",
            "owner_key_custody": "NOT_ATTESTED",
            "coder_reviewer_separation": "NOT_ATTESTED",
            "network_egress": "NOT_ATTESTED",
            "f18": "NOT_VERIFIED",
            "owner_grant_issued": False,
            "os_changed": False,
            "execution_allowed": False,
            "p2": "LOCKED",
        }


def inspect_windows_current_token_read_only() -> WindowsOwnerTokenObservation:
    """Current host process -> Windows TOKEN_QUERY -> redacted posture.

    Never impersonates, duplicates tokens, accesses protected keys, allocates a
    Job Object, creates an AppContainer, starts a process or modifies Windows.
    Positive elevation, restricted-token or AppContainer flags do NOT prove
    that a protected owner signer exists or that worker egress is denied.
    """
    import os
    if os.name != "nt":
        return WindowsOwnerTokenObservation("NON_WINDOWS", None, None, None, None)
    try:
        import ctypes
        from ctypes import wintypes

        system32_only = 0x00000800  # LOAD_LIBRARY_SEARCH_SYSTEM32
        advapi = ctypes.WinDLL("advapi32.dll", use_last_error=True,
                              winmode=system32_only)
        kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True,
                              winmode=system32_only)
        kernel.GetCurrentProcess.argtypes = ()
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        advapi.OpenProcessToken.argtypes = (
            wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
        )
        advapi.OpenProcessToken.restype = wintypes.BOOL
        advapi.GetTokenInformation.argtypes = (
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
        )
        advapi.GetTokenInformation.restype = wintypes.BOOL
        advapi.IsTokenRestricted.argtypes = (wintypes.HANDLE,)
        advapi.IsTokenRestricted.restype = wintypes.BOOL
        kernel.IsProcessInJob.argtypes = (
            wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)
        )
        kernel.IsProcessInJob.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL

        process = kernel.GetCurrentProcess()  # Pseudohandle; never close.
        token = wintypes.HANDLE()
        if not advapi.OpenProcessToken(process, 0x0008, ctypes.byref(token)):
            return WindowsOwnerTokenObservation(
                "WINDOWS_TOKEN_UNAVAILABLE", None, None, None, None
            )
        try:
            def query_dword(token_class: int) -> bool | None:
                value = wintypes.DWORD()
                received = wintypes.DWORD()
                ok = advapi.GetTokenInformation(
                    token, token_class, ctypes.byref(value),
                    ctypes.sizeof(value), ctypes.byref(received)
                )
                if not ok or received.value != ctypes.sizeof(value):
                    return None
                if value.value not in (0, 1):
                    return None
                return bool(value.value)

            # TOKEN_INFORMATION_CLASS: TokenElevation=20,
            # TokenIsAppContainer=29. Values are observations, not claims.
            elevation = query_dword(20)
            appcontainer = query_dword(29)
            ctypes.set_last_error(0)
            restricted_value = bool(advapi.IsTokenRestricted(token))
            restricted = (
                None if ctypes.get_last_error() != 0 else restricted_value
            )
            in_job = wintypes.BOOL()
            in_job_ok = kernel.IsProcessInJob(
                process, None, ctypes.byref(in_job)
            )
            job_member = bool(in_job.value) if in_job_ok else None
            return WindowsOwnerTokenObservation(
                "WINDOWS_TOKEN_QUERIED",
                elevation, appcontainer, restricted, job_member
            )
        finally:
            kernel.CloseHandle(token)
    except (OSError, AttributeError, ValueError, TypeError, OverflowError):
        return WindowsOwnerTokenObservation(
            "WINDOWS_TOKEN_UNAVAILABLE", None, None, None, None
        )


def _owner_token_read_only_main() -> int:
    """Explicit non-executing diagnostic: python -m my_local_ai.state.consent"""
    import json
    report = inspect_windows_current_token_read_only()
    print(json.dumps(report.to_redacted_dict(), sort_keys=True))
    return 0  # Diagnostic completed, NOT a signer/OS isolation PASS.


# Protected-service client. This is deliberately NOT a service installer or a
# new signer in the Controller. The four native services, TPM keys, protected
# ledgers and runtime policy have to be provisioned independently by the owner.
# An absent/misconfigured service is a hard denial, never a host fallback.
class ProtectedBrokerHold(PermissionError):
    def __init__(self, code: str = "PROTECTED_BROKER_UNAVAILABLE"):
        self.code = code if code in {
            "PROTECTED_BROKER_UNAVAILABLE", "PROTECTED_BROKER_PLATFORM",
            "PROTECTED_BROKER_IDENTITY", "PROTECTED_BROKER_TIMEOUT",
            "PROTECTED_BROKER_PROTOCOL", "PROTECTED_BROKER_SIGNATURE",
            "PROTECTED_OWNER_ACTION_DENIED", "PROTECTED_RUNTIME_DENIED",
        } else "PROTECTED_BROKER_UNAVAILABLE"
        super().__init__(self.code)


_BROKER_ROLES = ("owner", "coder", "reviewer", "scanner")
_BROKER_OPERATIONS = {
    "owner": frozenset({"authorize"}),
    "coder": frozenset({"prepare", "run", "abort"}),
    "reviewer": frozenset({"runtime-permit", "review"}),
    "scanner": frozenset({"semgrep", "defender"}),
}
_BROKER_LIMIT = 2 * 1024 * 1024


def _broker_canonical(value: object) -> bytes:
    import json
    try:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=True,
                         separators=(",", ":"), allow_nan=False).encode("ascii")
        if not 1 <= len(raw) <= _BROKER_LIMIT:
            raise ValueError()
        return raw
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL") from None


def _broker_decode(raw: bytes) -> dict:
    import json
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError()
            result[name] = value
        return result
    try:
        if type(raw) is not bytes or not 1 <= len(raw) <= _BROKER_LIMIT:
            raise ValueError()
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if type(result) is not dict:
            raise ValueError()
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL") from None


def _validate_broker_binding(binding: dict) -> None:
    import re
    if type(binding) is not dict or set(binding) != {
        "task_id", "run_id", "plan_sha256", "source_sha", "candidate_sha",
        "lease_epoch", "nonce_sha256", "owner_consent_ref",
    }:
        raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
    for field in ("task_id", "run_id", "owner_consent_ref"):
        if (type(binding[field]) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,63}", binding[field]) is None):
            raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
    for field in ("plan_sha256", "nonce_sha256", "source_sha", "candidate_sha"):
        count = 40 if field.endswith("_sha") else 64
        if (type(binding[field]) is not str
            or re.fullmatch(r"[0-9a-f]{%d}" % count, binding[field]) is None):
            raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
    if (type(binding["lease_epoch"]) is not int
        or not 1 <= binding["lease_epoch"] <= 2**63 - 1
        or binding["candidate_sha"] == binding["source_sha"]):
        raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")


class _WindowsBrokerAPI:
    """System32-only Win32 calls; no shell, policy writes or private-key reads."""
    def __init__(self):
        import os
        if os.name != "nt":
            raise ProtectedBrokerHold("PROTECTED_BROKER_PLATFORM")
        import ctypes as c
        from ctypes import wintypes as w
        self.c, self.w = c, w
        self.kernel = c.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
        self.advapi = c.WinDLL("advapi32.dll", use_last_error=True, winmode=0x800)
        self.bcrypt = c.WinDLL("bcrypt.dll", use_last_error=True, winmode=0x800)
        self._bind(self.kernel, "CloseHandle", [w.HANDLE], w.BOOL)
        self._bind(self.kernel, "LocalFree", [c.c_void_p], c.c_void_p)

    @staticmethod
    def _bind(dll, name, args, result):
        func = getattr(dll, name)
        func.argtypes, func.restype = args, result
        return func

    def sid_string(self, sid) -> str:
        c, w = self.c, self.w
        text = w.LPWSTR()
        convert = self._bind(self.advapi, "ConvertSidToStringSidW",
                             [c.c_void_p, c.POINTER(w.LPWSTR)], w.BOOL)
        if not sid or not convert(sid, c.byref(text)):
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        try:
            return text.value
        finally:
            self.kernel.LocalFree(c.cast(text, c.c_void_p))

    def check_acl(self, handle, kind: int, write_mask: int) -> None:
        """Reject NULL DACLs, unknown ACEs and non-admin writers/owners.

        Conservative allow-only analysis: even a matching deny ACE does not
        excuse a broad allow. Inherited ACEs are examined, never skipped.
        """
        c, w = self.c, self.w
        owner, dacl, descriptor = c.c_void_p(), c.c_void_p(), c.c_void_p()
        get = self._bind(self.advapi, "GetSecurityInfo", [w.HANDLE, c.c_int,
            w.DWORD, c.POINTER(c.c_void_p), c.c_void_p, c.POINTER(c.c_void_p),
            c.c_void_p, c.POINTER(c.c_void_p)], w.DWORD)
        if get(handle, kind, 5, c.byref(owner), None, c.byref(dacl), None,
               c.byref(descriptor)) != 0:
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        trusted = {"S-1-5-18", "S-1-5-32-544"}
        try:
            if self.sid_string(owner) not in trusted or not dacl.value:
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            class ACL(c.Structure):
                _fields_ = [("revision", c.c_ubyte), ("sbz1", c.c_ubyte),
                            ("size", w.WORD), ("count", w.WORD), ("sbz2", w.WORD)]
            header = c.cast(dacl, c.POINTER(ACL)).contents
            get_ace = self._bind(self.advapi, "GetAce",
                                 [c.c_void_p, w.DWORD, c.POINTER(c.c_void_p)], w.BOOL)
            for i in range(header.count):
                ace = c.c_void_p()
                if not get_ace(dacl, i, c.byref(ace)):
                    raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                ace_type = c.c_ubyte.from_address(ace.value).value
                ace_flags = c.c_ubyte.from_address(ace.value + 1).value
                # INHERIT_ONLY ACEs do not authorize access to this object.
                if ace_flags & 8 or ace_type == 1:  # ordinary DENY
                    continue
                if ace_type != 0:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                mask = w.DWORD.from_address(ace.value + 4).value
                if mask & write_mask and self.sid_string(ace.value + 8) not in trusted:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        finally:
            if descriptor.value:
                self.kernel.LocalFree(descriptor)

    def load_roots(self) -> dict:
        """Only preexisting 64-bit HKLM roots; HKCU/env/task pins are forbidden."""
        import re
        import winreg
        roots = {}
        base = r"SOFTWARE\MyLocalAI\ProtectedBrokers\v1"
        # Parent delete/rename rights can replace a perfectly protected child.
        for name in ("SOFTWARE", r"SOFTWARE\MyLocalAI",
                     r"SOFTWARE\MyLocalAI\ProtectedBrokers", base,
                     *(base + "\\" + role for role in _BROKER_ROLES)):
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, name, 0,
                                winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                self.check_acl(int(key), 4, 0xD0000 | 0x26 | 0x50000000)
                role = name.rsplit("\\", 1)[-1]
                if role not in _BROKER_ROLES:
                    continue
                sid, sid_kind = winreg.QueryValueEx(key, "PrincipalSid")
                image, image_kind = winreg.QueryValueEx(key, "ImageSha256")
                public, public_kind = winreg.QueryValueEx(key, "PublicKeyBlob")
                if (sid_kind != winreg.REG_SZ or type(sid) is not str
                    or re.fullmatch(r"S-1-5-21-(?:[0-9]+-){3}[0-9]+", sid) is None
                    or image_kind != winreg.REG_SZ or type(image) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", image) is None
                    or public_kind != winreg.REG_BINARY or type(public) is not bytes
                    or len(public) != 72 or public[:8] != b"ECS1\x20\x00\x00\x00"):
                    raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                roots[role] = (sid, image, public)
        if any(len({value[index] for value in roots.values()}) != 4 for index in (0, 1, 2)):
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        return roots

    def process_sid(self, process) -> str:
        c, w = self.c, self.w
        token = w.HANDLE()
        open_token = self._bind(self.advapi, "OpenProcessToken",
            [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)], w.BOOL)
        get = self._bind(self.advapi, "GetTokenInformation",
            [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
        if not open_token(process, 8, c.byref(token)):
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        try:
            length = w.DWORD()
            get(token, 1, None, 0, c.byref(length))  # TokenUser
            if not 1 <= length.value <= 65536:
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            data = c.create_string_buffer(length.value)
            if not get(token, 1, data, len(data), c.byref(length)):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            return self.sid_string(c.cast(data, c.POINTER(c.c_void_p))[0])
        finally:
            self.kernel.CloseHandle(token)

    def authenticate_pipe(self, pipe, role: str, roots: dict):
        """Hold the SCM/peer process handles until the transaction has ended."""
        c, w = self.c, self.w
        from contextlib import ExitStack
        from hashlib import sha256
        pid = w.ULONG()
        get_pid = self._bind(self.kernel, "GetNamedPipeServerProcessId",
                            [w.HANDLE, c.POINTER(w.ULONG)], w.BOOL)
        open_process = self._bind(self.kernel, "OpenProcess",
                                  [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
        current = self._bind(self.kernel, "GetCurrentProcess", [], w.HANDLE)
        if not get_pid(pipe, c.byref(pid)) or not pid.value:
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        stack = ExitStack()
        try:
            process = open_process(0x1000 | 0x100000, False, pid.value)
            if not process:
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            stack.callback(self.kernel.CloseHandle, process)
            if (self.process_sid(process) != roots[role][0]
                or self.process_sid(current()) in {v[0] for v in roots.values()}):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            open_scm = self._bind(self.advapi, "OpenSCManagerW",
                                  [w.LPCWSTR, w.LPCWSTR, w.DWORD], w.HANDLE)
            open_service = self._bind(self.advapi, "OpenServiceW",
                                      [w.HANDLE, w.LPCWSTR, w.DWORD], w.HANDLE)
            close = self._bind(self.advapi, "CloseServiceHandle", [w.HANDLE], w.BOOL)
            manager = open_scm(None, None, 1)
            if not manager:
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            stack.callback(close, manager)
            service = open_service(manager, "MyLocalAI." + role + ".v1", 0x20005)
            if not service:
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            stack.callback(close, service)
            self.check_acl(service, 2, 0xD0000 | 0x1F2 | 0x50000000)
            status = (w.DWORD * 9)()
            length = w.DWORD()
            query = self._bind(self.advapi, "QueryServiceStatusEx",
                [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
            if (not query(service, 0, status, c.sizeof(status), c.byref(length))
                or status[0] != 0x10 or status[1] != 4 or status[7] != pid.value):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            image = c.create_unicode_buffer(32768)
            count = w.DWORD(len(image))
            image_name = self._bind(self.kernel, "QueryFullProcessImageNameW",
                [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)], w.BOOL)
            if not image_name(process, 0, image, c.byref(count)):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            path = Path(image.value)
            if not path.is_absolute() or path.suffix.lower() != ".exe":
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            # Keep native image and all ancestors non-writable by untrusted
            # principals. FILE_SHARE_READ denies replacement while hashing.
            create = self._bind(self.kernel, "CreateFileW", [w.LPCWSTR, w.DWORD,
                w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE], w.HANDLE)
            for node in (path, *path.parents):
                info = node.lstat()
                if (stat.S_ISLNK(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & _REPARSE
                    or node == path and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)):
                    raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                handle = create(str(node), 0x20000, 1, None, 3, 0x02200000, None)
                if handle in (None, c.c_void_p(-1).value):
                    raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                stack.callback(self.kernel.CloseHandle, handle)
                self.check_acl(handle, 1, 0xD0000 | 0x156 | 0x50000000)
            if not 1 <= path.stat().st_size <= 128 * 1024 * 1024:
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            with path.open("rb") as stream:
                digest = sha256()
                while chunk := stream.read(65536):
                    digest.update(chunk)
            if digest.hexdigest() != roots[role][1]:
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            # No interpreter/script/extra arguments in the registered service.
            class Config(c.Structure):
                _fields_ = [("kind", w.DWORD), ("start", w.DWORD), ("error", w.DWORD),
                            ("binary", w.LPWSTR), ("group", w.LPWSTR), ("tag", w.DWORD),
                            ("dependencies", w.LPWSTR), ("account", w.LPWSTR), ("display", w.LPWSTR)]
            config_query = self._bind(self.advapi, "QueryServiceConfigW",
                [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
            config_query(service, None, 0, c.byref(length))
            if not c.sizeof(Config) <= length.value <= 65536:
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            config = c.create_string_buffer(length.value)
            if not config_query(service, config, len(config), c.byref(length)):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            binary = c.cast(config, c.POINTER(Config)).contents.binary
            if binary not in (str(path), '"' + str(path) + '"'):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            return stack
        except BaseException:
            stack.close()
            raise

    def verify_signature(self, public: bytes, payload: bytes, signature: bytes) -> None:
        from hashlib import sha256
        c, w = self.c, self.w
        alg, key = c.c_void_p(), c.c_void_p()
        open_alg = self._bind(self.bcrypt, "BCryptOpenAlgorithmProvider",
            [c.POINTER(c.c_void_p), w.LPCWSTR, w.LPCWSTR, w.DWORD], c.c_long)
        import_key = self._bind(self.bcrypt, "BCryptImportKeyPair",
            [c.c_void_p, c.c_void_p, w.LPCWSTR, c.POINTER(c.c_void_p),
             c.c_void_p, w.ULONG, w.ULONG], c.c_long)
        verify = self._bind(self.bcrypt, "BCryptVerifySignature",
            [c.c_void_p, c.c_void_p, c.c_void_p, w.ULONG, c.c_void_p,
             w.ULONG, w.ULONG], c.c_long)
        destroy = self._bind(self.bcrypt, "BCryptDestroyKey", [c.c_void_p], c.c_long)
        close = self._bind(self.bcrypt, "BCryptCloseAlgorithmProvider",
                            [c.c_void_p, w.ULONG], c.c_long)
        try:
            if (len(signature) != 64
                or open_alg(c.byref(alg), "ECDSA_P256", None, 0) != 0
                or import_key(alg, None, "ECCPUBLICBLOB", c.byref(key),
                              c.create_string_buffer(public), len(public), 0) != 0):
                raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")
            digest = sha256(b"mla-protected-broker/v1|" + payload).digest()
            if verify(key, None, c.create_string_buffer(digest), len(digest),
                      c.create_string_buffer(signature), len(signature), 0) != 0:
                raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")
        finally:
            if key.value:
                destroy(key)
            if alg.value:
                close(alg, 0)

    def transact(self, role: str, roots: dict, request: bytes, timeout: int) -> bytes:
        import time
        c, w = self.c, self.w
        class Overlapped(c.Structure):
            _fields_ = [("internal", c.c_size_t), ("internal_high", c.c_size_t),
                        ("offset", w.DWORD), ("offset_high", w.DWORD), ("event", w.HANDLE)]
        create = self._bind(self.kernel, "CreateFileW", [w.LPCWSTR, w.DWORD,
            w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE], w.HANDLE)
        event_create = self._bind(self.kernel, "CreateEventW",
            [c.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR], w.HANDLE)
        wait = self._bind(self.kernel, "WaitForSingleObject", [w.HANDLE, w.DWORD], w.DWORD)
        cancel = self._bind(self.kernel, "CancelIoEx",
            [w.HANDLE, c.POINTER(Overlapped)], w.BOOL)
        complete = self._bind(self.kernel, "GetOverlappedResult",
            [w.HANDLE, c.POINTER(Overlapped), c.POINTER(w.DWORD), w.BOOL], w.BOOL)
        # SECURITY_IDENTIFICATION prevents a pipe squatter impersonating us.
        pipe = create(r"\\.\pipe\MyLocalAI.v1." + role, 0xC0000000, 0, None,
                      3, 0x40000000 | 0x00110000, None)
        if pipe in (None, c.c_void_p(-1).value):
            raise ProtectedBrokerHold()
        deadline = time.monotonic() + timeout
        try:
            with self.authenticate_pipe(pipe, role, roots):
                def io(data: bytes | None, size: int) -> bytes:
                    buffer = c.create_string_buffer(data, size) if data is not None else c.create_string_buffer(size)
                    ov = Overlapped()
                    ov.event = event_create(None, True, False, None)
                    if not ov.event:
                        raise ProtectedBrokerHold()
                    count = w.DWORD()
                    call = self._bind(self.kernel, "WriteFile" if data is not None else "ReadFile",
                        [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD),
                         c.POINTER(Overlapped)], w.BOOL)
                    try:
                        ok = call(pipe, buffer, size, c.byref(count), c.byref(ov))
                        if not ok:
                            if c.get_last_error() != 997:  # ERROR_IO_PENDING
                                raise ProtectedBrokerHold()
                            remaining = max(0, int((deadline - time.monotonic()) * 1000))
                            if wait(ov.event, remaining) != 0:
                                cancel(pipe, c.byref(ov))
                                # Reap cancelled I/O BEFORE freeing its buffer/event.
                                complete(pipe, c.byref(ov), c.byref(count), True)
                                raise ProtectedBrokerHold("PROTECTED_BROKER_TIMEOUT")
                            if not complete(pipe, c.byref(ov), c.byref(count), False):
                                raise ProtectedBrokerHold()
                        if not 1 <= count.value <= size:
                            raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
                        return buffer.raw[:count.value]
                    finally:
                        self.kernel.CloseHandle(ov.event)
                packet = len(request).to_bytes(4, "little") + request
                position = 0
                while position < len(packet):
                    position += len(io(packet[position:], len(packet) - position))
                def read_exact(count):
                    parts = bytearray()
                    while len(parts) < count:
                        if time.monotonic() >= deadline:
                            raise ProtectedBrokerHold("PROTECTED_BROKER_TIMEOUT")
                        parts.extend(io(None, count - len(parts)))
                    return bytes(parts)
                length = int.from_bytes(read_exact(4), "little")
                if not 1 <= length <= _BROKER_LIMIT:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
                return read_exact(length)
        finally:
            self.kernel.CloseHandle(pipe)


def exchange_protected_broker(role: str, operation: str, *, binding: dict,
                              payload: dict, timeout_seconds: int = 30) -> dict:
    """Real authenticated IPC. Returned signed data is NEVER a Git capability.

    Fixed local pipes, SCM PID/user/image/ACL checks and HKLM-pinned ECDSA
    public keys. No private key ever enters this process. Each response binds
    the entire request, random transport challenge, exact lease and lifetime.
    A timeout is terminal: there is no retry of a possibly consumed action.
    """
    import base64
    import secrets
    import time
    from hashlib import sha256
    if (type(role) is not str or role not in _BROKER_ROLES
        or type(operation) is not str or operation not in _BROKER_OPERATIONS[role]
        or type(payload) is not dict or type(timeout_seconds) is not int
        or not 1 <= timeout_seconds <= 600):
        raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
    _validate_broker_binding(binding)
    binding = _broker_decode(_broker_canonical(binding))
    payload = _broker_decode(_broker_canonical(payload))
    nonce = secrets.token_hex(32)
    request = _broker_canonical({"schema": "mla-protected-request/v1",
        "role": role, "operation": operation, "binding": binding,
        "challenge": nonce, "payload": payload})
    started = int(time.time())
    try:
        api = _WindowsBrokerAPI()
        roots = api.load_roots()
        raw = api.transact(role, roots, request, timeout_seconds)
        envelope = _broker_decode(raw)
        if set(envelope) != {"body", "signature"} or type(envelope["body"]) is not dict:
            raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
        body = envelope["body"]
        if (set(body) != {"schema", "role", "operation", "request_sha256", "challenge",
                         "binding", "issued_at", "expires_at", "status", "result"}
            or body["schema"] != "mla-protected-response/v1"
            or body["role"] != role or body["operation"] != operation
            or body["request_sha256"] != sha256(request).hexdigest()
            or body["challenge"] != nonce or body["binding"] != binding
            or type(body["issued_at"]) is not int or type(body["expires_at"]) is not int
            or not started - 5 <= body["issued_at"] <= int(time.time()) + 5
            or not body["issued_at"] <= int(time.time()) < body["expires_at"]
            or not 1 <= body["expires_at"] - body["issued_at"] <= 30
            or body["status"] not in {"OK", "DENIED"} or type(body["result"]) is not dict
            or type(envelope["signature"]) is not str or len(envelope["signature"]) != 88):
            raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
        _validate_broker_binding(body["binding"])  # Reject bool-as-int epochs.
        signature = base64.b64decode(envelope["signature"], validate=True)
        api.verify_signature(roots[role][2], _broker_canonical(body), signature)
        if body["status"] != "OK":
            raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
        # Preserve the actual signed bytes so the protected callee can verify
        # independently and atomically consume authorization at execution.
        return {"result": body["result"], "signed_envelope": base64.b64encode(raw).decode("ascii"),
                "peer_image_sha256": roots[role][1]}
    except ProtectedBrokerHold:
        raise
    except (OSError, ValueError, TypeError, AttributeError, OverflowError):
        raise ProtectedBrokerHold() from None


def dispatch_protected_action(role: str, operation: str, *, binding: dict,
                              payload: dict, timeout_seconds: int = 30) -> dict:
    """Owner live action -> independent runtime permit -> fixed service callee.

    The native callee MUST validate both signed envelopes, live lease, P2/
    owner GO and one-shot nonce in its own protected store before any spawn.
    This client cannot install/provide those services or certify their policy.
    Existing V1 HMAC LOCAL_PLAN grants remain categorically insufficient.
    """
    from hashlib import sha256
    if (role, operation) not in {("coder", "prepare"), ("coder", "run"), ("reviewer", "review"),
                                 ("scanner", "semgrep"), ("scanner", "defender")}:
        raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
    if type(payload) is not dict or type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 600:
        raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
    _validate_broker_binding(binding)
    binding = _broker_decode(_broker_canonical(binding))
    payload = _broker_decode(_broker_canonical(payload))
    action_sha256 = sha256(_broker_canonical({"role": role, "operation": operation,
        "binding": binding, "payload": payload})).hexdigest()
    action = {"role": role, "operation": operation, "action_sha256": action_sha256}
    owner = exchange_protected_broker("owner", "authorize", binding=binding, payload=action)
    if owner["result"] != {"action_sha256": action_sha256, "decision": "APPROVED_SINGLE_USE"}:
        raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
    permit = exchange_protected_broker("reviewer", "runtime-permit", binding=binding,
        payload={**action, "owner_authorization": owner["signed_envelope"]})
    if permit["result"] != {"action_sha256": action_sha256, "decision": "RUNTIME_BOUNDARY_APPROVED"}:
        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
    return exchange_protected_broker(role, operation, binding=binding,
        payload={"action_sha256": action_sha256, "input": payload,
                 "owner_authorization": owner["signed_envelope"],
                 "runtime_permit": permit["signed_envelope"]}, timeout_seconds=timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(_owner_token_read_only_main())
