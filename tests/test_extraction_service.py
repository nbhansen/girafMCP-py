"""
Tests for ExtractionService.
"""

import pytest
from pathlib import Path
from unittest.mock import patch
import yaml

from girafmcp.core.services.extraction_service import ExtractionService

class TestExtractionService:
    
    @pytest.fixture
    def documents_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "documents"
        d.mkdir()
        return d
    
    @pytest.fixture
    def extracted_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "extracted"
        d.mkdir()
        return d
        
    @pytest.fixture
    def service(self, documents_dir: Path, extracted_dir: Path) -> ExtractionService:
        # Disable multiprocessing so mocks work in tests
        return ExtractionService(documents_dir, extracted_dir, use_multiprocessing=False)

    @pytest.mark.asyncio
    async def test_extract_all_processes_new_files(self, service: ExtractionService, documents_dir: Path, extracted_dir: Path):
        """Should extract new PDFs to Markdown."""
        
        # Setup source PDF
        pdf_path = documents_dir / "test.pdf"
        pdf_path.touch()
        
        # Mock pymupdf4llm
        with patch("girafmcp.core.services.extraction_service.pymupdf4llm") as mock_mu:
            mock_mu.to_markdown.return_value = "# Extracted Content"
            
            result = await service.extract_all()
            
            assert result.files_processed == 1
            assert result.files_skipped == 0
            
            # Check output file
            md_path = extracted_dir / "test.md"
            assert md_path.exists()
            
            content = md_path.read_text()
            assert content.startswith("---\n")
            assert "original_filename: test.pdf" in content
            assert "# Extracted Content" in content

    @pytest.mark.asyncio
    async def test_skips_up_to_date_files(self, service: ExtractionService, documents_dir: Path, extracted_dir: Path):
        """Should skip extraction if target is newer than source."""
        
        pdf_path = documents_dir / "test.pdf"
        pdf_path.touch()
        
        md_path = extracted_dir / "test.md"
        md_path.touch()
        
        # Ensure MD is newer (touch updates mtime)
        import time
        time.sleep(0.01)
        md_path.touch()
        
        with patch("girafmcp.core.services.extraction_service.pymupdf4llm") as mock_mu:
            result = await service.extract_all()
            
            assert result.files_processed == 0
            assert result.files_skipped == 1
            mock_mu.to_markdown.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_extract_overrides_skip(self, service: ExtractionService, documents_dir: Path, extracted_dir: Path):
        """Should extract even if up to date when force=True."""
        
        pdf_path = documents_dir / "test.pdf"
        pdf_path.touch()
        md_path = extracted_dir / "test.md"
        md_path.touch()
        
        with patch("girafmcp.core.services.extraction_service.pymupdf4llm") as mock_mu:
            mock_mu.to_markdown.return_value = "New Content"
            
            result = await service.extract_all(force=True)
            
            assert result.files_processed == 1
            assert result.files_skipped == 0
            mock_mu.to_markdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_preserves_subdirectories(self, service: ExtractionService, documents_dir: Path, extracted_dir: Path):
        """Should maintain directory structure in output."""
        
        sub = documents_dir / "sub" / "folder"
        sub.mkdir(parents=True)
        (sub / "doc.pdf").touch()
        
        with patch("girafmcp.core.services.extraction_service.pymupdf4llm") as mock_mu:
            mock_mu.to_markdown.return_value = "Content"
            
            await service.extract_all()
            
            expected_md = extracted_dir / "sub" / "folder" / "doc.md"
            assert expected_md.exists()

    @pytest.mark.asyncio
    async def test_reads_folder_tags(self, service: ExtractionService, documents_dir: Path, extracted_dir: Path):
        """Should read _meta.yaml tags and include in frontmatter."""
        
        # Setup meta file
        meta = {"tags": ["tagA", "tagB"]}
        (documents_dir / "_meta.yaml").write_text(yaml.dump(meta))
        
        (documents_dir / "doc.pdf").touch()
        
        with patch("girafmcp.core.services.extraction_service.pymupdf4llm") as mock_mu:
            mock_mu.to_markdown.return_value = "Content"
            
            await service.extract_all()
            
            md_path = extracted_dir / "doc.md"
            content = md_path.read_text()
            
            # Parse back frontmatter to verify
            parts = content.split("---\n")
            fm = yaml.safe_load(parts[1])
            assert fm["tags"] == ["tagA", "tagB"]
