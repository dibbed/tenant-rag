"""Multi-tenant support system for RAG Bot."""

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
from .tenant_analytics import TenantAnalytics
from .tenant_auth import ROLE_PERMISSIONS, Permission, TenantAuth, UserRole
from .tenant_manager import TenantManager

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
    # Models
    "TenantConfig",
    "TenantFeatures",
    "TenantLimits",
    # Core Classes
    "TenantManager",
    "TenantPlan",
    "TenantPolicy",
    "TenantStatus",
    "TenantTier",
    "TenantUsage",
    "TenantUser",
    # Auth Enums
    "UserRole",
]
