"""Host-side Windows Sandbox no-egress profile source (not a guest launcher).

The network-disabled .wsb manifest is an auditable boundary *request*, not
evidence that Windows applied it. The current owner OS_CHANGE signer denies
launch, and the Windows Sandbox CLI does not return guest process stdout.
Do not map owner checkout, secrets or a writeable host folder into a guest.
Actual host/guest command execution and independent F18 review are BLOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import stat
from xml.etree import ElementTree as ET

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

# Windows Sandbox WSB defaults allow networking and clipboard. Every
# profile below instead hard-disables network, clipboard, host filesystem
# mapping, audio/video, printing and vGPU. Never rely on defaults.
_NO_EGRESS_OPTIONS = (
    ("vGPU", "Disable"),
    ("Networking", "Disable"),
    ("AudioInput", "Disable"),
    ("VideoInput", "Disable"),
    ("ProtectedClient", "Enable"),
    ("PrinterRedirection", "Disable"),
    ("ClipboardRedirection", "Disable"),
)


class WindowsIsolationHold(ValueError):
    def __init__(self, reason: str = "WINDOWS_HOST_ISOLATION_NOT_ATTESTED"):
        self.code = reason if reason in {
            "WINDOWS_HOST_ISOLATION_NOT_ATTESTED",
            "INVALID_SANDBOX_SCOPE",
            "UNSAFE_GUEST_CONFIG",
            "NETWORK_EGRESS_UNVERIFIED",
            "OWNER_SIGNER_NOT_AVAILABLE",
        } else "WINDOWS_HOST_ISOLATION_NOT_ATTESTED"
        super().__init__(self.code)


@dataclass(frozen=True)
class WindowsNoEgressProfile:
    task_id: str
    run_id: str
    role: str
    source_sha: str
    plan_sha256: str
    config_xml: str
    config_sha256: str
    state: str = "SOURCE_NO_EGRESS_PROFILE_ONLY"
    network_disabled_requested: bool = True
    host_egress_attested: bool = False
    sandbox_started: bool = False
    may_start_worker: bool = False
    may_access_owner_checkout: bool = False
    may_issue_trusted_f18: bool = False


def _no_egress_xml(*, memory_mb: int) -> str:
    if type(memory_mb) is not int or not 2048 <= memory_mb <= 8192:
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    root = ET.Element("Configuration")
    for key, val in _NO_EGRESS_OPTIONS:
        ET.SubElement(root, key).text = val
    ET.SubElement(root, "MemoryInMB").text = str(memory_mb)
    return ET.tostring(root, encoding="unicode", short_empty_elements=False)


def prepare_windows_no_egress_profile(
    *, task_id: str, run_id: str, role: str,
    source_sha: str, plan_sha256: str,
    memory_mb: int = 3072,
) -> WindowsNoEgressProfile:
    """Generate an exact immutable Sandbox XML profile for future owner use.

    No host files are created or mounted and no process or network is touched.
    The guest must later be given a sealed *public/synthetic* source package by
    a separately protected broker; this module does not pretend a read/write
    host share or raw model output is safe.
    """
    if (not isinstance(task_id, str) or not _ID.fullmatch(task_id)
        or not isinstance(run_id, str) or not _ID.fullmatch(run_id)
        or role not in ("CODER", "REVIEWER")
        or not isinstance(source_sha, str) or not _SHA40.fullmatch(source_sha)
        or not isinstance(plan_sha256, str) or not _SHA64.fullmatch(plan_sha256)):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    xml = _no_egress_xml(memory_mb=memory_mb)
    digest = sha256(
        b"mla-wsb-profile/v1|" + role.encode("ascii") + b"|" +
        task_id.encode("ascii") + b"|" + run_id.encode("ascii") + b"|" +
        source_sha.encode("ascii") + b"|" + plan_sha256.encode("ascii") +
        b"|" + xml.encode("utf-8")
    ).hexdigest()
    return WindowsNoEgressProfile(
        task_id, run_id, role, source_sha, plan_sha256, xml, digest,
    )


def audit_no_egress_profile(
    profile: WindowsNoEgressProfile, *,
    expected_task_id: str, expected_run_id: str,
    expected_role: str, expected_source_sha: str,
    expected_plan_sha256: str,
) -> str:
    """Reject altered/unsafe config; a matching XML is not host isolation."""
    if not isinstance(profile, WindowsNoEgressProfile):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    if (profile.task_id != expected_task_id
        or profile.run_id != expected_run_id
        or profile.role != expected_role
        or profile.source_sha != expected_source_sha
        or profile.plan_sha256 != expected_plan_sha256
        or profile.state != "SOURCE_NO_EGRESS_PROFILE_ONLY"
        or profile.network_disabled_requested is not True
        or profile.host_egress_attested is not False
        or profile.sandbox_started is not False
        or profile.may_start_worker is not False
        or profile.may_access_owner_checkout is not False
        or profile.may_issue_trusted_f18 is not False):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    try:
        root = ET.fromstring(profile.config_xml)
        if root.tag != "Configuration" or root.attrib:
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        parts = list(root)
        if len(parts) != len(_NO_EGRESS_OPTIONS) + 1:
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        assert_names = tuple(name for name,_ in _NO_EGRESS_OPTIONS) + ("MemoryInMB",)
        if (tuple(part.tag for part in parts) != assert_names
            or any(part.attrib or len(part) or part.tail not in (None,"")
                   for part in parts)
            or any(part.text != text
                   for part,(_,text) in zip(parts,_NO_EGRESS_OPTIONS))
            or parts[-1].text is None
            or not re.fullmatch(r"[0-9]{4}", parts[-1].text)):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        memory_mb=int(parts[-1].text)
        expected=prepare_windows_no_egress_profile(
            task_id=expected_task_id,run_id=expected_run_id,
            role=expected_role,source_sha=expected_source_sha,
            plan_sha256=expected_plan_sha256,memory_mb=memory_mb,
        )
        if profile != expected:
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    except (ET.ParseError, TypeError, ValueError):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG") from None
    # XML has no MappedFolders, LogonCommand, writeable host path, vGPU or
    # networking enable. Host-side WSB feature and runtime egress probes P2.
    return "POLICY_EXACT_MATCH_HOST_EGRESS_NOT_ATTESTED"


def inspect_windows_profile_for_execution(
    profile: WindowsNoEgressProfile, *,
    expected_task_id: str, expected_run_id: str,
    expected_role: str, expected_source_sha: str,
    expected_plan_sha256: str,
) -> None:
    """Current P1 cannot launch even an exact no-network WSB profile."""
    audit_no_egress_profile(
        profile, expected_task_id=expected_task_id,
        expected_run_id=expected_run_id, expected_role=expected_role,
        expected_source_sha=expected_source_sha,
        expected_plan_sha256=expected_plan_sha256,
    )
    raise WindowsIsolationHold("WINDOWS_HOST_ISOLATION_NOT_ATTESTED")


# SWU-015 coder -> offline Windows isolation transport. The intended
# deployment packs a *separately licensed* local model/runtime into a
# protected read-only guest image. Host Ollama on 127.0.0.1 is NOT reachable
# inside a network-disabled Sandbox, so an ordinary host-Ollama request
# cannot be executed safely by this transport.
import json as _json
from my_local_ai.contracts.task import safe_path as _safe_path
from .opencode_worker import PreparedOpenCodeRun as _PreparedOpenCodeRun


@dataclass(frozen=True)
class OfflineCoderTransport:
    task_id: str
    source_sha: str
    plan_sha256: str
    run_id: str
    profile_sha256: str
    request_sha256: str
    allowed_paths: tuple[str, ...]
    state: str = "HOST_OFFLINE_MODEL_BROKER_UNAVAILABLE"
    sandbox_started: bool = False
    model_executed: bool = False
    network_egress_attested: bool = False
    output_trusted: bool = False
    may_write_owner_checkout: bool = False
    may_issue_review_receipt: bool = False


@dataclass(frozen=True)
class UntrustedGuestOutbox:
    task_id: str
    run_id: str
    response_sha256: str
    declared_paths: tuple[str, ...]
    output_bytes: int
    state: str = "UNTRUSTED_CODER_OUTBOX_F18_REQUIRED"
    model_executed_verified: bool = False
    candidate_independently_verified: bool = False
    may_promote: bool = False


def prepare_offline_coder_transport(
    *, profile: WindowsNoEgressProfile, prepared: _PreparedOpenCodeRun,
) -> OfflineCoderTransport:
    """Bind fixed local request to no-egress configuration, fail closed.

    This does not run the host's loopback Ollama: the independent guest would
    need its own approved offline model package and protected I/O broker.
    """
    if (not isinstance(profile,WindowsNoEgressProfile)
        or profile.role != "CODER"
        or not isinstance(prepared,_PreparedOpenCodeRun)
        or prepared.untrusted is not True
        or prepared.task_id != profile.task_id
        or prepared.source_sha != profile.source_sha
        or prepared.plan_sha256 != profile.plan_sha256
        or not isinstance(prepared.worktree,str)
        or not isinstance(prepared.argv,tuple)
        or len(prepared.argv) != 10
        or prepared.argv[:8] != ("opencode","run","--standalone","--archived",
                                  "--agent","build","--model",prepared.argv[8])
        or prepared.argv[9] != prepared.prompt
        or not prepared.argv[8].startswith("ollama/qwen3:")
        or not isinstance(prepared.allowed_paths,tuple)
        or not 1 <= len(prepared.allowed_paths) <= 16
        or any(not isinstance(x,str) or _safe_path(x)!=x
               for x in prepared.allowed_paths)
        or len(set(prepared.allowed_paths)) != len(prepared.allowed_paths)):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    audit_no_egress_profile(
        profile, expected_task_id=profile.task_id,expected_run_id=profile.run_id,
        expected_role="CODER",expected_source_sha=profile.source_sha,
        expected_plan_sha256=profile.plan_sha256,
    )
    # A loopback host URL cannot reach the host from within a no-network
    # Windows guest. Preserve this gap rather than permitting wide egress.
    if (not isinstance(prepared.environment,tuple)
        or not any(k=="OLLAMA_HOST" and v.startswith(
            ("http://127.0.0.1:","http://[::1]:")
        ) for k,v in prepared.environment)):
        raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
    material=_json.dumps({
        "task_id":profile.task_id,"run_id":profile.run_id,
        "profile_sha256":profile.config_sha256,
        "source_sha":profile.source_sha,"plan_sha256":profile.plan_sha256,
        "argv":prepared.argv,"allowed_paths":prepared.allowed_paths,
        "worktree":prepared.worktree,"env":prepared.environment,
    },sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")
    return OfflineCoderTransport(
        profile.task_id,profile.source_sha,profile.plan_sha256,
        profile.run_id,profile.config_sha256,
        sha256(b"mla-coder-transport/v1|"+material).hexdigest(),
        prepared.allowed_paths,
    )


def decode_untrusted_coder_outbox(
    raw: bytes, transport: OfflineCoderTransport,
) -> UntrustedGuestOutbox:
    """Bounded, schema-closed parse of guest's *untrusted* declared result."""
    if (not isinstance(transport,OfflineCoderTransport)
        or transport.state != "HOST_OFFLINE_MODEL_BROKER_UNAVAILABLE"
        or transport.sandbox_started or transport.model_executed
        or transport.network_egress_attested or transport.output_trusted
        or transport.may_write_owner_checkout
        or transport.may_issue_review_receipt
        or not isinstance(raw,bytes) or len(raw)>65536):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    def no_dupes(pairs):
        out={}
        for k,v in pairs:
            if k in out:
                raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
            out[k]=v
        return out
    try:
        payload=_json.loads(raw.decode("utf-8"),object_pairs_hook=no_dupes,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError, RecursionError):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG") from None
    if (not isinstance(payload,dict)
        or set(payload)!={"version","task_id","run_id","transport_sha256",
                           "output_sha256","declared_paths","exit_code"}
        or type(payload["version"]) is not int or payload["version"] != 1
        or payload["task_id"] != transport.task_id
        or payload["run_id"] != transport.run_id
        or payload["transport_sha256"] != transport.request_sha256
        or not isinstance(payload["output_sha256"],str)
        or not _SHA64.fullmatch(payload["output_sha256"])
        or type(payload["exit_code"]) is not int or payload["exit_code"] != 0
        or not isinstance(payload["declared_paths"],list)
        or not 0 <= len(payload["declared_paths"]) <= len(transport.allowed_paths)):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    paths=payload["declared_paths"]
    try:
        valid=tuple(_safe_path(s) for s in paths)
    except (TypeError, ValueError):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG") from None
    if len(set(valid))!=len(valid) or not set(valid).issubset(transport.allowed_paths):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    # A successful guest exit code and self-declared SHA do not establish the
    # candidate's integrity, actual execution, independent review or OS deny.
    return UntrustedGuestOutbox(
        transport.task_id,transport.run_id,payload["output_sha256"],
        valid,len(raw),
    )


def require_host_isolated_coder_runner(transport: OfflineCoderTransport,
                                      *, protected_broker=None) -> None:
    """No Python guest-supplied port can convert a request into OS attestation."""
    if not isinstance(transport,OfflineCoderTransport):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    raise WindowsIsolationHold("OWNER_SIGNER_NOT_AVAILABLE")
