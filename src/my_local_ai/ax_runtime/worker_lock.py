"""Single local model residency lock with OS locking and durable fencing epochs.

Does not launch a model or break stale locks. OS closes locks on process death;
epoch increases on reacquire. Requires a trusted, private local state directory.
Windows ACL and real multi-process fencing are P2 NOT_RUN.
"""
from __future__ import annotations

from dataclasses import dataclass
import errno
import os
from pathlib import Path
import stat
import threading

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_MAX_EPOCH = (1 << 62) - 1
_process_mutex = threading.Lock()

class ModelLockBusy(RuntimeError):
    pass

class ModelLockUnsafe(RuntimeError):
    pass

@dataclass(frozen=True)
class ModelLease:
    generation: int
    owner_pid: int
    lock_path: str

def _safe_directory(path: Path) -> None:
    if not path.is_dir() or path.is_symlink():
        raise ModelLockUnsafe("state directory missing/unsafe")
    for segment in (path, *path.parents):
        info = segment.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & _REPARSE:
            raise ModelLockUnsafe("state path contains reparse or symlink")

def _os_lock(handle) -> None:
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    elif os.name == "posix":
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    else:
        raise ModelLockUnsafe("unsupported operating system for lock")

def _os_unlock(handle) -> None:
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    elif os.name == "posix":
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

class OneModelLock:
    def __init__(self, state_directory: str | Path):
        directory = Path(state_directory).absolute()
        _safe_directory(directory)
        self.path = directory / "my_local_ai.model.lock"
        self._handle = None
        self._lease: ModelLease | None = None

    def acquire(self) -> ModelLease:
        if self._handle is not None:
            raise ModelLockBusy("model lock already acquired by this instance")
        # Protect same-instance concurrency and use OS advisory/mandatory locks
        # for interprocess coordination. An untrusted guest cannot write this dir.
        with _process_mutex:
            flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NOINHERIT", 0)
            if self.path.is_symlink():
                raise ModelLockUnsafe("lock file symlink")
            # Distinguish a NEW lock file from an existing empty/corrupt file.
            # An interrupted write must never reset an existing epoch to 1.
            created = False
            try:
                descriptor = os.open(self.path, flags | os.O_CREAT | os.O_EXCL, 0o600)
                created = True
            except FileExistsError:
                descriptor = os.open(self.path, flags)
            handle = os.fdopen(descriptor, "r+b", buffering=0)
            locked = False
            try:
                fd_info = os.fstat(handle.fileno())
                if not stat.S_ISREG(fd_info.st_mode) or fd_info.st_nlink != 1:
                    raise ModelLockUnsafe("lock must be a unique regular file")
                current_info = self.path.lstat()
                if not stat.S_ISREG(current_info.st_mode) or getattr(current_info, "st_file_attributes", 0) & _REPARSE:
                    raise ModelLockUnsafe("lock file reparse detected")
                if (current_info.st_dev, current_info.st_ino) != (fd_info.st_dev, fd_info.st_ino):
                    raise ModelLockUnsafe("lock inode changed")
                try:
                    # Lock before first write to avoid a concurrent startup race.
                    _os_lock(handle)
                    locked = True
                except (BlockingIOError, OSError) as error:
                    if isinstance(error, BlockingIOError) or getattr(error, "errno", None) in (errno.EACCES, errno.EAGAIN):
                        raise ModelLockBusy("another local model owns the lock") from None
                    raise
                # Recheck identity *after* acquiring OS lock. A replaced name
                # must never receive a valid fencing epoch on an orphan inode.
                checked = self.path.lstat()
                if (not stat.S_ISREG(checked.st_mode)
                    or getattr(checked, "st_file_attributes", 0) & _REPARSE
                    or checked.st_nlink != 1
                    or (checked.st_dev, checked.st_ino) != (fd_info.st_dev, fd_info.st_ino)):
                    raise ModelLockUnsafe("lock replaced while acquiring")
                if handle.seek(0, 2) == 0:
                    if not created:
                        raise ModelLockUnsafe("existing empty fencing epoch; manual HOLD")
                    handle.write(b"0")
                    handle.flush()
                    os.fsync(handle.fileno())
                handle.seek(0)
                raw = handle.read(32)
                if not raw or len(raw) > 20 or not raw.isdigit():
                    raise ModelLockUnsafe("corrupted fencing epoch; manual HOLD")
                epoch = int(raw)
                if epoch < 0 or epoch >= _MAX_EPOCH:
                    raise ModelLockUnsafe("fencing epoch exhausted")
                epoch += 1
                handle.seek(0)
                handle.write(str(epoch).encode("ascii"))
                handle.truncate()
                handle.flush()
                os.fsync(handle.fileno())
                lease = ModelLease(epoch, os.getpid(), str(self.path))
                self._lease = lease
                self._handle = handle
                return lease
            except BaseException:
                if locked:
                    _os_unlock(handle)
                handle.close()
                raise

    def release(self, lease: ModelLease) -> None:
        if self._handle is None or self._lease != lease:
            raise ModelLockUnsafe("wrong, stale, or already released model lease")
        try:
            _os_unlock(self._handle)
        finally:
            self._handle.close()
            self._handle = None
            self._lease = None

    def __enter__(self) -> ModelLease:
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._lease is not None:
            self.release(self._lease)
