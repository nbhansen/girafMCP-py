"""Search-related tool handlers using vector store."""

import logging
from pathlib import Path
from collections import defaultdict
from typing import Any
from mcp.types import TextContent
from girafmcp.adapters import ChromaAdapter

logger = logging.getLogger(__name__)


async def handle_search_documentation(
    adapter: ChromaAdapter, query: str, limit: int = 5
) -> list[TextContent]:
    """Search documentation using semantic search."""
    try:
        results = await adapter.search("wiki", query, limit)
# ...
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error searching documentation for '{query}'", exc_info=True)
        return [TextContent(type="text", text=f"Error searching documentation: {e}")]


async def handle_search_static_documents(
    adapter: ChromaAdapter, query: str, limit: int = 5, tags: list[str] | None = None
) -> list[TextContent]:
    """Search static documents (PDFs) using semantic search."""
    try:
        # Fetch extra for filtering if tags are provided
# ...
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error searching static documents for '{query}'", exc_info=True)
        return [TextContent(type="text", text=f"Error searching static documents: {e}")]


async def handle_list_static_documents(adapter: ChromaAdapter) -> list[TextContent]:
    """List all ingested static documents."""
    try:
        # Get count first
# ...
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error("Error listing static documents", exc_info=True)
        return [TextContent(type="text", text=f"Error listing static documents: {e}")]
