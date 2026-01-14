"""Logging middleware for research query tracking.

Records all tool invocations to SQLite for research analysis.
Fire-and-forget - errors don't propagate to prevent impacting tool calls.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from mcp.types import TextContent

from girafmcp.adapters.research_data_adapter import ResearchDataAdapter
from girafmcp.core.services.query_classifier import (
    classify_query_type,
    detect_meta_skills,
    extract_result_count,
)
from girafmcp.core.types import QueryLog
from girafmcp.middleware.base import Middleware, NextMiddleware, ToolContext

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class LoggingMiddleware(Middleware):
    """Middleware that logs all tool invocations for research analysis.

    Records:
    - Tool name and arguments (sanitized)
    - Query classification and meta-skill indicators
    - Response metrics (length, result count, duration)
    - Session metadata (team, role, discipline)

    Logging is fire-and-forget - errors are caught and logged
    but don't propagate to avoid impacting tool performance.
    """

    # Tools to exclude from logging (internal/admin tools)
    EXCLUDED_TOOLS = {
        "set_session_metadata",
        "export_query_logs",
        "get_feature_status",
        "configure_guardrails",
        "configure_resilience_test",
        "reload_configuration",
    }

    # Fields to truncate in arguments for privacy/size
    TRUNCATE_FIELDS = {"content", "code", "body", "text"}
    MAX_FIELD_LENGTH = 500

    def __init__(self, adapter: ResearchDataAdapter):
        """Initialize the logging middleware.

        Args:
            adapter: ResearchDataAdapter for storing logs
        """
        self.adapter = adapter

    @property
    def name(self) -> str:
        return "LoggingMiddleware"

    def should_process(self, ctx: ToolContext) -> bool:
        """Skip logging for excluded tools."""
        return ctx.name not in self.EXCLUDED_TOOLS

    async def process(
        self,
        ctx: ToolContext,
        next_middleware: NextMiddleware,
    ) -> list[TextContent]:
        """Process tool call and log the invocation.

        Args:
            ctx: Tool context with request data
            next_middleware: Next middleware in chain

        Returns:
            Tool result (unmodified)
        """
        start_time = time.monotonic()
        error_msg: str | None = None
        result: list[TextContent] = []

        try:
            # Call next middleware/dispatch
            result = await next_middleware(ctx)
            return result

        except Exception as e:
            error_msg = str(e)
            raise

        finally:
            # Log asynchronously (fire-and-forget)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            asyncio.create_task(
                self._log_query(ctx, result, duration_ms, error_msg)
            )

    async def _log_query(
        self,
        ctx: ToolContext,
        result: list[TextContent],
        duration_ms: int,
        error: str | None,
    ) -> None:
        """Create and store a query log entry.

        This runs asynchronously after the response is returned.
        Errors are logged but don't propagate.
        """
        try:
            # Extract query text and classify
            query_text = self._extract_query_text(ctx)
            query_type = classify_query_type(ctx.name, ctx.arguments)
            meta_skills = detect_meta_skills(query_text)

            # Calculate response metrics
            response_text = result[0].text if result else ""
            response_length = len(response_text)
            result_count = extract_result_count(response_text)

            # Create log entry
            log = QueryLog(
                id=str(uuid.uuid4()),
                timestamp=_utcnow(),
                session_id=ctx.session.id,
                team_id=ctx.session.team_id,
                role=ctx.session.role,
                discipline=ctx.session.discipline,
                tool_name=ctx.name,
                arguments=self._sanitize_arguments(ctx.arguments),
                query_text=query_text,
                response_length=response_length,
                result_count=result_count,
                duration_ms=duration_ms,
                error=error,
                query_type=query_type,
                meta_skills=meta_skills,
                guardrail_mode=ctx.metadata.get("guardrail_mode"),
                guardrail_tier=ctx.metadata.get("guardrail_tier"),
            )

            # Store log
            await self.adapter.log_query(log)

        except Exception as e:
            logger.error(f"Failed to log query: {e}", exc_info=True)

    def _extract_query_text(self, ctx: ToolContext) -> str | None:
        """Extract natural language query from tool arguments."""
        args = ctx.arguments

        # Direct query parameter
        if "query" in args:
            return str(args["query"])

        # For file retrieval
        if ctx.name == "get_file" and "path" in args:
            repo = args.get("repo", "")
            path = args.get("path", "")
            return f"get file {repo}/{path}"

        # For persona lookup
        if ctx.name == "get_persona" and "persona_id" in args:
            return f"get persona {args['persona_id']}"

        return None

    def _sanitize_arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Remove or truncate sensitive/large data from arguments.

        Args:
            arguments: Original tool arguments

        Returns:
            Sanitized copy safe for logging
        """
        sanitized = {}

        for key, value in arguments.items():
            if key in self.TRUNCATE_FIELDS and isinstance(value, str):
                if len(value) > self.MAX_FIELD_LENGTH:
                    sanitized[key] = value[: self.MAX_FIELD_LENGTH] + "...[truncated]"
                else:
                    sanitized[key] = value
            else:
                sanitized[key] = value

        return sanitized
