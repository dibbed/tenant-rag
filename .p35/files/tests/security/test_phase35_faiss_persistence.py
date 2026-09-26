"""Phase 3.5 regression tests: the FAISS store persists documents without pickle.

Bandit B301 (docs/security/PHASE3_5_SECURITY_HARDENING.md).

Vulnerability: the FAISS store saved its documents with pickle (documents.pkl)
and loaded that file with pickle.load when the store opened. A crafted file in
a store directory ran code in the application.

Expected: documents.npz (JSON and float64 arrays, read with
numpy.load(allow_pickle=False) and checked against a strict schema). The
application never unpickles a legacy documents.pkl: the store does not open
(fail closed) until an operator converts it with the migration command, which
uses a restricted unpickler.
"""

from __future__ import annotations

import ast
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any

import faiss
import numpy as np
import pytest

from ragbot.rag.store.base import VectorDocument
from ragbot.rag.store.faiss_store import FAISSVectorStore

ROOT = Path(__file__).resolve().parents[2]
DIMENSION = 8
UNSAFE_MODULES = {"pickle", "cPickle", "dill", "cloudpickle", "shelve", "jsonpickle", "joblib"}


class _Payload:
    """When it is unpickled, this object creates a marker file."""

    def __init__(self, marker: Path) -> None:
        self.marker = marker

    def __reduce__(self) -> Any:
        return (Path.touch, (self.marker,))


def _reduce_pickle(module: str, name: str, argument: str) -> bytes:
    """Protocol 0 pickle that calls module.name(argument) when it is loaded."""
    return (
        b"c" + module.encode() + b"\n" + name.encode() + b"\n"
        + b"(V" + argument.encode("raw_unicode_escape") + b"\ntR."
    )


def _documents() -> list[VectorDocument]:
    return [
        VectorDocument(
            id="doc-1",
            content="first",
            embedding=[0.1 * (index + 1) for index in range(DIMENSION)],
            metadata={"source": "a.txt", "page": 1, "tags": ["x"]},
        ),
        VectorDocument(
            id="doc-2",
            content="second \u0633\u0644\u0627\u0645",
            embedding=[1.0 / (index + 2) for index in range(DIMENSION)],
            metadata={"source": "b.txt", "nested": {"k": None}},
        ),
    ]


def _store(path: Path, **kwargs: Any) -> FAISSVectorStore:
    return FAISSVectorStore(index_path=str(path), embedding_dimension=DIMENSION, **kwargs)


def _legacy_store_dir(path: Path, documents_pickle: bytes) -> Path:
    """A store directory as the previous version wrote it: FAISS index, metadata.json, documents.pkl."""
    path.mkdir(parents=True)
    faiss.write_index(faiss.IndexIDMap2(faiss.IndexFlatIP(DIMENSION)), str(path / "faiss.index"))
    (path / "metadata.json").write_text(
        json.dumps(
            {"embedding_dimension": DIMENSION, "docid_to_faissid": {}, "faissid_to_docid": {}, "next_faiss_id": 1}
        ),
        encoding="utf-8",
    )
    (path / "documents.pkl").write_bytes(documents_pickle)
    return path


def _as_dicts(documents: dict[str, VectorDocument]) -> dict[str, dict[str, Any]]:
    return {key: document.to_dict() for key, document in documents.items()}


# Normal persistence


async def test_documents_round_trip_through_documents_npz(tmp_path: Path) -> None:
    store = _store(tmp_path / "store")
    await store.add_documents(_documents())
    assert (tmp_path / "store" / "documents.npz").exists()
    assert not (tmp_path / "store" / "documents.pkl").exists()
    reopened = _store(tmp_path / "store")
    assert _as_dicts(reopened.documents) == _as_dicts(store.documents)
    result = await reopened.search(_documents()[0].embedding, top_k=1)
    assert [document.id for document in result.documents] == ["doc-1"]


async def test_embeddings_are_not_stored_without_keep_embeddings(tmp_path: Path) -> None:
    store = _store(tmp_path / "store", keep_embeddings=False)
    await store.add_documents(_documents())
    reopened = _store(tmp_path / "store", keep_embeddings=False)
    assert sorted(reopened.documents) == ["doc-1", "doc-2"]
    assert all(document.embedding == [] for document in reopened.documents.values())
    assert reopened.documents["doc-2"].content == _documents()[1].content


async def test_the_document_file_holds_no_python_objects(tmp_path: Path) -> None:
    store = _store(tmp_path / "store")
    await store.add_documents(_documents())
    with np.load(tmp_path / "store" / "documents.npz", allow_pickle=False) as archive:
        assert sorted(archive.files) == ["documents_json", "embedding_values"]
        assert archive["documents_json"].dtype == np.uint8
        assert archive["embedding_values"].dtype == np.float64
        data = json.loads(archive["documents_json"].tobytes().decode("utf-8"))
    assert (data["format"], data["version"]) == ("tenant-rag/vector-documents", 1)
    assert [entry["id"] for entry in data["documents"]] == ["doc-1", "doc-2"]


