"""
Tests for IngestionService - Orchestrates Markdown ingestion into ChromaDB.
"""

import pytest
from dataclasses import dataclass
from pathlib import Path

import yaml

from girafmcp.core.services.ingestion_service import IngestionService, IngestionResult
from girafmcp.adapters.markdown_adapter import MarkdownAdapter
from girafmcp.adapters.chroma_adapter import ChromaAdapter


@dataclass
class MDFixture:
    """Helper to create test Markdown files."""
    path: Path
    content: str


class TestIngestionService:
    """Tests for IngestionService - ingests extracted Markdown into ChromaDB."""

    @pytest.fixture
    def chroma_adapter(self) -> ChromaAdapter:
        """Create ephemeral ChromaDB adapter for testing."""
        return ChromaAdapter(ephemeral=True)

    @pytest.fixture
    def extracted_dir(self, tmp_path: Path) -> Path:
        """Create an extracted artifacts directory."""
        d = tmp_path / "extracted"
        d.mkdir()
        return d

    @pytest.fixture
    def markdown_adapter(self, extracted_dir: Path) -> MarkdownAdapter:
        """Create Markdown adapter with test directory."""
        return MarkdownAdapter(extracted_dir=extracted_dir)

    @pytest.fixture
    def service(
        self, markdown_adapter: MarkdownAdapter, chroma_adapter: ChromaAdapter
    ) -> IngestionService:
        """Create ingestion service with test adapters."""
        return IngestionService(
            markdown_adapter=markdown_adapter,
            chroma_adapter=chroma_adapter,
        )

    def _create_md(self, folder: Path, filename: str, content: str, title: str = "Test Doc") -> Path:
        """Helper to create a test Markdown artifact."""
        full_content = f"""---
title: {title}
original_filename: {filename.replace('.md', '.pdf')}
source: pdf
tags: []
---

{content}
"""
        path = folder / filename
        path.write_text(full_content, encoding="utf-8")
        return path

    @pytest.fixture
    def single_md(self, extracted_dir: Path) -> MDFixture:
        """Create a single MD in extracted directory."""
        content = "Content about autism and visual schedules for testing."
        path = self._create_md(extracted_dir, "test-doc.md", content)
        return MDFixture(path=path, content=content)

    @pytest.fixture
    def multiple_mds(self, extracted_dir: Path) -> list[MDFixture]:
        """Create multiple MDs in extracted directory."""
        mds = []
        for i, topic in enumerate(["autism basics", "visual schedules", "sensory processing"]):
            content = f"Document about {topic} for GIRAF project."
            path = self._create_md(extracted_dir, f"doc-{i}.md", content)
            mds.append(MDFixture(path=path, content=content))
        return mds

    # === Basic Ingestion Tests ===

    @pytest.mark.asyncio
    async def test_ingests_single_file(
        self, service: IngestionService, single_md: MDFixture, chroma_adapter: ChromaAdapter
    ):
        """Should ingest a single MD file into ChromaDB."""
        result = await service.ingest_all()

        assert result.files_processed == 1
        assert result.documents_created >= 1

        # Verify document exists in ChromaDB
        count = await chroma_adapter.count("static_documents")
        assert count >= 1

    @pytest.mark.asyncio
    async def test_ingests_multiple_files(
        self, service: IngestionService, multiple_mds: list[MDFixture], chroma_adapter: ChromaAdapter
    ):
        """Should ingest multiple MD files."""
        result = await service.ingest_all()

        assert result.files_processed == 3
        assert result.documents_created >= 3

    @pytest.mark.asyncio
    async def test_search_finds_ingested_content(
        self, service: IngestionService, single_md: MDFixture, chroma_adapter: ChromaAdapter
    ):
        """Should be able to search ingested content."""
        await service.ingest_all()

        results = await chroma_adapter.search("static_documents", "autism visual", limit=5)

        assert len(results) >= 1
        assert "autism" in results[0].content.lower() or "visual" in results[0].content.lower()

    @pytest.mark.asyncio
    async def test_preserves_metadata_through_ingestion(
        self, service: IngestionService, single_md: MDFixture, chroma_adapter: ChromaAdapter
    ):
        """Should preserve document metadata in ChromaDB."""
        await service.ingest_all()

        results = await chroma_adapter.search("static_documents", "testing", limit=1)

        assert len(results) >= 1
        assert results[0].metadata.source == "pdf"
        assert "test-doc.md" in results[0].metadata.url

    # === Change Detection Tests ===

    @pytest.mark.asyncio
    async def test_skips_already_ingested_files(
        self, service: IngestionService, single_md: MDFixture
    ):
        """Should not re-ingest unchanged files."""
        # First ingestion
        result1 = await service.ingest_all()
        assert result1.files_processed == 1

        # Second ingestion - should skip
        result2 = await service.ingest_all()
        assert result2.files_processed == 0
        assert result2.files_skipped == 1

    @pytest.mark.asyncio
    async def test_reingests_modified_files(
        self, service: IngestionService, single_md: MDFixture, extracted_dir: Path
    ):
        """Should detect and re-ingest modified files."""
        # First ingestion
        await service.ingest_all()

        # Modify the MD
        import time
        time.sleep(0.01) # ensure mtime change if FS is fast
        self._create_md(extracted_dir, "test-doc.md", "Updated content about new topics.")

        # Second ingestion - should detect change
        result = await service.ingest_all()
        assert result.files_processed == 1
        assert result.files_updated == 1

    # === Edge Cases ===

    @pytest.mark.asyncio
    async def test_handles_empty_directory(
        self, service: IngestionService
    ):
        """Should handle empty extracted directory gracefully."""
        result = await service.ingest_all()

        assert result.files_processed == 0
        assert result.documents_created == 0

    @pytest.mark.asyncio
    async def test_handles_subfolder_files(
        self, service: IngestionService, extracted_dir: Path, chroma_adapter: ChromaAdapter
    ):
        """Should ingest files from subfolders."""
        sub = extracted_dir / "subdir"
        sub.mkdir()
        self._create_md(sub, "sub.md", "Content in subdir")
        
        result = await service.ingest_all()

        assert result.files_processed == 1
        
        results = await chroma_adapter.search("static_documents", "subdir", limit=1)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_handles_missing_directory(self, chroma_adapter: ChromaAdapter, tmp_path: Path):
        """Should handle missing extracted directory."""
        markdown_adapter = MarkdownAdapter(extracted_dir=tmp_path / "nonexistent")
        service = IngestionService(markdown_adapter=markdown_adapter, chroma_adapter=chroma_adapter)

        result = await service.ingest_all()

        assert result.files_processed == 0