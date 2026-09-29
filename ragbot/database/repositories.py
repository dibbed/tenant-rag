"""Focused SQLAlchemy repositories for tenant persistence.

Repositories issue statements and stage ORM changes. They never commit or roll back;
transaction ownership stays with the calling business operation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import Insert, insert

if TYPE_CHECKING:
    from datetime import date, datetime

    from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    TenantApiKeyRecord,
    TenantAuditLogRecord,
    TenantQuotaRecord,
    TenantRecord,
    TenantSessionRecord,
    TenantUsageRecord,
    TenantUserRecord,
)


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, tenant_id: str) -> TenantRecord | None:
        return await self.session.get(TenantRecord, tenant_id)

    async def list_all(self) -> list[TenantRecord]:
        result = await self.session.scalars(
            select(TenantRecord).order_by(TenantRecord.created_at)
        )
        return list(result.all())

    async def list_active(self) -> list[TenantRecord]:
        result = await self.session.scalars(
            select(TenantRecord)
            .where(TenantRecord.status == "active")
            .order_by(TenantRecord.created_at)
        )
        return list(result.all())

    async def count(self) -> int:
        value = await self.session.scalar(select(func.count()).select_from(TenantRecord))
        return int(value or 0)

    async def add(self, record: TenantRecord) -> None:
        self.session.add(record)

    async def delete(self, tenant_id: str) -> bool:
        result = await self.session.execute(
            delete(TenantRecord).where(TenantRecord.tenant_id == tenant_id)
        )
        return bool(result.rowcount)


class QuotaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def for_update_statement(tenant_id: str) -> Any:
        return (
            select(TenantQuotaRecord)
            .where(TenantQuotaRecord.tenant_id == tenant_id)
            .with_for_update()
        )

    async def get(self, tenant_id: str) -> TenantQuotaRecord | None:
        return await self.session.get(TenantQuotaRecord, tenant_id)

    async def get_for_update(self, tenant_id: str) -> TenantQuotaRecord | None:
        result = await self.session.scalars(self.for_update_statement(tenant_id))
        return result.first()

    async def add(self, record: TenantQuotaRecord) -> None:
        self.session.add(record)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def count_statement(tenant_id: str) -> Any:
        return select(func.count()).select_from(TenantUserRecord).where(
            TenantUserRecord.tenant_id == tenant_id
        )

    async def count_for_tenant(self, tenant_id: str) -> int:
        value = await self.session.scalar(self.count_statement(tenant_id))
        return int(value or 0)

    async def get(self, user_id: str) -> TenantUserRecord | None:
        return await self.session.get(TenantUserRecord, user_id)

    async def list_for_tenant(self, tenant_id: str) -> list[TenantUserRecord]:
        result = await self.session.scalars(
            select(TenantUserRecord)
            .where(TenantUserRecord.tenant_id == tenant_id)
            .order_by(TenantUserRecord.created_at)
        )
        return list(result.all())

    async def find_by_username(
        self, tenant_id: str, username: str
    ) -> TenantUserRecord | None:
        result = await self.session.scalars(
            select(TenantUserRecord).where(
                TenantUserRecord.tenant_id == tenant_id,
                TenantUserRecord.username == username,
            )
        )
        return result.first()

    async def find_by_email(
        self, tenant_id: str, email: str
    ) -> TenantUserRecord | None:
        result = await self.session.scalars(
            select(TenantUserRecord).where(
                TenantUserRecord.tenant_id == tenant_id,
                TenantUserRecord.email == email,
            )
        )
        return result.first()

    async def add(self, record: TenantUserRecord) -> None:
        self.session.add(record)


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def deactivate_expired_statement(before: datetime) -> Any:
        return (
            update(TenantApiKeyRecord)
            .where(
                TenantApiKeyRecord.is_active.is_(True),
                TenantApiKeyRecord.expires_at.is_not(None),
                TenantApiKeyRecord.expires_at <= before,
            )
            .values(is_active=False)
        )

    async def deactivate_expired(self, before: datetime) -> int:
        result = await self.session.execute(self.deactivate_expired_statement(before))
        return int(result.rowcount or 0)

    async def lookup_auth(self, key_id: str) -> dict[str, Any] | None:
        result = await self.session.execute(
            text("SELECT * FROM public.lookup_api_key_auth(:key_id)"),
            {"key_id": key_id},
        )
        row = result.mappings().first()
        return dict(row) if row is not None else None

    async def get(
        self, key_id: str, tenant_id: str | None = None
    ) -> TenantApiKeyRecord | None:
        statement = select(TenantApiKeyRecord).where(
            TenantApiKeyRecord.key_id == key_id
        )
        if tenant_id is not None:
            statement = statement.where(TenantApiKeyRecord.tenant_id == tenant_id)
        result = await self.session.scalars(statement)
        return result.first()

    async def list_for_tenant(self, tenant_id: str) -> list[TenantApiKeyRecord]:
        result = await self.session.scalars(
            select(TenantApiKeyRecord)
            .where(TenantApiKeyRecord.tenant_id == tenant_id)
            .order_by(TenantApiKeyRecord.created_at.desc())
        )
        return list(result.all())

    async def add(self, record: TenantApiKeyRecord) -> None:
        self.session.add(record)

    async def revoke(self, key_id: str, tenant_id: str) -> bool:
        result = await self.session.execute(
            update(TenantApiKeyRecord)
            .where(
                TenantApiKeyRecord.key_id == key_id,
                TenantApiKeyRecord.tenant_id == tenant_id,
            )
            .values(is_active=False)
        )
        return bool(result.rowcount)

    async def update_last_used(self, key_id: str, used_at: datetime) -> None:
        await self.session.execute(
            update(TenantApiKeyRecord)
            .where(TenantApiKeyRecord.key_id == key_id)
            .values(last_used_at=used_at)
        )


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lookup_auth(self, token_hash: str) -> dict[str, Any] | None:
        result = await self.session.execute(
            text("SELECT * FROM public.lookup_session_auth(:token_hash)"),
            {"token_hash": token_hash},
        )
        row = result.mappings().first()
        return dict(row) if row is not None else None

    async def add(self, record: TenantSessionRecord) -> None:
        self.session.add(record)

    async def revoke(self, session_id: str, revoked_at: datetime) -> bool:
        result = await self.session.execute(
            update(TenantSessionRecord)
            .where(
                TenantSessionRecord.session_id == session_id,
                TenantSessionRecord.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        return bool(result.rowcount)

    async def revoke_for_user(
        self, tenant_id: str, user_id: str, revoked_at: datetime
    ) -> int:
        result = await self.session.execute(
            update(TenantSessionRecord)
            .where(
                TenantSessionRecord.tenant_id == tenant_id,
                TenantSessionRecord.user_id == user_id,
                TenantSessionRecord.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        return int(result.rowcount or 0)

    async def touch(self, session_id: str, used_at: datetime) -> None:
        await self.session.execute(
            update(TenantSessionRecord)
            .where(TenantSessionRecord.session_id == session_id)
            .values(last_used_at=used_at)
        )

    async def delete_expired(self, before: datetime) -> int:
        result = await self.session.execute(
            delete(TenantSessionRecord).where(TenantSessionRecord.expires_at <= before)
        )
        return int(result.rowcount or 0)


class UsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def increment_statement(
        *,
        tenant_id: str,
        usage_date: date,
        operation: str,
        metadata: dict[str, Any] | None = None,
    ) -> Insert:
        metadata = metadata or {}
        values: dict[str, Any] = {
            "tenant_id": tenant_id,
            "usage_date": usage_date,
        }
        updates: dict[str, Any] = {"updated_at": func.now()}

        if operation == "query":
            values.update(
                queries_count=1,
                avg_response_time=float(metadata.get("response_time", 0.0)),
                error_rate=float(metadata.get("error_rate", 0.0)),
                satisfaction_score=float(metadata.get("satisfaction", 0.0)),
            )
            updates.update(
                queries_count=TenantUsageRecord.queries_count + 1,
                avg_response_time=float(metadata.get("response_time", 0.0)),
                error_rate=float(metadata.get("error_rate", 0.0)),
                satisfaction_score=float(metadata.get("satisfaction", 0.0)),
            )
        elif operation == "document":
            size_gb = float(metadata.get("size_gb", 0.0))
            values.update(documents_count=1, storage_used_gb=size_gb)
            updates.update(
                documents_count=TenantUsageRecord.documents_count + 1,
                storage_used_gb=TenantUsageRecord.storage_used_gb + size_gb,
            )
        elif operation == "api_call":
            values.update(api_calls=1)
            updates.update(api_calls=TenantUsageRecord.api_calls + 1)
        else:
            raise ValueError(f"Unsupported usage operation: {operation}")

        statement = insert(TenantUsageRecord).values(**values)
        return statement.on_conflict_do_update(
            index_elements=[
                TenantUsageRecord.tenant_id,
                TenantUsageRecord.usage_date,
            ],
            set_=updates,
        )

    async def increment(
        self,
        *,
        tenant_id: str,
        usage_date: date,
        operation: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.session.execute(
            self.increment_statement(
                tenant_id=tenant_id,
                usage_date=usage_date,
                operation=operation,
                metadata=metadata,
            )
        )

    async def get(
        self, tenant_id: str, usage_date: date
    ) -> TenantUsageRecord | None:
        return await self.session.get(
            TenantUsageRecord,
            {"tenant_id": tenant_id, "usage_date": usage_date},
        )

    async def list_between(
        self, tenant_id: str, start_date: date, end_date: date
    ) -> list[TenantUsageRecord]:
        result = await self.session.scalars(
            select(TenantUsageRecord)
            .where(
                TenantUsageRecord.tenant_id == tenant_id,
                TenantUsageRecord.usage_date >= start_date,
                TenantUsageRecord.usage_date <= end_date,
            )
            .order_by(TenantUsageRecord.usage_date)
        )
        return list(result.all())


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, record: TenantAuditLogRecord) -> None:
        self.session.add(record)

    async def list_for_tenant(
        self, tenant_id: str, *, limit: int = 1000
    ) -> list[TenantAuditLogRecord]:
        result = await self.session.scalars(
            select(TenantAuditLogRecord)
            .where(TenantAuditLogRecord.tenant_id == tenant_id)
            .order_by(TenantAuditLogRecord.created_at.desc())
            .limit(limit)
        )
        return list(result.all())
