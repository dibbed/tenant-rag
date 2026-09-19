"""
Key Management System for RAG System

This module provides comprehensive key management capabilities including
key generation, storage, rotation, and lifecycle management.
"""

from typing import Dict, List, Any, Optional
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import os
import sqlite3
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.fernet import Fernet

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.security.encryption import EncryptionKey, EncryptionAlgorithm


class KeyType(Enum):
    """Key types for different purposes"""

    MASTER = "master"
    DATA = "data"
    ENCRYPTION = "encryption"
    DECRYPTION = "decryption"
    SIGNING = "signing"
    VERIFICATION = "verification"
    BACKUP = "backup"


class KeyStatus(Enum):
    """Key status states"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"
    COMPROMISED = "compromised"


@dataclass
class KeyPolicy:
    """Key management policy"""

    key_type: KeyType
    algorithm: str
    key_size: int
    expiration_days: int
    rotation_interval_days: int
    max_documents_per_key: int
    require_backup: bool = True
    allow_export: bool = False


class KeyManager:
    """
    Comprehensive key management system

    Provides key generation, storage, rotation, and lifecycle management
    with secure storage and audit capabilities.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize key manager

        Args:
            storage_path: Custom storage path for keys
        """
        self.storage_path = Path(storage_path or settings.data_dir / "keys")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.db_path = self.storage_path / "key_manager.db"
        self.key_path = self.storage_path / "keystore"
        self.key_path.mkdir(exist_ok=True)

        # Key cache for performance
        self._key_cache: Dict[str, EncryptionKey] = {}
        self._cache_ttl = 3600  # 1 hour

        # Policies
        self.policies = self._load_default_policies()

        # Initialize database
        self._initialize_database()

        logger.info(f"KeyManager initialized with storage at {self.storage_path}")

    @contextmanager
    def _get_connection(self):
        """Get managed SQLite connection guaranteeing close() on block exit."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    async def generate_key(
        self,
        key_type: KeyType,
        algorithm: str = "AES-256",
        key_size: Optional[int] = None,
        expires_in_days: Optional[int] = None,
    ) -> EncryptionKey:
        """
        Generate new encryption key

        Args:
            key_type: Type of key to generate
            algorithm: Encryption algorithm
            key_size: Key size in bits
            expires_in_days: Key expiration in days

        Returns:
            Generated encryption key

        Raises:
            ValueError: If algorithm is not supported
        """
        key_id = self._generate_key_id()

        # Get policy for key type
        policy = self.policies.get(key_type.value)
        if policy:
            algorithm = algorithm or policy.algorithm
            key_size = key_size or policy.key_size
            expires_in_days = expires_in_days or policy.expiration_days
        else:
            key_size = key_size or 256
            expires_in_days = expires_in_days or 365

        # Generate key based on algorithm
        if algorithm == "AES-256":
            key_data = os.urandom(32)  # 256 bits
            encryption_algorithm = EncryptionAlgorithm.AES_256_GCM
        elif algorithm == "AES-256-GCM":
            key_data = os.urandom(32)  # 256 bits
            encryption_algorithm = EncryptionAlgorithm.AES_256_GCM
        elif algorithm == "RSA-2048":
            key_data = self._generate_rsa_key(2048)
            encryption_algorithm = EncryptionAlgorithm.RSA_2048
        elif algorithm == "RSA-4096":
            key_data = self._generate_rsa_key(4096)
            encryption_algorithm = EncryptionAlgorithm.RSA_4096
        elif algorithm == "Fernet":
            key_data = Fernet.generate_key()
            encryption_algorithm = EncryptionAlgorithm.FERNET
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        # Create key object
        key_obj = EncryptionKey(
            key_id=key_id,
            algorithm=encryption_algorithm,
            key_data=key_data,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=expires_in_days),
            is_active=True,
        )

        # Store key securely
        await self._store_key_securely(key_obj)

        # Record in database
        await self._record_key_creation(key_obj, key_type, algorithm)

        # Cache key
        self._cache_key(key_obj)

        logger.info(f"Generated {algorithm} key {key_id} for type {key_type.value}")
        return key_obj

    async def store_key_securely(self, key: EncryptionKey) -> str:
        """
        Store encryption key securely

        Args:
            key: Encryption key to store

        Returns:
            Key identifier
        """
        return await self._store_key_securely(key)

    async def retrieve_key(self, key_id: str) -> Optional[EncryptionKey]:
        """
        Retrieve encryption key by ID

        Args:
            key_id: Key identifier

        Returns:
            Encryption key or None if not found

        Raises:
            ValueError: If key is revoked or compromised
        """
        # Check cache first
        cached_key = self._get_cached_key(key_id)
        if cached_key:
            return cached_key

        # Read from database
        key_info = await self._get_key_info(key_id)
        if not key_info:
            return None

        # Check key status
        if key_info["status"] in ["revoked", "compromised"]:
            raise ValueError(f"Key {key_id} has been {key_info['status']}")

        if key_info["status"] == "expired":
            if not await self._check_key_grace_period(key_id):
                raise ValueError(f"Key {key_id} has expired")

        # Read key from file
        key_data = await self._read_key_from_file(key_id)
        if not key_data:
            return None

        # Create key object
        key_obj = EncryptionKey(
            key_id=key_id,
            algorithm=EncryptionAlgorithm(key_info["algorithm"]),
            key_data=key_data,
            created_at=datetime.fromisoformat(key_info["created_at"]),
            expires_at=datetime.fromisoformat(key_info["expires_at"])
            if key_info["expires_at"]
            else None,
            is_active=key_info["status"] == "active",
        )

        # Cache key
        self._cache_key(key_obj)

        return key_obj

    async def revoke_key(self, key_id: str, reason: str = "Manual revocation") -> bool:
        """
        Revoke encryption key

        Args:
            key_id: Key identifier
            reason: Revocation reason

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if key exists
            key_info = await self._get_key_info(key_id)
            if not key_info:
                return False

            # Revoke key in database
            await self._update_key_status(key_id, KeyStatus.REVOKED)

            # Log revocation
            await self._log_key_action(key_id, "revoke", reason)

            # Remove from cache
            self._remove_from_cache(key_id)

            logger.warning(f"Key {key_id} revoked: {reason}")
            return True

        except Exception as e:
            await self._log_key_action(key_id, "revoke_failed", str(e))
            logger.error(f"Failed to revoke key {key_id}: {e}")
            return False

    async def rotate_key(
        self, key_id: str, new_algorithm: Optional[str] = None
    ) -> Optional[EncryptionKey]:
        """
        Rotate encryption key

        Args:
            key_id: Key identifier to rotate
            new_algorithm: New algorithm (optional)

        Returns:
            New encryption key or None if failed
        """
        try:
            # Get current key info
            key_info = await self._get_key_info(key_id)
            if not key_info:
                return None

            # Determine new algorithm
            if not new_algorithm:
                new_algorithm = key_info["algorithm"]

            # Generate new key
            key_type = KeyType(key_info["key_type"])
            new_key = await self.generate_key(
                key_type=key_type,
                algorithm=new_algorithm,
                key_size=key_info.get("key_size"),
            )

            # Record rotation
            await self._record_key_rotation(key_id, new_key.key_id)

            # Log rotation
            await self._log_key_action(key_id, "rotate", f"Rotated to {new_key.key_id}")

            logger.info(f"Key {key_id} rotated to {new_key.key_id}")
            return new_key

        except Exception as e:
            await self._log_key_action(key_id, "rotate_failed", str(e))
            logger.error(f"Failed to rotate key {key_id}: {e}")
            return None

    async def list_keys(
        self, key_type: Optional[KeyType] = None, status: Optional[KeyStatus] = None
    ) -> List[Dict[str, Any]]:
        """
        List encryption keys with optional filtering

        Args:
            key_type: Filter by key type
            status: Filter by key status

        Returns:
            List of key information dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM keys WHERE 1=1"
            params = []

            if key_type:
                query += " AND key_type = ?"
                params.append(key_type.value)

            if status:
                query += " AND status = ?"
                params.append(status.value)

            query += " ORDER BY created_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            columns = [description[0] for description in cursor.description]
            keys = []

            for row in rows:
                key_dict = dict(zip(columns, row))
                # Add additional info
                key_dict["is_expired"] = self._is_key_expired(key_dict["expires_at"])
                key_dict["days_until_expiry"] = self._days_until_expiry(
                    key_dict["expires_at"]
                )
                keys.append(key_dict)

            return keys

    async def get_key_statistics(self) -> Dict[str, Any]:
        """
        Get key management statistics

        Returns:
            Dictionary with key statistics
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total keys
            cursor.execute("SELECT COUNT(*) FROM keys")
            total_keys = cursor.fetchone()[0]

            # Active keys
            cursor.execute("SELECT COUNT(*) FROM keys WHERE status = 'active'")
            active_keys = cursor.fetchone()[0]

            # Expired keys
            cursor.execute("SELECT COUNT(*) FROM keys WHERE status = 'expired'")
            expired_keys = cursor.fetchone()[0]

            # Revoked keys
            cursor.execute("SELECT COUNT(*) FROM keys WHERE status = 'revoked'")
            revoked_keys = cursor.fetchone()[0]

            # Keys by type
            cursor.execute("SELECT key_type, COUNT(*) FROM keys GROUP BY key_type")
            keys_by_type = dict(cursor.fetchall())

            # Keys by algorithm
            cursor.execute("SELECT algorithm, COUNT(*) FROM keys GROUP BY algorithm")
            keys_by_algorithm = dict(cursor.fetchall())

            return {
                "total_keys": total_keys,
                "active_keys": active_keys,
                "expired_keys": expired_keys,
                "revoked_keys": revoked_keys,
                "keys_by_type": keys_by_type,
                "keys_by_algorithm": keys_by_algorithm,
                "cache_size": len(self._key_cache),
            }

    def _generate_key_id(self) -> str:
        """Generate unique key identifier"""
        timestamp = str(int(time.time()))
        random_bytes = os.urandom(8)
        return hashlib.sha256(timestamp.encode() + random_bytes).hexdigest()[:16]

    def _generate_rsa_key(self, key_size: int) -> bytes:
        """Generate RSA key pair"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
        )

        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

    def _load_default_policies(self) -> Dict[str, KeyPolicy]:
        """Load default key policies"""
        return {
            "master": KeyPolicy(
                key_type=KeyType.MASTER,
                algorithm="AES-256",
                key_size=256,
                expiration_days=365,
                rotation_interval_days=180,
                max_documents_per_key=float("inf"),
                require_backup=True,
                allow_export=False,
            ),
            "data": KeyPolicy(
                key_type=KeyType.DATA,
                algorithm="AES-256-GCM",
                key_size=256,
                expiration_days=90,
                rotation_interval_days=30,
                max_documents_per_key=100000,
                require_backup=True,
                allow_export=True,
            ),
            "encryption": KeyPolicy(
                key_type=KeyType.ENCRYPTION,
                algorithm="RSA-2048",
                key_size=2048,
                expiration_days=180,
                rotation_interval_days=60,
                max_documents_per_key=10000,
                require_backup=True,
                allow_export=False,
            ),
            "backup": KeyPolicy(
                key_type=KeyType.BACKUP,
                algorithm="AES-256-GCM",
                key_size=256,
                expiration_days=365,
                rotation_interval_days=90,
                max_documents_per_key=float("inf"),
                require_backup=True,
                allow_export=True,
            ),
        }

    def _initialize_database(self):
        """Initialize key management database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Keys table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS keys (
                    key_id TEXT PRIMARY KEY,
                    key_type TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    key_size INTEGER,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    last_used TEXT,
                    created_by TEXT DEFAULT 'system'
                )
            """)

            # Key rotations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS key_rotations (
                    rotation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    old_key_id TEXT NOT NULL,
                    new_key_id TEXT NOT NULL,
                    rotation_date TEXT NOT NULL,
                    reason TEXT
                )
            """)

            # Key actions log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS key_actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT NOT NULL,
                    user_id TEXT DEFAULT 'system'
                )
            """)

            conn.commit()

    async def _store_key_securely(self, key: EncryptionKey) -> str:
        """Store key securely in filesystem"""
        key_file = self.key_path / f"{key.key_id}.key"

        # Encrypt key data before storing
        encrypted_data = self._encrypt_key_data(key.key_data)

        with open(key_file, "wb") as f:
            f.write(encrypted_data)

        # Set restrictive permissions
        os.chmod(key_file, 0o600)

        return key.key_id

    async def _read_key_from_file(self, key_id: str) -> Optional[bytes]:
        """Read key from secure storage"""
        key_file = self.key_path / f"{key_id}.key"

        if not key_file.exists():
            return None

        try:
            with open(key_file, "rb") as f:
                encrypted_data = f.read()

            # Decrypt key data
            return self._decrypt_key_data(encrypted_data)
        except Exception as e:
            logger.error(f"Failed to read key {key_id}: {e}")
            return None

    def _encrypt_key_data(self, key_data: bytes) -> bytes:
        """Encrypt key data for storage"""
        # Simple XOR encryption for demonstration
        # In production, use proper encryption with master key
        master_key = b"master_key_32_bytes_long_12345"
        encrypted = bytearray()
        for i, byte in enumerate(key_data):
            encrypted.append(byte ^ master_key[i % len(master_key)])
        return bytes(encrypted)

    def _decrypt_key_data(self, encrypted_data: bytes) -> bytes:
        """Decrypt key data from storage"""
        # Simple XOR decryption for demonstration
        # In production, use proper decryption with master key
        master_key = b"master_key_32_bytes_long_12345"
        decrypted = bytearray()
        for i, byte in enumerate(encrypted_data):
            decrypted.append(byte ^ master_key[i % len(master_key)])
        return bytes(decrypted)

    async def _record_key_creation(
        self, key: EncryptionKey, key_type: KeyType, algorithm: str
    ):
        """Record key creation in database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO keys (key_id, key_type, algorithm, key_size, status, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    key.key_id,
                    key_type.value,
                    algorithm,
                    len(key.key_data) * 8,  # Convert bytes to bits
                    "active",
                    key.created_at.isoformat(),
                    key.expires_at.isoformat() if key.expires_at else None,
                ),
            )
            conn.commit()

    async def _get_key_info(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Get key information from database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM keys WHERE key_id = ?", (key_id,))
            row = cursor.fetchone()

            if not row:
                return None

            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))

    async def _update_key_status(self, key_id: str, status: KeyStatus):
        """Update key status in database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE keys SET status = ? WHERE key_id = ?
            """,
                (status.value, key_id),
            )
            conn.commit()

    async def _log_key_action(self, key_id: str, action: str, details: str):
        """Log key action in database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO key_actions (key_id, action, details, timestamp)
                VALUES (?, ?, ?, ?)
            """,
                (key_id, action, details, datetime.now().isoformat()),
            )
            conn.commit()

    async def _record_key_rotation(self, old_key_id: str, new_key_id: str):
        """Record key rotation in database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO key_rotations (old_key_id, new_key_id, rotation_date)
                VALUES (?, ?, ?)
            """,
                (old_key_id, new_key_id, datetime.now().isoformat()),
            )
            conn.commit()

    async def _check_key_grace_period(self, key_id: str) -> bool:
        """Check if key is within grace period after expiration"""
        # Implement grace period logic
        # For now, return False (no grace period)
        return False

    def _cache_key(self, key: EncryptionKey):
        """Cache key for performance"""
        self._key_cache[key.key_id] = key

    def _get_cached_key(self, key_id: str) -> Optional[EncryptionKey]:
        """Get key from cache"""
        return self._key_cache.get(key_id)

    def _remove_from_cache(self, key_id: str):
        """Remove key from cache"""
        self._key_cache.pop(key_id, None)

    def _is_key_expired(self, expires_at: Optional[str]) -> bool:
        """Check if key is expired"""
        if not expires_at:
            return False
        return datetime.now() > datetime.fromisoformat(expires_at)

    def _days_until_expiry(self, expires_at: Optional[str]) -> int:
        """Get days until key expires"""
        if not expires_at:
            return float("inf")
        delta = datetime.fromisoformat(expires_at) - datetime.now()
        return max(0, delta.days)
