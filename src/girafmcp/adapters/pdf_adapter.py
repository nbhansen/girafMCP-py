"""PDF Adapter for extracting text from PDF documents.

Provides extraction of text content from PDFs for indexing in ChromaDB.
Supports page-based chunking, folder tags via _meta.yaml, and error handling.
"""

import hashlib
import logging
from pathlib import Path

import pdfplumber
import yaml  # type: ignore

from girafmcp.core.types import Document, DocumentMetadata

logger = logging.getLogger(__name__)


class PDFAdapter:
    """Adapter for extracting documents from PDF files."""

    def __init__(
        self,
        documents_dir: Path | None = None,
        max_chunk_size: int = 1500,
        chunk_overlap: int = 200,
    ):
        """Initialize the PDF adapter.

        Args:
            documents_dir: Path to the documents directory. Defaults to None.
            max_chunk_size: Maximum characters per chunk. Defaults to 1500.
            chunk_overlap: Overlap between chunks. Defaults to 200.
        """
        self.documents_dir = documents_dir
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    async def extract_documents(self, pdf_path: Path) -> list[Document]:
        """Extract text from a PDF, creating Documents for each page/chunk.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of Document objects with extracted text and metadata.
            Returns empty list on errors (graceful handling).
        """
        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            return []

        try:
            documents: list[Document] = []
            folder_tags = self._load_folder_tags(pdf_path.parent)
            title = pdf_path.name

            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""

                    if not text.strip():
                        continue

                    # Chunk long pages
                    chunks = self._chunk_text(text)

                    for chunk_idx, chunk in enumerate(chunks):
                        doc_id = self._generate_id(pdf_path, page_num, chunk_idx)

                        metadata = DocumentMetadata(
                            source="pdf",
                            url=str(pdf_path),
                            title=title,
                            page=page_num,
                            tags=folder_tags,
                        )

                        documents.append(
                            Document(
                                id=doc_id,
                                content=chunk,
                                metadata=metadata,
                            )
                        )

            return documents

        except Exception as e:
            logger.error(f"Error extracting PDF {pdf_path}: {e}")
            return []

    async def scan_directory(self) -> list[Path]:
        """Find all PDF files in the documents directory.

        Returns:
            List of paths to PDF files. Empty list if directory doesn't exist.
        """
        if self.documents_dir is None or not self.documents_dir.exists():
            return []

        return list(self.documents_dir.rglob("*.pdf"))

    def _load_folder_tags(self, folder: Path) -> list[str]:
        """Load tags from _meta.yaml in the given folder.

        Args:
            folder: Path to the folder to check for _meta.yaml.

        Returns:
            List of tags from _meta.yaml, or empty list if not found.
        """
        meta_path = folder / "_meta.yaml"

        if not meta_path.exists():
            return []

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = yaml.safe_load(f) or {}
                return list(meta.get("tags", []))
        except Exception as e:
            logger.warning(f"Error loading _meta.yaml from {folder}: {e}")
            return []

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into chunks with overlap.

        Args:
            text: The text to chunk.

        Returns:
            List of text chunks.
        """
        if len(text) <= self.max_chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0

        while start < len(text):
            end = start + self.max_chunk_size

            # If not at the end, try to break at word boundary
            if end < len(text):
                # Look for last space within chunk
                last_space = text.rfind(" ", start, end)
                if last_space > start:
                    end = last_space

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start with overlap
            start = end - self.chunk_overlap
            if start >= len(text):
                break

        return chunks

    def _generate_id(self, pdf_path: Path, page_num: int, chunk_idx: int) -> str:
        """Generate a unique document ID.

        Args:
            pdf_path: Path to the PDF file.
            page_num: Page number (1-indexed).
            chunk_idx: Chunk index within the page.

        Returns:
            Unique ID for the chunk
        """
        hash_suffix = hashlib.md5(str(pdf_path).encode()).hexdigest()[:8]
        return f"pdf-{pdf_path.stem}-p{page_num}-c{chunk_idx}-{hash_suffix}"
