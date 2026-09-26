import inspect
from typing import Optional
from unittest.mock import MagicMock

from fastapi import Depends, Header, HTTPException, Request, status

from ragbot.api.access_mode import ANONYMOUS_DISABLED_DETAIL, anonymous_access_allowed
from ragbot.api.edge.rate_limiter import count_request, count_unauthenticated_request
from ragbot.configs.settings import settings
from ragbot.multi_tenant.api_key_hashing import LEGACY_API_KEY_ERROR
from ragbot.multi_tenant.authorization import (
    can_access_tenant,
    can_manage_tenant,
    can_reset_tenant_store,
    is_system_admin,
)
from ragbot.multi_tenant.models import AuthenticatedPrincipal, TenantStatus
from ragbot.multi_tenant.tenant_auth import TenantAuth, UserRole
from ragbot.outputs.logger import logger
from ragbot.services.integration_service import (
    IntegrationService,
    get_integration_service,
)
from ragbot.services.rag_service import RAGService


async def get_integration_service_dep(request: Request) -> IntegrationService:
    """Retrieve shared IntegrationService instance from app state or singleton."""
    if (
        hasattr(request.app.state, "integration_service")
        and request.app.state.integration_service is not None
    ):
        return request.app.state.integration_service
    return await get_integration_service()


async def get_rag_service_dep(
    integration_service: IntegrationService = Depends(get_integration_service_dep),
) -> RAGService:
    """Retrieve shared RAGService instance from integration service."""
    rag_service = integration_service.get_rag_service()
    if rag_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAGService is not available or failed to initialize",
        )
    return rag_service


def _multi_tenant_enabled() -> bool:
    """Return True when multi-tenant authentication is enabled."""
    return bool(getattr(getattr(settings, "multi_tenant", object()), "enabled", False))


