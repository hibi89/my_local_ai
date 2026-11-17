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
        or len(prepared.argv) != 11
        or prepared.argv[:7] != ("opencode","run","--standalone","--archived",
                                  "--agent","build","--model")
        or prepared.argv[8:10] != ("--format","json")
        or prepared.argv[10] != prepared.prompt
        or not isinstance(prepared.argv[7],str)
        or not prepared.argv[7].startswith("ollama/qwen3:")
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


# Host-Qwen inference is a DATA-ONLY source path. Ollama runs on the host
# loopback with no code-execution tools; guest Windows Sandbox stays offline.
# The model's returned source is always untrusted and never written here.
from my_local_ai.ax_runtime.provider_policy import (
    LoopbackEndpoint as _LoopbackEndpoint, require_qwen_model as _require_qwen_model,
    ProviderHold as _ProviderHold,
)


@dataclass(frozen=True)
class HostQwenGenerationRequest:
    task_id: str
    run_id: str
    source_sha: str
    plan_sha256: str
    transport_sha256: str
    model: str
    endpoint: str
    prompt_sha256: str
    request_sha256: str
    request_body: bytes
    state: str = "HOST_ONLY_INFERENCE_NOT_EXECUTED"
    host_inference_executed: bool = False
    guest_sandbox_executed: bool = False
    owner_source_writable: bool = False
    model_output_trusted: bool = False
    may_promote: bool = False


@dataclass(frozen=True)
class UntrustedHostQwenFiles:
    task_id: str
    run_id: str
    source_sha: str
    plan_sha256: str
    request_sha256: str
    files: tuple[tuple[str, str], ...]
    files_sha256: str
    state: str = "UNTRUSTED_HOST_MODEL_OUTPUT_F18_REQUIRED"
    files_applied_to_original: bool = False
    guest_executed: bool = False
    independent_f18_verified: bool = False
    can_publish: bool = False


