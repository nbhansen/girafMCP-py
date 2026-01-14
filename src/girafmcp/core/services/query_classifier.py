"""Query classification service for research logging.

Provides heuristic classification of query types and meta-skill indicators
based on pattern matching in query text.
"""

import re
from typing import Any, Literal, cast

from girafmcp.core.types import MetaSkillIndicators, QueryType


# Pattern definitions for query type classification
QUERY_TYPE_PATTERNS: dict[QueryType, list[str]] = {
    QueryType.EXPLANATION: [
        r"\bexplain\b",
        r"\bwhat does\b",
        r"\bwhat is\b",
        r"\bhow does\b",
        r"\bwhy does\b",
        r"\bunderstand\b",
        r"\btell me about\b",
        r"\bdescribe\b",
    ],
    QueryType.GENERATION: [
        r"\bwrite\b",
        r"\bcreate\b",
        r"\bimplement\b",
        r"\bgenerate\b",
        r"\bmake\b",
        r"\bbuild\b",
        r"\badd\b",
    ],
    QueryType.NAVIGATION: [
        r"\bfind\b",
        r"\bwhere\b",
        r"\blocate\b",
        r"\blist\b",
        r"\bshow me\b",
        r"\bsearch\b",
        r"\blook for\b",
    ],
    QueryType.DEBUGGING: [
        r"\berror\b",
        r"\bfix\b",
        r"\bwrong\b",
        r"\bdoesn't work\b",
        r"\bdoesn't compile\b",
        r"\bfailing\b",
        r"\bfailed\b",
        r"\bbug\b",
        r"\bcrash\b",
        r"\bexception\b",
        r"\bbroken\b",
    ],
    QueryType.VERIFICATION: [
        r"\bis this correct\b",
        r"\bdoes this work\b",
        r"\bcheck\b",
        r"\bverify\b",
        r"\bvalidate\b",
        r"\breview my\b",
        r"\bis this right\b",
        r"\blook correct\b",
    ],
}

# Meta-skill detection patterns
META_SKILL_PATTERNS = {
    "verification_attempted": [
        r"\bi tried\b",
        r"\bi've tried\b",
        r"\bi tested\b",
        r"\bi ran\b",
        r"\boutput was\b",
        r"\bresult was\b",
        r"\bi checked\b",
    ],
    "test_run_before_query": [
        r"\btest (failed|passed|output)\b",
        r"\bpytest\b",
        r"\bjest\b",
        r"\bunittest\b",
        r"\berror (message|output)\b",
        r"\bstack trace\b",
        r"\btraceback\b",
    ],
    "references_existing_code": [
        r"\b\w+\.(py|ts|js|tsx|jsx|dart|cs)\b",  # File extensions
        r"\bfunction\s+\w+",  # Function names
        r"\bclass\s+\w+",  # Class names
        r"\bdef\s+\w+",  # Python function defs
        r"/\w+/\w+",  # Path patterns
    ],
    "asks_about_integration": [
        r"\bintegrat\w*\b",
        r"\bconnect\b",
        r"\bfit together\b",
        r"\bwork with\b",
        r"\binteract\b",
        r"\bcommunicate\b",
    ],
    "architectural_awareness": [
        r"\barchitecture\b",
        r"\bpattern\b",
        r"\bdesign\b",
        r"\bstructure\b",
        r"\blayer\b",
        r"\bmodule\b",
        r"\bcomponent\b",
    ],
    "hypothesis_present": [
        r"\bi think\b",
        r"\bmaybe because\b",
        r"\bcould it be\b",
        r"\bperhaps\b",
        r"\bi suspect\b",
        r"\bmy guess\b",
        r"\bi believe\b",
    ],
    "isolation_attempted": [
        r"\bi narrowed\b",
        r"\bisolated\b",
        r"\bminimal\b",
        r"\breproduced\b",
        r"\bsimplified\b",
    ],
    "discipline_translation_needed": [
        # Designer jargon
        r"\baffordance\b",
        r"\bux\b",
        r"\bui\b",
        r"\buser flow\b",
        r"\bwireframe\b",
        # Business jargon
        r"\broi\b",
        r"\bstakeholder\b",
        r"\bvalue proposition\b",
        # Health jargon
        r"\bclinical\b",
        r"\bpatient\b",
        r"\bfhir\b",
    ],
    "requests_alternative_framing": [
        r"\bexplain (for|to) a\b",
        r"\bin simpler terms\b",
        r"\bfor a designer\b",
        r"\bfor a non-technical\b",
        r"\bfor beginners\b",
    ],
}

