"""Independent F18 reviewer host-broker input boundary (source-only).

The coder must never supply the reviewer executable, policy, results, signer,
nonce or OS principal. This module constructs a canonical *UNSIGNED* review
transcript from a fixed policy and an independently supplied host check report.
It cannot mint a TrustedReceipt: a separately installed/protected Windows
reviewer must attest the actual principal, deny egress, consume the nonce and
sign the result. No guest process or test is run in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re

from .trusted_runner import (
    IsolatedReviewerIntent, MandatoryCheck, ReviewPlanHold,
    build_reviewer_policy,
)

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")


class ProtectedReviewerHold(ValueError):
    """Fixed bounded denial; never echo guest text or test output."""

    def __init__(self, reason="INDEPENDENT_OS_REVIEWER_NOT_ATTESTED"):
        codes = {
            "INDEPENDENT_OS_REVIEWER_NOT_ATTESTED",
            "STALE_REVIEW_REQUEST", "MANDATORY_REVIEW_FAILED",
            "UNTRUSTED_CHECK_RESULTS", "REVIEWER_NONCE_REUSED",
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
    reviewer_binary_sha256: str
    check_ids: tuple[str, ...]
    transcript_sha256: str
    state: str = "UNSIGNED_REVIEW_OBSERVATIONS_UNTRUSTED"
    guest_can_issue_receipt: bool = False
    reviewer_os_attested: bool = False
    nonce_consumed: bool = False
    trusted_receipt_issued: bool = False
    may_promote: bool = False


def _validate_protected_review_intent(intent: IsolatedReviewerIntent):
    """Validate fixed policy bindings without manufacturing check observations."""
    policy=build_reviewer_policy()
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
        or intent.policy_sha256 != policy.policy_sha256
        or type(intent.lease_epoch) is not int or intent.lease_epoch <= 0
        or intent.check_ids != tuple(check.check_id for check in policy.checks)):
        raise ProtectedReviewerHold("STALE_REVIEW_REQUEST")
    return policy


def canonicalize_fixed_review_observations(
    intent: IsolatedReviewerIntent,
    observations: tuple[HostCheckObservation, ...],
) -> UnsignedReviewerTranscript:
    """Validate untrusted observations; no signature or execution authority."""
    policy = _validate_protected_review_intent(intent)
    if not isinstance(observations,tuple) or len(observations)!=len(policy.checks):
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
            "check_id":check.check_id,
            "argv":list(check.argv),
            "timeout_seconds":check.timeout_seconds,
            "elapsed_ms":observation.elapsed_ms,
            "exit_code":observation.exit_code,
            "timed_out":False,
            "output_sha256":observation.output_sha256,
            "network_disabled_required":check.no_network,
        })
    canonical=json.dumps({
        "version":1,"task_id":intent.task_id,"run_id":intent.run_id,
        "source_sha":intent.source_sha,"candidate_sha":intent.candidate_sha,
        "plan_sha256":intent.plan_sha256,"lease_epoch":intent.lease_epoch,
        "policy_sha256":intent.policy_sha256,
        "reviewer_binary_sha256":intent.reviewer_binary_sha256,
        "checks":normalized,
    },ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii")
    digest=sha256(b"mla-untrusted-observations/v1|"+canonical).hexdigest()
    return UnsignedReviewerTranscript(
        intent.task_id,intent.run_id,intent.source_sha,intent.candidate_sha,
        intent.plan_sha256,intent.lease_epoch,intent.policy_sha256,
        intent.reviewer_binary_sha256,intent.check_ids,digest,
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
            "policy_sha256", "reviewer_binary_sha256", "checks",
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
        or not isinstance(data["checks"], list)):
        raise ProtectedReviewerHold("STALE_REVIEW_REQUEST")
    policy = build_reviewer_policy()
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
    """Authenticated service evidence for later independent P2 acceptance.

    Keep the opaque signed envelope intact. It cannot be converted to the old
    guest-supplied HMAC receipt or an in-process Git promotion capability.
    """
    transcript: UnsignedReviewerTranscript
    signed_service_receipt: str
    state: str = "PROTECTED_REVIEW_REPORT_P2_ACCEPTANCE_PENDING"
    may_promote: bool = False
    independently_accepted: bool = False

    def __post_init__(self):
        if (not isinstance(self.transcript, UnsignedReviewerTranscript)
            or type(self.signed_service_receipt) is not str
            or not 1 <= len(self.signed_service_receipt) <= 32768
            or self.state != "PROTECTED_REVIEW_REPORT_P2_ACCEPTANCE_PENDING"
            or self.may_promote is not False or self.independently_accepted is not False):
            raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")


def review_protected_candidate(intent: IsolatedReviewerIntent, *,
                               nonce_sha256: str, owner_consent_ref: str) -> ProtectedReviewSubmission:
    """Fixed policy -> independent reviewer service -> signed nonce-bound report.

    The protected reviewer, not the coder/Controller, must fetch the immutable
    candidate, execute every fixed check in its own no-egress OS compartment,
    recheck the live epoch and atomically consume nonce before signing. Missing
    service/owner/P2 authority, replay, failed check or mismatched pins HOLDS.
    No caller callback, supplied key, check result or arbitrary argv is used.
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
            "reviewer_binary_sha256": intent.reviewer_binary_sha256,
            "check_ids": list(intent.check_ids), "policy": "F18_FIXED_CHECKS_V1"},
            timeout_seconds=sum(c.timeout_seconds for c in policy.checks) + 10)
        result = reply["result"]
        if (set(result) != {"observations_b64", "nonce_state", "lease_state", "reviewer_binary_sha256"}
            or result["nonce_state"] != "CONSUMED" or result["lease_state"] != "LIVE_AT_SIGNING"
            or result["reviewer_binary_sha256"] != intent.reviewer_binary_sha256
            or result["reviewer_binary_sha256"] != reply["peer_image_sha256"]
            or type(result["observations_b64"]) is not str or len(result["observations_b64"]) > 10924):
            raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS")
        raw = base64.b64decode(result["observations_b64"], validate=True)
        transcript = decode_untrusted_reviewer_outbox(raw, intent)
        # Signature verification already occurred in the authenticated transport;
        # the unsigned inner transcript still cannot confer VERIFIED or Git GO.
        return ProtectedReviewSubmission(transcript, reply["signed_envelope"])
    except ProtectedReviewerHold:
        raise
    except ProtectedBrokerHold:
        raise ProtectedReviewerHold("INDEPENDENT_OS_REVIEWER_NOT_ATTESTED") from None
    except (ValueError, TypeError, KeyError):
        raise ProtectedReviewerHold("UNTRUSTED_CHECK_RESULTS") from None
