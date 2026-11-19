"""Cumulative timing and recent successful model durations for the workbench."""
from contextlib import closing
from pathlib import Path
import sqlite3
import stat

from ..state.local_files import local_path_stat


_INITIAL_ESTIMATES = {
    "focused": (45_000, 150_000),
    "short": (50_000, 150_000),
    "long": (85_000, 245_000),
}


def _timing_path(root: Path) -> Path:
    path = root / ".mla-timing.sqlite3"
    local_path_stat(root)
    for suffix in ("", "-journal", "-wal", "-shm"):
        try:
            info = local_path_stat(path.with_name(path.name + suffix))
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("unsafe timing store")
    return path


def recorded_time(root: Path, elapsed_ms: int | None = None, *,
                  sample: tuple[str, int] | None = None) -> int:
    path = _timing_path(root)
    if elapsed_ms is None and not path.exists():
        return 0
    with closing(sqlite3.connect(path, timeout=3.0)) as db, db:
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("CREATE TABLE IF NOT EXISTS timing (id INTEGER PRIMARY KEY, total_ms INTEGER NOT NULL)")
        if elapsed_ms is not None:
            db.execute("INSERT INTO timing VALUES (1, ?) ON CONFLICT (id) DO UPDATE "
                       "SET total_ms = total_ms + excluded.total_ms", (elapsed_ms,))
            if sample is not None:
                db.execute("CREATE TABLE IF NOT EXISTS draft_durations "
                           "(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, elapsed_ms INTEGER NOT NULL)")
                db.execute("INSERT INTO draft_durations (kind, elapsed_ms) VALUES (?, ?)", sample)
                db.execute("DELETE FROM draft_durations WHERE kind = ? AND id NOT IN "
                           "(SELECT id FROM draft_durations WHERE kind = ? ORDER BY id DESC LIMIT 8)",
                           (sample[0], sample[0]))
        row = db.execute("SELECT total_ms FROM timing WHERE id = 1").fetchone()
        total = row[0] if row else 0
        if type(total) is not int or total < 0:
            raise ValueError("invalid timing total")
        return total


def estimated_duration(root: Path, kind: str) -> dict:
    lower, upper = _INITIAL_ESTIMATES[kind]
    times = []
    try:
        path = _timing_path(root)
        if path.is_file():
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1.0)) as db:
                db.execute("PRAGMA trusted_schema=OFF")
                times = [row[0] for row in db.execute(
                    "SELECT elapsed_ms FROM draft_durations WHERE kind = ? "
                    "AND elapsed_ms BETWEEN 5000 AND 270000 ORDER BY id DESC LIMIT 8", (kind,),
                ) if type(row[0]) is int]
    except (OSError, sqlite3.Error, ValueError):
        pass  # Older stores contain only the cumulative time.
    if times:
        lower = max(5_000, min(times) * 3 // 4)
        upper = min(270_000, max(times) * 5 // 4 + 10_000)
    return {"lower_ms": lower, "upper_ms": upper, "runs": len(times)}
