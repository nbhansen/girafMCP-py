"""Resilience testing tool handlers.

Tools for students to report detected errors and for supervisors
to configure resilience testing scenarios.
"""

import logging

from mcp.types import TextContent, Tool

from girafmcp.core.services.resilience_service import (
    ResilienceService,
    ResilienceMode,
)
from girafmcp.core.session import SessionState

logger = logging.getLogger(__name__)


def list_tools() -> list[Tool]:
    """Return tool definitions for resilience tools."""
    return [
        Tool(
            name="report_error_found",
            description="Report a suspected error in AI-generated code or guidance. Use when you detect an issue that needs correction.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "The tool where the error was found",
                    },
                    "error_description": {
                        "type": "string",
                        "description": "Description of the suspected error",
                    },
                    "proposed_fix": {
                        "type": "string",
                        "description": "Your proposed correction (optional)",
                    },
                },
                "required": ["tool_name", "error_description"],
            },
        ),
        Tool(
            name="configure_resilience_test",
            description="Configure resilience testing for a team. Supervisor only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {
                        "type": "string",
                        "description": "Team to configure",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["normal", "degraded", "unavailable", "delayed"],
                        "description": "Resilience test mode",
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Enable or disable resilience testing",
                    },
                },
                "required": ["team_id"],
            },
        ),
        Tool(
            name="get_resilience_status",
            description="Get current resilience testing status for the session.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_resilience_metrics",
            description="Get error detection metrics for research analysis. Supervisor only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Optional: filter by session ID",
                    },
                },
                "required": [],
            },
        ),
    ]


# ============================================================================
# Student Tools
# ============================================================================


async def handle_report_error_found(
    service: ResilienceService,
    session: SessionState,
    tool_name: str,
    error_description: str,
    proposed_fix: str | None = None,
) -> list[TextContent]:
    """Report a suspected error in AI-generated code or guidance.

    Students use this tool when they detect an issue in AI output.
    This is tracked for research analysis of error detection skills.

    Args:
        service: Resilience service
        session: Current session state
        tool_name: The tool where the error was found
        error_description: Description of the suspected error
        proposed_fix: Optional proposed correction

    Returns:
        Acknowledgment of the report
    """
    report = service.record_error_report(
        session_id=session.id,
        tool_name=tool_name,
        error_description=error_description,
        proposed_fix=proposed_fix,
    )

    # Provide feedback without revealing if it was an injected error
    lines = [
        "# Error Report Received",
        "",
        f"**Report ID:** `{report.id[:8]}`",
        f"**Tool:** {tool_name}",
        "",
        "## Your Report",
        f"**Issue:** {error_description}",
    ]

    if proposed_fix:
        lines.append(f"**Proposed Fix:** {proposed_fix}")

    lines.extend([
        "",
        "---",
        "*Thank you for verifying the AI output. Your report has been recorded.*",
        "",
        "**Good practice!** Always verify AI-generated code through:",
        "- Running tests",
        "- Code review with teammates",
        "- Checking against documentation",
        "- Testing edge cases",
    ])

    return [TextContent(type="text", text="\n".join(lines))]


# ============================================================================
# Supervisor Tools
# ============================================================================


