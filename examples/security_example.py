"""
Security Features Example

This example demonstrates the usage of encryption, key management,
and secure backup features in the RAG system.
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from ragbot.security.encryption import EncryptionManager, EncryptionAlgorithm
from ragbot.security.key_manager import KeyManager, KeyType
from ragbot.security.secure_backup import SecureBackupManager, BackupType
from ragbot.rag.store.base import VectorDocument


async def main():
    """Main example function"""
    print("🔐 Security Features Example")
    print("=" * 50)

    # Create temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    print(f"📁 Using temporary directory: {temp_dir}")

    try:
        # 1. Encryption Manager Example
        print("\n🔒 1. Encryption Manager Example")
        print("-" * 30)

        encryption_manager = EncryptionManager({
            'algorithm': 'aes_256_gcm',
            'mode': 'symmetric'
        })

        # Create sample document
        sample_doc = VectorDocument(
            id="secure_doc_1",
            content="This is a confidential document that needs encryption.",
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            metadata={
                "classification": "confidential",
                "author": "security_team",
                "created_at": datetime.now().isoformat(),
                "tags": ["security", "encryption", "confidential"]
            }
        )

        print(f"📄 Original document: {sample_doc.id}")
        print(f"   Content length: {len(sample_doc.content)} characters")
        print(f"   Embedding dimension: {len(sample_doc.embedding)}")
        print(f"   Metadata keys: {list(sample_doc.metadata.keys())}")

        # Encrypt document
        encrypted_doc = await encryption_manager.encrypt_document(sample_doc)
        print(f"🔐 Encrypted document: {encrypted_doc.document_id}")
        print(f"   Encryption algorithm: {encrypted_doc.encryption_algorithm.value}")
        print(f"   Key ID: {encrypted_doc.key_id}")
        print(f"   Has IV: {encrypted_doc.iv is not None}")
        print(f"   Has tag: {encrypted_doc.tag is not None}")

        # Decrypt document
        decrypted_doc = await encryption_manager.decrypt_document(encrypted_doc)
        print(f"🔓 Decrypted document: {decrypted_doc.id}")
        print(f"   Content matches: {decrypted_doc.content == sample_doc.content}")
        print(f"   Embedding matches: {decrypted_doc.embedding == sample_doc.embedding}")
        print(f"   Metadata matches: {decrypted_doc.metadata == sample_doc.metadata}")

        # Test embeddings encryption
        embeddings = [0.1, 0.2, 0.3, 0.4, 0.5]
        encrypted_embeddings = await encryption_manager.encrypt_embeddings(embeddings)
        decrypted_embeddings = await encryption_manager.decrypt_embeddings(encrypted_embeddings)
        print(f"🧮 Embeddings encryption test: {embeddings == decrypted_embeddings}")

        # Key rotation
        print(f"\n🔄 Key rotation test:")
        old_key_id = encryption_manager.get_active_key_id()
        rotation_result = await encryption_manager.rotate_encryption_keys()
        new_key_id = encryption_manager.get_active_key_id()
        print(f"   Old key: {old_key_id}")
        print(f"   New key: {new_key_id}")
        print(f"   Rotation successful: {rotation_result.success}")
        print(f"   Rotation time: {rotation_result.rotation_time:.3f}s")

        # Encryption statistics
        stats = encryption_manager.get_encryption_stats()
        print(f"\n📊 Encryption statistics:")
        print(f"   Total keys: {stats['total_keys']}")
        print(f"   Active keys: {stats['active_keys']}")
        print(f"   Expired keys: {stats['expired_keys']}")
        print(f"   Algorithm: {stats['algorithm']}")
        print(f"   Mode: {stats['mode']}")

        # 2. Key Manager Example
        print("\n🗝️ 2. Key Manager Example")
        print("-" * 30)

        key_manager = KeyManager(storage_path=temp_dir)

        # Generate different types of keys
        data_key = await key_manager.generate_key(KeyType.DATA, algorithm="AES-256")
        encryption_key = await key_manager.generate_key(KeyType.ENCRYPTION, algorithm="RSA-2048")
        backup_key = await key_manager.generate_key(KeyType.BACKUP, algorithm="Fernet")

        print(f"🔑 Generated keys:")
        print(f"   Data key: {data_key.key_id} ({data_key.algorithm.value})")
        print(f"   Encryption key: {encryption_key.key_id} ({encryption_key.algorithm.value})")
        print(f"   Backup key: {backup_key.key_id} ({backup_key.algorithm.value})")

        # Retrieve key
        retrieved_key = await key_manager.retrieve_key(data_key.key_id)
        print(f"📥 Retrieved key: {retrieved_key.key_id}")
        print(f"   Key matches: {retrieved_key.key_data == data_key.key_data}")

        # List keys
        all_keys = await key_manager.list_keys()
        data_keys = await key_manager.list_keys(key_type=KeyType.DATA)
        print(f"📋 Key listing:")
        print(f"   Total keys: {len(all_keys)}")
        print(f"   Data keys: {len(data_keys)}")

        # Key statistics
        key_stats = await key_manager.get_key_statistics()
        print(f"📊 Key statistics:")
        print(f"   Total keys: {key_stats['total_keys']}")
        print(f"   Active keys: {key_stats['active_keys']}")
        print(f"   Keys by type: {key_stats['keys_by_type']}")
        print(f"   Keys by algorithm: {key_stats['keys_by_algorithm']}")

        # Key rotation
        print(f"\n🔄 Key rotation test:")
        new_rotated_key = await key_manager.rotate_key(data_key.key_id)
        print(f"   Original key: {data_key.key_id}")
        print(f"   Rotated key: {new_rotated_key.key_id}")
        print(f"   Rotation successful: {new_rotated_key is not None}")

        # Key revocation
        print(f"\n❌ Key revocation test:")
        revoke_result = await key_manager.revoke_key(encryption_key.key_id, "Test revocation")
        print(f"   Revocation successful: {revoke_result}")

        # 3. Secure Backup Example
        print("\n💾 3. Secure Backup Example")
        print("-" * 30)

        backup_manager = SecureBackupManager(encryption_manager)

        # Create mock vector stores
        class MockVectorStore:
            def __init__(self, store_id: str, documents: list):
                self.store_id = store_id
                self.documents = documents

            def get_store_type(self):
                return f"mock_store_{self.store_id}"

            async def get_all_documents(self):
                return self.documents

            async def add_documents(self, docs):
                self.documents.extend(docs)

        # Create sample documents
        sample_docs_1 = [
            VectorDocument(
                id=f"doc_1_{i}",
                content=f"Document 1-{i} content for backup testing",
                embedding=[0.1 * i, 0.2 * i, 0.3 * i, 0.4 * i, 0.5 * i],
                metadata={"store": "store_1", "index": i, "backup_test": True}
            )
            for i in range(3)
        ]

        sample_docs_2 = [
            VectorDocument(
                id=f"doc_2_{i}",
                content=f"Document 2-{i} content for backup testing",
                embedding=[0.2 * i, 0.4 * i, 0.6 * i, 0.8 * i, 1.0 * i],
                metadata={"store": "store_2", "index": i, "backup_test": True}
            )
            for i in range(2)
        ]

        mock_stores = [
            MockVectorStore("1", sample_docs_1),
            MockVectorStore("2", sample_docs_2)
        ]

        print(f"📦 Mock stores created:")
        print(f"   Store 1: {len(sample_docs_1)} documents")
        print(f"   Store 2: {len(sample_docs_2)} documents")

        # Create encrypted backup
        backup_result = await backup_manager.create_encrypted_backup(
            mock_stores,
            backup_name="security_example_backup",
            backup_type=BackupType.FULL,
            compression=True,
            verify_after=True
        )

        print(f"💾 Backup created:")
        print(f"   Backup ID: {backup_result.backup_id}")
        print(f"   Status: {backup_result.status.value}")
        print(f"   File size: {backup_result.file_size} bytes")
        print(f"   Compression ratio: {backup_result.compression_ratio:.2f}")
        print(f"   Encryption key: {backup_result.encryption_key_id}")
        print(f"   Stores backed up: {backup_result.vector_stores_backed_up}")

        # Verify backup
        verification_result = await backup_manager.verify_backup_integrity(backup_result.backup_path)
        print(f"✅ Backup verification:")
        print(f"   Is valid: {verification_result.is_valid}")
        print(f"   Checksum match: {verification_result.checksum_match}")
        print(f"   Corruption check: {verification_result.corruption_check}")
        print(f"   Signature valid: {verification_result.signature_valid}")

        # List backups
        backups = await backup_manager.list_backups()
        print(f"📋 Available backups: {len(backups)}")
        for backup in backups[:3]:  # Show first 3
            print(f"   - {backup['backup_id']}: {backup['file_size']} bytes")

        # Test restore (with new mock stores)
        print(f"\n🔄 Restore test:")
        restore_stores = [
            MockVectorStore("restore_1", []),
            MockVectorStore("restore_2", [])
        ]

        restore_result = await backup_manager.restore_from_backup(
            backup_result.backup_path,
            target_stores=restore_stores,
            verify_before=True
        )

        print(f"   Restore ID: {restore_result.restore_id}")
        print(f"   Status: {restore_result.status}")
        print(f"   Restored stores: {restore_result.restored_stores}")
        print(f"   Restore time: {restore_result.restore_time:.3f}s")

        # Check restored documents
        total_restored = sum(len(store.documents) for store in restore_stores)
        print(f"   Total documents restored: {total_restored}")

        # 4. Integration Example
        print("\n🔗 4. Integration Example")
        print("-" * 30)

        # Create document with encryption
        secure_doc = VectorDocument(
            id="integration_doc",
            content="This document will be encrypted, backed up, and restored.",
            embedding=[0.5, 0.6, 0.7, 0.8, 0.9],
            metadata={"integration_test": True, "timestamp": datetime.now().isoformat()}
        )

        # Encrypt document
        encrypted_integration_doc = await encryption_manager.encrypt_document(secure_doc)
        print(f"🔐 Document encrypted: {encrypted_integration_doc.document_id}")

        # Create backup with encrypted document
        integration_store = MockVectorStore("integration", [secure_doc])
        integration_backup = await backup_manager.create_encrypted_backup(
            [integration_store],
            backup_name="integration_test"
        )

        print(f"💾 Integration backup created: {integration_backup.backup_id}")
        print(f"   Status: {integration_backup.status.value}")

        # Verify integration backup
        integration_verification = await backup_manager.verify_backup_integrity(
            integration_backup.backup_path
        )
        print(f"✅ Integration backup verified: {integration_verification.is_valid}")

        print("\n🎉 Security Features Example Completed Successfully!")
        print("=" * 50)

    except Exception as e:
        print(f"❌ Error in security example: {e}")
        raise

    finally:
        # Cleanup
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)
        print(f"🧹 Cleaned up temporary directory: {temp_dir}")


if __name__ == "__main__":
    asyncio.run(main())
