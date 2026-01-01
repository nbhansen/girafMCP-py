"""SQLite adapter for research data storage.

Handles query logs, knowledge capture, and resilience tracking.
Uses aiosqlite for async database operations.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from girafmcp.core.types import MetaSkillIndicators, QueryLog, QueryType

logger = logging.getLogger(__name__)


# SQL schema for research data
SCHEMA_SQL = """
-- Query logging
CREATE TABLE IF NOT EXISTS query_logs (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    session_id TEXT NOT NULL,
    team_id TEXT,
    role TEXT,
    discipline TEXT,
    tool_name TEXT NOT NULL,
    arguments TEXT NOT NULL,
    query_text TEXT,
    response_length INTEGER NOT NULL,
    result_count INTEGER,
    duration_ms INTEGER NOT NULL,
    error TEXT,
    query_type TEXT,
    meta_skills TEXT,
    guardrail_mode TEXT,
    guardrail_tier INTEGER
);

CREATE INDEX IF NOT EXISTS idx_ql_session ON query_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_ql_team_time ON query_logs(team_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_ql_query_type ON query_logs(query_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_ql_tool ON query_logs(tool_name, timestamp);

-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    team_id TEXT,
    role TEXT,
    discipline TEXT,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_sess_team ON sessions(team_id);
"""


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class ResearchDataAdapter:
    """Unified SQLite adapter for research data storage.

    Handles query logs, knowledge capture (ADRs, learnings),
    and resilience tracking (injected errors).
    """

    def __init__(self, db_path: Path | str):
        """Initialize the adapter.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure database schema is created."""
        if self._initialized:
            return

        # Create parent directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA_SQL)
            await db.commit()

        self._initialized = True
        logger.info(f"Research database initialized at {self.db_path}")

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get a database connection (caller must close)."""
        await self._ensure_initialized()
        return await aiosqlite.connect(self.db_path)

    # =========================================================================
    # Query Logging
    # =========================================================================

    async def log_query(self, log: QueryLog) -> None:
        """Insert a query log record.

        This is fire-and-forget - errors are logged but don't propagate.
        """
        try:
            await self._ensure_initialized()

            meta_skills_json = None
            if log.meta_skills:
                meta_skills_json = json.dumps({
                    "verification_attempted": log.meta_skills.verification_attempted,
                    "test_run_before_query": log.meta_skills.test_run_before_query,
                    "error_description_quality": log.meta_skills.error_description_quality,
                    "references_existing_code": log.meta_skills.references_existing_code,
                    "asks_about_integration": log.meta_skills.asks_about_integration,
                    "architectural_awareness": log.meta_skills.architectural_awareness,
                    "hypothesis_present": log.meta_skills.hypothesis_present,
                    "isolation_attempted": log.meta_skills.isolation_attempted,
                    "follow_up_depth": log.meta_skills.follow_up_depth,
                    "accepted_without_verification": log.meta_skills.accepted_without_verification,
                    "discipline_translation_needed": log.meta_skills.discipline_translation_needed,
                    "requests_alternative_framing": log.meta_skills.requests_alternative_framing,
                })

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO query_logs (
                        id, timestamp, session_id, team_id, role, discipline,
                        tool_name, arguments, query_text, response_length,
                        result_count, duration_ms, error, query_type,
                        meta_skills, guardrail_mode, guardrail_tier
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        log.id,
                        log.timestamp.isoformat(),
                        log.session_id,
                        log.team_id,
                        log.role,
                        log.discipline,
                        log.tool_name,
                        json.dumps(log.arguments),
                        log.query_text,
                        log.response_length,
                        log.result_count,
                        log.duration_ms,
                        log.error,
                        log.query_type.value if log.query_type else None,
                        meta_skills_json,
                        log.guardrail_mode,
                        log.guardrail_tier,
                    ),
                )
                await db.commit()

        except Exception as e:
            logger.error(f"Failed to log query: {e}", exc_info=True)

    async def get_session_queries(self, session_id: str) -> list[QueryLog]:
        """Retrieve all queries for a session.

        Args:
            session_id: The session ID to query

        Returns:
            List of QueryLog records
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM query_logs
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (session_id,),
            )
            rows = await cursor.fetchall()
            return [self._row_to_query_log(row) for row in rows]

    async def get_queries_by_team(
        self,
        team_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[QueryLog]:
        """Retrieve queries for a team within optional time range.

        Args:
            team_id: Team identifier
            start: Optional start datetime (inclusive)
            end: Optional end datetime (exclusive)

        Returns:
            List of QueryLog records
        """
        await self._ensure_initialized()

        query = "SELECT * FROM query_logs WHERE team_id = ?"
        params: list[Any] = [team_id]

        if start:
            query += " AND timestamp >= ?"
            params.append(start.isoformat())
        if end:
            query += " AND timestamp < ?"
            params.append(end.isoformat())

        query += " ORDER BY timestamp ASC"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [self._row_to_query_log(row) for row in rows]

    async def get_query_type_counts(
        self,
        team_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, int]:
        """Aggregate query counts by type.

        Args:
            team_id: Optional filter by team
            start: Optional start datetime
            end: Optional end datetime

        Returns:
            Dict mapping query type to count
        """
        await self._ensure_initialized()

        query = "SELECT query_type, COUNT(*) as count FROM query_logs WHERE 1=1"
        params: list[Any] = []

        if team_id:
            query += " AND team_id = ?"
            params.append(team_id)
        if start:
            query += " AND timestamp >= ?"
            params.append(start.isoformat())
        if end:
            query += " AND timestamp < ?"
            params.append(end.isoformat())

        query += " GROUP BY query_type"

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return {row[0] or "unknown": row[1] for row in rows}

    async def get_tool_usage_counts(
        self,
        team_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, int]:
        """Aggregate usage counts by tool.

        Args:
            team_id: Optional filter by team
            start: Optional start datetime
            end: Optional end datetime

        Returns:
            Dict mapping tool name to count
        """
        await self._ensure_initialized()

        query = "SELECT tool_name, COUNT(*) as count FROM query_logs WHERE 1=1"
        params: list[Any] = []

        if team_id:
            query += " AND team_id = ?"
            params.append(team_id)
        if start:
            query += " AND timestamp >= ?"
            params.append(start.isoformat())
        if end:
            query += " AND timestamp < ?"
            params.append(end.isoformat())

        query += " GROUP BY tool_name ORDER BY count DESC"

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}

    async def export_csv(
        self,
        output_path: Path,
        team_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> int:
        """Export logs to CSV for external analysis.

        Args:
            output_path: Path to write CSV file
            team_id: Optional filter by team
            start: Optional start datetime
            end: Optional end datetime

        Returns:
            Number of rows exported
        """
        await self._ensure_initialized()

        query = """
            SELECT id, timestamp, session_id, team_id, role, discipline,
                   tool_name, query_type, duration_ms, result_count, error
            FROM query_logs WHERE 1=1
        """
        params: list[Any] = []

        if team_id:
            query += " AND team_id = ?"
            params.append(team_id)
        if start:
            query += " AND timestamp >= ?"
            params.append(start.isoformat())
        if end:
            query += " AND timestamp < ?"
            params.append(end.isoformat())

        query += " ORDER BY timestamp ASC"

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            # Write CSV
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                # Header
                f.write(
                    "id,timestamp,session_id,team_id,role,discipline,"
                    "tool_name,query_type,duration_ms,result_count,error\n"
                )
                # Data
                for row in rows:
                    # Escape/quote fields that might contain commas
                    formatted = [
                        f'"{str(v)}"' if v and "," in str(v) else str(v or "")
                        for v in row
                    ]
                    f.write(",".join(formatted) + "\n")

            return len(rows)

    def _row_to_query_log(self, row: aiosqlite.Row) -> QueryLog:
        """Convert a database row to a QueryLog object."""
        meta_skills = None
        if row["meta_skills"]:
            ms_data = json.loads(row["meta_skills"])
            meta_skills = MetaSkillIndicators(**ms_data)

        return QueryLog(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            session_id=row["session_id"],
            team_id=row["team_id"],
            role=row["role"],
            discipline=row["discipline"],
            tool_name=row["tool_name"],
            arguments=json.loads(row["arguments"]),
            query_text=row["query_text"],
            response_length=row["response_length"],
            result_count=row["result_count"],
            duration_ms=row["duration_ms"],
            error=row["error"],
            query_type=QueryType(row["query_type"]) if row["query_type"] else QueryType.UNKNOWN,
            meta_skills=meta_skills,
            guardrail_mode=row["guardrail_mode"],
            guardrail_tier=row["guardrail_tier"],
        )

    # =========================================================================
    # Session Management
    # =========================================================================

    async def save_session(
        self,
        session_id: str,
        started_at: datetime,
        team_id: str | None = None,
        role: str | None = None,
        discipline: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Save or update session metadata."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO sessions
                (id, started_at, team_id, role, discipline, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    started_at.isoformat(),
                    team_id,
                    role,
                    discipline,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            await db.commit()

    async def end_session(self, session_id: str) -> None:
        """Mark a session as ended."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?",
                (_utcnow().isoformat(), session_id),
            )
            await db.commit()