async def handle_configure_resilience_test(
    service: ResilienceService,
    team_id: str,
    mode: str | None = None,
    enabled: bool | None = None,
) -> list[TextContent]:
    """Configure resilience testing for a team.

    Supervisor-only tool for setting up A/B testing conditions.

    Args:
        service: Resilience service
        team_id: Team to configure
        mode: Mode to set (normal, degraded, unavailable, delayed)
        enabled: Whether to enable resilience testing for this team

    Returns:
        Confirmation of configuration
    """
    # Validate mode if provided
    if mode:
        try:
            ResilienceMode(mode)
        except ValueError:
            valid_modes = ", ".join(m.value for m in ResilienceMode)
            return [
                TextContent(
                    type="text",
                    text=f"Invalid mode '{mode}'. Valid modes: {valid_modes}",
                )
            ]

    # Apply configuration
    service.config.set_team_override(
        team_id=team_id,
        mode=mode,
        enabled=enabled,
    )

    # Get effective settings
    effective_mode = service.get_mode(team_id)

    lines = [
        "# Resilience Test Configuration Updated",
        "",
        f"**Team:** {team_id}",
        f"**Mode:** {effective_mode.value}",
        "",
    ]

    # Add mode-specific notes
    if effective_mode == ResilienceMode.DEGRADED:
        rate = service.config.error_injection_rate * 100
        lines.append(f"*Error injection rate: {rate:.0f}%*")
    elif effective_mode == ResilienceMode.UNAVAILABLE:
        allowed = service.config.allowed_tools_when_unavailable
        lines.append(f"*Allowed tools: {', '.join(allowed)}*")
    elif effective_mode == ResilienceMode.DELAYED:
        delay = service.config.delay_seconds
        lines.append(f"*Response delay: {delay} seconds*")

    lines.extend([
        "",
        "---",
        "*Note: Changes are in-memory only and reset when server restarts.*",
    ])

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_get_resilience_status(
    service: ResilienceService,
    session: SessionState,
) -> list[TextContent]:
    """Get current resilience testing status.

    Args:
        service: Resilience service
        session: Current session state

    Returns:
        Current resilience status
    """
    team_id = session.team_id
    mode = service.get_mode(team_id)
    config = service.config

    lines = [
        "# Resilience Testing Status",
        "",
        f"**Session ID:** `{session.id}`",
        f"**Team:** {team_id or '(not set)'}",
        f"**Current Mode:** {mode.value}",
        f"**Global Enabled:** {config.enabled}",
        "",
    ]

    # Mode-specific info
    if mode == ResilienceMode.DEGRADED:
        lines.extend([
            "## Degraded Mode Settings",
            f"- Error injection rate: {config.error_injection_rate * 100:.0f}%",
            f"- Error types configured: {len(config.error_types)}",
        ])
    elif mode == ResilienceMode.UNAVAILABLE:
        lines.extend([
            "## Unavailable Mode Settings",
            f"- Allowed tools: {len(config.allowed_tools_when_unavailable)}",
        ])
    elif mode == ResilienceMode.DELAYED:
        lines.extend([
            "## Delayed Mode Settings",
            f"- Delay: {config.delay_seconds} seconds",
        ])

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_get_resilience_metrics(
    service: ResilienceService,
    session_id: str | None = None,
) -> list[TextContent]:
    """Get detection metrics for research analysis.

    Supervisor-only tool.

    Args:
        service: Resilience service
        session_id: Optional filter by session

    Returns:
        Detection metrics summary
    """
    metrics = service.get_detection_metrics(session_id)

    lines = [
        "# Resilience Testing Metrics",
        "",
    ]

    if session_id:
        lines.append(f"*Filtered by session: `{session_id[:8]}`*")
        lines.append("")

    lines.extend([
        "## Error Detection Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Injected | {metrics['total_injected']} |",
        f"| Detected | {metrics['detected']} |",
        f"| Detection Rate | {metrics['detection_rate']:.1%} |",
        f"| True Positives | {metrics['true_positives']} |",
        f"| False Positives | {metrics['false_positives']} |",
    ])

    if metrics.get('avg_detection_time_seconds') is not None:
        lines.append(f"| Avg Detection Time | {metrics['avg_detection_time_seconds']:.1f}s |")

    # By difficulty
    by_diff = metrics.get('by_difficulty', {})
    if any(d['injected'] > 0 for d in by_diff.values()):
        lines.extend([
            "",
            "## By Difficulty",
            "",
            "| Difficulty | Injected | Detected | Rate |",
            "|------------|----------|----------|------|",
        ])
        for diff, data in by_diff.items():
            if data['injected'] > 0:
                rate = data['detected'] / data['injected'] if data['injected'] else 0
                lines.append(f"| {diff} | {data['injected']} | {data['detected']} | {rate:.1%} |")

    # By error type
    by_type = metrics.get('by_type', {})
    if any(t['injected'] > 0 for t in by_type.values()):
        lines.extend([
            "",
            "## By Error Type",
            "",
            "| Type | Injected | Detected | Rate |",
            "|------|----------|----------|------|",
        ])
        for etype, data in by_type.items():
            if data['injected'] > 0:
                rate = data['detected'] / data['injected'] if data['injected'] else 0
                lines.append(f"| {etype} | {data['injected']} | {data['detected']} | {rate:.1%} |")

    return [TextContent(type="text", text="\n".join(lines))]
