"""Tests that query-log exports stay inside data/exports/."""

import pytest

from girafmcp.tools import research


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "DATA_DIR", tmp_path)
    return tmp_path


class TestExportPath:
    async def test_named_export_lands_in_exports_dir(self, data_dir, mock_research_data_adapter):
        result = await research.handle_export_query_logs(
            mock_research_data_adapter, output_path="study.csv"
        )
        assert (data_dir / "exports" / "study.csv").exists(), result[0].text

    async def test_default_export_lands_in_exports_dir(self, data_dir, mock_research_data_adapter):
        await research.handle_export_query_logs(mock_research_data_adapter)
        assert len(list((data_dir / "exports").glob("query_logs_*.csv"))) == 1

    @pytest.mark.parametrize("escape", ["../outside.csv", "/tmp/outside.csv", "a/../../outside.csv"])
    async def test_rejects_paths_outside_exports_dir(
        self, data_dir, mock_research_data_adapter, escape
    ):
        result = await research.handle_export_query_logs(
            mock_research_data_adapter, output_path=escape
        )
        assert "Invalid output_path" in result[0].text
        assert not (data_dir / "outside.csv").exists()
