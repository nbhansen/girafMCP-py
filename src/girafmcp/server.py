"""GIRAF MCP Server - Knowledge assistant for the GIRAF project.

This MCP server provides tools for searching documentation, code,
and domain knowledge to help students working on the GIRAF project.
"""

import asyncio
import hmac
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ContentBlock,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from girafmcp.core.container import DependencyContainer
from girafmcp.core.session import SessionState, get_current_session, set_current_session
from girafmcp.middleware import create_context
from girafmcp.tools import (
    context,
    discipline,
    github,
    knowledge,
    projects,
    research,
    resilience,
    search,
)

logger = logging.getLogger(__name__)

# Initialize dependency container
container = DependencyContainer()


# === Tool Definitions ===


async def list_tools() -> list[Tool]:
    """List all available tools."""
    tools: list[Tool] = []
    
    # Aggregate tools from all modules
    tools.extend(github.list_tools())
    tools.extend(search.list_tools())
    tools.extend(context.list_tools())
    tools.extend(research.list_tools())
    tools.extend(knowledge.list_tools())
    tools.extend(resilience.list_tools())
    tools.extend(discipline.list_tools())
    tools.extend(projects.list_tools())
    
    return tools


ToolHandler = Callable[[dict[str, Any]], Awaitable[list[TextContent]]]

