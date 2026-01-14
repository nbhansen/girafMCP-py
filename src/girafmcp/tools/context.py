"""Context, domain knowledge, and persona tool handlers."""

import logging
from mcp.types import TextContent, Tool
from girafmcp.adapters import FileAdapter

logger = logging.getLogger(__name__)


def list_tools() -> list[Tool]:
    """Return tool definitions for context tools."""
    return [
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
    ]


async def handle_get_project_context(adapter: FileAdapter) -> list[TextContent]:
    """Get the current project context."""
    try:
        context = adapter.get_context()
        lines = ["# Project Context", ""]
        
        for key, value in context.items():
            lines.append(f"## {key.replace('_', ' ').title()}")
            if isinstance(value, list):
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(str(value))
            lines.append("")

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
        lines = ["# Available Personas", ""]
        
        personas = data.get("personas", {{}})
        if not personas:
            return [TextContent(type="text", text="No personas found.")]

        for persona_id, details in personas.items():
            name = details.get("name", persona_id)
            description = details.get("description", "No description")
            lines.append(f"- **{name}** (`{persona_id}`): {description}")

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
        if not persona:
            return [TextContent(type="text", text=f"Persona '{persona_id}' not found.")]

        lines = [f"# Persona: {persona.get('name', persona_id)}", ""]
        
        for key, value in persona.items():
            if key == "name":
                continue
            lines.append(f"## {key.replace('_', ' ').title()}")
            if isinstance(value, list):
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(str(value))
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error getting persona {persona_id}", exc_info=True)
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
            return [TextContent(type="text", text=f"No domain knowledge found for '{query}'")]

        lines = [f"# Domain Knowledge Results for '{query}'", ""]
        
        for result in results:
            lines.append(f"## {result.title} - {result.section}")
            lines.append(f"**Relevance:** {result.relevance:.2f}")
            lines.append("")
            lines.append(result.content)
            lines.append("")
            lines.append("---")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error searching domain knowledge for '{query}'", exc_info=True)
        return [TextContent(type="text", text=f"Error searching domain knowledge: {e}")]


async def handle_list_domain_topics(adapter: FileAdapter) -> list[TextContent]:
    """List all domain knowledge topics."""
    try:
        files = adapter.list_domain_files()
        lines = ["# Domain Knowledge Topics", ""]
        
        for file_path in files:
            topic = file_path.stem.replace("-", " ").title()
            lines.append(f"- {topic} (`{file_path.name}`)")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error("Error listing domain topics", exc_info=True)
        return [TextContent(type="text", text=f"Error listing domain topics: {e}")]