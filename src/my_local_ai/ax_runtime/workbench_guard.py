"""Exclusive local workbench lease; prevents two EXEs sharing one SQLite queue."""
from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import stat

from .draft_documents import DraftError
from .worker_lock import _safe_directory, _os_lock, _os_unlock, ModelLockBusy, ModelLockUnsafe

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


@contextmanager
def exclusive_workbench(root: Path):
    """Hold a fail-closed OS lock while one local workbench serves this draft root.

    This is single-user process coordination, NOT an F18/Owner protected lease.
    The file remains after shutdown; the OS releases its lock after a crash.
    """
    directory = Path(root).absolute()
    try:
        _safe_directory(directory)
    except (OSError, ValueError, ModelLockUnsafe) as exc:
        raise DraftError("작업 폴더의 로컬 경로와 접근 권한을 확인하세요.") from exc
    path = directory / ".mla-workbench.instance.lock"
    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NOINHERIT", 0)
    if path.is_symlink():
        raise DraftError("작업대 잠금 파일이 안전하지 않습니다.")
    try:
        try:
            descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
            created = True
        except FileExistsError:
            descriptor = os.open(path, flags)
            created = False
    except OSError as exc:
        raise DraftError("작업대 잠금 파일을 열 수 없습니다.") from exc
    handle = os.fdopen(descriptor, "r+b", buffering=0)
    locked = False
    try:
        info = os.fstat(handle.fileno())
        visible = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or not stat.S_ISREG(visible.st_mode) or visible.st_nlink != 1
            or getattr(visible, "st_file_attributes", 0) & _REPARSE
            or (info.st_dev, info.st_ino) != (visible.st_dev, visible.st_ino)):
            raise DraftError("작업대 잠금 파일이 변경되거나 연결돼 있습니다.")
        if created:
            # Windows byte-range locks need a real byte to lock.
            handle.write(b"0")
            handle.flush()
            os.fsync(handle.fileno())
        elif handle.seek(0, 2) != 1:
            raise DraftError("기존 작업대 잠금 기록이 손상되었습니다. 자동 복구하지 않습니다.")
        try:
            _os_lock(handle)
            locked = True
        except (BlockingIOError, OSError) as exc:
            if isinstance(exc, BlockingIOError) or getattr(exc, "errno", None) in (errno.EAGAIN, errno.EACCES):
                raise DraftError("같은 작업 폴더의 MLA 작업대가 이미 실행 중입니다.") from None
            raise
        again = path.lstat()
        if (not stat.S_ISREG(again.st_mode) or again.st_nlink != 1
            or getattr(again, "st_file_attributes", 0) & _REPARSE
            or (info.st_dev, info.st_ino) != (again.st_dev, again.st_ino)):
            raise DraftError("작업대 잠금 파일이 실행 중 바뀌어 진행을 보류했습니다.")
        yield
    except (ModelLockBusy, ModelLockUnsafe) as exc:
        raise DraftError("작업대의 안전한 단일 실행 잠금을 확보하지 못했습니다.") from exc
    finally:
        try:
            if locked:
                _os_unlock(handle)
        finally:
            handle.close()