def _strict_json(raw: bytes, *, limit: int) -> object:
    if not isinstance(raw, bytes) or not raw or len(raw) > limit:
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    def pairs_unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
            out[k] = v
        return out
    try:
        return _json.loads(
            raw.decode("utf-8"), object_pairs_hook=pairs_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG") from None


def prepare_host_qwen_generation(
    transport: OfflineCoderTransport, *,
    coding_request: str, classification: str = "PUBLIC_SYNTHETIC_ONLY",
    model: str = "qwen3:4b-instruct",
    endpoint_url: str = "http://127.0.0.1:11434",
) -> HostQwenGenerationRequest:
    """Create a bounded host-only Ollama /api/generate JSON request, no I/O.

    No task secret, original source, customer data, private repo content or
    credentials may be supplied in PUBLIC_SYNTHETIC_ONLY mode. The trusted
    owner must approve real private project use with a separate classification
    and OS boundary; this function intentionally rejects that scope.
    """
    if (not isinstance(transport, OfflineCoderTransport)
        or transport.state != "HOST_OFFLINE_MODEL_BROKER_UNAVAILABLE"
        or transport.model_executed or transport.sandbox_started
        or transport.network_egress_attested or transport.output_trusted
        or transport.may_write_owner_checkout or transport.may_issue_review_receipt
        or not isinstance(coding_request, str)
        or not coding_request.strip() or "\x00" in coding_request
        or len(coding_request.encode("utf-8")) > 8192
        or classification != "PUBLIC_SYNTHETIC_ONLY"):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    try:
        selected = _require_qwen_model(model)
        endpoint = _LoopbackEndpoint.parse(endpoint_url)
    except _ProviderHold:
        raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED") from None
    # Restrict this source path to a canonical IPv4 loopback URL. No proxy,
    # credentials, cloud host, DNS name, path suffix or remote provider.
    if endpoint.host != "127.0.0.1" or endpoint_url != (
        "http://127.0.0.1:" + str(endpoint.port)
    ):
        raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
    if selected != "qwen3:4b-instruct":
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    schema_hint = (
        'Return only JSON {"version":1,"files":['
        '{"path":"allowed/relative.py","content":"complete UTF-8 source"}'
        ']}. Use only these exact allowed paths: ' +
        ", ".join(transport.allowed_paths) +
        ". Do not request tools, shell, network or new file paths. Task: "
    )
    prompt = schema_hint + coding_request
    body = _json.dumps({
        "model":selected,"prompt":prompt,"stream":False,
        "format":"json",
        "options":{"temperature":0,"num_predict":2048,"num_ctx":4096},
        "keep_alive":"0",
    },ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("utf-8")
    if len(body)>14000:
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    body_hash=sha256(
        b"mla-host-qwen-request/v1|"+transport.request_sha256.encode("ascii")
        + b"|" + body
    ).hexdigest()
    return HostQwenGenerationRequest(
        transport.task_id,transport.run_id,transport.source_sha,
        transport.plan_sha256,transport.request_sha256,selected,endpoint_url,
        sha256(prompt.encode("utf-8")).hexdigest(),body_hash,body,
    )


def decode_untrusted_host_qwen_files(
    raw_ollama_response: bytes,
    request: HostQwenGenerationRequest,
    transport: OfflineCoderTransport,
) -> UntrustedHostQwenFiles:
    """Parse a host inference result into *untrusted* file changes, no writes.

    This parse does NOT assert the HTTP call occurred, whose principal ran,
    that the file contents are safe, or that guest/independent review ran.
    """
    if (not isinstance(request,HostQwenGenerationRequest)
        or not isinstance(transport,OfflineCoderTransport)
        or request.state != "HOST_ONLY_INFERENCE_NOT_EXECUTED"
        or request.host_inference_executed or request.guest_sandbox_executed
        or request.owner_source_writable or request.model_output_trusted
        or request.may_promote or request.task_id != transport.task_id
        or request.run_id != transport.run_id
        or request.source_sha != transport.source_sha
        or request.plan_sha256 != transport.plan_sha256
        or request.transport_sha256 != transport.request_sha256):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    response=_strict_json(raw_ollama_response,limit=262144)
    if (not isinstance(response,dict)
        or response.get("model") != request.model
        or response.get("done") is not True
        or not isinstance(response.get("response"),str)
        or len(response["response"].encode("utf-8")) > 131072
        or "tool_calls" in response or "message" in response):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    fileset=_strict_json(response["response"].encode("utf-8"),limit=131072)
    if (not isinstance(fileset,dict) or set(fileset)!={"version","files"}
        or type(fileset["version"]) is not int or fileset["version"]!=1
        or not isinstance(fileset["files"],list)
        or not 1<=len(fileset["files"])<=len(transport.allowed_paths)):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    files=[]
    seen=set()
    size=0
    for entry in fileset["files"]:
        if not isinstance(entry,dict) or set(entry)!={"path","content"}:
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        try:
            path=_safe_path(entry["path"])
        except (ValueError,TypeError):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG") from None
        if (path not in transport.allowed_paths or path.casefold() in seen
            or not isinstance(entry["content"],str)
            or "\x00" in entry["content"]):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        seen.add(path.casefold())
        size += len(entry["content"].encode("utf-8"))
        if size > 131072:
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        files.append((path,entry["content"]))
    files.sort(key=lambda item:item[0])
    canonical=_json.dumps(
        files,ensure_ascii=True,sort_keys=True,separators=(",",":")
    ).encode("utf-8")
    return UntrustedHostQwenFiles(
        request.task_id,request.run_id,request.source_sha,
        request.plan_sha256,request.request_sha256,tuple(files),
        sha256(b"mla-untrusted-host-files/v1|"+canonical).hexdigest(),
    )


# The host model can generate proposed file contents while the guest has no
# network interface. A separate protected owner broker may later place this
# in a one-run scratch directory (never original checkout) and map it into a
# Windows Sandbox as READ-ONLY. Host side never executes model-authored text.
from pathlib import PureWindowsPath as _PureWindowsPath


@dataclass(frozen=True)
class SandboxReadOnlyPatchImport:
    task_id: str
    run_id: str
    role: str
    plan_sha256: str
    source_sha: str
    host_scratch_input_dir: str
    guest_input_dir: str
    config_xml: str
    config_sha256: str
    manifest_sha256: str
    manifest_bytes: bytes
    state: str = "READ_ONLY_GUEST_IMPORT_SOURCE_ONLY"
    host_scratch_acl_verified: bool = False
    guest_isolation_attested: bool = False
    guest_execution_started: bool = False
    guest_writable_host_mapping: bool = False
    owner_source_written: bool = False
    may_promote: bool = False


def prepare_sandbox_readonly_patch_import(
    *, profile: WindowsNoEgressProfile,
    proposed_files: UntrustedHostQwenFiles,
    scratch_root: str,
) -> SandboxReadOnlyPatchImport:
    """Render exact .wsb read-only host-scratch mapping; no file or OS changes.

    Requires a disposable, task-specific host path. Before installing it,
    the protected Windows broker MUST attest path, DACL, no reparse ancestors,
    package hash and safe owner/guest principal separation. The directory
    and the WSB XML are source-only plans, not proof that mapping occurred.
    """
    if (not isinstance(profile,WindowsNoEgressProfile)
        or not isinstance(proposed_files,UntrustedHostQwenFiles)
        or profile.role != "CODER"
        or proposed_files.task_id != profile.task_id
        or proposed_files.run_id != profile.run_id
        or proposed_files.source_sha != profile.source_sha
        or proposed_files.plan_sha256 != profile.plan_sha256
        or proposed_files.state != "UNTRUSTED_HOST_MODEL_OUTPUT_F18_REQUIRED"
        or proposed_files.files_applied_to_original
        or proposed_files.guest_executed
        or proposed_files.independent_f18_verified
        or proposed_files.can_publish
        or not isinstance(scratch_root,str)
        or not scratch_root.isascii()):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    # Reject forged dataclasses and stale/broad paths before creating even a
    # read-only import request. Guest/model file lists never define authority.
    files = proposed_files.files
    if (not isinstance(files,tuple) or not 1 <= len(files) <= 16
        or not isinstance(proposed_files.files_sha256,str)
        or not _SHA64.fullmatch(proposed_files.files_sha256)):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    checked=[]
    seen=set()
    total=0
    for item in files:
        if (not isinstance(item,tuple) or len(item)!=2
            or not isinstance(item[0],str) or not isinstance(item[1],str)
            or "\x00" in item[1]):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        try:
            path=_safe_path(item[0])
            encoded=item[1].encode("utf-8")
        except (ValueError,TypeError,UnicodeError):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG") from None
        if path.casefold() in seen:
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        seen.add(path.casefold())
        checked.append((path,item[1]))
        total += len(encoded)
        if total > 131072:
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    checked.sort(key=lambda entry:entry[0])
    canonical_files=_json.dumps(
        checked,ensure_ascii=True,sort_keys=True,separators=(",",":")
    ).encode("utf-8")
    if (tuple(checked)!=files or
        sha256(b"mla-untrusted-host-files/v1|"+canonical_files).hexdigest()
        != proposed_files.files_sha256):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    audit_no_egress_profile(
        profile,expected_task_id=profile.task_id,
        expected_run_id=profile.run_id,expected_role="CODER",
        expected_source_sha=profile.source_sha,
        expected_plan_sha256=profile.plan_sha256,
    )
    # Require exactly one owner-selected scratch root. No path segments
    # from guest/model data, no UNC/\\?\ or alternate data streams.
    host_root = _PureWindowsPath(scratch_root)
    normalized = str(host_root)
    if (not host_root.is_absolute() or host_root.drive.upper() != "C:"
        or normalized != r"C:\MLA_Disposable"
        or any(part in (".", "..") for part in host_root.parts)):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    host_input = str(host_root / profile.run_id / "input")
    guest_input = r"C:\MLA_Input"
    root = ET.fromstring(profile.config_xml)
    mapped = ET.SubElement(root, "MappedFolders")
    folder = ET.SubElement(mapped, "MappedFolder")
    ET.SubElement(folder, "HostFolder").text = host_input
    ET.SubElement(folder, "SandboxFolder").text = guest_input
    ET.SubElement(folder, "ReadOnly").text = "true"
    config = ET.tostring(root, encoding="unicode", short_empty_elements=False)
    manifest = _json.dumps({
        "version":1,"task_id":profile.task_id,"run_id":profile.run_id,
        "source_sha":profile.source_sha,"plan_sha256":profile.plan_sha256,
        "files_sha256":proposed_files.files_sha256,
        "files":[{"path":p,"content":c} for p,c in proposed_files.files],
        "trust":"UNTRUSTED_MODEL_FILES_NEVER_HOST_EXECUTABLE",
    },ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("utf-8")
    if len(manifest)>196608:
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    config_hash=sha256(
        b"mla-wsb-readonly-import/v1|" + profile.config_sha256.encode("ascii")
        + b"|" + config.encode("utf-8")
    ).hexdigest()
    manifest_hash=sha256(b"mla-model-import/v1|"+manifest).hexdigest()
    return SandboxReadOnlyPatchImport(
        profile.task_id,profile.run_id,profile.role,profile.plan_sha256,
        profile.source_sha,host_input,guest_input,config,config_hash,
        manifest_hash,manifest,
    )


def audit_sandbox_readonly_patch_import(
    plan: SandboxReadOnlyPatchImport, *,
    profile: WindowsNoEgressProfile,
    proposed_files: UntrustedHostQwenFiles,
) -> str:
    """Verify all fields and exact XML before any protected broker operation."""
    if (not isinstance(plan,SandboxReadOnlyPatchImport)
        or plan.state != "READ_ONLY_GUEST_IMPORT_SOURCE_ONLY"
        or plan.host_scratch_acl_verified
        or plan.guest_isolation_attested
        or plan.guest_execution_started
        or plan.guest_writable_host_mapping
        or plan.owner_source_written or plan.may_promote):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    expected=prepare_sandbox_readonly_patch_import(
        profile=profile,proposed_files=proposed_files,
        scratch_root=r"C:\MLA_Disposable",
    )
    if plan != expected:
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    return "EXACT_READ_ONLY_GUEST_IMPORT_HOST_ACL_AND_EGRESS_NOT_ATTESTED"


# This host-only inference call uses the local Ollama service without OpenCode
# tools or guest networking. It is ONLY for explicitly public/synthetic text.
# Never send customer/private source or credentials to an external provider.
from http.client import HTTPConnection as _HTTPConnection
from my_local_ai.ax_runtime.budgets import (
    BudgetGuard as _BudgetGuard, BudgetExceeded as _BudgetExceeded,
)


def infer_host_qwen_public_synthetic(
    request: HostQwenGenerationRequest,
    transport: OfflineCoderTransport, *,
    budget: _BudgetGuard,
) -> UntrustedHostQwenFiles:
    """One local-only Ollama generation -> bounded untrusted files.

    This function performs a loopback model *inference*, not a worker process,
    tool call, Git action, network-enabled guest launch, or owner file write.
    Real protected/private task prompts remain gated by a separate owner
    approval and cannot use this PUBLIC_SYNTHETIC_ONLY source interface.
    """
    if (not isinstance(request,HostQwenGenerationRequest)
        or not isinstance(transport,OfflineCoderTransport)
        or not isinstance(budget,_BudgetGuard)
        or request.state != "HOST_ONLY_INFERENCE_NOT_EXECUTED"
        or request.host_inference_executed or request.guest_sandbox_executed
        or request.owner_source_writable or request.model_output_trusted
        or request.may_promote
        or request.task_id != transport.task_id
        or request.run_id != transport.run_id
        or request.source_sha != transport.source_sha
        or request.plan_sha256 != transport.plan_sha256
        or request.transport_sha256 != transport.request_sha256
        or request.model != "qwen3:4b-instruct"
        or request.endpoint != "http://127.0.0.1:11434"
        or not isinstance(request.request_body,bytes)
        or not 0 < len(request.request_body) <= 14000
        or request.request_sha256 != sha256(
            b"mla-host-qwen-request/v1|"
            +transport.request_sha256.encode("ascii")
            +b"|"+request.request_body
        ).hexdigest()):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    # Parse and bind all generated HTTP inputs to a fixed no-tool request.
    body = _strict_json(request.request_body,limit=14000)
    if (not isinstance(body,dict)
        or set(body) != {"model","prompt","stream","format","options","keep_alive"}
        or body["model"] != "qwen3:4b-instruct"
        or not isinstance(body["prompt"],str)
        or not body["prompt"].startswith(
            'Return only JSON {"version":1,"files":['
        )
        or sha256(body["prompt"].encode("utf-8")).hexdigest()
        != request.prompt_sha256
        or body["stream"] is not False or body["format"] != "json"
        or body["keep_alive"] != "0"
        or body["options"] != {
            "temperature":0,"num_predict":2048,"num_ctx":4096
        }):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    try:
        budget.reserve_call()
    except _BudgetExceeded:
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE") from None
    connection = None
    try:
        # HTTPConnection does not consult proxy environment variables,
        # resolve remote domains, redirect, follow tool calls, or use cloud.
        connection = _HTTPConnection("127.0.0.1",11434,timeout=20)
        connection.request(
            "POST","/api/generate",body=request.request_body,
            headers={"Content-Type":"application/json",
                     "Accept":"application/json","Connection":"close"},
        )
        response=connection.getresponse()
        if (response.status != 200
            or not response.getheader("Content-Type","").lower().startswith(
                "application/json"
            )):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        raw=response.read(262145)
        if len(raw)>262144:
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    except (OSError,TimeoutError,ValueError):
        raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED") from None
    finally:
        if connection is not None:
            connection.close()
    try:
        budget.check(output_bytes=len(raw))
    except _BudgetExceeded:
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG") from None
    # This response is still model-supplied untrusted code. A real candidate
    # must run in an isolated guest and pass *separate* trusted F18 review.
    return decode_untrusted_host_qwen_files(raw,request,transport)



# SWU-015: bounded real filesystem staging, NOT a Sandbox launcher or grant.
# The owner's original checkout is never touched. An independently protected
# broker must still provision/attest the DACL, run a separate Windows guest,
# enforce egress and extract/verifiably attribute results before F18.
import os as _os


@dataclass(frozen=True)
class StagedUntrustedSandboxInput:
    task_id: str
    run_id: str
    source_sha: str
    plan_sha256: str
    manifest_sha256: str
    manifest_size: int
    state: str = "PUBLIC_SYNTHETIC_SCRATCH_WRITTEN_UNTRUSTED"
    protected_owner_principal_verified: bool = False
    scratch_acl_attested: bool = False
    sandbox_started: bool = False
    network_egress_attested: bool = False
    independent_f18_verified: bool = False
    original_modified: bool = False
    can_execute: bool = False
    may_promote: bool = False

    def __post_init__(self) -> None:
        if (self.state != "PUBLIC_SYNTHETIC_SCRATCH_WRITTEN_UNTRUSTED"
            or type(self.manifest_size) is not int
            or not 1 <= self.manifest_size <= 196608
            or not _SHA64.fullmatch(self.manifest_sha256)
            or any(getattr(self, name) is not False for name in (
                "protected_owner_principal_verified", "scratch_acl_attested",
                "sandbox_started", "network_egress_attested",
                "independent_f18_verified", "original_modified",
                "can_execute", "may_promote",
            ))):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")


def _pinned_existing_stage_dir(path: Path) -> tuple[tuple[int, int, int], ...]:
    """Reject links/junctions on the full fixed scratch path, before/after IO."""
    identities = []
    for segment in (path, *path.parents):
        info = segment.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & _REPARSE):
            raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
        identities.append((info.st_dev, info.st_ino, info.st_mode))
    return tuple(identities)


def write_disposable_sandbox_manifest(
    plan: SandboxReadOnlyPatchImport, *,
    profile: WindowsNoEgressProfile,
    proposed_files: UntrustedHostQwenFiles,
) -> StagedUntrustedSandboxInput:
    """Write an untrusted public/synthetic JSON manifest to preexisting scratch.

    Real caller→IO→readback path. It NEVER creates directories, mutates owner
    source, starts guest tools, changes ACLs or treats filesystem success as
    trustworthy OS isolation. A protected owner process must separately create
    and attest the run directory with safe Windows DACLs before using this.
    Missing scratch or an existing file means HOLD rather than overwriting.
    """
    if _os.name != "nt":
        raise WindowsIsolationHold("WINDOWS_HOST_ISOLATION_NOT_ATTESTED")
    audit_sandbox_readonly_patch_import(
        plan, profile=profile, proposed_files=proposed_files,
    )
    if (not isinstance(plan.manifest_bytes, bytes)
        or not 0 < len(plan.manifest_bytes) <= 196608
        or sha256(b"mla-model-import/v1|" + plan.manifest_bytes).hexdigest()
            != plan.manifest_sha256
        or plan.run_id != profile.run_id or not _ID.fullmatch(plan.run_id)):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    fixed = _PureWindowsPath(r"C:\MLA_Disposable") / plan.run_id / "input"
    if (str(fixed) != plan.host_scratch_input_dir
        or not fixed.is_absolute() or fixed.drive.upper() != "C:"):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    directory = Path(str(fixed))
    manifest_path = directory / "manifest.json"
    try:
        before = _pinned_existing_stage_dir(directory)
        # Exclusive write: never replace a previous run's input, or a link.
        # A separate protected broker must prevent concurrent untrusted
        # mutation (Windows DACLs/handles); this code does not claim that.
        with _os.scandir(directory) as contents:
            if next(contents, None) is not None:
                raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
        flags = (_os.O_WRONLY | _os.O_CREAT | _os.O_EXCL
                 | getattr(_os, "O_BINARY", 0)
                 | getattr(_os, "O_NOFOLLOW", 0))
        fd = _os.open(manifest_path, flags, 0o600)
        with _os.fdopen(fd, "wb") as stream:
            stream.write(plan.manifest_bytes)
            stream.flush()
            _os.fsync(stream.fileno())
            written = _os.fstat(stream.fileno())
        after = _pinned_existing_stage_dir(directory)
        current = manifest_path.lstat()
        if (before != after or not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or getattr(current, "st_file_attributes", 0) & _REPARSE
            or (written.st_dev, written.st_ino, written.st_size)
              != (current.st_dev, current.st_ino, current.st_size)
            or current.st_size != len(plan.manifest_bytes)):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        # Read back exact bytes, reject replacement; no parsing or execution.
        with manifest_path.open("rb") as stream:
            read_back = stream.read(196609)
            read_id = _os.fstat(stream.fileno())
        if (read_back != plan.manifest_bytes
            or (read_id.st_dev, read_id.st_ino, read_id.st_size)
              != (written.st_dev, written.st_ino, written.st_size)
            or _pinned_existing_stage_dir(directory) != before):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    except WindowsIsolationHold:
        raise
    except (OSError, ValueError, OverflowError):
        # Do not delete a file after a TOCTOU failure; an untrusted path may
        # have been redirected. The owner-protected cleanup is separate.
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE") from None
    return StagedUntrustedSandboxInput(
        plan.task_id, plan.run_id, plan.source_sha,
        plan.plan_sha256, plan.manifest_sha256, len(plan.manifest_bytes),
    )



def generate_and_stage_public_synthetic_coder_input(
    *, profile: WindowsNoEgressProfile,
    prepared: _PreparedOpenCodeRun,
    coding_request: str,
    budget: _BudgetGuard,
) -> StagedUntrustedSandboxInput:
    """Public/synthetic host model -> bounded untrusted files -> scratch disk.

    This is a real, sequential caller→callee source path; it does NOT launch a
    Sandbox/guest, approve owner access, change ACLs, write original source,
    trust the generated code, or mint F18. The separate protected OS runner
    remains mandatory before any generated source may be executed or promoted.
    """
    if (_os.name != "nt" or not isinstance(budget, _BudgetGuard)):
        raise WindowsIsolationHold("WINDOWS_HOST_ISOLATION_NOT_ATTESTED")
    if (not isinstance(profile, WindowsNoEgressProfile)
        or not isinstance(prepared, _PreparedOpenCodeRun)
        or profile.role != "CODER"):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    transport = prepare_offline_coder_transport(
        profile=profile, prepared=prepared,
    )
    # Check the immutable, preprovisioned scratch *before* local inference.
    expected_dir = Path(
        str(_PureWindowsPath(r"C:\MLA_Disposable") / profile.run_id / "input")
    )
    try:
        _pinned_existing_stage_dir(expected_dir)
        with _os.scandir(expected_dir) as items:
            if next(items, None) is not None:
                raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    except WindowsIsolationHold:
        raise
    except (OSError, ValueError):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE") from None
    request = prepare_host_qwen_generation(
        transport, coding_request=coding_request,
        classification="PUBLIC_SYNTHETIC_ONLY",
    )
    proposal = infer_host_qwen_public_synthetic(
        request, transport, budget=budget,
    )
    plan = prepare_sandbox_readonly_patch_import(
        profile=profile, proposed_files=proposal,
        scratch_root=r"C:\MLA_Disposable",
    )
    # Exact content readback is repeated after the model call. Any stale run,
    # existing data, reparse path, wrong package or inaccessible folder HOLDS.
    return write_disposable_sandbox_manifest(
        plan, profile=profile, proposed_files=proposal,
    )


def recheck_disposable_sandbox_manifest(
    staged: StagedUntrustedSandboxInput, *,
    plan: SandboxReadOnlyPatchImport,
    profile: WindowsNoEgressProfile,
    proposed_files: UntrustedHostQwenFiles,
) -> StagedUntrustedSandboxInput:
    """Reopen the staged *public/synthetic* guest input before broker use.

    This is a real read-only filesystem integrity check, not OS identity
    attestation, a DACL grant or Sandbox execution. It rejects stale, edited,
    extra, linked or replaced scratch files and preserves deny-only flags.
    """
    if _os.name != "nt" or not isinstance(staged, StagedUntrustedSandboxInput):
        raise WindowsIsolationHold("WINDOWS_HOST_ISOLATION_NOT_ATTESTED")
    audit_sandbox_readonly_patch_import(
        plan, profile=profile, proposed_files=proposed_files,
    )
    if (staged.state != "PUBLIC_SYNTHETIC_SCRATCH_WRITTEN_UNTRUSTED"
        or any(getattr(staged, flag) is not False for flag in (
            "protected_owner_principal_verified", "scratch_acl_attested",
            "sandbox_started", "network_egress_attested",
            "independent_f18_verified", "original_modified",
            "can_execute", "may_promote",
        ))
        or (staged.task_id, staged.run_id, staged.source_sha,
            staged.plan_sha256, staged.manifest_sha256, staged.manifest_size)
        != (plan.task_id, plan.run_id, plan.source_sha,
            plan.plan_sha256, plan.manifest_sha256, len(plan.manifest_bytes))
        or len(plan.manifest_bytes) > 196608
        or sha256(b"mla-model-import/v1|" + plan.manifest_bytes).hexdigest()
            != plan.manifest_sha256):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    pinned_folder = str(
        _PureWindowsPath(r"C:\MLA_Disposable") / plan.run_id / "input"
    )
    if plan.host_scratch_input_dir != pinned_folder:
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    directory = Path(pinned_folder)
    target = directory / "manifest.json"
    try:
        start_dirs = _pinned_existing_stage_dir(directory)
        # Only this one file may be present. Avoid unbounded listing.
        with _os.scandir(directory) as entries:
            first = next(entries, None)
            extra = next(entries, None)
            if first is None or first.name != "manifest.json" or extra is not None:
                raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        before = target.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or getattr(before, "st_file_attributes", 0) & _REPARSE
            or before.st_size != staged.manifest_size):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        flags = (_os.O_RDONLY | getattr(_os, "O_BINARY", 0)
                 | getattr(_os, "O_NOFOLLOW", 0))
        fd = _os.open(target, flags)
        with _os.fdopen(fd, "rb") as stream:
            handle_before = _os.fstat(stream.fileno())
            raw = stream.read(196609)
            handle_after = _os.fstat(stream.fileno())
        after = target.lstat()
        identity = (before.st_dev, before.st_ino,
                    before.st_size, before.st_mtime_ns)
        if (raw != plan.manifest_bytes
            or (handle_before.st_dev, handle_before.st_ino,
                handle_before.st_size, handle_before.st_mtime_ns) != identity
            or (handle_after.st_dev, handle_after.st_ino,
                handle_after.st_size, handle_after.st_mtime_ns) != identity
            or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
               != identity
            or _pinned_existing_stage_dir(directory) != start_dirs):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    except WindowsIsolationHold:
        raise
    except (OSError, OverflowError, ValueError):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG") from None
    # Re-read exact bytes; never promote a caller-supplied status to GO.
    return staged


# MLA-SWU-015 source progress: *read-only* owner-device capability
# observation for choosing an OS-isolation implementation. Neither the
# presence of native APIs nor a supported CPU proves enforced isolation.
# Microsoft IsProcessorFeaturePresent: SLAT=20, firmware virtualization=21.
# CreateAppContainerProfile availability is inspected, never invoked.
@dataclass(frozen=True)
class WindowsHostCapabilityObservation:
    host: str
    windows_build: int | None
    slat_observed: bool | None
    firmware_virtualization_observed: bool | None
    appcontainer_api_exported: bool | None
    restricted_token_api_exported: bool | None
    job_object_api_exported: bool | None
    sandbox_feature_enabled: bool | None = None
    state: str = "READ_ONLY_CAPABILITIES_NOT_OS_ATTESTATION"
    protected_owner_principal_verified: bool = False
    sandbox_runtime_attested: bool = False
    network_egress_denied_attested: bool = False
    independent_f18_verified: bool = False
    os_configuration_changed: bool = False
    may_start_worker: bool = False

    def __post_init__(self) -> None:
        if (self.host not in ("WINDOWS_LOCAL_OBSERVED", "WINDOWS_PROBE_UNAVAILABLE",
                              "NON_WINDOWS")
            or self.state != "READ_ONLY_CAPABILITIES_NOT_OS_ATTESTATION"
            or (self.windows_build is not None
                and (type(self.windows_build) is not int or
                     not 10000 <= self.windows_build <= 100000))
            or any(type(getattr(self, key)) not in (bool, type(None))
                   for key in (
                       "slat_observed", "firmware_virtualization_observed",
                       "appcontainer_api_exported", "restricted_token_api_exported",
                       "job_object_api_exported", "sandbox_feature_enabled",
                   ))
            or self.sandbox_feature_enabled is not None
            or (self.host != "WINDOWS_LOCAL_OBSERVED"
                and any(getattr(self, key) is not None for key in (
                    "windows_build", "slat_observed",
                    "firmware_virtualization_observed", "appcontainer_api_exported",
                    "restricted_token_api_exported", "job_object_api_exported",
                )))
            or any(getattr(self, key) is not False for key in (
                "protected_owner_principal_verified", "sandbox_runtime_attested",
                "network_egress_denied_attested", "independent_f18_verified",
                "os_configuration_changed", "may_start_worker",
            ))):
            raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")

    def to_redacted_dict(self) -> dict[str, object]:
        """No host identity, process list, paths or secrets in the report."""
        return {
            "host": self.host,
            "windows_build": self.windows_build,
            "slat_observed": self.slat_observed,
            "firmware_virtualization_observed": (
                self.firmware_virtualization_observed
            ),
            "appcontainer_api_exported": self.appcontainer_api_exported,
            "restricted_token_api_exported": self.restricted_token_api_exported,
            "job_object_api_exported": self.job_object_api_exported,
            "sandbox_feature_enabled": "UNASSESSED",
            "isolation_policy": "NOT_ATTESTED",
            "host_egress": "NOT_ATTESTED",
            "independent_f18": "NOT_VERIFIED",
            "owner_go": False,
            "os_settings_changed": False,
            "execution_allowed": False,
            "p2": "LOCKED",
        }


def inspect_windows_host_capabilities_read_only() -> WindowsHostCapabilityObservation:
    """Read actual Windows CPU/API capability indicators, never modify OS.

    The returned observations are advisory and not permission to create an
    AppContainer, launch a process, enable Sandbox/Hyper-V or execute code.
    API exports do not prove usable security boundaries; Windows Sandbox
    optional-feature state is intentionally UNKNOWN, not inferred from a DLL.
    This is suitable for an explicit future *owner-side* read-only inspection.
    """
    import os
    import sys
    if os.name != "nt":
        return WindowsHostCapabilityObservation("NON_WINDOWS", None, None,
                                                 None, None, None, None)
    try:
        import ctypes

        # LOAD_LIBRARY_SEARCH_SYSTEM32; do not resolve DLLs from cwd/PATH.
        system32_only = 0x00000800
        kernel = ctypes.WinDLL("kernel32.dll", winmode=system32_only)
        userenv = ctypes.WinDLL("userenv.dll", winmode=system32_only)
        advapi = ctypes.WinDLL("advapi32.dll", winmode=system32_only)

        observed = kernel.IsProcessorFeaturePresent
        observed.argtypes = (ctypes.c_uint,)
        observed.restype = ctypes.c_int
        slat = bool(observed(20))
        virt = bool(observed(21))
        build = int(sys.getwindowsversion().build)
        return WindowsHostCapabilityObservation(
            "WINDOWS_LOCAL_OBSERVED", build, slat, virt,
            hasattr(userenv, "CreateAppContainerProfile"),
            hasattr(advapi, "CreateRestrictedToken"),
            hasattr(kernel, "CreateJobObjectW"),
        )
    except (OSError, AttributeError, TypeError, ValueError, OverflowError):
        # No fallback to environment variables, subprocess, DISM, PowerShell
        # or auto-enabling optional OS features.
        return WindowsHostCapabilityObservation(
            "WINDOWS_PROBE_UNAVAILABLE", None, None, None, None, None, None,
        )


def _capabilities_read_only_main() -> int:
    """Single nonprivileged diagnostic: python -m my_local_ai.ax_runtime.isolation_runner.

    Native CPU/APIs and process token state are sampled without OS changes.
    The result is NOT protected identity, a verified network policy, a signer
    or a green light to start any untrusted code.
    """
    import json
    from my_local_ai.state.consent import inspect_windows_current_token_read_only

    capability = inspect_windows_host_capabilities_read_only()
    owner_token = inspect_windows_current_token_read_only()
    report = {
        "host_capabilities": capability.to_redacted_dict(),
        "current_process_token": owner_token.to_redacted_dict(),
        "native_isolation_attested": False,
        "protected_owner_signer_attested": False,
        "independent_f18_verified": False,
        "network_egress_denial_attested": False,
        "execution_allowed": False,
        "p2": "LOCKED",
    }
    print(json.dumps(report, sort_keys=True))
    # Exit 0 only signals a completed read-only observation, never PASS.
    return 0


def _hold_live_zero_network_appcontainer(pid: int, expected_sid: str,
                                        creation_time: int):
    """Read the actual suspended worker token/loopback exemptions, hold handles.

    Restricted token/Job Object alone do not deny network. Require an actual
    low-integrity AppContainer token, ZERO capability SIDs and no OS loopback
    exemption. No profile, exemption, ACL or firewall setting is created here.
    A signed service is still required for suspended launch/job/file isolation.
    """
    from contextlib import ExitStack
    from my_local_ai.state.consent import _WindowsBrokerAPI, ProtectedBrokerHold
    if (type(pid) is not int or not 1 <= pid <= 2**32 - 1
        or type(creation_time) is not int or creation_time <= 0
        or type(expected_sid) is not str
        or re.fullmatch(r"S-1-15-2-(?:[0-9]+-)*[0-9]+", expected_sid) is None):
        raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
    stack = ExitStack()
    try:
        api = _WindowsBrokerAPI()
        c, w = api.c, api.w
        roots = api.load_roots()
        open_process = api._bind(api.kernel, "OpenProcess",
            [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
        process = open_process(0x1000 | 0x100000, False, pid)
        if not process:
            raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
        stack.callback(api.kernel.CloseHandle, process)
        if api.process_sid(process) != roots["coder"][0]:
            raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
        get_times = api._bind(api.kernel, "GetProcessTimes",
            [w.HANDLE, c.POINTER(w.FILETIME), c.POINTER(w.FILETIME),
             c.POINTER(w.FILETIME), c.POINTER(w.FILETIME)], w.BOOL)
        times = [w.FILETIME() for _ in range(4)]
        if (not get_times(process, *(c.byref(t) for t in times))
            or (times[0].dwHighDateTime << 32 | times[0].dwLowDateTime) != creation_time):
            raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
        token = w.HANDLE()
        open_token = api._bind(api.advapi, "OpenProcessToken",
            [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)], w.BOOL)
        if not open_token(process, 8, c.byref(token)):
            raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
        stack.callback(api.kernel.CloseHandle, token)
        get = api._bind(api.advapi, "GetTokenInformation",
            [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
        def info(kind):
            size = w.DWORD()
            get(token, kind, None, 0, c.byref(size))
            if not 4 <= size.value <= 65536:
                raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
            buffer = c.create_string_buffer(size.value)
            if not get(token, kind, buffer, len(buffer), c.byref(size)):
                raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
            return buffer
        restricted = api._bind(api.advapi, "IsTokenRestricted", [w.HANDLE], w.BOOL)
        in_job = api._bind(api.kernel, "IsProcessInJob",
            [w.HANDLE, w.HANDLE, c.POINTER(w.BOOL)], w.BOOL)
        job = w.BOOL()
        if (w.DWORD.from_buffer(info(29)).value != 1  # TokenIsAppContainer
            or w.DWORD.from_buffer(info(30)).value != 0  # TokenCapabilities count
            or w.DWORD.from_buffer(info(20)).value != 0  # TokenElevation
            or not restricted(token) or not in_job(process, None, c.byref(job)) or not job.value):
            raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
        package, integrity = info(31), info(25)
        if (api.sid_string(c.cast(package, c.POINTER(c.c_void_p))[0]) != expected_sid
            or api.sid_string(c.cast(integrity, c.POINTER(c.c_void_p))[0]) not in {"S-1-16-0", "S-1-16-4096"}):
            raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
        class SidAttributes(c.Structure):
            _fields_ = [("sid", c.c_void_p), ("attributes", w.DWORD)]
        firewall = c.WinDLL("FirewallAPI.dll", use_last_error=True, winmode=0x800)
        enumerate_exempt = api._bind(firewall, "NetworkIsolationGetAppContainerConfig",
            [c.POINTER(w.DWORD), c.POINTER(c.POINTER(SidAttributes))], w.DWORD)
        heap = api._bind(api.kernel, "GetProcessHeap", [], w.HANDLE)
        free = api._bind(api.kernel, "HeapFree", [w.HANDLE, w.DWORD, c.c_void_p], w.BOOL)
        count, exemptions = w.DWORD(), c.POINTER(SidAttributes)()
        error = enumerate_exempt(c.byref(count), c.byref(exemptions))
        try:
            if error or count.value > 65536 or count.value and not exemptions:
                raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
            if any(api.sid_string(exemptions[i].sid) == expected_sid for i in range(count.value)):
                raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
        finally:
            if exemptions:
                for i in range(count.value):
                    free(heap(), 0, exemptions[i].sid)
                free(heap(), 0, exemptions)
        return stack
    except BaseException as exc:
        stack.close()
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED") from None


@dataclass(frozen=True)
class ProtectedCoderArtifacts:
    outbox: UntrustedGuestOutbox
    files: tuple[tuple[str, str], ...]
    state: str = "PROTECTED_CODER_ARTIFACTS_UNTRUSTED_F18_REQUIRED"
    may_promote: bool = False
    independent_f18_verified: bool = False

    def __post_init__(self):
        if (not isinstance(self.outbox, UntrustedGuestOutbox) or type(self.files) is not tuple
            or self.state != "PROTECTED_CODER_ARTIFACTS_UNTRUSTED_F18_REQUIRED"
            or self.may_promote is not False or self.independent_f18_verified is not False):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")


def run_protected_coder(transport: OfflineCoderTransport, proposal: UntrustedHostQwenFiles,
                        *, candidate_sha: str, lease_epoch: int, nonce_sha256: str,
                        owner_consent_ref: str) -> ProtectedCoderArtifacts:
    """Host model DATA -> protected suspended worker -> checked token -> output.

    The service must implement prepare/run/abort, fixed tool policy, private
    scratch, job budgets and automatic kill-on-disconnect/deadline. Host Qwen
    remains the sole model; there is no guest model or host execution fallback.
    No artifact is imported, executed, applied to original or promoted here.
    Until that independently provisioned native service exists this path HOLDS.
    """
    from my_local_ai.state.consent import (
        ProtectedBrokerHold, dispatch_protected_action, exchange_protected_broker,
        _broker_canonical, _validate_broker_binding,
    )
    if (not isinstance(transport, OfflineCoderTransport)
        or transport.state != "HOST_OFFLINE_MODEL_BROKER_UNAVAILABLE"
        or any(getattr(transport, field) is not False for field in (
            "sandbox_started", "model_executed", "network_egress_attested", "output_trusted",
            "may_write_owner_checkout", "may_issue_review_receipt"))
        or type(transport.request_sha256) is not str or not _SHA64.fullmatch(transport.request_sha256)
        or type(transport.allowed_paths) is not tuple or not 1 <= len(transport.allowed_paths) <= 16
        or not isinstance(proposal, UntrustedHostQwenFiles)
        or proposal.task_id != transport.task_id or proposal.run_id != transport.run_id
        or proposal.source_sha != transport.source_sha or proposal.plan_sha256 != transport.plan_sha256
        or proposal.state != "UNTRUSTED_HOST_MODEL_OUTPUT_F18_REQUIRED"
        or proposal.guest_executed or proposal.files_applied_to_original
        or proposal.independent_f18_verified or proposal.can_publish
        or not isinstance(proposal.files, tuple) or not 1 <= len(proposal.files) <= 16):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    # Revalidate dataclass contents; caller-created Python objects are not grants.
    try:
        files = tuple((_safe_path(name), content) for name, content in proposal.files)
        if (any(name not in transport.allowed_paths or type(content) is not str or "\x00" in content
                for name, content in files)
            or len({name.casefold() for name, _ in files}) != len(files)
            or tuple(sorted(files)) != files
            or sum(len(content.encode("utf-8")) for _, content in files) > 131072
            or sha256(b"mla-untrusted-host-files/v1|" + _broker_canonical(files)).hexdigest() != proposal.files_sha256):
            raise ValueError()
        binding = {"task_id": transport.task_id, "run_id": transport.run_id,
            "plan_sha256": transport.plan_sha256, "source_sha": transport.source_sha,
            "candidate_sha": candidate_sha, "lease_epoch": lease_epoch,
            "nonce_sha256": nonce_sha256, "owner_consent_ref": owner_consent_ref}
        _validate_broker_binding(binding)
        payload = {"transport_sha256": transport.request_sha256,
            "allowed_paths": list(transport.allowed_paths),
            "files": [{"path": name, "content": content} for name, content in files],
            "policy": "APPCONTAINER_ZERO_CAPABILITIES_RESTRICTED_JOB_V1",
            "memory_mb": 512, "cpu_seconds": 60, "wall_seconds": 90,
            "active_process_limit": 8}
        prepared = dispatch_protected_action("coder", "prepare", binding=binding, payload=payload)
        prep = prepared["result"]
        try:
            if (set(prep) != {"state", "preparation_id", "worker_pid", "appcontainer_sid", "creation_time"}
                or prep["state"] != "READY_SUSPENDED"
                or type(prep["preparation_id"]) is not str
                or not _SHA64.fullmatch(prep["preparation_id"])):
                raise WindowsIsolationHold("WINDOWS_HOST_ISOLATION_NOT_ATTESTED")
            with _hold_live_zero_network_appcontainer(prep["worker_pid"], prep["appcontainer_sid"],
                                                      prep["creation_time"]):
                reply = dispatch_protected_action("coder", "run", binding=binding,
                    payload={"preparation": prepared["signed_envelope"],
                             "input_sha256": sha256(_broker_canonical(payload)).hexdigest()},
                    timeout_seconds=95)
            result = reply["result"]
            if (set(result) != {"preparation_id", "outbox", "files", "timed_out"}
                or result["preparation_id"] != prep["preparation_id"] or result["timed_out"] is not False
                or type(result["outbox"]) is not dict or type(result["files"]) is not list):
                raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
            outbox = decode_untrusted_coder_outbox(_broker_canonical(result["outbox"]), transport)
            returned = []
            for item in result["files"]:
                if (type(item) is not dict or set(item) != {"path", "content"}
                    or type(item["content"]) is not str or "\x00" in item["content"]):
                    raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
                returned.append((_safe_path(item["path"]), item["content"]))
            if (tuple(name for name, _ in returned) != outbox.declared_paths
                or sum(len(content.encode("utf-8")) for _, content in returned) > 131072
                or sha256(_broker_canonical(returned)).hexdigest() != result["outbox"]["output_sha256"]):
                raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
            return ProtectedCoderArtifacts(outbox, tuple(returned))
        finally:
            # No retry of prepare/run. Cleanup is idempotent and bound to the
            # exact signed preparation; the service also owns the kill deadline.
            exchange_protected_broker("coder", "abort", binding=binding,
                payload={"preparation": prepared["signed_envelope"]}, timeout_seconds=5)
    except WindowsIsolationHold:
        raise
    except ProtectedBrokerHold:
        raise WindowsIsolationHold("OWNER_SIGNER_NOT_AVAILABLE") from None
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE") from None


if __name__ == "__main__":
    raise SystemExit(_capabilities_read_only_main())
