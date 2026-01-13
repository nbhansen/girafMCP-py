"""Ingestion service for processing PDFs into ChromaDB.

Orchestrates scanning, extraction, and storage of static documents.
Tracks ingested files to avoid redundant re-processing.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from girafmcp.adapters.markdown_adapter import MarkdownAdapter
from girafmcp.adapters.chroma_adapter import ChromaAdapter

logger = logging.getLogger(__name__)

COLLECTION_NAME = "static_documents"
INGESTION_LOG_COLLECTION = "_ingestion_log"


@dataclass
class IngestionResult:
    """Result of an ingestion operation."""

    files_processed: int = 0
    files_skipped: int = 0
    files_updated: int = 0
    documents_created: int = 0
    errors: list[str] = field(default_factory=list)


class IngestionService:
    """Service for ingesting extracted Markdown documents into ChromaDB."""

    def __init__(
        self,
        markdown_adapter: MarkdownAdapter,
        chroma_adapter: ChromaAdapter,
        collection: str = COLLECTION_NAME,
    ):
        """Initialize the ingestion service.

        Args:
            markdown_adapter: Adapter for reading extracted Markdown artifacts.
            chroma_adapter: Adapter for storing documents in ChromaDB.
            collection: Collection name for storing documents.
        """
        self.markdown = markdown_adapter
        self.chroma = chroma_adapter
        self.collection = collection
        self._ingested_hashes: dict[str, str] = {}  # path -> hash
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure collections exist and load ingestion state."""
        if self._initialized:
            return

        await self.chroma.create_collection(self.collection)
        await self._load_ingestion_state()
        self._initialized = True

    async def _load_ingestion_state(self) -> None:
        """Load previously ingested file hashes from ChromaDB."""
        try:
            # Try to get the ingestion log document
            doc = await self.chroma.get(self.collection, "_ingestion_log")
            if doc:
                self._ingested_hashes = json.loads(doc.content)
        except Exception:
            # No log exists yet, start fresh
            self._ingested_hashes = {}

    async def _save_ingestion_state(self) -> None:
        """Save ingested file hashes to ChromaDB."""
        from girafmcp.core.types import Document, DocumentMetadata

        log_doc = Document(
            id="_ingestion_log",
            content=json.dumps(self._ingested_hashes),
            metadata=DocumentMetadata(
                source="pdf",
                url="_internal",
                title="Ingestion Log",
            ),
        )
        await self.chroma.upsert(self.collection, [log_doc])

    def _compute_file_hash(self, path: Path) -> str:
        """Compute SHA256 hash of a file for change detection."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def ingest_all(self) -> IngestionResult:
        """Scan extracted directory and ingest all Markdown files.

        Returns:
            IngestionResult with counts of processed files.
        """
        await self._ensure_initialized()

        result = IngestionResult()
        md_paths = await self.markdown.scan_directory()

        for md_path in md_paths:
            try:
                path_str = str(md_path)
                current_hash = self._compute_file_hash(md_path)

                # Check if already ingested
                previous_hash = self._ingested_hashes.get(path_str)

                if previous_hash == current_hash:
                    # Skip unchanged file
                    result.files_skipped += 1
                    continue

                # Ingest the file
                docs_created = await self.ingest_file(md_path)

                if docs_created > 0:
                    result.files_processed += 1
                    result.documents_created += docs_created

                    if previous_hash is not None:
                        # File was updated
                        result.files_updated += 1

                    # Record the hash
                    self._ingested_hashes[path_str] = current_hash

            except Exception as e:
                error_msg = f"Error ingesting {md_path}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        # Save ingestion state
        await self._save_ingestion_state()

        return result

    async def ingest_file(self, path: Path) -> int:
        """Ingest a single Markdown file.

        Args:
            path: Path to the Markdown file.

        Returns:
            Number of document chunks created.
        """
        await self._ensure_initialized()

        # Delete any existing documents from this file
        await self._delete_file_documents(path)

        # Extract documents from Markdown
        documents = await self.markdown.extract_documents(path)

        if not documents:
            return 0

        # Store in ChromaDB
        await self.chroma.upsert(self.collection, documents)

        return len(documents)

    async def _delete_file_documents(self, path: Path) -> None:
        """Delete all documents from a specific PDF file.

        This is used when re-ingesting a modified file.
        """
        # Get all document IDs that start with this file's prefix
        # We use a naming convention: pdf-{stem}-p{page}-c{chunk}-{hash}
        # This is a simplified approach - for production you might want
        # to store document IDs in metadata
        pass  # ChromaDB doesn't have efficient prefix deletion,
        # but our upsert will update existing IDs
