"""Core domain types and port interfaces."""

from .ports import RepositoryPort, VectorStorePort
from .types import (
    CodeSearchResult,
    Document,
    DocumentMetadata,
    DocumentSource,
    FileContent,
    Repository,
    SearchResult,
)

__all__ = [
    "CodeSearchResult",
    "Document",
    "DocumentMetadata",
    "DocumentSource",
    "FileContent",
    "Repository",
    "RepositoryPort",
    "SearchResult",
    "VectorStorePort",
]
