"""Tenant authentication and authorization system."""

import asyncio
import hashlib
import hmac
import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from ..outputs.logger import logger
from .api_key_hashing import (
    LEGACY_API_KEY_ERROR,
    VERIFIED_KEY_CACHE_MAX_ENTRIES,
    VERIFIED_KEY_CACHE_TTL_SECONDS,
    describe_hash_scheme,
    generate_api_key,
    hash_api_key_secret,
    is_scrypt_hash,
    legacy_sha256_digest,
    parse_api_key,
    verify_api_key_secret,
)
from .authorization import AuthorizationLevel, authorization_level_for_role
from .models import (
    TenantConfig,
    TenantUser,
    TenantAuditLog,
    TenantStatus,
    TenantApiKey,
    AuthenticatedPrincipal,
)


class UserRole(str, Enum):
    """نقش‌های کاربر"""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    VIEWER = "viewer"


class Permission(str, Enum):
    """مجوزها"""

    # مدیریت tenant
    MANAGE_TENANT = "manage_tenant"
    VIEW_TENANT_SETTINGS = "view_tenant_settings"
    UPDATE_TENANT_SETTINGS = "update_tenant_settings"

    # مدیریت کاربران
    MANAGE_USERS = "manage_users"
    INVITE_USERS = "invite_users"
    REMOVE_USERS = "remove_users"

    # مدیریت اسناد
    UPLOAD_DOCUMENTS = "upload_documents"
    DELETE_DOCUMENTS = "delete_documents"
    VIEW_DOCUMENTS = "view_documents"

    # پرسش و پاسخ
    ASK_QUESTIONS = "ask_questions"
    VIEW_QUERY_HISTORY = "view_query_history"

    # تحلیل‌ها
    VIEW_ANALYTICS = "view_analytics"
    EXPORT_ANALYTICS = "export_analytics"

    # API
    API_ACCESS = "api_access"
    WEBHOOK_ACCESS = "webhook_access"

    # تنظیمات سیستم
    SYSTEM_SETTINGS = "system_settings"
    AUDIT_LOGS = "audit_logs"


# نقش‌ها و مجوزهای پیش‌فرض
ROLE_PERMISSIONS = {
    UserRole.SUPER_ADMIN: [
        Permission.MANAGE_TENANT,
        Permission.VIEW_TENANT_SETTINGS,
        Permission.UPDATE_TENANT_SETTINGS,
        Permission.MANAGE_USERS,
        Permission.INVITE_USERS,
        Permission.REMOVE_USERS,
        Permission.UPLOAD_DOCUMENTS,
        Permission.DELETE_DOCUMENTS,
        Permission.VIEW_DOCUMENTS,
        Permission.ASK_QUESTIONS,
        Permission.VIEW_QUERY_HISTORY,
        Permission.VIEW_ANALYTICS,
        Permission.EXPORT_ANALYTICS,
        Permission.API_ACCESS,
        Permission.WEBHOOK_ACCESS,
        Permission.SYSTEM_SETTINGS,
        Permission.AUDIT_LOGS,
    ],
    UserRole.ADMIN: [
        Permission.VIEW_TENANT_SETTINGS,
        Permission.UPDATE_TENANT_SETTINGS,
        Permission.MANAGE_USERS,
        Permission.INVITE_USERS,
        Permission.REMOVE_USERS,
        Permission.UPLOAD_DOCUMENTS,
        Permission.DELETE_DOCUMENTS,
        Permission.VIEW_DOCUMENTS,
        Permission.ASK_QUESTIONS,
        Permission.VIEW_QUERY_HISTORY,
        Permission.VIEW_ANALYTICS,
        Permission.EXPORT_ANALYTICS,
        Permission.API_ACCESS,
        Permission.WEBHOOK_ACCESS,
        Permission.AUDIT_LOGS,
    ],
    UserRole.MANAGER: [
        Permission.VIEW_TENANT_SETTINGS,
        Permission.MANAGE_USERS,
        Permission.INVITE_USERS,
        Permission.UPLOAD_DOCUMENTS,
        Permission.VIEW_DOCUMENTS,
        Permission.ASK_QUESTIONS,
        Permission.VIEW_QUERY_HISTORY,
        Permission.VIEW_ANALYTICS,
        Permission.API_ACCESS,
    ],
    UserRole.USER: [
        Permission.UPLOAD_DOCUMENTS,
        Permission.VIEW_DOCUMENTS,
        Permission.ASK_QUESTIONS,
        Permission.VIEW_QUERY_HISTORY,
    ],
    UserRole.VIEWER: [
        Permission.VIEW_DOCUMENTS,
        Permission.VIEW_QUERY_HISTORY,
    ],
}


