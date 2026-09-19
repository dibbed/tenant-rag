"""
Encryption Manager for RAG System

This module provides comprehensive encryption capabilities for vector documents,
embeddings, and metadata using various encryption algorithms.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import os
import time
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

from ragbot.outputs.logger import logger


class EncryptionAlgorithm(Enum):
    """Encryption algorithms supported by the system"""

    AES_256_GCM = "aes_256_gcm"
    RSA_2048 = "rsa_2048"
    RSA_4096 = "rsa_4096"
    FERNET = "fernet"


class EncryptionMode(Enum):
    """Encryption modes"""

    SYMMETRIC = "symmetric"
    ASYMMETRIC = "asymmetric"
    HYBRID = "hybrid"


@dataclass
class EncryptedDocument:
    """Encrypted document structure"""

    document_id: str
    encrypted_content: bytes
    encrypted_metadata: bytes
    encrypted_embeddings: bytes
    encryption_algorithm: EncryptionAlgorithm
    key_id: str
    iv: Optional[bytes] = None
    tag: Optional[bytes] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class KeyRotationResult:
    """Key rotation operation result"""

    old_key_id: str
    new_key_id: str
    documents_rotated: int
    rotation_time: float
    success: bool
    errors: Optional[List[str]] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class EncryptionKey:
    """Encryption key structure"""

    key_id: str
    algorithm: EncryptionAlgorithm
    key_data: bytes
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True

    def is_expired(self) -> bool:
        """Check if key is expired"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def days_until_expiry(self) -> int:
        """Get days until key expires"""
        if self.expires_at is None:
            return float("inf")
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)


