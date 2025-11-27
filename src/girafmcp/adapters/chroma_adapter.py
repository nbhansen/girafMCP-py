"""ChromaDB adapter implementing VectorStorePort.

Provides semantic search capabilities for GIRAF documentation using
ChromaDB as the vector database. Supports both ephemeral (in-memory)
mode for testing and persistent mode for production.
"""

from dataclasses import asdict
from typing import Any

import chromadb
from chromadb.config import Settings

from girafmcp.core import Document, DocumentMetadata, SearchResult, VectorStorePort


class ChromaAdapter(VectorStorePort):
    """ChromaDB adapter for vector store operations."""

    def __init__(
        self,
        ephemeral: bool = False,
        persist_directory: str | None = None,
        host: str | None = None,
        port: int | None = None,
    ):
        """Initialize the ChromaDB adapter.

        Args:
            ephemeral: Use in-memory storage (for testing)
            persist_directory: Directory for persistent storage
            host: ChromaDB server host (for client mode)
            port: ChromaDB server port (for client mode)
        """
        if ephemeral:
            # In-memory client for testing - no server needed!
            self._client = chromadb.Client(Settings(anonymized_telemetry=False))
        elif host and port:
            # Connect to remote ChromaDB server
            self._client = chromadb.HttpClient(host=host, port=port)
        elif persist_directory:
            # Persistent local storage
            self._client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False),
            )
        else:
            # Default: ephemeral
            self._client = chromadb.Client(Settings(anonymized_telemetry=False))

    async def search(
        self, collection: str, query: str, limit: int = 10
    ) -> list[SearchResult]:
        """Search for similar documents using semantic similarity."""
        try:
            col = self._client.get_collection(collection)

            # ChromaDB query - it handles embedding automatically
            results = col.query(query_texts=[query], n_results=limit)

            if not results["ids"] or not results["ids"][0]:
                return []

            search_results: list[SearchResult] = []
            for i, doc_id in enumerate(results["ids"][0]):
                content = results["documents"][0][i] if results["documents"] else ""
                metadata_dict = results["metadatas"][0][i] if results["metadatas"] else {}

                # Convert distance to similarity score (ChromaDB returns L2 distance)
                # Lower distance = more similar, so we convert to 0-1 scale
                distance = results["distances"][0][i] if results["distances"] else 0
                # Simple conversion: score = 1 / (1 + distance)
                score = 1 / (1 + distance)

                search_results.append(
                    SearchResult(
                        id=doc_id,
                        content=content,
                        metadata=self._deserialize_metadata(metadata_dict),
                        score=score,
                    )
                )

            return search_results

        except Exception:
            # Collection doesn't exist or other error
            return []

    async def upsert(self, collection: str, documents: list[Document]) -> None:
        """Add or update documents in a collection."""
        col = self._client.get_collection(collection)

        col.upsert(
            ids=[doc.id for doc in documents],
            documents=[doc.content for doc in documents],
            metadatas=[self._serialize_metadata(doc.metadata) for doc in documents],
        )

    async def delete(self, collection: str, ids: list[str]) -> None:
        """Delete documents by ID."""
        try:
            col = self._client.get_collection(collection)
            col.delete(ids=ids)
        except Exception:
            # Gracefully handle deletion of non-existent IDs
            pass

    async def get(self, collection: str, id: str) -> Document | None:
        """Get a document by ID."""
        try:
            col = self._client.get_collection(collection)
            result = col.get(ids=[id])

            if not result["ids"]:
                return None

            return Document(
                id=result["ids"][0],
                content=result["documents"][0] if result["documents"] else "",
                metadata=self._deserialize_metadata(
                    result["metadatas"][0] if result["metadatas"] else {}
                ),
            )

        except Exception:
            return None

    async def list_collections(self) -> list[str]:
        """List all collections."""
        collections = self._client.list_collections()
        return [col.name for col in collections]

    async def create_collection(self, collection: str) -> None:
        """Create a collection if it doesn't exist."""
        try:
            self._client.create_collection(collection)
        except Exception:
            # Collection might already exist
            pass

    async def delete_collection(self, collection: str) -> None:
        """Delete a collection."""
        self._client.delete_collection(collection)

    async def count(self, collection: str) -> int:
        """Get the count of documents in a collection."""
        col = self._client.get_collection(collection)
        return col.count()

    def _serialize_metadata(self, metadata: DocumentMetadata) -> dict[str, Any]:
        """Serialize metadata to ChromaDB format.

        ChromaDB only supports primitive types, so we need to handle
        lists and None values specially.
        """
        result: dict[str, Any] = {}

        # Convert dataclass to dict
        metadata_dict = asdict(metadata)

        for key, value in metadata_dict.items():
            if value is None:
                continue
            elif isinstance(value, list):
                # Convert list to comma-separated string
                result[key] = ",".join(str(v) for v in value)
            else:
                result[key] = value

        return result

    def _deserialize_metadata(self, data: dict[str, Any]) -> DocumentMetadata:
        """Deserialize metadata from ChromaDB format."""
        # Handle tags specially - convert from comma-separated string
        tags: list[str] = []
        if "tags" in data and data["tags"]:
            tags = data["tags"].split(",")

        return DocumentMetadata(
            source=data.get("source", "wiki"),  # type: ignore
            url=data.get("url", ""),
            title=data.get("title"),
            section=data.get("section"),
            repo=data.get("repo"),
            path=data.get("path"),
            start_line=data.get("start_line"),
            end_line=data.get("end_line"),
            language=data.get("language"),
            topic=data.get("topic"),
            tags=tags if tags else [],
            last_updated=data.get("last_updated"),
        )
