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
from girafmcp.tools import context, github, search, research  # noqa: E402
from girafmcp.core.session import get_current_session  # noqa: E402
from girafmcp.core.services.guardrails_service import GuardrailsService  # noqa: E402

# Create server instance
server = Server("giraf-mcp")

# Initialize adapters and services (lazy loading)
_github_adapter: GitHubAdapter | None = None
_chroma_adapter: ChromaAdapter | None = None
_file_adapter: FileAdapter | None = None
_guardrails_service: GuardrailsService | None = None


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