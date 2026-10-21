"""GitHub-related tool handlers."""

import logging

from mcp.types import TextContent, Tool

from girafmcp.adapters import GitHubAdapter

logger = logging.getLogger(__name__)


def list_tools() -> list[Tool]:
    """Return tool definitions for GitHub tools."""
    return [
        Tool(
            name="list_repositories",
            description="List all GIRAF repositories with their descriptions and URLs",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_file",
            description="Get the content of a file from a GIRAF repository. Returns content with a permalink for citation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository name (e.g., 'foodplanner', 'wiki')",
                    },
                    "path": {
                        "type": "string",
                        "description": "File path within the repository",
                    },
                    "ref": {
                        "type": "string",
                        "description": "Git ref (branch, tag, or commit SHA). Optional.",
                    },
                },
                "required": ["repo", "path"],
            },
        ),
        Tool(
            name="search_code",
            description="Search for code across GIRAF repositories. Returns matching files with GitHub permalinks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Optional: limit search to a specific repository",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_permalink",
            description="Generate a GitHub permalink to a specific file and line range for citation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository name",
                    },
                    "path": {
                        "type": "string",
                        "description": "File path",
                    },
                    "line": {
                        "type": "integer",
                        "description": "Start line number (optional)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "End line number for range (optional)",
                    },
                },
                "required": ["repo", "path"],
            },
        ),
        Tool(
            name="search_wiki",
            description="Search the GIRAF wiki documentation. Fetches pages live from GitHub and performs keyword search. Returns matching pages with URLs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (keywords to find in wiki pages)",
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
            name="list_wiki_pages",
            description="List all pages in the GIRAF wiki. Returns page titles and URLs.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


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
        logger.exception("Error listing repositories")
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
        logger.exception(f"Error fetching file {repo}/{path}")
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
        logger.exception(f"Error searching code for '{query}'")
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
        logger.exception(f"Error searching wiki for '{query}'")
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
        logger.exception("Error listing wiki pages")
        return [TextContent(type="text", text=f"Error listing wiki pages: {e}")]