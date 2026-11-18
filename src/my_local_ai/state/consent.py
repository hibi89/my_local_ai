"""Local consent inspection, authenticated IPC, and native protected services.

LOCAL_PLAN inspection remains advisory. Native server activation requires
separately provisioned SCM principals, pinned images/TPM keys and protected
ledgers; this source never provisions or grants those OS rights itself.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing as _closing
from pathlib import Path
import stat

from my_local_ai.state.migrations import APP_ID, SCHEMA_VERSION

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_SYSTEM_TRUSTED_SIDS = frozenset({
    "S-1-5-18", "S-1-5-32-544",
    "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464",  # TrustedInstaller
})

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
# new signer in the Controller. The three native services, TPM keys, protected
# ledgers and runtime policy have to be provisioned independently by the owner.
# An absent/misconfigured service is a hard denial, never a host fallback.
class ProtectedBrokerHold(PermissionError):
    def __init__(self, code: str = "PROTECTED_BROKER_UNAVAILABLE"):
        self.code = code if code in {
            "PROTECTED_BROKER_UNAVAILABLE", "PROTECTED_BROKER_PLATFORM",
            "PROTECTED_BROKER_IDENTITY", "PROTECTED_BROKER_TIMEOUT",
            "PROTECTED_BROKER_PROTOCOL", "PROTECTED_BROKER_SIGNATURE",
            "PROTECTED_OWNER_ACTION_DENIED", "PROTECTED_RUNTIME_DENIED",
            "PROTECTED_ACTION_OUTCOME_UNKNOWN",
        } else "PROTECTED_BROKER_UNAVAILABLE"
        super().__init__(self.code)


_BROKER_ROLES = ("owner", "coder", "reviewer", "scanner")
_SERVICE_ROLES = ("owner", "reviewer", "scanner")
_BROKER_OPERATIONS = {
    "owner": frozenset({"authorize"}),
    "coder": frozenset(),  # Zero-VM V1.3: no generated-code broker execution.
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

    def check_acl(self, handle, kind: int, write_mask: int, *, allowed_writers=(), allowed_owners=()) -> None:
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
        trusted = _SYSTEM_TRUSTED_SIDS
        writers = trusted | set(allowed_writers)
        try:
            if self.sid_string(owner) not in trusted | set(allowed_owners) or not dacl.value:
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
                if mask & write_mask and self.sid_string(ace.value + 8) not in writers:
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
                     *(base + "\\" + role for role in _SERVICE_ROLES)):
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, name, 0,
                                winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                self.check_acl(int(key), 4, 0xD0000 | 0x26 | 0x50000000)
                role = name.rsplit("\\", 1)[-1]
                if role not in _SERVICE_ROLES:
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
        if any(len({value[index] for value in roots.values()}) != 3 for index in (0, 1, 2)):
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

    def authenticate_pipe(self, pipe, role: str, roots: dict, *, service_self=False):
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
        if service_self:
            # SCM validates our own PID/image before the pipe has a client.
            # Do not depend on a connected-peer pipe query during startup.
            pid.value = self._bind(self.kernel, "GetCurrentProcessId", [], w.DWORD)()
        elif not get_pid(pipe, c.byref(pid)) or not pid.value:
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        stack = ExitStack()
        try:
            process = open_process(0x1000 | 0x100000, False, pid.value)
            if not process:
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            stack.callback(self.kernel.CloseHandle, process)
            if (self.process_sid(process) != roots[role][0]
                or (self.process_sid(current()) != roots[role][0] if service_self
                    else self.process_sid(current()) in {v[0] for v in roots.values()})):
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
    """Owner live action -> independent permit -> fixed read-only service.

    Zero-VM policy denies coder prepare/run/abort even with owner claims.
    The native callee MUST validate both signed envelopes, live lease, P2/
    owner GO and one-shot nonce before any nonexecuting fixed scan/review.
    This client cannot install/provide those services or certify their policy.
    Existing V1 HMAC LOCAL_PLAN grants remain categorically insufficient.
    """
    from hashlib import sha256
    if (role, operation) not in {("reviewer", "review"),
                                 ("scanner", "semgrep"), ("scanner", "defender")}:
        raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
    if type(payload) is not dict or type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 600:
        raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
    _validate_broker_binding(binding)
    binding = _broker_decode(_broker_canonical(binding))
    payload = _broker_decode(_broker_canonical(payload))
    # Bind the complete action to the owner request. A digest-only prompt would
    # leave the independent owner unable to display what is being approved.
    # The broker still has to present its own authenticated, bounded summary;
    # no caller-supplied approval boolean is accepted here.
    action = {"role": role, "operation": operation,
        "binding": binding, "payload": payload}
    action_sha256 = sha256(_broker_canonical(action)).hexdigest()
    owner_action = {"action_sha256": action_sha256, "action": action}
    owner = exchange_protected_broker(
        "owner", "authorize", binding=binding, payload=owner_action,
    )
    if owner["result"] != {
        "action_sha256": action_sha256,
        "decision": "APPROVED_SINGLE_USE",
        "nonce_state": "CONSUMED",
        "lease_state": "LIVE_AT_SIGNING",
    }:
        raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
    permit = exchange_protected_broker("reviewer", "runtime-permit", binding=binding,
        payload={"action_sha256": action_sha256, "action": action,
                 "owner_authorization": owner["signed_envelope"]})
    if permit["result"] != {
        "action_sha256": action_sha256,
        "decision": "RUNTIME_BOUNDARY_APPROVED",
        "nonce_state": "LIVE_FOR_REVIEW",
        "lease_state": "LIVE_AT_SIGNING",
    }:
        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
    try:
        return exchange_protected_broker(role, operation, binding=binding,
            payload={"action_sha256": action_sha256, "input": payload,
                     "owner_authorization": owner["signed_envelope"],
                     "runtime_permit": permit["signed_envelope"]}, timeout_seconds=timeout_seconds)
    except ProtectedBrokerHold:
        # The final service may have consumed a nonce/started its native scan
        # before a connection or signature failure. Never mislabel that as a
        # proven NOT_RUN or automatically retry an indeterminate operation.
        raise ProtectedBrokerHold("PROTECTED_ACTION_OUTCOME_UNKNOWN") from None


# Native server implementation. Nothing below installs a service, creates a
# key/account, edits an ACL, or populates trust policy. An administrator must
# provision THREE distinct frozen service images/SIDs/TPM keys, the two schema
# types below, and a separate interactive owner before this entry point works.
# Runtime writes are confined to each service's existing private journal.
import base64 as _b64
import time as _time
from hashlib import sha256 as _digest
from contextlib import ExitStack as _ExitStack, contextmanager as _contextmanager

_AUTHORITY_APP_ID = 0x4D4C4141
_SERVICE_APP_ID = 0x4D4C4153
_SERVICE_HOME = Path(r"C:\ProgramData\MyLocalAI\Protected\v1")
PROTECTED_AUTHORITY_SCHEMA = """
PRAGMA application_id=1296843073;
PRAGMA user_version=1;
CREATE TABLE scopes (
 consent_ref TEXT PRIMARY KEY, binding_json TEXT NOT NULL,
 scope_json TEXT NOT NULL, expires_at INTEGER NOT NULL,
 revoked INTEGER NOT NULL CHECK(revoked IN (0,1))
);
"""
PROTECTED_SERVICE_LEDGER_SCHEMA = """
PRAGMA application_id=1296843091;
PRAGMA user_version=1;
CREATE TABLE journal (
 nonce_key TEXT PRIMARY KEY, action_sha256 TEXT NOT NULL,
 binding_sha256 TEXT NOT NULL, challenge TEXT NOT NULL UNIQUE,
 state TEXT NOT NULL CHECK(state IN ('RESERVED','DENIED','COMPLETED')),
 created_at INTEGER NOT NULL, response BLOB
);
"""


def _service_request(raw: bytes, role: str) -> dict:
    import re
    request = _broker_decode(raw)
    if (set(request) != {"schema", "role", "operation", "binding", "challenge", "payload"}
        or request["schema"] != "mla-protected-request/v1"
        or request["role"] != role or role not in _SERVICE_ROLES
        or type(request["operation"]) is not str
        or request["operation"] not in _BROKER_OPERATIONS[role]
        or type(request["challenge"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", request["challenge"]) is None
        or type(request["payload"]) is not dict):
        raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
    _validate_broker_binding(request["binding"])
    if raw != _broker_canonical(request):
        raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
    return request


class _ServiceJournal:
    """Durable anti-replay, not a trust root. Host must pin its OS protection.

    Reservation commits BEFORE UI/scan work. A crash after reservation burns
    the nonce; retries cannot reexecute it. Only a new independently approved
    lease/nonce can recover. Runtime never initializes or repairs a database.
    """
    def __init__(self, path: Path):
        self.path = path
        self.identity = (path.stat().st_dev, path.stat().st_ino)

    @_contextmanager
    def transaction(self):
        if (self.path.stat().st_dev, self.path.stat().st_ino) != self.identity:
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        with _closing(sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True,
                                     timeout=1, isolation_level=None)) as db:
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA synchronous=FULL")
            if (db.execute("PRAGMA application_id").fetchone()[0] != _SERVICE_APP_ID
                or db.execute("PRAGMA user_version").fetchone()[0] != 1
                or db.execute("PRAGMA journal_mode").fetchone()[0] != "delete"):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                if (self.path.stat().st_dev, self.path.stat().st_ino) != self.identity:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def reserve(self, request: dict, action_sha256: str) -> str:
        binding = request["binding"]
        # The same nonce cannot authorize another action, run or epoch. Permit
        # and final review are separate stages of one action, in one ledger.
        nonce_key = request["operation"] + ":" + binding["nonce_sha256"]
        try:
            with self.transaction() as db:
                db.execute("INSERT INTO journal VALUES(?,?,?,?,?,?,NULL)", (
                    nonce_key, action_sha256, _digest(_broker_canonical(binding)).hexdigest(),
                    request["challenge"], "RESERVED", int(_time.time()),
                ))
        except sqlite3.IntegrityError:
            raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED") from None
        return nonce_key

    def finish(self, nonce_key: str, response: bytes, *, approved: bool) -> None:
        with self.transaction() as db:
            changed = db.execute(
                "UPDATE journal SET state=?,response=? WHERE nonce_key=? AND state='RESERVED'",
                ("COMPLETED" if approved else "DENIED", response, nonce_key),
            ).rowcount
            if changed != 1:
                raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")


def _read_service_scope(path: Path, binding: dict, role: str, operation: str) -> dict:
    """Read live administrator-protected plan/lease policy; never caller flags."""
    from my_local_ai.security.codeshield_contracts import checked_relative_path
    with _closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        if (db.execute("PRAGMA application_id").fetchone()[0] != _AUTHORITY_APP_ID
            or db.execute("PRAGMA user_version").fetchone()[0] != 1):
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        row = db.execute(
            "SELECT binding_json,scope_json,expires_at,revoked FROM scopes WHERE consent_ref=?",
            (binding["owner_consent_ref"],),
        ).fetchone()
    if (row is None or type(row[2]) is not int or row[2] <= int(_time.time())
        or row[3] != 0 or _broker_decode(row[0].encode("ascii")) != binding):
        raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
    scope = _broker_decode(row[1].encode("ascii"))
    if (set(scope) != {"repository_path", "disposable_root", "allowed_paths",
                      "operations", "data_class", "plan_sha256"}
        or scope["data_class"] != "PUBLIC_SYNTHETIC"
        or scope["plan_sha256"] != binding["plan_sha256"]
        or type(scope["operations"]) is not list
        or role + ":" + operation not in scope["operations"]
        or not set(scope["operations"]) <= {"reviewer:review", "scanner:defender"}
        or type(scope["allowed_paths"]) is not list
        or not 1 <= len(scope["allowed_paths"]) <= 16):
        raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
    paths = [checked_relative_path(value) for value in scope["allowed_paths"]]
    if paths != sorted(paths) or len(set(value.casefold() for value in paths)) != len(paths):
        raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
    for key in ("repository_path", "disposable_root"):
        value = scope[key]
        if (type(value) is not str or not Path(value).is_absolute()
            or value.startswith(("\\\\", "//")) or ".." in Path(value).parts):
            raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
    if Path(scope["repository_path"]) == Path(scope["disposable_root"]):
        raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
    return scope


class _WindowsProtectedServiceAPI(_WindowsBrokerAPI):
    """SCM/pipe/TPM native server backend. No provisioning APIs are used."""
    def __init__(self, role: str):
        super().__init__()
        if role not in _SERVICE_ROLES:
            raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
        self.role = role
        self.roots = self.load_roots()
        self.resources = _ExitStack()
        c, w = self.c, self.w
        current = self._bind(self.kernel, "GetCurrentProcess", [], w.HANDLE)
        if self.process_sid(current()) != self.roots[role][0]:
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        self.settings = self._settings()
        self.authority_path = _SERVICE_HOME / "authority.sqlite3"
        self.ledger_path = _SERVICE_HOME / role / "journal.sqlite3"
        self.pin_path(self.authority_path, writable=True)
        self.pin_path(self.ledger_path, private=True, writable=True)
        for database in (self.authority_path, self.ledger_path):
            for suffix in ("-wal", "-shm", "-journal"):
                if Path(str(database) + suffix).exists():
                    raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        # A pinned EXE must not import its implementation/DLLs from a writable
        # temp extraction directory. Only a protected one-folder frozen bundle
        # is accepted; all shipped files remain pinned for the service lifetime.
        import os
        import sys
        bundle = Path(getattr(sys, "_MEIPASS", ""))
        image_parent = Path(sys.executable).parent
        if not bundle.is_absolute() or bundle.parent != image_parent or bundle.name != "_internal":
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        total, count = 0, 0
        for directory, subdirs, files in os.walk(bundle, followlinks=False):
            for name in (*subdirs, *files):
                node = Path(directory) / name
                info = node.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & _REPARSE:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            for name in files:
                path = Path(directory) / name
                count += 1
                total += path.stat().st_size
                if count > 2048 or total > 512 * 1024 * 1024:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                self.pin_path(path)

    def close(self):
        self.resources.close()

    def _settings(self) -> dict:
        import re
        import winreg
        base = r"SOFTWARE\MyLocalAI\ProtectedBrokers\v1"
        values = {}
        for sub, names in ((base, ("ControllerSid", "InteractiveOwnerSid", "OwnerSessionId")),
                           (base + "\\" + self.role, ("KeyName",))):
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub, 0,
                                winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                for name in names:
                    value, kind = winreg.QueryValueEx(key, name)
                    if name == "OwnerSessionId":
                        if kind != winreg.REG_DWORD or type(value) is not int or not 1 <= value < 65536:
                            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                    elif kind != winreg.REG_SZ or type(value) is not str:
                        raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                    values[name] = value
        for name in ("ControllerSid", "InteractiveOwnerSid"):
            if re.fullmatch(r"S-1-5-21-(?:[0-9]+-){3}[0-9]+", values[name]) is None:
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        if (len({values["ControllerSid"], values["InteractiveOwnerSid"],
                 *(entry[0] for entry in self.roots.values())}) != 5
            or re.fullmatch(r"MyLocalAI\.[A-Za-z0-9_.-]{3,64}", values["KeyName"]) is None):
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        return values

    def pin_path(self, path: Path, *, private=False, writable=False):
        """Retain non-delete shared handles to the file and every ancestor."""
        c, w = self.c, self.w
        if not path.is_absolute() or str(path).startswith("\\\\"):
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        create = self._bind(self.kernel, "CreateFileW", [w.LPCWSTR, w.DWORD,
            w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE], w.HANDLE)
        private_root = _SERVICE_HOME / self.role
        for node in (path, *path.parents):
            info = node.lstat()
            if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & _REPARSE
                or node == path and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            is_private = private and (node == private_root or private_root in node.parents)
            handle = create(str(node), 0x20000, 3 if writable else 1, None, 3, 0x02200000, None)
            if handle in (None, c.c_void_p(-1).value):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            self.resources.callback(self.kernel.CloseHandle, handle)
            self.check_acl(handle, 1, 0xD0000 | 0x156 | 0x50000000,
                           allowed_writers=(self.roots[self.role][0],) if is_private else (),
                           allowed_owners=(self.roots[self.role][0],) if is_private else ())

    def lock_untrusted_input(self, path: Path):
        """Pin untrusted file/ancestry against write/delete; this grants no trust."""
        c, w = self.c, self.w
        create = self._bind(self.kernel, "CreateFileW", [w.LPCWSTR, w.DWORD,
            w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE], w.HANDLE)
        identities = []
        for node in (path, *path.parents):
            before = node.lstat()
            if (stat.S_ISLNK(before.st_mode) or getattr(before, "st_file_attributes", 0) & _REPARSE
                or node == path and (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1)):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            handle = create(str(node), 0x80000000 if node == path else 0x20000,
                            1, None, 3, 0x02200000, None)
            if handle in (None, c.c_void_p(-1).value):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            self.resources.callback(self.kernel.CloseHandle, handle)
            after = node.lstat()
            if (before.st_dev, before.st_ino, before.st_mode) != (after.st_dev, after.st_ino, after.st_mode):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            identities.append((node, before.st_dev, before.st_ino, before.st_mode))
        for node, device, inode, mode in identities:
            current = node.lstat()
            if (current.st_dev, current.st_ino, current.st_mode) != (device, inode, mode):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")

    def _key_acl(self, raw: bytes):
        """Restrict existing key use to its service SID and system administrators."""
        c, w = self.c, self.w
        descriptor = c.create_string_buffer(raw)
        owner, dacl = c.c_void_p(), c.c_void_p()
        defaulted, present = w.BOOL(), w.BOOL()
        get_owner = self._bind(self.advapi, "GetSecurityDescriptorOwner",
            [c.c_void_p, c.POINTER(c.c_void_p), c.POINTER(w.BOOL)], w.BOOL)
        get_dacl = self._bind(self.advapi, "GetSecurityDescriptorDacl",
            [c.c_void_p, c.POINTER(w.BOOL), c.POINTER(c.c_void_p), c.POINTER(w.BOOL)], w.BOOL)
        if (not get_owner(descriptor, c.byref(owner), c.byref(defaulted))
            or self.sid_string(owner) not in _SYSTEM_TRUSTED_SIDS
            or not get_dacl(descriptor, c.byref(present), c.byref(dacl), c.byref(defaulted))
            or not present.value or not dacl.value):
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        count = w.WORD.from_address(dacl.value + 4).value
        get_ace = self._bind(self.advapi, "GetAce",
            [c.c_void_p, w.DWORD, c.POINTER(c.c_void_p)], w.BOOL)
        allowed = _SYSTEM_TRUSTED_SIDS | {self.roots[self.role][0]}
        for index in range(count):
            ace = c.c_void_p()
            if not get_ace(dacl, index, c.byref(ace)):
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            kind = c.c_ubyte.from_address(ace.value).value
            if kind == 1 or c.c_ubyte.from_address(ace.value + 1).value & 8:
                continue
            if kind != 0 or self.sid_string(ace.value + 8) not in allowed:
                raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")

    @_contextmanager
    def signer(self):
        """Open an EXISTING TPM ECDSA key; private material never enters Python."""
        c, w = self.c, self.w
        ncrypt = c.WinDLL("ncrypt.dll", use_last_error=True, winmode=0x800)
        handle_type = c.c_size_t
        provider, key = handle_type(), handle_type()
        free = self._bind(ncrypt, "NCryptFreeObject", [handle_type], c.c_long)
        open_provider = self._bind(ncrypt, "NCryptOpenStorageProvider",
            [c.POINTER(handle_type), w.LPCWSTR, w.DWORD], c.c_long)
        open_key = self._bind(ncrypt, "NCryptOpenKey",
            [handle_type, c.POINTER(handle_type), w.LPCWSTR, w.DWORD, w.DWORD], c.c_long)
        get = self._bind(ncrypt, "NCryptGetProperty", [handle_type, w.LPCWSTR,
            c.c_void_p, w.DWORD, c.POINTER(w.DWORD), w.DWORD], c.c_long)
        export = self._bind(ncrypt, "NCryptExportKey", [handle_type, handle_type,
            w.LPCWSTR, c.c_void_p, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), w.DWORD], c.c_long)
        sign = self._bind(ncrypt, "NCryptSignHash", [handle_type, c.c_void_p,
            c.c_void_p, w.DWORD, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), w.DWORD], c.c_long)
        try:
            if (open_provider(c.byref(provider), "Microsoft Platform Crypto Provider", 0) != 0
                or open_key(provider, c.byref(key), self.settings["KeyName"], 0, 0x60) != 0):
                raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")
            def prop(name, flags=0x40):
                length = w.DWORD()
                if get(key, name, None, 0, c.byref(length), flags) != 0 or not 1 <= length.value <= 65536:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")
                buf = c.create_string_buffer(length.value)
                if get(key, name, buf, len(buf), c.byref(length), flags) != 0:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")
                return buf.raw[:length.value]
            if (int.from_bytes(prop("Export Policy"), "little") != 0
                or int.from_bytes(prop("Length"), "little") != 256
                or prop("Algorithm Name").decode("utf-16-le").rstrip("\x00") != "ECDSA_P256"):
                raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")
            self._key_acl(prop("Security Descr", 5 | 0x40))
            public, length = c.create_string_buffer(72), w.DWORD()
            if (export(key, 0, "ECCPUBLICBLOB", None, public, len(public), c.byref(length), 0) != 0
                or length.value != 72 or public.raw != self.roots[self.role][2]):
                raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")
            def sign_body(body: dict) -> bytes:
                digest = _digest(b"mla-protected-broker/v1|" + _broker_canonical(body)).digest()
                output, size = c.create_string_buffer(64), w.DWORD()
                if (sign(key, None, c.create_string_buffer(digest), 32,
                         output, 64, c.byref(size), 0x40) != 0 or size.value != 64):
                    raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")
                self.verify_signature(public.raw, _broker_canonical(body), output.raw)
                return output.raw
            yield sign_body
        finally:
            if key.value:
                free(key)
            if provider.value:
                free(provider)

    def confirm_owner(self, action: dict, scope: dict) -> bool:
        """Show the entire ASCII-escaped action to a separately pinned desktop.

        No process input boolean is an approval. Missing WTS permission, a
        disconnected/replaced session, No/close/timeout all deny. The owner
        desktop SID is required to differ from the Controller and all services.
        """
        c, w = self.c, self.w
        wts = c.WinDLL("wtsapi32.dll", use_last_error=True, winmode=0x800)
        query = self._bind(wts, "WTSQuerySessionInformationW", [w.HANDLE, w.DWORD,
            c.c_int, c.POINTER(c.c_void_p), c.POINTER(w.DWORD)], w.BOOL)
        free = self._bind(wts, "WTSFreeMemory", [c.c_void_p], None)
        session = self.settings["OwnerSessionId"]
        def session_owner():
            state, size = c.c_void_p(), w.DWORD()
            if not query(None, session, 8, c.byref(state), c.byref(size)):
                raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
            try:
                if size.value != 4 or c.cast(state, c.POINTER(w.DWORD))[0] != 0:
                    raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
            finally:
                free(state)
            strings = []
            for kind in (7, 5):  # WTSDomainName, WTSUserName
                buf, size = c.c_void_p(), w.DWORD()
                if not query(None, session, kind, c.byref(buf), c.byref(size)):
                    raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
                try:
                    strings.append(c.wstring_at(buf))
                finally:
                    free(buf)
            if not all(strings):
                raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
            lookup = self._bind(self.advapi, "LookupAccountNameW", [w.LPCWSTR, w.LPCWSTR,
                c.c_void_p, c.POINTER(w.DWORD), w.LPWSTR, c.POINTER(w.DWORD), c.POINTER(w.DWORD)], w.BOOL)
            sid_size, domain_size, use = w.DWORD(), w.DWORD(), w.DWORD()
            name = "\\".join(strings)
            lookup(None, name, None, c.byref(sid_size), None, c.byref(domain_size), c.byref(use))
            if not 1 <= sid_size.value <= 1024 or not 1 <= domain_size.value <= 1024:
                raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
            sid, domain = c.create_string_buffer(sid_size.value), c.create_unicode_buffer(domain_size.value)
            if not lookup(None, name, sid, c.byref(sid_size), domain, c.byref(domain_size), c.byref(use)):
                raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
            return self.sid_string(sid)
        before = session_owner()
        if before != self.settings["InteractiveOwnerSid"]:
            return False
        text = _broker_canonical({"action": action, "approved_scope": scope}).decode("ascii")
        if len(text) > 16000:
            return False  # No truncation of the operation being approved.
        title = "My Local AI: approve ONE static action (default: No)"
        send = self._bind(wts, "WTSSendMessageW", [w.HANDLE, w.DWORD, w.LPWSTR,
            w.DWORD, w.LPWSTR, w.DWORD, w.DWORD, w.DWORD, c.POINTER(w.DWORD), w.BOOL], w.BOOL)
        response = w.DWORD()
        ok = send(None, session, title, len(title.encode("utf-16-le")), text,
                  len(text.encode("utf-16-le")), 0x104 | 0x30, 20, c.byref(response), True)
        return bool(ok and response.value == 6 and session_owner() == before)


class _ProtectedActionServer:
    """One authenticated request -> live policy -> durable nonce -> signed result."""
    def __init__(self, api: _WindowsProtectedServiceAPI, sign_body, stopped):
        self.api, self.sign_body, self.stopped = api, sign_body, stopped
        self.role = api.role
        self.journal = _ServiceJournal(api.ledger_path)

    def live_scope(self, binding, action):
        if self.stopped.is_set():
            raise ProtectedBrokerHold("PROTECTED_BROKER_UNAVAILABLE")
        return _read_service_scope(self.api.authority_path, binding,
                                   action["role"], action["operation"])

    def signed_response(self, request, raw, result, status, *, lease_expires_at=None):
        now = int(_time.time())
        expires_at = min(now + 30, lease_expires_at) if lease_expires_at is not None else now + 30
        if expires_at <= now:
            raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
        body = {"schema": "mla-protected-response/v1", "role": self.role,
                "operation": request["operation"], "request_sha256": _digest(raw).hexdigest(),
                "challenge": request["challenge"], "binding": request["binding"],
                "issued_at": now, "expires_at": expires_at, "status": status, "result": result}
        return _broker_canonical({"body": body,
            "signature": _b64.b64encode(self.sign_body(body)).decode("ascii")})

    def verify_grant(self, token: str, role: str, binding: dict) -> dict:
        if type(token) is not str or not 1 <= len(token) <= _BROKER_LIMIT:
            raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
        envelope = _broker_decode(_b64.b64decode(token, validate=True))
        if set(envelope) != {"body", "signature"} or type(envelope["body"]) is not dict:
            raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
        body = envelope["body"]
        if (set(body) != {"schema", "role", "operation", "request_sha256", "challenge",
                         "binding", "issued_at", "expires_at", "status", "result"}
            or body["schema"] != "mla-protected-response/v1" or body["role"] != role
            or body["binding"] != binding or body["status"] != "OK"
            or type(body["result"]) is not dict or type(body["issued_at"]) is not int
            or type(body["expires_at"]) is not int
            or not body["issued_at"] <= int(_time.time()) < body["expires_at"]
            or not 1 <= body["expires_at"] - body["issued_at"] <= 30):
            raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
        _validate_broker_binding(body["binding"])
        signature = _b64.b64decode(envelope["signature"], validate=True)
        self.api.verify_signature(self.api.roots[role][2], _broker_canonical(body), signature)
        return body

    def action_from_owner(self, payload, binding, action):
        owner = self.verify_grant(payload["owner_authorization"], "owner", binding)
        expected = {"action_sha256": payload["action_sha256"], "decision": "APPROVED_SINGLE_USE",
                    "nonce_state": "CONSUMED", "lease_state": "LIVE_AT_SIGNING"}
        if owner["operation"] != "authorize" or owner["result"] != expected:
            raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
        original = {"schema": "mla-protected-request/v1", "role": "owner",
                    "operation": "authorize", "binding": binding,
                    "challenge": owner["challenge"], "payload": {
                        "action_sha256": payload["action_sha256"], "action": action}}
        if owner["request_sha256"] != _digest(_broker_canonical(original)).hexdigest():
            raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
        return owner

    def process(self, raw: bytes) -> bytes:
        request = _service_request(raw, self.role)
        payload, binding, op = request["payload"], request["binding"], request["operation"]
        nonce_key = None
        try:
            if self.role == "owner":
                if set(payload) != {"action_sha256", "action"}:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
                action = payload["action"]
                if (type(action) is not dict or set(action) != {"role", "operation", "binding", "payload"}
                    or action["binding"] != binding or type(action["payload"]) is not dict
                    or (action["role"], action["operation"]) not in {
                        ("reviewer", "review"), ("scanner", "defender")}):
                    raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
                digest = _digest(_broker_canonical(action)).hexdigest()
                if payload["action_sha256"] != digest:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
                scope = self.live_scope(binding, action)
                nonce_key = self.journal.reserve(request, digest)
                if not self.api.confirm_owner(action, scope):
                    raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
                self.live_scope(binding, action)  # Revocation during UI wins.
                result = {"action_sha256": digest, "decision": "APPROVED_SINGLE_USE",
                          "nonce_state": "CONSUMED", "lease_state": "LIVE_AT_SIGNING"}
            elif self.role == "reviewer" and op == "runtime-permit":
                if set(payload) != {"action_sha256", "action", "owner_authorization"}:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
                action = payload["action"]
                if (type(action) is not dict
                    or set(action) != {"role", "operation", "binding", "payload"}
                    or action["binding"] != binding
                    or _digest(_broker_canonical(action)).hexdigest() != payload["action_sha256"]):
                    raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
                self.action_from_owner(payload, binding, action)
                self.live_scope(binding, action)
                # Runtime permit authorizes fixed STATIC operations only; it
                # does not permit code/test execution, even if owner approved.
                digest = payload["action_sha256"]
                nonce_key = self.journal.reserve(request, digest)
                result = {"action_sha256": digest, "decision": "RUNTIME_BOUNDARY_APPROVED",
                          "nonce_state": "LIVE_FOR_REVIEW", "lease_state": "LIVE_AT_SIGNING"}
            else:
                if set(payload) != {"action_sha256", "input", "owner_authorization", "runtime_permit"}:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
                action = {"role": self.role, "operation": op, "binding": binding, "payload": payload["input"]}
                digest = _digest(_broker_canonical(action)).hexdigest()
                if digest != payload["action_sha256"]:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
                self.action_from_owner(payload, binding, action)
                permit = self.verify_grant(payload["runtime_permit"], "reviewer", binding)
                if (permit["operation"] != "runtime-permit" or permit["result"] != {
                    "action_sha256": digest, "decision": "RUNTIME_BOUNDARY_APPROVED",
                    "nonce_state": "LIVE_FOR_REVIEW", "lease_state": "LIVE_AT_SIGNING"}):
                    raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
                permit_request = {"schema": "mla-protected-request/v1", "role": "reviewer",
                    "operation": "runtime-permit", "binding": binding,
                    "challenge": permit["challenge"], "payload": {
                        "action_sha256": digest, "action": action,
                        "owner_authorization": payload["owner_authorization"]}}
                if permit["request_sha256"] != _digest(_broker_canonical(permit_request)).hexdigest():
                    raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
                scope = self.live_scope(binding, action)
                nonce_key = self.journal.reserve(request, digest)
                if (self.role, op) == ("reviewer", "review"):
                    from my_local_ai.review.protected_reviewer import _serve_static_review
                    result = _serve_static_review(self.api, binding, payload["input"], scope, self.stopped)
                elif (self.role, op) == ("scanner", "defender"):
                    from my_local_ai.security.defender_status import _serve_defender_scan
                    result = _serve_defender_scan(self.api, binding, payload["input"], scope, self.stopped)
                else:
                    raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
                self.live_scope(binding, action)  # Check lease again at signing.
            # DELETE-mode authority DB: a read transaction holds a SHARED lock
            # through signature + journal commit, so revocation cannot commit
            # between the live lease check and durable result issuance.
            with _closing(sqlite3.connect(self.api.authority_path.as_uri() + "?mode=ro",
                                          uri=True, timeout=1)) as authority:
                authority.execute("PRAGMA query_only=ON")
                authority.execute("BEGIN")
                lease = authority.execute(
                    "SELECT expires_at FROM scopes WHERE consent_ref=?", (binding["owner_consent_ref"],)
                ).fetchone()
                if not lease or authority.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
                    raise ProtectedBrokerHold("PROTECTED_OWNER_ACTION_DENIED")
                self.live_scope(binding, action)
                response = self.signed_response(request, raw, result, "OK", lease_expires_at=lease[0])
                self.journal.finish(nonce_key, response, approved=True)
            return response
        except (ProtectedBrokerHold, sqlite3.Error, OSError, ValueError,
                TypeError, KeyError, OverflowError, SyntaxError, RecursionError, MemoryError):
            response = self.signed_response(request, raw, {"reason": "PROTECTED_ACTION_HOLD"}, "DENIED")
            if nonce_key is not None:
                self.journal.finish(nonce_key, response, approved=False)
            return response


def protected_service_main(role: str) -> int:
    """SCM entry for a separately frozen EXE. Never starts/installs a service.

    Package each role with this function as its zero-argument entry point.
    SCM ImagePath must be exactly that EXE, matching the existing client check.
    Plain Python, command-line role selection and developer foreground mode
    cannot act as production services. Every OS precondition is fail-closed.
    """
    import os
    import sys
    import threading
    if os.name != "nt" or role not in _SERVICE_ROLES or not getattr(sys, "frozen", False):
        raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
    import ctypes as c
    from ctypes import wintypes as w
    advapi = c.WinDLL("advapi32.dll", use_last_error=True, winmode=0x800)
    status_handle = None
    stopped = threading.Event()
    main_type = c.WINFUNCTYPE(None, w.DWORD, c.POINTER(w.LPWSTR))
    control_type = c.WINFUNCTYPE(w.DWORD, w.DWORD, w.DWORD, c.c_void_p, c.c_void_p)
    class Status(c.Structure):
        _fields_ = [(name, w.DWORD) for name in (
            "kind", "state", "accepted", "exit", "specific", "checkpoint", "wait_hint")]
    set_status = _WindowsBrokerAPI._bind(advapi, "SetServiceStatus", [w.HANDLE, c.POINTER(Status)], w.BOOL)
    def report(state, error=0):
        status = Status(0x10, state, 1 if state == 4 else 0, error, 0,
                        1 if state in (2, 3) else 0, 25000 if state in (2, 3) else 0)
        if status_handle and not set_status(status_handle, c.byref(status)):
            stopped.set()
    @control_type
    def control(code, event, data, context):
        if code in (1, 5):
            stopped.set()
            report(3)
        return 0
    @main_type
    def main(argc, argv):
        nonlocal status_handle
        register = _WindowsBrokerAPI._bind(advapi, "RegisterServiceCtrlHandlerExW",
            [w.LPCWSTR, control_type, c.c_void_p], w.HANDLE)
        status_handle = register("MyLocalAI." + role + ".v1", control, None)
        if not status_handle:
            return
        report(2)
        try:
            api = _WindowsProtectedServiceAPI(role)
            try:
                # StartServiceCtrlDispatcher/ServiceMain have completed before
                # opening CNG (NCrypt in a dispatcher initialization can lock).
                report(4)
                with api.signer() as sign_body:
                    server = _ProtectedActionServer(api, sign_body, stopped)
                    _serve_named_pipe(api, server, stopped)
            finally:
                api.close()
        except Exception:
            report(1, 1066)
            return
        report(1)
    class Entry(c.Structure):
        _fields_ = [("name", w.LPWSTR), ("main", main_type)]
    table = (Entry * 2)()
    table[0] = Entry("MyLocalAI." + role + ".v1", main)
    dispatch = _WindowsBrokerAPI._bind(advapi, "StartServiceCtrlDispatcherW", [c.POINTER(Entry)], w.BOOL)
    if not dispatch(table):
        raise ProtectedBrokerHold("PROTECTED_BROKER_UNAVAILABLE")
    return 0


def _run_bounded_fixed_process(argv, *, cwd, env, timeout_seconds, stopped, output_limit):
    """Native product operator only. Bounded capture, deadline/stop, reaped child.

    Callers, not external requests, construct argv from fixed operator schemas.
    No shell, inherited stdin, environment, handles, or generated executable.
    """
    import subprocess
    import threading
    process = subprocess.Popen(argv, cwd=str(cwd), env=env, shell=False,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        close_fds=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    overflow = threading.Event()
    buffers = [bytearray(), bytearray()]
    lock = threading.Lock()
    def drain(stream, index):
        try:
            while chunk := stream.read(8192):
                with lock:
                    if sum(map(len, buffers)) + len(chunk) > output_limit:
                        overflow.set()
                    elif not overflow.is_set():
                        buffers[index].extend(chunk)
        finally:
            stream.close()
    threads = [threading.Thread(target=drain, args=(stream, index), daemon=True)
               for index, stream in enumerate((process.stdout, process.stderr))]
    for thread in threads:
        thread.start()
    deadline = _time.monotonic() + timeout_seconds
    timed_out = False
    try:
        while process.poll() is None:
            if stopped.is_set() or _time.monotonic() >= deadline or overflow.is_set():
                timed_out = not overflow.is_set()
                process.kill()
                break
            stopped.wait(0.02)
        process.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=2)
        if overflow.is_set() or any(thread.is_alive() for thread in threads):
            raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
        return process.returncode, bytes(buffers[0]), bytes(buffers[1]), timed_out
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def _serve_named_pipe(api, server, stopped):
    """Fixed local, single-instance pipe; overlapped I/O with stop/deadline.

    FOUR-byte little-endian byte length then canonical JSON matches transact.
    Client identity is checked by OS PID/token before reading the request.
    IO cancellation is reaped before freeing OVERLAPPED/buffer memory.
    """
    c, w = api.c, api.w
    class Overlapped(c.Structure):
        _fields_ = [("internal", c.c_size_t), ("internal_high", c.c_size_t),
                    ("offset", w.DWORD), ("offset_high", w.DWORD), ("event", w.HANDLE)]
    class Attributes(c.Structure):
        _fields_ = [("length", w.DWORD), ("descriptor", c.c_void_p), ("inherit", w.BOOL)]
    convert = api._bind(api.advapi, "ConvertStringSecurityDescriptorToSecurityDescriptorW",
        [w.LPCWSTR, w.DWORD, c.POINTER(c.c_void_p), c.c_void_p], w.BOOL)
    create = api._bind(api.kernel, "CreateNamedPipeW", [w.LPCWSTR, w.DWORD,
        w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, c.POINTER(Attributes)], w.HANDLE)
    connect = api._bind(api.kernel, "ConnectNamedPipe", [w.HANDLE, c.POINTER(Overlapped)], w.BOOL)
    disconnect = api._bind(api.kernel, "DisconnectNamedPipe", [w.HANDLE], w.BOOL)
    make_event = api._bind(api.kernel, "CreateEventW", [c.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR], w.HANDLE)
    wait = api._bind(api.kernel, "WaitForSingleObject", [w.HANDLE, w.DWORD], w.DWORD)
    cancel = api._bind(api.kernel, "CancelIoEx", [w.HANDLE, c.POINTER(Overlapped)], w.BOOL)
    complete = api._bind(api.kernel, "GetOverlappedResult",
        [w.HANDLE, c.POINTER(Overlapped), c.POINTER(w.DWORD), w.BOOL], w.BOOL)
    # Specific read/write rights exclude FILE_CREATE_PIPE_INSTANCE (0x4).
    sid = api.settings["ControllerSid"]
    sddl = "D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;" + api.roots[api.role][0] + ")"
    sddl += "(A;;0x0012019b;;;" + sid + ")"
    descriptor = c.c_void_p()
    if not convert(sddl, 1, c.byref(descriptor), None):
        raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
    pipe = None
    try:
        attrs = Attributes(c.sizeof(Attributes), descriptor, False)
        pipe = create(r"\\.\pipe\MyLocalAI.v1." + api.role,
                      3 | 0x40000000 | 0x80000, 8, 1, 65536, 65536, 1000, c.byref(attrs))
        if pipe in (None, c.c_void_p(-1).value):
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        with api.authenticate_pipe(pipe, api.role, api.roots, service_self=True):
            frame_deadline = 0.0
            def operation(fn, buf=None, size=0, *, connecting=False):
                if not connecting and (stopped.is_set() or _time.monotonic() >= frame_deadline):
                    raise ProtectedBrokerHold("PROTECTED_BROKER_TIMEOUT")
                ov, count = Overlapped(), w.DWORD()
                ov.event = make_event(None, True, False, None)
                if not ov.event:
                    raise ProtectedBrokerHold()
                try:
                    ok = fn(pipe, c.byref(ov)) if connecting else fn(pipe, buf, size, c.byref(count), c.byref(ov))
                    if not ok:
                        error = c.get_last_error()
                        if connecting and error == 535:  # ERROR_PIPE_CONNECTED
                            return 0
                        if error != 997:
                            raise ProtectedBrokerHold()
                        deadline = (_time.monotonic() + 3600 if connecting else frame_deadline)
                        waited = wait(ov.event, 100)
                        while waited == 258:
                            if stopped.is_set() or _time.monotonic() >= deadline:
                                cancel(pipe, c.byref(ov))
                                complete(pipe, c.byref(ov), c.byref(count), True)
                                raise ProtectedBrokerHold("PROTECTED_BROKER_TIMEOUT")
                            waited = wait(ov.event, 100)
                        if waited != 0:
                            cancel(pipe, c.byref(ov))
                            complete(pipe, c.byref(ov), c.byref(count), True)
                            raise ProtectedBrokerHold("PROTECTED_BROKER_UNAVAILABLE")
                        if not complete(pipe, c.byref(ov), c.byref(count), False):
                            raise ProtectedBrokerHold()
                    return count.value
                finally:
                    api.kernel.CloseHandle(ov.event)
            read = api._bind(api.kernel, "ReadFile", [w.HANDLE, c.c_void_p, w.DWORD,
                c.POINTER(w.DWORD), c.POINTER(Overlapped)], w.BOOL)
            write = api._bind(api.kernel, "WriteFile", [w.HANDLE, c.c_void_p, w.DWORD,
                c.POINTER(w.DWORD), c.POINTER(Overlapped)], w.BOOL)
            pid_fn = api._bind(api.kernel, "GetNamedPipeClientProcessId",
                [w.HANDLE, c.POINTER(w.ULONG)], w.BOOL)
            open_process = api._bind(api.kernel, "OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
            def exact(size):
                parts = bytearray()
                while len(parts) < size:
                    buf = c.create_string_buffer(min(size - len(parts), 65536))
                    count = operation(read, buf, len(buf))
                    if not 1 <= count <= len(buf):
                        raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
                    parts.extend(buf.raw[:count])
                return bytes(parts)
            while not stopped.is_set():
                try:
                    operation(connect, connecting=True)
                    frame_deadline = _time.monotonic() + 10
                    pid = w.ULONG()
                    if not pid_fn(pipe, c.byref(pid)) or not pid.value:
                        raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                    peer = open_process(0x1000 | 0x100000, False, pid.value)
                    if not peer:
                        raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                    try:
                        if api.process_sid(peer) != sid:
                            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                        length = int.from_bytes(exact(4), "little")
                        if not 1 <= length <= _BROKER_LIMIT:
                            raise ProtectedBrokerHold("PROTECTED_BROKER_PROTOCOL")
                        response = server.process(exact(length))
                        frame_deadline = _time.monotonic() + 10
                        packet = len(response).to_bytes(4, "little") + response
                        pos = 0
                        while pos < len(packet):
                            buf = c.create_string_buffer(packet[pos:pos + 65536])
                            count = operation(write, buf, min(65536, len(packet) - pos))
                            if count == 0:
                                raise ProtectedBrokerHold()
                            pos += count
                    finally:
                        api.kernel.CloseHandle(peer)
                except ProtectedBrokerHold:
                    pass  # Invalid transport gets disconnected, never a grant.
                finally:
                    disconnect(pipe)
    finally:
        if pipe not in (None, c.c_void_p(-1).value):
            api.kernel.CloseHandle(pipe)
        api.kernel.LocalFree(descriptor)


if __name__ == "__main__":
    import sys
    if getattr(sys, "frozen", False):
        raise SystemExit(protected_service_main("owner"))
    raise SystemExit(_owner_token_read_only_main())
