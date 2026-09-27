"""Phase 3.5 security hardening regression tests."""

from __future__ import annotations

import hashlib
import inspect
import io
import json
import os
import pickle
import tarfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException, status

import ragbot.api.dependencies as dependencies
from ragbot.api.dependencies import get_authorized_tenant_context
from ragbot.caching.base import CacheKey
from ragbot.caching.redis_cache import RedisCache
from ragbot.monitoring.alert_manager import AlertManager
from ragbot.multi_tenant.models import AuthenticatedPrincipal, TenantStatus
from ragbot.rag.exceptions import VectorStoreError
from ragbot.rag.store.base import VectorDocument
from ragbot.rag.store.faiss_store import (
    FAISSStore,
    _load_documents_file,
    _write_documents_file,
)
from ragbot.security.secure_backup import _extract_tar_safely


class _TenantManager:
    def __init__(self, value=None, error: Exception | None = None) -> None:
        self.value = value
        self.error = error

    async def get_tenant(self, _tenant_id: str):
        if self.error is not None:
            raise self.error
        return self.value


def _principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        principal_id="principal-a",
        identity_type="api_key",
        tenant_id="tenant_a",
        role="user",
        permissions=[],
        is_super_admin=False,
    )


async def _tenant_context(manager):
    rag_service = SimpleNamespace(tenant_manager=manager)
    with patch.object(dependencies, "_multi_tenant_enabled", return_value=True):
        return await get_authorized_tenant_context(
            None,
            x_tenant_id="tenant_a",
            principal=_principal(),
            rag_service=rag_service,
        )


@pytest.mark.asyncio
async def test_tenant_verification_accepts_existing_active_tenant():
    tenant = SimpleNamespace(status=TenantStatus.ACTIVE)
    assert await _tenant_context(_TenantManager(tenant)) == "tenant_a"


@pytest.mark.asyncio
async def test_tenant_verification_rejects_missing_tenant():
    with pytest.raises(HTTPException) as exc:
        await _tenant_context(_TenantManager(None))
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_tenant_verification_fails_closed_on_backend_exception():
    with pytest.raises(HTTPException) as exc:
        await _tenant_context(_TenantManager(error=RuntimeError("database secret")))
    assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "database secret" not in str(exc.value.detail)


@pytest.mark.asyncio
async def test_tenant_verification_fails_closed_without_tenant_manager():
    with pytest.raises(HTTPException) as exc:
        await _tenant_context(None)
    assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_tenant_verification_rejects_inactive_tenant():
    tenant = SimpleNamespace(status=TenantStatus.SUSPENDED)
    with pytest.raises(HTTPException) as exc:
        await _tenant_context(_TenantManager(tenant))
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


def test_production_authentication_has_no_unittest_mock_dependency():
    source = inspect.getsource(dependencies)
    assert "unittest.mock" not in source
    assert "MagicMock" not in source


def test_redis_cache_json_round_trip():
    cache = RedisCache(redis_url="redis://localhost:6379/15")
    value = {
        "answer": "safe",
        "numbers": [1, 2.5, True, None],
        "metadata": {"tenant": "tenant_a"},
    }
    encoded = cache._serialize(value)
    assert json.loads(encoded.decode("utf-8"))["version"] == 1
    assert cache._deserialize(encoded) == value


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b"[]",
        b'{"version":2,"value":{}}',
        b'{"version":1,"value":{},"extra":true}',
    ],
)
def test_redis_cache_rejects_malformed_or_wrong_schema(payload):
    cache = RedisCache(redis_url="redis://localhost:6379/15")
    with pytest.raises(Exception):
        cache._deserialize(payload)


def test_redis_cache_never_executes_legacy_pickle(tmp_path: Path):
    marker = tmp_path / "pickle-executed"

    class Payload:
        def __reduce__(self):
            return (os.system, (f"touch {marker}",))

    legacy = pickle.dumps(Payload())
    cache = RedisCache(redis_url="redis://localhost:6379/15")
    with pytest.raises(Exception):
        cache._deserialize(legacy)
    assert not marker.exists()


def test_redis_cache_rejects_pickle_configuration():
    with pytest.raises(ValueError, match="safe JSON"):
        RedisCache(redis_url="redis://localhost:6379/15", serialization="pickle")


