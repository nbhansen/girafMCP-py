"""Keyword search adapter for extracted markdown documents.

Replaces ChromaDB semantic search with simple keyword matching
over the already-extracted markdown files in data/extracted/.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SearchHit:
    """A single search result."""

    title: str
    path: str
    snippet: str
    score: float
    tags: list[str]
    page: int | None = None


@dataclass
class DocumentInfo:
    """Metadata about an extracted document."""

    title: str
    path: str
    tags: list[str]
    source: str | None = None


class KeywordSearchAdapter:
    """Search extracted markdown files using keyword matching."""

    def __init__(self, extracted_dir: Path | None = None) -> None:
        self.extracted_dir = extracted_dir

    def _parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        """Parse YAML frontmatter from markdown content."""
        if content.startswith("---\n"):
            try:
                parts = content.split("---\n", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    body = parts[2]
                    return frontmatter or {}, body
            except Exception:
                pass
        return {}, content

    def _scan_files(self) -> list[Path]:
        """Find all markdown files in the extracted directory."""
        if self.extracted_dir is None or not self.extracted_dir.exists():
            return []
        return sorted(self.extracted_dir.rglob("*.md"))

    def _extract_snippet(self, text: str, keywords: list[str], context_chars: int = 200) -> str:
        """Extract a snippet around the first keyword match."""
        text_lower = text.lower()
        best_pos = len(text)
        for kw in keywords:
            pos = text_lower.find(kw)
            if pos != -1 and pos < best_pos:
                best_pos = pos

        if best_pos == len(text):
            # No keyword found, return start of text
            return text[:context_chars * 2].strip()

        start = max(0, best_pos - context_chars)
        end = min(len(text), best_pos + context_chars)
        snippet = text[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet

    async def search(
        self,
        query: str,
        limit: int = 5,
        tags: list[str] | None = None,
    ) -> list[SearchHit]:
        """Search extracted markdown files by keyword matching.

        Scores by number of keyword occurrences. Returns snippets with context.
        """
        files = self._scan_files()
        if not files:
            return []

        keywords = [kw.lower() for kw in query.split() if len(kw) >= 2]
        if not keywords:
            return []

        hits: list[SearchHit] = []

        for md_path in files:
            try:
                content = md_path.read_text(encoding="utf-8")
                frontmatter, body = self._parse_frontmatter(content)

                # Tag filtering
                doc_tags = frontmatter.get("tags", [])
                if tags and not any(t in doc_tags for t in tags):
                    continue

                title = frontmatter.get("title", md_path.stem)
                body_lower = body.lower()

                # Score: count keyword occurrences
                score = sum(body_lower.count(kw) for kw in keywords)
                if score == 0:
                    continue

                snippet = self._extract_snippet(body, keywords)

                hits.append(
                    SearchHit(
                        title=title,
                        path=str(md_path),
                        snippet=snippet,
                        score=float(score),
                        tags=doc_tags,
                    )
                )

            except Exception as e:
                logger.warning(f"Error reading {md_path}: {e}")

        # Sort by score descending
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]

    async def list_documents(self) -> list[DocumentInfo]:
        """List all extracted markdown documents with their metadata."""
        files = self._scan_files()
        docs: list[DocumentInfo] = []

        for md_path in files:
            try:
                # Read only the frontmatter (first few lines)
                content = md_path.read_text(encoding="utf-8")
                frontmatter, _ = self._parse_frontmatter(content)
                docs.append(
                    DocumentInfo(
                        title=frontmatter.get("title", md_path.stem),
                        path=str(md_path),
                        tags=frontmatter.get("tags", []),
                        source=frontmatter.get("source"),
                    )
                )
            except Exception as e:
                logger.warning(f"Error reading {md_path}: {e}")

        return docs
