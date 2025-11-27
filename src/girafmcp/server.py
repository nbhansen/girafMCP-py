"""GIRAF MCP Server - Knowledge assistant for the GIRAF project.

This MCP server provides tools for searching documentation, code,
and domain knowledge to help students working on the GIRAF project.
"""

import asyncio
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env file from project root
_project_root = Path(__file__).parent.parent.parent
load_dotenv(_project_root / ".env")

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from girafmcp.adapters import ChromaAdapter, FileAdapter, GitHubAdapter

# Create server instance
server = Server("giraf-mcp")

# Initialize adapters (lazy loading)
_github_adapter: GitHubAdapter | None = None
_chroma_adapter: ChromaAdapter | None = None
_file_adapter: FileAdapter | None = None


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


def get_file_adapter() -> FileAdapter:
    """Get or create file adapter."""
    global _file_adapter
    if _file_adapter is None:
        data_dir = os.environ.get("GIRAF_DATA_DIR")
        _file_adapter = FileAdapter(data_dir=data_dir)
    return _file_adapter


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
        Tool(
            name="get_project_context",
            description="Get the current project context including semester focus, priorities, known issues, and recent decisions.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="list_personas",
            description="List available user personas. Personas help tailor responses to different user backgrounds (CS student, pedagogy student, supervisor, etc.)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_persona",
            description="Get details about a specific persona including communication style and focus areas.",
            inputSchema={
                "type": "object",
                "properties": {
                    "persona_id": {
                        "type": "string",
                        "description": "Persona ID (e.g., 'cs_student', 'pedagogy_student', 'supervisor', 'new_student')",
                    },
                },
                "required": ["persona_id"],
            },
        ),
        Tool(
            name="search_domain_knowledge",
            description="Search domain knowledge about autism, visual schedules, sensory considerations, and other background information relevant to GIRAF users.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (keywords about autism, visual schedules, accessibility, etc.)",
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
            name="list_domain_topics",
            description="List all available domain knowledge topics (autism basics, visual schedules, sensory considerations, etc.)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
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

    elif name == "get_project_context":
        return await handle_get_project_context()

    elif name == "list_personas":
        return await handle_list_personas()

    elif name == "get_persona":
        return await handle_get_persona(persona_id=arguments["persona_id"])

    elif name == "search_domain_knowledge":
        return await handle_search_domain_knowledge(
            query=arguments["query"],
            limit=arguments.get("limit", 5),
        )

    elif name == "list_domain_topics":
        return await handle_list_domain_topics()

    elif name == "search_wiki":
        return await handle_search_wiki(
            query=arguments["query"],
            limit=arguments.get("limit", 5),
        )

    elif name == "list_wiki_pages":
        return await handle_list_wiki_pages()

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


async def handle_get_project_context() -> list[TextContent]:
    """Get the current project context."""
    adapter = get_file_adapter()

    try:
        context = adapter.get_context()

        lines = ["# GIRAF Project Context\n"]

        # Semester and focus
        lines.append(f"**Semester:** {context.get('semester', 'Not specified')}")
        lines.append(f"**Focus:** {context.get('focus', 'Not specified')}")
        lines.append("")

        # Current priorities
        priorities = context.get("current_priorities", [])
        if priorities:
            lines.append("## Current Priorities")
            for p in priorities:
                lines.append(f"- {p}")
            lines.append("")

        # Known gotchas
        gotchas = context.get("known_gotchas", [])
        if gotchas:
            lines.append("## Known Issues & Workarounds")
            for g in gotchas:
                lines.append(f"**Issue:** {g.get('issue', 'Unknown')}")
                lines.append(f"**Workaround:** {g.get('workaround', 'None provided')}")
                lines.append("")

        # Recent decisions
        decisions = context.get("recent_decisions", [])
        if decisions:
            lines.append("## Recent Decisions")
            for d in decisions:
                lines.append(f"- **{d.get('date', 'Unknown date')}:** {d.get('decision', '')}")
                if d.get("context"):
                    lines.append(f"  - Context: {d['context']}")
            lines.append("")

        # Important links
        links = context.get("important_links", [])
        if links:
            lines.append("## Important Links")
            for link in links:
                lines.append(f"- [{link.get('name', 'Link')}]({link.get('url', '#')}): {link.get('description', '')}")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except FileNotFoundError:
        return [TextContent(type="text", text="Project context file not found. Please create data/context.yaml")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error reading project context: {e}")]


async def handle_list_personas() -> list[TextContent]:
    """List all available personas."""
    adapter = get_file_adapter()

    try:
        data = adapter.get_personas()
        personas = data.get("personas", {})
        default = data.get("default_persona", "new_student")

        lines = ["# Available Personas\n"]
        lines.append(f"*Default persona: {default}*\n")

        for persona_id, persona in personas.items():
            name = persona.get("name", persona_id)
            desc = persona.get("description", "No description")
            lines.append(f"## {name}")
            lines.append(f"**ID:** `{persona_id}`")
            lines.append(f"**Description:** {desc}")
            lines.append("")

        lines.append("---")
        lines.append("Use `get_persona` with a persona ID to get full details.")

        return [TextContent(type="text", text="\n".join(lines))]

    except FileNotFoundError:
        return [TextContent(type="text", text="Personas file not found. Please create data/personas.yaml")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error reading personas: {e}")]


async def handle_get_persona(persona_id: str) -> list[TextContent]:
    """Get details about a specific persona."""
    adapter = get_file_adapter()

    try:
        persona = adapter.get_persona(persona_id)

        if persona is None:
            return [TextContent(type="text", text=f"Persona not found: {persona_id}")]

        lines = [f"# {persona.get('name', persona_id)}\n"]
        lines.append(f"**Description:** {persona.get('description', 'No description')}")
        lines.append("")

        # Style
        style = persona.get("style", {})
        if style:
            lines.append("## Communication Style")
            lines.append(f"- **Tone:** {style.get('tone', 'Not specified')}")
            lines.append(f"- **Detail level:** {style.get('detail_level', 'Not specified')}")
            lines.append(f"- **Vocabulary:** {style.get('vocabulary', 'Not specified')}")
            lines.append("")

        # Focus areas
        focus = persona.get("focus_areas", [])
        if focus:
            lines.append("## Focus Areas")
            for area in focus:
                lines.append(f"- {area}")
            lines.append("")

        # Example responses
        examples = persona.get("example_responses", [])
        if examples:
            lines.append("## Example Responses")
            for ex in examples:
                lines.append(f"**Q:** {ex.get('question', '')}")
                lines.append(f"**A:** {ex.get('answer', '')}")
                lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error getting persona: {e}")]


async def handle_search_domain_knowledge(
    query: str, limit: int = 5
) -> list[TextContent]:
    """Search domain knowledge files."""
    adapter = get_file_adapter()

    try:
        results = adapter.search_domain(query, limit)

        if not results:
            return [
                TextContent(
                    type="text",
                    text=f"No domain knowledge found matching: {query}\n\n"
                    "Try different keywords like: autism, visual schedules, sensory, pictograms, accessibility",
                )
            ]

        lines = [f"# Domain Knowledge: {query}\n"]
        for result in results:
            lines.append(f"## {result.title} - {result.section}")
            lines.append(f"**Source:** `{result.filename}`")
            lines.append(f"**Relevance:** {result.relevance:.0%}")
            lines.append("")
            lines.append(result.content)
            lines.append("")
            lines.append("---")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error searching domain knowledge: {e}")]


async def handle_list_domain_topics() -> list[TextContent]:
    """List all domain knowledge topics."""
    adapter = get_file_adapter()

    try:
        files = adapter.list_domain_files()

        if not files:
            return [
                TextContent(
                    type="text",
                    text="No domain knowledge files found.\n\n"
                    "Domain knowledge can be added in the `data/domain/` directory.",
                )
            ]

        lines = ["# Domain Knowledge Topics\n"]
        lines.append("The following topics are available for searching:\n")

        for file_path in sorted(files):
            content = file_path.read_text(encoding="utf-8")

            # Extract title
            import re

            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            title = title_match.group(1) if title_match else file_path.stem

            # Count sections
            sections = len(re.findall(r"^##\s+", content, re.MULTILINE))

            lines.append(f"## {title}")
            lines.append(f"**File:** `{file_path.name}`")
            lines.append(f"**Sections:** {sections}")
            lines.append("")

        lines.append("---")
        lines.append(
            "Use `search_domain_knowledge` to search for specific topics within these files."
        )

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error listing domain topics: {e}")]


async def handle_search_wiki(query: str, limit: int = 5) -> list[TextContent]:
    """Search wiki documentation."""
    adapter = get_github_adapter()

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


async def handle_list_wiki_pages() -> list[TextContent]:
    """List all wiki pages."""
    adapter = get_github_adapter()

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
        grouped: dict[str, list] = {}
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
