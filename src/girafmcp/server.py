"""GIRAF MCP Server - Knowledge assistant for the GIRAF project.

This MCP server provides tools for searching documentation, code,
and domain knowledge to help students working on the GIRAF project.
"""

import asyncio
import os
from pathlib import Path
from typing import Any, AsyncGenerator

from dotenv import load_dotenv

# Load .env file from project root
_project_root = Path(__file__).parent.parent.parent
load_dotenv(_project_root / ".env")

from mcp.server import Server  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402
from mcp.types import TextContent, Tool  # noqa: E402

from girafmcp.adapters import ChromaAdapter, FileAdapter, GitHubAdapter  # noqa: E402
from girafmcp.adapters.research_data_adapter import ResearchDataAdapter  # noqa: E402
from girafmcp.tools import context, github, search, research, knowledge, resilience, discipline  # noqa: E402
from girafmcp.core.session import get_current_session  # noqa: E402
from girafmcp.core.services.guardrails_service import GuardrailsService  # noqa: E402
from girafmcp.core.services.resilience_service import ResilienceService  # noqa: E402
from girafmcp.core.services.multiframe_service import MultiFrameService, MultiFrameConfig  # noqa: E402

# Create server instance
server = Server("giraf-mcp")

# Initialize adapters and services (lazy loading)
_github_adapter: GitHubAdapter | None = None
_chroma_adapter: ChromaAdapter | None = None
_file_adapter: FileAdapter | None = None
_guardrails_service: GuardrailsService | None = None
_research_data_adapter: ResearchDataAdapter | None = None
_resilience_service: ResilienceService | None = None
_multiframe_service: MultiFrameService | None = None


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


def get_guardrails_service() -> GuardrailsService:
    """Get or create guardrails service."""
    global _guardrails_service
    if _guardrails_service is None:
        _guardrails_service = GuardrailsService()
    return _guardrails_service


def get_research_data_adapter() -> ResearchDataAdapter:
    """Get or create research data adapter."""
    global _research_data_adapter
    if _research_data_adapter is None:
        db_path = os.environ.get("GIRAF_KNOWLEDGE_DB", "data/knowledge.db")
        _research_data_adapter = ResearchDataAdapter(db_path)
    return _research_data_adapter


def get_resilience_service() -> ResilienceService:
    """Get or create resilience service."""
    global _resilience_service
    if _resilience_service is None:
        _resilience_service = ResilienceService()
    return _resilience_service


def get_multiframe_service() -> MultiFrameService:
    """Get or create multiframe service."""
    global _multiframe_service
    if _multiframe_service is None:
        config_path = Path(os.environ.get(
            "GIRAF_DISCIPLINE_PROFILES",
            str(_project_root / "data" / "discipline_profiles.yaml")
        ))
        config = MultiFrameConfig(config_path)
        _multiframe_service = MultiFrameService(config)
    return _multiframe_service


# === Tool Definitions ===


