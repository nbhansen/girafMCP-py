"""Markdown Adapter for reading extracted artifacts.

Reads Markdown files with YAML frontmatter (produced by ExtractionService)
and converts them into Document objects for ingestion.
"""

import hashlib
import logging
from pathlib import Path
from typing import Any

import yaml

from girafmcp.core.types import Document, DocumentMetadata

logger = logging.getLogger(__name__)


class MarkdownAdapter:
    """Adapter for reading extracted Markdown documents."""

    def __init__(
        self,
        extracted_dir: Path | None = None,
        max_chunk_size: int = 1500,
        chunk_overlap: int = 200,
    ):
        self.extracted_dir = extracted_dir
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    async def scan_directory(self) -> list[Path]:
        """Find all Markdown files in the extracted directory."""
        if self.extracted_dir is None or not self.extracted_dir.exists():
            return []
        return list(self.extracted_dir.rglob("*.md"))

    async def extract_documents(self, md_path: Path) -> list[Document]:
        """Read a Markdown file and produce Document objects."""
        if not md_path.exists():
            return []

        try:
            content = md_path.read_text(encoding="utf-8")
            frontmatter, body = self._parse_frontmatter(content)
            
            # Use original filename for ID generation if available
            original_stem = Path(frontmatter.get("original_filename", md_path.name)).stem
            tags = frontmatter.get("tags", [])
            title = frontmatter.get("title", original_stem)

            documents: list[Document] = []
            
            # Split by page separators (PyMuPDF4LLM uses "-----")
            # Note: We need to be careful not to split on other horizontal rules if possible,
            # but usually extraction adds distinct page breaks.
            # PyMuPDF4LLM adds `\n-----\n`
            pages = body.split("\n-----\n")
            
            for page_idx, page_text in enumerate(pages, start=1):
                page_text = page_text.strip()
                if not page_text:
                    continue
                
                # Chunk if page is too large
                chunks = self._chunk_text(page_text)
                
                for chunk_idx, chunk in enumerate(chunks):
                    doc_id = self._generate_id(original_stem, page_idx, chunk_idx)
                    
                    metadata = DocumentMetadata(
                        source="pdf",  # Still essentially a PDF source
                        url=str(md_path), # Point to the MD artifact or original? MD is safer for now.
                        title=title,
                        page=page_idx,
                        tags=tags,
                        last_updated=frontmatter.get("last_updated")
                    )
                    
                    documents.append(
                        Document(
                            id=doc_id,
                            content=chunk,
                            metadata=metadata
                        )
                    )
            
            return documents

        except Exception as e:
            logger.error(f"Error reading Markdown {md_path}: {e}")
            return []

    def _parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        """Parse YAML frontmatter from Markdown content."""
        if content.startswith("---\n"):
            try:
                parts = content.split("---\n", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    body = parts[2]
                    return frontmatter, body
            except Exception:
                pass
        
        return {}, content

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into chunks with overlap."""
        if len(text) <= self.max_chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            # Default end is the hard limit or end of text
            end = min(start + self.max_chunk_size, text_len)

            if end < text_len:
                # Try to find a natural break point (space)
                last_space = text.rfind(" ", start, end)
                
                # CRITICAL FIX: Only use the space if it ensures forward progress.
                # The next chunk starts at 'end - overlap'. We must ensure
                # 'end - overlap > start', which means 'end > start + overlap'.
                if last_space > start + self.chunk_overlap:
                    end = last_space
                # If no suitable space found, we stick to the hard limit 'end'
                # which is 'start + max_chunk_size', guaranteeing progress.

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # If we reached the end of the text, we are done
            if end == text_len:
                break

            # Calculate start of next chunk
            start = end - self.chunk_overlap
            
        return chunks

    def _generate_id(self, stem: str, page_num: int, chunk_idx: int) -> str:
        """Generate a unique document ID."""
        # Using hash of stem to ensure uniqueness but consistency
        hash_suffix = hashlib.md5(stem.encode()).hexdigest()[:8]
        return f"doc-{stem}-p{page_num}-c{chunk_idx}-{hash_suffix}"
