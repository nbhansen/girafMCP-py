"""Tests that tool calls run through the research middleware chain."""

import pytest

from girafmcp import server
from girafmcp.core.container import DependencyContainer
from girafmcp.core.session import get_current_session
from girafmcp.middleware.discipline import DisciplineMiddleware
from girafmcp.middleware.guardrails import GuardrailsMiddleware
from girafmcp.middleware.logging import LoggingMiddleware
from girafmcp.middleware.resilience import ResilienceMiddleware


@pytest.fixture
async def real_container(tmp_path, monkeypatch):
    monkeypatch.setenv("GIRAF_KNOWLEDGE_DB", str(tmp_path / "knowledge.db"))
    container = DependencyContainer()
    monkeypatch.setattr(server, "container", container)
    yield container
    # Flush log writes before the test's event loop closes
    await container.aclose()


class TestMiddlewareWiring:
    def test_chain_order(self, real_container):
        assert [type(m) for m in real_container.middleware_chain.middlewares] == [
            LoggingMiddleware,
            GuardrailsMiddleware,
            DisciplineMiddleware,
            ResilienceMiddleware,
        ]

    async def test_tool_call_is_logged(self, real_container, monkeypatch):
        monkeypatch.setenv("GIRAF_QUERY_LOGGING_ENABLED", "true")
        await server.call_tool("list_domain_topics", {})

        logging_mw = real_container.middleware_chain.middlewares[0]
        assert isinstance(logging_mw, LoggingMiddleware)
        await logging_mw.drain()

        logs = await real_container.research_data_adapter.get_session_queries(
            get_current_session().id
        )
        assert [log.tool_name for log in logs][-1] == "list_domain_topics"

    async def test_logging_flag_off_skips_logging(self, real_container, monkeypatch):
        monkeypatch.setenv("GIRAF_QUERY_LOGGING_ENABLED", "false")
        await server.call_tool("list_domain_topics", {})

        logging_mw = real_container.middleware_chain.middlewares[0]
        assert isinstance(logging_mw, LoggingMiddleware)
        await logging_mw.drain()

        logs = await real_container.research_data_adapter.get_session_queries(
            get_current_session().id
        )
        assert logs == []


class TestConnectionSession:
    async def test_calls_on_one_connection_share_session(self, real_container):
        from types import SimpleNamespace

        from mcp.types import CallToolRequestParams

        from girafmcp.core.session import SessionState

        session = SessionState()
        ctx = SimpleNamespace(lifespan_context=session)
        params = CallToolRequestParams(
            name="set_session_metadata", arguments={"team_id": "team_a"}
        )
        await server._on_call_tool(ctx, params)  # type: ignore[arg-type]
        await server._on_call_tool(  # type: ignore[arg-type]
            ctx, CallToolRequestParams(name="list_domain_topics", arguments={})
        )
        assert session.team_id == "team_a"
        assert get_current_session() is session