@server.list_tools()  # type: ignore
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
        Tool(
            name="search_static_documents",
            description="Semantic search over PDFs, research papers, and static documents. Returns content with page-level citations.",
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
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags (e.g., ['research', 'handover'])",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_static_documents",
            description="List all ingested static documents (PDFs, research papers) with their tags.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        # === Research Feature Tools ===
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
        # === Knowledge Capture Tools ===
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
        # === Resilience Testing Tools ===
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
        # === Cross-Disciplinary Framing Tools ===
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


@server.call_tool()  # type: ignore
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    if name == "list_repositories":
        return await github.handle_list_repositories(get_github_adapter())

    elif name == "get_file":
        return await github.handle_get_file(
            get_github_adapter(),
            repo=arguments["repo"],
            path=arguments["path"],
            ref=arguments.get("ref"),
        )

    elif name == "search_code":
        return await github.handle_search_code(
            get_github_adapter(),
            query=arguments["query"],
            repo=arguments.get("repo"),
        )

    elif name == "search_documentation":
        return await search.handle_search_documentation(
            get_chroma_adapter(),
            query=arguments["query"],
            limit=arguments.get("limit", 5),
        )

    elif name == "get_permalink":
        return await github.handle_get_permalink(
            get_github_adapter(),
            repo=arguments["repo"],
            path=arguments["path"],
            line=arguments.get("line"),
            end_line=arguments.get("end_line"),
        )

    elif name == "get_project_context":
        return await context.handle_get_project_context(get_file_adapter())

    elif name == "list_personas":
        return await context.handle_list_personas(get_file_adapter())

    elif name == "get_persona":
        return await context.handle_get_persona(
            get_file_adapter(), persona_id=arguments["persona_id"]
        )

    elif name == "search_domain_knowledge":
        return await context.handle_search_domain_knowledge(
            get_file_adapter(),
            query=arguments["query"],
            limit=arguments.get("limit", 5),
        )

    elif name == "list_domain_topics":
        return await context.handle_list_domain_topics(get_file_adapter())

    elif name == "search_wiki":
        return await github.handle_search_wiki(
            get_github_adapter(),
            query=arguments["query"],
            limit=arguments.get("limit", 5),
        )

    elif name == "list_wiki_pages":
        return await github.handle_list_wiki_pages(get_github_adapter())

    elif name == "search_static_documents":
        return await search.handle_search_static_documents(
            get_chroma_adapter(),
            query=arguments["query"],
            limit=arguments.get("limit", 5),
            tags=arguments.get("tags"),
        )

    elif name == "list_static_documents":
        return await search.handle_list_static_documents(get_chroma_adapter())

    # === Research Feature Tool Handlers ===

    elif name == "set_session_metadata":
        return await research.handle_set_session_metadata(
            session=get_current_session(),
            team_id=arguments.get("team_id"),
            role=arguments.get("role"),
            discipline=arguments.get("discipline"),
        )

    elif name == "request_more_detail":
        return await research.handle_request_more_detail(
            session=get_current_session(),
            guardrails_service=get_guardrails_service(),
            dispatch_fn=_dispatch_tool,
        )

    elif name == "configure_guardrails":
        return await research.handle_configure_guardrails(
            guardrails_service=get_guardrails_service(),
            team_id=arguments["team_id"],
            enabled=arguments.get("enabled"),
            mode=arguments.get("mode"),
        )

    elif name == "get_guardrails_status":
        return await research.handle_get_guardrails_status(
            guardrails_service=get_guardrails_service(),
            session=get_current_session(),
        )

    elif name == "get_feature_status":
        return await research.handle_get_feature_status()

    # === Knowledge Capture Tool Handlers ===

    elif name == "capture_decision":
        return await knowledge.handle_capture_decision(
            adapter=get_research_data_adapter(),
            session=get_current_session(),
            title=arguments["title"],
            context=arguments["context"],
            decision=arguments["decision"],
            rationale=arguments["rationale"],
            alternatives=arguments.get("alternatives"),
            consequences=arguments.get("consequences"),
            related_issues=arguments.get("related_issues"),
            related_files=arguments.get("related_files"),
            tags=arguments.get("tags"),
            discipline_notes=arguments.get("discipline_notes"),
        )

    elif name == "capture_lesson":
        return await knowledge.handle_capture_lesson(
            adapter=get_research_data_adapter(),
            session=get_current_session(),
            sprint=arguments["sprint"],
            category=arguments["category"],
            description=arguments["description"],
            related_decisions=arguments.get("related_decisions"),
        )

    elif name == "search_knowledge":
        return await knowledge.handle_search_knowledge(
            adapter=get_research_data_adapter(),
            query=arguments["query"],
            type=arguments.get("type", "all"),
            limit=arguments.get("limit", 5),
        )

    elif name == "list_decisions":
        return await knowledge.handle_list_decisions(
            adapter=get_research_data_adapter(),
            status=arguments.get("status"),
            tags=arguments.get("tags"),
            limit=arguments.get("limit", 10),
        )

    elif name == "list_learnings":
        return await knowledge.handle_list_learnings(
            adapter=get_research_data_adapter(),
            sprint=arguments.get("sprint"),
            category=arguments.get("category"),
            limit=arguments.get("limit", 20),
        )

    elif name == "generate_handover_summary":
        return await knowledge.handle_generate_handover_summary(
            adapter=get_research_data_adapter(),
            semester=arguments["semester"],
            additional_notes=arguments.get("additional_notes"),
        )

    elif name == "get_handover":
        return await knowledge.handle_get_handover(
            adapter=get_research_data_adapter(),
            semester=arguments["semester"],
        )

    elif name == "review_handover":
        return await knowledge.handle_review_handover(
            adapter=get_research_data_adapter(),
            package_id=arguments["package_id"],
            approved=arguments["approved"],
            notes=arguments.get("notes"),
        )

    # === Resilience Testing Tool Handlers ===

    elif name == "report_error_found":
        return await resilience.handle_report_error_found(
            service=get_resilience_service(),
            session=get_current_session(),
            tool_name=arguments["tool_name"],
            error_description=arguments["error_description"],
            proposed_fix=arguments.get("proposed_fix"),
        )

    elif name == "configure_resilience_test":
        return await resilience.handle_configure_resilience_test(
            service=get_resilience_service(),
            team_id=arguments["team_id"],
            mode=arguments.get("mode"),
            enabled=arguments.get("enabled"),
        )

    elif name == "get_resilience_status":
        return await resilience.handle_get_resilience_status(
            service=get_resilience_service(),
            session=get_current_session(),
        )

    elif name == "get_resilience_metrics":
        return await resilience.handle_get_resilience_metrics(
            service=get_resilience_service(),
            session_id=arguments.get("session_id"),
        )

    # === Cross-Disciplinary Framing Tool Handlers ===

    elif name == "explain_for_discipline":
        return await discipline.handle_explain_for_discipline(
            service=get_multiframe_service(),
            session=get_current_session(),
            target_discipline=arguments["target_discipline"],
            concept=arguments.get("concept"),
        )

    elif name == "compare_perspectives":
        return await discipline.handle_compare_perspectives(
            service=get_multiframe_service(),
            topic=arguments["topic"],
        )

    elif name == "translate_term":
        return await discipline.handle_translate_term(
            service=get_multiframe_service(),
            term=arguments["term"],
            target_discipline=arguments.get("target_discipline"),
        )

    elif name == "get_discipline_profile":
        return await discipline.handle_get_discipline_profile(
            service=get_multiframe_service(),
            discipline=arguments["discipline"],
        )

    elif name == "list_disciplines":
        return await discipline.handle_list_disciplines(
            service=get_multiframe_service(),
        )

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _dispatch_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch a tool call to its handler.

    This is used by request_more_detail to re-run the previous query.
    """
    return await call_tool(name, arguments)


# === Startup Initialization ===


async def initialize_static_documents() -> None:
    """Auto-ingest static documents on server startup."""
    import logging

    logger = logging.getLogger(__name__)
    documents_dir = os.environ.get("GIRAF_DOCUMENTS_DIR")

    if not documents_dir:
        logger.info("GIRAF_DOCUMENTS_DIR not set, skipping static document ingestion")
        return

    from pathlib import Path

    docs_path = Path(documents_dir)
    if not docs_path.exists():
        logger.warning(f"Documents directory not found: {documents_dir}")
        return

    try:
        from girafmcp.adapters.pdf_adapter import PDFAdapter
        from girafmcp.core.services.ingestion_service import IngestionService

        pdf_adapter = PDFAdapter(documents_dir=docs_path)
        chroma_adapter = get_chroma_adapter()
        ingestion = IngestionService(pdf_adapter=pdf_adapter, chroma_adapter=chroma_adapter)

        result = await ingestion.ingest_all()

        if result.files_processed > 0:
            logger.info(
                f"Ingested {result.files_processed} files ({result.documents_created} chunks)"
            )
        if result.files_skipped > 0:
            logger.info(f"Skipped {result.files_skipped} unchanged files")
        if result.files_updated > 0:
            logger.info(f"Updated {result.files_updated} modified files")
        if result.errors:
            for error in result.errors:
                logger.error(error)

    except Exception as e:
        logger.error(f"Error during document ingestion: {e}")


# === Entry Point ===


async def run_stdio_server() -> None:
    """Run the MCP server with stdio transport (for Claude Desktop)."""
    await initialize_static_documents()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def run_http_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the MCP server with HTTP/SSE transport (for remote access).

    Args:
        host: Host to bind to. Use "0.0.0.0" for all interfaces.
        port: Port to listen on.
    """
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import JSONResponse
    import uvicorn
    import logging

    logger = logging.getLogger(__name__)

    # Create SSE transport
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Any) -> None:
        """Handle SSE connection."""
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )

    async def handle_messages(request: Any) -> None:
        """Handle incoming messages."""
        await sse.handle_post_message(request.scope, request.receive, request._send)

    async def health_check(request: Any) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({"status": "ok", "server": "giraf-mcp"})

    async def lifespan(app: Any) -> AsyncGenerator[None, None]:
        """Lifespan handler for startup/shutdown."""

        # Startup
        logger.info(f"Starting GIRAF MCP server on http://{host}:{port}")
        logger.info(f"SSE endpoint: http://{host}:{port}/sse")
        logger.info(f"Messages endpoint: http://{host}:{port}/messages/")
        await initialize_static_documents()
        yield
        # Shutdown
        logger.info("Shutting down GIRAF MCP server")

    # Create Starlette app
    app = Starlette(
        debug=False,
        routes=[
            Route("/health", health_check),
            Route("/sse", handle_sse),
            Route("/messages/", handle_messages, methods=["POST"]),
        ],
        lifespan=lifespan,  # type: ignore
    )

    # Run with uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    """Entry point for the MCP server.

    Usage:
        giraf-mcp              # Run with stdio (default, for Claude Desktop)
        giraf-mcp --http       # Run with HTTP/SSE transport
        giraf-mcp --http --port 9000  # Custom port
    """
    import argparse
    import logging
    import sys

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(
        description="GIRAF MCP Server - Knowledge assistant for the GIRAF project"
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run with HTTP/SSE transport instead of stdio",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("GIRAF_MCP_HOST", "0.0.0.0"),
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("GIRAF_MCP_PORT", "8000")),
        help="Port for HTTP server (default: 8000)",
    )

    args = parser.parse_args()

    if args.http:
        run_http_server(host=args.host, port=args.port)
    else:
        asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()