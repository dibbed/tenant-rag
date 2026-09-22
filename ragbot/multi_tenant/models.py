"""Multi-tenant data models and schemas."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, ConfigDict, Field
from dataclasses import dataclass


class TenantStatus(str, Enum):
    """وضعیت tenant"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"
    PENDING = "pending"


class TenantTier(str, Enum):
    """سطح دسترسی tenant"""

    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class TenantPlan(str, Enum):
    """پلن tenant"""

    TRIAL = "trial"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


@dataclass
class TenantLimits:
    """محدودیت‌های tenant"""

    max_documents: int = 1000
    max_queries_per_day: int = 1000
    max_storage_gb: float = 1.0
    max_users: int = 5
    max_concurrent_queries: int = 10
    retention_days: int = 30
    api_rate_limit: int = 100  # requests per minute


@dataclass
class TenantFeatures:
    """قابلیت‌های فعال tenant"""

    advanced_analytics: bool = False
    ml_insights: bool = False
    predictive_analytics: bool = False
    custom_embeddings: bool = False
    api_access: bool = False
    webhook_support: bool = False
    priority_support: bool = False
    custom_branding: bool = False


class TenantConfig(BaseModel):
    """تنظیمات tenant"""

    # شناسایی
    tenant_id: str = Field(..., description="شناسه یکتای tenant")
    name: str = Field(..., description="نام tenant")
    domain: Optional[str] = Field(None, description="دامنه tenant")

    # وضعیت و سطح
    status: TenantStatus = Field(
        default=TenantStatus.ACTIVE, description="وضعیت tenant"
    )
    tier: TenantTier = Field(default=TenantTier.FREE, description="سطح دسترسی")
    plan: TenantPlan = Field(default=TenantPlan.TRIAL, description="پلن اشتراک")

    # محدودیت‌ها
    limits: TenantLimits = Field(default_factory=TenantLimits, description="محدودیت‌ها")
    features: TenantFeatures = Field(
        default_factory=TenantFeatures, description="قابلیت‌ها"
    )

    # تنظیمات امنیتی
    encryption_enabled: bool = Field(default=True, description="رمزگذاری فعال")
    data_isolation: bool = Field(default=True, description="جداسازی داده")
    audit_logging: bool = Field(default=False, description="ثبت audit")

    # تنظیمات محتوا
    content_filtering: bool = Field(default=True, description="فیلتر محتوا")
    language_preference: str = Field(default="fa", description="زبان ترجیحی")
    timezone: str = Field(default="Asia/Tehran", description="منطقه زمانی")

    # متادیتا
    created_at: datetime = Field(
        default_factory=datetime.now, description="تاریخ ایجاد"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="تاریخ به‌روزرسانی"
    )
    expires_at: Optional[datetime] = Field(None, description="تاریخ انقضا")

    # اطلاعات تماس
    contact_email: Optional[str] = Field(None, description="ایمیل تماس")
    contact_phone: Optional[str] = Field(None, description="تلفن تماس")

    # تنظیمات سفارشی
    custom_settings: Dict[str, Any] = Field(
        default_factory=dict, description="تنظیمات سفارشی"
    )

    model_config = ConfigDict(use_enum_values=True)


class TenantUser(BaseModel):
    """کاربر tenant"""

    user_id: str = Field(..., description="شناسه کاربر")
    tenant_id: str = Field(..., description="شناسه tenant")
    username: str = Field(..., description="نام کاربری")
    email: str = Field(..., description="ایمیل")
    password_hash: Optional[str] = Field(None, description="هش رمز عبور")
    role: str = Field(default="user", description="نقش کاربر")
    permissions: List[str] = Field(default_factory=list, description="مجوزها")
    is_active: bool = Field(default=True, description="فعال")
    created_at: datetime = Field(
        default_factory=datetime.now, description="تاریخ ایجاد"
    )
    last_login: Optional[datetime] = Field(None, description="آخرین ورود")


