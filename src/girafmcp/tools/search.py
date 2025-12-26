"""Search-related tool handlers using vector store."""

from pathlib import Path
from collections import defaultdict
from typing import Any
from mcp.types import TextContent
from girafmcp.adapters import ChromaAdapter


async def handle_search_documentation(
    adapter: ChromaAdapter, query: str, limit: int = 5
) -> list[TextContent]:
    """Search documentation using semantic search."""
    try:
        results = await adapter.search("wiki", query, limit)

        if not results:
            return [
                TextContent(
                    type="text",
                    text=f"No documentation found matching: {query}\n\n"
                    "Note: The documentation index may need to be populated first.",
                )
            ]

        lines = [f"# Documentation Search Results for: {query}\n"]
        for result in results:
            title = result.metadata.title or "Untitled"
            lines.append(f"## {title}")
            lines.append(f"**Source:** {result.metadata.url}")
            lines.append(f"**Relevance:** {result.score:.2%}")
            lines.append("")
            # Show snippet of content
            snippet = result.content[:500] + "..." if len(result.content) > 500 else result.content
            lines.append(snippet)
            lines.append("")
            lines.append("---")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error searching documentation: {e}")]


async def handle_search_static_documents(
    adapter: ChromaAdapter, query: str, limit: int = 5, tags: list[str] | None = None
) -> list[TextContent]:
    """Search static documents (PDFs) using semantic search."""
    try:
        # Fetch extra for filtering if tags are provided
        fetch_limit = limit * 2 if tags else limit
        results = await adapter.search("static_documents", query, fetch_limit)

        if not results:
            return [
                TextContent(
                    type="text",
                    text=f"No static documents found matching: {query}\n\n"
                    "Note: Documents must be ingested first. Set GIRAF_DOCUMENTS_DIR environment variable.",
                )
            ]

        # Filter by tags if provided
        if tags:
            results = [
                r for r in results
                if r.metadata.tags and any(t in r.metadata.tags for t in tags)
            ]

        # Limit results after filtering
        results = results[:limit]

        if not results:
            return [
                TextContent(
                    type="text",
                    text=f"No documents found matching tags: {tags}\n\n"
                    "Try removing tag filters or use `list_static_documents` to see available tags.",
                )
            ]

        lines = [f"# Static Document Search: {query}\n"]
        if tags:
            lines.append(f"*Filtered by tags: {', '.join(tags)}*\n")

        for result in results:
            # Extract filename from URL/path
            title = result.metadata.title or Path(result.metadata.url).name
            page = result.metadata.page

            if page:
                lines.append(f"## {title} (Page {page})")
            else:
                lines.append(f"## {title}")

            lines.append(f"**Source:** {result.metadata.url}")

            if result.metadata.tags:
                lines.append(f"**Tags:** {', '.join(result.metadata.tags)}")

            lines.append(f"**Relevance:** {result.score:.2%}")
            lines.append("")

            # Show content snippet
            snippet = result.content[:500] + "..." if len(result.content) > 500 else result.content
            lines.append(snippet)
            lines.append("")
            lines.append("---")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error searching static documents: {e}")]


async def handle_list_static_documents(adapter: ChromaAdapter) -> list[TextContent]:
    """List all ingested static documents."""
    try:
        # Get count first
        count = await adapter.count("static_documents")

        if count == 0:
            return [
                TextContent(
                    type="text",
                    text="No static documents have been ingested.\n\n"
                    "To ingest documents:\n"
                    "1. Set GIRAF_DOCUMENTS_DIR environment variable\n"
                    "2. Add PDF files to that directory\n"
                    "3. Restart the server (auto-ingest on startup)",
                )
            ]

        # Search with empty query to get all documents
        results = await adapter.search("static_documents", " ", limit=100)

        # Group by file
        by_file: dict[str, dict[str, Any]] = defaultdict(lambda: {"pages": [], "tags": []})
        for result in results:
            if result.id.startswith("_"):  # Skip internal documents
                continue

            url = result.metadata.url
            by_file[url]["pages"].append(result.metadata.page)
            if result.metadata.tags:
                by_file[url]["tags"] = result.metadata.tags

        lines = [f"# Static Documents ({count} chunks from {len(by_file)} files)\n"]

        # Collect all tags
        all_tags: set[str] = set()
        for info in by_file.values():
            all_tags.update(info["tags"])

        if all_tags:
            lines.append(f"**Available tags:** {', '.join(sorted(all_tags))}\n")

        for url, info in sorted(by_file.items()):
            filename = Path(url).name
            page_count = len(set(info["pages"]))
            tags_str = f" [{', '.join(info['tags'])}]" if info["tags"] else ""

            lines.append(f"- **{filename}**{tags_str} - {page_count} pages")

        lines.append("")
        lines.append("---")
        lines.append("Use `search_static_documents` to search within these documents.")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error listing static documents: {e}")]