# Malformed and wrong-schema files


def _save_npz(path: Path, **arrays: Any) -> None:
    with open(path, "wb") as handle:
        np.savez(handle, **arrays)


def _json_array(value: Any) -> np.ndarray:
    return np.frombuffer(json.dumps(value).encode("utf-8"), dtype=np.uint8)


def _payload() -> dict[str, Any]:
    return {
        "format": "tenant-rag/vector-documents",
        "version": 1,
        "documents": [
            {"key": "d", "id": "d", "content": "c", "metadata": {}, "score": None, "embedding": [0, 2]}
        ],
    }


def _write_malformed(case: str, path: Path, marker: Path) -> None:
    values = np.array([0.5, 0.25])
    payload = _payload()
    entry = payload["documents"][0]
    if case == "not-an-archive":
        path.write_bytes(b"this is not a numpy archive")
    elif case == "npy-instead-of-npz":
        with open(path, "wb") as handle:
            np.save(handle, values)
    elif case == "pickled-object-array":
        _save_npz(path, documents_json=_json_array(payload), embedding_values=np.array([_Payload(marker)], dtype=object))
    elif case == "extra-array":
        _save_npz(path, documents_json=_json_array(payload), embedding_values=values, extra=values)
    elif case == "missing-array":
        _save_npz(path, documents_json=_json_array(payload))
    elif case == "integer-embeddings":
        _save_npz(path, documents_json=_json_array(payload), embedding_values=np.array([1, 2], dtype=np.int64))
    elif case == "invalid-json":
        _save_npz(path, documents_json=np.frombuffer(b"{not json", dtype=np.uint8), embedding_values=values)
    else:
        changes = {
            "wrong-format": lambda: payload.update(format="other"),
            "future-version": lambda: payload.update(version=2),
            "boolean-version": lambda: payload.update(version=True),
            "extra-top-level-field": lambda: payload.update(extra=1),
            "missing-field": lambda: entry.pop("score"),
            "extra-field": lambda: entry.update(extra=1),
            "empty-id": lambda: entry.update(id=""),
            "numeric-content": lambda: entry.update(content=5),
            "list-metadata": lambda: entry.update(metadata=[]),
            "boolean-score": lambda: entry.update(score=True),
            "embedding-out-of-range": lambda: entry.update(embedding=[1, 5]),
            "negative-offset": lambda: entry.update(embedding=[-1, 1]),
            "embedding-not-a-pair": lambda: entry.update(embedding=[0]),
            "duplicate-key": lambda: payload["documents"].append(dict(entry)),
        }
        changes[case]()
        _save_npz(path, documents_json=_json_array(payload), embedding_values=values)


MALFORMED = [
    "not-an-archive",
    "npy-instead-of-npz",
    "pickled-object-array",
    "extra-array",
    "missing-array",
    "integer-embeddings",
    "invalid-json",
    "wrong-format",
    "future-version",
    "boolean-version",
    "extra-top-level-field",
    "missing-field",
    "extra-field",
    "empty-id",
    "numeric-content",
    "list-metadata",
    "boolean-score",
    "embedding-out-of-range",
    "negative-offset",
    "embedding-not-a-pair",
    "duplicate-key",
]


@pytest.mark.parametrize("case", MALFORMED)
def test_a_malformed_document_file_is_refused(tmp_path: Path, case: str) -> None:
    from ragbot.rag.store.document_persistence import DocumentFileError, load_documents

    directory = tmp_path / "store"
    directory.mkdir()
    marker = tmp_path / "p35-npz-marker"
    _write_malformed(case, directory / "documents.npz", marker)
    with pytest.raises(DocumentFileError):
        load_documents(directory)
    assert not marker.exists()


def test_a_store_with_a_malformed_document_file_does_not_open(tmp_path: Path) -> None:
    directory = _legacy_store_dir(tmp_path / "store", b"")
    (directory / "documents.pkl").unlink()
    (directory / "documents.npz").write_bytes(b"corrupted")
    with pytest.raises(Exception):
        _store(directory)


# Legacy pickle files


def test_a_legacy_pickle_file_is_never_unpickled(tmp_path: Path) -> None:
    marker = tmp_path / "p35-faiss-marker"
    directory = _legacy_store_dir(tmp_path / "store", pickle.dumps({"doc": _Payload(marker)}))
    try:
        _store(directory)
    except Exception:
        pass
    assert not marker.exists()


