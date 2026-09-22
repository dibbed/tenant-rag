"""Tenant-specific analytics and reporting system."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from ..outputs.logger import logger
from .models import (
    TenantConfig,
    TenantTier,
)


class TenantAnalytics:
    """سیستم تحلیل و گزارش‌دهی tenant"""

    def __init__(self, tenant_manager=None):
        self.tenant_manager = tenant_manager
        self.analytics_cache: Dict[str, Dict[str, Any]] = {}

        logger.info("TenantAnalytics initialized")

    async def get_tenant_dashboard(self, tenant_id: str) -> Dict[str, Any]:
        """دریافت داشبورد tenant"""
        try:
            tenant = await self.tenant_manager.get_tenant(tenant_id)
            if not tenant:
                return {"error": "Tenant not found"}

            # دریافت آمار استفاده امروز
            today_usage = await self._get_daily_usage(tenant_id, datetime.now().date())

            # دریافت آمار استفاده هفته
            week_usage = await self._get_period_usage(tenant_id, 7)

            # دریافت آمار استفاده ماه
            month_usage = await self._get_period_usage(tenant_id, 30)

            # محاسبه آمار عملکرد
            performance_metrics = await self._calculate_performance_metrics(
                tenant_id, 7
            )

            # دریافت آخرین فعالیت‌ها
            recent_activities = await self._get_recent_activities(tenant_id, 10)

            # محاسبه هزینه‌ها
            cost_analysis = await self._calculate_cost_analysis(tenant_id, 30)

            dashboard = {
                "tenant_info": {
                    "tenant_id": tenant_id,
                    "name": tenant.name,
                    "tier": tenant.tier,
                    "status": tenant.status,
                    "created_at": tenant.created_at,
                    "expires_at": tenant.expires_at,
                },
                "usage_summary": {
                    "today": today_usage,
                    "this_week": week_usage,
                    "this_month": month_usage,
                },
                "performance_metrics": performance_metrics,
                "recent_activities": recent_activities,
                "cost_analysis": cost_analysis,
                "limits": asdict(tenant.limits),
                "features": asdict(tenant.features),
                "usage_percentages": await self._calculate_usage_percentages(
                    tenant, month_usage
                ),
            }

            return dashboard

        except Exception as e:
            logger.error(f"Error getting tenant dashboard: {e}")
            return {"error": str(e)}

    async def get_usage_trends(
        self,
        tenant_id: str,
        days: int = 30,
        metric: str = "queries",
    ) -> Dict[str, Any]:
        """دریافت روند استفاده"""
        try:
            tenant = await self.tenant_manager.get_tenant(tenant_id)
            if not tenant:
                return {"error": "Tenant not found"}

            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            # دریافت آمار روزانه
            daily_data = []
            current_date = start_date

            while current_date <= end_date:
                daily_usage = await self._get_daily_usage(tenant_id, current_date)

                if metric == "queries":
                    value = daily_usage.get("queries_count", 0)
                elif metric == "documents":
                    value = daily_usage.get("documents_count", 0)
                elif metric == "storage":
                    value = daily_usage.get("storage_used_gb", 0)
                elif metric == "api_calls":
                    value = daily_usage.get("api_calls", 0)
                elif metric == "cost":
                    value = daily_usage.get("cost_usd", 0)
                else:
                    value = 0

                daily_data.append(
                    {
                        "date": current_date.isoformat(),
                        "value": value,
                    }
                )

                current_date += timedelta(days=1)

            # محاسبه آمار کلی
            total_value = sum(item["value"] for item in daily_data)
            avg_value = total_value / len(daily_data) if daily_data else 0
            max_value = max(item["value"] for item in daily_data) if daily_data else 0

            trends = {
                "metric": metric,
                "period_days": days,
                "daily_data": daily_data,
                "summary": {
                    "total": total_value,
                    "average": round(avg_value, 2),
                    "maximum": max_value,
                    "trend": await self._calculate_trend(daily_data),
                },
            }

            return trends

        except Exception as e:
            logger.error(f"Error getting usage trends: {e}")
            return {"error": str(e)}

    async def get_user_activity_report(
        self,
        tenant_id: str,
        days: int = 7,
    ) -> Dict[str, Any]:
        """گزارش فعالیت کاربران"""
        try:
            tenant = await self.tenant_manager.get_tenant(tenant_id)
            if not tenant:
                return {"error": "Tenant not found"}

            # دریافت کاربران tenant
            tenant_users = self.tenant_manager.tenant_users.get(tenant_id, [])

            # دریافت audit logs
            audit_logs = self.tenant_manager.tenant_audit_logs.get(tenant_id, [])
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            filtered_logs = [
                log for log in audit_logs if start_date <= log.timestamp <= end_date
            ]

            # تحلیل فعالیت کاربران
            user_activities = {}
            for log in filtered_logs:
                if log.user_id:
                    if log.user_id not in user_activities:
                        user_activities[log.user_id] = {
                            "actions": 0,
                            "successful_actions": 0,
                            "failed_actions": 0,
                            "last_activity": log.timestamp,
                            "actions_list": [],
                        }

                    user_activities[log.user_id]["actions"] += 1
                    if log.success:
                        user_activities[log.user_id]["successful_actions"] += 1
                    else:
                        user_activities[log.user_id]["failed_actions"] += 1

                    if log.timestamp > user_activities[log.user_id]["last_activity"]:
                        user_activities[log.user_id]["last_activity"] = log.timestamp

                    user_activities[log.user_id]["actions_list"].append(
                        {
                            "action": log.action,
                            "resource": log.resource,
                            "timestamp": log.timestamp.isoformat(),
                            "success": log.success,
                        }
                    )

            # اضافه کردن اطلاعات کاربر
            user_reports = []
            for user in tenant_users:
                user_id = user.user_id
                activity = user_activities.get(
                    user_id,
                    {
                        "actions": 0,
                        "successful_actions": 0,
                        "failed_actions": 0,
                        "last_activity": None,
                        "actions_list": [],
                    },
                )

                user_reports.append(
                    {
                        "user_id": user_id,
                        "username": user.username,
                        "email": user.email,
                        "role": user.role,
                        "is_active": user.is_active,
                        "created_at": user.created_at.isoformat(),
                        "last_login": user.last_login.isoformat()
                        if user.last_login
                        else None,
                        "activity": activity,
                    }
                )

            # مرتب‌سازی بر اساس تعداد فعالیت
            user_reports.sort(key=lambda x: x["activity"]["actions"], reverse=True)

            report = {
                "tenant_id": tenant_id,
                "period_days": days,
                "total_users": len(tenant_users),
                "active_users": len([u for u in tenant_users if u.is_active]),
                "total_activities": len(filtered_logs),
                "user_reports": user_reports,
                "summary": {
                    "most_active_user": user_reports[0] if user_reports else None,
                    "total_actions": sum(
                        ua["actions"] for ua in user_activities.values()
                    ),
                    "success_rate": await self._calculate_success_rate(user_activities),
                },
            }

            return report

        except Exception as e:
            logger.error(f"Error getting user activity report: {e}")
            return {"error": str(e)}

    async def get_billing_report(
        self,
        tenant_id: str,
        months: int = 12,
    ) -> Dict[str, Any]:
        """گزارش صورتحساب"""
        try:
            tenant = await self.tenant_manager.get_tenant(tenant_id)
            if not tenant:
                return {"error": "Tenant not found"}

            # محاسبه هزینه‌های ماهانه
            monthly_costs = []
            current_date = datetime.now()

            for i in range(months):
                month_start = current_date.replace(day=1) - timedelta(days=30 * i)

                # دریافت آمار استفاده ماه
                month_usage = await self._get_period_usage(
                    tenant_id, 30, month_start.date()
                )

                # محاسبه هزینه
                cost = await self._calculate_monthly_cost(tenant, month_usage)

                monthly_costs.append(
                    {
                        "month": month_start.strftime("%Y-%m"),
                        "cost_usd": cost,
                        "usage": month_usage,
                    }
                )

            # محاسبه آمار کلی
            total_cost = sum(mc["cost_usd"] for mc in monthly_costs)
            avg_cost = total_cost / len(monthly_costs) if monthly_costs else 0
            max_cost = (
                max(mc["cost_usd"] for mc in monthly_costs) if monthly_costs else 0
            )

            billing_report = {
                "tenant_id": tenant_id,
                "tenant_name": tenant.name,
                "tier": tenant.tier,
                "plan": tenant.plan,
                "period_months": months,
                "monthly_costs": monthly_costs,
                "summary": {
                    "total_cost_usd": round(total_cost, 2),
                    "average_monthly_cost": round(avg_cost, 2),
                    "highest_monthly_cost": round(max_cost, 2),
                    "cost_trend": await self._calculate_cost_trend(monthly_costs),
                },
                "tier_comparison": await self._compare_tier_costs(tenant.tier),
            }

            return billing_report

        except Exception as e:
            logger.error(f"Error getting billing report: {e}")
            return {"error": str(e)}

    async def get_security_report(
        self,
        tenant_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """گزارش امنیتی"""
        try:
            tenant = await self.tenant_manager.get_tenant(tenant_id)
            if not tenant:
                return {"error": "Tenant not found"}

            # دریافت audit logs
            audit_logs = self.tenant_manager.tenant_audit_logs.get(tenant_id, [])
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            filtered_logs = [
                log for log in audit_logs if start_date <= log.timestamp <= end_date
            ]

            # تحلیل امنیتی
            security_events = []
            failed_logins = 0
            suspicious_activities = 0

            for log in filtered_logs:
                if log.action == "auth_attempt" and not log.success:
                    failed_logins += 1
                    security_events.append(
                        {
                            "type": "failed_login",
                            "timestamp": log.timestamp.isoformat(),
                            "details": log.details,
                            "ip_address": log.details.get("ip_address"),
                        }
                    )

                elif log.action in ["limit_exceeded", "unauthorized_access"]:
                    suspicious_activities += 1
                    security_events.append(
                        {
                            "type": "suspicious_activity",
                            "timestamp": log.timestamp.isoformat(),
                            "details": log.details,
                            "action": log.action,
                        }
                    )

            # محاسبه آمار امنیتی
            total_events = len(security_events)
            risk_score = await self._calculate_security_risk_score(
                failed_logins, suspicious_activities, total_events
            )

            security_report = {
                "tenant_id": tenant_id,
                "period_days": days,
                "security_events": security_events,
                "statistics": {
                    "total_events": total_events,
                    "failed_logins": failed_logins,
                    "suspicious_activities": suspicious_activities,
                    "risk_score": risk_score,
                },
                "recommendations": await self._generate_security_recommendations(
                    failed_logins, suspicious_activities, risk_score
                ),
                "tenant_security_settings": {
                    "encryption_enabled": tenant.encryption_enabled,
                    "data_isolation": tenant.data_isolation,
                    "audit_logging": tenant.audit_logging,
                    "content_filtering": tenant.content_filtering,
                },
            }

            return security_report

        except Exception as e:
            logger.error(f"Error getting security report: {e}")
            return {"error": str(e)}

    async def _get_daily_usage(self, tenant_id: str, date) -> Dict[str, Any]:
        """دریافت آمار استفاده روزانه"""
        try:
            usage_records = self.tenant_manager.tenant_usage.get(tenant_id, [])

            for usage in usage_records:
                if usage.date.date() == date:
                    return {
                        "queries_count": usage.queries_count,
                        "documents_count": usage.documents_count,
                        "storage_used_gb": usage.storage_used_gb,
                        "api_calls": usage.api_calls,
                        "avg_response_time": usage.avg_response_time,
                        "error_rate": usage.error_rate,
                        "satisfaction_score": usage.satisfaction_score,
                        "cost_usd": usage.cost_usd,
                    }

            return {
                "queries_count": 0,
                "documents_count": 0,
                "storage_used_gb": 0.0,
                "api_calls": 0,
                "avg_response_time": 0.0,
                "error_rate": 0.0,
                "satisfaction_score": 0.0,
                "cost_usd": 0.0,
            }

        except Exception as e:
            logger.error(f"Error getting daily usage: {e}")
            return {}

    async def _get_period_usage(
        self,
        tenant_id: str,
        days: int,
        start_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """دریافت آمار استفاده برای دوره"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=days)

            usage_records = self.tenant_manager.tenant_usage.get(tenant_id, [])

            filtered_usage = [
                usage
                for usage in usage_records
                if start_date <= usage.date <= datetime.now()
            ]

            if not filtered_usage:
                return {
                    "queries_count": 0,
                    "documents_count": 0,
                    "storage_used_gb": 0.0,
                    "api_calls": 0,
                    "avg_response_time": 0.0,
                    "error_rate": 0.0,
                    "satisfaction_score": 0.0,
                    "cost_usd": 0.0,
                }

            return {
                "queries_count": sum(u.queries_count for u in filtered_usage),
                "documents_count": sum(u.documents_count for u in filtered_usage),
                "storage_used_gb": sum(u.storage_used_gb for u in filtered_usage),
                "api_calls": sum(u.api_calls for u in filtered_usage),
                "avg_response_time": sum(u.avg_response_time for u in filtered_usage)
                / len(filtered_usage),
                "error_rate": sum(u.error_rate for u in filtered_usage)
                / len(filtered_usage),
                "satisfaction_score": sum(u.satisfaction_score for u in filtered_usage)
                / len(filtered_usage),
                "cost_usd": sum(u.cost_usd for u in filtered_usage),
            }

        except Exception as e:
            logger.error(f"Error getting period usage: {e}")
            return {}

    async def _calculate_performance_metrics(
        self,
        tenant_id: str,
        days: int,
    ) -> Dict[str, Any]:
        """محاسبه معیارهای عملکرد"""
        try:
            usage = await self._get_period_usage(tenant_id, days)

            return {
                "avg_response_time": round(usage.get("avg_response_time", 0), 2),
                "error_rate": round(usage.get("error_rate", 0), 2),
                "satisfaction_score": round(usage.get("satisfaction_score", 0), 2),
                "uptime_percentage": 99.9,  # محاسبه واقعی uptime
                "performance_score": await self._calculate_performance_score(usage),
            }

        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {}

    async def _get_recent_activities(
        self,
        tenant_id: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """دریافت آخرین فعالیت‌ها"""
        try:
            audit_logs = self.tenant_manager.tenant_audit_logs.get(tenant_id, [])

            # مرتب‌سازی بر اساس زمان
            sorted_logs = sorted(audit_logs, key=lambda x: x.timestamp, reverse=True)

            activities = []
            for log in sorted_logs[:limit]:
                activities.append(
                    {
                        "action": log.action,
                        "resource": log.resource,
                        "timestamp": log.timestamp.isoformat(),
                        "success": log.success,
                        "user_id": log.user_id,
                        "details": log.details,
                    }
                )

            return activities

        except Exception as e:
            logger.error(f"Error getting recent activities: {e}")
            return []

    async def _calculate_cost_analysis(
        self,
        tenant_id: str,
        days: int,
    ) -> Dict[str, Any]:
        """تحلیل هزینه‌ها"""
        try:
            usage = await self._get_period_usage(tenant_id, days)
            tenant = await self.tenant_manager.get_tenant(tenant_id)

            if not tenant:
                return {}

            # محاسبه هزینه‌های مختلف
            base_cost = await self._get_base_cost(tenant.tier)
            usage_cost = usage.get("cost_usd", 0)
            total_cost = base_cost + usage_cost

            return {
                "base_cost_usd": base_cost,
                "usage_cost_usd": usage_cost,
                "total_cost_usd": total_cost,
                "cost_per_query": usage_cost / max(usage.get("queries_count", 1), 1),
                "cost_per_document": usage_cost
                / max(usage.get("documents_count", 1), 1),
                "cost_per_gb": usage_cost / max(usage.get("storage_used_gb", 1), 1),
            }

        except Exception as e:
            logger.error(f"Error calculating cost analysis: {e}")
            return {}

    async def _calculate_usage_percentages(
        self,
        tenant: TenantConfig,
        usage: Dict[str, Any],
    ) -> Dict[str, float]:
        """محاسبه درصد استفاده از محدودیت‌ها"""
        try:
            limits = tenant.limits

            return {
                "queries_percentage": min(
                    (usage.get("queries_count", 0) / limits.max_queries_per_day) * 100,
                    100,
                ),
                "documents_percentage": min(
                    (usage.get("documents_count", 0) / limits.max_documents) * 100, 100
                ),
                "storage_percentage": min(
                    (usage.get("storage_used_gb", 0) / limits.max_storage_gb) * 100, 100
                ),
                "users_percentage": min(
                    (
                        len(self.tenant_manager.tenant_users.get(tenant.tenant_id, []))
                        / limits.max_users
                    )
                    * 100,
                    100,
                ),
            }

        except Exception as e:
            logger.error(f"Error calculating usage percentages: {e}")
            return {}

    async def _calculate_trend(self, daily_data: List[Dict[str, Any]]) -> str:
        """محاسبه روند"""
        try:
            if len(daily_data) < 2:
                return "stable"

            recent_values = [item["value"] for item in daily_data[-7:]]
            older_values = (
                [item["value"] for item in daily_data[-14:-7]]
                if len(daily_data) >= 14
                else recent_values
            )

            recent_avg = sum(recent_values) / len(recent_values)
            older_avg = sum(older_values) / len(older_values)

            if recent_avg > older_avg * 1.1:
                return "increasing"
            elif recent_avg < older_avg * 0.9:
                return "decreasing"
            else:
                return "stable"

        except Exception as e:
            logger.error(f"Error calculating trend: {e}")
            return "stable"

    async def _calculate_success_rate(self, user_activities: Dict[str, Any]) -> float:
        """محاسبه نرخ موفقیت"""
        try:
            total_actions = sum(ua["actions"] for ua in user_activities.values())
            successful_actions = sum(
                ua["successful_actions"] for ua in user_activities.values()
            )

            if total_actions == 0:
                return 0.0

            return round((successful_actions / total_actions) * 100, 2)

        except Exception as e:
            logger.error(f"Error calculating success rate: {e}")
            return 0.0

    async def _calculate_monthly_cost(
        self,
        tenant: TenantConfig,
        usage: Dict[str, Any],
    ) -> float:
        """محاسبه هزینه ماهانه"""
        try:
            base_cost = await self._get_base_cost(tenant.tier)
            usage_cost = usage.get("cost_usd", 0)
            return round(base_cost + usage_cost, 2)

        except Exception as e:
            logger.error(f"Error calculating monthly cost: {e}")
            return 0.0

    async def _get_base_cost(self, tier: TenantTier) -> float:
        """دریافت هزینه پایه بر اساس tier"""
        base_costs = {
            TenantTier.FREE: 0.0,
            TenantTier.BASIC: 10.0,
            TenantTier.PREMIUM: 50.0,
            TenantTier.ENTERPRISE: 200.0,
        }
        return base_costs.get(tier, 0.0)

    async def _calculate_cost_trend(self, monthly_costs: List[Dict[str, Any]]) -> str:
        """محاسبه روند هزینه"""
        try:
            if len(monthly_costs) < 2:
                return "stable"

            recent_costs = [mc["cost_usd"] for mc in monthly_costs[-3:]]
            older_costs = (
                [mc["cost_usd"] for mc in monthly_costs[-6:-3]]
                if len(monthly_costs) >= 6
                else recent_costs
            )

            recent_avg = sum(recent_costs) / len(recent_costs)
            older_avg = sum(older_costs) / len(older_costs)

            if recent_avg > older_avg * 1.1:
                return "increasing"
            elif recent_avg < older_avg * 0.9:
                return "decreasing"
            else:
                return "stable"

        except Exception as e:
            logger.error(f"Error calculating cost trend: {e}")
            return "stable"

    async def _compare_tier_costs(self, current_tier: TenantTier) -> Dict[str, Any]:
        """مقایسه هزینه‌های tier های مختلف"""
        try:
            tiers = [
                TenantTier.FREE,
                TenantTier.BASIC,
                TenantTier.PREMIUM,
                TenantTier.ENTERPRISE,
            ]
            comparison = {}

            for tier in tiers:
                comparison[tier.value] = {
                    "base_cost": await self._get_base_cost(tier),
                    "is_current": tier == current_tier,
                }

            return comparison

        except Exception as e:
            logger.error(f"Error comparing tier costs: {e}")
            return {}

    async def _calculate_security_risk_score(
        self,
        failed_logins: int,
        suspicious_activities: int,
        total_events: int,
    ) -> int:
        """محاسبه امتیاز ریسک امنیتی"""
        try:
            # امتیاز بر اساس تعداد رویدادهای امنیتی
            risk_score = 0

            if failed_logins > 10:
                risk_score += 30
            elif failed_logins > 5:
                risk_score += 20
            elif failed_logins > 0:
                risk_score += 10

            if suspicious_activities > 5:
                risk_score += 40
            elif suspicious_activities > 2:
                risk_score += 25
            elif suspicious_activities > 0:
                risk_score += 15

            return min(risk_score, 100)

        except Exception as e:
            logger.error(f"Error calculating security risk score: {e}")
            return 0

    async def _generate_security_recommendations(
        self,
        failed_logins: int,
        suspicious_activities: int,
        risk_score: int,
    ) -> List[str]:
        """تولید توصیه‌های امنیتی"""
        try:
            recommendations = []

            if failed_logins > 5:
                recommendations.append("فعال‌سازی احراز هویت دو مرحله‌ای")
                recommendations.append("بررسی و تقویت رمزهای عبور")

            if suspicious_activities > 2:
                recommendations.append("فعال‌سازی نظارت بر فعالیت‌های مشکوک")
                recommendations.append("بررسی دسترسی‌های غیرمجاز")

            if risk_score > 70:
                recommendations.append("بررسی کامل امنیت سیستم")
                recommendations.append("به‌روزرسانی سیاست‌های امنیتی")

            if not recommendations:
                recommendations.append("سیستم امنیتی در وضعیت مطلوب است")

            return recommendations

        except Exception as e:
            logger.error(f"Error generating security recommendations: {e}")
            return ["خطا در تولید توصیه‌های امنیتی"]

    async def _calculate_performance_score(self, usage: Dict[str, Any]) -> float:
        """محاسبه امتیاز عملکرد"""
        try:
            # امتیاز بر اساس معیارهای مختلف
            response_time_score = max(0, 100 - usage.get("avg_response_time", 0) * 10)
            error_rate_score = max(0, 100 - usage.get("error_rate", 0) * 100)
            satisfaction_score = usage.get("satisfaction_score", 0) * 20

            performance_score = (
                response_time_score + error_rate_score + satisfaction_score
            ) / 3
            return round(performance_score, 2)

        except Exception as e:
            logger.error(f"Error calculating performance score: {e}")
            return 0.0
