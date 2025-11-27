"""GIRAF MCP Server - Knowledge assistant for the GIRAF project.

This MCP server provides tools for searching documentation, code,
and domain knowledge to help students working on the GIRAF project.
"""

import asyncio
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from girafmcp.adapters import ChromaAdapter, GitHubAdapter

# Create server instance
server = Server("giraf-mcp")

# Initialize adapters (lazy loading)
_github_adapter: GitHubAdapter | None = None
_chroma_adapter: ChromaAdapter | None = None


def get_github_adapter() -> GitHubAdapter:
    """Get or create GitHub adapter."""
    global _github_adapter
    if _github_adapter is None:
        _github_adapter = GitHubAdapter(
            org="aau-giraf",
            token=os.environ.get("GITHUB_TOKEN"),
        )
    return _github_adapter


def get_chroma_adapter() -> ChromaAdapter:
    """Get or create ChromaDB adapter."""
    global _chroma_adapter
    if _chroma_adapter is None:
        persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_data")
        _chroma_adapter = ChromaAdapter(persist_directory=persist_dir)
    return _chroma_adapter


# === Tool Definitions ===


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
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
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    if name == "list_repositories":
        return await handle_list_repositories()

    elif name == "get_file":
        return await handle_get_file(
            repo=arguments["repo"],
            path=arguments["path"],
            ref=arguments.get("ref"),
        )

    elif name == "search_code":
        return await handle_search_code(
            query=arguments["query"],
            repo=arguments.get("repo"),
        )

    elif name == "search_documentation":
        return await handle_search_documentation(
            query=arguments["query"],
            limit=arguments.get("limit", 5),
        )

    elif name == "get_permalink":
        return await handle_get_permalink(
            repo=arguments["repo"],
            path=arguments["path"],
            line=arguments.get("line"),
            end_line=arguments.get("end_line"),
        )

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# === Tool Handlers ===


async def handle_list_repositories() -> list[TextContent]:
    """List all GIRAF repositories."""
    adapter = get_github_adapter()

    try:
        repos = await adapter.list_repos()

        lines = ["# GIRAF Repositories\n"]
        for repo in repos:
            lang = f" ({repo.language})" if repo.language else ""
            desc = repo.description or "No description"
            lines.append(f"## {repo.name}{lang}")
            lines.append(f"{desc}")
            lines.append(f"- URL: {repo.url}")
            lines.append(f"- Default branch: {repo.default_branch}")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error listing repositories: {e}")]


async def handle_get_file(
    repo: str, path: str, ref: str | None = None
) -> list[TextContent]:
    """Get file content from a repository."""
    adapter = get_github_adapter()

    try:
        file = await adapter.get_file(repo, path, ref)

        result = f"""# {repo}/{path}

**Permalink:** {file.url}

```
{file.content}
```
"""
        return [TextContent(type="text", text=result)]

    except FileNotFoundError:
        return [TextContent(type="text", text=f"File not found: {repo}/{path}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error fetching file: {e}")]


async def handle_search_code(
    query: str, repo: str | None = None
) -> list[TextContent]:
    """Search for code across repositories."""
    adapter = get_github_adapter()

    try:
        results = await adapter.search_code(query, repo)

        if not results:
            return [TextContent(type="text", text=f"No code found matching: {query}")]

        lines = [f"# Code Search Results for: {query}\n"]
        for result in results:
            lines.append(f"## {result.repo}/{result.path}")
            lines.append(f"- URL: {result.url}")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error searching code: {e}")]


async def handle_search_documentation(
    query: str, limit: int = 5
) -> list[TextContent]:
    """Search documentation using semantic search."""
    adapter = get_chroma_adapter()

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


async def handle_get_permalink(
    repo: str,
    path: str,
    line: int | None = None,
    end_line: int | None = None,
) -> list[TextContent]:
    """Generate a permalink for citation."""
    adapter = get_github_adapter()

    link = adapter.get_permalink(repo, path, line, end_line)

    if line is not None:
        if end_line is not None:
            location = f"lines {line}-{end_line}"
        else:
            location = f"line {line}"
        return [TextContent(type="text", text=f"Permalink to {repo}/{path} ({location}):\n{link}")]
    else:
        return [TextContent(type="text", text=f"Permalink to {repo}/{path}:\n{link}")]


# === Entry Point ===


async def run_server():
    """Run the MCP server (async)."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """Entry point for the MCP server."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
