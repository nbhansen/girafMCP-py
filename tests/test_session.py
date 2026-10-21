"""Tests for session state management."""


from girafmcp.core.session import (
    SessionState,
    get_current_session,
    set_current_session,
    reset_session,
)


class TestSessionState:
    """Tests for SessionState dataclass."""

    def test_default_values(self) -> None:
        """Session should have sensible defaults."""
        session = SessionState()

        assert session.id is not None
        assert len(session.id) == 36  # UUID format
        assert session.started_at is not None
        assert session.team_id is None
        assert session.role is None
        assert session.discipline is None
        assert session.guardrail_tier == 1
        assert session.guardrail_prompted is False
        assert session.cooldown_until is None
        assert session.last_tool is None
        assert session.pending_injected_errors == []

    def test_set_metadata(self) -> None:
        """set_metadata should update session fields."""
        session = SessionState()

        session.set_metadata(team_id="team_a", role="dev", discipline="cs")

        assert session.team_id == "team_a"
        assert session.role == "dev"
        assert session.discipline == "cs"

    def test_set_metadata_partial(self) -> None:
        """set_metadata should only update provided fields."""
        session = SessionState()
        session.set_metadata(team_id="team_a")

        session.set_metadata(role="sm")

        assert session.team_id == "team_a"  # Unchanged
        assert session.role == "sm"
        assert session.discipline is None

    def test_advance_tier(self) -> None:
        """advance_tier should increment up to max."""
        session = SessionState()

        assert session.guardrail_tier == 1

        assert session.advance_tier() == 2
        assert session.advance_tier() == 3
        assert session.advance_tier() == 4
        assert session.advance_tier() == 4  # Capped at max
        assert session.advance_tier(max_tier=5) == 5

    def test_reset_guardrail_state(self) -> None:
        """reset_guardrail_state should reset tier and prompted flag."""
        session = SessionState()
        session.guardrail_tier = 3
        session.guardrail_prompted = True

        session.reset_guardrail_state()

        assert session.guardrail_tier == 1
        assert session.guardrail_prompted is False

    def test_record_tool_call(self) -> None:
        """record_tool_call should store last tool info."""
        session = SessionState()

        session.record_tool_call(
            tool="search_code",
            arguments={"query": "test"},
            response="Found 5 results",
        )

        assert session.last_tool == "search_code"
        assert session.last_arguments == {"query": "test"}
        assert session.last_response == "Found 5 results"


class TestSessionContextVars:
    """Tests for context variable session management."""

    def test_get_current_session_creates_new(self) -> None:
        """get_current_session should create session if none exists."""
        reset_session()  # Clear any existing
        session = get_current_session()

        assert session is not None
        assert isinstance(session, SessionState)

    def test_get_current_session_returns_same(self) -> None:
        """get_current_session should return same session on repeated calls."""
        reset_session()
        session1 = get_current_session()
        session2 = get_current_session()

        assert session1 is session2
        assert session1.id == session2.id

    def test_set_current_session(self) -> None:
        """set_current_session should replace current session."""
        reset_session()
        original = get_current_session()

        new_session = SessionState()
        new_session.team_id = "custom_team"
        set_current_session(new_session)

        current = get_current_session()
        assert current is new_session
        assert current.team_id == "custom_team"
        assert current.id != original.id

    def test_reset_session(self) -> None:
        """reset_session should create fresh session."""
        session1 = get_current_session()
        session1.team_id = "team_a"
        session1.guardrail_tier = 3

        session2 = reset_session()

        assert session2.id != session1.id
        assert session2.team_id is None
        assert session2.guardrail_tier == 1

        # Should be the current session now
        assert get_current_session() is session2
