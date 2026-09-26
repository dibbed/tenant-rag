"""Phase 3.5 regression tests: tar extraction cannot write outside its destination.

Bandit B202 (docs/security/PHASE3_5_SECURITY_HARDENING.md).

Vulnerability: SecureBackupManager._restore_from_archive extracted the backup
archive with tarfile.extractall(temp_restore_dir) and no member checks. A
crafted archive could write files outside the restore directory (tar slip)
with '..' components, absolute paths or links, and could create device files.

Expected: every member is checked before anything is written. Only regular
files and directories inside the destination are extracted; any other member
refuses the whole archive.
"""

from __future__ import annotations

import io
import json
import shutil
import stat
import tarfile
from pathlib import Path
from typing import Any, Callable

import pytest

from ragbot.security.secure_backup import SecureBackupManager

Member = tuple[tarfile.TarInfo, bytes | None]


def _file(name: str, data: bytes = b"payload") -> Member:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    return info, data


def _special(name: str, kind: bytes, linkname: str = "") -> Member:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = linkname
    info.mode = 0o755 if kind == tarfile.DIRTYPE else 0o644
    return info, None


def _write_archive(path: Path, members: list[Member]) -> Path:
    with tarfile.open(path, "w") as tar:
        for info, data in members:
            tar.addfile(info, io.BytesIO(data) if data is not None else None)
    return path


