"""Test-only adapter for characterizing the removed legacy SQLite runtime.

Production TenantManager no longer accepts or selects SQLite. These tests keep
the old persistence/security behavior covered until the legacy compatibility
code can be deleted entirely in a later cleanup.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from ragbot.multi_tenant.tenant_manager import TenantManager

if TYPE_CHECKING:
    from pathlib import Path

    from ragbot.multi_tenant.models import (
        TenantAuditLog,
        TenantConfig,
        TenantPolicy,
        TenantUsage,
        TenantUser,
    )


class LegacySQLiteTenantManager(TenantManager):
    """Explicit test-only entry point for the historical SQLite code path."""

    def __init__(self, settings: Any | None, db_path: Path) -> None:
        self.settings = settings
        self.tenant_policies: dict[str, list[TenantPolicy]] = {}
        self._tenant_cache: dict[str, Any] = {}
        self._isolation_rules: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

        self._database_runtime = None
        self._session_factory = None
        self._legacy_sqlite = True

        self.tenants: dict[str, TenantConfig] = {}
        self.tenant_users: dict[str, list[TenantUser]] = {}
        self.tenant_usage: dict[str, list[TenantUsage]] = {}
        self.tenant_audit_logs: dict[str, list[TenantAuditLog]] = {}
        self.db_path = db_path

        self._init_db()
        self._load_persisted_data()
