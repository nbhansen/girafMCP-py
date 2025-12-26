"""GitHub-related tool handlers."""

import logging
from mcp.types import TextContent
from girafmcp.adapters import GitHubAdapter

logger = logging.getLogger(__name__)


async def handle_list_repositories(adapter: GitHubAdapter) -> list[TextContent]:
    """List all GIRAF repositories."""
    try:
        repos = await adapter.list_repos()
        lines = ["# GIRAF Repositories", ""]
        
        for repo in repos:
            lines.append(f"## {repo.name}")
            lines.append(f"**Description:** {repo.description}")
            lines.append(f"**URL:** {repo.url}")
            lines.append(f"**Language:** {repo.language}")
            lines.append("")

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
        
        header = f"# File: {file.path}\n**Repo:** {file.repo}\n**Permalink:** {file.url}\n\n```\n"
        footer = "\n```"
        
        return [TextContent(type="text", text=header + file.content + footer)]

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
        lines = [f"# Code Search Results for '{query}'", ""]
        
        for result in results:
            lines.append(f"- **{result.repo}**: [{result.path}]({result.url})")
            
        if not results:
            lines.append("No results found.")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error searching code for '{query}'", exc_info=True)
        return [TextContent(type="text", text=f"Error searching code: {e}")]


async def handle_get_permalink(
    adapter: GitHubAdapter, 
    repo: str, 
    path: str, 
    line: int | None = None, 
    end_line: int | None = None
) -> list[TextContent]:
    """Generate a permalink for citation."""
    # Permalinks are generated locally, minimal risk of error needing logging
    link = adapter.get_permalink(repo, path, line, end_line)
    return [TextContent(type="text", text=link)]


async def handle_search_wiki(
    adapter: GitHubAdapter, query: str, limit: int = 5
) -> list[TextContent]:
    """Search wiki documentation."""
    try:
        results = await adapter.search_wiki(query, limit=limit)
        lines = [f"# Wiki Search Results for '{query}'", ""]
        
        for result in results:
            lines.append(f"## [{result.page.title}]({result.page.url})")
            lines.append(f"**Relevance:** {result.relevance:.2f}")
            if result.matches:
                lines.append("**Matches:**")
                for match in result.matches:
                    lines.append(f"- ...{match.strip()}...")
            lines.append("")

        if not results:
            lines.append("No results found.")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error searching wiki for '{query}'", exc_info=True)
        return [TextContent(type="text", text=f"Error searching wiki: {e}")]


async def handle_list_wiki_pages(adapter: GitHubAdapter) -> list[TextContent]:
    """List all wiki pages."""
    try:
        pages = await adapter.list_wiki_pages()
        lines = ["# Wiki Pages", ""]
        
        for page in pages:
            lines.append(f"- [{page.title}]({page.url})")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error("Error listing wiki pages", exc_info=True)
        return [TextContent(type="text", text=f"Error listing wiki pages: {e}")]