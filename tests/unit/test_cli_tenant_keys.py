"""Unit tests for CLI tenant API key commands."""

import argparse
from unittest.mock import AsyncMock, patch
import pytest

from ragbot.cli import (
    cmd_create_tenant_api_key,
    cmd_revoke_tenant_api_key,
    cmd_list_tenant_api_keys,
)


@pytest.mark.asyncio
async def test_cli_create_tenant_api_key():
    """Verify CLI create-api-key command."""
    mock_service = AsyncMock()
    mock_service.create_tenant_api_key = AsyncMock(
        return_value={
            "success": True,
            "tenant_id": "test_tenant",
            "name": "cli_key",
            "api_key": "rgb_secret1234567890",
            "prefix": "rgb_secret12",
        }
    )

    args = argparse.Namespace(
        tenant_id="test_tenant",
        name="cli_key",
        user_id=None,
        expires_days=30,
    )

    with patch("ragbot.cli._get_rag_service", return_value=mock_service):
        code = await cmd_create_tenant_api_key(args)
        assert code == 0
        mock_service.create_tenant_api_key.assert_called_once_with(
            tenant_id="test_tenant",
            name="cli_key",
            user_id=None,
            expires_days=30,
        )


@pytest.mark.asyncio
async def test_cli_revoke_tenant_api_key():
    """Verify CLI revoke-api-key command."""
    mock_service = AsyncMock()
    mock_service.revoke_tenant_api_key = AsyncMock(
        return_value={"success": True, "message": "Revoked"}
    )

    args = argparse.Namespace(
        tenant_id="test_tenant",
        key_id="key_uuid_123",
    )

    with patch("ragbot.cli._get_rag_service", return_value=mock_service):
        code = await cmd_revoke_tenant_api_key(args)
        assert code == 0
        mock_service.revoke_tenant_api_key.assert_called_once_with(
            tenant_id="test_tenant",
            api_key_or_id="key_uuid_123",
        )


@pytest.mark.asyncio
async def test_cli_list_tenant_api_keys():
    """Verify CLI list-api-keys command."""
    mock_service = AsyncMock()
    mock_service.list_tenant_api_keys = AsyncMock(
        return_value={
            "success": True,
            "tenant_id": "test_tenant",
            "api_keys": [
                {
                    "key_id": "k1",
                    "name": "key1",
                    "key_prefix": "rgb_123",
                }
            ],
        }
    )

    args = argparse.Namespace(
        tenant_id="test_tenant",
    )

    with patch("ragbot.cli._get_rag_service", return_value=mock_service):
        code = await cmd_list_tenant_api_keys(args)
        assert code == 0
        mock_service.list_tenant_api_keys.assert_called_once_with("test_tenant")