# Maps each tool name to its handler; arguments come straight from the MCP request
TOOL_HANDLERS: dict[str, ToolHandler] = {
    # === GitHub Tools ===
    "list_repositories": lambda a: github.handle_list_repositories(container.github_adapter),
    "get_file": lambda a: github.handle_get_file(
        container.github_adapter,
        repo=a["repo"],
        path=a["path"],
        ref=a.get("ref"),
    ),
    "search_code": lambda a: github.handle_search_code(
        container.github_adapter,
        query=a["query"],
        repo=a.get("repo"),
    ),
    "get_permalink": lambda a: github.handle_get_permalink(
        container.github_adapter,
        repo=a["repo"],
        path=a["path"],
        line=a.get("line"),
        end_line=a.get("end_line"),
    ),
    "search_wiki": lambda a: github.handle_search_wiki(
        container.github_adapter,
        query=a["query"],
        limit=a.get("limit", 5),
    ),
    "list_wiki_pages": lambda a: github.handle_list_wiki_pages(container.github_adapter),
    # === Search Tools ===
    "search_documentation": lambda a: search.handle_search_documentation(
        container.keyword_search_adapter,
        query=a["query"],
        limit=a.get("limit", 5),
    ),
    "search_static_documents": lambda a: search.handle_search_static_documents(
        container.keyword_search_adapter,
        query=a["query"],
        limit=a.get("limit", 5),
        tags=a.get("tags"),
    ),
    "list_static_documents": lambda a: search.handle_list_static_documents(container.keyword_search_adapter),
    # === Context Tools ===
    "get_semester_context": lambda a: context.handle_get_semester_context(container.file_adapter),
    "list_personas": lambda a: context.handle_list_personas(container.file_adapter),
    "get_persona": lambda a: context.handle_get_persona(
        container.file_adapter, persona_id=a["persona_id"]
    ),
    "search_domain_knowledge": lambda a: context.handle_search_domain_knowledge(
        container.file_adapter,
        query=a["query"],
        limit=a.get("limit", 5),
    ),
    "list_domain_topics": lambda a: context.handle_list_domain_topics(container.file_adapter),
    # === Research Feature Tools ===
    "set_session_metadata": lambda a: research.handle_set_session_metadata(
        session=get_current_session(),
        team_id=a.get("team_id"),
        role=a.get("role"),
        discipline=a.get("discipline"),
    ),
    "request_more_detail": lambda a: research.handle_request_more_detail(
        session=get_current_session(),
        guardrails_service=container.guardrails_service,
        dispatch_fn=_dispatch_tool,
    ),
    "configure_guardrails": lambda a: research.handle_configure_guardrails(
        guardrails_service=container.guardrails_service,
        team_id=a["team_id"],
        enabled=a.get("enabled"),
        mode=a.get("mode"),
    ),
    "get_guardrails_status": lambda a: research.handle_get_guardrails_status(
        guardrails_service=container.guardrails_service,
        session=get_current_session(),
    ),
    "get_feature_status": lambda a: research.handle_get_feature_status(),
    "export_query_logs": lambda a: research.handle_export_query_logs(
        adapter=container.research_data_adapter,
        output_path=a.get("output_path"),
        start_date=a.get("start_date"),
        end_date=a.get("end_date"),
        team_id=a.get("team_id"),
    ),
    # === Knowledge Capture Tools ===
    "capture_decision": lambda a: knowledge.handle_capture_decision(
        adapter=container.research_data_adapter,
        session=get_current_session(),
        title=a["title"],
        context=a["context"],
        decision=a["decision"],
        rationale=a["rationale"],
        alternatives=a.get("alternatives"),
        consequences=a.get("consequences"),
        related_issues=a.get("related_issues"),
        related_files=a.get("related_files"),
        tags=a.get("tags"),
        discipline_notes=a.get("discipline_notes"),
    ),
    "capture_lesson": lambda a: knowledge.handle_capture_lesson(
        adapter=container.research_data_adapter,
        session=get_current_session(),
        sprint=a["sprint"],
        category=a["category"],
        description=a["description"],
        related_decisions=a.get("related_decisions"),
    ),
    "search_knowledge": lambda a: knowledge.handle_search_knowledge(
        adapter=container.research_data_adapter,
        query=a["query"],
        type=a.get("type", "all"),
        limit=a.get("limit", 5),
    ),
    "list_decisions": lambda a: knowledge.handle_list_decisions(
        adapter=container.research_data_adapter,
        status=a.get("status"),
        tags=a.get("tags"),
        limit=a.get("limit", 10),
    ),
    "list_learnings": lambda a: knowledge.handle_list_learnings(
        adapter=container.research_data_adapter,
        sprint=a.get("sprint"),
        category=a.get("category"),
        limit=a.get("limit", 20),
    ),
    "generate_handover_summary": lambda a: knowledge.handle_generate_handover_summary(
        adapter=container.research_data_adapter,
        semester=a["semester"],
        additional_notes=a.get("additional_notes"),
    ),
    "get_handover": lambda a: knowledge.handle_get_handover(
        adapter=container.research_data_adapter,
        semester=a["semester"],
    ),
    "review_handover": lambda a: knowledge.handle_review_handover(
        adapter=container.research_data_adapter,
        package_id=a["package_id"],
        approved=a["approved"],
        notes=a.get("notes"),
    ),
    # === Resilience Testing Tools ===
    "report_error_found": lambda a: resilience.handle_report_error_found(
        service=container.resilience_service,
        session=get_current_session(),
        tool_name=a["tool_name"],
        error_description=a["error_description"],
        proposed_fix=a.get("proposed_fix"),
    ),
    "configure_resilience_test": lambda a: resilience.handle_configure_resilience_test(
        service=container.resilience_service,
        team_id=a["team_id"],
        mode=a.get("mode"),
        enabled=a.get("enabled"),
    ),
    "get_resilience_status": lambda a: resilience.handle_get_resilience_status(
        service=container.resilience_service,
        session=get_current_session(),
    ),
    "get_resilience_metrics": lambda a: resilience.handle_get_resilience_metrics(
        service=container.resilience_service,
        session_id=a.get("session_id"),
    ),
    # === Cross-Disciplinary Framing Tools ===
    "explain_for_discipline": lambda a: discipline.handle_explain_for_discipline(
        service=container.multiframe_service,
        session=get_current_session(),
        target_discipline=a["target_discipline"],
        concept=a.get("concept"),
    ),
    "compare_perspectives": lambda a: discipline.handle_compare_perspectives(
        service=container.multiframe_service,
        topic=a["topic"],
    ),
    "translate_term": lambda a: discipline.handle_translate_term(
        service=container.multiframe_service,
        term=a["term"],
        target_discipline=a.get("target_discipline"),
    ),
    "get_discipline_profile": lambda a: discipline.handle_get_discipline_profile(
        service=container.multiframe_service,
        discipline=a["discipline"],
    ),
    "list_disciplines": lambda a: discipline.handle_list_disciplines(
        service=container.multiframe_service,
    ),
    # === GitHub Projects V2 Tools ===
    "list_github_projects": lambda a: projects.handle_list_github_projects(
        adapter=container.github_projects_adapter,
        limit=a.get("limit", 20),
    ),
    "get_github_project": lambda a: projects.handle_get_github_project(
        adapter=container.github_projects_adapter,
        project_number=a["project_number"],
    ),
    "list_project_items": lambda a: projects.handle_list_project_items(
        adapter=container.github_projects_adapter,
        project_number=a["project_number"],
        limit=a.get("limit", 50),
        status_filter=a.get("status_filter"),
    ),
    "check_github_projects_access": lambda a: projects.handle_check_github_projects_access(
        adapter=container.github_projects_adapter,
    ),
}


