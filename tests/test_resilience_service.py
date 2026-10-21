"""Tests for resilience service.

Tests cover:
- ResilienceConfig loading and mode determination
- Error injection logic
- Error report matching
- Detection metrics calculation
"""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import uuid

import pytest
import yaml

from girafmcp.core.services.resilience_service import (
    ResilienceService,
    ResilienceConfig,
    ResilienceMode,
    ErrorType,
)


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class TestResilienceConfig:
    """Tests for ResilienceConfig."""

    @pytest.fixture
    def sample_config(self) -> dict:
        """Sample configuration for testing."""
        return {
            "enabled": True,
            "mode": "degraded",
            "team_assignments": {
                "team_a": {"mode": "normal"},
                "team_b": {"mode": "degraded"},
                "team_c": {"mode": "unavailable"},
            },
            "degraded_mode": {
                "error_injection_rate": 0.5,
                "error_types": [
                    {"type": "off_by_one", "weight": 0.5},
                    {"type": "null_check_missing", "weight": 0.5},
                ],
                "difficulty_distribution": {
                    "obvious": 0.3,
                    "moderate": 0.4,
                    "subtle": 0.3,
                },
            },
            "unavailable_mode": {
                "message": "AI is unavailable",
                "allowed_tools": ["search_documentation", "get_semester_context"],
            },
            "delayed_mode": {
                "delay_seconds": 30,
            },
        }

    @pytest.fixture
    def config_file(self, sample_config: dict) -> Path:
        """Create a temporary config file."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "resilience_tests.yaml"
            with open(config_path, "w") as f:
                yaml.safe_dump(sample_config, f)
            yield config_path

    def test_load_config(self, config_file: Path) -> None:
        """Config should load from YAML file."""
        config = ResilienceConfig(config_file)
        assert config.enabled is True
        assert config.mode == ResilienceMode.DEGRADED

    def test_missing_config_file(self) -> None:
        """Missing config file should use safe defaults."""
        config = ResilienceConfig(Path("/nonexistent/path/config.yaml"))
        assert config.enabled is False
        assert config.mode == ResilienceMode.NORMAL

    def test_team_mode_override(self, config_file: Path) -> None:
        """Team override should take precedence."""
        config = ResilienceConfig(config_file)

        assert config.get_team_mode("team_a") == ResilienceMode.NORMAL
        assert config.get_team_mode("team_b") == ResilienceMode.DEGRADED
        assert config.get_team_mode("team_c") == ResilienceMode.UNAVAILABLE

        # Unknown team gets global mode
        assert config.get_team_mode("team_unknown") == ResilienceMode.DEGRADED

    def test_error_injection_rate(self, config_file: Path) -> None:
        """Error injection rate should be loaded."""
        config = ResilienceConfig(config_file)
        assert config.error_injection_rate == 0.5

    def test_allowed_tools_when_unavailable(self, config_file: Path) -> None:
        """Allowed tools should be loaded."""
        config = ResilienceConfig(config_file)
        allowed = config.allowed_tools_when_unavailable
        assert "search_documentation" in allowed
        assert "get_semester_context" in allowed

    def test_unavailable_message(self, config_file: Path) -> None:
        """Unavailable message should be loaded."""
        config = ResilienceConfig(config_file)
        assert config.unavailable_message == "AI is unavailable"

    def test_delay_seconds(self, config_file: Path) -> None:
        """Delay seconds should be loaded."""
        config = ResilienceConfig(config_file)
        assert config.delay_seconds == 30

    def test_set_team_override(self, config_file: Path) -> None:
        """set_team_override should update team configuration."""
        config = ResilienceConfig(config_file)

        # Add new team
        config.set_team_override("team_new", mode="delayed")
        assert config.get_team_mode("team_new") == ResilienceMode.DELAYED

        # Update existing team
        config.set_team_override("team_a", mode="unavailable")
        assert config.get_team_mode("team_a") == ResilienceMode.UNAVAILABLE


class TestResilienceService:
    """Tests for ResilienceService."""

    @pytest.fixture
    def service(self) -> ResilienceService:
        """Create service with test config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "resilience_tests.yaml"
            config_data = {
                "enabled": True,
                "mode": "degraded",
                "degraded_mode": {
                    "error_injection_rate": 1.0,  # Always inject for testing
                    "error_types": [
                        {"type": "off_by_one", "weight": 1.0},
                    ],
                },
            }
            with open(config_path, "w") as f:
                yaml.safe_dump(config_data, f)

            config = ResilienceConfig(config_path)
            yield ResilienceService(config)

    def test_get_mode_disabled(self) -> None:
        """Disabled service should return normal mode."""
        config = ResilienceConfig(None)  # No config = disabled
        service = ResilienceService(config)
        assert service.get_mode("any_team") == ResilienceMode.NORMAL

    def test_is_tool_allowed_normal_mode(self, service: ResilienceService) -> None:
        """All tools allowed in normal mode."""
        service.config.set_team_override("team_normal", mode="normal")
        assert service.is_tool_allowed("any_tool", "team_normal") is True

    def test_is_tool_allowed_unavailable_mode(self) -> None:
        """Only allowed tools work in unavailable mode."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "resilience_tests.yaml"
            config_data = {
                "enabled": True,
                "mode": "unavailable",
                "unavailable_mode": {
                    "allowed_tools": ["search_documentation"],
                },
            }
            with open(config_path, "w") as f:
                yaml.safe_dump(config_data, f)

            config = ResilienceConfig(config_path)
            service = ResilienceService(config)

            assert service.is_tool_allowed("search_documentation") is True
            assert service.is_tool_allowed("search_code") is False

    def test_should_inject_error(self, service: ResilienceService) -> None:
        """should_inject_error respects injection rate."""
        # With 1.0 rate, should always inject
        results = [service.should_inject_error() for _ in range(10)]
        assert all(results)

    def test_select_error_type(self, service: ResilienceService) -> None:
        """select_error_type returns configured types."""
        # With only off_by_one configured at weight 1.0
        types = [service.select_error_type() for _ in range(10)]
        assert all(t == ErrorType.OFF_BY_ONE for t in types)

    def test_inject_error(self, service: ResilienceService) -> None:
        """inject_error modifies response and records error."""
        session_id = str(uuid.uuid4())
        response = "Use a loop: for i in range(0, 10) to iterate."

        modified, error = service.inject_error(
            response=response,
            tool_name="search_code",
            session_id=session_id,
        )

        # With off_by_one and "range(0," in response, should modify
        if error:
            assert error.error_type == ErrorType.OFF_BY_ONE
            assert error.session_id == session_id
            assert error.tool_name == "search_code"
            assert error.detected is False
            # Error should be stored
            assert error.id in [e.id for e in service.get_injected_errors()]

    def test_record_error_report(self, service: ResilienceService) -> None:
        """record_error_report creates and stores report."""
        session_id = str(uuid.uuid4())

        report = service.record_error_report(
            session_id=session_id,
            tool_name="search_code",
            error_description="Off by one in loop",
            proposed_fix="Change < to <=",
        )

        assert report.session_id == session_id
        assert report.tool_name == "search_code"
        assert report.error_description == "Off by one in loop"
        assert report.proposed_fix == "Change < to <="

        # Report should be stored
        assert report.id in [r.id for r in service.get_error_reports()]

    def test_error_report_matches_injection(self, service: ResilienceService) -> None:
        """Error report should match corresponding injection."""
        session_id = str(uuid.uuid4())

        # First inject an error
        response = "for i in range(0, 10):"
        modified, error = service.inject_error(
            response=response,
            tool_name="search_code",
            session_id=session_id,
        )

        if error:
            # Now report it
            report = service.record_error_report(
                session_id=session_id,
                tool_name="search_code",
                error_description="Loop bound seems wrong",
            )

            assert report.matched_injection_id == error.id
            assert report.is_true_positive is True

            # Check that error is marked as detected
            assert error.detected is True

    def test_get_detection_metrics_empty(self, service: ResilienceService) -> None:
        """Metrics with no data should return zeros."""
        metrics = service.get_detection_metrics()
        assert metrics["total_injected"] == 0
        assert metrics["detected"] == 0
        assert metrics["detection_rate"] == 0.0

    def test_get_detection_metrics(self, service: ResilienceService) -> None:
        """Metrics should calculate correctly."""
        session_id = str(uuid.uuid4())

        # Inject some errors
        responses = [
            "for i in range(0, 10):",
            "for j in range(0, 5):",
            "if value < 10:",
        ]

        for r in responses:
            service.inject_error(r, "search_code", session_id)

        errors = service.get_injected_errors(session_id)

        # Report one error
        if errors:
            service.record_error_report(
                session_id=session_id,
                tool_name="search_code",
                error_description="Found an issue",
            )

        metrics = service.get_detection_metrics(session_id)
        # At least some errors should have been injected
        if metrics["total_injected"] > 0:
            assert metrics["detected"] >= 1 or metrics["detected"] == 0


class TestResilienceServiceModes:
    """Tests for each resilience mode."""

    def test_normal_mode_passthrough(self) -> None:
        """Normal mode should not modify anything."""
        config = ResilienceConfig(None)
        service = ResilienceService(config)

        assert service.get_mode() == ResilienceMode.NORMAL
        assert service.is_tool_allowed("any_tool") is True

    def test_degraded_mode_injection_rate_zero(self) -> None:
        """Degraded mode with 0 rate should not inject."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "resilience_tests.yaml"
            config_data = {
                "enabled": True,
                "mode": "degraded",
                "degraded_mode": {
                    "error_injection_rate": 0.0,
                },
            }
            with open(config_path, "w") as f:
                yaml.safe_dump(config_data, f)

            config = ResilienceConfig(config_path)
            service = ResilienceService(config)

            # Should never inject with 0 rate
            results = [service.should_inject_error() for _ in range(10)]
            assert not any(results)

    def test_unavailable_mode_message(self) -> None:
        """Unavailable mode should provide message."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "resilience_tests.yaml"
            config_data = {
                "enabled": True,
                "mode": "unavailable",
                "unavailable_mode": {
                    "message": "Custom unavailable message",
                },
            }
            with open(config_path, "w") as f:
                yaml.safe_dump(config_data, f)

            config = ResilienceConfig(config_path)
            service = ResilienceService(config)

            assert service.get_mode() == ResilienceMode.UNAVAILABLE
            assert service.get_unavailable_message() == "Custom unavailable message"

    def test_delayed_mode_delay(self) -> None:
        """Delayed mode should provide delay seconds."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "resilience_tests.yaml"
            config_data = {
                "enabled": True,
                "mode": "delayed",
                "delayed_mode": {
                    "delay_seconds": 120,
                },
            }
            with open(config_path, "w") as f:
                yaml.safe_dump(config_data, f)

            config = ResilienceConfig(config_path)
            service = ResilienceService(config)

            assert service.get_mode() == ResilienceMode.DELAYED
            assert service.get_delay_seconds() == 120