def test_a_store_with_only_a_legacy_pickle_file_fails_closed(tmp_path: Path) -> None:
    from ragbot.rag.store.document_persistence import LegacyPickleDocumentsError

    directory = _legacy_store_dir(tmp_path / "store", pickle.dumps({}))
    with pytest.raises(LegacyPickleDocumentsError) as caught:
        _store(directory)
    assert "legacy_pickle_migration" in str(caught.value)
    assert str(directory) in str(caught.value)


async def test_documents_npz_is_used_and_a_leftover_legacy_file_is_ignored(tmp_path: Path) -> None:
    store = _store(tmp_path / "store")
    await store.add_documents(_documents())
    marker = tmp_path / "p35-leftover-marker"
    (tmp_path / "store" / "documents.pkl").write_bytes(pickle.dumps({"doc": _Payload(marker)}))
    reopened = _store(tmp_path / "store")
    assert sorted(reopened.documents) == ["doc-1", "doc-2"]
    assert not marker.exists()


# The operator migration command


def test_the_migration_converts_a_trusted_legacy_store(tmp_path: Path) -> None:
    from ragbot.rag.store import legacy_pickle_migration as migration

    documents = {document.id: document for document in _documents()}
    directory = _legacy_store_dir(tmp_path / "store", pickle.dumps(documents))
    assert migration.main([str(directory), "--trust-legacy-pickle"]) == 0
    assert (directory / "documents.npz").exists()
    assert not (directory / "documents.pkl").exists()
    assert (directory / "documents.pkl.migrated").exists()
    assert _as_dicts(_store(directory).documents) == _as_dicts(documents)


def test_the_migration_reads_numpy_and_datetime_values(tmp_path: Path) -> None:
    from ragbot.rag.store import legacy_pickle_migration as migration
    from ragbot.rag.store.document_persistence import load_documents

    document = VectorDocument(
        id="d",
        content="c",
        embedding=[0.5, 0.25],
        metadata={"created": datetime(2026, 1, 2, 3, 4, 5), "weight": np.float32(0.5)},
    )
    document.embedding = np.array([0.5, 0.25], dtype=np.float32)
    directory = _legacy_store_dir(tmp_path / "store", pickle.dumps({"d": document}))
    assert migration.main([str(directory), "--trust-legacy-pickle"]) == 0
    loaded = load_documents(directory)
    assert loaded["d"].embedding == [0.5, 0.25]
    assert loaded["d"].metadata == {"created": "2026-01-02T03:04:05", "weight": 0.5}


def test_the_migration_needs_the_trust_flag(tmp_path: Path) -> None:
    from ragbot.rag.store import legacy_pickle_migration as migration

    directory = _legacy_store_dir(tmp_path / "store", pickle.dumps({}))
    assert migration.main([str(directory)]) == 2
    assert (directory / "documents.pkl").exists()
    assert not (directory / "documents.npz").exists()


@pytest.mark.parametrize("payload", ["path-touch", "os-system", "builtins-eval", "not-a-mapping", "foreign-object"])
def test_the_migration_refuses_functions_and_foreign_objects(tmp_path: Path, payload: str) -> None:
    from ragbot.rag.store import legacy_pickle_migration as migration

    marker = tmp_path / "p35-migration-marker"
    data = {
        "path-touch": lambda: pickle.dumps({"doc": _Payload(marker)}),
        "os-system": lambda: _reduce_pickle("os", "system", f"touch {marker}"),
        "builtins-eval": lambda: _reduce_pickle("builtins", "eval", f"__import__('pathlib').Path({str(marker)!r}).touch()"),
        "not-a-mapping": lambda: pickle.dumps([1, 2, 3]),
        "foreign-object": lambda: pickle.dumps({"doc": {"id": "doc", "content": "x"}}),
    }[payload]()
    directory = _legacy_store_dir(tmp_path / "store", data)
    assert migration.main([str(directory), "--trust-legacy-pickle"]) == 1
    assert not marker.exists()
    assert not (directory / "documents.npz").exists()
    assert (directory / "documents.pkl").exists()


# Code structure: only the operator migration command reads pickle data


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_only_the_migration_command_imports_pickle() -> None:
    importers = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "ragbot").rglob("*.py")
        if any(name.split(".")[0] in UNSAFE_MODULES for name in _imports(path))
    )
    assert importers == ["ragbot/rag/store/legacy_pickle_migration.py"]


def test_the_application_never_imports_the_migration_command() -> None:
    importers = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "ragbot").rglob("*.py")
        if path.name != "legacy_pickle_migration.py"
        and any(name.endswith("legacy_pickle_migration") for name in _imports(path))
    )
    assert importers == []
