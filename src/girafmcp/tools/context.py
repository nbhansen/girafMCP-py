"""Context, domain knowledge, and persona tool handlers."""

import logging
import re
from mcp.types import TextContent
from girafmcp.adapters import FileAdapter

logger = logging.getLogger(__name__)


async def handle_get_project_context(adapter: FileAdapter) -> list[TextContent]:
    """Get the current project context."""
    try:
        context = adapter.get_context()
# ...
        return [TextContent(type="text", text="\n".join(lines))]

    except FileNotFoundError:
        return [TextContent(type="text", text="Project context file not found. Please create data/context.yaml")]
    except Exception as e:
        logger.error("Error reading project context", exc_info=True)
        return [TextContent(type="text", text=f"Error reading project context: {e}")]


async def handle_list_personas(adapter: FileAdapter) -> list[TextContent]:
    """List all available personas."""
    try:
        data = adapter.get_personas()
# ...
        return [TextContent(type="text", text="\n".join(lines))]

    except FileNotFoundError:
        return [TextContent(type="text", text="Personas file not found. Please create data/personas.yaml")]
    except Exception as e:
        logger.error("Error reading personas", exc_info=True)
        return [TextContent(type="text", text=f"Error reading personas: {e}")]


async def handle_get_persona(adapter: FileAdapter, persona_id: str) -> list[TextContent]:
    """Get details about a specific persona."""
    try:
        persona = adapter.get_persona(persona_id)
# ...
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error getting persona {persona_id}", exc_info=True)
        return [TextContent(type="text", text=f"Error getting persona: {e}")]


async def handle_search_domain_knowledge(
    adapter: FileAdapter, query: str, limit: int = 5
) -> list[TextContent]:
    """Search domain knowledge files."""
    try:
        results = adapter.search_domain(query, limit)
# ...
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error searching domain knowledge for '{query}'", exc_info=True)
        return [TextContent(type="text", text=f"Error searching domain knowledge: {e}")]


async def handle_list_domain_topics(adapter: FileAdapter) -> list[TextContent]:
    """List all domain knowledge topics."""
    try:
        files = adapter.list_domain_files()
# ...
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error("Error listing domain topics", exc_info=True)
        return [TextContent(type="text", text=f"Error listing domain topics: {e}")]

