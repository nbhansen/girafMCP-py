"""File adapter for reading YAML configuration files.

Provides access to project context, personas, and domain knowledge
stored in local YAML/Markdown files.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DomainSearchResult:
    """Result from searching domain knowledge."""

    filename: str
    title: str
    section: str
    content: str
    relevance: float


class FileAdapter:
    """Adapter for reading local configuration and content files."""

    def __init__(self, data_dir: Path | str | None = None):
        """Initialize the file adapter.

        Args:
            data_dir: Path to the data directory. Defaults to ./data
        """
        if data_dir is None:
            # Default to data/ relative to the package
            self.data_dir = Path(__file__).parent.parent.parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)

    def read_yaml(self, filename: str) -> dict[str, Any]:
        """Read a YAML file from the data directory.

        Args:
            filename: Name of the YAML file (e.g., 'context.yaml')

        Returns:
            Parsed YAML content as a dictionary

        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        file_path = self.data_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def get_context(self) -> dict[str, Any]:
        """Get the project context.

        Returns:
            Project context dictionary from context.yaml
        """
        return self.read_yaml("context.yaml")

    def get_personas(self) -> dict[str, Any]:
        """Get the personas configuration.

        Returns:
            Personas dictionary from personas.yaml
        """
        return self.read_yaml("personas.yaml")

    def get_persona(self, persona_id: str) -> dict[str, Any] | None:
        """Get a specific persona by ID.

        Args:
            persona_id: The persona identifier (e.g., 'cs_student')

        Returns:
            Persona dictionary or None if not found
        """
        personas = self.get_personas()
        return personas.get("personas", {}).get(persona_id)

    def list_domain_files(self) -> list[Path]:
        """List all domain knowledge files.

        Returns:
            List of paths to markdown files in data/domain/
        """
        domain_dir = self.data_dir / "domain"
        if not domain_dir.exists():
            return []

        return list(domain_dir.glob("*.md"))

    def read_domain_file(self, filename: str) -> str:
        """Read a domain knowledge markdown file.

        Args:
            filename: Name of the markdown file

        Returns:
            Content of the file
        """
        file_path = self.data_dir / "domain" / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Domain file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def search_domain(self, query: str, limit: int = 5) -> list[DomainSearchResult]:
        """Search domain knowledge files for relevant content.

        Performs simple keyword matching with section extraction.

        Args:
            query: Search query (keywords)
            limit: Maximum number of results

        Returns:
            List of search results with relevance scores
        """
        results: list[DomainSearchResult] = []
        query_terms = query.lower().split()

        for file_path in self.list_domain_files():
            content = file_path.read_text(encoding="utf-8")
            filename = file_path.name

            # Extract title from first H1
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            title = title_match.group(1) if title_match else filename

            # Split into sections by H2 headers
            sections = re.split(r"(?=^##\s+)", content, flags=re.MULTILINE)

            for section in sections:
                if not section.strip():
                    continue

                section_lower = section.lower()

                # Count keyword matches
                matches = sum(1 for term in query_terms if term in section_lower)
                if matches == 0:
                    continue

                # Calculate relevance (percentage of query terms found)
                relevance = matches / len(query_terms)

                # Extract section header
                header_match = re.search(r"^##?\s+(.+)$", section, re.MULTILINE)
                section_title = header_match.group(1) if header_match else "Introduction"

                # Get a relevant snippet (first paragraph with a match)
                paragraphs = section.split("\n\n")
                snippet = ""
                for para in paragraphs:
                    if any(term in para.lower() for term in query_terms):
                        snippet = para.strip()[:500]
                        break

                if not snippet:
                    snippet = section.strip()[:500]

                results.append(
                    DomainSearchResult(
                        filename=filename,
                        title=title,
                        section=section_title,
                        content=snippet,
                        relevance=relevance,
                    )
                )

        # Sort by relevance and limit
        results.sort(key=lambda r: r.relevance, reverse=True)
        return results[:limit]