class TenantUsage(BaseModel):
    """استفاده tenant"""

    tenant_id: str = Field(..., description="شناسه tenant")
    date: datetime = Field(..., description="تاریخ")

    # آمار استفاده
    documents_count: int = Field(default=0, description="تعداد اسناد")
    queries_count: int = Field(default=0, description="تعداد پرسش‌ها")
    storage_used_gb: float = Field(default=0.0, description="فضای استفاده شده")
    api_calls: int = Field(default=0, description="فراخوانی API")

    # آمار عملکرد
    avg_response_time: float = Field(default=0.0, description="میانگین زمان پاسخ")
    error_rate: float = Field(default=0.0, description="نرخ خطا")
    satisfaction_score: float = Field(default=0.0, description="امتیاز رضایت")

    # هزینه
    cost_usd: float = Field(default=0.0, description="هزینه به دلار")

    model_config = ConfigDict(use_enum_values=True)


class TenantBilling(BaseModel):
    """صورت‌حساب tenant"""

    tenant_id: str = Field(..., description="شناسه tenant")
    billing_period_start: datetime = Field(..., description="شروع دوره")
    billing_period_end: datetime = Field(..., description="پایان دوره")

    # هزینه‌ها
    base_cost: float = Field(default=0.0, description="هزینه پایه")
    usage_cost: float = Field(default=0.0, description="هزینه استفاده")
    overage_cost: float = Field(default=0.0, description="هزینه اضافی")
    total_cost: float = Field(default=0.0, description="کل هزینه")

    # وضعیت پرداخت
    status: str = Field(default="pending", description="وضعیت پرداخت")
    paid_at: Optional[datetime] = Field(None, description="تاریخ پرداخت")
    due_date: datetime = Field(..., description="تاریخ سررسید")

    # جزئیات
    invoice_number: str = Field(..., description="شماره فاکتور")
    payment_method: Optional[str] = Field(None, description="روش پرداخت")

    model_config = ConfigDict(use_enum_values=True)


class TenantPolicy(BaseModel):
    """سیاست‌های tenant"""

    tenant_id: str = Field(..., description="شناسه tenant")
    policy_type: str = Field(..., description="نوع سیاست")
    policy_name: str = Field(..., description="نام سیاست")

    # تنظیمات سیاست
    rules: Dict[str, Any] = Field(default_factory=dict, description="قوانین")
    conditions: List[str] = Field(default_factory=list, description="شرایط")
    actions: List[str] = Field(default_factory=list, description="اقدامات")

    # وضعیت
    is_active: bool = Field(default=True, description="فعال")
    priority: int = Field(default=0, description="اولویت")

    # متادیتا
    created_at: datetime = Field(
        default_factory=datetime.now, description="تاریخ ایجاد"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="تاریخ به‌روزرسانی"
    )

    model_config = ConfigDict(use_enum_values=True)


class TenantAuditLog(BaseModel):
    """لاگ audit tenant"""

    tenant_id: str = Field(..., description="شناسه tenant")
    user_id: Optional[str] = Field(None, description="شناسه کاربر")
    action: str = Field(..., description="عمل انجام شده")
    resource: str = Field(..., description="منبع")

    # جزئیات
    details: Dict[str, Any] = Field(default_factory=dict, description="جزئیات")
    ip_address: Optional[str] = Field(None, description="آدرس IP")
    user_agent: Optional[str] = Field(None, description="User Agent")

    # نتیجه
    success: bool = Field(default=True, description="موفقیت")
    error_message: Optional[str] = Field(None, description="پیام خطا")

    # زمان
    timestamp: datetime = Field(default_factory=datetime.now, description="زمان")

    model_config = ConfigDict(use_enum_values=True)


