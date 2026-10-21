"""Tests for guardrails middleware."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from mcp.types import TextContent

from girafmcp.core.session import SessionState
from girafmcp.core.services.guardrails_service import (
    GuardrailsService,
    GuardrailsConfig,
)
from girafmcp.middleware import ToolContext
from girafmcp.middleware.guardrails import GuardrailsMiddleware


@pytest.fixture
def tiered_config() -> dict:
    """Configuration for tiered mode."""
    return {
        "enabled": True,
        "mode": "tiered",
        "guarded_tools": ["search_code", "get_file"],
        "exempt_tools": ["list_repositories"],
        "tiers": {
            1: {"name": "hint", "description": "Conceptual hint", "prompt_suffix": "\n---\n**Tier 1: Hint**"},
            2: {"name": "guidance", "description": "Guidance", "prompt_suffix": "\n---\n**Tier 2: Guidance**"},
            3: {"name": "example", "description": "Example", "prompt_suffix": "\n---\n**Tier 3: Example**"},
            4: {"name": "solution", "description": "Full", "prompt_suffix": None},
        },
    }


@pytest.fixture
def prompt_config() -> dict:
    """Configuration for prompt mode."""
    return {
        "enabled": True,
        "mode": "prompt",
        "guarded_tools": ["search_code"],
        "attempt_first": {
            "prompt": "What have you tried so far?",
            "bypass_indicators": ["i tried", "error"],
        },
    }


@pytest.fixture
def tiered_service(tiered_config: dict) -> GuardrailsService:
    """Create service in tiered mode."""
    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "guardrails.yaml"
        with open(config_path, "w") as f:
            yaml.safe_dump(tiered_config, f)
        config = GuardrailsConfig(config_path)
        yield GuardrailsService(config)


@pytest.fixture
def prompt_service(prompt_config: dict) -> GuardrailsService:
    """Create service in prompt mode."""
    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "guardrails.yaml"
        with open(config_path, "w") as f:
            yaml.safe_dump(prompt_config, f)
        config = GuardrailsConfig(config_path)
        yield GuardrailsService(config)


class TestGuardrailsMiddlewareTiered:
    """Tests for tiered mode middleware."""

    @pytest.fixture(autouse=True)
    def enable_guardrails(self):
        """Enable guardrails feature for tests."""
        os.environ["GIRAF_GUARDRAILS_ENABLED"] = "true"
        yield
        if "GIRAF_GUARDRAILS_ENABLED" in os.environ:
            del os.environ["GIRAF_GUARDRAILS_ENABLED"]

    @pytest.fixture
    def middleware(self, tiered_service: GuardrailsService) -> GuardrailsMiddleware:
        """Create middleware with tiered service."""
        return GuardrailsMiddleware(tiered_service)

    @pytest.fixture
    def session(self) -> SessionState:
        """Create fresh session."""
        return SessionState()

    async def test_exempt_tool_passes_through(
        self, middleware: GuardrailsMiddleware, session: SessionState
    ) -> None:
        """Exempt tools should pass through without modification."""
        ctx = ToolContext(
            name="list_repositories",
            arguments={},
            session=session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="Original response")]

        result = await middleware.process(ctx, next_fn)

        assert len(result) == 1
        assert result[0].text == "Original response"

    async def test_tier1_appends_suffix(
        self, middleware: GuardrailsMiddleware, session: SessionState
    ) -> None:
        """Tier 1 should append tier suffix to response."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "find something"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="Search results...")]

        result = await middleware.process(ctx, next_fn)

        assert len(result) == 1
        assert "Search results..." in result[0].text
        assert "Tier 1" in result[0].text

    async def test_tier4_no_suffix(
        self, middleware: GuardrailsMiddleware, session: SessionState
    ) -> None:
        """Tier 4 should not append suffix (full solution)."""
        session.guardrail_tier = 4

        ctx = ToolContext(
            name="search_code",
            arguments={"query": "find something"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="Full search results")]

        result = await middleware.process(ctx, next_fn)

        assert len(result) == 1
        assert result[0].text == "Full search results"
        assert "Tier" not in result[0].text

    async def test_records_last_query(
        self, middleware: GuardrailsMiddleware, session: SessionState
    ) -> None:
        """Middleware should record last query for request_more_detail."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "find something"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="Results")]

        await middleware.process(ctx, next_fn)

        assert session.last_tool == "search_code"
        assert session.last_arguments == {"query": "find something"}

    async def test_sets_metadata_in_context(
        self, middleware: GuardrailsMiddleware, session: SessionState
    ) -> None:
        """Middleware should set guardrail metadata in context."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "find something"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="Results")]

        await middleware.process(ctx, next_fn)

        assert ctx.metadata.get("guardrail_mode") == "tiered"
        assert ctx.metadata.get("guardrail_tier") == 1


