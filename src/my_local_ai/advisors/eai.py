"""Optional advisory JSON boundary. No dependency on EAI original products.

An external CPU analysis module may suggest ordering *after* the Controller
already established eligible READY IDs. Hints never approve, execute, add
paths, select models, change risk or authorize work. Unknown schemas fail shut.
"""
from __future__ import annotations

import json

_MAX_BYTES = 4096
_MAX_HINTS = 64


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate advisory key")
        obj[key] = value
    return obj


def parse_advisory(raw: str, eligible_ids: frozenset[str]) -> dict[str, int]:
    """Validate a strictly non-authoritative, bounded prioritization proposal."""
    if (not isinstance(raw, str) or not isinstance(eligible_ids, frozenset)
        or len(eligible_ids) > 512
        or any(not isinstance(tid, str) for tid in eligible_ids)):
        raise ValueError("invalid advisory")
    try:
        if len(raw.encode("utf-8")) > _MAX_BYTES:
            raise ValueError("advisory over limit")
        parsed = json.loads(
            raw, object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
    except (UnicodeError, ValueError, TypeError):
        raise ValueError("invalid advisory JSON") from None
    if (not isinstance(parsed, dict) or set(parsed) != {"version", "hints"}
        or type(parsed["version"]) is not int or parsed["version"] != 1
        or not isinstance(parsed["hints"], list)
        or len(parsed["hints"]) > _MAX_HINTS):
        raise ValueError("unrecognized advisory schema")
    result: dict[str, int] = {}
    for entry in parsed["hints"]:
        if not isinstance(entry, dict) or set(entry) != {"task_id", "rank"}:
            raise ValueError("extra advisory authority")
        tid, rank = entry["task_id"], entry["rank"]
        if (not isinstance(tid, str) or tid not in eligible_ids
            or tid in result or type(rank) is not int or not 0 <= rank <= 5):
            raise ValueError("unknown or repeated READY task/rank")
        result[tid] = rank
    return result


# The optional external engine is never imported/executed by this adapter.
# Its output is *data* passed by a separately isolated provider; this code
# validates schema and source pin without allowing any approval or commands.
from dataclasses import dataclass
import re

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class OptionalAdvisorResult:
    status: str
    hints: tuple[tuple[str, int], ...]
    independent_controller_required: bool = True
    executable: bool = False
    original_eai_imported: bool = False


def inspect_optional_eai(
    *, envelope_json: str | None, eligible_ids: frozenset[str],
    trusted_source_sha: str, trusted_plan_sha: str,
) -> OptionalAdvisorResult:
    """Decode offline advisory text; on any fault return deterministic fallback.

    The source SHA is a reference pin, *not* a signed/proven original license.
    Caller must not pass raw plans, secrets or customer files to this component.
    """
    if (not isinstance(trusted_source_sha, str) or not _SHA40.fullmatch(trusted_source_sha)
        or not isinstance(trusted_plan_sha, str) or not _SHA64.fullmatch(trusted_plan_sha)):
        raise ValueError("trusted reference required")
    if (not isinstance(eligible_ids, frozenset) or len(eligible_ids) > 512
        or any(not isinstance(tid, str) for tid in eligible_ids)):
        raise ValueError("eligible ready-set required")
    if envelope_json is None:
        return OptionalAdvisorResult("OFF", ())
    try:
        if (not isinstance(envelope_json, str)
            or len(envelope_json.encode("utf-8")) > _MAX_BYTES):
            raise ValueError("advisory too large")
        envelope = json.loads(
            envelope_json, object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        if (not isinstance(envelope, dict)
            or set(envelope) != {
                "version", "origin", "source_git_sha", "plan_sha256",
                "non_authoritative", "hints"
            } or type(envelope["version"]) is not int
            or envelope["version"] != 1
            or envelope["origin"] != "OPTIONAL_EAI_ADVISOR_DATA"
            or envelope["source_git_sha"] != trusted_source_sha
            or envelope["plan_sha256"] != trusted_plan_sha
            or envelope["non_authoritative"] is not True):
            raise ValueError("untrusted EAI envelope")
        hints = parse_advisory(json.dumps({
            "version": 1, "hints": envelope["hints"]
        }, sort_keys=True), eligible_ids)
    except (UnicodeError, ValueError, TypeError, OverflowError):
        return OptionalAdvisorResult("INVALID_OR_UNAVAILABLE_FALLBACK", ())
    return OptionalAdvisorResult("OPTIONAL_HINTS_VALIDATED_ONLY", tuple(sorted(hints.items())))
