"""Strict admission of synthetic or owned-redacted MESA observations.

Parsing is data-only. Even a valid observation cannot make a test PASS,
sign owner consent, promote a skill, or write the production state store.
"""
from __future__ import annotations

import json

from .schema import ExperienceEventV1

_MAX_BYTES = 8192
_EVENT_FIELDS = frozenset({
    "event_id", "project_id", "run_id", "task_id", "plan_sha256",
    "source_git_sha", "scope_ref", "rights_tag", "outcome",
    "error_fingerprint", "environment_digest", "observed_at",
})


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate experience key")
        result[key] = value
    return result


def parse_observation(
    raw: str, *, expected_project: str, expected_plan_sha: str,
    expected_source_sha: str, allowed_scope_refs: frozenset[str],
) -> ExperienceEventV1:
    """Admit a bounded record in exactly the caller's existing scope.

    allowed_scope_refs is NOT an owner grant. Protected consent/F18 checks
    remain external to this module and must never rely on its verdict.
    """
    if (not isinstance(raw, str) or not isinstance(allowed_scope_refs, frozenset)
        or len(allowed_scope_refs) > 128
        or any(not isinstance(x, str) for x in allowed_scope_refs)):
        raise ValueError("invalid experience source")
    try:
        if len(raw.encode("utf-8")) > _MAX_BYTES:
            raise ValueError("oversized observation")
        values = json.loads(
            raw, object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise ValueError("invalid experience JSON") from None
    if not isinstance(values, dict) or frozenset(values) != _EVENT_FIELDS:
        raise ValueError("untrusted experience fields")
    # F18/owner flags, raw text/diffs, PII and source code are not in this
    # schema. They cannot be smuggled in as additional fields.
    record = ExperienceEventV1(**values)
    if (record.project_id != expected_project
        or record.plan_sha256 != expected_plan_sha
        or record.source_git_sha != expected_source_sha
        or record.scope_ref not in allowed_scope_refs):
        raise ValueError("observation scope or source mismatch")
    return record
