"""Context, domain knowledge, and persona tool handlers."""

import re
from mcp.types import TextContent
from girafmcp.adapters import FileAdapter


async def handle_get_project_context(adapter: FileAdapter) -> list[TextContent]:
    """Get the current project context."""
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


async def handle_list_personas(adapter: FileAdapter) -> list[TextContent]:
    """List all available personas."""
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


async def handle_get_persona(adapter: FileAdapter, persona_id: str) -> list[TextContent]:
    """Get details about a specific persona."""
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
    adapter: FileAdapter,
    query: str,
    limit: int = 5
) -> list[TextContent]:
    """Search domain knowledge files."""
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


async def handle_list_domain_topics(adapter: FileAdapter) -> list[TextContent]:
    """List all domain knowledge topics."""
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
