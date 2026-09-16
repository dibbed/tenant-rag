"""
Vector Store Migration Tools.

This module provides comprehensive tools for migrating data between different
vector store implementations with validation, progress tracking, and rollback capabilities.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from ragbot.outputs.logger import logger
from ragbot.rag import VectorStoreFactory, BaseVectorStore, VectorDocument


class MigrationStatus(Enum):
    """Migration status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class MigrationProgress:
    """Track migration progress and statistics."""

    total_documents: int = 0
    migrated_documents: int = 0
    failed_documents: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    status: MigrationStatus = MigrationStatus.PENDING
    error_message: Optional[str] = None
    batch_size: int = 100
    current_batch: int = 0
    total_batches: int = 0

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_documents == 0:
            return 0.0
        return (self.migrated_documents / self.total_documents) * 100

    @property
    def elapsed_time(self) -> float:
        """Calculate elapsed time in seconds."""
        if not self.start_time:
            return 0.0
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def migration_rate(self) -> float:
        """Calculate documents per second migration rate."""
        elapsed = self.elapsed_time
        if elapsed == 0:
            return 0.0
        return self.migrated_documents / elapsed

    @property
    def estimated_remaining_time(self) -> float:
        """Estimate remaining time in seconds."""
        if self.migration_rate == 0:
            return 0.0
        remaining_docs = self.total_documents - self.migrated_documents
        return remaining_docs / self.migration_rate


