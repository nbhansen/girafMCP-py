"""Tests that default data paths do not depend on the working directory."""

import pytest

from girafmcp.core.container import DependencyContainer
from girafmcp.core.paths import DATA_DIR


class TestDefaultDataPaths:
    """Default paths must resolve under the project's data/ dir from any cwd."""

    @pytest.fixture(autouse=True)
    def _foreign_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        for var in ("GIRAF_KNOWLEDGE_DB", "GIRAF_EXTRACTED_DIR", "GIRAF_DOCUMENTS_DIR"):
            monkeypatch.delenv(var, raising=False)

    def test_knowledge_db_is_anchored(self):
        adapter = DependencyContainer().research_data_adapter
        assert adapter.db_path == DATA_DIR / "knowledge.db"

    def test_extracted_dir_is_anchored(self):
        adapter = DependencyContainer().keyword_search_adapter
        assert adapter.extracted_dir == DATA_DIR / "extracted"

    def test_documents_dir_is_anchored(self):
        service = DependencyContainer().extraction_service
        assert service.documents_dir == DATA_DIR / "documents"
