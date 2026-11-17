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
    if not isinstance(raw, str) or not isinstance(eligible_ids, frozenset):
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