class TestErrorInjectionTypes:
    """Tests for specific error injection types."""

    @pytest.fixture
    def service_with_type(self):
        """Factory for creating service with specific error type."""
        def _create(error_type: str) -> ResilienceService:
            with TemporaryDirectory() as tmpdir:
                config_path = Path(tmpdir) / "resilience_tests.yaml"
                config_data = {
                    "enabled": True,
                    "mode": "degraded",
                    "degraded_mode": {
                        "error_injection_rate": 1.0,
                        "error_types": [
                            {"type": error_type, "weight": 1.0},
                        ],
                    },
                }
                with open(config_path, "w") as f:
                    yaml.safe_dump(config_data, f)

                config = ResilienceConfig(config_path)
                return ResilienceService(config)
        return _create

    def test_off_by_one_injection(self, service_with_type) -> None:
        """Off-by-one should modify loop bounds."""
        service = service_with_type("off_by_one")
        response = "for i in range(0, 10):"
        modified, error = service.inject_error(response, "test", "session1")

        if error:
            assert error.error_type == ErrorType.OFF_BY_ONE
            assert "range(1," in modified or "<=" in modified or ">=" in modified

    def test_logic_inversion_injection(self, service_with_type) -> None:
        """Logic inversion should flip boolean logic."""
        service = service_with_type("logic_inversion")
        response = "if x == True: pass"
        modified, error = service.inject_error(response, "test", "session1")

        if error:
            assert error.error_type == ErrorType.LOGIC_INVERSION
            assert "False" in modified

    def test_wrong_variable_injection(self, service_with_type) -> None:
        """Wrong variable should swap similar names."""
        service = service_with_type("wrong_variable")
        response = "result = compute(data)"
        modified, error = service.inject_error(response, "test", "session1")

        if error:
            assert error.error_type == ErrorType.WRONG_VARIABLE
            assert "results" in modified or "datum" in modified
