"""
Tests for IngestionService - Orchestrates PDF ingestion into ChromaDB.

Following TDD: write failing tests first, then implement.
"""

import pytest
from dataclasses import dataclass
from pathlib import Path

import yaml
from fpdf import FPDF

# These imports will fail until we implement (TDD - RED phase)
from girafmcp.core.services.ingestion_service import IngestionService, IngestionResult
from girafmcp.adapters.pdf_adapter import PDFAdapter
from girafmcp.adapters.chroma_adapter import ChromaAdapter


@dataclass
class PDFFixture:
    """Helper to create test PDFs."""

    path: Path
    content: str


class TestIngestionService:
    """Tests for IngestionService - ingests PDFs into ChromaDB."""

    @pytest.fixture
    def chroma_adapter(self) -> ChromaAdapter:
        """Create ephemeral ChromaDB adapter for testing."""
        return ChromaAdapter(ephemeral=True)

    @pytest.fixture
    def docs_dir(self, tmp_path: Path) -> Path:
        """Create a documents directory."""
        docs = tmp_path / "documents"
        docs.mkdir()
        return docs

    @pytest.fixture
    def pdf_adapter(self, docs_dir: Path) -> PDFAdapter:
        """Create PDF adapter with test directory."""
        return PDFAdapter(documents_dir=docs_dir)

    @pytest.fixture
    def service(
        self, pdf_adapter: PDFAdapter, chroma_adapter: ChromaAdapter
    ) -> IngestionService:
        """Create ingestion service with test adapters."""
        return IngestionService(
            pdf_adapter=pdf_adapter,
            chroma_adapter=chroma_adapter,
        )

    def _create_pdf(self, folder: Path, filename: str, content: str) -> Path:
        """Helper to create a test PDF."""
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 10, content)

        pdf_path = folder / filename
        pdf.output(str(pdf_path))
        return pdf_path

    @pytest.fixture
    def single_pdf(self, docs_dir: Path) -> PDFFixture:
        """Create a single PDF in documents directory."""
        content = "Content about autism and visual schedules for testing."
        path = self._create_pdf(docs_dir, "test-doc.pdf", content)
        return PDFFixture(path=path, content=content)

    @pytest.fixture
    def multiple_pdfs(self, docs_dir: Path) -> list[PDFFixture]:
        """Create multiple PDFs in documents directory."""
        pdfs = []
        for i, topic in enumerate(["autism basics", "visual schedules", "sensory processing"]):
            content = f"Document about {topic} for GIRAF project."
            path = self._create_pdf(docs_dir, f"doc-{i}.pdf", content)
            pdfs.append(PDFFixture(path=path, content=content))
        return pdfs

    @pytest.fixture
    def tagged_subfolder(self, docs_dir: Path) -> Path:
        """Create a tagged subfolder with a PDF."""
        folder = docs_dir / "research"
        folder.mkdir()

        # Create _meta.yaml
        meta = {"tags": ["research", "academic"]}
        (folder / "_meta.yaml").write_text(yaml.dump(meta))

        # Create PDF
        self._create_pdf(folder, "study.pdf", "Research study on autism communication.")

        return folder

    # === Basic Ingestion Tests ===

    async def test_ingests_single_pdf(
        self, service: IngestionService, single_pdf: PDFFixture, chroma_adapter: ChromaAdapter
    ):
        """Should ingest a single PDF into ChromaDB."""
        result = await service.ingest_all()

        assert result.files_processed == 1
        assert result.documents_created >= 1

        # Verify document exists in ChromaDB
        count = await chroma_adapter.count("static_documents")
        assert count >= 1

    async def test_ingests_multiple_pdfs(
        self, service: IngestionService, multiple_pdfs: list[PDFFixture], chroma_adapter: ChromaAdapter
    ):
        """Should ingest multiple PDFs."""
        result = await service.ingest_all()

        assert result.files_processed == 3
        assert result.documents_created >= 3

    async def test_search_finds_ingested_content(
        self, service: IngestionService, single_pdf: PDFFixture, chroma_adapter: ChromaAdapter
    ):
        """Should be able to search ingested content."""
        await service.ingest_all()

        results = await chroma_adapter.search("static_documents", "autism visual", limit=5)

        assert len(results) >= 1
        assert "autism" in results[0].content.lower() or "visual" in results[0].content.lower()

    async def test_preserves_metadata_through_ingestion(
        self, service: IngestionService, single_pdf: PDFFixture, chroma_adapter: ChromaAdapter
    ):
        """Should preserve document metadata in ChromaDB."""
        await service.ingest_all()

        results = await chroma_adapter.search("static_documents", "testing", limit=1)

        assert len(results) >= 1
        assert results[0].metadata.source == "pdf"
        assert results[0].metadata.page is not None
        assert "test-doc.pdf" in results[0].metadata.url

    # === Change Detection Tests ===

    async def test_skips_already_ingested_files(
        self, service: IngestionService, single_pdf: PDFFixture
    ):
        """Should not re-ingest unchanged files."""
        # First ingestion
        result1 = await service.ingest_all()
        assert result1.files_processed == 1

        # Second ingestion - should skip
        result2 = await service.ingest_all()
        assert result2.files_processed == 0
        assert result2.files_skipped == 1

    async def test_reingests_modified_files(
        self, service: IngestionService, single_pdf: PDFFixture, docs_dir: Path
    ):
        """Should detect and re-ingest modified files."""
        # First ingestion
        await service.ingest_all()

        # Modify the PDF (recreate with different content)
        self._create_pdf(docs_dir, "test-doc.pdf", "Updated content about new topics.")

        # Second ingestion - should detect change
        result = await service.ingest_all()
        assert result.files_processed == 1
        assert result.files_updated == 1

    # === Edge Cases ===

    async def test_handles_empty_directory(
        self, service: IngestionService
    ):
        """Should handle empty documents directory gracefully."""
        result = await service.ingest_all()

        assert result.files_processed == 0
        assert result.documents_created == 0

    async def test_handles_subfolder_pdfs(
        self, service: IngestionService, tagged_subfolder: Path, chroma_adapter: ChromaAdapter
    ):
        """Should ingest PDFs from subfolders."""
        result = await service.ingest_all()

        assert result.files_processed == 1

        # Verify tags are preserved
        results = await chroma_adapter.search("static_documents", "research communication", limit=1)
        assert len(results) >= 1
        assert "research" in results[0].metadata.tags

    async def test_handles_missing_directory(self, chroma_adapter: ChromaAdapter, tmp_path: Path):
        """Should handle missing documents directory."""
        pdf_adapter = PDFAdapter(documents_dir=tmp_path / "nonexistent")
        service = IngestionService(pdf_adapter=pdf_adapter, chroma_adapter=chroma_adapter)

        result = await service.ingest_all()

        assert result.files_processed == 0

    # === Single File Ingestion ===

    async def test_ingest_single_file(
        self, service: IngestionService, single_pdf: PDFFixture
    ):
        """Should be able to ingest a single file directly."""
        count = await service.ingest_file(single_pdf.path)

        assert count >= 1

    async def test_ingest_file_returns_chunk_count(
        self, service: IngestionService, single_pdf: PDFFixture
    ):
        """Should return number of document chunks created."""
        count = await service.ingest_file(single_pdf.path)

        # Single page PDF should create at least 1 chunk
        assert isinstance(count, int)
        assert count >= 1

    # === Result Object Tests ===

    async def test_result_has_correct_counts(
        self, service: IngestionService, multiple_pdfs: list[PDFFixture]
    ):
        """IngestionResult should have accurate counts."""
        result = await service.ingest_all()

        assert result.files_processed == 3
        assert result.files_skipped == 0
        assert result.files_updated == 0
        assert result.documents_created >= 3
        assert result.errors == []

    async def test_handles_corrupt_pdf_gracefully(
        self, service: IngestionService, docs_dir: Path
    ):
        """Should handle corrupt PDFs gracefully (no crash, no documents created)."""
        # Create a corrupt PDF
        corrupt = docs_dir / "corrupt.pdf"
        corrupt.write_text("not a valid pdf")

        result = await service.ingest_all()

        # Corrupt PDF is handled gracefully - returns 0 documents
        # This is by design: PDFAdapter returns empty list for invalid files
        assert result.documents_created == 0
        # File is processed (attempted) but yields no documents
        assert result.files_processed == 0  # No successful processing
