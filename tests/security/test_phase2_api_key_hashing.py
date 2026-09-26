"""Phase 2 regression tests: API key storage and verification.

Audit finding C3 (docs/BASELINE_AUDIT.md) and related credential issues.

Vulnerability: API keys were stored as unsalted SHA-256 digests, and the key
lookup also accepted the stored digest itself as a credential, so anyone who
could read tenants.db or a backup could authenticate without the secret.
Raw keys were kept as dictionary keys in process memory, a revocation made by
another process was ignored by the in-memory fallback, and users without a
password hash could log in with the fixed password "password123".

Expected behavior: keys use the format rgb_<key_id>_<secret>; only a salted
scrypt hash is stored; lookup is by key id; stored hashes are never accepted;
legacy SHA-256 keys are rejected with an explicit migration error.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ragbot.api.app import create_app
from ragbot.api.dependencies import get_integration_service_dep, get_rag_service_dep
from ragbot.configs.settings import MultiTenantSettings, Settings
from ragbot.multi_tenant.api_key_hashing import (
    LEGACY_API_KEY_ERROR,
    hash_api_key_secret,
    is_scrypt_hash,
    parse_api_key,
    verify_api_key_secret,
)
from ragbot.multi_tenant.models import TenantApiKey, TenantTier
from ragbot.multi_tenant.tenant_auth import Permission, TenantAuth, UserRole
from ragbot.multi_tenant.tenant_manager import TenantManager
from ragbot.services.rag_service import QueryResult

KEY_FORMAT = re.compile(r"^rgb_[0-9a-f]{32}_[A-Za-z0-9_-]{43}$")
TENANT = "tenant_keys"
TABLES = ("tenants", "tenant_users", "tenant_usage", "tenant_audit_logs", "tenant_api_keys")


def _settings(db_path):
    return Settings(
        multi_tenant=MultiTenantSettings(
            enabled=True, default_tier="free", data_dir=db_path.parent
        )
    )


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "phase2_keys.db"


@pytest.fixture
def manager(db_path):
    mgr = TenantManager(_settings(db_path), db_path=db_path)
    yield mgr
    mgr.close()


@pytest.fixture
def auth(manager):
    return TenantAuth(manager)


@pytest.fixture
def api_client(manager, auth):
    rag = MagicMock()
    rag.tenant_manager = manager
    rag.tenant_auth = auth
    rag.query_documents = AsyncMock(
        return_value=QueryResult(
            answer="ok",
            sources=[],
            confidence_score=1.0,
            processing_time=0.01,
            language="en",
            retrieved_chunks=[],
            metadata={},
        )
    )
    integration = MagicMock()
    integration.track_user_action = AsyncMock()
    with patch("ragbot.api.dependencies.settings.multi_tenant.enabled", True):
        app = create_app(lifespan_context=None)
        app.dependency_overrides[get_integration_service_dep] = lambda: integration
        app.dependency_overrides[get_rag_service_dep] = lambda: rag
        with TestClient(app) as client:
            yield client


async def _create_tenant(manager, tenant_id=TENANT, tier=TenantTier.FREE):
    await manager.create_tenant(name=f"{tenant_id} corp", tenant_id=tenant_id, tier=tier)


def _insert_legacy_key(manager, tenant_id=TENANT):
    """Store a key exactly as the pre-Phase-2 code did (unsalted SHA-256)."""
    raw = "rgb_" + secrets.token_urlsafe(32)
    record = TenantApiKey(
        key_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id="usr_legacy",
        name="legacy_key",
        key_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        key_prefix=raw[:12],
        permissions=[
            Permission.API_ACCESS.value,
            Permission.VIEW_DOCUMENTS.value,
            Permission.ASK_QUESTIONS.value,
        ],
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(days=30),
        is_active=True,
    )
    manager.save_api_key(record)
    return raw, record


def _db_dump(manager) -> str:
    rows = []
    for table in TABLES:
        rows.extend(manager._conn.execute(f"SELECT * FROM {table}").fetchall())
    return repr(rows)


def _query(client, key):
    return client.post("/api/v1/query", json={"question": "hello"}, headers={"X-API-Key": key})


@pytest.mark.asyncio
async def test_new_api_key_has_key_id_format_and_scrypt_hash(manager, auth):
    await _create_tenant(manager)
    ok, raw_key, err = await auth.create_api_key(tenant_id=TENANT, name="svc")
    assert ok, err

    assert KEY_FORMAT.match(raw_key)
    parsed = parse_api_key(raw_key)
    record = manager.get_api_key_by_id(parsed.key_id)
    assert record is not None
    assert is_scrypt_hash(record.key_hash)
    assert record.key_hash != hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    assert raw_key not in record.key_hash
    assert record.key_prefix == raw_key[:12]


@pytest.mark.asyncio
async def test_raw_api_key_is_never_stored_or_kept_in_memory(manager, auth):
    await _create_tenant(manager)
    ok, raw_key, err = await auth.create_api_key(tenant_id=TENANT, name="svc")
    assert ok, err
    secret = parse_api_key(raw_key).secret

    dump = _db_dump(manager)
    assert raw_key not in dump
    assert secret not in dump
    assert hashlib.sha256(raw_key.encode("utf-8")).hexdigest() not in dump
    assert raw_key not in repr(auth.api_keys)
    assert raw_key not in auth.api_keys


@pytest.mark.asyncio
async def test_valid_api_key_authenticates(manager, auth, api_client):
    await _create_tenant(manager)
    ok, raw_key, err = await auth.create_api_key(tenant_id=TENANT, name="svc")
    assert ok, err

    ok_auth, principal, error = await auth.authenticate_principal(raw_key)
    assert ok_auth is True and error is None
    assert principal.tenant_id == TENANT
    assert principal.principal_id == parse_api_key(raw_key).key_id

    assert _query(api_client, raw_key).status_code == status.HTTP_200_OK
    bearer = api_client.post(
        "/api/v1/query",
        json={"question": "hello"},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert bearer.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_valid_api_key_authenticates_after_restart(db_path, manager, auth):
    """A new process has no verification cache and must verify with scrypt."""
    await _create_tenant(manager)
    ok, raw_key, err = await auth.create_api_key(tenant_id=TENANT, name="svc")
    assert ok, err

    manager2 = TenantManager(_settings(db_path), db_path=db_path)
    try:
        auth2 = TenantAuth(manager2)
        ok_auth, principal, error = await auth2.authenticate_principal(raw_key)
        assert ok_auth is True, error
        assert principal.tenant_id == TENANT
    finally:
        manager2.close()


@pytest.mark.asyncio
async def test_invalid_api_keys_are_rejected(manager, auth, api_client):
    await _create_tenant(manager)
    ok, raw_key, err = await auth.create_api_key(tenant_id=TENANT, name="svc")
    assert ok, err
    parsed = parse_api_key(raw_key)

    wrong_secret = f"rgb_{parsed.key_id}_{secrets.token_urlsafe(32)}"
    unknown_id = f"rgb_{uuid.uuid4().hex}_{parsed.secret}"
    candidates = [wrong_secret, unknown_id, "rgb_" + secrets.token_urlsafe(32), "garbage", raw_key + "x"]

    fresh_auth = TenantAuth(manager)  # no verification cache
    for candidate in candidates:
        for checker in (auth, fresh_auth):
            ok_auth, principal, _ = await checker.authenticate_principal(candidate)
            assert ok_auth is False and principal is None, candidate
        response = _query(api_client, candidate)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Invalid, expired, or revoked authentication credentials"


@pytest.mark.asyncio
async def test_stored_hash_is_never_accepted_as_credential(manager, auth, api_client):
    """C3 core issue: a database reader must not be able to use a stored hash."""
    await _create_tenant(manager)
    ok, raw_key, err = await auth.create_api_key(tenant_id=TENANT, name="svc")
    assert ok, err
    scrypt_hash = manager.get_api_key_by_id(parse_api_key(raw_key).key_id).key_hash
    _legacy_raw, legacy_record = _insert_legacy_key(manager)

    for stored_value in (scrypt_hash, legacy_record.key_hash):
        ok_auth, principal, _ = await auth.authenticate_principal(stored_value)
        assert ok_auth is False and principal is None
        assert _query(api_client, stored_value).status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_legacy_sha256_key_is_rejected_with_migration_error(manager, auth, api_client):
    await _create_tenant(manager)
    legacy_raw, _ = _insert_legacy_key(manager)

    ok_auth, principal, error = await auth.authenticate_principal(legacy_raw)
    assert ok_auth is False and principal is None
    assert error == LEGACY_API_KEY_ERROR

    response = _query(api_client, legacy_raw)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == LEGACY_API_KEY_ERROR
    assert "Legacy API key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_legacy_sha256_key_can_still_be_revoked(manager, auth):
    await _create_tenant(manager)
    legacy_raw, legacy_record = _insert_legacy_key(manager)

    assert await auth.revoke_api_key(tenant_id=TENANT, api_key_or_id=legacy_raw) is True
    assert manager.get_api_key_by_id(legacy_record.key_id).is_active is False


@pytest.mark.asyncio
async def test_revoked_key_is_rejected_immediately(manager, auth, api_client):
    await _create_tenant(manager)
    ok, key_1, _ = await auth.create_api_key(tenant_id=TENANT, name="by_raw")
    ok2, key_2, _ = await auth.create_api_key(tenant_id=TENANT, name="by_id")
    assert ok and ok2
    assert _query(api_client, key_1).status_code == status.HTTP_200_OK
    assert _query(api_client, key_2).status_code == status.HTTP_200_OK

    assert await auth.revoke_api_key(tenant_id=TENANT, api_key_or_id=key_1) is True
    assert await auth.revoke_api_key(
        tenant_id=TENANT, api_key_or_id=parse_api_key(key_2).key_id
    ) is True

    for key in (key_1, key_2):
        ok_auth, _, error = await auth.authenticate_principal(key)
        assert ok_auth is False and error == "API key has been revoked"
        assert _query(api_client, key).status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_revocation_by_another_process_takes_effect_immediately(db_path, manager, auth):
    """The in-memory fallback used to keep a key valid after a CLI revocation."""
    await _create_tenant(manager)
    ok, raw_key, err = await auth.create_api_key(tenant_id=TENANT, name="svc")
    assert ok, err
    assert (await auth.authenticate_principal(raw_key))[0] is True

    other_process = TenantManager(_settings(db_path), db_path=db_path)
    try:
        assert other_process.revoke_api_key(parse_api_key(raw_key).key_id, tenant_id=TENANT)
    finally:
        other_process.close()

    ok_auth, principal, _ = await auth.authenticate_principal(raw_key)
    assert ok_auth is False and principal is None


@pytest.mark.asyncio
async def test_key_listing_reports_hash_scheme_without_secrets(manager, auth):
    await _create_tenant(manager)
    ok, raw_key, err = await auth.create_api_key(tenant_id=TENANT, name="svc")
    assert ok, err
    _insert_legacy_key(manager)

    keys = await auth.list_api_keys(TENANT)
    schemes = sorted(k["hash_scheme"] for k in keys)
    assert schemes == ["legacy-sha256", "scrypt"]
    for entry in keys:
        assert "key_hash" not in entry
        assert raw_key not in repr(entry)
    assert raw_key[:12] in [k["key_prefix"] for k in keys]


@pytest.mark.asyncio
async def test_keys_without_persistent_store_hold_no_raw_key():
    auth = TenantAuth(tenant_manager=None)
    ok, raw_key, err = await auth.create_api_key(tenant_id="memory_tenant", name="svc")
    assert ok, err
    assert raw_key not in repr(auth.api_keys)

    ok_auth, principal, error = await auth.authenticate_principal(raw_key)
    assert ok_auth is True, error
    assert principal.tenant_id == "memory_tenant"

    assert await auth.revoke_api_key("memory_tenant", raw_key) is True
    assert (await auth.authenticate_principal(raw_key))[0] is False


def test_scrypt_verification_rejects_tampered_or_wrong_input():
    raw_key = "rgb_" + uuid.uuid4().hex + "_" + secrets.token_urlsafe(32)
    stored = hash_api_key_secret(raw_key)
    assert verify_api_key_secret(raw_key, stored) is True
    assert verify_api_key_secret(raw_key + "x", stored) is False
    assert verify_api_key_secret(raw_key, hashlib.sha256(raw_key.encode()).hexdigest()) is False

    parts = stored.split("$")
    too_costly = "$".join(["scrypt", str(2**30)] + parts[2:])
    assert verify_api_key_secret(raw_key, too_costly) is False
    assert verify_api_key_secret(raw_key, "scrypt$16384$8$1$bad$bad") is False


@pytest.mark.asyncio
async def test_user_without_password_hash_cannot_log_in_with_default_password(manager, auth):
    """Auto-created API users have no password; 'password123' must not work."""
    await _create_tenant(manager)
    ok, _raw_key, err = await auth.create_api_key(tenant_id=TENANT, name="default")
    assert ok, err

    ok_login, user, _ = await auth.authenticate_user(TENANT, "api_default", "password123")
    assert ok_login is False and user is None


@pytest.mark.asyncio
async def test_key_without_user_id_is_never_bound_to_system_admin(manager, auth):
    """C4: a key created without user_id must not inherit super_admin rights."""
    await _create_tenant(manager, tier=TenantTier.BASIC)
    ok_user, _root, err = await auth.create_user(
        tenant_id=TENANT,
        username="root",
        email="root@keys.test",
        password="Str0ng-Passw0rd!",
        role=UserRole.SUPER_ADMIN,
    )
    assert ok_user, err

    ok, raw_key, err = await auth.create_api_key(tenant_id=TENANT, name="implicit")
    assert ok, err
    ok_auth, principal, error = await auth.authenticate_principal(raw_key)
    assert ok_auth is True, error
    assert principal.is_super_admin is False