class TestGuardrailsMiddlewarePrompt:
    """Tests for prompt mode middleware."""

    @pytest.fixture(autouse=True)
    def enable_guardrails(self):
        """Enable guardrails feature for tests."""
        os.environ["GIRAF_GUARDRAILS_ENABLED"] = "true"
        yield
        if "GIRAF_GUARDRAILS_ENABLED" in os.environ:
            del os.environ["GIRAF_GUARDRAILS_ENABLED"]

    @pytest.fixture
    def middleware(self, prompt_service: GuardrailsService) -> GuardrailsMiddleware:
        """Create middleware with prompt service."""
        return GuardrailsMiddleware(prompt_service)

    @pytest.fixture
    def session(self) -> SessionState:
        """Create fresh session."""
        return SessionState()

    async def test_first_request_gets_prompt(
        self, middleware: GuardrailsMiddleware, session: SessionState
    ) -> None:
        """First request should get attempt-first prompt."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "how do I do X?"},
            session=session,
            start_time=0.0,
        )

        call_count = 0

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            nonlocal call_count
            call_count += 1
            return [TextContent(type="text", text="Should not reach here")]

        result = await middleware.process(ctx, next_fn)

        # Should not call next_fn
        assert call_count == 0
        assert "What have you tried" in result[0].text
        assert session.guardrail_prompted is True

    async def test_bypass_with_indicator(
        self, middleware: GuardrailsMiddleware, session: SessionState
    ) -> None:
        """Query with bypass indicator should pass through."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "I tried X but got an error"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="Search results")]

        result = await middleware.process(ctx, next_fn)

        assert result[0].text == "Search results"

    async def test_after_prompt_passes_through(
        self, middleware: GuardrailsMiddleware, session: SessionState
    ) -> None:
        """After prompting, should pass through."""
        session.guardrail_prompted = True

        ctx = ToolContext(
            name="search_code",
            arguments={"query": "how do I do X?"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="Search results")]

        result = await middleware.process(ctx, next_fn)

        assert result[0].text == "Search results"


class TestGuardrailsMiddlewareDisabled:
    """Tests for disabled guardrails."""

    @pytest.fixture(autouse=True)
    def disable_guardrails(self):
        """Disable guardrails feature for tests."""
        os.environ["GIRAF_GUARDRAILS_ENABLED"] = "false"
        yield
        if "GIRAF_GUARDRAILS_ENABLED" in os.environ:
            del os.environ["GIRAF_GUARDRAILS_ENABLED"]

    @pytest.fixture
    def middleware(self, tiered_service: GuardrailsService) -> GuardrailsMiddleware:
        """Create middleware with tiered service."""
        return GuardrailsMiddleware(tiered_service)

    @pytest.fixture
    def session(self) -> SessionState:
        """Create fresh session."""
        return SessionState()

    async def test_disabled_passes_through(
        self, middleware: GuardrailsMiddleware, session: SessionState
    ) -> None:
        """Disabled guardrails should pass through."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "find something"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="Original response")]

        # should_process returns False when feature disabled
        assert middleware.should_process(ctx) is False