async def _run_handler(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Run a tool's handler directly, without middleware."""
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    return await handler(arguments)


async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls through the research middleware chain."""
    ctx = create_context(name, arguments)
    return await container.middleware_chain.execute(ctx, _run_handler)


async def _dispatch_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch a tool call to its handler.

    This is used by request_more_detail to re-run the previous query; it goes
    through the middleware so guardrails apply the newly advanced tier.
    """
    return await call_tool(name, arguments)


# === MCP Protocol Handlers ===


async def _on_list_tools(
    ctx: ServerRequestContext[SessionState], params: PaginatedRequestParams | None
) -> ListToolsResult:
    return ListToolsResult(tools=await list_tools())


@asynccontextmanager
async def _connection_session(_: Server[SessionState]) -> AsyncIterator[SessionState]:
    """Research session state for one client connection.

    The server enters its lifespan once per connection; each request runs in its
    own context, so the session is carried here rather than in a contextvar.
    """
    yield SessionState()


async def _on_call_tool(
    ctx: ServerRequestContext[SessionState], params: CallToolRequestParams
) -> CallToolResult:
    set_current_session(ctx.lifespan_context)
    try:
        content: list[ContentBlock] = [*await call_tool(params.name, params.arguments or {})]
    except Exception as e:
        # Report tool failures to the client as an error result, not a protocol error
        logger.exception("Tool %s failed", params.name)
        return CallToolResult(content=[TextContent(type="text", text=str(e))], is_error=True)
    return CallToolResult(content=content)


server: Server[SessionState] = Server(
    "giraf-mcp",
    lifespan=_connection_session,
    on_list_tools=_on_list_tools,
    on_call_tool=_on_call_tool,
)


# === Entry Point ===


async def run_stdio_server() -> None:
    """Run the MCP server with stdio transport (for Claude Desktop)."""
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await container.aclose()


async def run_extraction() -> None:
    """Run document extraction and exit (no server).
    
    Use this to convert PDFs to Markdown artifacts:
        giraf-mcp --extract
    """
    import logging
    
    # Configure logging to stdout for CLI usage
    logging.basicConfig(level=logging.INFO)

    print("Extracting documents...")
    print(f"Source: {container.extraction_service.documents_dir}")
    print(f"Target: {container.extraction_service.extracted_dir}")

    try:
        result = await container.extraction_service.extract_all()
        
        print("\nExtraction complete:")
        print(f"  Files processed: {result.files_processed}")
        print(f"  Files skipped (unchanged): {result.files_skipped}")
        print(f"  Files failed: {result.files_failed}")
        
        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors:
                print(f"  - {error}")
                
    except Exception as e:
        print(f"Error during extraction: {e}")
        raise


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def require_bearer_token(app: Any, token: str) -> Any:
    """Wrap an ASGI app so every request except /health needs `Authorization: Bearer <token>`."""
    from starlette.responses import JSONResponse

    expected = f"Bearer {token}".encode()

    async def guarded(scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http" and scope["path"] != "/health":
            supplied = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(supplied, expected):
                response = JSONResponse({"error": "unauthorized"}, status_code=401)
                await response(scope, receive, send)
                return
        await app(scope, receive, send)

    return guarded


def run_http_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the MCP server with HTTP/SSE transport (for remote access).

    Binding to anything other than loopback requires GIRAF_MCP_TOKEN, since
    the tools can write files and read the knowledge base.

    Args:
        host: Host to bind to. Use "0.0.0.0" for all interfaces.
        port: Port to listen on.
    """
    token = os.environ.get("GIRAF_MCP_TOKEN")
    if not token and host not in LOOPBACK_HOSTS:
        raise SystemExit(
            f"Refusing to serve on {host} without authentication: set GIRAF_MCP_TOKEN, "
            "or bind to 127.0.0.1"
        )

    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Mount, Route

    # Create SSE transport
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Any) -> Response:
        """Handle SSE connection."""
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )
        # The SSE stream already responded; Starlette still needs a Response object
        return Response()

    async def health_check(request: Any) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({"status": "ok", "server": "giraf-mcp"})

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        """Lifespan handler for startup/shutdown."""

        # Startup
        logger.info(f"Starting GIRAF MCP server on http://{host}:{port}")
        logger.info(f"SSE endpoint: http://{host}:{port}/sse")
        logger.info(f"Messages endpoint: http://{host}:{port}/messages/")
        yield
        # Shutdown
        logger.info("Shutting down GIRAF MCP server")
        await container.aclose()

    # Create Starlette app
    app = Starlette(
        debug=False,
        routes=[
            Route("/health", health_check),
            Route("/sse", handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        lifespan=lifespan,
    )

    # Run with uvicorn
    asgi_app = require_bearer_token(app, token) if token else app
    uvicorn.run(asgi_app, host=host, port=port, log_level="info")


def main() -> None:
    """Entry point for the MCP server.

    Usage:
        giraf-mcp              # Run with stdio (default, for Claude Desktop)
        giraf-mcp --extract    # Extract Markdown from PDFs and exit
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
        "--extract",
        action="store_true",
        help="Extract Markdown from PDFs and exit (no server)",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run with HTTP/SSE transport instead of stdio",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("GIRAF_MCP_HOST", "127.0.0.1"),
        help="Host to bind to (default: 127.0.0.1; other hosts require GIRAF_MCP_TOKEN)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("GIRAF_MCP_PORT", "8000")),
        help="Port for HTTP server (default: 8000)",
    )

    args = parser.parse_args()

    if args.extract:
        asyncio.run(run_extraction())
    elif args.http:
        run_http_server(host=args.host, port=args.port)
    else:
        asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
