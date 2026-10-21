"""Knowledge capture tool handlers.

Tools for capturing architectural decisions, retrospective learnings,
and generating handover packages.
"""

import logging
import uuid
from datetime import UTC, datetime

from mcp.types import TextContent, Tool

from girafmcp.adapters.research_data_adapter import ResearchDataAdapter
from girafmcp.core.session import SessionState
from girafmcp.core.types import (
    ArchitecturalDecision,
    DecisionStatus,
    FollowUpStatus,
    HandoverPackage,
    LearningCategory,
    RetrospectiveLearning,
)

logger = logging.getLogger(__name__)


def list_tools() -> list[Tool]:
    """Return tool definitions for knowledge capture tools."""
    return [
        Tool(
            name="capture_decision",
            description="Record an architectural or technical decision (ADR). Creates an ADR for future reference and handover.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Brief title for the decision (e.g., 'Use PostgreSQL for Foodplanner')",
                    },
                    "context": {
                        "type": "string",
                        "description": "Why was this decision needed? What problem does it solve?",
                    },
                    "decision": {
                        "type": "string",
                        "description": "What was decided?",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Why was this option chosen over alternatives?",
                    },
                    "alternatives": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Other options that were considered",
                    },
                    "consequences": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Expected impacts of this decision",
                    },
                    "related_issues": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Related GitHub issue numbers",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Categories (e.g., 'database', 'api', 'frontend')",
                    },
                },
                "required": ["title", "context", "decision", "rationale"],
            },
        ),
        Tool(
            name="capture_lesson",
            description="Record a learning or insight from a sprint retrospective.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sprint": {
                        "type": "string",
                        "description": "Sprint identifier (e.g., '2025s1-sprint3')",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["went_well", "to_improve", "action_item", "insight"],
                        "description": "Type of learning",
                    },
                    "description": {
                        "type": "string",
                        "description": "The learning or insight",
                    },
                    "related_decisions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of related architectural decisions",
                    },
                },
                "required": ["sprint", "category", "description"],
            },
        ),
        Tool(
            name="search_knowledge",
            description="Search captured decisions and learnings. Useful for finding relevant past decisions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["decisions", "learnings", "all"],
                        "description": "What to search (default: all)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default: 5)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_decisions",
            description="List architectural decisions with optional filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["proposed", "accepted", "deprecated", "superseded"],
                        "description": "Filter by status",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default: 10)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="list_learnings",
            description="List retrospective learnings with optional filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sprint": {
                        "type": "string",
                        "description": "Filter by sprint",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["went_well", "to_improve", "action_item", "insight"],
                        "description": "Filter by category",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default: 20)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="generate_handover_summary",
            description="Generate a handover package summarizing the semester's decisions, learnings, and recommendations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "semester": {
                        "type": "string",
                        "description": "Semester identifier (e.g., '2025s1')",
                    },
                    "additional_notes": {
                        "type": "string",
                        "description": "Any additional notes to include in handover",
                    },
                },
                "required": ["semester"],
            },
        ),
        Tool(
            name="get_handover",
            description="Get an existing handover package for a semester.",
            inputSchema={
                "type": "object",
                "properties": {
                    "semester": {
                        "type": "string",
                        "description": "Semester identifier (e.g., '2025s1')",
                    },
                },
                "required": ["semester"],
            },
        ),
        Tool(
            name="review_handover",
            description="Mark a handover package as reviewed and add reviewer notes. Supervisor only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "package_id": {
                        "type": "string",
                        "description": "Handover package ID",
                    },
                    "approved": {
                        "type": "boolean",
                        "description": "Whether the package is approved",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Reviewer notes and corrections",
                    },
                },
                "required": ["package_id", "approved"],
            },
        ),
    ]


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(UTC)


# ============================================================================
# Architectural Decision Tools
# ============================================================================


