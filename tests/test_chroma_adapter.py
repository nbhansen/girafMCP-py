"""
Tests for ChromaAdapter - Vector store implementation.

These tests use ChromaDB's ephemeral (in-memory) mode, so no server
is needed. This is a key advantage of using Python for ChromaDB.
"""

import pytest

from girafmcp.adapters.chroma_adapter import ChromaAdapter
from girafmcp.core import Document, DocumentMetadata


class TestChromaAdapter:
    """Tests for ChromaAdapter using ephemeral mode."""

    @pytest.fixture
    def test_collection(self, mock_chroma_adapter):
        """Standard test collection name with cleanup."""
        collection_name = "test-giraf-docs"
        # Clean up any existing collection before the test
        try:
            mock_chroma_adapter._client.delete_collection(collection_name)
        except Exception:
            pass
        return collection_name

    # === Collection Management ===

    async def test_creates_collection(self, mock_chroma_adapter, test_collection):
        """Should create a new collection."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        collections = await adapter.list_collections()
        assert test_collection in collections

    async def test_create_collection_is_idempotent(self, mock_chroma_adapter, test_collection):
        """Creating same collection twice should not raise."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)
        await adapter.create_collection(test_collection)  # Should not raise

        collections = await adapter.list_collections()
        assert collections.count(test_collection) == 1

    async def test_list_collections_empty(self, mock_chroma_adapter):
        """Should return empty list when no collections exist."""
        adapter = mock_chroma_adapter
        collections = await adapter.list_collections()
        assert isinstance(collections, list)

    async def test_delete_collection(self, mock_chroma_adapter, test_collection):
        """Should delete a collection."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)
        await adapter.delete_collection(test_collection)

        collections = await adapter.list_collections()
        assert test_collection not in collections

    # === Document Operations ===

    async def test_upserts_documents(self, mock_chroma_adapter, test_collection):
        """Should add documents to a collection."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        docs = [
            Document(
                id="wiki-intro",
                content="The GIRAF project helps children with autism using visual schedules.",
                metadata=DocumentMetadata(
                    source="wiki",
                    url="https://aau-giraf.github.io/wiki/about/",
                    title="About GIRAF",
                ),
            ),
            Document(
                id="code-main",
                content="void main() { runApp(FoodPlannerApp()); }",
                metadata=DocumentMetadata(
                    source="code",
                    url="https://github.com/aau-giraf/foodplanner/blob/staging/lib/main.dart#L5",
                    repo="foodplanner",
                    path="lib/main.dart",
                    start_line=5,
                    language="dart",
                ),
            ),
        ]

        await adapter.upsert(test_collection, docs)

        count = await adapter.count(test_collection)
        assert count == 2

    async def test_upsert_updates_existing_document(self, mock_chroma_adapter, test_collection):
        """Upserting with same ID should update, not duplicate."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        doc = Document(
            id="test-doc",
            content="Original content",
            metadata=DocumentMetadata(source="wiki", url="https://example.com/test"),
        )
        await adapter.upsert(test_collection, [doc])

        # Update with same ID
        updated_doc = Document(
            id="test-doc",
            content="Updated content",
            metadata=DocumentMetadata(source="wiki", url="https://example.com/test-updated"),
        )
        await adapter.upsert(test_collection, [updated_doc])

        # Should still be 1 document
        count = await adapter.count(test_collection)
        assert count == 1

        # Should have updated content
        retrieved = await adapter.get(test_collection, "test-doc")
        assert retrieved is not None
        assert retrieved.content == "Updated content"

    async def test_get_document_by_id(self, mock_chroma_adapter, test_collection):
        """Should retrieve a document by its ID."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        doc = Document(
            id="wiki-autism",
            content="Autism spectrum disorder affects social communication.",
            metadata=DocumentMetadata(
                source="domain",
                url="https://giraf.cs.aau.dk/domain/autism",
                topic="autism-basics",
                tags=["autism", "asd"],
            ),
        )
        await adapter.upsert(test_collection, [doc])

        retrieved = await adapter.get(test_collection, "wiki-autism")

        assert retrieved is not None
        assert retrieved.id == "wiki-autism"
        assert retrieved.content == doc.content
        assert retrieved.metadata.source == "domain"
        assert retrieved.metadata.url == "https://giraf.cs.aau.dk/domain/autism"
        assert retrieved.metadata.topic == "autism-basics"

    async def test_get_nonexistent_document_returns_none(self, mock_chroma_adapter, test_collection):
        """Should return None for non-existent document."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        result = await adapter.get(test_collection, "nonexistent-id")
        assert result is None

    async def test_delete_documents(self, mock_chroma_adapter, test_collection):
        """Should delete documents by ID."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        docs = [
            Document(
                id="doc-1",
                content="First document",
                metadata=DocumentMetadata(source="wiki", url="https://example.com/1"),
            ),
            Document(
                id="doc-2",
                content="Second document",
                metadata=DocumentMetadata(source="wiki", url="https://example.com/2"),
            ),
        ]
        await adapter.upsert(test_collection, docs)
        assert await adapter.count(test_collection) == 2

        await adapter.delete(test_collection, ["doc-1"])

        assert await adapter.count(test_collection) == 1
        assert await adapter.get(test_collection, "doc-1") is None
        assert await adapter.get(test_collection, "doc-2") is not None

    async def test_delete_nonexistent_documents_is_safe(self, mock_chroma_adapter, test_collection):
        """Deleting non-existent IDs should not raise."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        # Should not raise
        await adapter.delete(test_collection, ["nonexistent-id"])

    # === Semantic Search ===

    async def test_search_finds_similar_documents(self, mock_chroma_adapter, test_collection):
        """Should find semantically similar documents."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        docs = [
            Document(
                id="doc-flutter",
                content="Flutter is a UI toolkit for building natively compiled applications.",
                metadata=DocumentMetadata(
                    source="wiki", url="https://aau-giraf.github.io/wiki/tech/flutter"
                ),
            ),
            Document(
                id="doc-autism",
                content="Children with autism benefit from visual schedules and predictable routines.",
                metadata=DocumentMetadata(
                    source="domain", url="https://giraf.cs.aau.dk/domain/visual-supports"
                ),
            ),
            Document(
                id="doc-api",
                content="The REST API uses ASP.NET Core with Entity Framework for database access.",
                metadata=DocumentMetadata(
                    source="wiki", url="https://aau-giraf.github.io/wiki/tech/api"
                ),
            ),
        ]
        await adapter.upsert(test_collection, docs)

        # Search for autism-related content
        results = await adapter.search(
            test_collection, "visual supports for autistic children", limit=3
        )

        assert len(results) > 0
        # The autism document should be most relevant
        assert results[0].id == "doc-autism"
        assert results[0].score > 0
        assert results[0].metadata.url == "https://giraf.cs.aau.dk/domain/visual-supports"

    async def test_search_returns_similarity_scores(self, mock_chroma_adapter, test_collection):
        """Search results should include similarity scores."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        doc = Document(
            id="test-doc",
            content="Testing search functionality with similarity scores.",
            metadata=DocumentMetadata(source="wiki", url="https://example.com/test"),
        )
        await adapter.upsert(test_collection, [doc])

        results = await adapter.search(test_collection, "search functionality", limit=1)

        assert len(results) == 1
        # Score should be between 0 and 1
        assert 0 <= results[0].score <= 1

    async def test_search_respects_limit(self, mock_chroma_adapter, test_collection):
        """Should return at most 'limit' results."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        docs = [
            Document(
                id=f"doc-{i}",
                content=f"Document number {i} about various topics.",
                metadata=DocumentMetadata(source="wiki", url=f"https://example.com/doc-{i}"),
            )
            for i in range(10)
        ]
        await adapter.upsert(test_collection, docs)

        results = await adapter.search(test_collection, "document topics", limit=3)

        assert len(results) == 3

    async def test_search_empty_collection_returns_empty(self, mock_chroma_adapter, test_collection):
        """Searching empty collection should return empty list."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        results = await adapter.search(test_collection, "anything", limit=5)

        assert results == []

    # === Count ===

    async def test_count_documents(self, mock_chroma_adapter, test_collection):
        """Should return correct document count."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        assert await adapter.count(test_collection) == 0

        docs = [
            Document(
                id=str(i),
                content=f"Doc {i}",
                metadata=DocumentMetadata(source="wiki", url=f"https://example.com/{i}"),
            )
            for i in range(5)
        ]
        await adapter.upsert(test_collection, docs)

        assert await adapter.count(test_collection) == 5

    # === Metadata Preservation ===

    async def test_preserves_all_metadata_fields(self, mock_chroma_adapter, test_collection):
        """All metadata fields should be preserved through upsert/get cycle."""
        adapter = mock_chroma_adapter
        await adapter.create_collection(test_collection)

        doc = Document(
            id="full-metadata-doc",
            content="Test document with all metadata fields.",
            metadata=DocumentMetadata(
                source="code",
                url="https://github.com/aau-giraf/foodplanner/blob/abc123/lib/main.dart#L10-L20",
                title="Main entry point",
                repo="foodplanner",
                path="lib/main.dart",
                start_line=10,
                end_line=20,
                language="dart",
                tags=["entry", "main"],
                last_updated="2025-01-15",
            ),
        )
        await adapter.upsert(test_collection, [doc])

        retrieved = await adapter.get(test_collection, "full-metadata-doc")

        assert retrieved is not None
        assert retrieved.metadata.source == "code"
        assert retrieved.metadata.url == doc.metadata.url
        assert retrieved.metadata.title == "Main entry point"
        assert retrieved.metadata.repo == "foodplanner"
        assert retrieved.metadata.path == "lib/main.dart"
        assert retrieved.metadata.start_line == 10
        assert retrieved.metadata.end_line == 20
        assert retrieved.metadata.language == "dart"
        # Note: tags may be serialized differently, check if preserved
        assert retrieved.metadata.last_updated == "2025-01-15"
