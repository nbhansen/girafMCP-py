"""Tests for LoggingMiddleware."""

import asyncio
import pytest
from pathlib import Path
import tempfile
import os

from mcp.types import TextContent

from girafmcp.adapters.research_data_adapter import ResearchDataAdapter
from girafmcp.core.session import SessionState, reset_session
from girafmcp.middleware import ToolContext, create_context
from girafmcp.middleware.logging import LoggingMiddleware


@pytest.fixture
def temp_db() -> Path:
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        os.unlink(path)


@pytest.fixture
def adapter(temp_db: Path) -> ResearchDataAdapter:
    """Create an adapter with a temporary database."""
    return ResearchDataAdapter(temp_db)


@pytest.fixture
def middleware(adapter: ResearchDataAdapter) -> LoggingMiddleware:
    """Create logging middleware."""
    return LoggingMiddleware(adapter)


@pytest.fixture
def session() -> SessionState:
    """Create a test session."""
    session = reset_session()
    session.team_id = "team_a"
    session.role = "dev"
    session.discipline = "cs"
    return session


async def mock_dispatch(name: str, args: dict) -> list[TextContent]:
    """Mock tool dispatch that returns a simple result."""
    return [TextContent(type="text", text=f"Result for {name}")]


async def failing_dispatch(name: str, args: dict) -> list[TextContent]:
    """Mock dispatch that raises an error."""
    raise ValueError("Tool failed")


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    async def test_logs_successful_call(
        self,
        middleware: LoggingMiddleware,
        adapter: ResearchDataAdapter,
        session: SessionState,
    ) -> None:
        """Should log successful tool calls."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "find function"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(c: ToolContext) -> list[TextContent]:
            return await mock_dispatch(c.name, c.arguments)

        result = await middleware.process(ctx, next_fn)

        # Wait for async logging
        await asyncio.sleep(0.1)

        # Verify log was created
        logs = await adapter.get_session_queries(session.id)
        assert len(logs) == 1
        assert logs[0].tool_name == "search_code"
        assert logs[0].team_id == "team_a"
        assert logs[0].error is None

    async def test_logs_failed_call(
        self,
        middleware: LoggingMiddleware,
        adapter: ResearchDataAdapter,
        session: SessionState,
    ) -> None:
        """Should log failed tool calls with error."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "test"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(c: ToolContext) -> list[TextContent]:
            return await failing_dispatch(c.name, c.arguments)

        with pytest.raises(ValueError):
            await middleware.process(ctx, next_fn)

        # Wait for async logging
        await asyncio.sleep(0.1)

        logs = await adapter.get_session_queries(session.id)
        assert len(logs) == 1
        assert logs[0].error == "Tool failed"

    async def test_classifies_query_type(
        self,
        middleware: LoggingMiddleware,
        adapter: ResearchDataAdapter,
        session: SessionState,
    ) -> None:
        """Should classify query type."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "explain how authentication works"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(c: ToolContext) -> list[TextContent]:
            return await mock_dispatch(c.name, c.arguments)

        await middleware.process(ctx, next_fn)
        await asyncio.sleep(0.1)

        logs = await adapter.get_session_queries(session.id)
        assert logs[0].query_type.value == "explanation"

    async def test_detects_meta_skills(
        self,
        middleware: LoggingMiddleware,
        adapter: ResearchDataAdapter,
        session: SessionState,
    ) -> None:
        """Should detect meta-skill indicators."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "I tried running tests but they fail"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(c: ToolContext) -> list[TextContent]:
            return await mock_dispatch(c.name, c.arguments)

        await middleware.process(ctx, next_fn)
        await asyncio.sleep(0.1)

        logs = await adapter.get_session_queries(session.id)
        assert logs[0].meta_skills is not None
        assert logs[0].meta_skills.verification_attempted is True

    async def test_excludes_internal_tools(
        self,
        middleware: LoggingMiddleware,
        adapter: ResearchDataAdapter,
        session: SessionState,
    ) -> None:
        """Should not log excluded tools."""
        ctx = ToolContext(
            name="set_session_metadata",
            arguments={"team_id": "test"},
            session=session,
            start_time=0.0,
        )

        # should_process returns False for excluded tools
        assert middleware.should_process(ctx) is False

    async def test_sanitizes_long_arguments(
        self, middleware: LoggingMiddleware
    ) -> None:
        """Should truncate long argument values."""
        long_content = "x" * 1000
        args = {"content": long_content, "query": "test"}

        sanitized = middleware._sanitize_arguments(args)

        assert len(sanitized["content"]) == 500 + len("...[truncated]")
        assert sanitized["query"] == "test"  # Short values unchanged

    async def test_records_duration(
        self,
        middleware: LoggingMiddleware,
        adapter: ResearchDataAdapter,
        session: SessionState,
    ) -> None:
        """Should record call duration."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "test"},
            session=session,
            start_time=0.0,
        )

        async def slow_dispatch(c: ToolContext) -> list[TextContent]:
            await asyncio.sleep(0.05)  # 50ms
            return [TextContent(type="text", text="done")]

        await middleware.process(ctx, slow_dispatch)
        await asyncio.sleep(0.1)

        logs = await adapter.get_session_queries(session.id)
        assert logs[0].duration_ms >= 50

    async def test_extracts_query_text_from_file_request(
        self, middleware: LoggingMiddleware, session: SessionState
    ) -> None:
        """Should extract query text from get_file requests."""
        ctx = ToolContext(
            name="get_file",
            arguments={"repo": "foodplanner", "path": "src/main.dart"},
            session=session,
            start_time=0.0,
        )

        query_text = middleware._extract_query_text(ctx)
        assert query_text == "get file foodplanner/src/main.dart"