async def handle_capture_decision(
    adapter: ResearchDataAdapter,
    session: SessionState,
    title: str,
    context: str,
    decision: str,
    rationale: str,
    alternatives: list[str] | None = None,
    consequences: list[str] | None = None,
    related_issues: list[str] | None = None,
    related_files: list[str] | None = None,
    tags: list[str] | None = None,
    discipline_notes: dict[str, str] | None = None,
) -> list[TextContent]:
    """Capture an architectural decision (ADR).

    Args:
        adapter: Research data adapter
        session: Current session state
        title: Brief title for the decision
        context: Why this decision was needed
        decision: What was decided
        rationale: Why this option was chosen
        alternatives: Other options considered
        consequences: Expected impacts
        related_issues: GitHub issue numbers
        related_files: File paths affected
        tags: Categorization tags
        discipline_notes: Discipline-specific explanations

    Returns:
        Confirmation with decision ID
    """
    adr = ArchitecturalDecision(
        id=str(uuid.uuid4()),
        timestamp=_utcnow(),
        team_id=session.team_id,
        title=title,
        context=context,
        decision=decision,
        rationale=rationale,
        alternatives=alternatives or [],
        consequences=consequences or [],
        status=DecisionStatus.ACCEPTED,
        related_issues=related_issues or [],
        related_files=related_files or [],
        tags=tags or [],
        discipline_notes=discipline_notes or {},
    )

    try:
        await adapter.save_decision(adr)

        return [
            TextContent(
                type="text",
                text=f"# Decision Recorded\n\n"
                f"**{title}** (ID: `{adr.id[:8]}`)\n\n"
                f"This decision has been captured and will be included in the semester handover.\n\n"
                f"**Full ID:** `{adr.id}`\n"
                f"**Team:** {session.team_id or 'not set'}\n"
                f"**Tags:** {', '.join(tags) if tags else 'none'}",
            )
        ]

    except Exception as e:
        logger.exception("Error saving decision")
        return [
            TextContent(
                type="text",
                text=f"Error saving decision: {e}",
            )
        ]


async def handle_list_decisions(
    adapter: ResearchDataAdapter,
    status: str | None = None,
    tags: list[str] | None = None,
    limit: int = 10,
) -> list[TextContent]:
    """List architectural decisions.

    Args:
        adapter: Research data adapter
        status: Filter by status (proposed, accepted, deprecated, superseded)
        tags: Filter by tags
        limit: Maximum number of results

    Returns:
        List of decisions
    """
    try:
        status_filter = DecisionStatus(status) if status else None
    except ValueError:
        valid = ", ".join(s.value for s in DecisionStatus)
        return [
            TextContent(
                type="text",
                text=f"Invalid status '{status}'. Valid: {valid}",
            )
        ]

    try:
        decisions = await adapter.list_decisions(
            status=status_filter,
            tags=tags,
            limit=limit,
        )

        if not decisions:
            return [
                TextContent(
                    type="text",
                    text="No architectural decisions found.",
                )
            ]

        lines = ["# Architectural Decisions", ""]
        for d in decisions:
            lines.append(f"## {d.title}")
            lines.append(f"**ID:** `{d.id[:8]}` | **Status:** {d.status.value} | **Date:** {d.timestamp.date()}")
            lines.append(f"\n{d.decision[:200]}..." if len(d.decision) > 200 else f"\n{d.decision}")
            if d.tags:
                lines.append(f"\n*Tags: {', '.join(d.tags)}*")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.exception("Error listing decisions")
        return [TextContent(type="text", text=f"Error listing decisions: {e}")]


# ============================================================================
# Retrospective Learning Tools
# ============================================================================