# Error description quality patterns
ERROR_QUALITY_PATTERNS = {
    "diagnostic": [
        r"\bbecause\b.*\bwhen\b",
        r"\bwhen\b.*\bthen\b",
        r"\bif\b.*\belse\b",
        r"\bnull\b.*\bundefined\b",
        r"\bcaused by\b",
    ],
    "specific": [
        r"\bline \d+\b",
        r"\breturns\b",
        r"\bexpected\b.*\bgot\b",
        r"\bvalue\b.*\bnull\b",
        r"\btype\b.*\berror\b",
    ],
    "vague": [
        r"\bit doesn't work\b",
        r"\bsomething.{0,10}wrong\b",
        r"\bnot working\b",
        r"\bbroken\b",
    ],
}


def classify_query_type(tool_name: str, arguments: dict[str, Any]) -> QueryType:
    """Classify the type of query based on tool and arguments.

    Args:
        tool_name: The MCP tool being called
        arguments: Tool arguments

    Returns:
        The classified QueryType
    """
    # Extract query text from arguments
    query_text = _extract_query_text(tool_name, arguments)
    if not query_text:
        # Fall back to tool-based classification
        return _classify_by_tool(tool_name)

    query_lower = query_text.lower()

    # Check patterns in order of specificity
    for query_type, patterns in QUERY_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, query_lower):
                return query_type

    # Fall back to tool-based classification
    return _classify_by_tool(tool_name)


def _classify_by_tool(tool_name: str) -> QueryType:
    """Classify by tool name when no query text available."""
    navigation_tools = [
        "list_repositories",
        "list_wiki_pages",
        "list_personas",
        "list_domain_topics",
        "list_static_documents",
        "get_file",
        "get_permalink",
    ]
    search_tools = [
        "search_code",
        "search_documentation",
        "search_wiki",
        "search_domain_knowledge",
        "search_static_documents",
    ]
    context_tools = [
        "get_project_context",
        "get_persona",
    ]

    if tool_name in navigation_tools:
        return QueryType.NAVIGATION
    elif tool_name in search_tools:
        return QueryType.NAVIGATION  # Search is primarily navigation
    elif tool_name in context_tools:
        return QueryType.EXPLANATION  # Getting context is explanatory

    return QueryType.UNKNOWN


def detect_meta_skills(query_text: str | None) -> MetaSkillIndicators:
    """Detect meta-skill indicators from query text.

    Uses simple pattern matching - more complex session-level analysis
    can be added later.

    Args:
        query_text: The natural language query text

    Returns:
        MetaSkillIndicators with detected patterns
    """
    if not query_text:
        return MetaSkillIndicators()

    query_lower = query_text.lower()
    indicators = MetaSkillIndicators()

    # Check each pattern category
    for field, patterns in META_SKILL_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, query_lower):
                setattr(indicators, field, True)
                break

    # Determine error description quality
    indicators.error_description_quality = _assess_error_quality(query_lower)

    return indicators


def _assess_error_quality(query_lower: str) -> Literal["none", "vague", "specific", "diagnostic"]:
    """Assess the quality of error description in query."""
    ErrorQuality = Literal["none", "vague", "specific", "diagnostic"]
    # Check from most to least specific
    for quality, patterns in [
        ("diagnostic", ERROR_QUALITY_PATTERNS["diagnostic"]),
        ("specific", ERROR_QUALITY_PATTERNS["specific"]),
        ("vague", ERROR_QUALITY_PATTERNS["vague"]),
    ]:
        for pattern in patterns:
            if re.search(pattern, query_lower):
                return cast(ErrorQuality, quality)

    return "none"


def _extract_query_text(tool_name: str, arguments: dict[str, Any]) -> str | None:
    """Extract natural language query from tool arguments.

    Args:
        tool_name: The tool being called
        arguments: Tool arguments

    Returns:
        Extracted query text or None
    """
    # Direct query parameter
    if "query" in arguments:
        return str(arguments["query"])

    # For file retrieval, use path as proxy
    if tool_name == "get_file" and "path" in arguments:
        return f"get file {arguments['path']}"

    # For persona, use persona_id
    if tool_name == "get_persona" and "persona_id" in arguments:
        return f"get persona {arguments['persona_id']}"

    return None


def extract_result_count(response_text: str) -> int | None:
    """Heuristically extract result count from response.

    Args:
        response_text: The tool response text

    Returns:
        Estimated result count or None
    """
    if not response_text:
        return 0

    # Count markdown headers as results
    h2_count = response_text.count("\n## ")
    if h2_count > 0:
        return h2_count

    h3_count = response_text.count("\n### ")
    if h3_count > 0:
        return h3_count

    # Count numbered list items
    numbered_pattern = r"^\d+\."
    numbered_matches = len(re.findall(numbered_pattern, response_text, re.MULTILINE))
    if numbered_matches > 0:
        return numbered_matches

    # Count bullet points
    bullet_count = response_text.count("\n- ")
    if bullet_count > 0:
        return bullet_count

    return None
