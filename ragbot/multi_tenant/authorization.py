"""Authorization levels and tenant boundary checks.

Security fix C4 (Phase 2 hardening, see docs/BASELINE_AUDIT.md).

Before this change, any API key with the ``manage_tenant`` permission was
treated as a cross-tenant super admin. Permissions can be set per key, so a
tenant-scoped credential could reach every tenant.

Authorization levels now come from the user's role only:

- ``system_admin``: role ``super_admin`` (``system_admin`` is accepted as an
  alias). May act on every tenant.
- ``tenant_admin``: role ``admin`` (``tenant_admin`` is accepted as an alias).
  May manage and reset its own tenant only.
- ``user``: every other role (``manager``, ``user``, ``viewer``,
  ``api_user``). Limited to its own tenant and its granted permissions.

Permissions attached to a key never raise the authorization level.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional


class AuthorizationLevel(str, Enum):
    """Authorization level of an authenticated principal."""

    SYSTEM_ADMIN = "system_admin"
    TENANT_ADMIN = "tenant_admin"
    USER = "user"


SYSTEM_ADMIN_ROLES = frozenset({"super_admin", "system_admin"})
TENANT_ADMIN_ROLES = frozenset({"admin", "tenant_admin"})
RESET_PERMISSION = "delete_documents"
_ADMIN_LEVELS = (AuthorizationLevel.SYSTEM_ADMIN, AuthorizationLevel.TENANT_ADMIN)


def _role_name(role: Any) -> str:
    value = getattr(role, "value", role)
    return str(value or "").strip().lower()


def authorization_level_for_role(role: Any) -> AuthorizationLevel:
    """Map a user role to its authorization level."""
    name = _role_name(role)
    if name in SYSTEM_ADMIN_ROLES:
        return AuthorizationLevel.SYSTEM_ADMIN
    if name in TENANT_ADMIN_ROLES:
        return AuthorizationLevel.TENANT_ADMIN
    return AuthorizationLevel.USER


def authorization_level(principal: Any) -> AuthorizationLevel:
    """Return the authorization level of an authenticated principal.

    ``system_admin`` needs both a system admin role and the ``is_super_admin``
    flag that authentication sets from that role. A principal with only one of
    the two is treated as, at most, an admin of its own tenant.
    """
    if principal is None:
        return AuthorizationLevel.USER
    level = authorization_level_for_role(getattr(principal, "role", None))
    if level is AuthorizationLevel.SYSTEM_ADMIN and not bool(
        getattr(principal, "is_super_admin", False)
    ):
        return AuthorizationLevel.TENANT_ADMIN
    return level


def is_system_admin(principal: Any) -> bool:
    """Return True if the principal may act on every tenant."""
    return authorization_level(principal) is AuthorizationLevel.SYSTEM_ADMIN


def can_access_tenant(principal: Any, tenant_id: Optional[str]) -> bool:
    """Return True if the principal may act on ``tenant_id`` at all."""
    if principal is None or not tenant_id:
        return False
    if is_system_admin(principal):
        return True
    return getattr(principal, "tenant_id", None) == tenant_id


def can_manage_tenant(principal: Any, tenant_id: Optional[str]) -> bool:
    """Return True if the principal may manage ``tenant_id``.

    tenant_admin: own tenant only. system_admin: any tenant.
    """
    if not can_access_tenant(principal, tenant_id):
        return False
    return authorization_level(principal) in _ADMIN_LEVELS


def can_reset_tenant_store(principal: Any, tenant_id: Optional[str]) -> bool:
    """Return True if the principal may reset the vector store of ``tenant_id``.

    Allowed: system_admin on any tenant, tenant_admin on its own tenant, and
    principals with the explicit ``delete_documents`` permission on their own
    tenant.
    """
    if not can_access_tenant(principal, tenant_id):
        return False
    if authorization_level(principal) in _ADMIN_LEVELS:
        return True
    permissions = [
        str(getattr(permission, "value", permission))
        for permission in (getattr(principal, "permissions", None) or [])
    ]
    return RESET_PERMISSION in permissions