async def handle_capture_lesson(
    adapter: ResearchDataAdapter,
    session: SessionState,
    sprint: str,
    category: str,
    description: str,
    related_decisions: list[str] | None = None,
) -> list[TextContent]:
    """Capture a retrospective learning.

    Args:
        adapter: Research data adapter
        session: Current session state
        sprint: Sprint identifier (e.g., "2025s1-sprint3")
        category: Category (went_well, to_improve, action_item, insight)
        description: The learning or insight
        related_decisions: IDs of related architectural decisions

    Returns:
        Confirmation with learning ID
    """
    try:
        cat = LearningCategory(category)
    except ValueError:
        valid = ", ".join(c.value for c in LearningCategory)
        return [
            TextContent(
                type="text",
                text=f"Invalid category '{category}'. Valid: {valid}",
            )
        ]

    learning = RetrospectiveLearning(
        id=str(uuid.uuid4()),
        timestamp=_utcnow(),
        team_id=session.team_id,
        sprint=sprint,
        category=cat,
        description=description,
        related_decisions=related_decisions or [],
        follow_up_status=FollowUpStatus.PENDING if cat == LearningCategory.ACTION_ITEM else None,
    )

    try:
        await adapter.save_learning(learning)

        emoji = {
            LearningCategory.WENT_WELL: "+",
            LearningCategory.TO_IMPROVE: "-",
            LearningCategory.ACTION_ITEM: "!",
            LearningCategory.INSIGHT: "*",
        }.get(cat, "-")

        return [
            TextContent(
                type="text",
                text=f"# [{emoji}] Learning Captured\n\n"
                f"**Sprint:** {sprint}\n"
                f"**Category:** {cat.value}\n"
                f"**ID:** `{learning.id[:8]}`\n\n"
                f"{description}",
            )
        ]

    except Exception as e:
        logger.exception("Error saving learning")
        return [TextContent(type="text", text=f"Error saving learning: {e}")]


async def handle_list_learnings(
    adapter: ResearchDataAdapter,
    sprint: str | None = None,
    category: str | None = None,
    limit: int = 20,
) -> list[TextContent]:
    """List retrospective learnings.

    Args:
        adapter: Research data adapter
        sprint: Filter by sprint
        category: Filter by category
        limit: Maximum results

    Returns:
        List of learnings
    """
    try:
        if sprint:
            learnings = await adapter.get_learnings_by_sprint(sprint)
        elif category:
            try:
                cat = LearningCategory(category)
            except ValueError:
                valid = ", ".join(c.value for c in LearningCategory)
                return [TextContent(type="text", text=f"Invalid category. Valid: {valid}")]
            learnings = await adapter.get_learnings_by_category(cat, limit=limit)
        else:
            learnings = await adapter.list_learnings(limit=limit)

        if not learnings:
            return [TextContent(type="text", text="No learnings found.")]

        lines = ["# Retrospective Learnings", ""]

        # Group by sprint if not filtered
        current_sprint = None
        for learning in learnings:
            if learning.sprint != current_sprint:
                current_sprint = learning.sprint
                lines.append(f"## Sprint: {current_sprint}")
                lines.append("")

            emoji = {
                LearningCategory.WENT_WELL: "[+]",
                LearningCategory.TO_IMPROVE: "[-]",
                LearningCategory.ACTION_ITEM: "[!]",
                LearningCategory.INSIGHT: "[*]",
            }.get(learning.category, "[-]")

            lines.append(f"{emoji} {learning.description}")
            if learning.follow_up_status:
                lines.append(f"    *Status: {learning.follow_up_status.value}*")
            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.exception("Error listing learnings")
        return [TextContent(type="text", text=f"Error listing learnings: {e}")]


# ============================================================================
# Knowledge Search Tools
# ============================================================================


async def handle_search_knowledge(
    adapter: ResearchDataAdapter,
    query: str,
    type: str = "all",
    limit: int = 5,
) -> list[TextContent]:
    """Search captured decisions and learnings.

    Args:
        adapter: Research data adapter
        query: Search query
        type: What to search (decisions, learnings, all)
        limit: Maximum results per type

    Returns:
        Search results
    """
    lines = [f"# Search Results for: {query}", ""]

    try:
        if type in ("decisions", "all"):
            decisions = await adapter.search_decisions(query, limit=limit)
            if decisions:
                lines.append("## Architectural Decisions")
                lines.append("")
                for d in decisions:
                    lines.append(f"### {d.title}")
                    lines.append(f"*ID: `{d.id[:8]}` | Status: {d.status.value}*")
                    lines.append(f"\n**Context:** {d.context[:150]}..." if len(d.context) > 150 else f"\n**Context:** {d.context}")
                    lines.append(f"\n**Decision:** {d.decision[:150]}..." if len(d.decision) > 150 else f"\n**Decision:** {d.decision}")
                    lines.append("")
            elif type == "decisions":
                lines.append("No matching decisions found.")
                lines.append("")

        if type in ("learnings", "all"):
            learnings = await adapter.search_learnings(query, limit=limit)
            if learnings:
                lines.append("## Retrospective Learnings")
                lines.append("")
                for learning in learnings:
                    emoji = {
                        LearningCategory.WENT_WELL: "[+]",
                        LearningCategory.TO_IMPROVE: "[-]",
                        LearningCategory.ACTION_ITEM: "[!]",
                        LearningCategory.INSIGHT: "[*]",
                    }.get(learning.category, "[-]")
                    lines.append(f"{emoji} **{learning.sprint}**: {learning.description[:200]}")
                    lines.append(f"   *ID: `{learning.id[:8]}`*")
                    lines.append("")
            elif type == "learnings":
                lines.append("No matching learnings found.")
                lines.append("")

        if len(lines) == 2:  # Only header
            lines.append("No results found.")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.exception("Error searching knowledge")
        return [TextContent(type="text", text=f"Error searching knowledge: {e}")]


