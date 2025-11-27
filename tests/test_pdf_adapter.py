"""
Tests for PDFAdapter - PDF text extraction for semantic search.

These tests use fpdf2 to create test PDFs dynamically, following TDD.
Write tests first (RED), then implement to pass (GREEN).
"""

import pytest
from pathlib import Path

import yaml
from fpdf import FPDF

# This import will fail until we implement PDFAdapter (TDD - RED phase)
from girafmcp.adapters.pdf_adapter import PDFAdapter


class TestPDFAdapter:
    """Tests for PDFAdapter - extracts text from PDFs for indexing."""

    @pytest.fixture
    def adapter(self, tmp_path: Path) -> PDFAdapter:
        """Create adapter with temporary documents directory."""
        return PDFAdapter(documents_dir=tmp_path)

    @pytest.fixture
    def single_page_pdf(self, tmp_path: Path) -> Path:
        """Create a simple single-page PDF for testing."""
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 10, "This is test content about autism and visual schedules.")

        pdf_path = tmp_path / "single-page.pdf"
        pdf.output(str(pdf_path))
        return pdf_path

    @pytest.fixture
    def multi_page_pdf(self, tmp_path: Path) -> Path:
        """Create a 3-page PDF for testing pagination."""
        pdf = FPDF()

        # Page 1
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 10, "Page one content about introduction to GIRAF project.")

        # Page 2
        pdf.add_page()
        pdf.multi_cell(0, 10, "Page two content about sensory considerations for users.")

        # Page 3
        pdf.add_page()
        pdf.multi_cell(0, 10, "Page three content about visual schedule implementation.")

        pdf_path = tmp_path / "multi-page.pdf"
        pdf.output(str(pdf_path))
        return pdf_path

    @pytest.fixture
    def long_page_pdf(self, tmp_path: Path) -> Path:
        """Create a PDF with very long content to test chunking."""
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=6)  # Small font to fit more on page

        # Create content longer than 1500 chars but small enough to fit on page
        long_content = "Autism support. " * 200  # ~3200 chars
        pdf.multi_cell(0, 3, long_content)

        pdf_path = tmp_path / "long-content.pdf"
        pdf.output(str(pdf_path))
        return pdf_path

    @pytest.fixture
    def tagged_folder(self, tmp_path: Path) -> Path:
        """Create a folder with _meta.yaml tags and a PDF."""
        folder = tmp_path / "research-papers"
        folder.mkdir()

        # Create _meta.yaml with tags
        meta = {"tags": ["research", "academic"], "description": "Research papers"}
        meta_path = folder / "_meta.yaml"
        meta_path.write_text(yaml.dump(meta))

        # Create PDF in folder
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 10, "Research paper content about autism communication.")

        pdf_path = folder / "research-paper.pdf"
        pdf.output(str(pdf_path))

        return folder

    @pytest.fixture
    def corrupt_pdf(self, tmp_path: Path) -> Path:
        """Create an invalid PDF file for error handling tests."""
        pdf_path = tmp_path / "corrupt.pdf"
        pdf_path.write_text("This is not a valid PDF file")
        return pdf_path

    # === Core Extraction Tests ===

    async def test_extracts_text_from_single_page_pdf(
        self, adapter: PDFAdapter, single_page_pdf: Path
    ):
        """Should extract text content from a PDF."""
        docs = await adapter.extract_documents(single_page_pdf)

        assert len(docs) >= 1
        assert "autism" in docs[0].content.lower()
        assert "visual schedules" in docs[0].content.lower()

    async def test_creates_document_per_page(
        self, adapter: PDFAdapter, multi_page_pdf: Path
    ):
        """Should create one Document per page."""
        docs = await adapter.extract_documents(multi_page_pdf)

        assert len(docs) == 3
        assert "introduction" in docs[0].content.lower()
        assert "sensory" in docs[1].content.lower()
        assert "implementation" in docs[2].content.lower()

    async def test_metadata_has_source_and_page(
        self, adapter: PDFAdapter, multi_page_pdf: Path
    ):
        """Should include source='pdf' and page number in metadata."""
        docs = await adapter.extract_documents(multi_page_pdf)

        for i, doc in enumerate(docs, start=1):
            assert doc.metadata.source == "pdf"
            assert doc.metadata.page == i
            assert str(multi_page_pdf) in doc.metadata.url

    async def test_generates_unique_document_ids(
        self, adapter: PDFAdapter, multi_page_pdf: Path
    ):
        """Should generate unique IDs for each document."""
        docs = await adapter.extract_documents(multi_page_pdf)

        ids = [doc.id for doc in docs]
        assert len(ids) == len(set(ids)), "Document IDs should be unique"

    # === Chunking Tests ===

    async def test_splits_long_pages_into_chunks(
        self, adapter: PDFAdapter, long_page_pdf: Path
    ):
        """Should split very long pages into multiple chunks."""
        docs = await adapter.extract_documents(long_page_pdf)

        # Long content should be split into multiple chunks
        assert len(docs) > 1, "Long page should be split into chunks"

        # All chunks should have the same page number
        for doc in docs:
            assert doc.metadata.page == 1

    async def test_chunks_have_reasonable_size(
        self, adapter: PDFAdapter, long_page_pdf: Path
    ):
        """Chunks should not exceed max size (with some tolerance)."""
        docs = await adapter.extract_documents(long_page_pdf)

        max_chunk_size = 2000  # Allow some tolerance over 1500
        for doc in docs:
            assert len(doc.content) <= max_chunk_size

    # === Folder Tags Tests ===

    async def test_applies_folder_tags_from_meta_yaml(
        self, adapter: PDFAdapter, tagged_folder: Path
    ):
        """Should inherit tags from folder's _meta.yaml."""
        pdf_path = tagged_folder / "research-paper.pdf"
        docs = await adapter.extract_documents(pdf_path)

        assert len(docs) >= 1
        assert "research" in docs[0].metadata.tags
        assert "academic" in docs[0].metadata.tags

    async def test_extracts_title_from_filename(
        self, adapter: PDFAdapter, single_page_pdf: Path
    ):
        """Should use filename as document title."""
        docs = await adapter.extract_documents(single_page_pdf)

        assert docs[0].metadata.title == "single-page.pdf"

    # === Error Handling Tests ===

    async def test_handles_corrupt_pdf_gracefully(
        self, adapter: PDFAdapter, corrupt_pdf: Path
    ):
        """Should return empty list for invalid PDFs, not raise exception."""
        docs = await adapter.extract_documents(corrupt_pdf)

        assert docs == []

    async def test_handles_nonexistent_file(self, adapter: PDFAdapter, tmp_path: Path):
        """Should return empty list for missing files."""
        missing_pdf = tmp_path / "does-not-exist.pdf"
        docs = await adapter.extract_documents(missing_pdf)

        assert docs == []

    # === Directory Scanning Tests ===

    async def test_scans_directory_for_pdfs(
        self, adapter: PDFAdapter, single_page_pdf: Path, multi_page_pdf: Path
    ):
        """Should find all PDFs in the documents directory."""
        pdfs = await adapter.scan_directory()

        assert len(pdfs) >= 2
        assert any("single-page.pdf" in str(p) for p in pdfs)
        assert any("multi-page.pdf" in str(p) for p in pdfs)

    async def test_scans_nested_directories(
        self, adapter: PDFAdapter, tagged_folder: Path
    ):
        """Should find PDFs in subdirectories."""
        pdfs = await adapter.scan_directory()

        assert len(pdfs) >= 1
        assert any("research-paper.pdf" in str(p) for p in pdfs)

    async def test_returns_empty_for_missing_directory(self, tmp_path: Path):
        """Should return empty list if documents directory doesn't exist."""
        adapter = PDFAdapter(documents_dir=tmp_path / "nonexistent")
        pdfs = await adapter.scan_directory()

        assert pdfs == []

    # === Metadata YAML Loading Tests ===

    def test_loads_folder_tags_from_meta_yaml(
        self, adapter: PDFAdapter, tagged_folder: Path
    ):
        """Should load tags from _meta.yaml file."""
        tags = adapter._load_folder_tags(tagged_folder)

        assert "research" in tags
        assert "academic" in tags

    def test_returns_empty_tags_when_no_meta_yaml(
        self, adapter: PDFAdapter, tmp_path: Path
    ):
        """Should return empty tags when no _meta.yaml exists."""
        tags = adapter._load_folder_tags(tmp_path)

        assert tags == []
