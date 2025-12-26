"""GitHub-related tool handlers."""

import logging
from mcp.types import TextContent
from girafmcp.adapters import GitHubAdapter
from girafmcp.core import WikiPage

logger = logging.getLogger(__name__)


async def handle_list_repositories(adapter: GitHubAdapter) -> list[TextContent]:
    """List all GIRAF repositories."""
    try:
        repos = await adapter.list_repos()
# ...
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error("Error listing repositories", exc_info=True)
        return [TextContent(type="text", text=f"Error listing repositories: {e}")]


async def handle_get_file(
    adapter: GitHubAdapter, repo: str, path: str, ref: str | None = None
) -> list[TextContent]:
    """Get file content from a repository."""
    try:
        file = await adapter.get_file(repo, path, ref)
# ...
        return [TextContent(type="text", text=result)]

    except FileNotFoundError:
        return [TextContent(type="text", text=f"File not found: {repo}/{path}")]
    except Exception as e:
        logger.error(f"Error fetching file {repo}/{path}", exc_info=True)
        return [TextContent(type="text", text=f"Error fetching file: {e}")]


async def handle_search_code(
    adapter: GitHubAdapter, query: str, repo: str | None = None
) -> list[TextContent]:
    """Search for code across repositories."""
    try:
        results = await adapter.search_code(query, repo)
# ...
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error searching code for '{query}'", exc_info=True)
        return [TextContent(type="text", text=f"Error searching code: {e}")]


async def handle_get_permalink(
# ...
) -> list[TextContent]:
    """Generate a permalink for citation."""
    # Permalinks are generated locally, minimal risk of error needing logging
    link = adapter.get_permalink(repo, path, line, end_line)
# ...

async def handle_search_wiki(
    adapter: GitHubAdapter, query: str, limit: int = 5
) -> list[TextContent]:
    """Search wiki documentation."""
    try:
        results = await adapter.search_wiki(query, limit=limit)
# ...
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error searching wiki for '{query}'", exc_info=True)
        return [TextContent(type="text", text=f"Error searching wiki: {e}")]


async def handle_list_wiki_pages(adapter: GitHubAdapter) -> list[TextContent]:
    """List all wiki pages."""
    try:
        pages = await adapter.list_wiki_pages()
# ...
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error("Error listing wiki pages", exc_info=True)
        return [TextContent(type="text", text=f"Error listing wiki pages: {e}")]
