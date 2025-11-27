"""Adapter implementations for external services."""

from .chroma_adapter import ChromaAdapter
from .file_adapter import FileAdapter
from .github_adapter import GitHubAdapter

__all__ = ["ChromaAdapter", "FileAdapter", "GitHubAdapter"]
