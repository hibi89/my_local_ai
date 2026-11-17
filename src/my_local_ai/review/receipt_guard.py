"""Strict F18 receipt *inspection*, never owner consent or ref-promotion.

Only a trusted independent OS reviewer can produce a receipt and protect its
HMAC key. Guest-supplied JSON/MAC/exit codes and checksum alone mean nothing.
This parser cannot prove the origin of a key or the reviewer OS boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from typing import Callable

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_MAX_BYTES = 16_384


class ReceiptHold(ValueError):
    def __init__(self, reason: str = "UNTRUSTED_RECEIPT"):
        self.code = reason if reason in {
            "UNTRUSTED_RECEIPT", "MISSING_PROTECTED_KEY", "CONTEXT_MISMATCH",
            "MISSING_MANDATORY_CHECK", "STALE_LEASE_OR_NONCE", "BAD_SIGNATURE",
        } else "UNTRUSTED_RECEIPT"
        super().__init__(self.code)


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptHold()
        result[key] = value
    return result


@dataclass(frozen=True)
class ExpectedReceipt:
    task_id: str
    run_id: str
    plan_sha256: str
    source_sha: str
    candidate_sha: str
    reviewer_sha256: str
    policy_sha256: str
    trust_boundary_id: str
    lease_epoch: int
    nonce: str
    mandatory_argv_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReceiptInspection:
    task_id: str
    candidate_sha: str
    signature_matches: bool
    status: str = "SIGNATURE_CHECKED_F18_NOT_PROVEN"
    independent_os_review_proven: bool = False
    may_promote_git_ref: bool = False


_FIELDS = frozenset({
    "version", "task_id", "run_id", "plan_sha256", "source_sha",
    "candidate_sha", "reviewer_sha256", "policy_sha256",
    "trust_boundary_id", "lease_epoch", "nonce", "checks",
    "result", "signature",
})
_CHECK_FIELDS = frozenset({"argv_id", "environment", "exit_code", "result"})


def _payload_without_signature(value: dict) -> bytes:
    return json.dumps(
        {k: v for k, v in value.items() if k != "signature"},
        ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def inspect_receipt(
    raw_json: str, expected: ExpectedReceipt, *,
    trusted_hmac_key: bytes | None = None,
    trusted_consume_nonce: Callable[[str, int, str], bool] | None = None,
) -> ReceiptInspection:
    """Protected caller supplies key and atomic one-time nonce consumer.

    A successful MAC inspection is NOT F18 independent OS isolation proof.
    """
    if not isinstance(expected, ExpectedReceipt):
        raise ReceiptHold()
    if (not isinstance(raw_json, str)
        or len(raw_json.encode("utf-8")) > _MAX_BYTES):
        raise ReceiptHold()
    try:
        receipt = json.loads(raw_json, object_pairs_hook=_no_duplicate_keys,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ReceiptHold() from None
    if not isinstance(receipt, dict) or set(receipt) != _FIELDS or type(receipt["version"]) is not int or receipt["version"] != 1:
        raise ReceiptHold()
    for field, value, regex in (
        ("plan_sha256", expected.plan_sha256, _SHA64),
        ("source_sha", expected.source_sha, _SHA40),
        ("candidate_sha", expected.candidate_sha, _SHA40),
        ("reviewer_sha256", expected.reviewer_sha256, _SHA64),
        ("policy_sha256", expected.policy_sha256, _SHA64),
    ):
        if (not isinstance(receipt[field], str) or not regex.fullmatch(receipt[field])
            or receipt[field] != value):
            raise ReceiptHold("CONTEXT_MISMATCH")
    for field in ("task_id", "run_id", "trust_boundary_id", "nonce"):
        if (not isinstance(receipt[field], str) or not _ID.fullmatch(receipt[field])
            or receipt[field] != getattr(expected, field)):
            raise ReceiptHold("CONTEXT_MISMATCH")
    if (type(receipt["lease_epoch"]) is not int
        or receipt["lease_epoch"] != expected.lease_epoch or expected.lease_epoch <= 0):
        raise ReceiptHold("STALE_LEASE_OR_NONCE")
    if receipt["result"] != "PASS":
        raise ReceiptHold("MISSING_MANDATORY_CHECK")
    checks = receipt["checks"]
    if (not isinstance(checks, list) or not 1 <= len(checks) <= 32
        or len(expected.mandatory_argv_ids) != len(checks)
        or len(set(expected.mandatory_argv_ids)) != len(checks)):
        raise ReceiptHold("MISSING_MANDATORY_CHECK")
    returned_ids = []
    for entry in checks:
        if (not isinstance(entry, dict) or set(entry) != _CHECK_FIELDS
            or not isinstance(entry["argv_id"], str) or not _ID.fullmatch(entry["argv_id"])
            or entry["environment"] != "ISOLATED_TRUSTED_REVIEWER"
            or type(entry["exit_code"]) is not int or entry["exit_code"] != 0
            or entry["result"] != "PASS"):
            raise ReceiptHold("MISSING_MANDATORY_CHECK")
        returned_ids.append(entry["argv_id"])
    if tuple(returned_ids) != expected.mandatory_argv_ids:
        raise ReceiptHold("MISSING_MANDATORY_CHECK")
    if not isinstance(receipt["signature"], str) or not _SHA64.fullmatch(receipt["signature"]):
        raise ReceiptHold("BAD_SIGNATURE")
    if not isinstance(trusted_hmac_key, bytes) or len(trusted_hmac_key) < 32:
        raise ReceiptHold("MISSING_PROTECTED_KEY")
    if not callable(trusted_consume_nonce):
        raise ReceiptHold("STALE_LEASE_OR_NONCE")
    valid_signature = hmac.new(
        trusted_hmac_key, b"mla-f18-review/v1|" + _payload_without_signature(receipt),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(receipt["signature"], valid_signature):
        raise ReceiptHold("BAD_SIGNATURE")
    # Caller MUST atomically consume nonce+lease under separately protected
    # authority. Any exception or replay is fail-closed.
    try:
        fresh = trusted_consume_nonce(expected.run_id, expected.lease_epoch, expected.nonce)
    except Exception:
        fresh = False
    if fresh is not True:
        raise ReceiptHold("STALE_LEASE_OR_NONCE")
    return ReceiptInspection(expected.task_id, expected.candidate_sha, True)