def _entries(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*")}


UNSAFE: dict[str, Callable[[Path], list[Member]]] = {
    "parent-traversal": lambda root: [_file("../../outside.txt")],
    "nested-traversal": lambda root: [_special("backup", tarfile.DIRTYPE), _file("backup/../../../nested.txt")],
    "dot-segments": lambda root: [_file("backup/./../../dot.txt")],
    "absolute-path": lambda root: [_file(str(root / "absolute.txt"))],
    "windows-drive": lambda root: [_file("C:/windows.txt")],
    "backslash-traversal": lambda root: [_file("..\\..\\backslash.txt")],
    "symlink-outside": lambda root: [
        _special("backup", tarfile.DIRTYPE),
        _special("backup/link", tarfile.SYMTYPE, str(root)),
        _file("backup/link/through-link.txt"),
    ],
    "symlink-relative": lambda root: [_special("escape", tarfile.SYMTYPE, "../../..")],
    "hardlink-outside": lambda root: [_special("backup/hard", tarfile.LNKTYPE, "../../outside-target.txt")],
    "character-device": lambda root: [_special("backup/null", tarfile.CHRTYPE)],
    "block-device": lambda root: [_special("backup/disk", tarfile.BLKTYPE)],
    "fifo": lambda root: [_special("backup/pipe", tarfile.FIFOTYPE)],
    "duplicate-member": lambda root: [_file("backup/a.txt", b"one"), _file("backup/a.txt", b"two")],
}


@pytest.mark.parametrize("case", sorted(UNSAFE))
def test_an_unsafe_archive_is_refused_before_anything_is_written(tmp_path: Path, case: str) -> None:
    from ragbot.security.safe_archive import UnsafeArchiveError, safe_extract_tar

    root = tmp_path / "root"
    destination = root / "work" / "restore"
    destination.mkdir(parents=True)
    archive = _write_archive(tmp_path / "archive.tar", UNSAFE[case](root))
    before = _entries(root)
    with tarfile.open(archive) as tar, pytest.raises(UnsafeArchiveError):
        safe_extract_tar(tar, destination)
    assert _entries(root) == before


def test_a_valid_archive_is_extracted_without_unsafe_permission_bits(tmp_path: Path) -> None:
    from ragbot.security.safe_archive import safe_extract_tar

    tool, data = _file("backup/tool.sh", b"#!/bin/sh\n")
    tool.mode = 0o6777
    archive = _write_archive(
        tmp_path / "archive.tar",
        [_special("backup", tarfile.DIRTYPE), _file("backup/documents.json", b"[]"), (tool, data)],
    )
    destination = tmp_path / "destination"
    with tarfile.open(archive) as tar:
        names = safe_extract_tar(tar, destination)
    assert names == ["backup", "backup/documents.json", "backup/tool.sh"]
    assert (destination / "backup" / "documents.json").read_bytes() == b"[]"
    mode = (destination / "backup" / "tool.sh").stat().st_mode
    assert not mode & (stat.S_ISUID | stat.S_ISGID | stat.S_IWOTH)


def test_a_python_without_extraction_filters_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ragbot.security.safe_archive import UnsafeArchiveError, safe_extract_tar

    archive = _write_archive(tmp_path / "archive.tar", [_file("backup/a.txt")])
    monkeypatch.delattr(tarfile, "data_filter")
    with tarfile.open(archive) as tar, pytest.raises(UnsafeArchiveError):
        safe_extract_tar(tar, tmp_path / "destination")
    assert not (tmp_path / "destination").exists()


# The restore path of SecureBackupManager


class _Store:
    def __init__(self, store_type: str) -> None:
        self.store_type = store_type
        self.added: list[Any] = []

    def get_store_type(self) -> str:
        return self.store_type

    async def add_documents(self, documents: list[Any]) -> list[str]:
        self.added.extend(documents)
        return [document.id for document in documents]


def _manager(temp_dir: Path) -> SecureBackupManager:
    """A backup manager without key store or metadata database, for the restore step only."""
    manager = SecureBackupManager.__new__(SecureBackupManager)
    manager.temp_dir = temp_dir
    temp_dir.mkdir(parents=True, exist_ok=True)
    return manager


def _decrypt_returning(archive: Path, temp_dir: Path) -> Callable[..., Any]:
    async def decrypt(backup_file: Path, encryption_key: Any) -> Path:
        copy = temp_dir / "decrypted.tar"
        shutil.copyfile(archive, copy)
        return copy

    return decrypt


@pytest.mark.parametrize("case", ["parent-traversal", "nested-traversal", "absolute-path", "symlink-outside"])
async def test_a_backup_restore_never_writes_outside_the_restore_directory(tmp_path: Path, case: str) -> None:
    root = tmp_path / "root"
    manager = _manager(root / "backups" / "temp")
    archive = _write_archive(tmp_path / "archive.tar", UNSAFE[case](root))
    manager._decrypt_backup_file = _decrypt_returning(archive, manager.temp_dir)  # type: ignore[method-assign]
    before = _entries(root)
    try:
        await manager._restore_from_archive(root / "backup.tar.gz", None, [])
    except Exception:
        pass
    assert _entries(root) == before


async def test_an_unsafe_backup_is_not_restored(tmp_path: Path) -> None:
    from ragbot.security.safe_archive import UnsafeArchiveError

    root = tmp_path / "root"
    manager = _manager(root / "temp")
    archive = _write_archive(tmp_path / "archive.tar", UNSAFE["parent-traversal"](root))
    manager._decrypt_backup_file = _decrypt_returning(archive, manager.temp_dir)  # type: ignore[method-assign]
    store = _Store("faiss")
    with pytest.raises(UnsafeArchiveError):
        await manager._restore_from_archive(root / "backup.tar", None, [store])
    assert store.added == []


async def test_a_valid_backup_is_restored(tmp_path: Path) -> None:
    root = tmp_path / "root"
    manager = _manager(root / "temp")
    documents = [
        {"id": "doc-1", "content": "hello", "embedding": [0.25, 0.5], "metadata": {"source": "a.txt"}, "score": None}
    ]
    archive = _write_archive(
        tmp_path / "backup.tar",
        [
            _special("backup", tarfile.DIRTYPE),
            _special("backup/faiss", tarfile.DIRTYPE),
            _file("backup/faiss/documents.json", json.dumps(documents).encode("utf-8")),
            _file("backup/faiss/metadata.json", b'{"store_type": "faiss"}'),
        ],
    )
    manager._decrypt_backup_file = _decrypt_returning(archive, manager.temp_dir)  # type: ignore[method-assign]
    store = _Store("faiss")
    restored = await manager._restore_from_archive(root / "backup.tar", None, [store])
    assert restored == ["faiss"]
    assert [document.id for document in store.added] == ["doc-1"]
    assert store.added[0].embedding == [0.25, 0.5]
