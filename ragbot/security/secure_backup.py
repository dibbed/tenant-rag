"""
Secure Backup System for RAG System

This module provides comprehensive backup and restore capabilities with
encryption, compression, and integrity verification.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json
import os
import shutil
import tarfile
import time
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.security.encryption import EncryptionManager
from ragbot.security.key_manager import KeyManager, KeyType


class BackupStatus(Enum):
    """Backup operation status"""

    CREATING = "creating"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"


class BackupType(Enum):
    """Backup types"""

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"


@dataclass
class BackupResult:
    """Backup operation result"""

    backup_id: str
    backup_path: str
    status: BackupStatus
    created_at: datetime
    file_size: int
    compression_ratio: float
    encryption_key_id: str
    vector_stores_backed_up: List[str]
    errors: Optional[List[str]] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class RestoreResult:
    """Restore operation result"""

    restore_id: str
    status: str
    restored_stores: List[str]
    restored_documents: int
    restore_time: float
    errors: Optional[List[str]] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class VerificationResult:
    """Backup verification result"""

    is_valid: bool
    checksum_match: bool
    signature_valid: bool
    corruption_check: bool
    errors: Optional[List[str]] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class SecureBackupManager:
    """
    Comprehensive secure backup manager

    Provides encrypted backup and restore capabilities for vector stores
    with compression, integrity verification, and metadata tracking.
    """

    def __init__(self, encryption_manager: Optional[EncryptionManager] = None):
        """
        Initialize secure backup manager

        Args:
            encryption_manager: Encryption manager instance
        """
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.key_manager = KeyManager()

        self.backup_dir = Path(settings.data_dir) / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.temp_dir = self.backup_dir / "temp"
        self.temp_dir.mkdir(exist_ok=True)

        self.metadata_db = self.backup_dir / "backup_metadata.db"
        self._initialize_metadata_db()

        logger.info(
            f"SecureBackupManager initialized with backup dir: {self.backup_dir}"
        )

    async def create_encrypted_backup(
        self,
        vector_stores: List[Any],
        backup_name: Optional[str] = None,
        backup_type: BackupType = BackupType.FULL,
        compression: bool = True,
        verify_after: bool = True,
    ) -> BackupResult:
        """
        Create encrypted backup of vector stores

        Args:
            vector_stores: List of vector stores to backup
            backup_name: Custom backup name
            backup_type: Type of backup
            compression: Enable compression
            verify_after: Verify backup after creation

        Returns:
            Backup result with operation details
        """
        backup_id = self._generate_backup_id()

        try:
            # Create backup filename
            if backup_name:
                backup_filename = (
                    f"{backup_name}_{backup_id}.tar.gz"
                    if compression
                    else f"{backup_name}_{backup_id}.tar"
                )
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = (
                    f"backup_{timestamp}_{backup_id}.tar.gz"
                    if compression
                    else f"backup_{timestamp}_{backup_id}.tar"
                )

            backup_path = self.backup_dir / backup_filename

            # Get encryption key
            encryption_key = await self.key_manager.retrieve_key("backup_key")
            if not encryption_key:
                encryption_key = await self.key_manager.generate_key(
                    KeyType.BACKUP, algorithm="AES-256-GCM"
                )

            # Create encrypted backup archive
            await self._create_encrypted_backup_archive(
                vector_stores, backup_path, encryption_key, compression
            )

            # Calculate statistics
            file_size = backup_path.stat().st_size

            # Verify backup
            if verify_after:
                verification_result = await self.verify_backup_integrity(
                    str(backup_path)
                )
                status = (
                    BackupStatus.VERIFIED
                    if verification_result.is_valid
                    else BackupStatus.FAILED
                )
            else:
                status = BackupStatus.COMPLETED

            # Record metadata
            await self._record_backup_metadata(
                backup_id, backup_path, encryption_key.key_id, vector_stores, file_size
            )

            return BackupResult(
                backup_id=backup_id,
                backup_path=str(backup_path),
                status=status,
                created_at=datetime.now(),
                file_size=file_size,
                compression_ratio=0.75,  # Estimate
                encryption_key_id=encryption_key.key_id,
                vector_stores_backed_up=[
                    store.get_store_type() for store in vector_stores
                ],
            )

        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            return BackupResult(
                backup_id=backup_id,
                backup_path="",
                status=BackupStatus.FAILED,
                created_at=datetime.now(),
                file_size=0,
                compression_ratio=0.0,
                encryption_key_id="",
                vector_stores_backed_up=[],
                errors=[str(e)],
            )

    async def restore_from_backup(
        self,
        backup_path: str,
        target_stores: Optional[List[Any]] = None,
        verify_before: bool = True,
    ) -> RestoreResult:
        """
        Restore vector stores from encrypted backup

        Args:
            backup_path: Path to backup file
            target_stores: Target vector stores for restoration
            verify_before: Verify backup before restoration

        Returns:
            Restore result with operation details
        """
        start_time = time.time()
        restore_id = self._generate_restore_id()

        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_path}")

            # Verify backup if requested
            if verify_before:
                verification_result = await self.verify_backup_integrity(backup_path)
                if not verification_result.is_valid:
                    raise ValueError(
                        f"Backup verification failed: {verification_result.errors}"
                    )

            # Get backup metadata
            backup_metadata = await self._get_backup_metadata(backup_file.name)
            if not backup_metadata:
                raise ValueError("Backup metadata not found")

            # Get encryption key
            encryption_key = await self.key_manager.retrieve_key(
                backup_metadata["encryption_key_id"]
            )
            if not encryption_key:
                raise ValueError(
                    f"Encryption key not found: {backup_metadata['encryption_key_id']}"
                )

            # Restore from backup
            restored_stores = await self._restore_from_archive(
                backup_file, encryption_key, target_stores
            )

            restore_time = time.time() - start_time

            # Log restoration
            await self._log_restore_operation(
                restore_id, backup_path, restored_stores, restore_time
            )

            return RestoreResult(
                restore_id=restore_id,
                status="completed",
                restored_stores=restored_stores,
                restored_documents=0,  # Should be calculated during restoration
                restore_time=restore_time,
            )

        except Exception as e:
            logger.error(f"Restore operation failed: {e}")
            return RestoreResult(
                restore_id=restore_id,
                status="failed",
                restored_stores=[],
                restored_documents=0,
                restore_time=time.time() - start_time,
                errors=[str(e)],
            )

    async def verify_backup_integrity(self, backup_path: str) -> VerificationResult:
        """
        Verify backup integrity and authenticity

        Args:
            backup_path: Path to backup file

        Returns:
            Verification result with detailed status
        """
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                return VerificationResult(
                    is_valid=False,
                    checksum_match=False,
                    signature_valid=False,
                    corruption_check=False,
                    errors=["Backup file not found"],
                )

            # Calculate checksum
            calculated_checksum = await self._calculate_file_checksum(backup_file)

            # Get stored checksum from metadata
            backup_metadata = await self._get_backup_metadata(backup_file.name)
            stored_checksum = (
                backup_metadata.get("checksum") if backup_metadata else None
            )

            # Verify checksum
            checksum_match = calculated_checksum == stored_checksum

            # Check for corruption (basic file structure check)
            corruption_check = await self._check_backup_corruption(backup_file)

            # Signature verification using encryption manager
            signature_valid = await self._verify_backup_signature(backup_file)

            is_valid = checksum_match and corruption_check and signature_valid

            return VerificationResult(
                is_valid=is_valid,
                checksum_match=checksum_match,
                signature_valid=signature_valid,
                corruption_check=corruption_check,
                errors=[] if is_valid else ["Backup verification failed"],
            )

        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return VerificationResult(
                is_valid=False,
                checksum_match=False,
                signature_valid=False,
                corruption_check=False,
                errors=[str(e)],
            )

    async def list_backups(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List available backups

        Args:
            limit: Maximum number of backups to return

        Returns:
            List of backup information dictionaries
        """
        with sqlite3.connect(self.metadata_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM backup_metadata
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (limit,),
            )

            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]

            backups = []
            for row in rows:
                backup_dict = dict(zip(columns, row))
                # Add file existence check
                backup_path = Path(backup_dict["backup_path"])
                backup_dict["file_exists"] = backup_path.exists()
                backup_dict["file_size"] = (
                    backup_path.stat().st_size if backup_path.exists() else 0
                )
                backups.append(backup_dict)

            return backups

    async def delete_backup(self, backup_id: str) -> bool:
        """
        Delete backup and its metadata

        Args:
            backup_id: Backup identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get backup metadata
            backup_metadata = await self._get_backup_metadata_by_id(backup_id)
            if not backup_metadata:
                return False

            # Delete backup file
            backup_path = Path(backup_metadata["backup_path"])
            if backup_path.exists():
                backup_path.unlink()

            # Delete metadata
            with sqlite3.connect(self.metadata_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM backup_metadata WHERE backup_id = ?", (backup_id,)
                )
                conn.commit()

            logger.info(f"Backup {backup_id} deleted successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to delete backup {backup_id}: {e}")
            return False

    async def _create_encrypted_backup_archive(
        self,
        vector_stores: List[Any],
        backup_path: Path,
        encryption_key: Any,
        compression: bool,
    ):
        """Create encrypted backup archive"""
        temp_backup_dir = self.temp_dir / f"backup_{int(time.time())}"
        temp_backup_dir.mkdir(exist_ok=True)

        try:
            # Export data from each vector store
            for store in vector_stores:
                store_type = store.get_store_type()
                store_backup_dir = temp_backup_dir / store_type
                store_backup_dir.mkdir(exist_ok=True)

                # Export documents
                documents = await store.get_all_documents()
                documents_file = store_backup_dir / "documents.json"

                with open(documents_file, "w") as f:
                    json.dump([doc.to_dict() for doc in documents], f, indent=2)

                # Export metadata
                metadata = {
                    "store_type": store_type,
                    "document_count": len(documents),
                    "exported_at": datetime.now().isoformat(),
                }

                metadata_file = store_backup_dir / "metadata.json"
                with open(metadata_file, "w") as f:
                    json.dump(metadata, f, indent=2)

            # Create archive
            mode = "w:gz" if compression else "w"
            with tarfile.open(backup_path, mode) as tar:
                tar.add(temp_backup_dir, arcname="backup")

            # Encrypt the archive
            await self._encrypt_backup_file(backup_path, encryption_key)

        finally:
            # Cleanup temp directory
            if temp_backup_dir.exists():
                shutil.rmtree(temp_backup_dir)

    async def _restore_from_archive(
        self,
        backup_file: Path,
        encryption_key: Any,
        target_stores: Optional[List[Any]],
    ) -> List[str]:
        """Restore from backup archive"""
        # Decrypt backup file
        decrypted_backup = await self._decrypt_backup_file(backup_file, encryption_key)

        temp_restore_dir = self.temp_dir / f"restore_{int(time.time())}"
        temp_restore_dir.mkdir(exist_ok=True)

        try:
            # Extract archive
            with tarfile.open(decrypted_backup, "r:*") as tar:
                tar.extractall(temp_restore_dir)

            # Restore each store
            restored_stores = []
            backup_dir = temp_restore_dir / "backup"

            if backup_dir.exists():
                for store_dir in backup_dir.iterdir():
                    if store_dir.is_dir():
                        store_type = store_dir.name

                        # Find target store
                        target_store = None
                        if target_stores:
                            for store in target_stores:
                                if store.get_store_type() == store_type:
                                    target_store = store
                                    break

                        if target_store:
                            # Restore documents
                            documents_file = store_dir / "documents.json"
                            if documents_file.exists():
                                with open(documents_file, "r") as f:
                                    documents_data = json.load(f)

                                # Convert back to VectorDocument objects
                                from ragbot.rag.store.base import VectorDocument

                                documents = [
                                    VectorDocument.from_dict(doc)
                                    for doc in documents_data
                                ]

                                # Add documents to store
                                await target_store.add_documents(documents)
                                restored_stores.append(store_type)

            return restored_stores

        finally:
            # Cleanup
            if temp_restore_dir.exists():
                shutil.rmtree(temp_restore_dir)
            if decrypted_backup.exists():
                decrypted_backup.unlink()

    async def _encrypt_backup_file(self, backup_path: Path, encryption_key: Any):
        """Encrypt backup file"""
        # Read backup file
        with open(backup_path, "rb") as f:
            backup_data = f.read()

        # Encrypt data
        encrypted_data = await self.encryption_manager._encrypt_data(
            backup_data, encryption_key
        )

        # Write encrypted backup
        encrypted_backup_path = backup_path.with_suffix(".encrypted")
        with open(encrypted_backup_path, "wb") as f:
            f.write(encrypted_data["data"])

        # Replace original with encrypted version
        backup_path.unlink()
        encrypted_backup_path.rename(backup_path)

    async def _decrypt_backup_file(
        self, backup_path: Path, encryption_key: Any
    ) -> Path:
        """Decrypt backup file"""
        # Read encrypted backup
        with open(backup_path, "rb") as f:
            encrypted_data = f.read()

        # Decrypt data
        decrypted_data = await self.encryption_manager._decrypt_data(
            encrypted_data, encryption_key
        )

        # Write decrypted backup
        decrypted_backup_path = self.temp_dir / f"decrypted_{backup_path.name}"
        with open(decrypted_backup_path, "wb") as f:
            f.write(decrypted_data)

        return decrypted_backup_path

    async def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    async def _check_backup_corruption(self, backup_path: Path) -> bool:
        """Check for backup file corruption"""
        try:
            # Try to open as tar file
            with tarfile.open(backup_path, "r:*") as tar:
                # Try to list contents
                tar.getnames()
            return True
        except Exception:
            return False

    def _generate_backup_id(self) -> str:
        """Generate unique backup identifier"""
        timestamp = str(int(time.time()))
        random_bytes = os.urandom(4)
        return hashlib.sha256(timestamp.encode() + random_bytes).hexdigest()[:12]

    def _generate_restore_id(self) -> str:
        """Generate unique restore identifier"""
        timestamp = str(int(time.time()))
        random_bytes = os.urandom(4)
        return hashlib.sha256(timestamp.encode() + random_bytes).hexdigest()[:12]

    def _initialize_metadata_db(self):
        """Initialize backup metadata database"""
        with sqlite3.connect(self.metadata_db) as conn:
            cursor = conn.cursor()

            # Backup metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backup_metadata (
                    backup_id TEXT PRIMARY KEY,
                    backup_name TEXT,
                    backup_path TEXT NOT NULL,
                    backup_type TEXT NOT NULL,
                    encryption_key_id TEXT NOT NULL,
                    file_size INTEGER,
                    checksum TEXT,
                    compression_ratio REAL,
                    vector_stores TEXT,
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'completed'
                )
            """)

            # Restore operations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS restore_operations (
                    restore_id TEXT PRIMARY KEY,
                    backup_id TEXT NOT NULL,
                    backup_path TEXT NOT NULL,
                    restored_stores TEXT,
                    restore_time REAL,
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'completed'
                )
            """)

            conn.commit()

    async def _record_backup_metadata(
        self,
        backup_id: str,
        backup_path: Path,
        encryption_key_id: str,
        vector_stores: List[Any],
        file_size: int,
    ):
        """Record backup metadata in database"""
        # Calculate checksum
        checksum = await self._calculate_file_checksum(backup_path)

        with sqlite3.connect(self.metadata_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO backup_metadata (
                    backup_id, backup_path, encryption_key_id, file_size,
                    checksum, vector_stores, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    backup_id,
                    str(backup_path),
                    encryption_key_id,
                    file_size,
                    checksum,
                    json.dumps([store.get_store_type() for store in vector_stores]),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()

    async def _get_backup_metadata(
        self, backup_filename: str
    ) -> Optional[Dict[str, Any]]:
        """Get backup metadata by filename"""
        with sqlite3.connect(self.metadata_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM backup_metadata
                WHERE backup_path LIKE ?
            """,
                (f"%{backup_filename}",),
            )

            row = cursor.fetchone()
            if not row:
                return None

            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))

    async def _get_backup_metadata_by_id(
        self, backup_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get backup metadata by ID"""
        with sqlite3.connect(self.metadata_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM backup_metadata WHERE backup_id = ?
            """,
                (backup_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))

    async def _log_restore_operation(
        self,
        restore_id: str,
        backup_path: str,
        restored_stores: List[str],
        restore_time: float,
    ):
        """Log restore operation in database"""
        with sqlite3.connect(self.metadata_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO restore_operations (
                    restore_id, backup_path, restored_stores,
                    restore_time, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """,
                (
                    restore_id,
                    backup_path,
                    json.dumps(restored_stores),
                    restore_time,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()

    async def _verify_backup_signature(self, backup_file: Path) -> bool:
        """
        Verify backup signature using encryption manager.

        Args:
            backup_file: Path to backup file

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Get backup metadata to find encryption key
            backup_metadata = await self._get_backup_metadata(backup_file.name)
            if not backup_metadata:
                logger.warning(f"No metadata found for backup {backup_file.name}")
                return False

            encryption_key_id = backup_metadata.get("encryption_key_id")
            if not encryption_key_id:
                logger.warning(
                    f"No encryption key ID found for backup {backup_file.name}"
                )
                return False

            # Retrieve encryption key
            encryption_key = await self.key_manager.retrieve_key(encryption_key_id)
            if not encryption_key:
                logger.error(f"Encryption key {encryption_key_id} not found")
                return False

            # Read backup file
            with open(backup_file, "rb") as f:
                backup_data = f.read()

            # Extract signature from backup data (last 256 bytes)
            if len(backup_data) < 256:
                logger.error("Backup file too small to contain signature")
                return False

            signature = backup_data[-256:]
            data_without_signature = backup_data[:-256]

            # Verify signature using encryption manager
            try:
                # Use encryption manager to verify signature
                verification_result = await self.encryption_manager.verify_signature(
                    data_without_signature, signature, encryption_key.key_data
                )
                return verification_result
            except Exception as e:
                logger.error(f"Signature verification failed: {e}")
                return False

        except Exception as e:
            logger.error(f"Error verifying backup signature: {e}")
            return False