def test_faiss_document_json_round_trip(tmp_path: Path):
    path = tmp_path / "documents.json"
    document = VectorDocument(
        id="doc-1",
        content="content",
        embedding=[0.1, 0.2],
        metadata={"tenant_id": "tenant_a"},
    )
    _write_documents_file(path, {"doc-1": document})
    loaded = _load_documents_file(path)
    assert loaded["doc-1"].to_dict() == document.to_dict()


@pytest.mark.parametrize(
    "payload",
    [
        {"documents": []},
        {"version": 999, "documents": []},
        {"version": 1, "documents": {}},
        {"version": 1, "documents": [{"id": "x"}]},
    ],
)
def test_faiss_document_json_rejects_invalid_schema(tmp_path: Path, payload):
    path = tmp_path / "documents.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises((ValueError, TypeError, KeyError)):
        _load_documents_file(path)


def test_faiss_store_rejects_legacy_pickle_without_executing_it(tmp_path: Path):
    marker = tmp_path / "faiss-pickle-executed"

    class Payload:
        def __reduce__(self):
            return (os.system, (f"touch {marker}",))

    (tmp_path / "documents.pkl").write_bytes(pickle.dumps(Payload()))
    with pytest.raises(VectorStoreError, match="Legacy FAISS documents.pkl"):
        FAISSStore(store_path=str(tmp_path), dimension=128)
    assert not marker.exists()


@pytest.mark.asyncio
async def test_alert_condition_supports_documented_comparisons():
    manager = AlertManager()
    assert await manager._evaluate_condition(
        "cpu_usage > threshold", 80.0, {"cpu_usage": 90.0}
    )
    assert not await manager._evaluate_condition(
        "cpu_usage > threshold", 80.0, {"cpu_usage": 70.0}
    )
    assert await manager._evaluate_condition(
        "cpu_usage > threshold and error_rate < 5",
        80.0,
        {"cpu_usage": 90.0, "error_rate": 1.0},
    )


@pytest.mark.asyncio
async def test_alert_condition_rejects_unsupported_expressions(tmp_path: Path):
    marker = tmp_path / "eval-executed"
    manager = AlertManager()
    expression = f"__import__('os').system('touch {marker}') == 0"
    assert not await manager._evaluate_condition(expression, 1.0, {})
    assert not marker.exists()


def _archive_with_member(name: str, *, type_: bytes | None = None, linkname: str = "") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo(name)
        if type_ is not None:
            info.type = type_
            info.linkname = linkname
            archive.addfile(info)
        else:
            data = b"safe"
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _extract_bytes(data: bytes, destination: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        _extract_tar_safely(archive, destination)


def test_secure_tar_extracts_valid_archive(tmp_path: Path):
    destination = tmp_path / "restore"
    _extract_bytes(_archive_with_member("backup/store/data.txt"), destination)
    assert (destination / "backup/store/data.txt").read_bytes() == b"safe"


@pytest.mark.parametrize(
    "member",
    [
        "../../outside.txt",
        "backup/../../../outside.txt",
        "/absolute.txt",
        r"C:\outside.txt",
    ],
)
def test_secure_tar_rejects_path_escape(tmp_path: Path, member: str):
    destination = tmp_path / "restore"
    with pytest.raises(ValueError, match="Unsafe archive member"):
        _extract_bytes(_archive_with_member(member), destination)
    assert not (tmp_path / "outside.txt").exists()


@pytest.mark.parametrize(
    ("type_", "linkname"),
    [
        (tarfile.SYMTYPE, "../../outside.txt"),
        (tarfile.LNKTYPE, "../../outside.txt"),
    ],
)
def test_secure_tar_rejects_links(tmp_path: Path, type_: bytes, linkname: str):
    destination = tmp_path / "restore"
    with pytest.raises(ValueError, match="Unsupported archive member type"):
        _extract_bytes(
            _archive_with_member("backup/link", type_=type_, linkname=linkname),
            destination,
        )
    assert not (tmp_path / "outside.txt").exists()


def test_cache_key_md5_behavior_is_compatibility_stable():
    text = "hello"
    expected = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
    assert CacheKey.embedding(text, "model") == f"embedding:model:{expected}"
