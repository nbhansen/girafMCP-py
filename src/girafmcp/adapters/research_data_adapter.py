"""SQLite adapter for research data storage.

Handles query logs, knowledge capture, and resilience tracking.
Uses aiosqlite for async database operations.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from girafmcp.core.types import (
    ArchitecturalDecision,
    DecisionStatus,
    FollowUpStatus,
    HandoverPackage,
    LearningCategory,
    MetaSkillIndicators,
    QueryLog,
    QueryType,
    RetrospectiveLearning,
)

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

-- Knowledge Capture: Architectural Decisions (ADRs)
CREATE TABLE IF NOT EXISTS architectural_decisions (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    team_id TEXT,
    title TEXT NOT NULL,
    context TEXT NOT NULL,
    decision TEXT NOT NULL,
    rationale TEXT NOT NULL,
    alternatives TEXT,
    consequences TEXT,
    status TEXT NOT NULL DEFAULT 'accepted',
    related_issues TEXT,
    related_files TEXT,
    tags TEXT,
    discipline_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_ad_status ON architectural_decisions(status);
CREATE INDEX IF NOT EXISTS idx_ad_timestamp ON architectural_decisions(timestamp);
CREATE INDEX IF NOT EXISTS idx_ad_team ON architectural_decisions(team_id);

-- Knowledge Capture: Retrospective Learnings
CREATE TABLE IF NOT EXISTS retrospective_learnings (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    team_id TEXT,
    sprint TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    related_decisions TEXT,
    follow_up_status TEXT
);

CREATE INDEX IF NOT EXISTS idx_rl_sprint ON retrospective_learnings(sprint);
CREATE INDEX IF NOT EXISTS idx_rl_category ON retrospective_learnings(category);
CREATE INDEX IF NOT EXISTS idx_rl_team ON retrospective_learnings(team_id);

-- Knowledge Capture: Handover Packages
CREATE TABLE IF NOT EXISTS handover_packages (
    id TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    semester TEXT NOT NULL UNIQUE,
    executive_summary TEXT NOT NULL,
    key_decisions TEXT,
    lessons_learned TEXT,
    known_issues TEXT,
    recommended_priorities TEXT,
    human_reviewed INTEGER DEFAULT 0,
    reviewer_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_hp_semester ON handover_packages(semester);
"""


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(UTC)


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

        except Exception:
            logger.exception("Failed to log query")

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
            rows = list(await cursor.fetchall())

        await asyncio.to_thread(self._write_csv, output_path, rows)
        return len(rows)

    @staticmethod
    def _write_csv(output_path: Path, rows: list[aiosqlite.Row]) -> None:
        """Write exported query-log rows to a CSV file."""
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
                    f'"{v!s}"' if v and "," in str(v) else str(v or "")
                    for v in row
                ]
                f.write(",".join(formatted) + "\n")

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

    # =========================================================================
    # Knowledge Capture: Architectural Decisions
    # =========================================================================

    async def save_decision(self, decision: ArchitecturalDecision) -> None:
        """Save an architectural decision.

        Args:
            decision: The decision record to save
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO architectural_decisions (
                    id, timestamp, team_id, title, context, decision, rationale,
                    alternatives, consequences, status, related_issues,
                    related_files, tags, discipline_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.id,
                    decision.timestamp.isoformat(),
                    decision.team_id,
                    decision.title,
                    decision.context,
                    decision.decision,
                    decision.rationale,
                    json.dumps(decision.alternatives),
                    json.dumps(decision.consequences),
                    decision.status.value,
                    json.dumps(decision.related_issues),
                    json.dumps(decision.related_files),
                    json.dumps(decision.tags),
                    json.dumps(decision.discipline_notes),
                ),
            )
            await db.commit()

    async def get_decision(self, decision_id: str) -> ArchitecturalDecision | None:
        """Get an architectural decision by ID.

        Args:
            decision_id: The decision UUID

        Returns:
            The decision record or None if not found
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM architectural_decisions WHERE id = ?",
                (decision_id,),
            )
            row = await cursor.fetchone()
            if row:
                return self._row_to_decision(row)
            return None

    async def list_decisions(
        self,
        status: DecisionStatus | None = None,
        tags: list[str] | None = None,
        team_id: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[ArchitecturalDecision]:
        """List architectural decisions with optional filters.

        Args:
            status: Filter by status
            tags: Filter by tags (any match)
            team_id: Filter by team
            since: Only decisions after this time
            limit: Maximum number of results

        Returns:
            List of matching decisions
        """
        await self._ensure_initialized()

        query = "SELECT * FROM architectural_decisions WHERE 1=1"
        params: list[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.value)
        if team_id:
            query += " AND team_id = ?"
            params.append(team_id)
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            decisions = [self._row_to_decision(row) for row in rows]

            # Filter by tags if specified (post-query since tags are JSON)
            if tags:
                decisions = [
                    d for d in decisions
                    if any(tag in d.tags for tag in tags)
                ]

            return decisions

    async def search_decisions(self, query: str, limit: int = 5) -> list[ArchitecturalDecision]:
        """Search decisions by text content.

        Simple text search across title, context, decision, rationale.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching decisions
        """
        await self._ensure_initialized()

        # Simple LIKE search (for semantic search, use ChromaDB integration)
        search_pattern = f"%{query}%"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM architectural_decisions
                WHERE title LIKE ? OR context LIKE ? OR decision LIKE ? OR rationale LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (search_pattern, search_pattern, search_pattern, search_pattern, limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_decision(row) for row in rows]

    def _row_to_decision(self, row: aiosqlite.Row) -> ArchitecturalDecision:
        """Convert a database row to an ArchitecturalDecision."""
        return ArchitecturalDecision(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            team_id=row["team_id"],
            title=row["title"],
            context=row["context"],
            decision=row["decision"],
            rationale=row["rationale"],
            alternatives=json.loads(row["alternatives"]) if row["alternatives"] else [],
            consequences=json.loads(row["consequences"]) if row["consequences"] else [],
            status=DecisionStatus(row["status"]),
            related_issues=json.loads(row["related_issues"]) if row["related_issues"] else [],
            related_files=json.loads(row["related_files"]) if row["related_files"] else [],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            discipline_notes=json.loads(row["discipline_notes"]) if row["discipline_notes"] else {},
        )

    # =========================================================================
    # Knowledge Capture: Retrospective Learnings
    # =========================================================================

    async def save_learning(self, learning: RetrospectiveLearning) -> None:
        """Save a retrospective learning.

        Args:
            learning: The learning record to save
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO retrospective_learnings (
                    id, timestamp, team_id, sprint, category, description,
                    related_decisions, follow_up_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    learning.id,
                    learning.timestamp.isoformat(),
                    learning.team_id,
                    learning.sprint,
                    learning.category.value,
                    learning.description,
                    json.dumps(learning.related_decisions),
                    learning.follow_up_status.value if learning.follow_up_status else None,
                ),
            )
            await db.commit()

    async def get_learning(self, learning_id: str) -> RetrospectiveLearning | None:
        """Get a retrospective learning by ID.

        Args:
            learning_id: The learning UUID

        Returns:
            The learning record or None if not found
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM retrospective_learnings WHERE id = ?",
                (learning_id,),
            )
            row = await cursor.fetchone()
            if row:
                return self._row_to_learning(row)
            return None

    async def get_learnings_by_sprint(self, sprint: str) -> list[RetrospectiveLearning]:
        """Get all learnings for a sprint.

        Args:
            sprint: Sprint identifier (e.g., "2025s1-sprint3")

        Returns:
            List of learnings for the sprint
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM retrospective_learnings WHERE sprint = ? ORDER BY timestamp ASC",
                (sprint,),
            )
            rows = await cursor.fetchall()
            return [self._row_to_learning(row) for row in rows]

    async def get_learnings_by_category(
        self,
        category: LearningCategory,
        team_id: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[RetrospectiveLearning]:
        """Get learnings filtered by category.

        Args:
            category: Learning category
            team_id: Optional team filter
            since: Optional time filter
            limit: Maximum results

        Returns:
            List of matching learnings
        """
        await self._ensure_initialized()

        query = "SELECT * FROM retrospective_learnings WHERE category = ?"
        params: list[Any] = [category.value]

        if team_id:
            query += " AND team_id = ?"
            params.append(team_id)
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [self._row_to_learning(row) for row in rows]

    async def list_learnings(
        self,
        team_id: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[RetrospectiveLearning]:
        """List all retrospective learnings.

        Args:
            team_id: Optional team filter
            since: Optional time filter
            limit: Maximum results

        Returns:
            List of learnings
        """
        await self._ensure_initialized()

        query = "SELECT * FROM retrospective_learnings WHERE 1=1"
        params: list[Any] = []

        if team_id:
            query += " AND team_id = ?"
            params.append(team_id)
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [self._row_to_learning(row) for row in rows]

    async def search_learnings(self, query: str, limit: int = 5) -> list[RetrospectiveLearning]:
        """Search learnings by text content.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching learnings
        """
        await self._ensure_initialized()

        search_pattern = f"%{query}%"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM retrospective_learnings
                WHERE description LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (search_pattern, limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_learning(row) for row in rows]

    def _row_to_learning(self, row: aiosqlite.Row) -> RetrospectiveLearning:
        """Convert a database row to a RetrospectiveLearning."""
        follow_up = None
        if row["follow_up_status"]:
            follow_up = FollowUpStatus(row["follow_up_status"])

        return RetrospectiveLearning(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            team_id=row["team_id"],
            sprint=row["sprint"],
            category=LearningCategory(row["category"]),
            description=row["description"],
            related_decisions=json.loads(row["related_decisions"]) if row["related_decisions"] else [],
            follow_up_status=follow_up,
        )

    # =========================================================================
    # Knowledge Capture: Handover Packages
    # =========================================================================

    async def save_handover(self, package: HandoverPackage) -> None:
        """Save a handover package.

        Args:
            package: The handover package to save
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO handover_packages (
                    id, generated_at, semester, executive_summary, key_decisions,
                    lessons_learned, known_issues, recommended_priorities,
                    human_reviewed, reviewer_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    package.id,
                    package.generated_at.isoformat(),
                    package.semester,
                    package.executive_summary,
                    json.dumps(package.key_decisions),
                    json.dumps(package.lessons_learned),
                    json.dumps(package.known_issues),
                    json.dumps(package.recommended_priorities),
                    1 if package.human_reviewed else 0,
                    package.reviewer_notes,
                ),
            )
            await db.commit()

    async def get_handover(self, semester: str) -> HandoverPackage | None:
        """Get handover package for a semester.

        Args:
            semester: Semester identifier (e.g., "2025s1")

        Returns:
            The handover package or None if not found
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM handover_packages WHERE semester = ?",
                (semester,),
            )
            row = await cursor.fetchone()
            if row:
                return self._row_to_handover(row)
            return None

    async def get_handover_by_id(self, package_id: str) -> HandoverPackage | None:
        """Get handover package by ID.

        Args:
            package_id: Package UUID

        Returns:
            The handover package or None if not found
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM handover_packages WHERE id = ?",
                (package_id,),
            )
            row = await cursor.fetchone()
            if row:
                return self._row_to_handover(row)
            return None

    async def list_handovers(self) -> list[HandoverPackage]:
        """List all handover packages.

        Returns:
            List of all handover packages
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM handover_packages ORDER BY generated_at DESC"
            )
            rows = await cursor.fetchall()
            return [self._row_to_handover(row) for row in rows]

    async def mark_handover_reviewed(
        self,
        package_id: str,
        approved: bool,
        notes: str | None = None,
    ) -> bool:
        """Mark a handover package as reviewed.

        Args:
            package_id: Package UUID
            approved: Whether the package was approved
            notes: Optional reviewer notes

        Returns:
            True if package was found and updated, False otherwise
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE handover_packages
                SET human_reviewed = ?, reviewer_notes = ?
                WHERE id = ?
                """,
                (1 if approved else 0, notes, package_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    def _row_to_handover(self, row: aiosqlite.Row) -> HandoverPackage:
        """Convert a database row to a HandoverPackage."""
        return HandoverPackage(
            id=row["id"],
            generated_at=datetime.fromisoformat(row["generated_at"]),
            semester=row["semester"],
            executive_summary=row["executive_summary"],
            key_decisions=json.loads(row["key_decisions"]) if row["key_decisions"] else [],
            lessons_learned=json.loads(row["lessons_learned"]) if row["lessons_learned"] else [],
            known_issues=json.loads(row["known_issues"]) if row["known_issues"] else [],
            recommended_priorities=json.loads(row["recommended_priorities"]) if row["recommended_priorities"] else [],
            human_reviewed=bool(row["human_reviewed"]),
            reviewer_notes=row["reviewer_notes"],
        )
