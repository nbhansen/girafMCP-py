"""Cross-disciplinary framing tool handlers.

Tools for adapting explanations across disciplinary boundaries
(CS, Interaction Design, Business, Health).
"""

import logging

from mcp.types import TextContent, Tool

from girafmcp.core.services.multiframe_service import MultiFrameService
from girafmcp.core.session import SessionState

logger = logging.getLogger(__name__)


def list_tools() -> list[Tool]:
    """Return tool definitions for discipline framing tools."""
    return [
        Tool(
            name="explain_for_discipline",
            description="Re-explain a concept or response for a different disciplinary background (CS, Interaction Design, Business, Health).",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_discipline": {
                        "type": "string",
                        "enum": ["cs", "id", "business", "health"],
                        "description": "Target discipline for explanation",
                    },
                    "concept": {
                        "type": "string",
                        "description": "Specific concept to explain (optional)",
                    },
                },
                "required": ["target_discipline"],
            },
        ),
        Tool(
            name="compare_perspectives",
            description="Show how different disciplines would approach or understand a topic or design decision.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic or decision to analyze",
                    },
                },
                "required": ["topic"],
            },
        ),
        Tool(
            name="translate_term",
            description="Translate a technical term for a specific discipline or all disciplines.",
            inputSchema={
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Technical term to translate",
                    },
                    "target_discipline": {
                        "type": "string",
                        "enum": ["cs", "id", "business", "health"],
                        "description": "Target discipline (optional, shows all if not specified)",
                    },
                },
                "required": ["term"],
            },
        ),
        Tool(
            name="get_discipline_profile",
            description="Get detailed information about a discipline profile including vocabulary emphasis and explanation style.",
            inputSchema={
                "type": "object",
                "properties": {
                    "discipline": {
                        "type": "string",
                        "enum": ["cs", "id", "business", "health"],
                        "description": "Discipline to get profile for",
                    },
                },
                "required": ["discipline"],
            },
        ),
        Tool(
            name="list_disciplines",
            description="List all available discipline profiles with summaries.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


# ============================================================================
# Tool Handlers
# ============================================================================


async def handle_explain_for_discipline(
    service: MultiFrameService,
    session: SessionState,
    target_discipline: str,
    concept: str | None = None,
) -> list[TextContent]:
    """Re-explain a concept for a different disciplinary background.

    Args:
        service: MultiFrameService instance
        session: Current session state
        target_discipline: Target discipline (cs, id, business, health)
        concept: Specific concept to explain (optional)

    Returns:
        Discipline-adapted explanation
    """
    # Validate discipline
    valid_disciplines = service.get_all_disciplines()
    if target_discipline not in valid_disciplines:
        return [
            TextContent(
                type="text",
                text=f"Invalid discipline '{target_discipline}'. "
                f"Valid options: {', '.join(valid_disciplines)}",
            )
        ]

    profile = service.get_discipline_profile(target_discipline)
    if not profile:
        return [
            TextContent(
                type="text",
                text=f"No profile found for discipline '{target_discipline}'.",
            )
        ]

    lines = [
        f"# Explanation for {profile.name}",
        "",
    ]

    if concept:
        # Try to get a translation for this concept
        framed = service.generate_multiframe_explanation(concept)

        if target_discipline in framed.frames:
            lines.extend([
                f"## {concept}",
                "",
                framed.frames[target_discipline],
                "",
            ])
        else:
            # Provide general guidance based on profile
            lines.extend([
                f"## {concept}",
                "",
                f"*Explanation style: {profile.explanation_style.value}*",
                "",
                (f"This concept should be explained with focus on: "
                f"{', '.join(profile.vocabulary_emphasis[:3])}"),
                "",
            ])

        # Add translation hints if relevant
        hint = service.get_translation_hint(concept, target_discipline)
        if hint:
            lines.extend([
                "**Quick translation:** " + hint,
                "",
            ])
    else:
        # General explanation about the discipline's needs
        lines.extend([
            f"## {profile.name} Perspective",
            "",
            f"**Explanation style:** {profile.explanation_style.value}",
            f"**Code detail level:** {profile.default_code_depth.value}",
            "",
            "### Vocabulary emphasis:",
            "",
        ])
        for vocab in profile.vocabulary_emphasis:
            lines.append(f"- {vocab}")

        lines.extend([
            "",
            "### Assumed knowledge:",
            "",
        ])
        for knowledge in profile.assumed_knowledge:
            lines.append(f"- {knowledge}")

        if profile.translation_hints:
            lines.extend([
                "",
                "### Common term translations:",
                "",
            ])
            for term, translation in list(profile.translation_hints.items())[:5]:
                lines.append(f"- **{term}**: {translation}")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_compare_perspectives(
    service: MultiFrameService,
    topic: str,
) -> list[TextContent]:
    """Show how different disciplines would approach a topic.

    Args:
        service: MultiFrameService instance
        topic: Topic or decision to analyze

    Returns:
        Multi-disciplinary perspective comparison
    """
    perspectives = service.compare_perspectives(topic)

    if not perspectives:
        return [
            TextContent(
                type="text",
                text=f"No perspectives available for topic: {topic}",
            )
        ]

    lines = [
        f"# Multi-Disciplinary Perspectives on: {topic}",
        "",
    ]

    for discipline, perspective in perspectives.items():
        profile = service.get_discipline_profile(discipline)
        name = profile.name if profile else discipline.upper()

        lines.extend([
            f"## {name} Perspective",
            "",
            perspective,
            "",
        ])

    lines.extend([
        "---",
        ("*These perspectives highlight how different backgrounds "
        "approach the same technical concepts with different priorities.*"),
    ])

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_translate_term(
    service: MultiFrameService,
    term: str,
    target_discipline: str | None = None,
) -> list[TextContent]:
    """Translate a technical term for a discipline.

    Args:
        service: MultiFrameService instance
        term: Technical term to translate
        target_discipline: Target discipline (optional, shows all if not specified)

    Returns:
        Translation(s) for the term
    """
    lines = [f"# Term Translation: {term}", ""]

    if target_discipline:
        # Single discipline translation
        valid_disciplines = service.get_all_disciplines()
        if target_discipline not in valid_disciplines:
            return [
                TextContent(
                    type="text",
                    text=f"Invalid discipline '{target_discipline}'. "
                    f"Valid options: {', '.join(valid_disciplines)}",
                )
            ]

        # Try concept translation first
        translation = service.translate_concept(term, target_discipline)
        if translation:
            profile = service.get_discipline_profile(target_discipline)
            name = profile.name if profile else target_discipline.upper()
            lines.extend([
                f"## For {name}",
                "",
                translation,
            ])
        else:
            # Try translation hint
            hint = service.get_translation_hint(term, target_discipline)
            if hint:
                profile = service.get_discipline_profile(target_discipline)
                name = profile.name if profile else target_discipline.upper()
                lines.extend([
                    f"## For {name}",
                    "",
                    hint,
                ])
            else:
                lines.append(
                    f"No translation available for '{term}' "
                    f"in {target_discipline}."
                )
    else:
        # All disciplines
        translations = service.get_all_translations_for_concept(term)

        if translations:
            for discipline, translation in translations.items():
                profile = service.get_discipline_profile(discipline)
                name = profile.name if profile else discipline.upper()
                lines.extend([
                    f"## {name}",
                    "",
                    translation,
                    "",
                ])
        else:
            # Try translation hints from each profile
            found_any = False
            for discipline in service.get_all_disciplines():
                hint = service.get_translation_hint(term, discipline)
                if hint:
                    found_any = True
                    profile = service.get_discipline_profile(discipline)
                    name = profile.name if profile else discipline.upper()
                    lines.extend([
                        f"## {name}",
                        "",
                        hint,
                        "",
                    ])

            if not found_any:
                lines.append(f"No translations available for '{term}'.")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_get_discipline_profile(
    service: MultiFrameService,
    discipline: str,
) -> list[TextContent]:
    """Get detailed information about a discipline profile.

    Args:
        service: MultiFrameService instance
        discipline: Discipline identifier

    Returns:
        Detailed profile information
    """
    profile = service.get_discipline_profile(discipline)

    if not profile:
        valid = service.get_all_disciplines()
        return [
            TextContent(
                type="text",
                text=f"Unknown discipline '{discipline}'. "
                f"Available: {', '.join(valid)}",
            )
        ]

    lines = [
        f"# {profile.name} Profile",
        "",
        f"**Discipline ID:** {profile.discipline.value}",
        f"**Explanation Style:** {profile.explanation_style.value}",
        f"**Default Code Depth:** {profile.default_code_depth.value}",
        "",
        "## Vocabulary Emphasis",
        "",
    ]

    for vocab in profile.vocabulary_emphasis:
        lines.append(f"- {vocab}")

    lines.extend([
        "",
        "## Assumed Knowledge",
        "",
    ])

    for knowledge in profile.assumed_knowledge:
        lines.append(f"- {knowledge}")

    if profile.translation_hints:
        lines.extend([
            "",
            "## Translation Hints",
            "",
            "| Term | Translation |",
            "|------|-------------|",
        ])
        for term, translation in profile.translation_hints.items():
            # Escape pipes in translation
            safe_translation = translation.replace("|", "\\|")
            lines.append(f"| {term} | {safe_translation} |")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_list_disciplines(
    service: MultiFrameService,
) -> list[TextContent]:
    """List all available discipline profiles.

    Args:
        service: MultiFrameService instance

    Returns:
        List of disciplines with summaries
    """
    profiles = service.config.get_all_profiles()

    if not profiles:
        return [
            TextContent(
                type="text",
                text="No discipline profiles configured.",
            )
        ]

    lines = [
        "# Available Discipline Profiles",
        "",
        "| ID | Name | Explanation Style | Code Depth |",
        "|----|------|-------------------|------------|",
    ]

    for discipline_id, profile in profiles.items():
        lines.append(
            f"| {discipline_id} | {profile.name} | "
            f"{profile.explanation_style.value} | "
            f"{profile.default_code_depth.value} |"
        )

    lines.extend([
        "",
        ("Use `explain_for_discipline` to get explanations adapted for a "
        "specific discipline."),
        "",
        ("Use `compare_perspectives` to see how different disciplines "
        "approach the same topic."),
    ])

    return [TextContent(type="text", text="\n".join(lines))]