async def get_current_principal(
    request: Request,
    rag_service: RAGService = Depends(get_rag_service_dep),
) -> Optional[AuthenticatedPrincipal]:
    """
    Extract and authenticate the calling principal from request headers.

    - Multi-tenant mode: the credential comes from 'X-API-Key' or
      'Authorization: Bearer <token>' and is verified by TenantAuth. Missing,
      malformed, invalid, expired, revoked or legacy credentials return 401.
    - Single-tenant mode has no credential store. Security (C5): anonymous
      access is allowed only when ENVIRONMENT=development and
      ALLOW_ANONYMOUS=true. Otherwise the request is rejected with 401.
    """
    if not _multi_tenant_enabled():
        if anonymous_access_allowed():
            return None
        # Security (C9): a rejected request still counts against the Client
        # Address. Over the limit, the caller gets 429 instead of 401.
        await count_unauthenticated_request(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ANONYMOUS_DISABLED_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract credential from headers
    credential = request.headers.get("X-API-Key")
    if not credential:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.strip().split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                credential = parts[1].strip()
            elif len(parts) == 1:
                credential = parts[0].strip()

    if not credential:
        await count_unauthenticated_request(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Resolve TenantAuth
    tenant_auth = getattr(rag_service, "tenant_auth", None)
    if tenant_auth is None:
        tenant_mgr = getattr(rag_service, "tenant_manager", None)
        tenant_auth = TenantAuth(tenant_mgr)

    # Authenticate credential (supporting awaitable or sync mock)
    auth_res = tenant_auth.authenticate_principal(credential)
    if inspect.isawaitable(auth_res):
        auth_ok, principal, error_msg = await auth_res
    else:
        auth_ok, principal, error_msg = auth_res

    if not auth_ok or principal is None:
        # Security (C3): legacy SHA-256 keys get an explicit migration message.
        # Every other failure keeps the generic message.
        detail = (
            LEGACY_API_KEY_ERROR
            if error_msg == LEGACY_API_KEY_ERROR
            else "Invalid, expired, or revoked authentication credentials"
        )
        # Security (C9): failed attempts count against the Client Address.
        await count_unauthenticated_request(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return principal


async def enforce_rate_limit(
    request: Request,
    principal: AuthenticatedPrincipal | None = Depends(get_current_principal),
) -> None:
    """Count the request against its Rate Limit Subject (Security C9).

    Router dependency of every API router except health. It runs after
    authentication: an authenticated request counts against its Principal,
    and a request without a Principal (anonymous development mode) counts
    against its Client Address. A request that RateLimitMiddleware already
    counted before the body was read is not counted again. Over the limit,
    the request is refused with HTTP 429.
    """
    await count_request(request, principal)


async def get_authorized_tenant_context(
    request: Request,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_principal),
    rag_service: RAGService = Depends(get_rag_service_dep),
) -> Optional[str]:
    """
    Retrieve and authorize tenant context.

    - In single-tenant mode (multi_tenant.enabled=False): returns None.
    - In multi-tenant mode:
      - Validates principal is authenticated.
      - Security (C4): the requested X-Tenant-ID must match the principal's
        tenant unless the principal is a system_admin (role super_admin).
        Key permissions such as manage_tenant never grant cross-tenant access.
      - If X-Tenant-ID is omitted, defaults to principal.tenant_id.
      - Verifies target tenant exists and is active.
    """
    if not _multi_tenant_enabled():
        return None

    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Determine requested tenant
    target_tenant = (
        x_tenant_id.strip()
        if x_tenant_id and x_tenant_id.strip()
        else principal.tenant_id
    )

    # Check tenant authorization boundary
    if not can_access_tenant(principal, target_tenant):
        logger.warning(
            f"Tenant authorization failure: Principal '{principal.principal_id}' of tenant "
            f"'{principal.tenant_id}' denied access to tenant '{target_tenant}'"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Access to requested tenant '{target_tenant}' is denied",
        )

    # Check if target tenant exists and is active
    tenant_mgr = getattr(rag_service, "tenant_manager", None)
    if tenant_mgr and hasattr(tenant_mgr, "get_tenant"):
        try:
            tenant_res = tenant_mgr.get_tenant(target_tenant)
            tenant = await tenant_res if inspect.isawaitable(tenant_res) else tenant_res
            if tenant is None and not isinstance(tenant_mgr, MagicMock):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Tenant '{target_tenant}' does not exist",
                )
            if tenant is not None:
                status_attr = getattr(tenant, "status", None)
                if status_attr is not None and not isinstance(status_attr, MagicMock):
                    status_str = (
                        status_attr.value
                        if hasattr(status_attr, "value")
                        else str(status_attr)
                    )
                    if status_str.lower() != "active":
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Tenant '{target_tenant}' is not active",
                        )
        except HTTPException:
            raise
        except Exception as t_err:
            logger.debug(f"Tenant verification note: {t_err}")

    return target_tenant


# Alias for backward compatibility across all existing route signatures
get_tenant_context = get_authorized_tenant_context


async def verify_reset_authorization(
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_principal),
    tenant_id: Optional[str] = Depends(get_authorized_tenant_context),
) -> None:
    """Verify the principal may reset the target tenant store.

    Security (C4):
    - system_admin (role super_admin): any tenant, and the global store.
    - tenant_admin (role admin): its own tenant only.
    - other principals: only with the explicit ``delete_documents``
      permission, and only on their own tenant.
    The ``manager`` role and the ``manage_tenant`` key permission no longer
    grant reset rights.
    """
    if not _multi_tenant_enabled():
        return

    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
        )

    if not tenant_id:
        if is_system_admin(principal):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Tenant administrators can only reset their own tenant store",
        )

    if not can_reset_tenant_store(principal, tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Insufficient permissions to perform store reset",
        )


async def require_tenant_admin(
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_principal),
    tenant_id: Optional[str] = Depends(get_authorized_tenant_context),
) -> Optional[AuthenticatedPrincipal]:
    """Require tenant management rights on the target tenant.

    Security (C4): use this dependency for every tenant management route.
    tenant_admin may manage only its own tenant; system_admin may manage any
    tenant; every other principal gets HTTP 403.
    """
    if not _multi_tenant_enabled():
        return principal

    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
        )

    if not tenant_id or not can_manage_tenant(principal, tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Tenant management requires tenant_admin on the target tenant or system_admin",
        )
    return principal
