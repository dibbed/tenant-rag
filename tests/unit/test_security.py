"""
Unit tests for security components

Tests for encryption, key management, and secure backup functionality.
"""

import pytest
import asyncio
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from ragbot.security.encryption import (
    EncryptionManager,
    EncryptionAlgorithm,
    EncryptionMode,
    EncryptedDocument,
    KeyRotationResult,
    EncryptionKey,
)
from ragbot.security.key_manager import (
    KeyManager,
    KeyType,
    KeyStatus,
    KeyPolicy,
)
from ragbot.security.secure_backup import (
    SecureBackupManager,
    BackupStatus,
    BackupType,
    BackupResult,
    RestoreResult,
    VerificationResult,
)
from ragbot.rag.store.base import VectorDocument


class TestEncryptionManager:
    """Test cases for EncryptionManager"""

    @pytest.fixture
    def encryption_manager(self):
        """Create encryption manager instance"""
        return EncryptionManager()

    @pytest.fixture
    def sample_document(self):
        """Create sample vector document"""
        return VectorDocument(
            id="test_doc_1",
            content="This is a test document for encryption testing.",
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            metadata={"category": "test", "score": 0.85},
        )

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_document(self, encryption_manager, sample_document):
        """Test document encryption and decryption"""
        # Encrypt document
        encrypted_doc = await encryption_manager.encrypt_document(sample_document)

        assert isinstance(encrypted_doc, EncryptedDocument)
        assert encrypted_doc.document_id == sample_document.id
        assert encrypted_doc.encrypted_content != sample_document.content.encode()
        assert (
            encrypted_doc.encrypted_metadata != str(sample_document.metadata).encode()
        )
        assert (
            encrypted_doc.encrypted_embeddings
            != str(sample_document.embedding).encode()
        )
        assert encrypted_doc.key_id is not None
        assert encrypted_doc.timestamp is not None

        # Decrypt document
        decrypted_doc = await encryption_manager.decrypt_document(encrypted_doc)

        assert decrypted_doc.id == sample_document.id
        assert decrypted_doc.content == sample_document.content
        assert decrypted_doc.embedding == sample_document.embedding
        assert decrypted_doc.metadata == sample_document.metadata

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_embeddings(self, encryption_manager):
        """Test embeddings encryption and decryption"""
        embeddings = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

        # Encrypt embeddings
        encrypted_embeddings, iv, tag = await encryption_manager.encrypt_embeddings(
            embeddings
        )

        assert isinstance(encrypted_embeddings, bytes)
        assert encrypted_embeddings != str(embeddings).encode()

        # Decrypt embeddings
        decrypted_embeddings = await encryption_manager.decrypt_embeddings(
            encrypted_embeddings, iv, tag
        )

        assert decrypted_embeddings == embeddings

    @pytest.mark.asyncio
    async def test_key_rotation(self, encryption_manager):
        """Test encryption key rotation"""
        old_key_id = encryption_manager.get_active_key_id()

        # Rotate keys
        rotation_result = await encryption_manager.rotate_encryption_keys()

        assert isinstance(rotation_result, KeyRotationResult)
        assert rotation_result.success
        assert rotation_result.old_key_id == old_key_id
        assert rotation_result.new_key_id != old_key_id
        assert rotation_result.rotation_time >= 0

        # Check new active key
        new_key_id = encryption_manager.get_active_key_id()
        assert new_key_id == rotation_result.new_key_id
        assert new_key_id != old_key_id

    def test_get_key_info(self, encryption_manager):
        """Test getting key information"""
        active_key_id = encryption_manager.get_active_key_id()
        key_info = encryption_manager.get_key_info(active_key_id)

        assert key_info is not None
        assert key_info["key_id"] == active_key_id
        assert key_info["is_active"] is True
        assert key_info["algorithm"] in [alg.value for alg in EncryptionAlgorithm]

    def test_list_keys(self, encryption_manager):
        """Test listing all keys"""
        keys = encryption_manager.list_keys()

        assert isinstance(keys, list)
        assert len(keys) > 0
        assert all("key_id" in key for key in keys)

    def test_get_encryption_stats(self, encryption_manager):
        """Test getting encryption statistics"""
        stats = encryption_manager.get_encryption_stats()

        assert isinstance(stats, dict)
        assert "total_keys" in stats
        assert "active_keys" in stats
        assert "expired_keys" in stats
        assert "active_key_id" in stats
        assert "algorithm" in stats
        assert "mode" in stats

    def test_set_active_key(self, encryption_manager):
        """Test setting active key"""
        keys = encryption_manager.list_keys()
        if len(keys) > 1:
            # Try to set a different key as active
            other_key_id = keys[1]["key_id"]
            result = encryption_manager.set_active_key(other_key_id)
            assert result is True
            assert encryption_manager.get_active_key_id() == other_key_id


