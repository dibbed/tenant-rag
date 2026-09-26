"""Tenant identifier validation for storage partitioning.

Security fix for audit findings C1, C2 and C12 (Phase 2 hardening).

A tenant id becomes a filesystem path segment
(``<STORE_PATH>/tenants/<tenant_id>``) and part of a collection name
(``tenant_<tenant_id>``). A value such as ``../other`` could leave the tenant
partition, and a tenant reset deletes that path with ``shutil.rmtree``. Tenant
ids are therefore limited to a safe character set before any path or
collection name is built.
"""

from __future__ import annotations

import re

from ragbot.rag.exceptions import TenantStorageError

TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def is_valid_tenant_id(tenant_id: object) -> bool:
    """Return True if ``tenant_id`` is safe to use as a partition name."""
    return isinstance(tenant_id, str) and TENANT_ID_PATTERN.fullmatch(tenant_id) is not None


def validate_tenant_id(tenant_id: object) -> str:
    """Return ``tenant_id`` if it is valid, else raise TenantStorageError."""
    if not is_valid_tenant_id(tenant_id):
        raise TenantStorageError("Invalid tenant identifier", operation="validate")
    return tenant_id  # type: ignore[return-value]