# ============================================================================
# Handover Package Tools
# ============================================================================


async def handle_generate_handover_summary(
    adapter: ResearchDataAdapter,
    semester: str,
    additional_notes: str | None = None,
) -> list[TextContent]:
    """Generate a handover package for the semester.

    Aggregates decisions and learnings into a comprehensive handover document.

    Args:
        adapter: Research data adapter
        semester: Semester identifier (e.g., "2025s1")
        additional_notes: Additional notes to include

    Returns:
        Generated handover package
    """
    try:
        # Gather all decisions and learnings
        decisions = await adapter.list_decisions(limit=100)
        learnings = await adapter.list_learnings(limit=100)

        # Filter for accepted decisions
        accepted_decisions = [d for d in decisions if d.status == DecisionStatus.ACCEPTED]

        # Separate learnings by category
        went_well = [learn for learn in learnings if learn.category == LearningCategory.WENT_WELL]
        to_improve = [learn for learn in learnings if learn.category == LearningCategory.TO_IMPROVE]
        action_items = [learn for learn in learnings if learn.category == LearningCategory.ACTION_ITEM]
        insights = [learn for learn in learnings if learn.category == LearningCategory.INSIGHT]

        # Generate executive summary
        summary_parts = [
            (f"This handover covers {len(accepted_decisions)} architectural decisions "
            f"and {len(learnings)} retrospective learnings from {semester}."),
        ]
        if to_improve:
            summary_parts.append(f"Key areas for improvement: {len(to_improve)} items identified.")
        if action_items:
            pending = [a for a in action_items if a.follow_up_status == FollowUpStatus.PENDING]
            if pending:
                summary_parts.append(f"Pending action items: {len(pending)}.")

        executive_summary = " ".join(summary_parts)
        if additional_notes:
            executive_summary += f"\n\n{additional_notes}"

        # Identify known issues from action items and to_improve
        known_issues = [learn.description for learn in to_improve[:5]]
        known_issues.extend([a.description for a in action_items if a.follow_up_status == FollowUpStatus.PENDING][:3])

        # Generate priorities
        priorities = []
        if action_items:
            priorities.append(f"Address {len([a for a in action_items if a.follow_up_status == FollowUpStatus.PENDING])} pending action items")
        if to_improve:
            priorities.append("Review and address improvement areas")
        if accepted_decisions:
            priorities.append("Review architectural decisions for continued relevance")

        # Create package
        package = HandoverPackage(
            id=str(uuid.uuid4()),
            generated_at=_utcnow(),
            semester=semester,
            executive_summary=executive_summary,
            key_decisions=[d.id for d in accepted_decisions[:10]],  # Top 10
            lessons_learned=[learn.id for learn in learnings[:20]],  # Top 20
            known_issues=known_issues,
            recommended_priorities=priorities,
            human_reviewed=False,
            reviewer_notes=None,
        )

        # Save package
        await adapter.save_handover(package)

        # Format output
        output = [
            f"# GIRAF Handover Package: {semester}",
            f"\n*Generated: {package.generated_at.isoformat()}*",
            f"\n## Executive Summary\n\n{executive_summary}",
            "\n## Key Decisions\n",
        ]

        for decision_id in package.key_decisions[:5]:
            decision = await adapter.get_decision(decision_id)
            if decision:
                output.append(f"### {decision.title}")
                output.append(f"\n**Context:** {decision.context}")
                output.append(f"\n**Decision:** {decision.decision}")
                output.append(f"\n**Rationale:** {decision.rationale}\n")

        if len(package.key_decisions) > 5:
            output.append(f"*...and {len(package.key_decisions) - 5} more decisions*\n")

        output.append("\n## Lessons Learned\n")
        output.append("### What Went Well")
        for learn in went_well[:5]:
            output.append(f"- {learn.description}")
        output.append("\n### Areas to Improve")
        for learn in to_improve[:5]:
            output.append(f"- {learn.description}")
        output.append("\n### Key Insights")
        for learn in insights[:5]:
            output.append(f"- {learn.description}")

        output.append("\n## Known Issues\n")
        for issue in package.known_issues:
            output.append(f"- {issue}")

        output.append("\n## Recommended Priorities for Next Semester\n")
        for i, priority in enumerate(package.recommended_priorities, 1):
            output.append(f"{i}. {priority}")

        output.append("\n---")
        output.append("\n*This package requires human review before finalizing.*")
        output.append(f"\n*Package ID: `{package.id}`*")

        return [TextContent(type="text", text="\n".join(output))]

    except Exception as e:
        logger.exception("Error generating handover")
        return [TextContent(type="text", text=f"Error generating handover: {e}")]


