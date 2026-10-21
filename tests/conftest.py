"""Pytest configuration and fixtures."""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

from girafmcp.adapters import FileAdapter, GitHubAdapter
from girafmcp.adapters.keyword_search_adapter import KeywordSearchAdapter
from girafmcp.adapters.research_data_adapter import ResearchDataAdapter
from girafmcp.core.container import DependencyContainer
from girafmcp.core.services.guardrails_service import GuardrailsService
from girafmcp.core.services.multiframe_service import MultiFrameService
from girafmcp.core.services.resilience_service import ResilienceService

# Load environment variables from .env file
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


@pytest.fixture
def mock_research_data_adapter() -> Generator[ResearchDataAdapter, None, None]:
    """Create a fresh ResearchDataAdapter with a temporary database."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield ResearchDataAdapter(db_path)


@pytest.fixture
def mock_file_adapter() -> Generator[FileAdapter, None, None]:
    """Create a mock FileAdapter."""
    adapter = MagicMock(spec=FileAdapter)
    adapter.get_context.return_value = {"semester": "2025s1", "focus": "Test Focus"}
    adapter.get_personas.return_value = {"personas": {"student": {"name": "Student"}}}
    yield adapter


@pytest.fixture
def mock_github_adapter() -> Generator[GitHubAdapter, None, None]:
    """Create a mock GitHubAdapter."""
    adapter = MagicMock(spec=GitHubAdapter)
    yield adapter


@pytest.fixture
def mock_container(
    mock_research_data_adapter: ResearchDataAdapter,
    mock_file_adapter: FileAdapter,
    mock_github_adapter: GitHubAdapter,
) -> Generator[DependencyContainer, None, None]:
    """Create a mock DependencyContainer with mocked adapters."""
    container = MagicMock(spec=DependencyContainer)

    # Adapters
    type(container).keyword_search_adapter = property(
        lambda self: KeywordSearchAdapter(extracted_dir=None)
    )
    type(container).research_data_adapter = property(lambda self: mock_research_data_adapter)
    type(container).file_adapter = property(lambda self: mock_file_adapter)
    type(container).github_adapter = property(lambda self: mock_github_adapter)

    # Services
    container.guardrails_service = MagicMock(spec=GuardrailsService)
    container.resilience_service = MagicMock(spec=ResilienceService)
    container.multiframe_service = MagicMock(spec=MultiFrameService)

    yield container


@pytest.fixture
def patch_server_container(mock_container: DependencyContainer) -> Generator[None, None, None]:
    """Patch the global container in server.py with the mock container."""
    with patch("girafmcp.server.container", mock_container):
        yield
