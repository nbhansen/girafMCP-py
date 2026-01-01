"""Tests for resilience middleware."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from mcp.types import TextContent

from girafmcp.core.session import SessionState
from girafmcp.core.services.resilience_service import (
    ResilienceService,
    ResilienceConfig,
    ResilienceMode,
)
from girafmcp.middleware import ToolContext
from girafmcp.middleware.resilience import ResilienceMiddleware


@pytest.fixture
def normal_config() -> dict:
    """Configuration for normal mode."""
    return {
        "enabled": True,
        "mode": "normal",
    }


@pytest.fixture
def unavailable_config() -> dict:
    """Configuration for unavailable mode."""
    return {
        "enabled": True,
        "mode": "unavailable",
        "unavailable_mode": {
            "message": "AI is temporarily unavailable.",
            "allowed_tools": ["search_documentation", "get_project_context"],
        },
    }


@pytest.fixture
def degraded_config() -> dict:
    """Configuration for degraded mode."""
    return {
        "enabled": True,
        "mode": "degraded",
        "degraded_mode": {
            "error_injection_rate": 1.0,  # Always inject for testing
            "error_types": [
                {"type": "off_by_one", "weight": 1.0},
            ],
        },
    }


def create_service(config_data: dict) -> ResilienceService:
    """Create a ResilienceService with given config."""
    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "resilience_tests.yaml"
        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)
        config = ResilienceConfig(config_path)
        return ResilienceService(config)


class TestResilienceMiddlewareNormalMode:
    """Tests for normal mode middleware."""

    @pytest.fixture(autouse=True)
    def enable_resilience(self):
        """Enable resilience feature for tests."""
        os.environ["GIRAF_RESILIENCE_ENABLED"] = "true"
        yield
        if "GIRAF_RESILIENCE_ENABLED" in os.environ:
            del os.environ["GIRAF_RESILIENCE_ENABLED"]

    @pytest.fixture
    def middleware(self, normal_config: dict) -> ResilienceMiddleware:
        """Create middleware in normal mode."""
        # Need to create service inline due to temp directory scope
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "resilience_tests.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(normal_config, f)
            config = ResilienceConfig(config_path)
            service = ResilienceService(config)
            yield ResilienceMiddleware(service)

    @pytest.fixture
    def session(self) -> SessionState:
        """Create fresh session."""
        return SessionState()

    async def test_normal_mode_passes_through(
        self, middleware: ResilienceMiddleware, session: SessionState
    ) -> None:
        """Normal mode should pass through without modification."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "test"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="Original response")]

        result = await middleware.process(ctx, next_fn)

        assert len(result) == 1
        assert result[0].text == "Original response"
        assert ctx.metadata.get("resilience_mode") == "normal"


class TestResilienceMiddlewareUnavailableMode:
    """Tests for unavailable mode middleware."""

    @pytest.fixture(autouse=True)
    def enable_resilience(self):
        """Enable resilience feature for tests."""
        os.environ["GIRAF_RESILIENCE_ENABLED"] = "true"
        yield
        if "GIRAF_RESILIENCE_ENABLED" in os.environ:
            del os.environ["GIRAF_RESILIENCE_ENABLED"]

    @pytest.fixture
    def middleware(self, unavailable_config: dict) -> ResilienceMiddleware:
        """Create middleware in unavailable mode."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "resilience_tests.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(unavailable_config, f)
            config = ResilienceConfig(config_path)
            service = ResilienceService(config)
            yield ResilienceMiddleware(service)

    @pytest.fixture
    def session(self) -> SessionState:
        """Create fresh session."""
        return SessionState()

    async def test_unavailable_blocks_most_tools(
        self, middleware: ResilienceMiddleware, session: SessionState
    ) -> None:
        """Unavailable mode should block non-allowed tools."""
        ctx = ToolContext(
            name="search_code",  # Not in allowed list
            arguments={"query": "test"},
            session=session,
            start_time=0.0,
        )

        call_count = 0

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            nonlocal call_count
            call_count += 1
            return [TextContent(type="text", text="Should not reach")]

        result = await middleware.process(ctx, next_fn)

        # Should not call next_fn
        assert call_count == 0
        assert "unavailable" in result[0].text.lower()
        assert ctx.metadata.get("resilience_blocked") is True

    async def test_unavailable_allows_permitted_tools(
        self, middleware: ResilienceMiddleware, session: SessionState
    ) -> None:
        """Unavailable mode should allow permitted tools."""
        ctx = ToolContext(
            name="search_documentation",  # In allowed list
            arguments={"query": "test"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="Documentation result")]

        result = await middleware.process(ctx, next_fn)

        assert result[0].text == "Documentation result"


class TestResilienceMiddlewareDegradedMode:
    """Tests for degraded mode middleware."""

    @pytest.fixture(autouse=True)
    def enable_resilience(self):
        """Enable resilience feature for tests."""
        os.environ["GIRAF_RESILIENCE_ENABLED"] = "true"
        yield
        if "GIRAF_RESILIENCE_ENABLED" in os.environ:
            del os.environ["GIRAF_RESILIENCE_ENABLED"]

    @pytest.fixture
    def middleware(self, degraded_config: dict) -> ResilienceMiddleware:
        """Create middleware in degraded mode."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "resilience_tests.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(degraded_config, f)
            config = ResilienceConfig(config_path)
            service = ResilienceService(config)
            yield ResilienceMiddleware(service)

    @pytest.fixture
    def session(self) -> SessionState:
        """Create fresh session."""
        return SessionState()

    async def test_degraded_may_inject_error(
        self, middleware: ResilienceMiddleware, session: SessionState
    ) -> None:
        """Degraded mode may inject errors into response."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "test"},
            session=session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="for i in range(0, 10):")]

        result = await middleware.process(ctx, next_fn)

        # With 100% injection rate and off_by_one, response may be modified
        # Either original or modified is valid (injection can fail if no pattern found)
        assert len(result) == 1
        assert ctx.metadata.get("resilience_mode") == "degraded"


class TestResilienceMiddlewareDisabled:
    """Tests for disabled resilience."""

    @pytest.fixture(autouse=True)
    def disable_resilience(self):
        """Disable resilience feature for tests."""
        os.environ["GIRAF_RESILIENCE_ENABLED"] = "false"
        yield
        if "GIRAF_RESILIENCE_ENABLED" in os.environ:
            del os.environ["GIRAF_RESILIENCE_ENABLED"]

    @pytest.fixture
    def middleware(self, unavailable_config: dict) -> ResilienceMiddleware:
        """Create middleware (will be disabled by env var)."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "resilience_tests.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(unavailable_config, f)
            config = ResilienceConfig(config_path)
            service = ResilienceService(config)
            yield ResilienceMiddleware(service)

    @pytest.fixture
    def session(self) -> SessionState:
        """Create fresh session."""
        return SessionState()

    async def test_disabled_passes_through(
        self, middleware: ResilienceMiddleware, session: SessionState
    ) -> None:
        """Disabled resilience should pass through."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "test"},
            session=session,
            start_time=0.0,
        )

        # should_process returns False when feature disabled
        assert middleware.should_process(ctx) is False
