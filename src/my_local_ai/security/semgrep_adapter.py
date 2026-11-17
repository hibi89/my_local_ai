"""CodeShield V1.3 pinned local Semgrep CE scanner, Python/JS static only.

No remote registry, login, updates, imported guest code, autofix or test run.
The protected controller must independently authenticate all binary/rule pins,
scope, network isolation and F18 before treating any result as evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import stat

from .ast_preflight import preflight_changed_paths
from .codeshield_contracts import (
    CodeShieldContext, CodeShieldHold, RiskOutcome, ScanStatus, ScannerEvidence,
)

_MAX_BINARY = 128 * 1024 * 1024
_MAX_RULES = 64 * 1024
_MAX_REPORT = 512 * 1024
_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx")


@dataclass(frozen=True)
class SemgrepResult:
    outcome: RiskOutcome
    status: ScanStatus
    reason: str
    finding_count: int
    evidence: ScannerEvidence | None
    execution_granted: bool = False
    f18_verified: bool = False
    remote_upload_performed: bool = False
    can_promote: bool = False


def _digest(path: Path, *, max_size: int) -> str | None:
    try:
        st = path.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
            or not 1 <= st.st_size <= max_size
            or getattr(st, "st_file_attributes", 0) &
               getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            return None
        h = sha256()
        with path.open("rb") as stream:
            while piece := stream.read(65536):
                h.update(piece)
        after = path.lstat()
        if (st.st_ino, st.st_dev, st.st_size, st.st_mtime_ns) != (
            after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns
        ):
            return None
        return h.hexdigest()
    except (OSError, ValueError):
        return None


def _result(
    context: CodeShieldContext, code: ScanStatus, reason: str,
    count: int = 0,
) -> SemgrepResult:
    pins = [p for p in context.scanner_pins if p.tool == "semgrep"]
    pin = pins[0] if pins else None
    evidence = None if pin is None else ScannerEvidence(
        tool="semgrep", version=pin.version,
        binary_sha256=pin.binary_sha256, rules_sha256=pin.rules_sha256,
        context_sha256=context.fingerprint_sha256,
        candidate_git_sha=context.candidate_git_sha,
        status=code, finding_count=count,
    )
    risk = (RiskOutcome.ALLOW_NON_EXECUTING if code == ScanStatus.PASS
            else RiskOutcome.HOLD_HIGH_RISK if code == ScanStatus.FINDINGS
            else RiskOutcome.UNKNOWN_HOLD)
    return SemgrepResult(risk, code, reason, count, evidence)


_MAX_SOURCE_BYTES = 256 * 1024
_MAX_SOURCES_TOTAL = 1024 * 1024


@dataclass(frozen=True)
class SemgrepBrokerRequest:
    """Pure pinned scan *data* for a future independently protected OS broker.

    The Python Controller cannot prove the caller's Windows SID, egress policy
    or OS sandbox. Nothing here is a capability, authorizer or runnable grant.
    """
    context_sha256: str
    candidate_git_sha: str
    binary_sha256: str
    rules_sha256: str
    pinned_version: str
    argv: tuple[str, ...]
    source_sha256: tuple[tuple[str, str], ...]
    allowed_paths: tuple[str, ...]
    timeout_seconds: int
    stage: str = "PROTECTED_WINDOWS_BROKER_NOT_INSTALLED"
    can_spawn: bool = False
    network_isolation_attested: bool = False
    host_execution_allowed: bool = False
    f18_verified: bool = False
    owner_go_verified: bool = False

    def __post_init__(self) -> None:
        if (self.stage != "PROTECTED_WINDOWS_BROKER_NOT_INSTALLED"
            or not isinstance(self.argv, tuple)
            or len(self.argv) < 9 or len(self.argv) > 40
            or not isinstance(self.source_sha256, tuple)
            or len(self.source_sha256) != len(self.allowed_paths)
            or any(getattr(self, flag) is not False for flag in (
                "can_spawn", "network_isolation_attested",
                "host_execution_allowed", "f18_verified", "owner_go_verified",
            ))):
            raise CodeShieldHold("UNTRUSTED_DECISION")


def _bounded_source_sha256(path: Path) -> str | None:
    """Hash a non-symlink source file, ensuring identity did not change."""
    try:
        before = path.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or not 1 <= before.st_size <= _MAX_SOURCE_BYTES
            or getattr(before, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            return None
        flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_BINARY", 0))
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if ((opened.st_dev, opened.st_ino, opened.st_size)
                != (before.st_dev, before.st_ino, before.st_size)):
                return None
            data = stream.read(_MAX_SOURCE_BYTES + 1)
            current = os.fstat(stream.fileno())
        after = path.lstat()
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if (len(data) != before.st_size
            or (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                != identity
            or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != identity):
            return None
        return sha256(data).hexdigest()
    except (OSError, ValueError, OverflowError):
        return None


def _reject_guest_semgrep_ignores(worktree: Path, paths: tuple[str, ...]) -> None:
    """Prevent per-project ignore/config directives from silently skipping files.

    Git ignore is disabled in fixed argv; Semgrep's own ignore files remain a
    separate attack surface until a native broker can verify tool behavior.
    """
    for name in paths:
        parent = (worktree / name).parent
        while True:
            for ignored in (".semgrepignore", ".semgrep.yml", ".semgrep.yaml"):
                target = parent / ignored
                try:
                    target.lstat()
                except FileNotFoundError:
                    continue
                except OSError:
                    raise CodeShieldHold("UNSAFE_PATH") from None
                else:
                    raise CodeShieldHold("UNSAFE_PATH")
            if parent == worktree:
                break
            if parent == parent.parent or worktree not in parent.parents:
                raise CodeShieldHold("UNSAFE_PATH")
            parent = parent.parent


def prepare_protected_semgrep_request(
    context: CodeShieldContext, *, executable: str | Path,
    local_rules: str | Path, disposable_worktree: str | Path,
    original_checkout: str | Path, changed_paths: tuple[str, ...],
    timeout_seconds: int = 20,
) -> SemgrepBrokerRequest:
    """Preflight exact local inputs, producing a non-executing broker request.

    This function NEVER invokes a process or trusts a caller 'isolated' bool.
    The future OS broker must independently revalidate SHA, owner/OS identity,
    WFP egress policy, Git source, open handles, process tree and tool version.
    """
    if (not isinstance(context, CodeShieldContext)
        or type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 30):
        raise CodeShieldHold()
    pins = [p for p in context.scanner_pins if p.tool == "semgrep"]
    if len(pins) != 1 or pins[0].rules_sha256 is None:
        raise CodeShieldHold("UNPINNED_SCANNER")
    pin = pins[0]
    if (not isinstance(changed_paths, tuple) or not changed_paths
        or any(not name.endswith(_SUFFIXES) for name in changed_paths)):
        raise CodeShieldHold("UNSAFE_PATH")
    scoped = preflight_changed_paths(
        context, worktree=disposable_worktree,
        original_checkout=original_checkout, changed_paths=changed_paths,
    )
    if scoped.may_execute or scoped.may_write or scoped.git_diff_verified:
        raise CodeShieldHold("UNTRUSTED_DECISION")
    root, original = Path(disposable_worktree), Path(original_checkout)
    exe, rules = Path(executable), Path(local_rules)
    expected_rules = Path(__file__).parent / "rules" / "codeshield.yaml"
    if (not exe.is_absolute() or not rules.is_absolute()
        or not root.is_absolute() or not original.is_absolute()
        or exe.suffix.casefold() != ".exe"
        or rules != expected_rules
        or any(".." in path.parts for path in (exe, rules, root, original))
        or any(path == exe or path in exe.parents for path in (root, original))
        or exe == rules):
        raise CodeShieldHold("UNPINNED_SCANNER")
    # Do not trust a scanner executable inside the generated worktree.
    # Parent symlinks/reparse aliases must not mask a substituted binary.
    for parent in (exe.parent, *exe.parent.parents, rules.parent, *rules.parent.parents):
        try:
            st = parent.lstat()
        except (OSError, ValueError):
            raise CodeShieldHold("UNPINNED_SCANNER") from None
        if (not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode)
            or getattr(st, "st_file_attributes", 0)
               & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise CodeShieldHold("UNPINNED_SCANNER")
    if (_digest(exe, max_size=_MAX_BINARY) != pin.binary_sha256
        or _digest(rules, max_size=_MAX_RULES) != pin.rules_sha256):
        raise CodeShieldHold("UNPINNED_SCANNER")
    _reject_guest_semgrep_ignores(root, changed_paths)
    digests = []
    for name in changed_paths:
        actual = _bounded_source_sha256(root / name)
        if actual is None:
            raise CodeShieldHold("STALE_EVIDENCE")
        digests.append((name, actual))
    if len(digests) > 16 or sum((root / name).stat().st_size for name in changed_paths) > _MAX_SOURCES_TOTAL:
        raise CodeShieldHold("UNSAFE_PATH")
    # Request only; the caller cannot use or change these argv to run a tool.
    argv = (
        str(exe), "scan", "--config", str(rules), "--metrics=off",
        "--disable-version-check", "--no-git-ignore", "--disable-nosem",
        "--jobs=1", "--max-target-bytes=262144", "--json", "--error", "--",
        *(str(root / name) for name in changed_paths),
    )
    return SemgrepBrokerRequest(
        context.fingerprint_sha256, context.candidate_git_sha,
        pin.binary_sha256, pin.rules_sha256, pin.version,
        argv, tuple(digests), changed_paths, timeout_seconds,
    )


def read_untrusted_semgrep_report(
    request: SemgrepBrokerRequest, raw: bytes,
    *, exit_code: int,
) -> SemgrepResult:
    """Parse bounded guest/broker JSON; findings may increase HOLD only.

    Even a clean JSON result is UNKNOWN_HOLD because a Python object and an
    exit code cannot prove protected OS egress or independent F18 review.
    """
    if (not isinstance(request, SemgrepBrokerRequest)
        or not isinstance(raw, bytes) or len(raw) > _MAX_REPORT
        or type(exit_code) is not int or exit_code not in (0, 1)):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise CodeShieldHold("UNTRUSTED_DECISION") from None
    if (not isinstance(data, dict) or not isinstance(data.get("results"), list)
        or not isinstance(data.get("errors", []), list) or data.get("errors")):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    findings = data["results"]
    if len(findings) > 10000:
        raise CodeShieldHold("UNTRUSTED_DECISION")
    import ntpath
    allowed = set(request.allowed_paths)
    root = request.argv[-len(request.allowed_paths):]
    accepted = {
        ntpath.normcase(ntpath.normpath(path)) for path in root
    }
    accepted.update(ntpath.normcase(ntpath.normpath(path)) for path in allowed)
    for item in findings:
        if (not isinstance(item, dict)
            or not isinstance(item.get("check_id"), str)
            or not 1 <= len(item["check_id"]) <= 160
            or not isinstance(item.get("path"), str)
            or ntpath.normcase(ntpath.normpath(item["path"])) not in accepted
            or not isinstance(item.get("start"), dict)
            or type(item["start"].get("line")) is not int
            or not 1 <= item["start"]["line"] <= 1000000):
            raise CodeShieldHold("UNTRUSTED_DECISION")
    if (exit_code == 1) != bool(findings):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    # NEVER create ScannerEvidence from unauthenticated result contents.
    return SemgrepResult(
        RiskOutcome.HOLD_HIGH_RISK if findings else RiskOutcome.UNKNOWN_HOLD,
        ScanStatus.FINDINGS if findings else ScanStatus.NOT_RUN,
        "UNTRUSTED_SEMGREP_FINDINGS" if findings else "CLEAN_REPORT_NOT_OS_ATTESTED",
        len(findings), None,
    )


def run_local_semgrep(
    context: CodeShieldContext, *, executable: str | Path,
    local_rules: str | Path, disposable_worktree: str | Path,
    original_checkout: str | Path, changed_paths: tuple[str, ...],
    owner_protected_no_egress: bool = False, timeout_seconds: int = 20,
) -> SemgrepResult:
    """Validate local scan request only; no direct Windows scanner execution.

    The legacy boolean is retained for callers but is NOT an authorization,
    including when True. Actual Semgrep execution requires a separate,
    independently attested native Windows no-egress broker, not yet present.
    """
    if not isinstance(context, CodeShieldContext):
        raise CodeShieldHold()
    if type(owner_protected_no_egress) is not bool:
        raise CodeShieldHold("UNTRUSTED_DECISION")
    if os.name != "nt":
        return _result(context, ScanStatus.NOT_RUN, "WINDOWS_REQUIRED")
    try:
        request = prepare_protected_semgrep_request(
            context, executable=executable, local_rules=local_rules,
            disposable_worktree=disposable_worktree,
            original_checkout=original_checkout,
            changed_paths=changed_paths, timeout_seconds=timeout_seconds,
        )
    except (CodeShieldHold, OSError, ValueError):
        return _result(context, ScanStatus.ERROR, "SEMGREP_INPUT_OR_PIN_HOLD")
    if request.can_spawn or request.network_isolation_attested:
        raise CodeShieldHold("UNTRUSTED_DECISION")
    return _result(
        context, ScanStatus.NOT_RUN, "PROTECTED_EGRESS_BROKER_NOT_IMPLEMENTED",
    )


@dataclass(frozen=True)
class SemgrepRulesInspection:
    """Non-executing local rules pin check, NOT a Semgrep scan receipt."""
    state: str
    rules_sha256: str | None
    expected_rules_sha256: str | None
    can_execute_scanner: bool = False
    can_execute_candidate: bool = False
    independent_f18_verified: bool = False

    def __post_init__(self) -> None:
        if (self.state not in {"LOCAL_RULES_PINNED_STATIC_ONLY", "UNKNOWN_HOLD"}
            or any(getattr(self, field) is not False for field in (
                "can_execute_scanner", "can_execute_candidate",
                "independent_f18_verified",
            ))):
            raise CodeShieldHold("UNTRUSTED_DECISION")


def inspect_packaged_semgrep_rules(context: CodeShieldContext) -> SemgrepRulesInspection:
    """Match only the packaged CodeShield YAML to the trusted-side rule pin.

    No registry/YAML evaluation, no Semgrep binary invocation, no network.
    The caller's pin is still merely data until independently authenticated.
    """
    if not isinstance(context, CodeShieldContext):
        raise CodeShieldHold()
    pin = next((p for p in context.scanner_pins if p.tool == "semgrep"), None)
    expected = pin.rules_sha256 if pin is not None else None
    packaged = Path(__file__).parent / "rules" / "codeshield.yaml"
    actual = _digest(packaged, max_size=_MAX_RULES)
    valid = expected is not None and actual == expected
    return SemgrepRulesInspection(
        "LOCAL_RULES_PINNED_STATIC_ONLY" if valid else "UNKNOWN_HOLD",
        actual, expected,
    )


# CS-SWU-007: manually approved Windows Sandbox fallback (CONFIG ONLY).
# NEVER starts Sandbox, enables Windows features, runs scanners or writes .wsb.
# Microsoft Windows Sandbox supports Networking=Disable and mapped ReadOnly
# folders; actual OS/network isolation and Windows policy require P2 evidence.
from xml.etree import ElementTree as _ET


def _validate_sandbox_xml(xml_text: str) -> None:
    """Reject altered .wsb content even when its digest was recalculated.

    This checks only an inert configuration preview. It does not attest to
    an effective Windows policy or permit launching the Sandbox.
    """
    if (type(xml_text) is not str or not 0 < len(xml_text) <= 4096
        or "<!" in xml_text or "<?" in xml_text):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    try:
        root = _ET.fromstring(xml_text)
    except _ET.ParseError:
        raise CodeShieldHold("UNTRUSTED_DECISION") from None
    settings = (
        ("VGpu", "Disable"), ("Networking", "Disable"),
        ("AudioInput", "Disable"), ("VideoInput", "Disable"),
        ("ProtectedClient", "Enable"), ("PrinterRedirection", "Disable"),
        ("ClipboardRedirection", "Disable"), ("MemoryInMB", "2048"),
    )
    if (root.tag != "Configuration" or root.attrib
        or [part.tag for part in root] != [
            *(name for name, _ in settings), "MappedFolders"
        ]):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    for node, (name, expected) in zip(root, settings):
        if (node.tag != name or node.attrib or len(node) != 0
            or node.text != expected or node.tail not in (None, "")):
            raise CodeShieldHold("UNTRUSTED_DECISION")
    mapped = root[-1]
    if (mapped.attrib or mapped.text not in (None, "")
        or mapped.tail not in (None, "") or len(mapped) != 1):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    entry = mapped[0]
    if (entry.tag != "MappedFolder" or entry.attrib
        or entry.text not in (None, "") or entry.tail not in (None, "")
        or [part.tag for part in entry] != [
            "HostFolder", "SandboxFolder", "ReadOnly"
        ]):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    for part in entry:
        if part.attrib or len(part) != 0 or part.tail not in (None, ""):
            raise CodeShieldHold("UNTRUSTED_DECISION")
    host = entry[0].text
    if (not isinstance(host, str) or not Path(host).is_absolute()
        or ".." in Path(host).parts or len(host) > 180
        or "%" in host or "\x00" in host
        or entry[1].text != r"C:\CodeShieldIn"
        or entry[2].text != "true"):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    # Accept only the exact producer format; discard XML extensions/comments.
    if _ET.tostring(root, encoding="unicode", short_empty_elements=False) != xml_text:
        raise CodeShieldHold("UNTRUSTED_DECISION")


@dataclass(frozen=True)
class OfflineSandboxConfigPreview:
    """Inert fallback .wsb XML from an exactly pinned disposable input staging.

    The host folder must be a *minimal* owner-prepared staging directory:
    semgrep.exe, codeshield.yaml and numbered source copies only. There are no
    host executable actions or Sandbox LogonCommand. Never treat this as OS
    attestation, permission, successful scan, or independent F18.
    """
    request_context_sha256: str
    inventory_sha256: str
    configuration_sha256: str
    xml_text: str
    source_count: int
    stage: str = "WINDOWS_SANDBOX_FALLBACK_CONFIG_ONLY"
    may_launch_sandbox: bool = False
    may_run_scanner: bool = False
    os_isolation_attested: bool = False
    owner_permission_verified: bool = False
    f18_verified: bool = False
    git_promotion_allowed: bool = False

    def __post_init__(self) -> None:
        if (self.stage != "WINDOWS_SANDBOX_FALLBACK_CONFIG_ONLY"
            or type(self.source_count) is not int
            or not 1 <= self.source_count <= 16
            or any(not isinstance(value, str) or len(value) != 64
                   or any(c not in "0123456789abcdef" for c in value)
                   for value in (
                       self.request_context_sha256,
                       self.inventory_sha256,
                       self.configuration_sha256,
                   ))
            or not isinstance(self.xml_text, str)
            or len(self.xml_text) > 4096
            or sha256(self.xml_text.encode("utf-8")).hexdigest()
               != self.configuration_sha256
            or any(getattr(self, flag) is not False for flag in (
                "may_launch_sandbox", "may_run_scanner",
                "os_isolation_attested", "owner_permission_verified",
                "f18_verified", "git_promotion_allowed",
            ))):
            raise CodeShieldHold("UNTRUSTED_DECISION")

        _validate_sandbox_xml(self.xml_text)

    def to_redacted_dict(self) -> dict[str, object]:
        """Never include local paths or executable config in UI/log output."""
        return {
            "stage": self.stage,
            "request_context_sha256": self.request_context_sha256,
            "inventory_sha256": self.inventory_sha256,
            "configuration_sha256": self.configuration_sha256,
            "source_count": self.source_count,
            "networking_requested": "Disable",
            "readonly_mapping_requested": True,
            "logon_command_present": False,
            "may_launch_sandbox": False,
            "may_run_scanner": False,
            "os_isolation_attested": False,
            "f18_verified": False,
            "git_promotion_allowed": False,
        }


def prepare_on_demand_sandbox_fallback(
    request: SemgrepBrokerRequest, *,
    minimal_staging_folder: str | Path,
) -> OfflineSandboxConfigPreview:
    """Return inert, offline Windows Sandbox XML for optional future owner GO.

    This is NOT the default scanner runner. A protected Windows service must
    independently verify the owner principal, staging ACLs, folder inventory,
    OS Sandbox support, effective networking policy and exact Git snapshot.
    No shell, OS settings, file write, .wsb launch, network or model call.
    """
    if not isinstance(request, SemgrepBrokerRequest):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    if os.name != "nt":
        raise CodeShieldHold("WINDOWS_REQUIRED")
    folder = Path(minimal_staging_folder)
    if (not folder.is_absolute() or ".." in folder.parts
        or folder.anchor == str(folder) or len(folder.parts) < 3
        or len(str(folder)) > 180 or "%" in str(folder)):
        raise CodeShieldHold("UNSAFE_PATH")
    # Staging cannot be the candidate source worktree or trusted tool dir.
    toolpath = Path(request.argv[0])
    sources = tuple(request.source_sha256)
    if (not 1 <= len(sources) <= 16 or len(request.allowed_paths) != len(sources)
        or request.can_spawn or request.network_isolation_attested
        or request.owner_go_verified or request.f18_verified):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    if (folder == toolpath.parent or folder in toolpath.parents
        or toolpath in folder.parents
        or any(folder == Path(p).parent or folder in Path(p).parents
               or Path(p) in folder.parents for p in request.argv[-len(sources):])):
        raise CodeShieldHold("UNSAFE_PATH")
    expected = {
        "semgrep.exe": request.binary_sha256,
        "codeshield.yaml": request.rules_sha256,
    }
    for index, (relative, digest) in enumerate(sources):
        if (relative != request.allowed_paths[index]
            or not isinstance(digest, str) or len(digest) != 64
            or any(v not in "0123456789abcdef" for v in digest)):
            raise CodeShieldHold("UNTRUSTED_DECISION")
        suffix = Path(relative).suffix.lower()
        if suffix not in _SUFFIXES:
            raise CodeShieldHold("UNSAFE_PATH")
        expected[f"source_{index:02d}{suffix}"] = digest
    # No unexpected files, nested directories, symlinks, NTFS junctions,
    # hardlinked files or stealth config. Include *only* scanner/rule/sources.
    try:
        for parent in (folder, *folder.parents):
            st = parent.lstat()
            if (not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode)
                or getattr(st, "st_file_attributes", 0)
                   & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                raise CodeShieldHold("UNSAFE_PATH")
        # Bounded enumeration: hostile staging with millions of files must
        # not force unbounded memory allocation in the Controller.
        from itertools import islice
        with os.scandir(folder) as iterator:
            entries = [item.name for item in islice(iterator, len(expected) + 1)]
        if (len(entries) != len(expected)
            or set(entries) != set(expected)
            or len({v.casefold() for v in entries}) != len(entries)):
            raise CodeShieldHold("UNSAFE_PATH")
        for name, digest in expected.items():
            limit = (_MAX_BINARY if name.endswith(".exe")
                     else _MAX_RULES if name.endswith(".yaml")
                     else _MAX_SOURCE_BYTES)
            if _digest(folder / name, max_size=limit) != digest:
                raise CodeShieldHold("STALE_EVIDENCE")
    except CodeShieldHold:
        raise
    except (OSError, ValueError, UnicodeError):
        raise CodeShieldHold("UNSAFE_PATH") from None
    root = _ET.Element("Configuration")
    for key, value in (
        ("VGpu", "Disable"), ("Networking", "Disable"),
        ("AudioInput", "Disable"), ("VideoInput", "Disable"),
        ("ProtectedClient", "Enable"), ("PrinterRedirection", "Disable"),
        ("ClipboardRedirection", "Disable"), ("MemoryInMB", "2048"),
    ):
        _ET.SubElement(root, key).text = value
    mapped = _ET.SubElement(root, "MappedFolders")
    item = _ET.SubElement(mapped, "MappedFolder")
    _ET.SubElement(item, "HostFolder").text = str(folder)
    _ET.SubElement(item, "SandboxFolder").text = r"C:\CodeShieldIn"
    _ET.SubElement(item, "ReadOnly").text = "true"
    xml = _ET.tostring(root, encoding="unicode", short_empty_elements=False)
    # No <LogonCommand>: even starting this config must not auto-run Semgrep.
    if "LogonCommand" in xml:
        raise CodeShieldHold("UNTRUSTED_DECISION")
    inventory = sha256(
        json.dumps({
            "context": request.context_sha256,
            "candidate": request.candidate_git_sha,
            "staging": str(folder),
            "files": sorted(expected.items()),
        }, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return OfflineSandboxConfigPreview(
        request.context_sha256, inventory,
        sha256(xml.encode("utf-8")).hexdigest(),
        xml, len(sources),
    )
