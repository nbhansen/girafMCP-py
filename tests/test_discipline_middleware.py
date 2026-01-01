"""Tests for discipline middleware."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from mcp.types import TextContent

from girafmcp.core.session import SessionState
from girafmcp.core.services.multiframe_service import (
    MultiFrameService,
    MultiFrameConfig,
)
from girafmcp.middleware import ToolContext
from girafmcp.middleware.discipline import DisciplineMiddleware


@pytest.fixture
def sample_config() -> dict:
    """Sample configuration for testing."""
    return {
        "enabled": True,
        "disciplines": {
            "cs": {
                "name": "Computer Science",
                "explanation_style": "technical_precise",
                "default_code_depth": "detailed",
                "translation_hints": {},
            },
            "id": {
                "name": "Interaction Design",
                "explanation_style": "conceptual_visual",
                "default_code_depth": "high_level",
                "translation_hints": {
                    "API": "The language apps use to talk to servers",
                    "callback": "Code that runs when something happens",
                },
            },
        },
    }


def create_service(config_data: dict) -> MultiFrameService:
    """Create a MultiFrameService with given config."""
    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "discipline_profiles.yaml"
        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)
        config = MultiFrameConfig(config_path)
        return MultiFrameService(config)


class TestDisciplineMiddlewareEnabled:
    """Tests for enabled discipline middleware."""

    @pytest.fixture(autouse=True)
    def enable_discipline(self):
        """Enable discipline feature for tests."""
        os.environ["GIRAF_DISCIPLINE_ENABLED"] = "true"
        yield
        if "GIRAF_DISCIPLINE_ENABLED" in os.environ:
            del os.environ["GIRAF_DISCIPLINE_ENABLED"]

    @pytest.fixture
    def middleware(self, sample_config: dict) -> DisciplineMiddleware:
        """Create middleware with test config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "discipline_profiles.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(sample_config, f)
            config = MultiFrameConfig(config_path)
            service = MultiFrameService(config)
            yield DisciplineMiddleware(service)

    @pytest.fixture
    def cs_session(self) -> SessionState:
        """Create session with CS discipline."""
        session = SessionState()
        session.discipline = "cs"
        return session

    @pytest.fixture
    def id_session(self) -> SessionState:
        """Create session with ID discipline."""
        session = SessionState()
        session.discipline = "id"
        return session

    async def test_cs_discipline_passes_through(
        self, middleware: DisciplineMiddleware, cs_session: SessionState
    ) -> None:
        """CS discipline should pass through without modification."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "test"},
            session=cs_session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="The API uses callbacks.")]

        # CS discipline shouldn't trigger processing
        assert middleware.should_process(ctx) is False

    async def test_id_discipline_adapts_response(
        self, middleware: DisciplineMiddleware, id_session: SessionState
    ) -> None:
        """ID discipline should adapt response."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "test"},
            session=id_session,
            start_time=0.0,
        )

        async def next_fn(ctx: ToolContext) -> list[TextContent]:
            return [TextContent(type="text", text="The API uses callbacks.")]

        assert middleware.should_process(ctx) is True

        result = await middleware.process(ctx, next_fn)

        # Should have added translation notes
        assert len(result) == 1
        assert "API" in result[0].text
        # Should include translation for ID
        assert "language" in result[0].text.lower() or "talk" in result[0].text.lower()

    async def test_no_discipline_passes_through(
        self, middleware: DisciplineMiddleware
    ) -> None:
        """No discipline set should pass through."""
        session = SessionState()
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "test"},
            session=session,
            start_time=0.0,
        )

        assert middleware.should_process(ctx) is False


class TestDisciplineMiddlewareDisabled:
    """Tests for disabled discipline middleware."""

    @pytest.fixture(autouse=True)
    def disable_discipline(self):
        """Disable discipline feature for tests."""
        os.environ["GIRAF_DISCIPLINE_ENABLED"] = "false"
        yield
        if "GIRAF_DISCIPLINE_ENABLED" in os.environ:
            del os.environ["GIRAF_DISCIPLINE_ENABLED"]

    @pytest.fixture
    def middleware(self, sample_config: dict) -> DisciplineMiddleware:
        """Create middleware with test config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "discipline_profiles.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(sample_config, f)
            config = MultiFrameConfig(config_path)
            service = MultiFrameService(config)
            yield DisciplineMiddleware(service)

    @pytest.fixture
    def id_session(self) -> SessionState:
        """Create session with ID discipline."""
        session = SessionState()
        session.discipline = "id"
        return session

    async def test_disabled_passes_through(
        self, middleware: DisciplineMiddleware, id_session: SessionState
    ) -> None:
        """Disabled middleware should pass through."""
        ctx = ToolContext(
            name="search_code",
            arguments={"query": "test"},
            session=id_session,
            start_time=0.0,
        )

        # Should not process when disabled
        assert middleware.should_process(ctx) is False