class EncryptionManager:
    """
    Comprehensive encryption manager for RAG system

    Provides encryption/decryption capabilities for documents, embeddings,
    and metadata using various encryption algorithms with key management.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize encryption manager

        Args:
            config: Configuration dictionary with encryption settings
        """
        self.config = config or {}
        self.keys: Dict[str, EncryptionKey] = {}
        self.active_key_id: Optional[str] = None
        self.encryption_mode = EncryptionMode(self.config.get("mode", "symmetric"))
        self.algorithm = EncryptionAlgorithm(
            self.config.get("algorithm", "aes_256_gcm")
        )

        # Initialize default key
        self._initialize_default_key()
        logger.info(f"EncryptionManager initialized with {self.algorithm.value}")

    async def encrypt_document(self, document: Any) -> EncryptedDocument:
        """
        Encrypt complete document including content, metadata, and embeddings

        Args:
            document: Vector document to encrypt

        Returns:
            Encrypted document structure

        Raises:
            ValueError: If no active encryption key is available
        """
        if not self.active_key_id:
            raise ValueError("No active encryption key available")

        key = self.keys[self.active_key_id]

        try:
            # Encrypt content
            content_bytes = document.content.encode("utf-8")
            encrypted_content = await self._encrypt_data(content_bytes, key)

            # Encrypt metadata
            metadata_bytes = json.dumps(document.metadata).encode("utf-8")
            encrypted_metadata = await self._encrypt_data(metadata_bytes, key)

            # Encrypt embeddings
            embeddings_bytes = json.dumps(document.embedding).encode("utf-8")
            encrypted_embeddings = await self._encrypt_data(embeddings_bytes, key)

            # Bundle IV and tag for metadata and embeddings for AES-GCM
            if key.algorithm == EncryptionAlgorithm.AES_256_GCM:
                meta_data = (
                    encrypted_metadata.get("iv", b"")
                    + encrypted_metadata.get("tag", b"")
                    + encrypted_metadata["data"]
                )
                emb_data = (
                    encrypted_embeddings.get("iv", b"")
                    + encrypted_embeddings.get("tag", b"")
                    + encrypted_embeddings["data"]
                )
            else:
                meta_data = encrypted_metadata["data"]
                emb_data = encrypted_embeddings["data"]

            encrypted_doc = EncryptedDocument(
                document_id=document.id,
                encrypted_content=encrypted_content["data"],
                encrypted_metadata=meta_data,
                encrypted_embeddings=emb_data,
                encryption_algorithm=self.algorithm,
                key_id=self.active_key_id,
                iv=encrypted_content.get("iv"),
                tag=encrypted_content.get("tag"),
                timestamp=datetime.now(),
            )

            logger.debug(f"Document {document.id} encrypted successfully")
            return encrypted_doc

        except Exception as e:
            logger.error(f"Failed to encrypt document {document.id}: {e}")
            raise

    async def decrypt_document(self, encrypted_doc: EncryptedDocument) -> Any:
        """
        Decrypt encrypted document back to original format

        Args:
            encrypted_doc: Encrypted document to decrypt

        Returns:
            Original vector document

        Raises:
            ValueError: If encryption key is not found
        """
        if encrypted_doc.key_id not in self.keys:
            raise ValueError(f"Encryption key {encrypted_doc.key_id} not found")

        key = self.keys[encrypted_doc.key_id]

        try:
            # Decrypt content
            decrypted_content = await self._decrypt_data(
                encrypted_doc.encrypted_content,
                key,
                iv=encrypted_doc.iv,
                tag=encrypted_doc.tag,
            )
            content = decrypted_content.decode("utf-8")

            # Decrypt metadata
            if (
                key.algorithm == EncryptionAlgorithm.AES_256_GCM
                and len(encrypted_doc.encrypted_metadata) >= 28
            ):
                meta_iv = encrypted_doc.encrypted_metadata[:12]
                meta_tag = encrypted_doc.encrypted_metadata[12:28]
                meta_ciphertext = encrypted_doc.encrypted_metadata[28:]
                decrypted_metadata = await self._decrypt_aes_gcm(
                    meta_ciphertext, key, meta_iv, meta_tag
                )
            else:
                decrypted_metadata = await self._decrypt_data(
                    encrypted_doc.encrypted_metadata,
                    key,
                    iv=encrypted_doc.iv,
                    tag=encrypted_doc.tag,
                )
            metadata = json.loads(decrypted_metadata.decode("utf-8"))

            # Decrypt embeddings
            if (
                key.algorithm == EncryptionAlgorithm.AES_256_GCM
                and len(encrypted_doc.encrypted_embeddings) >= 28
            ):
                emb_iv = encrypted_doc.encrypted_embeddings[:12]
                emb_tag = encrypted_doc.encrypted_embeddings[12:28]
                emb_ciphertext = encrypted_doc.encrypted_embeddings[28:]
                decrypted_embeddings = await self._decrypt_aes_gcm(
                    emb_ciphertext, key, emb_iv, emb_tag
                )
            else:
                decrypted_embeddings = await self._decrypt_data(
                    encrypted_doc.encrypted_embeddings,
                    key,
                    iv=encrypted_doc.iv,
                    tag=encrypted_doc.tag,
                )
            embedding = json.loads(decrypted_embeddings.decode("utf-8"))

            # Create original document
            from ragbot.rag.store.base import VectorDocument

            document = VectorDocument(
                id=encrypted_doc.document_id,
                content=content,
                embedding=embedding,
                metadata=metadata,
            )

            logger.debug(f"Document {encrypted_doc.document_id} decrypted successfully")
            return document

        except Exception as e:
            logger.error(f"Failed to decrypt document {encrypted_doc.document_id}: {e}")
            raise

    async def encrypt_embeddings(
        self, embeddings: List[float]
    ) -> Tuple[bytes, Optional[bytes], Optional[bytes]]:
        """
        Encrypt embeddings vector

        Args:
            embeddings: List of embedding values

        Returns:
            Tuple of (encrypted_data, iv, tag)

        Raises:
            ValueError: If no active encryption key is available
        """
        if not self.active_key_id:
            raise ValueError("No active encryption key available")

        key = self.keys[self.active_key_id]
        embeddings_bytes = json.dumps(embeddings).encode("utf-8")

        result = await self._encrypt_data(embeddings_bytes, key)
        return result["data"], result.get("iv"), result.get("tag")

    async def decrypt_embeddings(
        self,
        encrypted_embeddings: bytes,
        iv: Optional[bytes] = None,
        tag: Optional[bytes] = None,
    ) -> List[float]:
        """
        Decrypt embeddings back to original format

        Args:
            encrypted_embeddings: Encrypted embeddings as bytes
            iv: Initialization vector (for AES-GCM)
            tag: Authentication tag (for AES-GCM)

        Returns:
            Original embeddings list

        Raises:
            ValueError: If no active encryption key is available
        """
        if not self.active_key_id:
            raise ValueError("No active encryption key available")

        key = self.keys[self.active_key_id]
        decrypted_bytes = await self._decrypt_data(encrypted_embeddings, key, iv, tag)

        return json.loads(decrypted_bytes.decode("utf-8"))

    async def rotate_encryption_keys(self) -> KeyRotationResult:
        """
        Rotate encryption keys for enhanced security

        Returns:
            Key rotation result with operation details
        """
        start_time = time.time()
        old_key_id = self.active_key_id
        errors = []

        try:
            # Generate new key
            new_key = await self._generate_new_key()
            new_key_id = new_key.key_id

            # Store new key
            self.keys[new_key_id] = new_key

            # Activate new key
            self.active_key_id = new_key_id

            # Deactivate old key
            if old_key_id and old_key_id in self.keys:
                self.keys[old_key_id].is_active = False

            rotation_time = time.time() - start_time

            logger.info(f"Key rotation completed: {old_key_id} -> {new_key_id}")

            return KeyRotationResult(
                old_key_id=old_key_id or "",
                new_key_id=new_key_id,
                documents_rotated=0,  # Should be retrieved from vector store
                rotation_time=rotation_time,
                success=True,
                errors=errors,
            )

        except Exception as e:
            errors.append(str(e))
            logger.error(f"Key rotation failed: {e}")
            return KeyRotationResult(
                old_key_id=old_key_id or "",
                new_key_id="",
                documents_rotated=0,
                rotation_time=time.time() - start_time,
                success=False,
                errors=errors,
            )

    async def _encrypt_data(self, data: bytes, key: EncryptionKey) -> Dict[str, bytes]:
        """Encrypt data using specified key and algorithm"""
        if key.algorithm == EncryptionAlgorithm.FERNET:
            return await self._encrypt_fernet(data, key)
        elif key.algorithm == EncryptionAlgorithm.AES_256_GCM:
            return await self._encrypt_aes_gcm(data, key)
        else:
            raise ValueError(f"Unsupported encryption algorithm: {key.algorithm}")

    async def _decrypt_data(
        self,
        encrypted_data: bytes,
        key: EncryptionKey,
        iv: Optional[bytes] = None,
        tag: Optional[bytes] = None,
    ) -> bytes:
        """Decrypt data using specified key and algorithm"""
        if key.algorithm == EncryptionAlgorithm.FERNET:
            return await self._decrypt_fernet(encrypted_data, key)
        elif key.algorithm == EncryptionAlgorithm.AES_256_GCM:
            return await self._decrypt_aes_gcm(encrypted_data, key, iv, tag)
        else:
            raise ValueError(f"Unsupported encryption algorithm: {key.algorithm}")

    async def _encrypt_fernet(
        self, data: bytes, key: EncryptionKey
    ) -> Dict[str, bytes]:
        """Encrypt data using Fernet symmetric encryption"""
        fernet = Fernet(key.key_data)
        encrypted = fernet.encrypt(data)
        return {"data": encrypted}

    async def _decrypt_fernet(self, encrypted_data: bytes, key: EncryptionKey) -> bytes:
        """Decrypt data using Fernet symmetric encryption"""
        fernet = Fernet(key.key_data)
        return fernet.decrypt(encrypted_data)

    async def _encrypt_aes_gcm(
        self, data: bytes, key: EncryptionKey
    ) -> Dict[str, bytes]:
        """Encrypt data using AES-256-GCM"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        # Generate random IV
        iv = os.urandom(12)  # 96-bit IV for GCM

        # Encrypt
        aesgcm = AESGCM(key.key_data)
        encrypted_data = aesgcm.encrypt(iv, data, None)

        # Separate ciphertext and tag
        ciphertext = encrypted_data[:-16]
        tag = encrypted_data[-16:]

        return {"data": ciphertext, "iv": iv, "tag": tag}

    async def _decrypt_aes_gcm(
        self, encrypted_data: bytes, key: EncryptionKey, iv: bytes, tag: bytes
    ) -> bytes:
        """Decrypt data using AES-256-GCM"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        if not iv or not tag:
            raise ValueError("IV and tag are required for AES-GCM decryption")

        # Combine ciphertext and tag
        combined_data = encrypted_data + tag

        # Decrypt
        aesgcm = AESGCM(key.key_data)
        return aesgcm.decrypt(iv, combined_data, None)

    async def _generate_new_key(self) -> EncryptionKey:
        """Generate new encryption key"""
        key_id = self._generate_key_id()

        if self.algorithm == EncryptionAlgorithm.FERNET:
            key_data = Fernet.generate_key()
        elif self.algorithm == EncryptionAlgorithm.AES_256_GCM:
            key_data = os.urandom(32)  # 256-bit key
        else:
            raise ValueError(f"Unsupported algorithm: {self.algorithm}")

        return EncryptionKey(
            key_id=key_id,
            algorithm=self.algorithm,
            key_data=key_data,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=365),  # 1 year
            is_active=True,
        )

    def _generate_key_id(self) -> str:
        """Generate unique key identifier"""
        timestamp = str(int(time.time()))
        random_bytes = os.urandom(8)
        return hashlib.sha256(timestamp.encode() + random_bytes).hexdigest()[:16]

    def _initialize_default_key(self):
        """Initialize default encryption key"""
        if not self.keys:
            # Generate default key
            key_id = self._generate_key_id()

            if self.algorithm == EncryptionAlgorithm.FERNET:
                key_data = Fernet.generate_key()
            elif self.algorithm == EncryptionAlgorithm.AES_256_GCM:
                key_data = os.urandom(32)
            else:
                key_data = os.urandom(32)  # fallback

            default_key = EncryptionKey(
                key_id=key_id,
                algorithm=self.algorithm,
                key_data=key_data,
                created_at=datetime.now(),
                is_active=True,
            )

            self.keys[key_id] = default_key
            self.active_key_id = key_id

    def get_key_info(self, key_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific key

        Args:
            key_id: Key identifier

        Returns:
            Key information dictionary or None if not found
        """
        if key_id not in self.keys:
            return None

        key = self.keys[key_id]
        return {
            "key_id": key.key_id,
            "algorithm": key.algorithm.value,
            "created_at": key.created_at.isoformat(),
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "is_active": key.is_active,
            "is_expired": key.is_expired(),
            "days_until_expiry": key.days_until_expiry(),
        }

    def list_keys(self) -> List[Dict[str, Any]]:
        """
        List all available encryption keys

        Returns:
            List of key information dictionaries
        """
        return [self.get_key_info(key_id) for key_id in self.keys.keys()]

    def get_active_key_id(self) -> Optional[str]:
        """Get the currently active key ID"""
        return self.active_key_id

    def set_active_key(self, key_id: str) -> bool:
        """
        Set active encryption key

        Args:
            key_id: Key identifier to activate

        Returns:
            True if successful, False otherwise
        """
        if key_id not in self.keys:
            logger.error(f"Key {key_id} not found")
            return False

        if not self.keys[key_id].is_active:
            logger.error(f"Key {key_id} is not active")
            return False

        if self.keys[key_id].is_expired():
            logger.error(f"Key {key_id} is expired")
            return False

        self.active_key_id = key_id
        logger.info(f"Active key set to {key_id}")
        return True

    def get_encryption_stats(self) -> Dict[str, Any]:
        """
        Get encryption statistics

        Returns:
            Dictionary with encryption statistics
        """
        total_keys = len(self.keys)
        active_keys = sum(1 for key in self.keys.values() if key.is_active)
        expired_keys = sum(1 for key in self.keys.values() if key.is_expired())

        return {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "active_key_id": self.active_key_id,
            "algorithm": self.algorithm.value,
            "mode": self.encryption_mode.value,
        }

    async def verify_signature(
        self, data: bytes, signature: bytes, key_data: bytes
    ) -> bool:
        """
        Verify digital signature of data.

        Args:
            data: Original data to verify
            signature: Digital signature to verify against
            key_data: Key data for verification

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            import hashlib
            import hmac

            # Generate expected signature using HMAC-SHA256
            expected_signature = hmac.new(key_data, data, hashlib.sha256).digest()

            # Compare signatures using constant-time comparison
            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False
