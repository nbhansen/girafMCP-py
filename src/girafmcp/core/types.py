"""Domain types for the GIRAF MCP server."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class DocumentSource(str, Enum):
    """Source types for indexed documents."""

    WIKI = "wiki"
    CODE = "code"
    DOMAIN = "domain"
    HANDOVER = "handover"


@dataclass
class DocumentMetadata:
    """Metadata for indexed documents - includes source information for citations."""

    source: Literal["wiki", "code", "domain", "handover"]
    url: str  # URL to the original source (for citations)

    # For wiki/docs
    title: str | None = None
    section: str | None = None

    # For code
    repo: str | None = None
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    language: str | None = None

    # For domain knowledge
    topic: str | None = None
    tags: list[str] = field(default_factory=list)

    # Common
    last_updated: str | None = None


@dataclass
class Document:
    """A document to be stored in the vector database."""

    id: str
    content: str
    metadata: DocumentMetadata


@dataclass
class SearchResult:
    """Result from a vector search."""

    id: str
    content: str
    metadata: DocumentMetadata
    score: float  # Similarity score (0-1, higher is better)


@dataclass
class Repository:
    """A GitHub repository."""

    name: str
    description: str
    url: str
    language: str | None
    default_branch: str


@dataclass
class FileContent:
    """Content of a file from a repository."""

    content: str
    path: str
    repo: str
    url: str  # GitHub permalink
    sha: str


@dataclass
class CodeSearchResult:
    """Result from a code search."""

    repo: str
    path: str
    url: str  # Permalink to the file
    matches: list[str]  # Matching lines/snippets
