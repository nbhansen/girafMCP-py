"""Extraction service for converting PDFs to Markdown artifacts.

Handles the conversion of raw PDF documents into structured Markdown files
stored in a separate 'extracted' directory. Preserves metadata via YAML frontmatter.
"""

import logging
import multiprocessing
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf4llm  # type: ignore[import-untyped]
import yaml

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of an extraction operation."""

    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    errors: list[str] = field(default_factory=list)


def run_extraction_task(source_path: Path, target_path: Path, tags: list[str]) -> None:
    """Run extraction for a single file.
    
    This function is run in a separate process to ensure memory cleanup.
    """
    try:
        # Convert to Markdown using PyMuPDF4LLM
        md_content = pymupdf4llm.to_markdown(str(source_path))
        
        # Construct Frontmatter
        frontmatter = {
            "source": "pdf",
            "original_filename": source_path.name,
            "title": source_path.stem,
            "tags": tags,
            "extraction_tool": "pymupdf4llm"
        }
        
        # Write file
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("---\n")
            yaml.dump(frontmatter, f, default_flow_style=False)
            f.write("---\n\n")
            f.write(md_content)
    except Exception as e:
        # Re-raise to be caught by the pool error handler or main loop
        raise RuntimeError(f"Failed to extract {source_path}: {str(e)}") from e


class ExtractionService:
    """Service for extracting Markdown from PDFs."""

    def __init__(
        self,
        documents_dir: Path,
        extracted_dir: Path,
        use_multiprocessing: bool = True,
    ):
        """Initialize the extraction service.

        Args:
            documents_dir: Source directory containing PDFs.
            extracted_dir: Target directory for Markdown artifacts.
            use_multiprocessing: If True, run extraction in separate processes
                to prevent memory leaks. Set to False for testing with mocks.
        """
        self.documents_dir = documents_dir
        self.extracted_dir = extracted_dir
        self.use_multiprocessing = use_multiprocessing

    async def extract_all(self, force: bool = False) -> ExtractionResult:
        """Scan documents directory and extract all PDFs to Markdown.

        Args:
            force: If True, re-extract even if source hasn't changed.

        Returns:
            ExtractionResult with counts.
        """
        if not self.documents_dir.exists():
            logger.warning(f"Documents directory not found: {self.documents_dir}")
            return ExtractionResult()

        self.extracted_dir.mkdir(parents=True, exist_ok=True)

        result = ExtractionResult()
        pdf_paths = list(self.documents_dir.rglob("*.pdf"))
        
        # Prepare tasks
        tasks = []
        for pdf_path in pdf_paths:
            # Calculate relative path to mirror structure
            try:
                rel_path = pdf_path.relative_to(self.documents_dir)
            except ValueError:
                continue # Should not happen given rglob

            target_path = self.extracted_dir / rel_path.with_suffix(".md")

            # Skip if up to date
            if not force and self._is_up_to_date(pdf_path, target_path):
                result.files_skipped += 1
                continue

            # Ensure target directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get metadata
            tags = self._load_folder_tags(pdf_path.parent)
            
            tasks.append((pdf_path, target_path, tags))

        # Run extraction - either in separate processes (production) or in-process (testing)
        if tasks:
            if self.use_multiprocessing:
                # Use separate process for each file to prevent memory leaks
                # maxtasksperchild=1 forces a new process for each task
                with multiprocessing.Pool(processes=1, maxtasksperchild=1) as pool:
                    for pdf_path, target_path, tags in tasks:
                        try:
                            pool.apply(run_extraction_task, args=(pdf_path, target_path, tags))
                            result.files_processed += 1
                            logger.info(f"Successfully extracted: {pdf_path.name}")
                        except Exception as e:
                            error_msg = f"Error extracting {pdf_path}: {e}"
                            logger.error(error_msg)
                            result.errors.append(error_msg)
                            result.files_failed += 1
            else:
                # Run in-process (useful for testing with mocks)
                for pdf_path, target_path, tags in tasks:
                    try:
                        run_extraction_task(pdf_path, target_path, tags)
                        result.files_processed += 1
                        logger.info(f"Successfully extracted: {pdf_path.name}")
                    except Exception as e:
                        error_msg = f"Error extracting {pdf_path}: {e}"
                        logger.error(error_msg)
                        result.errors.append(error_msg)
                        result.files_failed += 1

        return result

    def _is_up_to_date(self, source: Path, target: Path) -> bool:
        """Check if target is newer than source."""
        if not target.exists():
            return False
        return target.stat().st_mtime >= source.stat().st_mtime

    def _load_folder_tags(self, folder: Path) -> list[str]:
        """Load tags from _meta.yaml in the folder."""
        meta_path = folder / "_meta.yaml"
        if not meta_path.exists():
            return []
        
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = yaml.safe_load(f) or {}
                return list(meta.get("tags", []))
        except Exception:
            return []
