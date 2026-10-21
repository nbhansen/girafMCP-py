"""Dependency injection container for the GIRAF MCP server.

Manages the lifecycle of adapters and services, replacing global state.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from girafmcp.adapters import FileAdapter, GitHubAdapter
from girafmcp.adapters.github_projects_adapter import GitHubProjectsAdapter
from girafmcp.adapters.keyword_search_adapter import KeywordSearchAdapter
from girafmcp.adapters.research_data_adapter import ResearchDataAdapter
from girafmcp.core.paths import DATA_DIR, PROJECT_ROOT
from girafmcp.core.services.extraction_service import ExtractionService
from girafmcp.core.services.guardrails_service import GuardrailsService
from girafmcp.core.services.multiframe_service import MultiFrameConfig, MultiFrameService
from girafmcp.core.services.resilience_service import ResilienceService

# Load .env file from project root
load_dotenv(PROJECT_ROOT / ".env")


class DependencyContainer:
    """Container for managing singleton instances of adapters and services."""

    def __init__(self) -> None:
        """Initialize the container."""
        self._github_adapter: GitHubAdapter | None = None
        self._github_projects_adapter: GitHubProjectsAdapter | None = None
        self._keyword_search_adapter: KeywordSearchAdapter | None = None
        self._file_adapter: FileAdapter | None = None
        self._extraction_service: ExtractionService | None = None
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
    def github_projects_adapter(self) -> GitHubProjectsAdapter:
        """Get or create GitHub Projects V2 adapter."""
        if self._github_projects_adapter is None:
            self._github_projects_adapter = GitHubProjectsAdapter(
                org="aau-giraf",
                token=os.environ.get("GITHUB_TOKEN"),
            )
        return self._github_projects_adapter

    @property
    def keyword_search_adapter(self) -> KeywordSearchAdapter:
        """Get or create keyword search adapter."""
        if self._keyword_search_adapter is None:
            extracted_dir = Path(os.environ.get("GIRAF_EXTRACTED_DIR", str(DATA_DIR / "extracted")))
            self._keyword_search_adapter = KeywordSearchAdapter(extracted_dir=extracted_dir)
        return self._keyword_search_adapter

    @property
    def file_adapter(self) -> FileAdapter:
        """Get or create file adapter."""
        if self._file_adapter is None:
            data_dir = os.environ.get("GIRAF_DATA_DIR")
            self._file_adapter = FileAdapter(data_dir=data_dir)
        return self._file_adapter

    @property
    def extraction_service(self) -> ExtractionService:
        """Get or create extraction service."""
        if self._extraction_service is None:
            documents_dir = Path(os.environ.get("GIRAF_DOCUMENTS_DIR", str(DATA_DIR / "documents")))
            extracted_dir = Path(os.environ.get("GIRAF_EXTRACTED_DIR", str(DATA_DIR / "extracted")))
            self._extraction_service = ExtractionService(
                documents_dir=documents_dir,
                extracted_dir=extracted_dir,
            )
        return self._extraction_service

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
            db_path = os.environ.get("GIRAF_KNOWLEDGE_DB", str(DATA_DIR / "knowledge.db"))
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
                    str(DATA_DIR / "discipline_profiles.yaml"),
                )
            )
            config = MultiFrameConfig(config_path)
            self._multiframe_service = MultiFrameService(config)
        return self._multiframe_service