# Default configurations for different tiers
DEFAULT_TIER_CONFIGS = {
    TenantTier.FREE: TenantConfig(
        tenant_id="",
        name="Free Tier",
        tier=TenantTier.FREE,
        plan=TenantPlan.TRIAL,
        limits=TenantLimits(
            max_documents=100,
            max_queries_per_day=100,
            max_storage_gb=0.1,
            max_users=1,
            max_concurrent_queries=2,
            retention_days=7,
            api_rate_limit=10,
        ),
        features=TenantFeatures(
            advanced_analytics=False,
            ml_insights=False,
            predictive_analytics=False,
            custom_embeddings=False,
            api_access=False,
            webhook_support=False,
            priority_support=False,
            custom_branding=False,
        ),
    ),
    TenantTier.BASIC: TenantConfig(
        tenant_id="",
        name="Basic Tier",
        tier=TenantTier.BASIC,
        plan=TenantPlan.MONTHLY,
        limits=TenantLimits(
            max_documents=1000,
            max_queries_per_day=1000,
            max_storage_gb=1.0,
            max_users=5,
            max_concurrent_queries=10,
            retention_days=30,
            api_rate_limit=100,
        ),
        features=TenantFeatures(
            advanced_analytics=True,
            ml_insights=False,
            predictive_analytics=False,
            custom_embeddings=False,
            api_access=True,
            webhook_support=False,
            priority_support=False,
            custom_branding=False,
        ),
    ),
    TenantTier.PREMIUM: TenantConfig(
        tenant_id="",
        name="Premium Tier",
        tier=TenantTier.PREMIUM,
        plan=TenantPlan.MONTHLY,
        limits=TenantLimits(
            max_documents=10000,
            max_queries_per_day=10000,
            max_storage_gb=10.0,
            max_users=25,
            max_concurrent_queries=50,
            retention_days=90,
            api_rate_limit=1000,
        ),
        features=TenantFeatures(
            advanced_analytics=True,
            ml_insights=True,
            predictive_analytics=True,
            custom_embeddings=True,
            api_access=True,
            webhook_support=True,
            priority_support=True,
            custom_branding=False,
        ),
    ),
    TenantTier.ENTERPRISE: TenantConfig(
        tenant_id="",
        name="Enterprise Tier",
        tier=TenantTier.ENTERPRISE,
        plan=TenantPlan.CUSTOM,
        limits=TenantLimits(
            max_documents=100000,
            max_queries_per_day=100000,
            max_storage_gb=100.0,
            max_users=1000,
            max_concurrent_queries=200,
            retention_days=365,
            api_rate_limit=10000,
        ),
        features=TenantFeatures(
            advanced_analytics=True,
            ml_insights=True,
            predictive_analytics=True,
            custom_embeddings=True,
            api_access=True,
            webhook_support=True,
            priority_support=True,
            custom_branding=True,
        ),
    ),
}


class TenantApiKey(BaseModel):
    """API key credential for tenant access."""

    key_id: str = Field(..., description="Unique key identifier")
    tenant_id: str = Field(..., description="Associated tenant ID")
    user_id: str = Field(..., description="User ID who owns or created the key")
    name: str = Field(..., description="Descriptive name or label for the key")
    key_hash: str = Field(..., description="Cryptographic SHA-256 hash of the secret key")
    key_prefix: str = Field(..., description="Public prefix for key identification")
    permissions: List[str] = Field(default_factory=list, description="Explicit permissions")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    last_used_at: Optional[datetime] = Field(None, description="Last used timestamp")
    is_active: bool = Field(default=True, description="Active status")

    model_config = ConfigDict(use_enum_values=True)


class AuthenticatedPrincipal(BaseModel):
    """Resolved identity and authorization context for an API request."""

    principal_id: str = Field(..., description="User ID or Key ID of the principal")
    identity_type: str = Field(
        ..., description="Credential type: 'api_key' or 'user_session'"
    )
    tenant_id: str = Field(..., description="Tenant ID to which this principal belongs")
    username: Optional[str] = Field(None, description="Username if authenticated as user")
    role: str = Field(default="user", description="Assigned role in tenant")
    permissions: List[str] = Field(
        default_factory=list, description="Granted permissions"
    )
    is_super_admin: bool = Field(
        default=False, description="Whether principal possesses cross-tenant super-admin rights"
    )

    model_config = ConfigDict(use_enum_values=True)
