"""Adapter implementations for external services."""

from .file_adapter import FileAdapter
from .github_adapter import GitHubAdapter
from .github_projects_adapter import GitHubProjectsAdapter
from .keyword_search_adapter import KeywordSearchAdapter

__all__ = ["FileAdapter", "GitHubAdapter", "GitHubProjectsAdapter", "KeywordSearchAdapter"]
