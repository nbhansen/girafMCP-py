"""Adapter implementations for external services."""

from .chroma_adapter import ChromaAdapter
from .github_adapter import GitHubAdapter

__all__ = ["ChromaAdapter", "GitHubAdapter"]