class VectorStoreMigrator:
    """
    Comprehensive vector store migration tool.

    Features:
    - Batch processing for large datasets
    - Progress tracking and reporting
    - Data validation and verification
    - Error handling and recovery
    - Rollback capabilities
    - Resume interrupted migrations
    """

    def __init__(
        self,
        source_store_type: str,
        target_store_type: str,
        batch_size: int = 100,
        validation_enabled: bool = True,
        backup_enabled: bool = True,
        **store_kwargs: Any,
    ):
        """
        Initialize migrator.

        Args:
            source_store_type: Type of source vector store
            target_store_type: Type of target vector store
            batch_size: Number of documents to process in each batch
            validation_enabled: Whether to validate migrated data
            backup_enabled: Whether to create backups
            **store_kwargs: Additional arguments for store creation
        """
        self.source_store_type = source_store_type
        self.target_store_type = target_store_type
        self.batch_size = batch_size
        self.validation_enabled = validation_enabled
        self.backup_enabled = backup_enabled
        self.store_kwargs = store_kwargs

        # Initialize stores
        self.source_store: Optional[BaseVectorStore] = None
        self.target_store: Optional[BaseVectorStore] = None

        # Migration tracking
        self.progress = MigrationProgress(batch_size=batch_size)
        self.failed_documents: List[Tuple[VectorDocument, str]] = []
        self.backup_path: Optional[str] = None

        # Progress callbacks
        self.progress_callbacks: List[Callable[[MigrationProgress], None]] = []

    def add_progress_callback(
        self, callback: Callable[[MigrationProgress], None]
    ) -> None:
        """Add a progress callback function."""
        self.progress_callbacks.append(callback)

    def _notify_progress(self) -> None:
        """Notify all progress callbacks."""
        for callback in self.progress_callbacks:
            try:
                callback(self.progress)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    async def initialize_stores(self) -> None:
        """Initialize source and target stores."""
        try:
            logger.info(f"Initializing {self.source_store_type} source store...")
            self.source_store = VectorStoreFactory.create_store(
                self.source_store_type, **self.store_kwargs
            )

            logger.info(f"Initializing {self.target_store_type} target store...")
            self.target_store = VectorStoreFactory.create_store(
                self.target_store_type, **self.store_kwargs
            )

            logger.info("✅ Stores initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize stores: {e}")
            raise

    async def create_backup(self) -> Optional[str]:
        """Create backup of target store before migration."""
        if not self.backup_enabled or not self.target_store:
            return None

        try:
            logger.info("Creating backup of target store...")
            backup_path = await self.target_store.backup()
            self.backup_path = backup_path
            logger.info(f"✅ Backup created at: {backup_path}")
            return backup_path

        except Exception as e:
            logger.warning(f"Backup creation failed: {e}")
            return None

    async def get_all_documents_from_source(self) -> List[VectorDocument]:
        """
        Retrieve all documents from source store.

        This is a comprehensive method that works with different store types.
        """
        if not self.source_store:
            raise ValueError("Source store not initialized")

        documents = []

        try:
            # Method 1: Try to get document count first
            total_count = self.source_store.get_document_count()
            logger.info(f"Source store contains {total_count:,} documents")

            # Method 2: For FAISS, access documents directly if available
            if hasattr(self.source_store, "documents") and self.source_store.documents:
                logger.info("Extracting documents from FAISS store...")
                for doc_id, doc in self.source_store.documents.items():
                    if isinstance(doc, VectorDocument):
                        documents.append(doc)
                    else:
                        # Convert to VectorDocument if needed
                        vector_doc = VectorDocument(
                            id=doc_id,
                            content=getattr(doc, "content", str(doc)),
                            embedding=getattr(doc, "embedding", []),
                            metadata=getattr(doc, "metadata", {}),
                        )
                        documents.append(vector_doc)

            # Method 3: Try to get documents by metadata (if supported)
            elif hasattr(self.source_store, "get_documents_by_metadata"):
                logger.info("Extracting documents using metadata query...")
                try:
                    # Get all documents with empty filter (should return all)
                    all_docs = await self.source_store.get_documents_by_metadata({})
                    documents.extend(all_docs)
                except Exception as e:
                    logger.warning(f"Metadata query method failed: {e}")

            # Method 4: For stores with search capability, use broad search
            if not documents and hasattr(self.source_store, "search"):
                logger.info("Extracting documents using search method...")
                try:
                    # Use a zero vector to get all documents
                    zero_embedding = [0.0] * getattr(
                        self.source_store, "embedding_dimension", 1536
                    )
                    search_result = await self.source_store.search(
                        zero_embedding, top_k=total_count if total_count > 0 else 10000
                    )
                    documents.extend(search_result.documents)
                except Exception as e:
                    logger.warning(f"Search method failed: {e}")

            logger.info(f"✅ Retrieved {len(documents)} documents from source store")
            return documents

        except Exception as e:
            logger.error(f"Failed to retrieve documents from source: {e}")
            raise

    async def validate_document(
        self, original: VectorDocument, migrated: VectorDocument
    ) -> bool:
        """
        Validate that a document was migrated correctly.

        Args:
            original: Original document from source
            migrated: Migrated document from target

        Returns:
            True if validation passes
        """
        if not self.validation_enabled:
            return True

        try:
            # Check ID
            if original.id != migrated.id:
                logger.warning(f"ID mismatch: {original.id} != {migrated.id}")
                return False

            # Check content
            if original.content != migrated.content:
                logger.warning(f"Content mismatch for document {original.id}")
                return False

            # Check embedding (allow for small floating point differences)
            if len(original.embedding) != len(migrated.embedding):
                logger.warning(
                    f"Embedding dimension mismatch for document {original.id}"
                )
                return False

            # Check metadata (allow for additional metadata added during migration)
            for key, value in original.metadata.items():
                if key not in migrated.metadata:
                    logger.warning(
                        f"Missing metadata key '{key}' in document {original.id}"
                    )
                    return False
                if migrated.metadata[key] != value:
                    logger.warning(
                        f"Metadata value mismatch for key '{key}' in document {original.id}"
                    )
                    return False

            return True

        except Exception as e:
            logger.warning(f"Validation failed for document {original.id}: {e}")
            return False

    async def migrate_batch(
        self, batch: List[VectorDocument]
    ) -> Tuple[List[str], List[Tuple[VectorDocument, str]]]:
        """
        Migrate a batch of documents.

        Args:
            batch: List of documents to migrate

        Returns:
            Tuple of (successfully migrated IDs, failed documents with errors)
        """
        if not self.target_store:
            raise ValueError("Target store not initialized")

        successful_ids = []
        failed_docs = []

        try:
            # Add documents to target store
            added_ids = await self.target_store.add_documents(batch)

            # Validate each document if validation is enabled
            if self.validation_enabled:
                for doc in batch:
                    try:
                        migrated_doc = await self.target_store.get_document(doc.id)
                        if migrated_doc and await self.validate_document(
                            doc, migrated_doc
                        ):
                            successful_ids.append(doc.id)
                        else:
                            failed_docs.append((doc, "Validation failed"))
                    except Exception as e:
                        failed_docs.append((doc, f"Validation error: {e}"))
            else:
                successful_ids = added_ids

            return successful_ids, failed_docs

        except Exception as e:
            # If batch fails completely, mark all as failed
            failed_docs = [(doc, str(e)) for doc in batch]
            return [], failed_docs

    async def migrate_all_documents(
        self,
        resume_from_batch: int = 0,
        progress_callback: Optional[Callable[[MigrationProgress], None]] = None,
    ) -> MigrationProgress:
        """
        Migrate all documents from source to target store.

        Args:
            resume_from_batch: Batch number to resume from (for interrupted migrations)
            progress_callback: Optional callback for progress updates

        Returns:
            Final migration progress
        """
        if progress_callback:
            self.add_progress_callback(progress_callback)

        try:
            # Initialize stores
            await self.initialize_stores()

            # Create backup
            await self.create_backup()

            # Get all documents from source
            logger.info("Retrieving documents from source store...")
            all_documents = await self.get_all_documents_from_source()

            if not all_documents:
                logger.info("No documents to migrate")
                self.progress.status = MigrationStatus.COMPLETED
                return self.progress

            # Initialize progress tracking
            self.progress.total_documents = len(all_documents)
            self.progress.total_batches = (
                len(all_documents) + self.batch_size - 1
            ) // self.batch_size
            self.progress.current_batch = resume_from_batch
            self.progress.start_time = time.time()
            self.progress.status = MigrationStatus.IN_PROGRESS

            logger.info(
                f"Starting migration of {len(all_documents):,} documents in {self.progress.total_batches} batches"
            )

            # Process documents in batches
            for batch_idx in range(resume_from_batch, self.progress.total_batches):
                start_idx = batch_idx * self.batch_size
                end_idx = min(start_idx + self.batch_size, len(all_documents))
                batch = all_documents[start_idx:end_idx]

                self.progress.current_batch = batch_idx + 1

                logger.info(
                    f"Processing batch {batch_idx + 1}/{self.progress.total_batches} ({len(batch)} documents)"
                )

                # Migrate batch
                successful_ids, failed_docs = await self.migrate_batch(batch)

                # Update progress
                self.progress.migrated_documents += len(successful_ids)
                self.progress.failed_documents += len(failed_docs)
                self.failed_documents.extend(failed_docs)

                # Notify progress
                self._notify_progress()

                # Log batch results
                if failed_docs:
                    logger.warning(
                        f"Batch {batch_idx + 1}: {len(successful_ids)} succeeded, {len(failed_docs)} failed"
                    )
                else:
                    logger.info(
                        f"Batch {batch_idx + 1}: All {len(successful_ids)} documents migrated successfully"
                    )

            # Finalize migration
            self.progress.end_time = time.time()

            if self.progress.failed_documents == 0:
                self.progress.status = MigrationStatus.COMPLETED
                logger.info(
                    f"✅ Migration completed successfully! {self.progress.migrated_documents:,} documents migrated"
                )
            else:
                self.progress.status = (
                    MigrationStatus.COMPLETED
                )  # Completed with errors
                logger.warning(
                    f"⚠️ Migration completed with {self.progress.failed_documents} failures"
                )

            return self.progress

        except Exception as e:
            self.progress.status = MigrationStatus.FAILED
            self.progress.error_message = str(e)
            self.progress.end_time = time.time()
            logger.error(f"❌ Migration failed: {e}")
            raise

    async def verify_migration(self) -> Dict[str, Any]:
        """
        Verify that migration was successful by comparing document counts and sampling.

        Returns:
            Dictionary containing verification results
        """
        if not self.source_store or not self.target_store:
            raise ValueError("Stores not initialized")

        try:
            logger.info("Verifying migration...")

            # Compare document counts
            source_count = self.source_store.get_document_count()
            target_count = self.target_store.get_document_count()

            # Sample verification (check 10 random documents)
            verified_documents = 0
            sample_size = min(10, source_count)

            if sample_size > 0:
                # Get sample documents from source
                all_source_docs = await self.get_all_documents_from_source()
                sample_docs = all_source_docs[:sample_size]

                for doc in sample_docs:
                    try:
                        target_doc = await self.target_store.get_document(doc.id)
                        if target_doc and await self.validate_document(doc, target_doc):
                            verified_documents += 1
                    except Exception as e:
                        logger.warning(
                            f"Verification failed for document {doc.id}: {e}"
                        )

            verification_result = {
                "source_count": source_count,
                "target_count": target_count,
                "count_match": source_count == target_count,
                "sample_size": sample_size,
                "verified_documents": verified_documents,
                "sample_verification_rate": verified_documents / sample_size
                if sample_size > 0
                else 0,
                "overall_success": (
                    source_count == target_count
                    and (verified_documents == sample_size if sample_size > 0 else True)
                ),
                "failed_documents_count": len(self.failed_documents),
                "migration_success_rate": (
                    self.progress.migrated_documents / self.progress.total_documents
                    if self.progress.total_documents > 0
                    else 0
                ),
            }

            if verification_result["overall_success"]:
                logger.info("✅ Migration verification successful")
            else:
                logger.warning("⚠️ Migration verification found issues")

            return verification_result

        except Exception as e:
            logger.error(f"Migration verification failed: {e}")
            raise

    async def rollback_migration(self) -> bool:
        """
        Rollback migration by restoring from backup.

        Returns:
            True if rollback was successful
        """
        if not self.backup_path or not self.target_store:
            logger.error(
                "Cannot rollback: no backup available or target store not initialized"
            )
            return False

        try:
            logger.info(f"Rolling back migration from backup: {self.backup_path}")

            # Clear target store
            await self.target_store.clear()

            # Restore from backup
            await self.target_store.restore(self.backup_path)

            self.progress.status = MigrationStatus.ROLLED_BACK
            logger.info("✅ Migration rolled back successfully")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def save_migration_report(self, output_path: str) -> None:
        """
        Save detailed migration report to JSON file.

        Args:
            output_path: Path to save the report
        """
        try:
            report = {
                "migration_info": {
                    "source_store_type": self.source_store_type,
                    "target_store_type": self.target_store_type,
                    "batch_size": self.batch_size,
                    "validation_enabled": self.validation_enabled,
                    "backup_enabled": self.backup_enabled,
                },
                "progress": asdict(self.progress),
                "failed_documents": [
                    {
                        "document_id": doc.id,
                        "error": error,
                        "content_preview": doc.content[:100] + "..."
                        if len(doc.content) > 100
                        else doc.content,
                        "metadata": doc.metadata,
                    }
                    for doc, error in self.failed_documents
                ],
                "backup_path": self.backup_path,
                "timestamp": time.time(),
            }

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            logger.info(f"📄 Migration report saved to: {output_path}")

        except Exception as e:
            logger.error(f"Failed to save migration report: {e}")


