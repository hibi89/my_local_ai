"""Independent static reviewer client, transcript parser and native handler.

The installed protected service reads immutable Git objects and fixed static
checks before issuing a signed STATIC_ONLY report. OS provisioning is separate.
It never emits the legacy executed-test PASS/HMAC receipt or runs guest tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re

from my_local_ai.review.trusted_runner import (
    IsolatedReviewerIntent, MandatoryCheck, ReviewPlanHold,
    build_reviewer_policy,
)

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_SOURCE_POLICY_CHECK_IDS = ("SYNTAX-001", "UNIT-001", "SECURITY-001")
_STATIC_CHECKS = (
    ("SOURCE-SHA-001", 30),
    ("AST-PARSE-001", 60),
    ("STATIC-POLICY-001", 60),
)
_STATIC_CHECK_IDS = tuple(check_id for check_id, _ in _STATIC_CHECKS)
_STATIC_POLICY_SHA256 = sha256(
    b"mla-f18-review-static-only/v1|source-sha|ast-parse|static-policy|no-exec"
).hexdigest()
_UNTRUSTED_TEST_REPORT_SHA256 = sha256(
    b"mla-f18-untrusted-test-report/v1|not-static|not-attested"
).hexdigest()


class ProtectedReviewerHold(ValueError):
    """Fixed bounded denial; never echo guest text or test output."""

    def __init__(self, reason="INDEPENDENT_OS_REVIEWER_NOT_ATTESTED"):
        codes = {
            "INDEPENDENT_OS_REVIEWER_NOT_ATTESTED",
            "STALE_REVIEW_REQUEST", "MANDATORY_REVIEW_FAILED",
            "UNTRUSTED_CHECK_RESULTS", "REVIEWER_NONCE_REUSED",
            "REVIEW_EXECUTION_FORBIDDEN", "STATIC_REVIEW_POLICY_MISMATCH",
        }
        self.code = reason if reason in codes else "INDEPENDENT_OS_REVIEWER_NOT_ATTESTED"
        super().__init__(self.code)


@dataclass(frozen=True)
class HostCheckObservation:
    """Bare check exit observation from a future protected OS reviewer.

    Caller-provided observations are NEVER treated as trusted OS evidence.
    """
    check_id: str
    exit_code: int
    elapsed_ms: int
    timed_out: bool
    output_sha256: str


@dataclass(frozen=True)
class UnsignedReviewerTranscript:
    task_id: str
    run_id: str
    source_sha: str
    candidate_sha: str
    plan_sha256: str
    lease_epoch: int
    policy_sha256: str
    static_policy_sha256: str
    reviewer_binary_sha256: str
    check_ids: tuple[str, ...]
    transcript_sha256: str
    validation_scope: str = "STATIC_ONLY"
    execution_count: int = 0
    state: str = "UNSIGNED_REVIEW_OBSERVATIONS_UNTRUSTED"
    guest_can_issue_receipt: bool = False
    reviewer_os_attested: bool = False
    nonce_consumed: bool = False
    trusted_receipt_issued: bool = False
    may_promote: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.task_id, str) or not _ID.fullmatch(self.task_id)
            or not isinstance(self.run_id, str) or not _ID.fullmatch(self.run_id)
            or not isinstance(self.source_sha, str) or not _SHA40.fullmatch(self.source_sha)
            or not isinstance(self.candidate_sha, str) or not _SHA40.fullmatch(self.candidate_sha)
            or self.source_sha == self.candidate_sha
            or not isinstance(self.plan_sha256, str) or not _SHA64.fullmatch(self.plan_sha256)
            or type(self.lease_epoch) is not int or self.lease_epoch <= 0
            or not isinstance(self.policy_sha256, str) or not _SHA64.fullmatch(self.policy_sha256)
            or not isinstance(self.static_policy_sha256, str)
            or not isinstance(self.reviewer_binary_sha256, str)
            or not _SHA64.fullmatch(self.reviewer_binary_sha256)
            or not isinstance(self.transcript_sha256, str)
            or not _SHA64.fullmatch(self.transcript_sha256)
            or self.validation_scope not in {
                "STATIC_ONLY", "UNTRUSTED_TEST_RESULTS",
            }
            or type(self.execution_count) is not int
            or self.validation_scope == "STATIC_ONLY"
                and (self.static_policy_sha256 != _STATIC_POLICY_SHA256
                     or self.check_ids != _STATIC_CHECK_IDS
                     or self.execution_count != 0)
            or self.validation_scope == "UNTRUSTED_TEST_RESULTS"
                and (self.static_policy_sha256 != _UNTRUSTED_TEST_REPORT_SHA256
                     or self.check_ids != _SOURCE_POLICY_CHECK_IDS
                     or self.execution_count != 2)
            or self.state != "UNSIGNED_REVIEW_OBSERVATIONS_UNTRUSTED"
            or any(getattr(self, field) is not False for field in (
                "guest_can_issue_receipt", "reviewer_os_attested",
                "nonce_consumed", "trusted_receipt_issued", "may_promote",
            ))):
            raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")


@dataclass(frozen=True)
class _StaticReviewCheck:
    check_id: str
    timeout_seconds: int


@dataclass(frozen=True)
class _StaticReviewPolicy:
    checks: tuple[_StaticReviewCheck, ...]


def _validate_protected_review_intent(intent: IsolatedReviewerIntent):
    """Validate the old plan identity, then select a non-executing policy.

    The source plan carries legacy unit/security check IDs. They are accepted
    only as provenance; they are never sent to a runner. This F18 request is
    STATIC_ONLY and contains no test, interpreter, shell, or build command.
    """
    source_policy = build_reviewer_policy()
    if (not isinstance(intent, IsolatedReviewerIntent)
        or intent.state != "HOLD_UNTIL_INDEPENDENT_OS_REVIEWER"
        or intent.executable is not False
        or intent.can_issue_trusted_receipt is not False
        or intent.host_fallback is not False
        or not isinstance(intent.task_id,str) or not _ID.fullmatch(intent.task_id)
        or not isinstance(intent.run_id,str) or not _ID.fullmatch(intent.run_id)
        or not isinstance(intent.source_sha,str) or not _SHA40.fullmatch(intent.source_sha)
        or not isinstance(intent.candidate_sha,str) or not _SHA40.fullmatch(intent.candidate_sha)
        or intent.source_sha == intent.candidate_sha
        or not isinstance(intent.plan_sha256,str) or not _SHA64.fullmatch(intent.plan_sha256)
        or not isinstance(intent.reviewer_binary_sha256,str)
        or not _SHA64.fullmatch(intent.reviewer_binary_sha256)
        or intent.policy_sha256 != source_policy.policy_sha256
        or type(intent.lease_epoch) is not int or intent.lease_epoch <= 0
        or intent.check_ids != _SOURCE_POLICY_CHECK_IDS):
        raise ProtectedReviewerHold("STALE_REVIEW_REQUEST")
    return _StaticReviewPolicy(tuple(
        _StaticReviewCheck(check_id, timeout_seconds)
        for check_id, timeout_seconds in _STATIC_CHECKS
    ))


def canonicalize_fixed_review_observations(
    intent: IsolatedReviewerIntent,
    observations: tuple[HostCheckObservation, ...],
) -> UnsignedReviewerTranscript:
    """Validate unsigned static observations or label legacy test claims.

    The legacy plan includes test command IDs. Those observations remain
    readable for history/compatibility but are explicitly classified as
    UNTRUSTED_TEST_RESULTS and can never enter the STATIC_ONLY receipt path.
    """
    static_policy = _validate_protected_review_intent(intent)
    if not isinstance(observations, tuple):
        raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
    observed_ids = tuple(
        item.check_id if isinstance(item, HostCheckObservation) else None
        for item in observations
    )
    legacy_test_claims = observed_ids == _SOURCE_POLICY_CHECK_IDS
    if legacy_test_claims:
        source_policy = build_reviewer_policy()
        policy = _StaticReviewPolicy(tuple(
            _StaticReviewCheck(check.check_id, check.timeout_seconds)
            for check in source_policy.checks
        ))
        validation_scope = "UNTRUSTED_TEST_RESULTS"
        execution_count = 2
        report_policy_sha256 = _UNTRUSTED_TEST_REPORT_SHA256
    else:
        policy = static_policy
        validation_scope = "STATIC_ONLY"
        execution_count = 0
        report_policy_sha256 = _STATIC_POLICY_SHA256
    if len(observations) != len(policy.checks):
        raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
    normalized=[]
    for observation,check in zip(observations,policy.checks):
        if (not isinstance(observation,HostCheckObservation)
            or observation.check_id != check.check_id
            or type(observation.exit_code) is not int
            or type(observation.elapsed_ms) is not int
            or not 0 <= observation.elapsed_ms <= check.timeout_seconds*1000
            or type(observation.timed_out) is not bool
            or not isinstance(observation.output_sha256,str)
            or not _SHA64.fullmatch(observation.output_sha256)):
            raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
        if observation.exit_code != 0 or observation.timed_out:
            raise ProtectedReviewerHold("MANDATORY_REVIEW_FAILED")
        normalized.append({
            "check_id": check.check_id,
            "elapsed_ms":observation.elapsed_ms,
            "exit_code":observation.exit_code,
            "timed_out":False,
            "output_sha256":observation.output_sha256,
        })
    canonical=json.dumps({
        "version":1,"task_id":intent.task_id,"run_id":intent.run_id,
        "source_sha":intent.source_sha,"candidate_sha":intent.candidate_sha,
        "plan_sha256":intent.plan_sha256,"lease_epoch":intent.lease_epoch,
        "policy_sha256":intent.policy_sha256,
        "static_policy_sha256": report_policy_sha256,
        "reviewer_binary_sha256":intent.reviewer_binary_sha256,
        "validation_scope": validation_scope,
        "execution_count": execution_count,
        "checks":normalized,
    },ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii")
    digest=sha256(b"mla-untrusted-observations/v1|"+canonical).hexdigest()
    return UnsignedReviewerTranscript(
        intent.task_id,intent.run_id,intent.source_sha,intent.candidate_sha,
        intent.plan_sha256,intent.lease_epoch,intent.policy_sha256,
        report_policy_sha256,intent.reviewer_binary_sha256,
        tuple(check.check_id for check in policy.checks),digest,
        validation_scope=validation_scope, execution_count=execution_count,
    )


def require_protected_reviewer_issuer(
    transcript: UnsignedReviewerTranscript, *,
    independent_os_principal_evidence=None,
    owner_signer_evidence=None,
) -> None:
    """P1 never promotes self-declared attestations to protected F18 proof.

    Only an external reviewer process with its own OS-controlled security
    principal and key custody can issue the official, nonce-bound receipt.
    """
    if not isinstance(transcript,UnsignedReviewerTranscript):
        raise ProtectedReviewerHold("STALE_REVIEW_REQUEST")
    raise ProtectedReviewerHold("INDEPENDENT_OS_REVIEWER_NOT_ATTESTED")



# SWU-021: bounded real data ingress for externally extracted F18 observations.
# The reviewer must still execute as a separate *protected* OS principal and
# the receipt must be issued with the protected key outside this module.
def decode_untrusted_reviewer_outbox(
    raw: bytes, intent: IsolatedReviewerIntent,
) -> UnsignedReviewerTranscript:
    """Raw reviewer result bytes -> strict observations -> unsigned digest.

    No user/guest-supplied 'trusted', 'signed', 'passed' or arbitrary argv
    fields are accepted. This function does not run checks, accept owner GO,
    verify the origin of raw bytes, issue a receipt or authorize promotion.
    """
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= 8192:
        raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")

    def no_duplicate_keys(pairs):
        item = {}
        for name, value in pairs:
            if name in item:
                raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
            item[name] = value
        return item

    try:
        data = json.loads(
            raw.decode("utf-8"), object_pairs_hook=no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS") from None
    if (not isinstance(data, dict)
        or set(data) != {
            "version", "task_id", "run_id", "source_sha",
            "candidate_sha", "plan_sha256", "lease_epoch",
            "policy_sha256", "static_policy_sha256", "reviewer_binary_sha256",
            "validation_scope", "execution_count", "checks",
        } or type(data["version"]) is not int or data["version"] != 1
        or not isinstance(intent, IsolatedReviewerIntent)
        or data["task_id"] != intent.task_id
        or data["run_id"] != intent.run_id
        or data["source_sha"] != intent.source_sha
        or data["candidate_sha"] != intent.candidate_sha
        or data["plan_sha256"] != intent.plan_sha256
        or type(data["lease_epoch"]) is not int
        or data["lease_epoch"] != intent.lease_epoch
        or data["reviewer_binary_sha256"] != intent.reviewer_binary_sha256
        or data["policy_sha256"] != intent.policy_sha256
        or data["static_policy_sha256"] != _STATIC_POLICY_SHA256
        or data["validation_scope"] != "STATIC_ONLY"
        or type(data["execution_count"]) is not int
        or data["execution_count"] != 0
        or not isinstance(data["checks"], list)):
        raise ProtectedReviewerHold("STALE_REVIEW_REQUEST")
    policy = _validate_protected_review_intent(intent)
    if len(data["checks"]) != len(policy.checks):
        raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
    observations = []
    for item, check in zip(data["checks"], policy.checks):
        if (not isinstance(item, dict)
            or set(item) != {
                "check_id", "exit_code", "elapsed_ms",
                "timed_out", "output_sha256",
            }
            or item["check_id"] != check.check_id
            or type(item["exit_code"]) is not int
            or type(item["elapsed_ms"]) is not int
            or type(item["timed_out"]) is not bool
            or not isinstance(item["output_sha256"], str)
            or not _SHA64.fullmatch(item["output_sha256"])):
            raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
        observations.append(HostCheckObservation(
            item["check_id"], item["exit_code"], item["elapsed_ms"],
            item["timed_out"], item["output_sha256"],
        ))
    # A passing transcript is *never* authenticated OS evidence.
    return canonicalize_fixed_review_observations(
        intent, tuple(observations),
    )


# SWU-021: bounded reader for the *untrusted*, never signed, reviewer outbox.
# Only independently protected Windows reviewer/issuer can attest OS identity,
# consume a lease nonce and sign a genuine F18 receipt.
from pathlib import Path as _Path, PureWindowsPath as _PureWindowsPath
import os as _os
import stat as _stat

_MAX_F18_OUTBOX_BYTES = 8192
_REPARSE_ATTRIBUTE = getattr(_stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _lstat_review_outbox_parent_chain(parent: _Path) -> tuple[tuple[int, int, int], ...]:
    result = []
    for segment in (parent, *parent.parents):
        info = segment.lstat()
        if (not _stat.S_ISDIR(info.st_mode) or _stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE):
            raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
        result.append((info.st_dev, info.st_ino, info.st_mode))
    return tuple(result)


def read_untrusted_reviewer_outbox_from_scratch(
    intent: IsolatedReviewerIntent,
) -> UnsignedReviewerTranscript:
    """Read fixed local reviewer outbox → validate pinned lease/checks → digest.

    Windows-only; exact path C:\MLA_Disposable\<run_id>\review\outbox.json.
    No execution, no arbitrary caller path, no follow-symlink fallback, no
    deletion/writes, no F18 receipt issuing. Same-user scratch can be forged,
    so a valid UNSIGNED transcript is ALWAYS untrusted, even on hash match.
    """
    if (_os.name != "nt" or not isinstance(intent, IsolatedReviewerIntent)
        or not isinstance(intent.run_id, str) or not _ID.fullmatch(intent.run_id)):
        raise ProtectedReviewerHold("INDEPENDENT_OS_REVIEWER_NOT_ATTESTED")
    filename = _Path(str(
        _PureWindowsPath(r"C:\MLA_Disposable")
        / intent.run_id / "review" / "outbox.json"
    ))
    try:
        ancestry = _lstat_review_outbox_parent_chain(filename.parent)
        before = filename.lstat()
        if (not _stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or getattr(before, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE
            or not 1 <= before.st_size <= _MAX_F18_OUTBOX_BYTES):
            raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
        flags = (_os.O_RDONLY | getattr(_os, "O_BINARY", 0)
                 | getattr(_os, "O_NOFOLLOW", 0))
        fd = _os.open(filename, flags)
        with _os.fdopen(fd, "rb") as stream:
            opened = _os.fstat(stream.fileno())
            raw = stream.read(_MAX_F18_OUTBOX_BYTES + 1)
            final_handle = _os.fstat(stream.fileno())
        after = filename.lstat()
        identity = (
            before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
        )
        if (len(raw) != before.st_size
            or (opened.st_dev, opened.st_ino, opened.st_size,
                opened.st_mtime_ns) != identity
            or (final_handle.st_dev, final_handle.st_ino,
                final_handle.st_size, final_handle.st_mtime_ns) != identity
            or (after.st_dev, after.st_ino, after.st_size,
                after.st_mtime_ns) != identity
            or _lstat_review_outbox_parent_chain(filename.parent) != ancestry):
            raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
    except ProtectedReviewerHold:
        raise
    except (OSError, OverflowError, ValueError):
        raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS") from None
    # The decoder verifies task/run/source/candidate/plan/lease/policy/binary
    # against the fixed F18 policy, and returns only an UNSIGNED transcript.
    return decode_untrusted_reviewer_outbox(raw, intent)


@dataclass(frozen=True)
class ProtectedReviewSubmission:
    """Authenticated STATIC_ONLY service evidence for later P2 acceptance.

    Keep the opaque signed envelope intact. It cannot be converted to the old
    guest-supplied HMAC receipt or an in-process Git promotion capability.
    Static evidence is not executed-test evidence and cannot be promoted to it.
    """
    transcript: UnsignedReviewerTranscript
    signed_service_receipt: str
    validation_scope: str = "STATIC_ONLY"
    execution_count: int = 0
    state: str = "PROTECTED_REVIEW_REPORT_P2_ACCEPTANCE_PENDING"
    may_promote: bool = False
    independently_accepted: bool = False

    def __post_init__(self):
        if (not isinstance(self.transcript, UnsignedReviewerTranscript)
            or type(self.signed_service_receipt) is not str
            or not 1 <= len(self.signed_service_receipt) <= 32768
            or self.validation_scope != "STATIC_ONLY"
            or type(self.execution_count) is not int or self.execution_count != 0
            or self.transcript.validation_scope != self.validation_scope
            or self.transcript.execution_count != self.execution_count
            or self.state != "PROTECTED_REVIEW_REPORT_P2_ACCEPTANCE_PENDING"
            or self.may_promote is not False or self.independently_accepted is not False):
            raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")


def review_protected_candidate(intent: IsolatedReviewerIntent, *,
                               nonce_sha256: str, owner_consent_ref: str) -> ProtectedReviewSubmission:
    """Static-only source review -> independent reviewer -> signed receipt.

    The protected reviewer, not the coder/Controller, must read back the
    immutable candidate SHA, run only fixed non-executing source/static checks,
    recheck the live epoch and atomically consume the nonce before signing.
    Test, build, shell and generated-code execution are forbidden on this
    path. Missing service/owner/P2 authority, replay, failed checks or pin
    mismatches HOLD. No caller callback, supplied key, check result or argv is
    used as authority.
    """
    import base64
    from my_local_ai.state.consent import ProtectedBrokerHold, dispatch_protected_action
    if not isinstance(intent, IsolatedReviewerIntent):
        raise ProtectedReviewerHold("STALE_REVIEW_REQUEST")
    policy = _validate_protected_review_intent(intent)
    try:
        reply = dispatch_protected_action("reviewer", "review", binding={
            "task_id": intent.task_id, "run_id": intent.run_id,
            "plan_sha256": intent.plan_sha256, "source_sha": intent.source_sha,
            "candidate_sha": intent.candidate_sha, "lease_epoch": intent.lease_epoch,
            "nonce_sha256": nonce_sha256, "owner_consent_ref": owner_consent_ref,
        }, payload={"policy_sha256": intent.policy_sha256,
            "static_policy_sha256": _STATIC_POLICY_SHA256,
            "reviewer_binary_sha256": intent.reviewer_binary_sha256,
            "check_ids": list(_STATIC_CHECK_IDS),
            "validation_scope": "STATIC_ONLY", "execution_count": 0,
            "execution_permitted": False,
            "policy": "F18_STATIC_ONLY_V1"},
            timeout_seconds=sum(c.timeout_seconds for c in policy.checks) + 10)
        result = reply["result"]
        if (set(result) != {
                "observations_b64", "nonce_state", "lease_state",
                "reviewer_binary_sha256", "source_sha", "candidate_sha",
                "static_policy_sha256", "validation_scope", "execution_count",
                "evidence_sha256",
            }
            or result["nonce_state"] != "CONSUMED" or result["lease_state"] != "LIVE_AT_SIGNING"
            or result["reviewer_binary_sha256"] != intent.reviewer_binary_sha256
            or result["reviewer_binary_sha256"] != reply["peer_image_sha256"]
            or result["source_sha"] != intent.source_sha
            or result["candidate_sha"] != intent.candidate_sha
            or result["static_policy_sha256"] != _STATIC_POLICY_SHA256
            or result["validation_scope"] != "STATIC_ONLY"
            or type(result["execution_count"]) is not int
            or result["execution_count"] != 0
            or not isinstance(result["evidence_sha256"], str)
            or not _SHA64.fullmatch(result["evidence_sha256"])
            or type(result["observations_b64"]) is not str or len(result["observations_b64"]) > 10924):
            raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
        raw = base64.b64decode(result["observations_b64"], validate=True)
        if sha256(raw).hexdigest() != result["evidence_sha256"]:
            raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
        transcript = decode_untrusted_reviewer_outbox(raw, intent)
        if transcript.check_ids != _STATIC_CHECK_IDS:
            raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
        # Signature verification already occurred in the authenticated transport;
        # the unsigned inner transcript still cannot confer VERIFIED or Git GO.
        return ProtectedReviewSubmission(
            transcript, reply["signed_envelope"],
            validation_scope="STATIC_ONLY", execution_count=0,
        )
    except ProtectedReviewerHold:
        raise
    except ProtectedBrokerHold:
        raise ProtectedReviewerHold("INDEPENDENT_OS_REVIEWER_NOT_ATTESTED") from None
    except (ValueError, TypeError, KeyError):
        raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS") from None


def _bounded_review_changed_paths(
    source: dict[str, tuple[str, str]],
    candidate: dict[str, tuple[str, str]],
    allowed_paths: list[str],
) -> tuple[str, ...]:
    """Prove changed-file lexical scope before any candidate bytes are accepted.

    This is data validation, not a Git trust receipt. A protected mirror
    supplies the two content-addressed tree inventories. Matching the
    CodeShield lexical check alone is insufficient on Windows: a PlanSpec
    disallows reserved device names, aliases, glob syntax and non-ASCII paths.
    No deleted, renamed-out-of-scope or non-Python candidate can pass.
    """
    from my_local_ai.security.codeshield_contracts import checked_relative_path
    from my_local_ai.contracts.task import safe_path
    from my_local_ai.state.consent import ProtectedBrokerHold
    changed = tuple(sorted(path for path in source.keys() | candidate.keys()
                           if source.get(path) != candidate.get(path)))
    if (not changed or not set(changed) <= set(allowed_paths)
        or any(path not in candidate or not path.endswith(".py") for path in changed)):
        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
    # Scope authorizes TEXT changes, not Git executable-mode transitions.
    # A mode-only diff or a newly executable script cannot be accepted as a
    # STATIC_ONLY Python candidate even when its bytes parse successfully.
    # An existing executable file can be reviewed only with its mode unchanged.
    for path in changed:
        candidate_mode = candidate[path][0]
        source_mode = source[path][0] if path in source else "100644"
        if (candidate_mode not in {"100644", "100755"}
            or source_mode != candidate_mode):
            raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
    try:
        for path in changed:
            safe_path(checked_relative_path(path))
    except ValueError:
        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED") from None
    return changed


def _decode_protected_git_tree_listing(listing: bytes) -> dict[str, tuple[str, str]]:
    """Decode a bounded, NUL-terminated Git tree without collapsing duplicates.

    A Git tree can be malformed despite matching its object ID. Reject exact
    and case-insensitive duplicate paths BEFORE Python dictionary insertion.
    This does not execute or check out untrusted repository content.
    """
    from my_local_ai.state.consent import ProtectedBrokerHold
    if type(listing) is not bytes or not listing or not listing.endswith(b"\x00"):
        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
    entries = listing[:-1].split(b"\x00")
    if not 1 <= len(entries) <= 4096:
        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
    result = {}
    seen_casefold = set()
    for item in entries:
        try:
            meta, name = item.split(b"\t", 1)
            mode, kind, digest = meta.decode("ascii").split(" ")
            path = name.decode("utf-8")
        except (ValueError, UnicodeError):
            raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED") from None
        if (not path or len(path) > 240 or path.startswith("/")
            or "\\" in path or ":" in path
            or any(part in ("", ".", "..") for part in path.split("/"))
            or any(ord(ch) < 32 for ch in path)
            or mode not in {"100644", "100755"}
            or kind != "blob" or not _SHA40.fullmatch(digest)):
            raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
        key = path.casefold()
        if key in seen_casefold:
            raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
        seen_casefold.add(key)
        result[path] = (mode, digest)
    return result


def _read_protected_git_candidate(api, binding: dict, scope: dict, stopped) -> dict[str, bytes]:
    """Read immutable Git objects with one pinned, non-filtering Git operator.

    Never checks out a tree, imports a module, runs a hook/filter, loads local
    tools or follows a promisor remote. Every commit/blob is independently
    content-address checked. Scope/plan come from the protected authority DB.
    """
    import hashlib
    import winreg
    from my_local_ai.state.consent import ProtectedBrokerHold
    root = _Path(scope["repository_path"])
    # Repository used here is an independently provisioned read-only bare
    # mirror, never the Controller's writable checkout or candidate worktree.
    if root == _Path(scope["disposable_root"]):
        raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\MyLocalAI\ProtectedBrokers\v1\reviewer", 0,
        winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        git_path, pkind = winreg.QueryValueEx(key, "GitPath")
        git_sha, hkind = winreg.QueryValueEx(key, "GitSha256")
    if (pkind != winreg.REG_SZ or hkind != winreg.REG_SZ
        or type(git_path) is not str or type(git_sha) is not str
        or not _SHA64.fullmatch(git_sha) or not _Path(git_path).is_absolute()
        or _Path(git_path).name.casefold() != "git.exe"):
        raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
    # Retain image/ancestor locks for all Git reads, then close them. The
    # repository directory is also protected, including its object/config DB.
    with _ExitStackForReview(api):
        api.pin_path(_Path(git_path))
        api.pin_path(root / "HEAD")
        # Reject unprotected/reparse object stores and alternates. A private
        # read-only bare mirror is a provisioning requirement, not a claim in
        # the Controller request. Packed and loose objects are both supported.
        count = 0
        for directory, subdirs, filenames in _os.walk(root, followlinks=False):
            for name in (*subdirs, *filenames):
                node = _Path(directory) / name
                info = node.lstat()
                if (_stat.S_ISLNK(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE):
                    raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
            for name in filenames:
                path = _Path(directory) / name
                count += 1
                if count > 1024 or path.name in {"alternates", "http-alternates", "grafts"}:
                    raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
                api.pin_path(path)
        if sha256(_Path(git_path).read_bytes()).hexdigest() != git_sha:
            raise ProtectedBrokerHold("PROTECTED_BROKER_IDENTITY")
        system_root = _os.environ.get("SystemRoot", r"C:\Windows")
        env = {"SystemRoot": system_root, "WINDIR": system_root,
               "PATH": str(_Path(system_root) / "System32"),
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": "NUL",
               "GIT_CONFIG_GLOBAL": "NUL", "GIT_NO_REPLACE_OBJECTS": "1",
               "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0",
               "GIT_OPTIONAL_LOCKS": "0", "GIT_ATTR_NOSYSTEM": "1"}
        deadline = _timeForReview.monotonic() + 30
        def git(*args):
            if stopped.is_set() or _timeForReview.monotonic() >= deadline:
                raise ProtectedBrokerHold("PROTECTED_BROKER_TIMEOUT")
            prefix = [git_path, "--no-pager", "--no-optional-locks",
                      "--git-dir=" + str(root), "-c", "core.fsmonitor=false",
                      "-c", "core.hooksPath=NUL", "-c", "core.attributesFile=NUL"]
            # Fixed product-owned executable/argv only, never candidate argv.
            from my_local_ai.state.consent import _run_bounded_fixed_process
            code, out, err, timed_out = _run_bounded_fixed_process(
                prefix + list(args), cwd=root, env=env,
                timeout_seconds=max(0.1, deadline - _timeForReview.monotonic()),
                stopped=stopped, output_limit=2 * 1024 * 1024,
            )
            if timed_out:
                raise ProtectedBrokerHold("PROTECTED_BROKER_TIMEOUT")
            if code != 0 or err:
                raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
            return out
        def object_bytes(kind, oid):
            data = git("cat-file", kind, oid)
            canonical = kind.encode("ascii") + b" " + str(len(data)).encode("ascii") + b"\x00" + data
            if hashlib.sha1(canonical).hexdigest() != oid:
                raise ProtectedBrokerHold("PROTECTED_BROKER_SIGNATURE")
            return data
        def tree(oid):
            object_bytes("commit", oid)
            listing = git("ls-tree", "-rz", "--full-tree", oid)
            return _decode_protected_git_tree_listing(listing)
        source, candidate = tree(binding["source_sha"]), tree(binding["candidate_sha"])
        changed = _bounded_review_changed_paths(
            source, candidate, scope["allowed_paths"]
        )
        files = {}
        for path in changed:
            data = object_bytes("blob", candidate[path][1])
            if not 1 <= len(data) <= 256 * 1024:
                raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
            files[path] = data
        if sum(map(len, files.values())) > 1024 * 1024:
            raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
        return files


# Keep native path locks scoped to a request; long-running services must not
# accumulate one handle per source object or scan.
from contextlib import ExitStack as _ReviewExitStack
import time as _timeForReview


class _ExitStackForReview:
    def __init__(self, api):
        self.api = api

    def __enter__(self):
        self.previous = self.api.resources
        self.api.resources = _ReviewExitStack()
        return self.api.resources

    def __exit__(self, *exc):
        try:
            return self.api.resources.__exit__(*exc)
        finally:
            self.api.resources = self.previous


def _serve_static_review(api, binding: dict, payload: dict, scope: dict, stopped) -> dict:
    """Independent server: protected Git readback -> AST/static evidence -> receipt.

    REQ-14 originally asks for executed unit/security tests. Zero-VM §L forbids
    executing those generated tests. This server explicitly reports STATIC_ONLY;
    it cannot satisfy or downgrade the executed-test acceptance condition. The
    old receipt_guard PASS/HMAC route remains separate and rejects this schema.
    """
    import ast
    import base64
    from my_local_ai.state.consent import ProtectedBrokerHold, _broker_canonical
    from my_local_ai.security.ast_preflight import scan_python_sources
    from my_local_ai.security.codeshield_contracts import CodeShieldContext, DataClass, RiskOutcome
    expected = {"policy_sha256", "static_policy_sha256", "reviewer_binary_sha256",
                "check_ids", "validation_scope", "execution_count", "execution_permitted", "policy"}
    if (type(payload) is not dict or set(payload) != expected
        or payload["policy_sha256"] != build_reviewer_policy().policy_sha256
        or payload["static_policy_sha256"] != _STATIC_POLICY_SHA256
        or payload["reviewer_binary_sha256"] != api.roots["reviewer"][1]
        or payload["check_ids"] != list(_STATIC_CHECK_IDS)
        or payload["validation_scope"] != "STATIC_ONLY"
        or type(payload["execution_count"]) is not int or payload["execution_count"] != 0
        or payload["execution_permitted"] is not False
        or payload["policy"] != "F18_STATIC_ONLY_V1"):
        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
    started = _timeForReview.monotonic()
    files = _read_protected_git_candidate(api, binding, scope, stopped)
    source_evidence = {path: sha256(data).hexdigest() for path, data in files.items()}
    observations = [{"check_id": "SOURCE-SHA-001", "exit_code": 0,
        "elapsed_ms": min(30000, int((_timeForReview.monotonic() - started) * 1000)),
        "timed_out": False, "output_sha256": sha256(_broker_canonical(source_evidence)).hexdigest()}]
    started = _timeForReview.monotonic()
    for path, content in files.items():
        if stopped.is_set():
            raise ProtectedBrokerHold("PROTECTED_BROKER_TIMEOUT")
        ast.parse(content.decode("utf-8"), filename="<candidate>", mode="exec")
    observations.append({"check_id": "AST-PARSE-001", "exit_code": 0,
        "elapsed_ms": int((_timeForReview.monotonic() - started) * 1000),
        "timed_out": False, "output_sha256": sha256(b"AST_PARSE_ONLY").hexdigest()})
    context = CodeShieldContext("hibi89/my_local_ai", binding["task_id"], binding["run_id"],
        binding["owner_consent_ref"], binding["plan_sha256"], binding["source_sha"],
        binding["candidate_sha"], binding["lease_epoch"], binding["nonce_sha256"],
        tuple(scope["allowed_paths"]), DataClass.PUBLIC_SYNTHETIC, ())
    started = _timeForReview.monotonic()
    report = scan_python_sources(context, files)
    if report.outcome != RiskOutcome.ALLOW_NON_EXECUTING or report.findings:
        raise ProtectedBrokerHold("PROTECTED_RUNTIME_DENIED")
    observations.append({"check_id": "STATIC-POLICY-001", "exit_code": 0,
        "elapsed_ms": int((_timeForReview.monotonic() - started) * 1000),
        "timed_out": False, "output_sha256": sha256(_broker_canonical({
            "context_sha256": report.context_sha256, "digests": report.file_digests,
            "reason": report.reason})).hexdigest()})
    raw = _broker_canonical({"version": 1, "task_id": binding["task_id"],
        "run_id": binding["run_id"], "source_sha": binding["source_sha"],
        "candidate_sha": binding["candidate_sha"], "plan_sha256": binding["plan_sha256"],
        "lease_epoch": binding["lease_epoch"], "policy_sha256": payload["policy_sha256"],
        "static_policy_sha256": _STATIC_POLICY_SHA256,
        "reviewer_binary_sha256": api.roots["reviewer"][1], "validation_scope": "STATIC_ONLY",
        "execution_count": 0, "checks": observations})
    # Reuse exactly the client decoder. A server may never mint a result the
    # fixed trusted_runner/STATIC_ONLY client contract cannot consume.
    intent = IsolatedReviewerIntent(binding["task_id"], binding["run_id"], binding["plan_sha256"],
        binding["source_sha"], binding["candidate_sha"], binding["lease_epoch"],
        payload["policy_sha256"], api.roots["reviewer"][1], _SOURCE_POLICY_CHECK_IDS)
    decode_untrusted_reviewer_outbox(raw, intent)
    return {"observations_b64": base64.b64encode(raw).decode("ascii"),
        "nonce_state": "CONSUMED", "lease_state": "LIVE_AT_SIGNING",
        "reviewer_binary_sha256": api.roots["reviewer"][1],
        "source_sha": binding["source_sha"], "candidate_sha": binding["candidate_sha"],
        "static_policy_sha256": _STATIC_POLICY_SHA256, "validation_scope": "STATIC_ONLY",
        "execution_count": 0, "evidence_sha256": sha256(raw).hexdigest()}


if __name__ == "__main__":
    from my_local_ai.state.consent import protected_service_main
    raise SystemExit(protected_service_main("reviewer"))
