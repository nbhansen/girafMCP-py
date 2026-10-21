"""Tests for ResearchDataAdapter."""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from girafmcp.adapters.research_data_adapter import ResearchDataAdapter
from girafmcp.core.types import MetaSkillIndicators, QueryLog, QueryType


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(UTC)


@pytest.fixture
def temp_db() -> Path:
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    # Cleanup
    if path.exists():
        os.unlink(path)


@pytest.fixture
def adapter(temp_db: Path) -> ResearchDataAdapter:
    """Create an adapter with a temporary database."""
    return ResearchDataAdapter(temp_db)


def make_query_log(
    id: str = "test-id",
    session_id: str = "session-1",
    tool_name: str = "search_code",
    **kwargs,
) -> QueryLog:
    """Create a QueryLog with defaults."""
    defaults = {
        "id": id,
        "timestamp": _utcnow(),
        "session_id": session_id,
        "team_id": "team_a",
        "role": "dev",
        "discipline": "cs",
        "tool_name": tool_name,
        "arguments": {"query": "test"},
        "query_text": "test query",
        "response_length": 100,
        "result_count": 5,
        "duration_ms": 50,
        "error": None,
        "query_type": QueryType.NAVIGATION,
        "meta_skills": None,
        "guardrail_mode": "off",
        "guardrail_tier": 1,
    }
    defaults.update(kwargs)
    return QueryLog(**defaults)


class TestQueryLogging:
    """Tests for query logging functionality."""

    async def test_log_query_creates_record(self, adapter: ResearchDataAdapter) -> None:
        """log_query should insert a record."""
        log = make_query_log(id="log-1")
        await adapter.log_query(log)

        # Retrieve and verify
        logs = await adapter.get_session_queries("session-1")
        assert len(logs) == 1
        assert logs[0].id == "log-1"
        assert logs[0].tool_name == "search_code"

    async def test_log_query_with_meta_skills(
        self, adapter: ResearchDataAdapter
    ) -> None:
        """log_query should store meta_skills."""
        meta_skills = MetaSkillIndicators(
            verification_attempted=True,
            hypothesis_present=True,
            error_description_quality="specific",
        )
        log = make_query_log(id="log-2", meta_skills=meta_skills)
        await adapter.log_query(log)

        logs = await adapter.get_session_queries("session-1")
        assert len(logs) == 1
        assert logs[0].meta_skills is not None
        assert logs[0].meta_skills.verification_attempted is True
        assert logs[0].meta_skills.hypothesis_present is True
        assert logs[0].meta_skills.error_description_quality == "specific"

    async def test_log_query_handles_errors_gracefully(
        self, adapter: ResearchDataAdapter
    ) -> None:
        """log_query should not raise on errors."""
        # Use an invalid path that will fail
        bad_adapter = ResearchDataAdapter(Path("/nonexistent/path/db.sqlite"))
        log = make_query_log()

        # Should not raise
        await bad_adapter.log_query(log)

    async def test_get_session_queries_ordered(
        self, adapter: ResearchDataAdapter
    ) -> None:
        """get_session_queries should return in timestamp order."""
        now = _utcnow()
        logs = [
            make_query_log(id="log-3", timestamp=now + timedelta(minutes=2)),
            make_query_log(id="log-1", timestamp=now),
            make_query_log(id="log-2", timestamp=now + timedelta(minutes=1)),
        ]

        for log in logs:
            await adapter.log_query(log)

        result = await adapter.get_session_queries("session-1")
        assert [r.id for r in result] == ["log-1", "log-2", "log-3"]

    async def test_get_queries_by_team(self, adapter: ResearchDataAdapter) -> None:
        """get_queries_by_team should filter by team."""
        await adapter.log_query(make_query_log(id="a1", team_id="team_a"))
        await adapter.log_query(make_query_log(id="b1", team_id="team_b"))
        await adapter.log_query(make_query_log(id="a2", team_id="team_a"))

        team_a = await adapter.get_queries_by_team("team_a")
        assert len(team_a) == 2
        assert {log.id for log in team_a} == {"a1", "a2"}

    async def test_get_queries_by_team_with_time_range(
        self, adapter: ResearchDataAdapter
    ) -> None:
        """get_queries_by_team should filter by time range."""
        now = _utcnow()
        await adapter.log_query(
            make_query_log(id="old", timestamp=now - timedelta(days=2))
        )
        await adapter.log_query(make_query_log(id="in_range", timestamp=now))
        await adapter.log_query(
            make_query_log(id="future", timestamp=now + timedelta(days=2))
        )

        result = await adapter.get_queries_by_team(
            "team_a",
            start=now - timedelta(days=1),
            end=now + timedelta(days=1),
        )
        assert len(result) == 1
        assert result[0].id == "in_range"

    async def test_get_query_type_counts(self, adapter: ResearchDataAdapter) -> None:
        """get_query_type_counts should aggregate by type."""
        await adapter.log_query(
            make_query_log(id="1", query_type=QueryType.NAVIGATION)
        )
        await adapter.log_query(
            make_query_log(id="2", query_type=QueryType.NAVIGATION)
        )
        await adapter.log_query(
            make_query_log(id="3", query_type=QueryType.EXPLANATION)
        )
        await adapter.log_query(
            make_query_log(id="4", query_type=QueryType.DEBUGGING)
        )

        counts = await adapter.get_query_type_counts()
        assert counts["navigation"] == 2
        assert counts["explanation"] == 1
        assert counts["debugging"] == 1

    async def test_get_tool_usage_counts(self, adapter: ResearchDataAdapter) -> None:
        """get_tool_usage_counts should aggregate by tool."""
        await adapter.log_query(make_query_log(id="1", tool_name="search_code"))
        await adapter.log_query(make_query_log(id="2", tool_name="search_code"))
        await adapter.log_query(make_query_log(id="3", tool_name="get_file"))

        counts = await adapter.get_tool_usage_counts()
        assert counts["search_code"] == 2
        assert counts["get_file"] == 1

    async def test_export_csv(self, adapter: ResearchDataAdapter, temp_db: Path) -> None:
        """export_csv should create a CSV file."""
        await adapter.log_query(make_query_log(id="1"))
        await adapter.log_query(make_query_log(id="2"))

        csv_path = temp_db.parent / "export.csv"
        count = await adapter.export_csv(csv_path)

        assert count == 2
        assert csv_path.exists()

        content = csv_path.read_text()
        assert "id,timestamp,session_id" in content  # Header
        assert "team_a" in content
        assert "search_code" in content


class TestSessionManagement:
    """Tests for session management."""

    async def test_save_session(self, adapter: ResearchDataAdapter) -> None:
        """save_session should create a session record."""
        await adapter.save_session(
            session_id="sess-1",
            started_at=_utcnow(),
            team_id="team_a",
            role="dev",
            discipline="cs",
        )

        # Verify via raw query
        import aiosqlite

        async with aiosqlite.connect(adapter.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM sessions WHERE id = ?", ("sess-1",)
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row["team_id"] == "team_a"
            assert row["role"] == "dev"
            assert row["discipline"] == "cs"

    async def test_end_session(self, adapter: ResearchDataAdapter) -> None:
        """end_session should set ended_at."""
        await adapter.save_session(session_id="sess-1", started_at=_utcnow())
        await adapter.end_session("sess-1")

        import aiosqlite

        async with aiosqlite.connect(adapter.db_path) as db:
            cursor = await db.execute(
                "SELECT ended_at FROM sessions WHERE id = ?", ("sess-1",)
            )
            row = await cursor.fetchone()
            assert row[0] is not None  # ended_at should be set
