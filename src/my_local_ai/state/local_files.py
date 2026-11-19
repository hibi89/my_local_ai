"""Bounded reads of regular files from the local workspace."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat


MAX_LOCAL_BYTES = 1_048_576


def local_path_stat(path: Path) -> os.stat_result:
    """Reject aliases anywhere in the path before opening a local file."""
    chain = (path, *path.parents)
    for segment in reversed(chain):
        info = segment.lstat()
        if (stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError("unsafe local file alias")
    return info


def read_bounded_regular(path: Path) -> bytes:
    """Read a local file without following links or accepting a replaced file."""
    candidate = path.absolute()
    before = local_path_stat(candidate)
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
        or before.st_size > MAX_LOCAL_BYTES):
        raise ValueError("nonregular or oversized local file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(candidate, flags)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            raise ValueError("local file replaced before read")
        raw = stream.read(MAX_LOCAL_BYTES + 1)
    after = candidate.lstat()
    if ((after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
        or after.st_size != len(raw) or len(raw) > MAX_LOCAL_BYTES):
        raise ValueError("local file changed while reading")
    return raw


def _unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate status JSON key")
        obj[key] = value
    return obj


def _reject_nonfinite(value):
    raise ValueError("nonfinite status JSON")


def read_local_metadata(path: Path) -> dict:
    data = json.loads(read_bounded_regular(path).decode("utf-8"),
                      object_pairs_hook=_unique_keys, parse_constant=_reject_nonfinite)
    if not isinstance(data, dict):
        raise ValueError("malformed status")
    return data
