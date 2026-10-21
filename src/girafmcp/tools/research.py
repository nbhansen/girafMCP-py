"""Research feature tool handlers.

Tools for session management, guardrails, and research data export.
"""

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool

from girafmcp.adapters.research_data_adapter import ResearchDataAdapter
from girafmcp.core.paths import DATA_DIR
from girafmcp.core.services.guardrails_service import (
    GuardrailMode,
    GuardrailsService,
)
from girafmcp.core.session import SessionState

logger = logging.getLogger(__name__)


def list_tools() -> list[Tool]:
    """Return tool definitions for research tools."""
    return [
        Tool(
            name="set_session_metadata",
            description="Set research metadata for this session (team, role, discipline). Called once at session start for logging purposes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {
                        "type": "string",
                        "description": "Anonymized team identifier (e.g., 'team_a', 'team_b')",
                    },
                    "role": {
                        "type": "string",
                        "enum": ["po", "sm", "dev"],
                        "description": "Student's role in the project",
                    },
                    "discipline": {
                        "type": "string",
                        "enum": ["cs", "id", "business", "health"],
                        "description": "Student's discipline",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="request_more_detail",
            description="Request more detailed guidance on the previous query. Advances through hint -> guidance -> example -> solution tiers.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="configure_guardrails",
            description="Configure guardrail settings for a team. Supervisor only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {
                        "type": "string",
                        "description": "Team to configure",
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Enable or disable guardrails for team",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["off", "prompt", "tiered", "cooldown"],
                        "description": "Guardrail mode",
                    },
                },
                "required": ["team_id"],
            },
        ),
        Tool(
            name="get_guardrails_status",
            description="Get current guardrails status for the session.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_feature_status",
            description="Get status of all research features (enabled/disabled).",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        # Supervisor-only export tool (was missing from server.py tool list, adding here)
        Tool(
            name="export_query_logs",
            description="Export query logs to CSV for research analysis. Supervisor only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Path for CSV output (optional)",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Filter by start date (ISO 8601)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Filter by end date (ISO 8601)",
                    },
                    "team_id": {
                        "type": "string",
                        "description": "Filter by team",
                    },
                },
                "required": [],
            },
        ),
    ]


# ============================================================================
# Session Metadata Tools
# ============================================================================


async def handle_set_session_metadata(
    session: SessionState,
    team_id: str | None = None,
    role: str | None = None,
    discipline: str | None = None,
) -> list[TextContent]:
    """Set research metadata for the current session.

    Args:
        session: Current session state
        team_id: Anonymized team identifier
        role: Student's role (po, sm, dev)
        discipline: Student's discipline (cs, id, business, health)

    Returns:
        Confirmation message
    """
    session.set_metadata(team_id=team_id, role=role, discipline=discipline)

    parts = []
    if team_id:
        parts.append(f"team={team_id}")
    if role:
        parts.append(f"role={role}")
    if discipline:
        parts.append(f"discipline={discipline}")

    metadata_str = ", ".join(parts) if parts else "no changes"

    return [
        TextContent(
            type="text",
            text=f"Session metadata updated: {metadata_str}\n\n"
            f"Session ID: `{session.id}`",
        )
    ]


# ============================================================================
# Guardrails Tools
# ============================================================================


async def handle_request_more_detail(
    session: SessionState,
    guardrails_service: GuardrailsService,
    dispatch_fn: Callable[[str, dict[str, Any]], Awaitable[list[TextContent]]],
) -> list[TextContent]:
    """Request more detailed guidance on the previous query.

    Advances through hint -> guidance -> example -> solution tiers.

    Args:
        session: Current session state
        guardrails_service: The guardrails service
        dispatch_fn: Function to dispatch tool calls

    Returns:
        More detailed response for the previous query
    """
    if not session.last_tool or session.last_arguments is None:
        return [
            TextContent(
                type="text",
                text="No previous query to elaborate on. Please ask a question first.",
            )
        ]

    # Advance tier
    max_tier = guardrails_service.config.max_tier
    new_tier = session.advance_tier(max_tier)
    tier_config = guardrails_service.config.get_tier_config(new_tier)

    # Re-run the previous query with new tier
    # The middleware will use the updated session.guardrail_tier
    try:
        result = await dispatch_fn(session.last_tool, session.last_arguments)

        # Add tier indicator if not at max tier
        if new_tier < max_tier and tier_config and tier_config.prompt_suffix:
            result_text = result[0].text if result else ""
            modified_text = result_text + "\n" + tier_config.prompt_suffix
            return [TextContent(type="text", text=modified_text)]

        return result

    except Exception as e:
        logger.exception("Error re-running previous query")
        return [
            TextContent(
                type="text",
                text=f"Error getting more detail: {e}",
            )
        ]


