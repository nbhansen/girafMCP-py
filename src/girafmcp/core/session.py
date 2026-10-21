"""Session state management for research features.

Uses Python's contextvars for request-scoped session state:
- Works correctly in HTTP mode (each request gets own context)
- Falls back gracefully in STDIO mode (single global context)
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(UTC)


@dataclass
class SessionState:
    """Session state for a client connection.

    Tracks research metadata and feature state across tool invocations
    within a single session.
    """

    # Session identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=_utcnow)

    # Research metadata (set via set_session_metadata tool)
    team_id: str | None = None
    role: Literal["po", "sm", "dev", "unknown"] | None = None
    discipline: Literal["cs", "id", "business", "health", "unknown"] | None = None

    # Guardrail state
    guardrail_tier: int = 1
    guardrail_prompted: bool = False
    cooldown_until: datetime | None = None

    # Last query tracking (for tiered responses and request_more_detail)
    last_tool: str | None = None
    last_arguments: dict[str, Any] | None = None
    last_response: str | None = None

    # Resilience tracking
    pending_injected_errors: list[str] = field(default_factory=list)

    def reset_guardrail_state(self) -> None:
        """Reset guardrail state for a new topic."""
        self.guardrail_tier = 1
        self.guardrail_prompted = False

    def advance_tier(self, max_tier: int = 4) -> int:
        """Advance to next tier, return new tier number."""
        self.guardrail_tier = min(self.guardrail_tier + 1, max_tier)
        return self.guardrail_tier

    def set_metadata(
        self,
        team_id: str | None = None,
        role: str | None = None,
        discipline: str | None = None,
    ) -> None:
        """Update session metadata."""
        if team_id is not None:
            self.team_id = team_id
        if role is not None:
            self.role = role  # type: ignore[assignment]
        if discipline is not None:
            self.discipline = discipline  # type: ignore[assignment]

    def record_tool_call(
        self, tool: str, arguments: dict[str, Any], response: str | None = None
    ) -> None:
        """Record the last tool call for tiered response tracking."""
        self.last_tool = tool
        self.last_arguments = arguments
        self.last_response = response


# Context variable for current session
_current_session: ContextVar[SessionState] = ContextVar("current_session")


def get_current_session() -> SessionState:
    """Get or create session for current context.

    In STDIO mode, creates a single global session on first call.
    In HTTP mode, each request should call set_current_session() first.
    """
    try:
        return _current_session.get()
    except LookupError:
        session = SessionState()
        _current_session.set(session)
        return session


def set_current_session(session: SessionState) -> None:
    """Set session for current context.

    Used in HTTP mode to set up session at start of each request.
    """
    _current_session.set(session)


def reset_session() -> SessionState:
    """Create and set a new session, returning it.

    Useful for testing or explicitly starting a new session.
    """
    session = SessionState()
    _current_session.set(session)
    return session
