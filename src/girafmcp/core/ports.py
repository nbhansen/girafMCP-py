"""Port interfaces for the hexagonal architecture.

Ports define the boundaries between the core domain and external systems.
Adapters implement these ports to connect to specific technologies.
"""

from abc import ABC, abstractmethod

from .types import (
    CodeSearchResult,
    Document,
    FileContent,
    Repository,
    SearchResult,
)


class RepositoryPort(ABC):
    """Port interface for repository operations.

    Abstracts access to code repositories (GitHub, GitLab, etc.)
    """

    @abstractmethod
    async def list_repos(self) -> list[Repository]:
        """List all repositories in the organization."""
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
    async def search_code(self, query: str, repo: str | None = None) -> list[CodeSearchResult]:
        """Search for code across repositories.

        Args:
            query: Search query
            repo: Optional repository to limit search to
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


class VectorStorePort(ABC):
    """Port interface for vector store operations.

    Abstracts semantic search functionality (ChromaDB, Qdrant, etc.)
    """

    @abstractmethod
    async def search(
        self, collection: str, query: str, limit: int = 10
    ) -> list[SearchResult]:
        """Search for similar documents.

        Args:
            collection: Collection name (e.g., 'wiki', 'code', 'domain')
            query: Search query (will be embedded)
            limit: Maximum number of results
        """
        ...

    @abstractmethod
    async def upsert(self, collection: str, documents: list[Document]) -> None:
        """Add or update documents in a collection.

        Args:
            collection: Collection name
            documents: Documents to upsert
        """
        ...

    @abstractmethod
    async def delete(self, collection: str, ids: list[str]) -> None:
        """Delete documents by ID.

        Args:
            collection: Collection name
            ids: Document IDs to delete
        """
        ...

    @abstractmethod
    async def get(self, collection: str, id: str) -> Document | None:
        """Get a document by ID.

        Args:
            collection: Collection name
            id: Document ID
        """
        ...

    @abstractmethod
    async def list_collections(self) -> list[str]:
        """List all collections."""
        ...

    @abstractmethod
    async def create_collection(self, collection: str) -> None:
        """Create a collection if it doesn't exist."""
        ...

    @abstractmethod
    async def delete_collection(self, collection: str) -> None:
        """Delete a collection."""
        ...

    @abstractmethod
    async def count(self, collection: str) -> int:
        """Get the count of documents in a collection."""
        ...
