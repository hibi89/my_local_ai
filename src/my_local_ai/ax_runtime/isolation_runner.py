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
