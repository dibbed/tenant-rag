"""Safe extraction of tar archives.

Security (Phase 3.5, Bandit B202): ``tarfile.extractall`` without checks writes
wherever the member names point. A crafted archive can use ``..`` components,
absolute paths, symbolic or hard links, or device files to write or link
outside the destination directory (tar slip).

:func:`safe_extract_tar` checks every member before it writes anything, and
refuses the whole archive (:class:`UnsafeArchiveError`) when one member is
unsafe. Only regular files and directories whose relative path stays inside
the destination are allowed; links, devices, FIFOs and other special members
are refused. The extraction then uses the ``data`` extraction filter of
:mod:`tarfile` (PEP 706), which also removes unsafe permission bits. Python
versions without extraction filters (3.10 before 3.10.12, 3.11 before 3.11.4)
are refused.
"""

from __future__ import annotations

import os
import tarfile
from pathlib import Path, PurePosixPath

__all__ = ["UnsafeArchiveError", "safe_extract_tar"]


class UnsafeArchiveError(ValueError):
    """The archive has a member that must not be extracted."""


def _member_problem(member: tarfile.TarInfo, destination: Path) -> str | None:
    """Return why ``member`` must not be extracted, or None when it is safe."""
    name = member.name
    if not name or "\x00" in name:
        return "empty member name or NUL character"
    if "\\" in name:
        return "backslash in the member name"
    if name.startswith("/") or (len(name) >= 2 and name[1] == ":"):
        return "absolute path"
    if ".." in PurePosixPath(name).parts:
        return "'..' path component"
    if member.issym() or member.islnk():
        return "symbolic or hard link"
    if not (member.isreg() or member.isdir()):
        return "special file (device, FIFO or other type)"
    target = (destination / name).resolve()
    if target != destination and destination not in target.parents:
        return "path outside the destination"
    return None


def safe_extract_tar(tar: tarfile.TarFile, destination: str | os.PathLike[str]) -> list[str]:
    """Extract ``tar`` into ``destination`` when every member is safe.

    Returns the names of the extracted members. Raises UnsafeArchiveError,
    before anything is written, for the first unsafe member, and when this
    Python version has no tarfile extraction filters.
    """
    root = Path(destination).resolve()
    members = tar.getmembers()
    seen: set[str] = set()
    for member in members:
        problem = _member_problem(member, root)
        if problem is None:
            key = PurePosixPath(member.name).as_posix()
            if key in seen:
                problem = "duplicate member name"
            seen.add(key)
        if problem is not None:
            raise UnsafeArchiveError(f"unsafe archive member {member.name!r}: {problem}")
    if not hasattr(tarfile, "data_filter"):
        raise UnsafeArchiveError(
            "this Python version has no tarfile extraction filters (PEP 706); "
            "use Python 3.10.12, 3.11.4, 3.12 or later"
        )
    root.mkdir(parents=True, exist_ok=True)
    try:
        tar.extractall(root, members=members, filter="data")
    except tarfile.FilterError as exc:
        raise UnsafeArchiveError(f"unsafe archive member: {exc}") from exc
    return [member.name for member in members]