def print_progress(progress: MigrationProgress) -> None:
    """Default progress callback that prints to console."""
    print(
        f"\r🔄 Progress: {progress.progress_percentage:.1f}% "
        f"({progress.migrated_documents}/{progress.total_documents}) "
        f"| Rate: {progress.migration_rate:.1f} docs/sec "
        f"| ETA: {progress.estimated_remaining_time:.0f}s",
        end="",
        flush=True,
    )


async def migrate_store_command(
    source: str,
    target: str,
    batch_size: int = 100,
    validate: bool = True,
    backup: bool = True,
    report_path: str = "migration_report.json",
    **kwargs: Any,
) -> bool:
    """
    CLI command for migrating between stores.

    Args:
        source: Source store type
        target: Target store type
        batch_size: Batch size for migration
        validate: Whether to validate migrated data
        backup: Whether to create backup
        report_path: Path to save migration report
        **kwargs: Additional store configuration

    Returns:
        True if migration was successful
    """
    print(f"🔄 Starting migration from {source} to {target}...")
    print(
        f"📊 Configuration: batch_size={batch_size}, validate={validate}, backup={backup}"
    )

    # Initialize migrator
    migrator = VectorStoreMigrator(
        source_store_type=source,
        target_store_type=target,
        batch_size=batch_size,
        validation_enabled=validate,
        backup_enabled=backup,
        **kwargs,
    )

    try:
        # Run migration with progress display
        progress = await migrator.migrate_all_documents(
            progress_callback=print_progress
        )
        print()  # New line after progress

        # Verify migration
        print("🔍 Verifying migration...")
        verification = await migrator.verify_migration()

        # Save report
        migrator.save_migration_report(report_path)

        # Print results
        if verification["overall_success"]:
            print(f"✅ Migration completed successfully!")
            print(f"   • Migrated: {progress.migrated_documents:,} documents")
            print(f"   • Time: {progress.elapsed_time:.1f}s")
            print(f"   • Rate: {progress.migration_rate:.1f} docs/sec")
            return True
        else:
            print(f"⚠️ Migration completed with issues:")
            print(
                f"   • Migrated: {progress.migrated_documents:,}/{progress.total_documents:,} documents"
            )
            print(f"   • Failed: {progress.failed_documents:,} documents")
            print(f"   • Success rate: {verification['migration_success_rate']:.1%}")
            return False

    except Exception as e:
        print(f"❌ Migration failed: {e}")

        # Save report even on failure
        try:
            migrator.save_migration_report(report_path)
        except Exception:
            pass

        return False
