"""Share the cumulative time for completed workbench attempts."""
from contextlib import closing
from pathlib import Path
import sqlite3
import stat

from ..state.local_files import local_path_stat


def recorded_time(root: Path, elapsed_ms: int | None = None) -> int:
    path = root / ".mla-timing.sqlite3"
    local_path_stat(root)
    for suffix in ("", "-journal", "-wal", "-shm"):
        try:
            info = local_path_stat(path.with_name(path.name + suffix))
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("unsafe timing store")
    if elapsed_ms is None and not path.exists():
        return 0
    with closing(sqlite3.connect(path, timeout=3.0)) as db, db:
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("CREATE TABLE IF NOT EXISTS timing (id INTEGER PRIMARY KEY, total_ms INTEGER NOT NULL)")
        if elapsed_ms is not None:
            db.execute("INSERT INTO timing VALUES (1, ?) ON CONFLICT (id) DO UPDATE "
                       "SET total_ms = total_ms + excluded.total_ms", (elapsed_ms,))
        row = db.execute("SELECT total_ms FROM timing WHERE id = 1").fetchone()
        total = row[0] if row else 0
        if type(total) is not int or total < 0:
            raise ValueError("invalid timing total")
        return total
