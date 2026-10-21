"""
Tests for MarkdownAdapter - parsing extracted artifacts.
"""

from pathlib import Path

import pytest

from girafmcp.adapters.markdown_adapter import MarkdownAdapter


class TestMarkdownAdapter:
    
    @pytest.fixture
    def extracted_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "extracted"
        d.mkdir()
        return d
    
    @pytest.fixture
    def adapter(self, extracted_dir: Path) -> MarkdownAdapter:
        return MarkdownAdapter(extracted_dir=extracted_dir)
        
    async def test_extract_documents_parses_frontmatter(self, adapter: MarkdownAdapter, extracted_dir: Path):
        """Should parse YAML frontmatter correctly."""
        md_file = extracted_dir / "test.md"
        content = """---
title: My Test Doc
original_filename: original.pdf
tags:
- tag1
- tag2
---

# Content
This is page 1.
"""
        md_file.write_text(content, encoding="utf-8")
        
        docs = await adapter.extract_documents(md_file)
        
        assert len(docs) == 1
        assert docs[0].metadata.title == "My Test Doc"
        assert docs[0].metadata.tags == ["tag1", "tag2"]
        # ID generation uses original filename stem "original"
        assert "original" in docs[0].id
        
    async def test_extract_documents_splits_pages(self, adapter: MarkdownAdapter, extracted_dir: Path):
        """Should split content by page separators."""
        md_file = extracted_dir / "paged.md"
        content = """---
original_filename: paged.pdf
---

Page 1 content
-----
Page 2 content
-----
Page 3 content
"""
        md_file.write_text(content, encoding="utf-8")
        
        docs = await adapter.extract_documents(md_file)
        
        assert len(docs) == 3
        assert docs[0].metadata.page == 1
        assert "Page 1 content" in docs[0].content
        assert docs[1].metadata.page == 2
        assert "Page 2 content" in docs[1].content
        assert docs[2].metadata.page == 3
        assert "Page 3 content" in docs[2].content

    async def test_extract_documents_chunks_large_pages(self, adapter: MarkdownAdapter, extracted_dir: Path):
        """Should chunk large pages into multiple documents."""
        # Adapter defaults: max_chunk_size=1500
        adapter.max_chunk_size = 10
        adapter.chunk_overlap = 0
        
        md_file = extracted_dir / "large.md"
        content = """---
original_filename: large.pdf
---
12345678901234567890
"""
        md_file.write_text(content, encoding="utf-8")
        
        docs = await adapter.extract_documents(md_file)
        
        # Should be split into 2 chunks of size 10
        assert len(docs) == 2
        assert docs[0].content == "1234567890"
        assert docs[1].content == "1234567890"
        
    async def test_scan_directory(self, adapter: MarkdownAdapter, extracted_dir: Path):
        """Should list all .md files in directory."""
        (extracted_dir / "doc1.md").touch()
        (extracted_dir / "doc2.md").touch()
        (extracted_dir / "ignore.txt").touch()
        
        files = await adapter.scan_directory()
        assert len(files) == 2
        assert all(f.suffix == ".md" for f in files)
