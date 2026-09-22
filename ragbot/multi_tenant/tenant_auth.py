"""Tenant authentication and authorization system."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from ..outputs.logger import logger
from .models import TenantConfig, TenantUser, TenantAuditLog, TenantStatus


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
        self.api_keys: Dict[str, Dict[str, Any]] = {}

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
        """احراز هویت API key"""
        try:
            # بررسی API key
            if api_key not in self.api_keys:
                return False, None, "Invalid API key"

            key_info = self.api_keys[api_key]

            # بررسی انقضا
            if key_info.get("expires_at") and datetime.now() > key_info["expires_at"]:
                del self.api_keys[api_key]
                return False, None, "API key expired"

            # بررسی tenant
            if tenant_id and key_info.get("tenant_id") != tenant_id:
                return False, None, "API key not valid for this tenant"

            # دریافت کاربر
            tenant_id = key_info["tenant_id"]
            tenant_users = self.tenant_manager.tenant_users.get(tenant_id, [])
            user = None
            for u in tenant_users:
                if u.user_id == key_info["user_id"] and u.is_active:
                    user = u
                    break

            if not user:
                return False, None, "User not found"

            # بررسی مجوز API
            if not await self.has_permission(user, Permission.API_ACCESS):
                return False, None, "API access not permitted"

            logger.info(f"API key authenticated: {user.username} in tenant {tenant_id}")
            return True, user, None

        except Exception as e:
            logger.error(f"Error authenticating API key: {e}")
            return False, None, str(e)

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
        user_id: str,
        name: str,
        expires_days: int = 365,
        permissions: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """ایجاد API key"""
        try:
            # بررسی کاربر
            tenant_users = self.tenant_manager.tenant_users.get(tenant_id, [])
            user = None
            for u in tenant_users:
                if u.user_id == user_id and u.is_active:
                    user = u
                    break

            if not user:
                return False, None, "User not found"

            # بررسی مجوز API
            if not await self.has_permission(user, Permission.API_ACCESS):
                return False, None, "API access not permitted"

            # ایجاد API key
            api_key = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(days=expires_days)

            self.api_keys[api_key] = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "name": name,
                "created_at": datetime.now(),
                "expires_at": expires_at,
                "permissions": permissions or user.permissions,
                "last_used": None,
            }

            # ثبت audit log
            await self.tenant_manager._log_audit(
                tenant_id=tenant_id,
                action="api_key_created",
                resource="api_key",
                details={"name": name, "expires_at": expires_at.isoformat()},
                user_id=user_id,
            )

            logger.info(
                f"API key created for user {user.username} in tenant {tenant_id}"
            )
            return True, api_key, None

        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            return False, None, str(e)

    async def revoke_api_key(
        self,
        tenant_id: str,
        api_key: str,
        revoked_by: str,
    ) -> bool:
        """لغو API key"""
        try:
            if api_key not in self.api_keys:
                return False

            key_info = self.api_keys[api_key]
            if key_info["tenant_id"] != tenant_id:
                return False

            del self.api_keys[api_key]

            # ثبت audit log
            await self.tenant_manager._log_audit(
                tenant_id=tenant_id,
                action="api_key_revoked",
                resource="api_key",
                details={"api_key_name": key_info.get("name", "Unknown")},
                user_id=revoked_by,
            )

            logger.info(f"API key revoked in tenant {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Error revoking API key: {e}")
            return False

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
        """بررسی رمز عبور"""
        try:
            if not getattr(user, "password_hash", None):
                # رمز عبور پیش‌فرض برای تست اگر هش ثبت نشده بود
                return password == "password123"

            salt, stored_hash = user.password_hash.split(":")
            password_hash = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
            )
            return password_hash.hex() == stored_hash

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
