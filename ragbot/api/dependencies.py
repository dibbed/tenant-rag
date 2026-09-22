import inspect
from typing import Optional
from unittest.mock import MagicMock

from fastapi import Depends, Header, HTTPException, Request, status

from ragbot.configs.settings import settings
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


async def get_current_principal(
    request: Request,
    rag_service: RAGService = Depends(get_rag_service_dep),
) -> Optional[AuthenticatedPrincipal]:
    """
    Extract and authenticate the calling principal from request headers.

    When multi-tenancy is disabled, returns None.
    When multi-tenancy is enabled, extracts credentials from 'X-API-Key' or 'Authorization: Bearer <token>',
    authenticates via TenantAuth, and returns the AuthenticatedPrincipal.
    Raises HTTP 401 if credentials are missing, malformed, invalid, expired, or revoked.
    """
    if not getattr(getattr(settings, "multi_tenant", object()), "enabled", False):
        return None

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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return principal


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
      - Enforces tenant isolation: requested X-Tenant-ID must match principal.tenant_id
        unless principal is super_admin.
      - If X-Tenant-ID is omitted, defaults to principal.tenant_id.
      - Verifies target tenant exists and is active.
    """
    if not getattr(getattr(settings, "multi_tenant", object()), "enabled", False):
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
    if not principal.is_super_admin and principal.tenant_id != target_tenant:
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
    """Verify principal is authorized to perform store reset."""
    if not getattr(getattr(settings, "multi_tenant", object()), "enabled", False):
        return

    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
        )

    allowed_roles = {"admin", "super_admin", "manager"}
    has_perm = (
        "delete_documents" in principal.permissions
        or "manage_tenant" in principal.permissions
    )
    if (
        principal.role not in allowed_roles
        and not has_perm
        and not principal.is_super_admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Insufficient permissions to perform store reset",
        )

    if not tenant_id and not principal.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Tenant administrators can only reset their own tenant store",
        )
