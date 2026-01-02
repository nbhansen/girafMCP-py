"""Dependency injection container for the GIRAF MCP server.

Manages the lifecycle of adapters and services, replacing global state.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from girafmcp.adapters import ChromaAdapter, FileAdapter, GitHubAdapter
from girafmcp.adapters.research_data_adapter import ResearchDataAdapter
from girafmcp.core.services.guardrails_service import GuardrailsService
from girafmcp.core.services.multiframe_service import MultiFrameConfig, MultiFrameService
from girafmcp.core.services.resilience_service import ResilienceService

# Load .env file from project root
_project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(_project_root / ".env")


class DependencyContainer:
    """Container for managing singleton instances of adapters and services."""

    def __init__(self) -> None:
        """Initialize the container."""
        self._github_adapter: GitHubAdapter | None = None
        self._chroma_adapter: ChromaAdapter | None = None
        self._file_adapter: FileAdapter | None = None
        self._guardrails_service: GuardrailsService | None = None
        self._research_data_adapter: ResearchDataAdapter | None = None
        self._resilience_service: ResilienceService | None = None
        self._multiframe_service: MultiFrameService | None = None

    @property
    def github_adapter(self) -> GitHubAdapter:
        """Get or create GitHub adapter."""
        if self._github_adapter is None:
            self._github_adapter = GitHubAdapter(
                org="aau-giraf",
                token=os.environ.get("GITHUB_TOKEN"),
            )
        return self._github_adapter

    @property
    def chroma_adapter(self) -> ChromaAdapter:
        """Get or create ChromaDB adapter."""
        if self._chroma_adapter is None:
            persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_data")
            self._chroma_adapter = ChromaAdapter(persist_directory=persist_dir)
        return self._chroma_adapter

    @property
    def file_adapter(self) -> FileAdapter:
        """Get or create file adapter."""
        if self._file_adapter is None:
            data_dir = os.environ.get("GIRAF_DATA_DIR")
            self._file_adapter = FileAdapter(data_dir=data_dir)
        return self._file_adapter

    @property
    def guardrails_service(self) -> GuardrailsService:
        """Get or create guardrails service."""
        if self._guardrails_service is None:
            self._guardrails_service = GuardrailsService()
        return self._guardrails_service

    @property
    def research_data_adapter(self) -> ResearchDataAdapter:
        """Get or create research data adapter."""
        if self._research_data_adapter is None:
            db_path = os.environ.get("GIRAF_KNOWLEDGE_DB", "data/knowledge.db")
            self._research_data_adapter = ResearchDataAdapter(db_path)
        return self._research_data_adapter

    @property
    def resilience_service(self) -> ResilienceService:
        """Get or create resilience service."""
        if self._resilience_service is None:
            self._resilience_service = ResilienceService()
        return self._resilience_service

    @property
    def multiframe_service(self) -> MultiFrameService:
        """Get or create multiframe service."""
        if self._multiframe_service is None:
            config_path = Path(
                os.environ.get(
                    "GIRAF_DISCIPLINE_PROFILES",
                    str(_project_root / "data" / "discipline_profiles.yaml"),
                )
            )
            config = MultiFrameConfig(config_path)
            self._multiframe_service = MultiFrameService(config)
        return self._multiframe_service