async def handle_review_handover(
    adapter: ResearchDataAdapter,
    package_id: str,
    approved: bool,
    notes: str | None = None,
) -> list[TextContent]:
    """Mark a handover package as reviewed.

    Supervisor-only tool.

    Args:
        adapter: Research data adapter
        package_id: Handover package ID
        approved: Whether the package is approved
        notes: Reviewer notes

    Returns:
        Confirmation
    """
    try:
        # First check if package exists
        package = await adapter.get_handover_by_id(package_id)
        if not package:
            return [
                TextContent(
                    type="text",
                    text=f"Handover package `{package_id}` not found.",
                )
            ]

        success = await adapter.mark_handover_reviewed(
            package_id=package_id,
            approved=approved,
            notes=notes,
        )

        if success:
            status = "APPROVED" if approved else "NEEDS REVISION"
            return [
                TextContent(
                    type="text",
                    text=f"# Handover Review Complete\n\n"
                    f"**Package:** `{package_id[:8]}`\n"
                    f"**Semester:** {package.semester}\n"
                    f"**Status:** {status}\n"
                    f"**Notes:** {notes or 'none'}\n",
                )
            ]
        else:
            return [
                TextContent(
                    type="text",
                    text=f"Failed to update package `{package_id}`.",
                )
            ]

    except Exception as e:
        logger.exception("Error reviewing handover")
        return [TextContent(type="text", text=f"Error reviewing handover: {e}")]


async def handle_get_handover(
    adapter: ResearchDataAdapter,
    semester: str,
) -> list[TextContent]:
    """Get a handover package for a semester.

    Args:
        adapter: Research data adapter
        semester: Semester identifier

    Returns:
        Handover package if found
    """
    try:
        package = await adapter.get_handover(semester)
        if not package:
            return [
                TextContent(
                    type="text",
                    text=f"No handover package found for semester `{semester}`.",
                )
            ]

        status = "Reviewed" if package.human_reviewed else "Pending Review"

        output = [
            f"# Handover Package: {semester}",
            f"\n*Generated: {package.generated_at.isoformat()}*",
            f"\n*Status: {status}*",
            f"\n## Executive Summary\n\n{package.executive_summary}",
            "\n## Statistics\n",
            f"- Key Decisions: {len(package.key_decisions)}",
            f"- Lessons Learned: {len(package.lessons_learned)}",
            f"- Known Issues: {len(package.known_issues)}",
            f"- Priorities: {len(package.recommended_priorities)}",
        ]

        if package.reviewer_notes:
            output.append(f"\n## Reviewer Notes\n\n{package.reviewer_notes}")

        output.append(f"\n\n*Package ID: `{package.id}`*")

        return [TextContent(type="text", text="\n".join(output))]

    except Exception as e:
        logger.exception("Error getting handover")
        return [TextContent(type="text", text=f"Error getting handover: {e}")]