async def handle_configure_guardrails(
    guardrails_service: GuardrailsService,
    team_id: str,
    enabled: bool | None = None,
    mode: str | None = None,
) -> list[TextContent]:
    """Configure guardrail settings for a team.

    Supervisor-only tool for adjusting A/B testing conditions.

    Args:
        guardrails_service: The guardrails service
        team_id: Team to configure
        enabled: Whether guardrails are enabled for this team
        mode: Guardrail mode (off, prompt, tiered, cooldown)

    Returns:
        Confirmation of configuration change
    """
    # Validate mode if provided
    if mode:
        try:
            GuardrailMode(mode)
        except ValueError:
            valid_modes = ", ".join(m.value for m in GuardrailMode)
            return [
                TextContent(
                    type="text",
                    text=f"Invalid mode '{mode}'. Valid modes: {valid_modes}",
                )
            ]

    # Apply configuration
    guardrails_service.config.set_team_override(
        team_id=team_id,
        enabled=enabled,
        mode=mode,
    )

    # Get effective settings
    effective_mode = guardrails_service.config.get_team_mode(team_id)
    is_enabled = guardrails_service.config.is_team_enabled(team_id)

    return [
        TextContent(
            type="text",
            text=f"# Guardrails Configuration Updated\n\n"
            f"**Team:** {team_id}\n"
            f"**Enabled:** {is_enabled}\n"
            f"**Mode:** {effective_mode.value}\n\n"
            f"*Note: Changes are in-memory only. Use `save` parameter to persist to disk.*",
        )
    ]


async def handle_get_guardrails_status(
    guardrails_service: GuardrailsService,
    session: SessionState,
) -> list[TextContent]:
    """Get current guardrails status for the session.

    Args:
        guardrails_service: The guardrails service
        session: Current session state

    Returns:
        Current guardrails status
    """
    config = guardrails_service.config
    team_id = session.team_id

    mode = config.get_team_mode(team_id)
    enabled = config.is_team_enabled(team_id)

    lines = [
        "# Guardrails Status",
        "",
        f"**Session ID:** `{session.id}`",
        f"**Team:** {team_id or '(not set)'}",
        f"**Enabled:** {enabled}",
        f"**Mode:** {mode.value}",
        "",
        "## Session State",
        f"- Current Tier: {session.guardrail_tier}",
        f"- Prompted This Query: {session.guardrail_prompted}",
        f"- Cooldown Until: {session.cooldown_until or 'N/A'}",
        f"- Last Tool: {session.last_tool or 'N/A'}",
    ]

    return [TextContent(type="text", text="\n".join(lines))]


# ============================================================================
# Research Data Export Tools
# ============================================================================


async def handle_export_query_logs(
    adapter: ResearchDataAdapter,
    output_path: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    team_id: str | None = None,
) -> list[TextContent]:
    """Export query logs to CSV for research analysis.

    Supervisor-only tool for extracting research data.

    Args:
        adapter: Research data adapter
        output_path: Path for CSV output (default: data/exports/query_logs.csv)
        start_date: Filter by start date (ISO 8601)
        end_date: Filter by end date (ISO 8601)
        team_id: Filter by team

    Returns:
        Export summary with row count and file path
    """
    from datetime import datetime

    # Parse dates if provided
    start = None
    end = None
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
        except ValueError:
            return [
                TextContent(
                    type="text",
                    text=f"Invalid start_date format: {start_date}. Use ISO 8601 (e.g., 2025-02-01)",
                )
            ]

    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
        except ValueError:
            return [
                TextContent(
                    type="text",
                    text=f"Invalid end_date format: {end_date}. Use ISO 8601 (e.g., 2025-02-28)",
                )
            ]

    # Determine output path
    if output_path:
        path = Path(output_path)
    else:
        # Default to data/exports/
        exports_dir = DATA_DIR / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = exports_dir / f"query_logs_{timestamp}.csv"

    try:
        row_count = await adapter.export_csv(
            output_path=path,
            start=start,
            end=end,
            team_id=team_id,
        )

        return [
            TextContent(
                type="text",
                text=f"# Export Complete\n\n"
                f"**File:** `{path}`\n"
                f"**Rows:** {row_count}\n"
                f"**Filters:**\n"
                f"- Start: {start_date or 'none'}\n"
                f"- End: {end_date or 'none'}\n"
                f"- Team: {team_id or 'all'}",
            )
        ]

    except Exception as e:
        logger.exception("Error exporting query logs")
        return [
            TextContent(
                type="text",
                text=f"Error exporting query logs: {e}",
            )
        ]


async def handle_get_feature_status() -> list[TextContent]:
    """Get status of all research features.

    Returns:
        Feature toggle status for all research features
    """
    from girafmcp.core.features import FeatureRegistry

    states = FeatureRegistry.get_all_states()

    lines = ["# Research Feature Status", ""]
    for state in states:
        status = "enabled" if state.enabled else "disabled"
        default = "default" if state.enabled == state.default else "overridden"
        lines.append(
            f"- **{state.feature.name}**: {status} ({default})\n"
            f"  - Env var: `{state.env_var}`"
        )
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]
