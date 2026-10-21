"""Tests for guardrails service."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from girafmcp.core.services.guardrails_service import (
    GuardrailMode,
    GuardrailsConfig,
    GuardrailsService,
)


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(UTC)


class TestGuardrailsConfig:
    """Tests for GuardrailsConfig."""

    @pytest.fixture
    def sample_config(self) -> dict:
        """Sample configuration for testing."""
        return {
            "enabled": True,
            "mode": "tiered",
            "team_overrides": {
                "team_a": {"enabled": True, "mode": "tiered"},
                "team_b": {"enabled": False, "mode": "off"},
                "team_c": {"enabled": True, "mode": "cooldown"},
            },
            "guarded_tools": ["search_code", "get_file"],
            "exempt_tools": ["list_repositories", "get_semester_context"],
            "tiers": {
                1: {
                    "name": "hint",
                    "description": "Conceptual hint",
                    "prompt_suffix": "This is tier 1 suffix",
                },
                2: {
                    "name": "guidance",
                    "description": "Specific guidance",
                    "prompt_suffix": "This is tier 2 suffix",
                },
                4: {
                    "name": "solution",
                    "description": "Full solution",
                    "prompt_suffix": None,
                },
            },
            "cooldown": {"delay_seconds": 30, "reflection_prompt": "Wait {remaining_seconds}s"},
            "attempt_first": {
                "prompt": "What have you tried?",
                "bypass_indicators": ["i tried", "doesn't work", "error"],
            },
        }

    @pytest.fixture
    def config_file(self, sample_config: dict) -> Path:
        """Create a temporary config file."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "guardrails.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(sample_config, f)
            yield config_path

    def test_load_config(self, config_file: Path) -> None:
        """Config should load from YAML file."""
        config = GuardrailsConfig(config_file)
        assert config.enabled is True
        assert config.mode == GuardrailMode.TIERED

    def test_missing_config_file(self) -> None:
        """Missing config file should use safe defaults."""
        config = GuardrailsConfig(Path("/nonexistent/path/guardrails.yaml"))
        # When config is missing, enabled defaults to True but mode defaults to OFF
        # This means guardrails are technically "enabled" but in OFF mode (no intervention)
        assert config.enabled is True  # Default
        assert config.mode == GuardrailMode.OFF  # Safe default - no intervention

    def test_global_mode(self, config_file: Path) -> None:
        """Global mode should be returned when no team override."""
        config = GuardrailsConfig(config_file)
        assert config.mode == GuardrailMode.TIERED

    def test_team_mode_override(self, config_file: Path) -> None:
        """Team override should take precedence."""
        config = GuardrailsConfig(config_file)

        # Team with tiered mode
        assert config.get_team_mode("team_a") == GuardrailMode.TIERED

        # Team with disabled guardrails
        assert config.get_team_mode("team_b") == GuardrailMode.OFF

        # Team with cooldown mode
        assert config.get_team_mode("team_c") == GuardrailMode.COOLDOWN

        # Unknown team gets global mode
        assert config.get_team_mode("team_unknown") == GuardrailMode.TIERED

        # None team gets global mode
        assert config.get_team_mode(None) == GuardrailMode.TIERED

    def test_is_team_enabled(self, config_file: Path) -> None:
        """is_team_enabled should check effective mode."""
        config = GuardrailsConfig(config_file)

        assert config.is_team_enabled("team_a") is True
        assert config.is_team_enabled("team_b") is False
        assert config.is_team_enabled("team_c") is True
        assert config.is_team_enabled(None) is True

    def test_guarded_tools(self, config_file: Path) -> None:
        """should_guard should check guarded and exempt tools."""
        config = GuardrailsConfig(config_file)

        # Guarded tools
        assert config.should_guard("search_code") is True
        assert config.should_guard("get_file") is True

        # Exempt tools
        assert config.should_guard("list_repositories") is False
        assert config.should_guard("get_semester_context") is False

        # Unknown tool - not in guarded list
        assert config.should_guard("unknown_tool") is False

    def test_exempt_tools_take_precedence(self, sample_config: dict) -> None:
        """Exempt tools should not be guarded even if in guarded list."""
        # Add list_repositories to guarded_tools as well
        sample_config["guarded_tools"].append("list_repositories")

        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "guardrails.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(sample_config, f)

            config = GuardrailsConfig(config_path)
            # Should still be exempt
            assert config.should_guard("list_repositories") is False

    def test_tier_config(self, config_file: Path) -> None:
        """get_tier_config should return tier configuration."""
        config = GuardrailsConfig(config_file)

        tier1 = config.get_tier_config(1)
        assert tier1 is not None
        assert tier1.name == "hint"
        assert tier1.prompt_suffix == "This is tier 1 suffix"

        tier4 = config.get_tier_config(4)
        assert tier4 is not None
        assert tier4.prompt_suffix is None

        tier3 = config.get_tier_config(3)
        assert tier3 is None

    def test_max_tier(self, config_file: Path) -> None:
        """max_tier should return highest tier number."""
        config = GuardrailsConfig(config_file)
        assert config.max_tier == 4

    def test_cooldown_settings(self, config_file: Path) -> None:
        """Cooldown settings should be loaded."""
        config = GuardrailsConfig(config_file)
        assert config.cooldown_delay_seconds == 30
        assert "remaining_seconds" in config.cooldown_reflection_prompt

    def test_bypass_indicators(self, config_file: Path) -> None:
        """Bypass indicators should be detected."""
        config = GuardrailsConfig(config_file)

        assert config.has_bypass_indicator("I tried something") is True
        assert config.has_bypass_indicator("It doesn't work") is True
        assert config.has_bypass_indicator("Getting an error") is True
        assert config.has_bypass_indicator("How do I...") is False
        assert config.has_bypass_indicator(None) is False

    def test_set_team_override(self, config_file: Path) -> None:
        """set_team_override should update team configuration."""
        config = GuardrailsConfig(config_file)

        # Add new team
        config.set_team_override("team_new", enabled=True, mode="prompt")
        assert config.get_team_mode("team_new") == GuardrailMode.PROMPT

        # Update existing team
        config.set_team_override("team_a", mode="cooldown")
        assert config.get_team_mode("team_a") == GuardrailMode.COOLDOWN

        # Disable existing team
        config.set_team_override("team_c", enabled=False)
        assert config.is_team_enabled("team_c") is False


