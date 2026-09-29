"""Multi-tenant support system for RAG Bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .models import (
    DEFAULT_TIER_CONFIGS,
    AuthenticatedPrincipal,
    TenantApiKey,
    TenantAuditLog,
    TenantBilling,
    TenantConfig,
    TenantFeatures,
    TenantLimits,
    TenantPlan,
    TenantPolicy,
    TenantStatus,
    TenantTier,
    TenantUsage,
    TenantUser,
)

if TYPE_CHECKING:
    from .tenant_analytics import TenantAnalytics
    from .tenant_auth import ROLE_PERMISSIONS, Permission, TenantAuth, UserRole
    from .tenant_manager import TenantManager


def __getattr__(name: str) -> Any:
    """Load higher-level services lazily to avoid package import cycles."""
    if name == "TenantManager":
        from .tenant_manager import TenantManager

        return TenantManager
    if name == "TenantAnalytics":
        from .tenant_analytics import TenantAnalytics

        return TenantAnalytics
    if name in {"TenantAuth", "Permission", "UserRole", "ROLE_PERMISSIONS"}:
        from .tenant_auth import ROLE_PERMISSIONS, Permission, TenantAuth, UserRole

        return {
            "TenantAuth": TenantAuth,
            "Permission": Permission,
            "UserRole": UserRole,
            "ROLE_PERMISSIONS": ROLE_PERMISSIONS,
        }[name]
    raise AttributeError(name)


__all__ = [
    "DEFAULT_TIER_CONFIGS",
    "ROLE_PERMISSIONS",
    "AuthenticatedPrincipal",
    "Permission",
    "TenantAnalytics",
    "TenantApiKey",
    "TenantAuditLog",
    "TenantAuth",
    "TenantBilling",
    "TenantConfig",
    "TenantFeatures",
    "TenantLimits",
    "TenantManager",
    "TenantPlan",
    "TenantPolicy",
    "TenantStatus",
    "TenantTier",
    "TenantUsage",
    "TenantUser",
    "UserRole",
]
