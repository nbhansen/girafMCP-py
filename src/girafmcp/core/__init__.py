"""Core domain types and port interfaces."""

from .ports import GitHubProjectsPort, RepositoryPort
from .types import (
    CodeSearchResult,
    Document,
    DocumentMetadata,
    DocumentSource,
    FileContent,
    Project,
    ProjectItem,
    Repository,
    SearchResult,
    TokenScopeResult,
    WikiPage,
    WikiSearchResult,
)

__all__ = [
    "CodeSearchResult",
    "Document",
    "DocumentMetadata",
    "DocumentSource",
    "FileContent",
    "GitHubProjectsPort",
    "Project",
    "ProjectItem",
    "Repository",
    "RepositoryPort",
    "SearchResult",
    "TokenScopeResult",
    "WikiPage",
    "WikiSearchResult",
]
