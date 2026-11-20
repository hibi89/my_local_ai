"""Bounded last-24-hour SQLite liveness digest; never a verification receipt.

The local workbench records are not signed, device-attested or sufficient to
prove continuous operation. No source files/prompts/credentials are read.
"""
from __future__ import annotations

import math
import sqlite3

_WINDOW_SECONDS = 24 * 60 * 60
_MAX_ROWS = 4096
_GAP_SECONDS = 180


def summarize_local_24h(db: sqlite3.Connection, wall_seconds: float) -> dict:
    """Summarize at most 4096 existing receipts; no file writes or P2 claims."""
    if not math.isfinite(wall_seconds) or wall_seconds < 0:
        raise ValueError("invalid observation timestamp")
    end = int(wall_seconds)
    start = max(0, end - _WINDOW_SECONDS)
    rows = list(db.execute(
        "SELECT session,event,utc_seconds,elapsed_seconds,gap "
        "FROM longrun_receipts "
        "WHERE utc_seconds BETWEEN ? AND ? ORDER BY id DESC LIMIT ?",
        (start, end, _MAX_ROWS),
    ))
    rows.reverse()
    gaps = 0
    sessions: set[str] = set()
    prev: tuple[str, int, int] | None = None
    first_seen: int | None = None
    last_seen: int | None = None
    for session, event, wall, elapsed, marked in rows:
        if (type(session) is not str or len(session) != 24
            or any(char not in "0123456789abcdef" for char in session)
            or event not in {"START", "HEARTBEAT", "STOP"}
            or type(wall) is not int or not start <= wall <= end
            or type(elapsed) is not int or elapsed < 0
            or type(marked) is not int or marked not in (0, 1)):
            raise ValueError("invalid recorded long-run observation")
        sessions.add(session)
        if prev is not None and prev[0] == session:
            delta_wall = wall - prev[1]
            delta_elapsed = elapsed - prev[2]
            gap = (delta_wall < 0 or delta_elapsed < 0
                   or max(delta_wall, delta_elapsed) > _GAP_SECONDS
                   or abs(delta_wall - delta_elapsed) > 120)
        else:
            gap = False
        gaps += int(marked != 0 or gap)
        prev = (session, wall, elapsed)
        first_seen = wall if first_seen is None else min(first_seen, wall)
        last_seen = wall if last_seen is None else max(last_seen, wall)

    def peak(sql: str) -> float | None:
        value = db.execute(sql, (start, end)).fetchone()[0]
        if (type(value) in (int, float) and math.isfinite(value)
            and 0 <= value <= 262144):
            return round(float(value), 2)
        return None

    process_peak = peak(
        "SELECT MAX(r.working_set_mb) FROM longrun_process_ram AS r "
        "JOIN longrun_receipts AS l ON l.id = r.receipt_id "
        "WHERE l.utc_seconds BETWEEN ? AND ? AND r.working_set_mb BETWEEN 0 AND 262144"
    )
    gpu_peak = peak(
        "SELECT MAX(r.used_mb) FROM longrun_gpu_vram AS r "
        "JOIN longrun_receipts AS l ON l.id = r.receipt_id "
        "WHERE l.utc_seconds BETWEEN ? AND ? AND r.used_mb BETWEEN 0 AND 131072"
    )
    return {
        "window_seconds": _WINDOW_SECONDS,
        "recorded_samples": len(rows),
        "recorded_sessions": len(sessions),
        "recorded_gaps": gaps,
        "recorded_span_seconds": max(0, last_seen - first_seen)
        if first_seen is not None and last_seen is not None else 0,
        "last_receipt_age_seconds": max(0, end - last_seen) if last_seen is not None else None,
        "retention_limit_reached": len(rows) >= _MAX_ROWS,
        "process_ram_peak_mb": process_peak,
        "gpu0_global_vram_peak_mb": gpu_peak,
        "verification": "NOT_RUN",
        "real_24h_accepted": False,
        "basis": "UNATTESTED_LOCAL_WALL_CLOCK_RECEIPTS",
    }
