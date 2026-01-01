"""Feature toggle registry for research features.

Provides environment-variable-driven feature toggles that control
which research features are enabled at runtime.
"""

from dataclasses import dataclass
from enum import Enum
import os


class Feature(Enum):
    """Available research features.

    Each feature has an associated environment variable that controls
    whether it's enabled.
    """

    QUERY_LOGGING = "GIRAF_QUERY_LOGGING_ENABLED"
    GUARDRAILS = "GIRAF_GUARDRAILS_ENABLED"
    RESILIENCE = "GIRAF_RESILIENCE_ENABLED"
    DISCIPLINE_FRAMING = "GIRAF_DISCIPLINE_FRAMING_ENABLED"
    KNOWLEDGE_CAPTURE = "GIRAF_KNOWLEDGE_CAPTURE_ENABLED"


@dataclass
class FeatureState:
    """State of a feature toggle."""

    feature: Feature
    enabled: bool
    default: bool
    env_var: str


class FeatureRegistry:
    """Central registry for feature toggles.

    Provides methods to check if features are enabled and to inspect
    the state of all features.
    """

    # Default values for each feature
    DEFAULTS: dict[Feature, bool] = {
        Feature.QUERY_LOGGING: True,
        Feature.GUARDRAILS: True,
        Feature.RESILIENCE: False,  # Off by default - enable during assessment
        Feature.DISCIPLINE_FRAMING: True,
        Feature.KNOWLEDGE_CAPTURE: True,
    }

    @classmethod
    def is_enabled(cls, feature: Feature) -> bool:
        """Check if a feature is enabled.

        Reads from environment variable, falling back to default if not set.

        Args:
            feature: The feature to check

        Returns:
            True if the feature is enabled
        """
        env_var = feature.value
        default = cls.DEFAULTS.get(feature, False)
        value = os.getenv(env_var, str(default).lower())
        return value.lower() in ("true", "1", "yes")

    @classmethod
    def get_state(cls, feature: Feature) -> FeatureState:
        """Get the full state of a feature.

        Args:
            feature: The feature to inspect

        Returns:
            FeatureState with all toggle information
        """
        return FeatureState(
            feature=feature,
            enabled=cls.is_enabled(feature),
            default=cls.DEFAULTS.get(feature, False),
            env_var=feature.value,
        )

    @classmethod
    def get_all_states(cls) -> list[FeatureState]:
        """Get all feature states for introspection.

        Returns:
            List of FeatureState for all features
        """
        return [cls.get_state(f) for f in Feature]

    @classmethod
    def set_override(cls, feature: Feature, enabled: bool) -> None:
        """Override a feature's state via environment variable.

        Useful for testing. Sets the environment variable directly.

        Args:
            feature: The feature to override
            enabled: Whether to enable the feature
        """
        os.environ[feature.value] = str(enabled).lower()

    @classmethod
    def clear_override(cls, feature: Feature) -> None:
        """Clear a feature override, returning to default.

        Args:
            feature: The feature to clear
        """
        env_var = feature.value
        if env_var in os.environ:
            del os.environ[env_var]


# Convenience functions for common checks
def is_logging_enabled() -> bool:
    """Check if query logging is enabled."""
    return FeatureRegistry.is_enabled(Feature.QUERY_LOGGING)


def is_guardrails_enabled() -> bool:
    """Check if guardrails are enabled."""
    return FeatureRegistry.is_enabled(Feature.GUARDRAILS)


def is_resilience_enabled() -> bool:
    """Check if resilience testing is enabled."""
    return FeatureRegistry.is_enabled(Feature.RESILIENCE)


def is_discipline_framing_enabled() -> bool:
    """Check if cross-disciplinary framing is enabled."""
    return FeatureRegistry.is_enabled(Feature.DISCIPLINE_FRAMING)


def is_knowledge_capture_enabled() -> bool:
    """Check if knowledge capture is enabled."""
    return FeatureRegistry.is_enabled(Feature.KNOWLEDGE_CAPTURE)