class TestKeyManager:
    """Test cases for KeyManager"""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def key_manager(self, temp_storage):
        """Create key manager instance"""
        return KeyManager(storage_path=temp_storage)

    @pytest.mark.asyncio
    async def test_generate_key(self, key_manager):
        """Test key generation"""
        key = await key_manager.generate_key(KeyType.DATA, algorithm="AES-256")

        assert isinstance(key, EncryptionKey)
        assert key.key_id is not None
        assert key.algorithm == EncryptionAlgorithm.AES_256_GCM
        assert key.is_active is True
        assert key.expires_at is not None

    @pytest.mark.asyncio
    async def test_store_retrieve_key(self, key_manager):
        """Test key storage and retrieval"""
        # Generate and store key
        key = await key_manager.generate_key(KeyType.ENCRYPTION, algorithm="Fernet")
        key_id = key.key_id

        # Retrieve key
        retrieved_key = await key_manager.retrieve_key(key_id)

        assert retrieved_key is not None
        assert retrieved_key.key_id == key_id
        assert retrieved_key.algorithm == key.algorithm
        assert retrieved_key.key_data == key.key_data

    @pytest.mark.asyncio
    async def test_revoke_key(self, key_manager):
        """Test key revocation"""
        # Generate key
        key = await key_manager.generate_key(KeyType.DATA)
        key_id = key.key_id

        # Revoke key
        result = await key_manager.revoke_key(key_id, "Test revocation")

        assert result is True

        # Try to retrieve revoked key
        with pytest.raises(ValueError, match="has been revoked"):
            await key_manager.retrieve_key(key_id)

    @pytest.mark.asyncio
    async def test_rotate_key(self, key_manager):
        """Test key rotation"""
        # Generate key
        original_key = await key_manager.generate_key(KeyType.DATA)
        original_key_id = original_key.key_id

        # Rotate key
        new_key = await key_manager.rotate_key(original_key_id)

        assert new_key is not None
        assert new_key.key_id != original_key_id
        assert new_key.algorithm == original_key.algorithm

    @pytest.mark.asyncio
    async def test_list_keys(self, key_manager):
        """Test listing keys"""
        # Generate multiple keys
        await key_manager.generate_key(KeyType.DATA)
        await key_manager.generate_key(KeyType.ENCRYPTION)
        await key_manager.generate_key(KeyType.BACKUP)

        # List all keys
        all_keys = await key_manager.list_keys()
        assert len(all_keys) >= 3

        # List keys by type
        data_keys = await key_manager.list_keys(key_type=KeyType.DATA)
        assert len(data_keys) >= 1
        assert all(key["key_type"] == "data" for key in data_keys)

    @pytest.mark.asyncio
    async def test_get_key_statistics(self, key_manager):
        """Test getting key statistics"""
        # Generate some keys
        await key_manager.generate_key(KeyType.DATA)
        await key_manager.generate_key(KeyType.ENCRYPTION)

        # Get statistics
        stats = await key_manager.get_key_statistics()

        assert isinstance(stats, dict)
        assert "total_keys" in stats
        assert "active_keys" in stats
        assert "expired_keys" in stats
        assert "revoked_keys" in stats
        assert "keys_by_type" in stats
        assert "keys_by_algorithm" in stats
        assert "cache_size" in stats
        assert stats["total_keys"] >= 2


