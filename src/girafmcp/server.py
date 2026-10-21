"""GIRAF MCP Server - Knowledge assistant for the GIRAF project.

This MCP server provides tools for searching documentation, code,
and domain knowledge to help students working on the GIRAF project.
"""

import asyncio
import os
from collections.abc import AsyncGenerator
from typing import Any, cast

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from girafmcp.core.container import DependencyContainer
from girafmcp.core.session import get_current_session
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

# Create server instance
server = Server("giraf-mcp")

# Initialize dependency container
container = DependencyContainer()


# === Tool Definitions ===


@server.list_tools()  # type: ignore
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


@server.call_tool()  # type: ignore
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    # === GitHub Tools ===
    if name == "list_repositories":
        return await github.handle_list_repositories(container.github_adapter)

    elif name == "get_file":
        return await github.handle_get_file(
            container.github_adapter,
            repo=arguments["repo"],
            path=arguments["path"],
            ref=arguments.get("ref"),
        )

    elif name == "search_code":
        return await github.handle_search_code(
            container.github_adapter,
            query=arguments["query"],
            repo=arguments.get("repo"),
        )

    elif name == "get_permalink":
        return await github.handle_get_permalink(
            container.github_adapter,
            repo=arguments["repo"],
            path=arguments["path"],
            line=arguments.get("line"),
            end_line=arguments.get("end_line"),
        )
    
    elif name == "search_wiki":
        return await github.handle_search_wiki(
            container.github_adapter,
            query=arguments["query"],
            limit=arguments.get("limit", 5),
        )

    elif name == "list_wiki_pages":
        return await github.handle_list_wiki_pages(container.github_adapter)

    # === Search Tools ===
    elif name == "search_documentation":
        return await search.handle_search_documentation(
            container.keyword_search_adapter,
            query=arguments["query"],
            limit=arguments.get("limit", 5),
        )

    elif name == "search_static_documents":
        return await search.handle_search_static_documents(
            container.keyword_search_adapter,
            query=arguments["query"],
            limit=arguments.get("limit", 5),
            tags=arguments.get("tags"),
        )

    elif name == "list_static_documents":
        return await search.handle_list_static_documents(container.keyword_search_adapter)

    # === Context Tools ===
    elif name == "get_semester_context":
        return await context.handle_get_semester_context(container.file_adapter)

    elif name == "list_personas":
        return await context.handle_list_personas(container.file_adapter)

    elif name == "get_persona":
        return await context.handle_get_persona(
            container.file_adapter, persona_id=arguments["persona_id"]
        )

    elif name == "search_domain_knowledge":
        return await context.handle_search_domain_knowledge(
            container.file_adapter,
            query=arguments["query"],
            limit=arguments.get("limit", 5),
        )

    elif name == "list_domain_topics":
        return await context.handle_list_domain_topics(container.file_adapter)

    # === Research Feature Tools ===
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
            guardrails_service=container.guardrails_service,
            dispatch_fn=_dispatch_tool,
        )

    elif name == "configure_guardrails":
        return await research.handle_configure_guardrails(
            guardrails_service=container.guardrails_service,
            team_id=arguments["team_id"],
            enabled=arguments.get("enabled"),
            mode=arguments.get("mode"),
        )

    elif name == "get_guardrails_status":
        return await research.handle_get_guardrails_status(
            guardrails_service=container.guardrails_service,
            session=get_current_session(),
        )

    elif name == "get_feature_status":
        return await research.handle_get_feature_status()
        
    elif name == "export_query_logs":
        return await research.handle_export_query_logs(
            adapter=container.research_data_adapter,
            output_path=arguments.get("output_path"),
            start_date=arguments.get("start_date"),
            end_date=arguments.get("end_date"),
            team_id=arguments.get("team_id"),
        )

    # === Knowledge Capture Tools ===
    elif name == "capture_decision":
        return await knowledge.handle_capture_decision(
            adapter=container.research_data_adapter,
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
            adapter=container.research_data_adapter,
            session=get_current_session(),
            sprint=arguments["sprint"],
            category=arguments["category"],
            description=arguments["description"],
            related_decisions=arguments.get("related_decisions"),
        )

    elif name == "search_knowledge":
        return await knowledge.handle_search_knowledge(
            adapter=container.research_data_adapter,
            query=arguments["query"],
            type=arguments.get("type", "all"),
            limit=arguments.get("limit", 5),
        )

    elif name == "list_decisions":
        return await knowledge.handle_list_decisions(
            adapter=container.research_data_adapter,
            status=arguments.get("status"),
            tags=arguments.get("tags"),
            limit=arguments.get("limit", 10),
        )

    elif name == "list_learnings":
        return await knowledge.handle_list_learnings(
            adapter=container.research_data_adapter,
            sprint=arguments.get("sprint"),
            category=arguments.get("category"),
            limit=arguments.get("limit", 20),
        )

    elif name == "generate_handover_summary":
        return await knowledge.handle_generate_handover_summary(
            adapter=container.research_data_adapter,
            semester=arguments["semester"],
            additional_notes=arguments.get("additional_notes"),
        )

    elif name == "get_handover":
        return await knowledge.handle_get_handover(
            adapter=container.research_data_adapter,
            semester=arguments["semester"],
        )

    elif name == "review_handover":
        return await knowledge.handle_review_handover(
            adapter=container.research_data_adapter,
            package_id=arguments["package_id"],
            approved=arguments["approved"],
            notes=arguments.get("notes"),
        )

    # === Resilience Testing Tools ===
    elif name == "report_error_found":
        return await resilience.handle_report_error_found(
            service=container.resilience_service,
            session=get_current_session(),
            tool_name=arguments["tool_name"],
            error_description=arguments["error_description"],
            proposed_fix=arguments.get("proposed_fix"),
        )

    elif name == "configure_resilience_test":
        return await resilience.handle_configure_resilience_test(
            service=container.resilience_service,
            team_id=arguments["team_id"],
            mode=arguments.get("mode"),
            enabled=arguments.get("enabled"),
        )

    elif name == "get_resilience_status":
        return await resilience.handle_get_resilience_status(
            service=container.resilience_service,
            session=get_current_session(),
        )

    elif name == "get_resilience_metrics":
        return await resilience.handle_get_resilience_metrics(
            service=container.resilience_service,
            session_id=arguments.get("session_id"),
        )

    # === Cross-Disciplinary Framing Tools ===
    elif name == "explain_for_discipline":
        return await discipline.handle_explain_for_discipline(
            service=container.multiframe_service,
            session=get_current_session(),
            target_discipline=arguments["target_discipline"],
            concept=arguments.get("concept"),
        )

    elif name == "compare_perspectives":
        return await discipline.handle_compare_perspectives(
            service=container.multiframe_service,
            topic=arguments["topic"],
        )

    elif name == "translate_term":
        return await discipline.handle_translate_term(
            service=container.multiframe_service,
            term=arguments["term"],
            target_discipline=arguments.get("target_discipline"),
        )

    elif name == "get_discipline_profile":
        return await discipline.handle_get_discipline_profile(
            service=container.multiframe_service,
            discipline=arguments["discipline"],
        )

    elif name == "list_disciplines":
        return await discipline.handle_list_disciplines(
            service=container.multiframe_service,
        )

    # === GitHub Projects V2 Tools ===
    elif name == "list_github_projects":
        return await projects.handle_list_github_projects(
            adapter=container.github_projects_adapter,
            limit=arguments.get("limit", 20),
        )

    elif name == "get_github_project":
        return await projects.handle_get_github_project(
            adapter=container.github_projects_adapter,
            project_number=arguments["project_number"],
        )

    elif name == "list_project_items":
        return await projects.handle_list_project_items(
            adapter=container.github_projects_adapter,
            project_number=arguments["project_number"],
            limit=arguments.get("limit", 50),
            status_filter=arguments.get("status_filter"),
        )

    elif name == "check_github_projects_access":
        return await projects.handle_check_github_projects_access(
            adapter=container.github_projects_adapter,
        )

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _dispatch_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch a tool call to its handler.

    This is used by request_more_detail to re-run the previous query.
    """
    return cast(list[TextContent], await call_tool(name, arguments))


# === Entry Point ===


async def run_stdio_server() -> None:
    """Run the MCP server with stdio transport (for Claude Desktop)."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


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


def run_http_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the MCP server with HTTP/SSE transport (for remote access).

    Args:
        host: Host to bind to. Use "0.0.0.0" for all interfaces.
        port: Port to listen on.
    """
    import logging

    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

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

    if args.extract:
        asyncio.run(run_extraction())
    elif args.http:
        run_http_server(host=args.host, port=args.port)
    else:
        asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
