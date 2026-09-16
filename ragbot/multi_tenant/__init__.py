"""Multi-tenant support system for RAG Bot."""

from .models import (
    TenantConfig,
    TenantUser,
    TenantUsage,
    TenantBilling,
    TenantPolicy,
    TenantAuditLog,
    TenantStatus,
    TenantTier,
    TenantPlan,
    TenantLimits,
    TenantFeatures,
    DEFAULT_TIER_CONFIGS,
)

from .tenant_manager import TenantManager
from .tenant_auth import TenantAuth, UserRole, Permission, ROLE_PERMISSIONS
from .tenant_analytics import TenantAnalytics

__all__ = [
    # Models
    "TenantConfig",
    "TenantUser",
    "TenantUsage",
    "TenantBilling",
    "TenantPolicy",
    "TenantAuditLog",
    "TenantStatus",
    "TenantTier",
    "TenantPlan",
    "TenantLimits",
    "TenantFeatures",
    "DEFAULT_TIER_CONFIGS",
    # Core Classes
    "TenantManager",
    "TenantAuth",
    "TenantAnalytics",
    # Auth Enums
    "UserRole",
    "Permission",
    "ROLE_PERMISSIONS",
]
