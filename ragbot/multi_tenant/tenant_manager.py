"""Tenant management system for multi-tenant support."""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import asdict

from ..outputs.logger import logger
from ..rag.store.base import VectorDocument
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


class TenantManager:
    """مدیریت tenant ها و جداسازی داده‌ها"""

    def __init__(self, settings=None):
        self.settings = settings
        self.tenants: Dict[str, TenantConfig] = {}
        self.tenant_users: Dict[str, List[TenantUser]] = {}
        self.tenant_usage: Dict[str, List[TenantUsage]] = {}
        self.tenant_policies: Dict[str, List[TenantPolicy]] = {}
        self.tenant_audit_logs: Dict[str, List[TenantAuditLog]] = {}

        # Cache for tenant isolation
        self._tenant_cache: Dict[str, Any] = {}
        self._isolation_rules: Dict[str, Dict[str, Any]] = {}

        logger.info("TenantManager initialized")

    async def create_tenant(
        self,
        name: str,
        tier: TenantTier = TenantTier.FREE,
        plan: TenantPlan = TenantPlan.TRIAL,
        domain: Optional[str] = None,
        contact_email: Optional[str] = None,
        custom_settings: Optional[Dict[str, Any]] = None,
    ) -> TenantConfig:
        """ایجاد tenant جدید"""
        try:
            tenant_id = str(uuid.uuid4())

            # ایجاد تنظیمات بر اساس tier
            base_config = DEFAULT_TIER_CONFIGS[tier]

            # تنظیمات سفارشی
            custom_settings = custom_settings or {}

            # محاسبه تاریخ انقضا
            expires_at = None
            if plan == TenantPlan.TRIAL:
                expires_at = datetime.now() + timedelta(days=14)
            elif plan == TenantPlan.MONTHLY:
                expires_at = datetime.now() + timedelta(days=30)
            elif plan == TenantPlan.YEARLY:
                expires_at = datetime.now() + timedelta(days=365)

            tenant_config = TenantConfig(
                tenant_id=tenant_id,
                name=name,
                domain=domain,
                tier=tier,
                plan=plan,
                limits=base_config.limits,
                features=base_config.features,
                expires_at=expires_at,
                contact_email=contact_email,
                custom_settings=custom_settings,
            )

            # ذخیره tenant
            self.tenants[tenant_id] = tenant_config
            self.tenant_users[tenant_id] = []
            self.tenant_usage[tenant_id] = []
            self.tenant_policies[tenant_id] = []
            self.tenant_audit_logs[tenant_id] = []

            # ثبت audit log
            await self._log_audit(
                tenant_id=tenant_id,
                action="tenant_created",
                resource="tenant",
                details={"name": name, "tier": tier, "plan": plan},
            )

            logger.info(f"Tenant created: {tenant_id} ({name})")
            return tenant_config

        except Exception as e:
            logger.error(f"Error creating tenant: {e}")
            raise

    async def get_tenant(self, tenant_id: str) -> Optional[TenantConfig]:
        """دریافت تنظیمات tenant"""
        try:
            tenant = self.tenants.get(tenant_id)
            if tenant:
                # بررسی انقضا
                if tenant.expires_at and datetime.now() > tenant.expires_at:
                    await self._suspend_tenant(tenant_id, "expired")
                    return None
            return tenant
        except Exception as e:
            logger.error(f"Error getting tenant {tenant_id}: {e}")
            return None

    async def update_tenant(
        self, tenant_id: str, updates: Dict[str, Any]
    ) -> Optional[TenantConfig]:
        """به‌روزرسانی تنظیمات tenant"""
        try:
            tenant = self.tenants.get(tenant_id)
            if not tenant:
                return None

            # به‌روزرسانی فیلدها
            for key, value in updates.items():
                if hasattr(tenant, key):
                    setattr(tenant, key, value)

            tenant.updated_at = datetime.now()

            # ثبت audit log
            await self._log_audit(
                tenant_id=tenant_id,
                action="tenant_updated",
                resource="tenant",
                details=updates,
            )

            logger.info(f"Tenant updated: {tenant_id}")
            return tenant

        except Exception as e:
            logger.error(f"Error updating tenant {tenant_id}: {e}")
            return None

    async def suspend_tenant(self, tenant_id: str, reason: str = "manual") -> bool:
        """تعلیق tenant"""
        return await self._suspend_tenant(tenant_id, reason)

    async def _suspend_tenant(self, tenant_id: str, reason: str) -> bool:
        """تعلیق داخلی tenant"""
        try:
            tenant = self.tenants.get(tenant_id)
            if not tenant:
                return False

            tenant.status = TenantStatus.SUSPENDED
            tenant.updated_at = datetime.now()

            # ثبت audit log
            await self._log_audit(
                tenant_id=tenant_id,
                action="tenant_suspended",
                resource="tenant",
                details={"reason": reason},
            )

            logger.info(f"Tenant suspended: {tenant_id} (reason: {reason})")
            return True

        except Exception as e:
            logger.error(f"Error suspending tenant {tenant_id}: {e}")
            return False

    async def activate_tenant(self, tenant_id: str) -> bool:
        """فعال‌سازی tenant"""
        try:
            tenant = self.tenants.get(tenant_id)
            if not tenant:
                return False

            tenant.status = TenantStatus.ACTIVE
            tenant.updated_at = datetime.now()

            # ثبت audit log
            await self._log_audit(
                tenant_id=tenant_id,
                action="tenant_activated",
                resource="tenant",
                details={},
            )

            logger.info(f"Tenant activated: {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Error activating tenant {tenant_id}: {e}")
            return False

    async def delete_tenant(self, tenant_id: str) -> bool:
        """حذف tenant"""
        try:
            if tenant_id not in self.tenants:
                return False

            # حذف تمام داده‌های مربوط به tenant
            del self.tenants[tenant_id]
            del self.tenant_users[tenant_id]
            del self.tenant_usage[tenant_id]
            del self.tenant_policies[tenant_id]
            del self.tenant_audit_logs[tenant_id]

            # پاک کردن cache
            if tenant_id in self._tenant_cache:
                del self._tenant_cache[tenant_id]

            logger.info(f"Tenant deleted: {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting tenant {tenant_id}: {e}")
            return False

    async def isolate_data(
        self, tenant_id: str, documents: List[VectorDocument]
    ) -> List[VectorDocument]:
        """جداسازی داده‌ها بر اساس tenant"""
        try:
            tenant = await self.get_tenant(tenant_id)
            if not tenant or tenant.status != TenantStatus.ACTIVE:
                return []

            # اعمال قوانین جداسازی
            isolated_docs = []
            for doc in documents:
                # اضافه کردن tenant_id به metadata
                if not hasattr(doc, "metadata"):
                    doc.metadata = {}

                doc.metadata["tenant_id"] = tenant_id
                doc.metadata["tenant_tier"] = tenant.tier
                doc.metadata["created_at"] = datetime.now().isoformat()

                # اعمال فیلتر محتوا
                if tenant.content_filtering:
                    if await self._apply_content_filter(doc, tenant):
                        isolated_docs.append(doc)
                else:
                    isolated_docs.append(doc)

            logger.debug(
                f"Data isolated for tenant {tenant_id}: {len(isolated_docs)} documents"
            )
            return isolated_docs

        except Exception as e:
            logger.error(f"Error isolating data for tenant {tenant_id}: {e}")
            return []

    async def apply_tenant_policies(
        self, tenant_id: str, query: str
    ) -> Tuple[str, Dict[str, Any]]:
        """اعمال سیاست‌های tenant بر روی query"""
        try:
            tenant = await self.get_tenant(tenant_id)
            if not tenant or tenant.status != TenantStatus.ACTIVE:
                return query, {}

            policies = self.tenant_policies.get(tenant_id, [])
            applied_policies = {}

            # اعمال سیاست‌ها بر اساس اولویت
            sorted_policies = sorted(policies, key=lambda p: p.priority, reverse=True)

            for policy in sorted_policies:
                if not policy.is_active:
                    continue

                # بررسی شرایط
                if await self._check_policy_conditions(policy, query, tenant):
                    # اعمال اقدامات
                    query, policy_result = await self._apply_policy_actions(
                        policy, query, tenant
                    )
                    applied_policies[policy.policy_name] = policy_result

            logger.debug(
                f"Applied {len(applied_policies)} policies for tenant {tenant_id}"
            )
            return query, applied_policies

        except Exception as e:
            logger.error(f"Error applying policies for tenant {tenant_id}: {e}")
            return query, {}

    async def check_tenant_limits(self, tenant_id: str, operation: str) -> bool:
        """بررسی محدودیت‌های tenant"""
        try:
            tenant = await self.get_tenant(tenant_id)
            if not tenant:
                return False

            limits = tenant.limits
            usage = await self._get_tenant_usage(tenant_id)

            # بررسی محدودیت‌ها بر اساس نوع عملیات
            if operation == "query":
                if usage.queries_count >= limits.max_queries_per_day:
                    await self._log_audit(
                        tenant_id=tenant_id,
                        action="limit_exceeded",
                        resource="queries",
                        details={
                            "limit": limits.max_queries_per_day,
                            "usage": usage.queries_count,
                        },
                    )
                    return False

            elif operation == "document":
                if usage.documents_count >= limits.max_documents:
                    await self._log_audit(
                        tenant_id=tenant_id,
                        action="limit_exceeded",
                        resource="documents",
                        details={
                            "limit": limits.max_documents,
                            "usage": usage.documents_count,
                        },
                    )
                    return False

            elif operation == "storage":
                if usage.storage_used_gb >= limits.max_storage_gb:
                    await self._log_audit(
                        tenant_id=tenant_id,
                        action="limit_exceeded",
                        resource="storage",
                        details={
                            "limit": limits.max_storage_gb,
                            "usage": usage.storage_used_gb,
                        },
                    )
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking limits for tenant {tenant_id}: {e}")
            return False

    async def track_tenant_usage(
        self,
        tenant_id: str,
        operation: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """ردیابی استفاده tenant"""
        try:
            tenant = await self.get_tenant(tenant_id)
            if not tenant:
                return

            # دریافت یا ایجاد usage record برای امروز
            today = datetime.now().date()
            usage_records = self.tenant_usage.get(tenant_id, [])

            today_usage = None
            for usage in usage_records:
                if usage.date.date() == today:
                    today_usage = usage
                    break

            if not today_usage:
                today_usage = TenantUsage(
                    tenant_id=tenant_id,
                    date=datetime.now(),
                )
                usage_records.append(today_usage)
                self.tenant_usage[tenant_id] = usage_records

            # به‌روزرسانی آمار
            metadata = metadata or {}

            if operation == "query":
                today_usage.queries_count += 1
                today_usage.avg_response_time = metadata.get("response_time", 0)
                today_usage.error_rate = metadata.get("error_rate", 0)
                today_usage.satisfaction_score = metadata.get("satisfaction", 0)

            elif operation == "document":
                today_usage.documents_count += 1
                today_usage.storage_used_gb += metadata.get("size_gb", 0)

            elif operation == "api_call":
                today_usage.api_calls += 1

            # محاسبه هزینه
            today_usage.cost_usd = await self._calculate_usage_cost(tenant, today_usage)

            logger.debug(f"Usage tracked for tenant {tenant_id}: {operation}")

        except Exception as e:
            logger.error(f"Error tracking usage for tenant {tenant_id}: {e}")

    async def get_tenant_analytics(
        self, tenant_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """دریافت تحلیل‌های tenant"""
        try:
            tenant = await self.get_tenant(tenant_id)
            if not tenant:
                return {"error": "Tenant not found"}

            # دریافت آمار استفاده
            usage_records = self.tenant_usage.get(tenant_id, [])
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            filtered_usage = [
                usage for usage in usage_records if start_date <= usage.date <= end_date
            ]

            # محاسبه آمار
            total_queries = sum(usage.queries_count for usage in filtered_usage)
            total_documents = sum(usage.documents_count for usage in filtered_usage)
            total_storage = sum(usage.storage_used_gb for usage in filtered_usage)
            total_api_calls = sum(usage.api_calls for usage in filtered_usage)
            total_cost = sum(usage.cost_usd for usage in filtered_usage)

            avg_response_time = 0
            avg_error_rate = 0
            avg_satisfaction = 0

            if filtered_usage:
                avg_response_time = sum(
                    usage.avg_response_time for usage in filtered_usage
                ) / len(filtered_usage)
                avg_error_rate = sum(
                    usage.error_rate for usage in filtered_usage
                ) / len(filtered_usage)
                avg_satisfaction = sum(
                    usage.satisfaction_score for usage in filtered_usage
                ) / len(filtered_usage)

            analytics = {
                "tenant_id": tenant_id,
                "tenant_name": tenant.name,
                "tier": tenant.tier,
                "period_days": days,
                "usage_summary": {
                    "total_queries": total_queries,
                    "total_documents": total_documents,
                    "total_storage_gb": total_storage,
                    "total_api_calls": total_api_calls,
                    "total_cost_usd": total_cost,
                },
                "performance_metrics": {
                    "avg_response_time": avg_response_time,
                    "avg_error_rate": avg_error_rate,
                    "avg_satisfaction_score": avg_satisfaction,
                },
                "limits": {
                    "max_queries_per_day": tenant.limits.max_queries_per_day,
                    "max_documents": tenant.limits.max_documents,
                    "max_storage_gb": tenant.limits.max_storage_gb,
                    "max_users": tenant.limits.max_users,
                },
                "usage_percentage": {
                    "queries": (
                        total_queries / (tenant.limits.max_queries_per_day * days)
                    )
                    * 100,
                    "documents": (total_documents / tenant.limits.max_documents) * 100,
                    "storage": (total_storage / tenant.limits.max_storage_gb) * 100,
                },
                "features_enabled": asdict(tenant.features),
            }

            return analytics

        except Exception as e:
            logger.error(f"Error getting analytics for tenant {tenant_id}: {e}")
            return {"error": str(e)}

    async def _apply_content_filter(
        self, doc: VectorDocument, tenant: TenantConfig
    ) -> bool:
        """اعمال فیلتر محتوا"""
        try:
            # بررسی محتوای سند بر اساس سیاست‌های tenant
            content = getattr(doc, "content", "") or getattr(doc, "text", "")

            # فیلترهای ساده
            if tenant.content_filtering:
                # بررسی کلمات ممنوعه
                forbidden_words = tenant.custom_settings.get("forbidden_words", [])
                if any(word.lower() in content.lower() for word in forbidden_words):
                    return False

                # بررسی طول محتوا
                min_length = tenant.custom_settings.get("min_content_length", 10)
                if len(content) < min_length:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error applying content filter: {e}")
            return True

    async def _check_policy_conditions(
        self, policy: TenantPolicy, query: str, tenant: TenantConfig
    ) -> bool:
        """بررسی شرایط سیاست"""
        try:
            for condition in policy.conditions:
                if condition == "time_based":
                    # بررسی زمان‌بندی
                    current_hour = datetime.now().hour
                    allowed_hours = policy.rules.get("allowed_hours", list(range(24)))
                    if current_hour not in allowed_hours:
                        return False

                elif condition == "query_length":
                    # بررسی طول query
                    max_length = policy.rules.get("max_query_length", 1000)
                    if len(query) > max_length:
                        return False

                elif condition == "tier_based":
                    # بررسی tier
                    required_tier = policy.rules.get("required_tier", TenantTier.FREE)
                    if tenant.tier.value < required_tier.value:
                        return False

            return True

        except Exception as e:
            logger.error(f"Error checking policy conditions: {e}")
            return False

    async def _apply_policy_actions(
        self, policy: TenantPolicy, query: str, tenant: TenantConfig
    ) -> Tuple[str, Dict[str, Any]]:
        """اعمال اقدامات سیاست"""
        try:
            result = {"policy": policy.policy_name, "actions_applied": []}

            for action in policy.actions:
                if action == "query_modification":
                    # تغییر query
                    prefix = policy.rules.get("query_prefix", "")
                    suffix = policy.rules.get("query_suffix", "")
                    query = f"{prefix} {query} {suffix}".strip()
                    result["actions_applied"].append("query_modification")

                elif action == "rate_limiting":
                    # محدودیت نرخ
                    result["actions_applied"].append("rate_limiting")

                elif action == "logging":
                    # ثبت لاگ
                    result["actions_applied"].append("logging")

            return query, result

        except Exception as e:
            logger.error(f"Error applying policy actions: {e}")
            return query, {}

    async def _get_tenant_usage(self, tenant_id: str) -> TenantUsage:
        """دریافت آمار استفاده tenant"""
        try:
            usage_records = self.tenant_usage.get(tenant_id, [])
            if not usage_records:
                return TenantUsage(tenant_id=tenant_id, date=datetime.now())

            # بازگشت آخرین record
            return max(usage_records, key=lambda x: x.date)

        except Exception as e:
            logger.error(f"Error getting tenant usage: {e}")
            return TenantUsage(tenant_id=tenant_id, date=datetime.now())

    async def _calculate_usage_cost(
        self, tenant: TenantConfig, usage: TenantUsage
    ) -> float:
        """محاسبه هزینه استفاده"""
        try:
            # هزینه‌های پایه بر اساس tier
            base_costs = {
                TenantTier.FREE: 0.0,
                TenantTier.BASIC: 10.0,
                TenantTier.PREMIUM: 50.0,
                TenantTier.ENTERPRISE: 200.0,
            }

            base_cost = base_costs.get(tenant.tier, 0.0)

            # هزینه‌های اضافی بر اساس استفاده
            query_cost = usage.queries_count * 0.001  # $0.001 per query
            storage_cost = usage.storage_used_gb * 0.1  # $0.1 per GB
            api_cost = usage.api_calls * 0.01  # $0.01 per API call

            total_cost = base_cost + query_cost + storage_cost + api_cost
            return round(total_cost, 2)

        except Exception as e:
            logger.error(f"Error calculating usage cost: {e}")
            return 0.0

    async def _log_audit(
        self,
        tenant_id: str,
        action: str,
        resource: str,
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """ثبت audit log"""
        try:
            audit_log = TenantAuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                resource=resource,
                details=details,
                success=success,
                error_message=error_message,
            )

            if tenant_id not in self.tenant_audit_logs:
                self.tenant_audit_logs[tenant_id] = []

            self.tenant_audit_logs[tenant_id].append(audit_log)

            # نگه داشتن فقط آخرین 1000 log
            if len(self.tenant_audit_logs[tenant_id]) > 1000:
                self.tenant_audit_logs[tenant_id] = self.tenant_audit_logs[tenant_id][
                    -1000:
                ]

        except Exception as e:
            logger.error(f"Error logging audit: {e}")

    async def get_all_tenants(self) -> List[TenantConfig]:
        """دریافت تمام tenant ها"""
        return list(self.tenants.values())

    async def get_tenant_count(self) -> int:
        """تعداد کل tenant ها"""
        return len(self.tenants)

    async def get_active_tenants(self) -> List[TenantConfig]:
        """دریافت tenant های فعال"""
        return [
            tenant
            for tenant in self.tenants.values()
            if tenant.status == TenantStatus.ACTIVE
        ]

    async def cleanup_expired_tenants(self) -> int:
        """پاکسازی tenant های منقضی شده"""
        try:
            expired_count = 0
            current_time = datetime.now()

            for tenant_id, tenant in list(self.tenants.items()):
                if tenant.expires_at and current_time > tenant.expires_at:
                    await self._suspend_tenant(tenant_id, "expired")
                    expired_count += 1

            logger.info(f"Cleaned up {expired_count} expired tenants")
            return expired_count

        except Exception as e:
            logger.error(f"Error cleaning up expired tenants: {e}")
            return 0
