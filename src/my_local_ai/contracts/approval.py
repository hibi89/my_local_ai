"""Fail-closed, non-executing owner-consent claims.

The coder cannot mint grants. Signatures require a separate protected 256-bit key,
and revocation must be checked against a trusted local consent store at use-time.
These primitives DO NOT establish OS trust isolation; runtime integration is HOLD.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from typing import Callable

_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9_-]{8,128}\Z")
SCOPES = frozenset({
    "LOCAL_PLAN", "REMOTE_PR", "OS_CHANGE", "PAID_API",
    "CUSTOMER_DATA", "PRODUCTION", "NETWORK_EGRESS",
})
_MAX_SECONDS = 86400 * 30

def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate claim JSON key")
        out[key] = value
    return out

@dataclass(frozen=True)
class OwnerGrant:
    grant_id: str
    plan_sha256: str
    source_git_sha: str
    scope: str
    issued_at: int
    expires_at: int
    nonce: str
    signature: str

    @classmethod
    def parse_json(cls, raw: str) -> "OwnerGrant":
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > 8192:
            raise ValueError("oversized grant")
        obj = json.loads(raw, object_pairs_hook=_unique_pairs)
        fields = {"version","grant_id","plan_sha256","source_git_sha","scope","issued_at","expires_at","nonce","signature"}
        if not isinstance(obj, dict) or set(obj) != fields or type(obj["version"]) is not int or obj["version"] != 1:
            raise ValueError("unrecognized grant schema")
        for key in ("grant_id", "nonce"):
            if not isinstance(obj[key], str) or not _ID.fullmatch(obj[key]):
                raise ValueError("invalid owner grant identity")
        for key, regex in (("plan_sha256", _HEX64), ("source_git_sha", _HEX40), ("signature", _HEX64)):
            if not isinstance(obj[key], str) or not regex.fullmatch(obj[key]):
                raise ValueError("invalid digest")
        if obj["scope"] not in SCOPES:
            raise ValueError("unknown consent scope")
        a, b = obj["issued_at"], obj["expires_at"]
        if type(a) is not int or type(b) is not int or a <= 0 or not 0 < b - a <= _MAX_SECONDS:
            raise ValueError("invalid grant lifetime")
        return cls(obj["grant_id"], obj["plan_sha256"], obj["source_git_sha"],obj["scope"],a,b,obj["nonce"],obj["signature"])

    def payload(self) -> bytes:
        return json.dumps({
            "version":1, "grant_id":self.grant_id, "plan_sha256":self.plan_sha256,
            "source_git_sha":self.source_git_sha, "scope":self.scope,
            "issued_at":self.issued_at,"expires_at":self.expires_at,"nonce":self.nonce,
        }, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")

def authorize_claim(
    grant: OwnerGrant, *,
    trusted_hmac_key: bytes | None,
    expected_plan_sha: str,
    expected_source_sha: str,
    required_scope: str,
    now_seconds: int,
    trusted_live_consent_check: Callable[[str,str,str], bool] | None,
) -> bool:
    """Every condition must hold; parsing/self-declared APPROVED is insufficient.

    The key and consent checker must come from a separately protected owner
    process; NEVER from guest, task JSON, or the public repository.
    """
    if not isinstance(grant, OwnerGrant) or type(now_seconds) is not int:
        return False
    # V1 signer can bind only a local plan. A scope-only grant MUST NOT
    # authorize individual remote PRs, payments, OS/network/customer changes:
    # these require action-specific, one-shot approval + protected OS signer.
    # Preserve the future scope catalog for parsing, but fail closed at use-time.
    if required_scope != "LOCAL_PLAN":
        return False
    if required_scope not in SCOPES or required_scope != grant.scope:
        return False
    if grant.plan_sha256 != expected_plan_sha or grant.source_git_sha != expected_source_sha:
        return False
    if now_seconds < grant.issued_at or now_seconds >= grant.expires_at:
        return False
    if not isinstance(trusted_hmac_key, bytes) or len(trusted_hmac_key) < 32:
        return False
    if trusted_live_consent_check is None or not callable(trusted_live_consent_check):
        return False
    expected = hmac.new(trusted_hmac_key, b"mla-owner-go/v1|" + grant.payload(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, grant.signature):
        return False
    try:
        # A revoked grant must never be considered live, even if signed/within TTL.
        return trusted_live_consent_check(grant.grant_id, grant.plan_sha256, grant.scope) is True
    except Exception:
        return False
