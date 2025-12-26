"""GitHub-related tool handlers."""

from mcp.types import TextContent
from girafmcp.adapters import GitHubAdapter
from girafmcp.core import WikiPage


async def handle_list_repositories(adapter: GitHubAdapter) -> list[TextContent]:
    """List all GIRAF repositories."""
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
    adapter: GitHubAdapter, repo: str, path: str, ref: str | None = None
) -> list[TextContent]:
    """Get file content from a repository."""
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
    adapter: GitHubAdapter, query: str, repo: str | None = None
) -> list[TextContent]:
    """Search for code across repositories."""
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


async def handle_get_permalink(
    adapter: GitHubAdapter,
    repo: str,
    path: str,
    line: int | None = None,
    end_line: int | None = None,
) -> list[TextContent]:
    """Generate a permalink for citation."""
    link = adapter.get_permalink(repo, path, line, end_line)

    if line is not None:
        if end_line is not None:
            location = f"lines {line}-{end_line}"
        else:
            location = f"line {line}"
        return [TextContent(type="text", text=f"Permalink to {repo}/{path} ({location}):\n{link}")]
    else:
        return [TextContent(type="text", text=f"Permalink to {repo}/{path}:\n{link}")]


async def handle_search_wiki(
    adapter: GitHubAdapter, query: str, limit: int = 5
) -> list[TextContent]:
    """Search wiki documentation."""
    try:
        results = await adapter.search_wiki(query, limit=limit)

        if not results:
            return [
                TextContent(
                    type="text",
                    text=f"No wiki pages found matching: {query}\n\n"
                    "Try different keywords or use `list_wiki_pages` to see all available pages.",
                )
            ]

        lines = [f"# Wiki Search Results: {query}\n"]
        for result in results:
            lines.append(f"## {result.page.title}")
            lines.append(f"**URL:** {result.page.url}")
            lines.append(f"**GitHub:** {result.page.github_url}")
            lines.append(f"**Relevance:** {result.relevance:.0%}")
            lines.append("")
            if result.matches:
                lines.append("**Matching content:**")
                for match in result.matches[:3]:
                    lines.append(f"> {match}")
                lines.append("")
            lines.append("---")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error searching wiki: {e}")]


async def handle_list_wiki_pages(adapter: GitHubAdapter) -> list[TextContent]:
    """List all wiki pages."""
    try:
        pages = await adapter.list_wiki_pages()

        if not pages:
            return [
                TextContent(
                    type="text",
                    text="No wiki pages found.",
                )
            ]

        # Group by top-level folder
        grouped: dict[str, list[WikiPage]] = {}
        for page in pages:
            parts = page.path.replace("docs/", "").split("/")
            folder = parts[0] if len(parts) > 1 else "Root"
            if folder not in grouped:
                grouped[folder] = []
            grouped[folder].append(page)

        lines = [f"# GIRAF Wiki Pages ({len(pages)} total)\n"]

        for folder in sorted(grouped.keys()):
            lines.append(f"## {folder.replace('_', ' ')}")
            for page in grouped[folder]:
                lines.append(f"- [{page.title}]({page.url})")
            lines.append("")

        lines.append("---")
        lines.append("Use `search_wiki` to search for specific content.")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error listing wiki pages: {e}")]