class TenantAuth:
    """سیستم احراز هویت و مجوزدهی tenant"""

    def __init__(self, tenant_manager=None):
        self.tenant_manager = tenant_manager
        self.user_sessions: Dict[str, Dict[str, Any]] = {}
        # Key metadata keyed by key_id. Used only when the tenant manager has no
        # persistent key store. Security (C3): it never holds raw keys.
        self.api_keys: Dict[str, Dict[str, Any]] = {}
        # key_id -> (SHA-256 of the verified raw key, monotonic expiry time).
        # Memory only, never persisted. It avoids running scrypt on every
        # request; revocation and expiry are still checked on every request.
        self._verified_key_cache: Dict[str, Tuple[str, float]] = {}

        logger.info("TenantAuth initialized")

    async def authenticate_user(
        self,
        tenant_id: str,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[bool, Optional[TenantUser], Optional[str]]:
        """احراز هویت کاربر"""
        try:
            # بررسی وجود tenant
            tenant = await self.tenant_manager.get_tenant(tenant_id)
            if not tenant or tenant.status != TenantStatus.ACTIVE:
                await self._log_auth_attempt(
                    tenant_id,
                    username,
                    "tenant_inactive",
                    False,
                    ip_address,
                    user_agent,
                )
                return False, None, "Tenant is not active"

            # بررسی کاربر
            tenant_users = self.tenant_manager.tenant_users.get(tenant_id, [])
            user = None
            for u in tenant_users:
                if u.username == username and u.is_active:
                    user = u
                    break

            if not user:
                await self._log_auth_attempt(
                    tenant_id, username, "user_not_found", False, ip_address, user_agent
                )
                return False, None, "User not found"

            # بررسی رمز عبور
            if not await self._verify_password(password, user):
                await self._log_auth_attempt(
                    tenant_id,
                    username,
                    "invalid_password",
                    False,
                    ip_address,
                    user_agent,
                )
                return False, None, "Invalid password"

            # ایجاد session
            session_token = await self._create_user_session(
                user, ip_address, user_agent
            )

            # به‌روزرسانی آخرین ورود
            user.last_login = datetime.now()

            await self._log_auth_attempt(
                tenant_id, username, "success", True, ip_address, user_agent
            )

            logger.info(f"User authenticated: {username} in tenant {tenant_id}")
            return True, user, session_token

        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            return False, None, str(e)

    async def authenticate_api_key(
        self,
        api_key: str,
        tenant_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[TenantUser], Optional[str]]:
        """Authenticate an API key.

        Security (C3):
        - The key id in ``rgb_<key_id>_<secret>`` selects one stored record. The
          full key is then verified against its salted scrypt hash in constant
          time.
        - The stored hash is never accepted as a credential, and there is no
          lookup by the raw presented value.
        - Legacy keys stored as unsalted SHA-256 digests are rejected with
          ``LEGACY_API_KEY_ERROR``; they must be re-issued (see SECURITY.md).
        - Revocation and expiry are read from storage on every call, so a key
          revoked by another process stops working at once.
        """
        ok, user, _record, error = await self._resolve_api_key(api_key, tenant_id)
        return ok, user, error

    def _load_api_key_record(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Load key metadata by key id: persistent storage first, else memory."""
        manager = self.tenant_manager
        if manager is not None and hasattr(manager, "get_api_key_by_id"):
            key_obj = manager.get_api_key_by_id(key_id)
            if key_obj is None:
                return None
            return {
                "key_id": key_obj.key_id,
                "tenant_id": key_obj.tenant_id,
                "user_id": key_obj.user_id,
                "name": key_obj.name,
                "key_hash": key_obj.key_hash,
                "permissions": list(key_obj.permissions or []),
                "expires_at": key_obj.expires_at,
                "is_active": bool(key_obj.is_active),
                "persistent": True,
            }
        info = self.api_keys.get(key_id)
        if info is None:
            return None
        return {
            "key_id": key_id,
            "tenant_id": info.get("tenant_id"),
            "user_id": info.get("user_id"),
            "name": info.get("name", "api_user"),
            "key_hash": info.get("key_hash"),
            "permissions": list(info.get("permissions") or []),
            "expires_at": info.get("expires_at"),
            "is_active": bool(info.get("is_active", True)),
            "persistent": False,
        }

    def _is_legacy_api_key(self, raw_key: str) -> bool:
        """Return True if ``raw_key`` is an active legacy SHA-256 key.

        Used only to return a clear migration error. It never authenticates.
        """
        manager = self.tenant_manager
        if manager is None or not hasattr(manager, "get_api_key_by_hash"):
            return False
        try:
            return manager.get_api_key_by_hash(legacy_sha256_digest(raw_key)) is not None
        except Exception:
            return False

    async def _verify_key_secret(
        self, key_id: str, raw_key: str, stored_hash: str
    ) -> bool:
        """Verify a raw key against its scrypt hash, with a short-lived cache."""
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        now = time.monotonic()
        cached = self._verified_key_cache.get(key_id)
        if (
            cached is not None
            and cached[1] > now
            and hmac.compare_digest(cached[0], digest)
        ):
            return True
        verified = await asyncio.to_thread(verify_api_key_secret, raw_key, stored_hash)
        if verified:
            if len(self._verified_key_cache) >= VERIFIED_KEY_CACHE_MAX_ENTRIES:
                self._verified_key_cache.clear()
            self._verified_key_cache[key_id] = (
                digest,
                now + VERIFIED_KEY_CACHE_TTL_SECONDS,
            )
        return verified

    async def _resolve_api_key(
        self,
        api_key: str,
        tenant_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[TenantUser], Optional[Dict[str, Any]], Optional[str]]:
        """Resolve an API key to ``(ok, user, key_record, error)``."""
        try:
            if not api_key or not isinstance(api_key, str):
                return False, None, None, "Invalid API key"

            raw_key = api_key.strip()
            parsed = parse_api_key(raw_key)
            if parsed is None:
                if self._is_legacy_api_key(raw_key):
                    logger.warning(
                        "Rejected a legacy SHA-256 API key; it must be re-issued"
                    )
                    return False, None, None, LEGACY_API_KEY_ERROR
                return False, None, None, "Invalid API key"

            record = self._load_api_key_record(parsed.key_id)
            if record is None:
                return False, None, None, "Invalid API key"

            stored_hash = record.get("key_hash")
            if not is_scrypt_hash(stored_hash):
                # The stored record still uses the legacy scheme.
                return False, None, None, LEGACY_API_KEY_ERROR

            # Verify the secret before revealing anything about the key.
            if not await self._verify_key_secret(parsed.key_id, raw_key, stored_hash):
                return False, None, None, "Invalid API key"

            if not record.get("is_active", False):
                self._verified_key_cache.pop(parsed.key_id, None)
                return False, None, None, "API key has been revoked"

            expires_at = record.get("expires_at")
            if expires_at and datetime.now() > expires_at:
                return False, None, None, "API key expired"

            actual_tenant_id = record.get("tenant_id")
            if tenant_id and actual_tenant_id != tenant_id:
                return False, None, None, "API key not valid for this tenant"

            if self.tenant_manager and hasattr(self.tenant_manager, "get_tenant"):
                t_cfg = await self.tenant_manager.get_tenant(actual_tenant_id)
                if not t_cfg:
                    return False, None, None, "Tenant does not exist"

            key_permissions = list(record.get("permissions") or [])
            tenant_users = (
                self.tenant_manager.tenant_users.get(actual_tenant_id, [])
                if self.tenant_manager
                else []
            )
            user = next(
                (
                    u
                    for u in tenant_users
                    if u.user_id == record.get("user_id") and u.is_active
                ),
                None,
            )
            if not user:
                key_name = record.get("name") or "api"
                user = TenantUser(
                    user_id=record.get("user_id") or f"usr_{parsed.key_id[:8]}",
                    tenant_id=actual_tenant_id,
                    username=f"api_{key_name}",
                    email=f"{key_name}@{actual_tenant_id}.local",
                    role="api_user",
                    permissions=key_permissions,
                    is_active=True,
                )

            if not await self.has_permission(user, Permission.API_ACCESS):
                if Permission.API_ACCESS.value not in key_permissions:
                    return False, None, None, "API access not permitted"

            if record.get("persistent") and hasattr(
                self.tenant_manager, "update_api_key_last_used"
            ):
                self.tenant_manager.update_api_key_last_used(record["key_id"])

            logger.info(f"API key authenticated for tenant {actual_tenant_id}")
            return True, user, record, None

        except Exception as e:
            logger.error(f"Error authenticating API key: {e}")
            return False, None, None, "Authentication service error"

    async def create_user(
        self,
        tenant_id: str,
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.USER,
        created_by: Optional[str] = None,
    ) -> Tuple[bool, Optional[TenantUser], Optional[str]]:
        """ایجاد کاربر جدید"""
        try:
            # بررسی وجود tenant
            tenant = await self.tenant_manager.get_tenant(tenant_id)
            if not tenant:
                return False, None, "Tenant not found"

            # بررسی محدودیت کاربران
            current_users = len(self.tenant_manager.tenant_users.get(tenant_id, []))
            if current_users >= tenant.limits.max_users:
                return False, None, "User limit exceeded"

            # بررسی تکراری بودن username
            existing_users = self.tenant_manager.tenant_users.get(tenant_id, [])
            if any(u.username == username for u in existing_users):
                return False, None, "Username already exists"

            # بررسی تکراری بودن email
            if any(u.email == email for u in existing_users):
                return False, None, "Email already exists"

            # ایجاد کاربر
            user_id = str(uuid.uuid4())
            hashed_password = await self._hash_password(password)

            user = TenantUser(
                user_id=user_id,
                tenant_id=tenant_id,
                username=username,
                email=email,
                password_hash=hashed_password,
                role=role.value,
                permissions=ROLE_PERMISSIONS.get(role, []),
                is_active=True,
            )

            # ذخیره کاربر
            if hasattr(self.tenant_manager, "save_user"):
                self.tenant_manager.save_user(user)
            else:
                if tenant_id not in self.tenant_manager.tenant_users:
                    self.tenant_manager.tenant_users[tenant_id] = []
                self.tenant_manager.tenant_users[tenant_id].append(user)

            # ثبت audit log
            await self.tenant_manager._log_audit(
                tenant_id=tenant_id,
                action="user_created",
                resource="user",
                details={
                    "user_id": user_id,
                    "username": username,
                    "role": role.value,
                },
                user_id=created_by,
            )

            logger.info(f"User created: {username} in tenant {tenant_id}")
            return True, user, None

        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return False, None, str(e)

    async def update_user_role(
        self,
        tenant_id: str,
        user_id: str,
        new_role: UserRole,
        updated_by: str,
    ) -> bool:
        """به‌روزرسانی نقش کاربر"""
        try:
            tenant_users = self.tenant_manager.tenant_users.get(tenant_id, [])
            user = None
            for u in tenant_users:
                if u.user_id == user_id:
                    user = u
                    break

            if not user:
                return False

            old_role = user.role
            user.role = new_role.value
            user.permissions = ROLE_PERMISSIONS.get(new_role, [])

            # ثبت audit log
            await self.tenant_manager._log_audit(
                tenant_id=tenant_id,
                action="user_role_updated",
                resource="user",
                details={
                    "user_id": user_id,
                    "old_role": old_role,
                    "new_role": new_role.value,
                },
                user_id=updated_by,
            )

            logger.info(
                f"User role updated: {user.username} from {old_role} to {new_role.value}"
            )
            return True

        except Exception as e:
            logger.error(f"Error updating user role: {e}")
            return False

    async def deactivate_user(
        self,
        tenant_id: str,
        user_id: str,
        deactivated_by: str,
    ) -> bool:
        """غیرفعال کردن کاربر"""
        try:
            tenant_users = self.tenant_manager.tenant_users.get(tenant_id, [])
            user = None
            for u in tenant_users:
                if u.user_id == user_id:
                    user = u
                    break

            if not user:
                return False

            user.is_active = False

            # حذف session های فعال
            await self._revoke_user_sessions(user_id)

            # ثبت audit log
            await self.tenant_manager._log_audit(
                tenant_id=tenant_id,
                action="user_deactivated",
                resource="user",
                details={"user_id": user_id, "username": user.username},
                user_id=deactivated_by,
            )

            logger.info(f"User deactivated: {user.username} in tenant {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Error deactivating user: {e}")
            return False

    async def has_permission(self, user: TenantUser, permission: Permission) -> bool:
        """بررسی مجوز کاربر"""
        try:
            return permission.value in user.permissions
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False

    async def check_resource_access(
        self,
        user: TenantUser,
        resource: str,
        action: str,
    ) -> bool:
        """بررسی دسترسی به منبع"""
        try:
            # نقش‌های مختلف دسترسی‌های مختلف دارند
            if user.role == UserRole.SUPER_ADMIN.value:
                return True

            # بررسی مجوزهای خاص
            if action == "read":
                return await self.has_permission(user, Permission.VIEW_DOCUMENTS)
            elif action == "write":
                return await self.has_permission(user, Permission.UPLOAD_DOCUMENTS)
            elif action == "delete":
                return await self.has_permission(user, Permission.DELETE_DOCUMENTS)
            elif action == "query":
                return await self.has_permission(user, Permission.ASK_QUESTIONS)

            return False

        except Exception as e:
            logger.error(f"Error checking resource access: {e}")
            return False

    async def create_api_key(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        name: str = "default",
        expires_days: int = 365,
        permissions: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Create an API key and store only its salted scrypt hash.

        Security (C3): the raw key ``rgb_<key_id>_<secret>`` is returned once. It
        is never stored, logged or kept in memory.
        Security (C4): a key created without ``user_id`` is never bound to a
        system_admin user, and key permissions never grant system_admin rights.
        """
        try:
            # 1. The tenant must exist.
            if self.tenant_manager and hasattr(self.tenant_manager, "get_tenant"):
                tenant = await self.tenant_manager.get_tenant(tenant_id)
                if not tenant:
                    return False, None, "Tenant not found"

            # 2. Resolve the user that owns the key.
            tenant_users = (
                self.tenant_manager.tenant_users.get(tenant_id, [])
                if self.tenant_manager
                else []
            )
            user = None
            if user_id:
                for u in tenant_users:
                    if u.user_id == user_id and u.is_active:
                        user = u
                        break
                if not user:
                    return False, None, "User not found"
            else:
                user = next(
                    (
                        u
                        for u in tenant_users
                        if u.is_active
                        and authorization_level_for_role(u.role)
                        is not AuthorizationLevel.SYSTEM_ADMIN
                    ),
                    None,
                )
                if not user:
                    user_id = f"usr_{uuid.uuid4().hex[:8]}"
                    user = TenantUser(
                        user_id=user_id,
                        tenant_id=tenant_id,
                        username=f"api_{name}",
                        email=f"{name}@{tenant_id}.local",
                        role=UserRole.ADMIN if not tenant_users else UserRole.USER,
                        permissions=permissions
                        or [
                            Permission.API_ACCESS.value,
                            Permission.VIEW_DOCUMENTS.value,
                            Permission.UPLOAD_DOCUMENTS.value,
                            Permission.ASK_QUESTIONS.value,
                        ],
                        is_active=True,
                    )
                    if self.tenant_manager and hasattr(self.tenant_manager, "save_user"):
                        self.tenant_manager.save_user(user)
                else:
                    user_id = user.user_id

            # 3. The key must allow API access.
            if not await self.has_permission(user, Permission.API_ACCESS):
                if Permission.API_ACCESS.value not in (
                    permissions or user.permissions or []
                ):
                    return False, None, "API access not permitted"

            # 4. Generate the key and store only its scrypt hash.
            key_id, raw_key = generate_api_key()
            key_hash = await asyncio.to_thread(hash_api_key_secret, raw_key)
            key_prefix = raw_key[:12]
            expires_at = datetime.now() + timedelta(days=expires_days)

            key_permissions = list(permissions or user.permissions or [])
            if Permission.API_ACCESS.value not in key_permissions:
                key_permissions.append(Permission.API_ACCESS.value)

            key_obj = TenantApiKey(
                key_id=key_id,
                tenant_id=tenant_id,
                user_id=user_id,
                name=name,
                key_hash=key_hash,
                key_prefix=key_prefix,
                permissions=key_permissions,
                created_at=datetime.now(),
                expires_at=expires_at,
                is_active=True,
            )

            persisted = False
            if self.tenant_manager and hasattr(self.tenant_manager, "save_api_key"):
                self.tenant_manager.save_api_key(key_obj)
                persisted = True

            if not persisted:
                # No persistent store: keep metadata (never the raw key) in memory.
                self.api_keys[key_id] = {
                    "key_id": key_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "name": name,
                    "key_hash": key_hash,
                    "key_prefix": key_prefix,
                    "created_at": key_obj.created_at,
                    "expires_at": expires_at,
                    "permissions": key_permissions,
                    "is_active": True,
                    "last_used": None,
                }

            # The key was just hashed; skip a second scrypt run on first use.
            self._verified_key_cache[key_id] = (
                hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
                time.monotonic() + VERIFIED_KEY_CACHE_TTL_SECONDS,
            )

            if self.tenant_manager and hasattr(self.tenant_manager, "_log_audit"):
                await self.tenant_manager._log_audit(
                    tenant_id=tenant_id,
                    action="api_key_created",
                    resource="api_key",
                    details={
                        "name": name,
                        "key_id": key_id,
                        "expires_at": expires_at.isoformat(),
                    },
                    user_id=user_id,
                )

            logger.info(f"API key created for user {user.username} in tenant {tenant_id}")
            return True, raw_key, None

        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            return False, None, str(e)

    async def revoke_api_key(
        self,
        tenant_id: str,
        api_key_or_id: str,
        revoked_by: Optional[str] = None,
    ) -> bool:
        """Revoke an API key immediately, given the raw key or its key id.

        Security (C3): the key id is parsed from a current-format raw key. A
        legacy raw key (``rgb_<token>``) is found by its SHA-256 digest only so
        that it can be revoked. Revocation is always scoped to ``tenant_id``.
        """
        try:
            identifier = (api_key_or_id or "").strip()
            if not identifier:
                return False
            parsed = parse_api_key(identifier)
            key_id = parsed.key_id if parsed else identifier
            key_name = "Unknown"
            effective_revoked_by = revoked_by or "system"
            revoked_in_db = False

            manager = self.tenant_manager
            if manager is not None and hasattr(manager, "revoke_api_key"):
                key_obj = None
                if hasattr(manager, "get_api_key_by_id"):
                    key_obj = manager.get_api_key_by_id(key_id)
                if (
                    key_obj is None
                    and parsed is None
                    and hasattr(manager, "get_api_key_by_hash")
                ):
                    key_obj = manager.get_api_key_by_hash(legacy_sha256_digest(identifier))
                if key_obj is not None:
                    key_id = key_obj.key_id
                    key_name = key_obj.name
                revoked_in_db = bool(manager.revoke_api_key(key_id, tenant_id=tenant_id))

            revoked_in_mem = False
            info = self.api_keys.get(key_id)
            if info is not None and info.get("tenant_id") == tenant_id:
                key_name = info.get("name", key_name)
                del self.api_keys[key_id]
                revoked_in_mem = True

            self._verified_key_cache.pop(key_id, None)

            if not revoked_in_db and not revoked_in_mem:
                return False

            if manager is not None and hasattr(manager, "_log_audit"):
                await manager._log_audit(
                    tenant_id=tenant_id,
                    action="api_key_revoked",
                    resource="api_key",
                    details={"api_key_name": key_name, "key_id": key_id},
                    user_id=effective_revoked_by,
                )

            logger.info(f"API key revoked in tenant {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Error revoking API key: {e}")
            return False

    async def list_api_keys(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List a tenant's API keys without secrets or hashes.

        Each entry has ``hash_scheme`` (``scrypt`` or ``legacy-sha256``) so that
        operators can find keys that must be re-issued (see SECURITY.md).
        """

        def _iso(value: Any) -> Optional[str]:
            if value is None:
                return None
            return value.isoformat() if hasattr(value, "isoformat") else str(value)

        try:
            if self.tenant_manager and hasattr(self.tenant_manager, "list_api_keys"):
                keys = self.tenant_manager.list_api_keys(tenant_id)
                return [
                    {
                        "key_id": k.key_id,
                        "tenant_id": k.tenant_id,
                        "user_id": k.user_id,
                        "name": k.name,
                        "key_prefix": k.key_prefix,
                        "permissions": k.permissions,
                        "created_at": _iso(k.created_at),
                        "expires_at": _iso(k.expires_at),
                        "last_used_at": _iso(k.last_used_at),
                        "is_active": k.is_active,
                        "hash_scheme": describe_hash_scheme(k.key_hash),
                    }
                    for k in keys
                ]

            results = []
            for key_id, info in self.api_keys.items():
                if info.get("tenant_id") == tenant_id:
                    results.append(
                        {
                            "key_id": key_id,
                            "tenant_id": tenant_id,
                            "user_id": info.get("user_id", ""),
                            "name": info.get("name", ""),
                            "key_prefix": info.get("key_prefix", ""),
                            "permissions": info.get("permissions", []),
                            "created_at": _iso(info.get("created_at")),
                            "expires_at": _iso(info.get("expires_at")),
                            "last_used_at": _iso(info.get("last_used")),
                            "is_active": bool(info.get("is_active", True)),
                            "hash_scheme": describe_hash_scheme(info.get("key_hash")),
                        }
                    )
            return results
        except Exception as e:
            logger.error(f"Error listing API keys for tenant {tenant_id}: {e}")
            return []

    async def authenticate_principal(
        self,
        credential: str,
        tenant_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[AuthenticatedPrincipal], Optional[str]]:
        """Authenticate a session token or an API key and return the principal.

        Security (C4): ``is_super_admin`` (system_admin) comes from the user's
        role only. Key permissions such as ``manage_tenant`` never grant
        cross-tenant access.
        """
        try:
            if not credential or not isinstance(credential, str) or not credential.strip():
                return False, None, "Missing authentication credential"

            token = credential.strip()

            # 1. A valid user session token
            is_valid_session, session_user = await self.validate_session(token)
            if is_valid_session and session_user:
                if tenant_id and session_user.tenant_id != tenant_id:
                    return False, None, "Session token not valid for requested tenant"

                principal = AuthenticatedPrincipal(
                    principal_id=session_user.user_id,
                    identity_type="user_session",
                    tenant_id=session_user.tenant_id,
                    username=session_user.username,
                    role=session_user.role,
                    permissions=session_user.permissions,
                    is_super_admin=authorization_level_for_role(session_user.role)
                    is AuthorizationLevel.SYSTEM_ADMIN,
                )
                return True, principal, None

            # 2. An API key
            auth_ok, api_user, record, err_msg = await self._resolve_api_key(
                token, tenant_id=tenant_id
            )
            if auth_ok and api_user and record:
                permissions = list(record.get("permissions") or []) or list(
                    api_user.permissions or []
                )
                principal = AuthenticatedPrincipal(
                    principal_id=record["key_id"],
                    identity_type="api_key",
                    tenant_id=api_user.tenant_id,
                    username=api_user.username,
                    role=api_user.role,
                    permissions=permissions,
                    is_super_admin=authorization_level_for_role(api_user.role)
                    is AuthorizationLevel.SYSTEM_ADMIN,
                )
                return True, principal, None

            return False, None, err_msg or "Invalid authentication credential"

        except Exception as e:
            logger.error(f"Error authenticating principal: {e}")
            return False, None, "Authentication service error"

    async def validate_session(
        self, session_token: str
    ) -> Tuple[bool, Optional[TenantUser]]:
        """اعتبارسنجی session"""
        try:
            if session_token not in self.user_sessions:
                return False, None

            session_info = self.user_sessions[session_token]

            # بررسی انقضا
            if (
                session_info.get("expires_at")
                and datetime.now() > session_info["expires_at"]
            ):
                del self.user_sessions[session_token]
                return False, None

            # دریافت کاربر
            tenant_id = session_info["tenant_id"]
            tenant_users = self.tenant_manager.tenant_users.get(tenant_id, [])
            user = None
            for u in tenant_users:
                if u.user_id == session_info["user_id"] and u.is_active:
                    user = u
                    break

            if not user:
                del self.user_sessions[session_token]
                return False, None

            # به‌روزرسانی آخرین استفاده
            session_info["last_used"] = datetime.now()

            return True, user

        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return False, None

    async def logout_user(self, session_token: str) -> bool:
        """خروج کاربر"""
        try:
            if session_token in self.user_sessions:
                del self.user_sessions[session_token]
                logger.info("User logged out")
                return True
            return False

        except Exception as e:
            logger.error(f"Error logging out user: {e}")
            return False

    async def _hash_password(self, password: str) -> str:
        """هش کردن رمز عبور"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
        )
        return f"{salt}:{password_hash.hex()}"

    async def _verify_password(self, password: str, user: TenantUser) -> bool:
        """Verify a user password with constant-time comparison.

        Security: a user without a stored password hash (for example a user that
        was created automatically for an API key) can never log in with a
        password. The previous code accepted the fixed password "password123" for
        such users.
        """
        try:
            stored = getattr(user, "password_hash", None)
            if not stored or ":" not in stored:
                return False

            salt, stored_hash = stored.split(":", 1)
            candidate = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
            ).hex()
            return hmac.compare_digest(candidate, stored_hash)

        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False

    async def _create_user_session(
        self,
        user: TenantUser,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """ایجاد session کاربر"""
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=24)

        self.user_sessions[session_token] = {
            "tenant_id": user.tenant_id,
            "user_id": user.user_id,
            "created_at": datetime.now(),
            "expires_at": expires_at,
            "last_used": datetime.now(),
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        return session_token

    async def _revoke_user_sessions(self, user_id: str) -> None:
        """لغو تمام session های کاربر"""
        sessions_to_remove = []
        for session_token, session_info in self.user_sessions.items():
            if session_info["user_id"] == user_id:
                sessions_to_remove.append(session_token)

        for session_token in sessions_to_remove:
            del self.user_sessions[session_token]

    async def _log_auth_attempt(
        self,
        tenant_id: str,
        username: str,
        result: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """ثبت تلاش احراز هویت"""
        await self.tenant_manager._log_audit(
            tenant_id=tenant_id,
            action="auth_attempt",
            resource="authentication",
            details={
                "username": username,
                "result": result,
                "ip_address": ip_address,
                "user_agent": user_agent,
            },
            success=success,
        )

    async def cleanup_expired_sessions(self) -> int:
        """پاکسازی session های منقضی شده"""
        try:
            expired_count = 0
            current_time = datetime.now()

            sessions_to_remove = []
            for session_token, session_info in self.user_sessions.items():
                if (
                    session_info.get("expires_at")
                    and current_time > session_info["expires_at"]
                ):
                    sessions_to_remove.append(session_token)

            for session_token in sessions_to_remove:
                del self.user_sessions[session_token]
                expired_count += 1

            logger.info(f"Cleaned up {expired_count} expired sessions")
            return expired_count

        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0

    async def cleanup_expired_api_keys(self) -> int:
        """پاکسازی API key های منقضی شده"""
        try:
            expired_count = 0
            current_time = datetime.now()

            keys_to_remove = []
            for api_key, key_info in self.api_keys.items():
                if key_info.get("expires_at") and current_time > key_info["expires_at"]:
                    keys_to_remove.append(api_key)

            for api_key in keys_to_remove:
                del self.api_keys[api_key]
                expired_count += 1

            logger.info(f"Cleaned up {expired_count} expired API keys")
            return expired_count

        except Exception as e:
            logger.error(f"Error cleaning up expired API keys: {e}")
            return 0