class TestSecureBackupManager:
    """Test cases for SecureBackupManager"""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_vector_stores(self):
        """Create mock vector stores"""
        stores = []
        for i in range(2):
            store = Mock()
            store.get_store_type.return_value = f"mock_store_{i}"
            store.get_all_documents = AsyncMock(
                return_value=[
                    VectorDocument(
                        id=f"doc_{i}_{j}",
                        content=f"Document {i}-{j} content",
                        embedding=[0.1 * j, 0.2 * j, 0.3 * j],
                        metadata={"store": f"store_{i}", "index": j},
                    )
                    for j in range(3)
                ]
            )
            store.add_documents = AsyncMock()
            stores.append(store)
        return stores

    @pytest.fixture
    def backup_manager(self, temp_storage):
        """Create backup manager instance"""
        with patch("ragbot.configs.settings.settings") as mock_settings:
            mock_settings.data_dir = Path(temp_storage)
            return SecureBackupManager()

    @pytest.mark.asyncio
    async def test_create_encrypted_backup(self, backup_manager, mock_vector_stores):
        """Test creating encrypted backup"""
        result = await backup_manager.create_encrypted_backup(
            mock_vector_stores, backup_name="test_backup", compression=True
        )

        assert isinstance(result, BackupResult)
        assert result.backup_id is not None
        assert result.status in [BackupStatus.COMPLETED, BackupStatus.VERIFIED]
        assert result.file_size > 0
        assert result.encryption_key_id is not None
        assert len(result.vector_stores_backed_up) == 2
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_verify_backup_integrity(self, backup_manager, mock_vector_stores):
        """Test backup integrity verification"""
        # Create backup first
        backup_result = await backup_manager.create_encrypted_backup(
            mock_vector_stores, backup_name="verify_test"
        )

        # Verify backup
        verification_result = await backup_manager.verify_backup_integrity(
            backup_result.backup_path
        )

        assert isinstance(verification_result, VerificationResult)
        assert verification_result.is_valid is True
        assert verification_result.checksum_match is True
        assert verification_result.corruption_check is True
        assert verification_result.errors == []

    @pytest.mark.asyncio
    async def test_list_backups(self, backup_manager, mock_vector_stores):
        """Test listing backups"""
        # Create some backups
        await backup_manager.create_encrypted_backup(
            mock_vector_stores, backup_name="backup_1"
        )
        await backup_manager.create_encrypted_backup(
            mock_vector_stores, backup_name="backup_2"
        )

        # List backups
        backups = await backup_manager.list_backups()

        assert isinstance(backups, list)
        assert len(backups) >= 2
        assert all("backup_id" in backup for backup in backups)
        assert all("backup_path" in backup for backup in backups)
        assert all("created_at" in backup for backup in backups)

    @pytest.mark.asyncio
    async def test_delete_backup(self, backup_manager, mock_vector_stores):
        """Test backup deletion"""
        # Create backup
        backup_result = await backup_manager.create_encrypted_backup(
            mock_vector_stores, backup_name="delete_test"
        )

        # Delete backup
        result = await backup_manager.delete_backup(backup_result.backup_id)

        assert result is True

        # Verify backup is deleted
        backups = await backup_manager.list_backups()
        backup_ids = [backup["backup_id"] for backup in backups]
        assert backup_result.backup_id not in backup_ids

    @pytest.mark.asyncio
    async def test_restore_from_backup(self, backup_manager, mock_vector_stores):
        """Test restoring from backup"""
        # Create backup
        backup_result = await backup_manager.create_encrypted_backup(
            mock_vector_stores, backup_name="restore_test"
        )

        # Create target stores for restoration
        target_stores = []
        for i in range(2):
            store = Mock()
            store.get_store_type.return_value = f"mock_store_{i}"
            store.add_documents = AsyncMock()
            target_stores.append(store)

        # Restore from backup
        restore_result = await backup_manager.restore_from_backup(
            backup_result.backup_path, target_stores=target_stores
        )

        assert isinstance(restore_result, RestoreResult)
        assert restore_result.status == "completed"
        assert len(restore_result.restored_stores) >= 0
        assert restore_result.restore_time > 0
        assert restore_result.errors == []


class TestIntegration:
    """Integration tests for security components"""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_encryption_with_key_management(self, temp_storage):
        """Test encryption with key management integration"""
        # Create managers
        key_manager = KeyManager(storage_path=temp_storage)
        encryption_manager = EncryptionManager()

        # Generate key
        key = await key_manager.generate_key(KeyType.DATA, algorithm="AES-256")

        # Set key in encryption manager
        encryption_manager.keys[key.key_id] = key
        encryption_manager.active_key_id = key.key_id

        # Create and encrypt document
        document = VectorDocument(
            id="integration_test",
            content="Integration test document",
            embedding=[0.1, 0.2, 0.3],
            metadata={"test": True},
        )

        encrypted_doc = await encryption_manager.encrypt_document(document)
        decrypted_doc = await encryption_manager.decrypt_document(encrypted_doc)

        assert decrypted_doc.content == document.content
        assert decrypted_doc.embedding == document.embedding
        assert decrypted_doc.metadata == document.metadata

    @pytest.mark.asyncio
    async def test_backup_with_encryption(self, temp_storage):
        """Test backup with encryption integration"""
        # Create managers
        encryption_manager = EncryptionManager()
        backup_manager = SecureBackupManager(encryption_manager)

        # Create mock vector stores
        mock_stores = []
        for i in range(2):
            store = Mock()
            store.get_store_type.return_value = f"test_store_{i}"
            store.get_all_documents = AsyncMock(
                return_value=[
                    VectorDocument(
                        id=f"doc_{i}_{j}",
                        content=f"Test document {i}-{j}",
                        embedding=[0.1 * j, 0.2 * j, 0.3 * j],
                        metadata={"store": f"store_{i}", "index": j},
                    )
                    for j in range(2)
                ]
            )
            store.add_documents = AsyncMock()
            mock_stores.append(store)

        # Create encrypted backup
        backup_result = await backup_manager.create_encrypted_backup(
            mock_stores, backup_name="encrypted_backup_test"
        )

        assert backup_result.status in [BackupStatus.COMPLETED, BackupStatus.VERIFIED]
        assert backup_result.encryption_key_id is not None

        # Verify backup
        verification_result = await backup_manager.verify_backup_integrity(
            backup_result.backup_path
        )
        assert verification_result.is_valid is True
