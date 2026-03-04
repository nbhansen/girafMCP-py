"""Port interfaces for the hexagonal architecture.

Ports define the boundaries between the core domain and external systems.
Adapters implement these ports to connect to specific technologies.
"""

from abc import ABC, abstractmethod

from .types import (
    CodeSearchResult,
    FileContent,
    Project,
    ProjectItem,
    Repository,
    TokenScopeResult,
)


class RepositoryPort(ABC):
    """Port interface for repository operations.

    Abstracts access to code repositories (GitHub, GitLab, etc.)
    """

    @abstractmethod
    async def list_repos(self, include_archived: bool = False) -> list[Repository]:
        """List all repositories in the organization.

        Args:
            include_archived: If True, include archived repositories. Default False.
        """
        ...

    @abstractmethod
    async def get_file(self, repo: str, path: str, ref: str | None = None) -> FileContent:
        """Get file content from a repository.

        Args:
            repo: Repository name
            path: File path within the repo
            ref: Git ref (branch, tag, commit). Defaults to default branch.

        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        ...

    @abstractmethod
    async def search_code(
        self, query: str, repo: str | None = None, include_archived: bool = False
    ) -> list[CodeSearchResult]:
        """Search for code across repositories.

        Args:
            query: Search query
            repo: Optional repository to limit search to
            include_archived: If True, include archived repositories. Default False.
        """
        ...

    @abstractmethod
    def get_permalink(
        self,
        repo: str,
        path: str,
        line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        """Generate a permalink to a file or line range.

        Args:
            repo: Repository name
            path: File path
            line: Optional start line number
            end_line: Optional end line number (for ranges)

        Returns:
            URL that will always point to the same content
        """
        ...


class GitHubProjectsPort(ABC):
    """Port interface for GitHub Projects V2 operations.

    Abstracts access to GitHub Projects V2 via GraphQL API.
    """

    @abstractmethod
    async def list_org_projects(self, limit: int = 20) -> list[Project]:
        """List all Projects V2 in the organization.

        Args:
            limit: Maximum number of projects to return.

        Returns:
            List of projects in the organization.
        """
        ...

    @abstractmethod
    async def get_project(self, project_number: int) -> Project | None:
        """Get a specific project by number.

        Args:
            project_number: The project number (visible in URL).

        Returns:
            Project if found, None otherwise.
        """
        ...

    @abstractmethod
    async def list_project_items(
        self,
        project_number: int,
        limit: int = 50,
        status_filter: str | None = None,
    ) -> list[ProjectItem]:
        """List items in a project.

        Args:
            project_number: The project number.
            limit: Maximum number of items to return.
            status_filter: Optional status value to filter by.

        Returns:
            List of project items (issues, PRs, drafts).
        """
        ...

    @abstractmethod
    async def check_token_scope(self) -> TokenScopeResult:
        """Check if the token has required scopes for Projects V2.

        Returns:
            TokenScopeResult with scope information.
        """
        ...
