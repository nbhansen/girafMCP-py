"""Tests for feature toggle registry."""

import os

import pytest

from girafmcp.core.features import (
    Feature,
    FeatureRegistry,
    is_discipline_framing_enabled,
    is_guardrails_enabled,
    is_knowledge_capture_enabled,
    is_logging_enabled,
    is_resilience_enabled,
)


class TestFeatureRegistry:
    """Tests for FeatureRegistry."""

    @pytest.fixture(autouse=True)
    def clean_env(self):
        """Clear all feature env vars before and after each test."""
        for feature in Feature:
            if feature.value in os.environ:
                del os.environ[feature.value]
        yield
        for feature in Feature:
            if feature.value in os.environ:
                del os.environ[feature.value]

    def test_default_values(self) -> None:
        """Features should have expected defaults."""
        assert FeatureRegistry.is_enabled(Feature.QUERY_LOGGING) is True
        assert FeatureRegistry.is_enabled(Feature.GUARDRAILS) is True
        assert FeatureRegistry.is_enabled(Feature.RESILIENCE) is False
        assert FeatureRegistry.is_enabled(Feature.DISCIPLINE_FRAMING) is True
        assert FeatureRegistry.is_enabled(Feature.KNOWLEDGE_CAPTURE) is True

    def test_env_var_override_true(self) -> None:
        """Setting env var to true should enable feature."""
        os.environ["GIRAF_RESILIENCE_ENABLED"] = "true"
        assert FeatureRegistry.is_enabled(Feature.RESILIENCE) is True

        os.environ["GIRAF_RESILIENCE_ENABLED"] = "1"
        assert FeatureRegistry.is_enabled(Feature.RESILIENCE) is True

        os.environ["GIRAF_RESILIENCE_ENABLED"] = "yes"
        assert FeatureRegistry.is_enabled(Feature.RESILIENCE) is True

        os.environ["GIRAF_RESILIENCE_ENABLED"] = "TRUE"
        assert FeatureRegistry.is_enabled(Feature.RESILIENCE) is True

    def test_env_var_override_false(self) -> None:
        """Setting env var to false should disable feature."""
        os.environ["GIRAF_QUERY_LOGGING_ENABLED"] = "false"
        assert FeatureRegistry.is_enabled(Feature.QUERY_LOGGING) is False

        os.environ["GIRAF_QUERY_LOGGING_ENABLED"] = "0"
        assert FeatureRegistry.is_enabled(Feature.QUERY_LOGGING) is False

        os.environ["GIRAF_QUERY_LOGGING_ENABLED"] = "no"
        assert FeatureRegistry.is_enabled(Feature.QUERY_LOGGING) is False

    def test_get_state(self) -> None:
        """get_state should return full feature info."""
        state = FeatureRegistry.get_state(Feature.RESILIENCE)

        assert state.feature == Feature.RESILIENCE
        assert state.enabled is False  # Default
        assert state.default is False
        assert state.env_var == "GIRAF_RESILIENCE_ENABLED"

    def test_get_state_with_override(self) -> None:
        """get_state should reflect env var override."""
        os.environ["GIRAF_RESILIENCE_ENABLED"] = "true"
        state = FeatureRegistry.get_state(Feature.RESILIENCE)

        assert state.enabled is True
        assert state.default is False  # Default unchanged

    def test_get_all_states(self) -> None:
        """get_all_states should return all features."""
        states = FeatureRegistry.get_all_states()

        assert len(states) == len(Feature)
        features = {s.feature for s in states}
        assert features == set(Feature)

    def test_set_override(self) -> None:
        """set_override should set env var."""
        FeatureRegistry.set_override(Feature.RESILIENCE, True)
        assert os.environ.get("GIRAF_RESILIENCE_ENABLED") == "true"
        assert FeatureRegistry.is_enabled(Feature.RESILIENCE) is True

        FeatureRegistry.set_override(Feature.RESILIENCE, False)
        assert os.environ.get("GIRAF_RESILIENCE_ENABLED") == "false"
        assert FeatureRegistry.is_enabled(Feature.RESILIENCE) is False

    def test_clear_override(self) -> None:
        """clear_override should remove env var."""
        os.environ["GIRAF_RESILIENCE_ENABLED"] = "true"
        FeatureRegistry.clear_override(Feature.RESILIENCE)

        assert "GIRAF_RESILIENCE_ENABLED" not in os.environ
        assert FeatureRegistry.is_enabled(Feature.RESILIENCE) is False  # Back to default

    def test_clear_override_no_env_var(self) -> None:
        """clear_override should not fail if env var not set."""
        # Should not raise
        FeatureRegistry.clear_override(Feature.RESILIENCE)


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.fixture(autouse=True)
    def clean_env(self):
        """Clear all feature env vars before and after each test."""
        for feature in Feature:
            if feature.value in os.environ:
                del os.environ[feature.value]
        yield
        for feature in Feature:
            if feature.value in os.environ:
                del os.environ[feature.value]

    def test_is_logging_enabled(self) -> None:
        """is_logging_enabled should check QUERY_LOGGING."""
        assert is_logging_enabled() is True  # Default

        os.environ["GIRAF_QUERY_LOGGING_ENABLED"] = "false"
        assert is_logging_enabled() is False

    def test_is_guardrails_enabled(self) -> None:
        """is_guardrails_enabled should check GUARDRAILS."""
        assert is_guardrails_enabled() is True  # Default

        os.environ["GIRAF_GUARDRAILS_ENABLED"] = "false"
        assert is_guardrails_enabled() is False

    def test_is_resilience_enabled(self) -> None:
        """is_resilience_enabled should check RESILIENCE."""
        assert is_resilience_enabled() is False  # Default

        os.environ["GIRAF_RESILIENCE_ENABLED"] = "true"
        assert is_resilience_enabled() is True

    def test_is_discipline_framing_enabled(self) -> None:
        """is_discipline_framing_enabled should check DISCIPLINE_FRAMING."""
        assert is_discipline_framing_enabled() is True  # Default

        os.environ["GIRAF_DISCIPLINE_FRAMING_ENABLED"] = "false"
        assert is_discipline_framing_enabled() is False

    def test_is_knowledge_capture_enabled(self) -> None:
        """is_knowledge_capture_enabled should check KNOWLEDGE_CAPTURE."""
        assert is_knowledge_capture_enabled() is True  # Default

        os.environ["GIRAF_KNOWLEDGE_CAPTURE_ENABLED"] = "false"
        assert is_knowledge_capture_enabled() is False
