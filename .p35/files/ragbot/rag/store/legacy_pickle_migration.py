"""Convert a legacy FAISS document store (documents.pkl) to documents.npz, once.

    python -m ragbot.rag.store.legacy_pickle_migration --trust-legacy-pickle DIRECTORY [DIRECTORY ...]

Security (Phase 3.5, Bandit B301): loading a pickle file can run arbitrary
code. The application never loads documents.pkl (see
ragbot/rag/store/document_persistence.py); a store that has only that file does
not open. This command is the only reader of the legacy format, and an operator
runs it deliberately:

- Run it only for a store directory whose documents.pkl TenantRAG wrote on a
  system you control. Never run it for a file that you received, downloaded or
  restored from an untrusted source; delete such a store and ingest the
  documents again instead.
- The command refuses to run without --trust-legacy-pickle.
- Even then, it reads the file with a restricted unpickler that resolves only
  the classes that a TenantRAG document store contains (VectorDocument, date
  and time values, sets, and NumPy arrays and scalars). Any other class or
  function, for example os.system, stops the conversion before it is called.

The documents are checked, written to documents.npz and read back. Then
documents.pkl is renamed to documents.pkl.migrated; delete that file after you
have checked the store. The application is not changed by this command and
never imports it.

Exit codes: 0 every directory was converted, 1 a directory was not converted,
2 usage error.
"""

from __future__ import annotations

import argparse
import io
import pickle  # Security: read only through _RestrictedUnpickler below.
import sys
from pathlib import Path
from typing import Any

from ragbot.rag.store.base import VectorDocument
from ragbot.rag.store.document_persistence import (
    DOCUMENTS_FILE,
    LEGACY_PICKLE_FILE,
    DocumentFileError,
    read_documents_file,
    save_documents,
)

MIGRATED_SUFFIX = ".migrated"
ALLOWED_GLOBALS = frozenset(
    {
        ("ragbot.rag.store.base", "VectorDocument"),
        ("builtins", "set"),
        ("builtins", "frozenset"),
        ("collections", "OrderedDict"),
        ("datetime", "date"),
        ("datetime", "datetime"),
        ("datetime", "time"),
        ("datetime", "timedelta"),
        ("datetime", "timezone"),
        ("numpy", "dtype"),
        ("numpy", "ndarray"),
        ("numpy.core.multiarray", "_reconstruct"),
        ("numpy.core.multiarray", "scalar"),
        ("numpy._core.multiarray", "_reconstruct"),
        ("numpy._core.multiarray", "scalar"),
    }
)


class LegacyMigrationError(Exception):
    """A legacy document file cannot be converted."""


class _RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that resolves only the classes of a legacy document store."""

    def find_class(self, module: str, name: str) -> Any:
        if (module, name) not in ALLOWED_GLOBALS:
            raise pickle.UnpicklingError(
                f"the file refers to {module}.{name}, which a document store does not contain"
            )
        return super().find_class(module, name)


def read_legacy_documents(data: bytes) -> dict[str, VectorDocument]:
    """Read the documents of a legacy documents.pkl with the restricted unpickler."""
    try:
        loaded = _RestrictedUnpickler(io.BytesIO(data)).load()
    except (
        pickle.UnpicklingError,
        AttributeError,
        EOFError,
        ImportError,
        IndexError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise LegacyMigrationError(f"the file is not a legacy document store: {exc}") from exc
    if not isinstance(loaded, dict):
        raise LegacyMigrationError(
            f"the file holds {type(loaded).__name__}, not a mapping of documents"
        )
    documents: dict[str, VectorDocument] = {}
    for key, document in loaded.items():
        if not isinstance(key, str) or type(document) is not VectorDocument:
            raise LegacyMigrationError(f"the entry {key!r} is not a VectorDocument")
        state = vars(document)
        try:
            documents[key] = VectorDocument(
                id=state.get("id"),
                content=state.get("content"),
                embedding=state.get("embedding"),
                metadata=state.get("metadata"),
                score=state.get("score"),
            )
        except (TypeError, ValueError) as exc:
            raise LegacyMigrationError(f"the entry {key!r} is not a valid document: {exc}") from exc
    return documents


def migrate_directory(directory: Path) -> Path:
    """Convert one store directory and return the path of its new documents.npz."""
    legacy = directory / LEGACY_PICKLE_FILE
    target = directory / DOCUMENTS_FILE
    migrated = legacy.with_name(legacy.name + MIGRATED_SUFFIX)
    if not legacy.is_file():
        raise LegacyMigrationError(f"{legacy} does not exist")
    if target.exists():
        raise LegacyMigrationError(f"{target} already exists; the store is already converted")
    if migrated.exists():
        raise LegacyMigrationError(f"{migrated} already exists")
    documents = read_legacy_documents(legacy.read_bytes())
    save_documents(directory, documents)
    try:
        converted = read_documents_file(target)
        if list(converted) != list(documents) or any(
            converted[key].id != document.id
            or converted[key].content != document.content
            or len(converted[key].embedding) != len(document.embedding)
            for key, document in documents.items()
        ):
            raise LegacyMigrationError(f"{target} does not match {legacy}")
    except (DocumentFileError, LegacyMigrationError):
        target.unlink(missing_ok=True)
        raise
    legacy.rename(migrated)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ragbot.rag.store.legacy_pickle_migration",
        description="Convert legacy FAISS document stores (documents.pkl) to documents.npz.",
    )
    parser.add_argument(
        "directories", nargs="+", type=Path, help="FAISS store directories that contain documents.pkl"
    )
    parser.add_argument(
        "--trust-legacy-pickle",
        action="store_true",
        help="confirm that TenantRAG wrote every documents.pkl on a system you control",
    )
    args = parser.parse_args(argv)
    if not args.trust_legacy_pickle:
        print(
            "error: loading a pickle file can run arbitrary code. Convert only a "
            "documents.pkl that TenantRAG wrote on a system you control, and confirm "
            "that with --trust-legacy-pickle. For any other store, delete the store "
            "directory and ingest the documents again.",
            file=sys.stderr,
        )
        return 2
    failures = 0
    for directory in args.directories:
        try:
            target = migrate_directory(directory)
        except (LegacyMigrationError, DocumentFileError, OSError) as exc:
            failures += 1
            print(f"error: {directory}: {exc}", file=sys.stderr)
        else:
            print(
                f"converted {directory / LEGACY_PICKLE_FILE} to {target}; "
                f"the old file is now {LEGACY_PICKLE_FILE}{MIGRATED_SUFFIX}"
            )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
