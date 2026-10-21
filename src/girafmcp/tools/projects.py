"""GitHub Projects V2 tool handlers."""

import logging
from mcp.types import TextContent, Tool

from girafmcp.adapters.github_projects_adapter import GitHubProjectsAdapter
from girafmcp.core.types import ProjectItem

logger = logging.getLogger(__name__)


def list_tools() -> list[Tool]:
    """Return tool definitions for GitHub Projects V2 tools."""
    return [
        Tool(
            name="list_github_projects",
            description="List all GitHub Projects V2 in the aau-giraf organization. "
            "Returns project titles, numbers, item counts, and URLs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of projects to return (default: 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_github_project",
            description="Get details about a specific GitHub Project V2 by its number. "
            "The number is visible in the project URL.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_number": {
                        "type": "integer",
                        "description": "The project number (e.g., 1, 2, 3)",
                    },
                },
                "required": ["project_number"],
            },
        ),
        Tool(
            name="list_project_items",
            description="List items (issues, PRs, draft issues) in a GitHub Project V2. "
            "Returns item titles, types, status, assignees, and labels.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_number": {
                        "type": "integer",
                        "description": "The project number",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of items to return (default: 50)",
                        "default": 50,
                    },
                    "status_filter": {
                        "type": "string",
                        "description": "Filter by status value (e.g., 'Todo', 'In Progress', 'Done')",
                    },
                },
                "required": ["project_number"],
            },
        ),
        Tool(
            name="check_github_projects_access",
            description="Check if the configured GitHub token has the 'read:project' scope "
            "required for accessing GitHub Projects V2.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


async def handle_list_github_projects(
    adapter: GitHubProjectsAdapter,
    limit: int = 20,
) -> list[TextContent]:
    """Handle list_github_projects tool call."""
    try:
        projects = await adapter.list_org_projects(limit=limit)

        if not projects:
            return [
                TextContent(
                    type="text",
                    text="No projects found in the aau-giraf organization. "
                    "This could mean:\n"
                    "- No Projects V2 exist yet\n"
                    "- The token lacks 'read:project' scope (run: gh auth refresh -s read:project)",
                )
            ]

        lines = [f"# GitHub Projects V2 in aau-giraf ({len(projects)} projects)", ""]

        for p in projects:
            status = "Closed" if p.closed else "Open"
            visibility = "Public" if p.public else "Private"
            lines.append(f"## [{p.title}]({p.url}) (#{p.number})")
            lines.append(f"- **Status:** {status} | **Visibility:** {visibility}")
            lines.append(f"- **Items:** {p.items_count}")
            if p.description:
                lines.append(f"- **Description:** {p.description}")
            lines.append(f"- **Updated:** {p.updated_at}")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except ValueError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        logger.error("Error listing GitHub projects", exc_info=True)
        return [TextContent(type="text", text=f"Error listing projects: {e}")]


async def handle_get_github_project(
    adapter: GitHubProjectsAdapter,
    project_number: int,
) -> list[TextContent]:
    """Handle get_github_project tool call."""
    try:
        project = await adapter.get_project(project_number)

        if not project:
            return [
                TextContent(
                    type="text",
                    text=f"Project #{project_number} not found in aau-giraf organization.",
                )
            ]

        status = "Closed" if project.closed else "Open"
        visibility = "Public" if project.public else "Private"

        lines = [
            f"# {project.title} (#{project.number})",
            "",
            f"**URL:** {project.url}",
            f"**Status:** {status}",
            f"**Visibility:** {visibility}",
            f"**Total Items:** {project.items_count}",
            "",
        ]

        if project.description:
            lines.extend(["## Description", project.description, ""])

        lines.extend([
            "## Timeline",
            f"- **Created:** {project.created_at}",
            f"- **Updated:** {project.updated_at}",
        ])

        return [TextContent(type="text", text="\n".join(lines))]

    except ValueError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        logger.error(f"Error getting project #{project_number}", exc_info=True)
        return [TextContent(type="text", text=f"Error getting project: {e}")]


async def handle_list_project_items(
    adapter: GitHubProjectsAdapter,
    project_number: int,
    limit: int = 50,
    status_filter: str | None = None,
) -> list[TextContent]:
    """Handle list_project_items tool call."""
    try:
        items = await adapter.list_project_items(
            project_number=project_number,
            limit=limit,
            status_filter=status_filter,
        )

        if not items:
            filter_msg = f" with status '{status_filter}'" if status_filter else ""
            return [
                TextContent(
                    type="text",
                    text=f"No items found in project #{project_number}{filter_msg}.",
                )
            ]

        filter_text = f" (filtered by '{status_filter}')" if status_filter else ""
        lines = [
            f"# Items in Project #{project_number}{filter_text} ({len(items)} items)",
            "",
        ]

        # Group by status
        by_status: dict[str, list[ProjectItem]] = {}
        for item in items:
            status = item.status or "No Status"
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(item)

        for status, status_items in by_status.items():
            lines.append(f"## {status} ({len(status_items)})")
            lines.append("")

            for item in status_items:
                type_emoji = {
                    "ISSUE": "🔵",
                    "PULL_REQUEST": "🟢",
                    "DRAFT_ISSUE": "⚪",
                }.get(item.type, "⚫")

                if item.url:
                    lines.append(f"- {type_emoji} [{item.title}]({item.url})")
                else:
                    lines.append(f"- {type_emoji} {item.title} *(draft)*")

                details = []
                if item.assignees:
                    details.append(f"Assignees: {', '.join(item.assignees)}")
                if item.labels:
                    details.append(f"Labels: {', '.join(item.labels)}")
                if item.repository:
                    details.append(f"Repo: {item.repository}")

                if details:
                    lines.append(f"  - {' | '.join(details)}")

            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except ValueError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        logger.error(f"Error listing items for project #{project_number}", exc_info=True)
        return [TextContent(type="text", text=f"Error listing project items: {e}")]


async def handle_check_github_projects_access(
    adapter: GitHubProjectsAdapter,
) -> list[TextContent]:
    """Handle check_github_projects_access tool call."""
    try:
        result = await adapter.check_token_scope()

        lines = ["# GitHub Projects V2 Access Check", ""]

        if result.has_project_scope:
            lines.append("**Status:** ✅ Access available")
        else:
            lines.append("**Status:** ❌ Access not available")

        lines.append("")
        lines.append(f"**Message:** {result.message}")

        if result.scopes:
            lines.extend(["", "## Current Token Scopes", ""])
            for scope in sorted(result.scopes):
                check = "✓" if scope == "read:project" else " "
                lines.append(f"- [{check}] `{scope}`")

        if not result.has_project_scope:
            lines.extend([
                "",
                "## How to Add Scope",
                "",
                "Run the following command to add the required scope:",
                "",
                "```bash",
                "gh auth refresh -s read:project",
                "```",
                "",
                "Then restart the MCP server.",
            ])

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error("Error checking GitHub projects access", exc_info=True)
        return [TextContent(type="text", text=f"Error checking access: {e}")]
