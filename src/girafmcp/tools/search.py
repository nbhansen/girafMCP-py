"""Search-related tool handlers using vector store."""

import logging
from mcp.types import TextContent, Tool
from girafmcp.adapters import ChromaAdapter

logger = logging.getLogger(__name__)


def list_tools() -> list[Tool]:
    """Return tool definitions for search tools."""
    return [
        Tool(
            name="search_documentation",
            description="Semantic search across GIRAF wiki and documentation. Returns relevant sections with URLs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (natural language)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="search_static_documents",
            description="Semantic search over PDFs, research papers, and static documents. Returns content with page-level citations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (natural language)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5)",
                        "default": 5,
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags (e.g., ['research', 'handover'])",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_static_documents",
            description="List all ingested static documents (PDFs, research papers) with their tags.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


async def handle_search_documentation(
    adapter: ChromaAdapter, query: str, limit: int = 5
) -> list[TextContent]:
    """Search documentation using semantic search."""
    try:
        results = await adapter.search("wiki", query, limit)
        lines = [f"# Documentation Search Results for '{query}'", ""]
        
        for result in results:
            title = result.metadata.title or "Untitled"
            section = f" - {result.metadata.section}" if result.metadata.section else ""
            lines.append(f"## {title}{section}")
            lines.append(f"**Score:** {result.score:.2f}")
            if result.metadata.url:
                lines.append(f"**Source:** {result.metadata.url}")
            lines.append("")
            lines.append(result.content)
            lines.append("")
            lines.append("---")
            lines.append("")

        if not results:
            lines.append("No results found.")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error searching documentation for '{query}'", exc_info=True)
        return [TextContent(type="text", text=f"Error searching documentation: {e}")]


async def handle_search_static_documents(
    adapter: ChromaAdapter, query: str, limit: int = 5, tags: list[str] | None = None
) -> list[TextContent]:
    """Search static documents (PDFs) using semantic search."""
    try:
        # Note: ChromaDB adapter doesn't support tag filtering in search() yet in this implementation
        # For now, we search and then filter, or just search if tags not supported
        results = await adapter.search("documents", query, limit * 2) # Fetch extra for filtering
        
        if tags:
            results = [
                r for r in results 
                if any(tag in r.metadata.tags for tag in tags)
            ]
            results = results[:limit]
        else:
            results = results[:limit]

        lines = [f"# Static Documents Search Results for '{query}'", ""]
        
        for result in results:
            title = result.metadata.title or result.metadata.source or "Untitled"
            page_info = f" (Page {result.metadata.page})" if result.metadata.page else ""
            lines.append(f"## {title}{page_info}")
            lines.append(f"**Score:** {result.score:.2f}")
            if result.metadata.tags:
                lines.append(f"**Tags:** {', '.join(result.metadata.tags)}")
            lines.append("")
            lines.append(result.content)
            lines.append("")
            lines.append("---")
            lines.append("")

        if not results:
            lines.append("No results found.")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error searching static documents for '{query}'", exc_info=True)
        return [TextContent(type="text", text=f"Error searching static documents: {e}")]


async def handle_list_static_documents(adapter: ChromaAdapter) -> list[TextContent]:
    """List all ingested static documents."""
    try:
        count = await adapter.count("documents")
        lines = [
            "# Static Documents", 
            "", 
            f"Total documents indexed: {count}",
            "",
            "Note: Listing individual documents is not yet supported by the adapter."
        ]
        
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error("Error listing static documents", exc_info=True)
        return [TextContent(type="text", text=f"Error listing static documents: {e}")]