class TestGuardrailsService:
    """Tests for GuardrailsService."""

    @pytest.fixture
    def sample_config(self) -> dict:
        """Sample configuration for testing."""
        return {
            "enabled": True,
            "mode": "tiered",
            "guarded_tools": ["search_code", "get_file"],
            "exempt_tools": ["list_repositories"],
            "tiers": {
                1: {"name": "hint", "prompt_suffix": "Tier 1 suffix"},
                2: {"name": "guidance", "prompt_suffix": "Tier 2 suffix"},
                3: {"name": "example", "prompt_suffix": "Tier 3 suffix"},
                4: {"name": "solution", "prompt_suffix": None},
            },
            "cooldown": {"delay_seconds": 30, "reflection_prompt": "Wait {remaining_seconds}s"},
            "attempt_first": {
                "prompt": "What have you tried?",
                "bypass_indicators": ["i tried"],
            },
        }

    @pytest.fixture
    def service(self, sample_config: dict) -> GuardrailsService:
        """Create service with test config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "guardrails.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(sample_config, f)

            config = GuardrailsConfig(config_path)
            yield GuardrailsService(config)

    def test_exempt_tool_allowed(self, service: GuardrailsService) -> None:
        """Exempt tools should always be allowed."""
        decision = service.get_decision(
            tool_name="list_repositories",
            query_text="list all repos",
            team_id=None,
            session_tier=1,
            session_prompted=False,
            cooldown_until=None,
        )
        assert decision.action == "allow"

    def test_tiered_mode_tier1(self, service: GuardrailsService) -> None:
        """Tiered mode at tier 1 should return tier decision."""
        decision = service.get_decision(
            tool_name="search_code",
            query_text="search for something",
            team_id=None,
            session_tier=1,
            session_prompted=False,
            cooldown_until=None,
        )
        assert decision.action == "tier"
        assert decision.tier == 1
        assert "Tier 1 suffix" in (decision.tier_suffix or "")

    def test_tiered_mode_tier4(self, service: GuardrailsService) -> None:
        """Tiered mode at tier 4 should allow (full solution)."""
        decision = service.get_decision(
            tool_name="search_code",
            query_text="search for something",
            team_id=None,
            session_tier=4,
            session_prompted=False,
            cooldown_until=None,
        )
        assert decision.action == "allow"
        assert decision.tier == 4

    def test_cooldown_calculation(self, service: GuardrailsService) -> None:
        """calculate_cooldown_end should return future time."""
        now = _utcnow()
        cooldown_end = service.calculate_cooldown_end()

        assert cooldown_end > now
        # Should be approximately 30 seconds in future
        delta = (cooldown_end - now).total_seconds()
        assert 29 <= delta <= 31


class TestGuardrailsPromptMode:
    """Tests for prompt mode behavior."""

    @pytest.fixture
    def prompt_service(self) -> GuardrailsService:
        """Create service in prompt mode."""
        config_data = {
            "enabled": True,
            "mode": "prompt",
            "guarded_tools": ["search_code"],
            "attempt_first": {
                "prompt": "What have you tried so far?",
                "bypass_indicators": ["i tried", "error message"],
            },
        }
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "guardrails.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(config_data, f)

            config = GuardrailsConfig(config_path)
            yield GuardrailsService(config)

    def test_prompt_on_first_request(self, prompt_service: GuardrailsService) -> None:
        """First request should get prompt."""
        decision = prompt_service.get_decision(
            tool_name="search_code",
            query_text="How do I do X?",
            team_id=None,
            session_tier=1,
            session_prompted=False,
            cooldown_until=None,
        )
        assert decision.action == "prompt"
        assert "What have you tried" in (decision.response or "")

    def test_bypass_with_indicator(self, prompt_service: GuardrailsService) -> None:
        """Query with bypass indicator should skip prompt."""
        decision = prompt_service.get_decision(
            tool_name="search_code",
            query_text="I tried doing X but got an error message",
            team_id=None,
            session_tier=1,
            session_prompted=False,
            cooldown_until=None,
        )
        assert decision.action == "allow"

    def test_allow_after_prompted(self, prompt_service: GuardrailsService) -> None:
        """After prompting, should allow request."""
        decision = prompt_service.get_decision(
            tool_name="search_code",
            query_text="How do I do X?",
            team_id=None,
            session_tier=1,
            session_prompted=True,  # Already prompted
            cooldown_until=None,
        )
        assert decision.action == "allow"


class TestGuardrailsCooldownMode:
    """Tests for cooldown mode behavior."""

    @pytest.fixture
    def cooldown_service(self) -> GuardrailsService:
        """Create service in cooldown mode."""
        config_data = {
            "enabled": True,
            "mode": "cooldown",
            "guarded_tools": ["search_code"],
            "cooldown": {
                "delay_seconds": 30,
                "reflection_prompt": "Please wait {remaining_seconds} seconds.",
            },
        }
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "guardrails.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(config_data, f)

            config = GuardrailsConfig(config_path)
            yield GuardrailsService(config)

    def test_cooldown_start(self, cooldown_service: GuardrailsService) -> None:
        """First request without active cooldown should start cooldown."""
        decision = cooldown_service.get_decision(
            tool_name="search_code",
            query_text="How do I do X?",
            team_id=None,
            session_tier=1,
            session_prompted=False,
            cooldown_until=None,
        )
        assert decision.action == "cooldown_start"

    def test_cooldown_active(self, cooldown_service: GuardrailsService) -> None:
        """Request during active cooldown should return reflection prompt."""
        future_time = _utcnow() + timedelta(seconds=20)

        decision = cooldown_service.get_decision(
            tool_name="search_code",
            query_text="How do I do X?",
            team_id=None,
            session_tier=1,
            session_prompted=False,
            cooldown_until=future_time,
        )
        assert decision.action == "cooldown"
        assert "seconds" in (decision.response or "").lower()

    def test_cooldown_expired(self, cooldown_service: GuardrailsService) -> None:
        """Request after cooldown expires should start new cooldown."""
        past_time = _utcnow() - timedelta(seconds=10)

        decision = cooldown_service.get_decision(
            tool_name="search_code",
            query_text="How do I do X?",
            team_id=None,
            session_tier=1,
            session_prompted=False,
            cooldown_until=past_time,
        )
        assert decision.action == "cooldown_start"


class TestGuardrailsOffMode:
    """Tests for off mode behavior."""

    @pytest.fixture
    def off_service(self) -> GuardrailsService:
        """Create service in off mode."""
        config_data = {
            "enabled": True,
            "mode": "off",
            "guarded_tools": ["search_code"],
        }
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "guardrails.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(config_data, f)

            config = GuardrailsConfig(config_path)
            yield GuardrailsService(config)

    def test_off_mode_allows_all(self, off_service: GuardrailsService) -> None:
        """Off mode should allow all requests."""
        decision = off_service.get_decision(
            tool_name="search_code",
            query_text="How do I do X?",
            team_id=None,
            session_tier=1,
            session_prompted=False,
            cooldown_until=None,
        )
        assert decision.action == "allow"


class TestGuardrailsDisabled:
    """Tests for globally disabled guardrails."""

    @pytest.fixture
    def disabled_service(self) -> GuardrailsService:
        """Create service with guardrails disabled."""
        config_data = {
            "enabled": False,
            "mode": "tiered",
            "guarded_tools": ["search_code"],
        }
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "guardrails.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(config_data, f)

            config = GuardrailsConfig(config_path)
            yield GuardrailsService(config)

    def test_disabled_allows_all(self, disabled_service: GuardrailsService) -> None:
        """Disabled guardrails should allow all requests."""
        decision = disabled_service.get_decision(
            tool_name="search_code",
            query_text="How do I do X?",
            team_id=None,
            session_tier=1,
            session_prompted=False,
            cooldown_until=None,
        )
        assert decision.action == "allow"
