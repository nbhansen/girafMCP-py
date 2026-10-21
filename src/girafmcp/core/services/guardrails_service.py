"""Guardrails service for scaffolded AI responses.

Implements tiered response system to build student skills rather than dependency.
Supports multiple modes: off, prompt, tiered, and cooldown.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, cast

import yaml

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(UTC)


class GuardrailMode(Enum):
    """Available guardrail modes."""

    OFF = "off"
    PROMPT = "prompt"
    TIERED = "tiered"
    COOLDOWN = "cooldown"


@dataclass
class TierConfig:
    """Configuration for a response tier."""

    name: str
    description: str
    prompt_suffix: str | None


@dataclass
class GuardrailDecision:
    """Decision made by guardrails for a tool call.

    Contains the action to take and any response to return.
    """

    action: str  # "allow", "prompt", "tier", "cooldown"
    response: str | None = None  # Response to return if short-circuiting
    tier: int | None = None  # Current tier for tiered mode
    tier_suffix: str | None = None  # Suffix to append to response


class GuardrailsConfig:
    """Configuration loaded from guardrails.yaml."""

    def __init__(self, config_path: Path | None = None):
        """Initialize guardrails configuration.

        Args:
            config_path: Path to guardrails.yaml. If None, uses default location.
        """
        self._config: dict[str, Any] = {}
        self._config_path = config_path or self._default_config_path()
        self._load_config()

    def _default_config_path(self) -> Path:
        """Get the default configuration path."""
        # Look for data/guardrails.yaml relative to project root
        current = Path(__file__).parent
        # Go up: services -> core -> girafmcp -> src -> project_root
        project_root = current.parent.parent.parent.parent
        return project_root / "data" / "guardrails.yaml"

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if self._config_path.exists():
            try:
                with open(self._config_path) as f:
                    self._config = yaml.safe_load(f) or {}
                logger.info(f"Loaded guardrails config from {self._config_path}")
            except (OSError, yaml.YAMLError) as e:
                logger.warning(f"Failed to load guardrails config: {e}")
                self._config = {}
        else:
            logger.info(f"Guardrails config not found at {self._config_path}, using defaults")
            self._config = {}

    def reload(self) -> None:
        """Reload configuration from disk."""
        self._load_config()

    @property
    def enabled(self) -> bool:
        """Check if guardrails are enabled globally."""
        return cast(bool, self._config.get("enabled", True))

    @property
    def mode(self) -> GuardrailMode:
        """Get the global guardrail mode."""
        mode_str = self._config.get("mode", "off")
        try:
            return GuardrailMode(mode_str)
        except ValueError:
            logger.warning(f"Invalid guardrail mode '{mode_str}', defaulting to OFF")
            return GuardrailMode.OFF

    def get_team_mode(self, team_id: str | None) -> GuardrailMode:
        """Get the effective guardrail mode for a team.

        Args:
            team_id: The team identifier, or None for global mode

        Returns:
            The effective GuardrailMode for this team
        """
        if not self.enabled:
            return GuardrailMode.OFF

        if team_id:
            overrides = self._config.get("team_overrides") or {}
            if team_id in overrides:
                override = overrides[team_id]
                if not override.get("enabled", True):
                    return GuardrailMode.OFF
                mode_str = override.get("mode", self._config.get("mode", "off"))
                try:
                    return GuardrailMode(mode_str)
                except ValueError:
                    pass

        return self.mode

    def is_team_enabled(self, team_id: str | None) -> bool:
        """Check if guardrails are enabled for a specific team.

        Args:
            team_id: The team identifier

        Returns:
            True if guardrails are enabled for this team
        """
        return self.get_team_mode(team_id) != GuardrailMode.OFF

    @property
    def guarded_tools(self) -> set[str]:
        """Get set of tools that trigger guardrails."""
        return set(self._config.get("guarded_tools", []))

    @property
    def exempt_tools(self) -> set[str]:
        """Get set of tools exempt from guardrails."""
        return set(self._config.get("exempt_tools", []))

    def should_guard(self, tool_name: str) -> bool:
        """Check if a tool should trigger guardrails.

        Args:
            tool_name: The name of the tool

        Returns:
            True if the tool should be guarded
        """
        if tool_name in self.exempt_tools:
            return False

        guarded = self.guarded_tools
        if guarded:
            return tool_name in guarded

        # If no guarded_tools specified, guard all non-exempt tools
        return True

    def get_tier_config(self, tier: int) -> TierConfig | None:
        """Get configuration for a specific tier.

        Args:
            tier: The tier number (1-4)

        Returns:
            TierConfig if found, None otherwise
        """
        tiers = self._config.get("tiers") or {}
        if tier in tiers:
            tier_data = tiers[tier]
            return TierConfig(
                name=tier_data.get("name", f"tier_{tier}"),
                description=tier_data.get("description", ""),
                prompt_suffix=tier_data.get("prompt_suffix"),
            )
        return None

    @property
    def max_tier(self) -> int:
        """Get the maximum tier number."""
        tiers = self._config.get("tiers") or {}
        if tiers:
            return cast(int, max(tiers.keys()))
        return 4

    @property
    def cooldown_delay_seconds(self) -> int:
        """Get cooldown delay in seconds."""
        return cast(int, (self._config.get("cooldown") or {}).get("delay_seconds", 30))

    @property
    def cooldown_reflection_prompt(self) -> str:
        """Get the cooldown reflection prompt template."""
        return cast(str, (self._config.get("cooldown") or {}).get(
            "reflection_prompt",
            "Please wait {remaining_seconds} seconds before receiving the full solution.",
        ))

    @property
    def attempt_first_prompt(self) -> str:
        """Get the attempt-first prompt for prompt mode."""
        return cast(str, (self._config.get("attempt_first") or {}).get(
            "prompt",
            "What have you tried so far?",
        ))

    @property
    def bypass_indicators(self) -> list[str]:
        """Get list of phrases that bypass the attempt-first prompt."""
        return cast(list[str], (self._config.get("attempt_first") or {}).get("bypass_indicators", []))

    def has_bypass_indicator(self, query_text: str | None) -> bool:
        """Check if query text contains a bypass indicator.

        Args:
            query_text: The query text to check

        Returns:
            True if a bypass indicator is found
        """
        if not query_text:
            return False

        query_lower = query_text.lower()
        return any(indicator in query_lower for indicator in self.bypass_indicators)

    def set_team_override(
        self,
        team_id: str,
        enabled: bool | None = None,
        mode: str | None = None,
    ) -> None:
        """Set a team-specific override.

        Args:
            team_id: The team to configure
            enabled: Whether guardrails are enabled for this team
            mode: The guardrail mode for this team
        """
        if "team_overrides" not in self._config:
            self._config["team_overrides"] = {}

        if team_id not in self._config["team_overrides"]:
            self._config["team_overrides"][team_id] = {}

        override = self._config["team_overrides"][team_id]
        if enabled is not None:
            override["enabled"] = enabled
        if mode is not None:
            override["mode"] = mode

    def save(self) -> None:
        """Save current configuration to disk."""
        with open(self._config_path, "w") as f:
            yaml.safe_dump(self._config, f, default_flow_style=False)
        logger.info(f"Saved guardrails config to {self._config_path}")


class GuardrailsService:
    """Service for managing guardrail behavior.

    Handles mode-specific logic for prompt, tiered, and cooldown modes.
    Integrates with session state for tier tracking and cooldown management.
    """

    def __init__(self, config: GuardrailsConfig | None = None):
        """Initialize the guardrails service.

        Args:
            config: GuardrailsConfig instance. If None, creates default config.
        """
        self.config = config or GuardrailsConfig()

    def get_decision(
        self,
        tool_name: str,
        query_text: str | None,
        team_id: str | None,
        session_tier: int,
        session_prompted: bool,
        cooldown_until: datetime | None,
    ) -> GuardrailDecision:
        """Get the guardrail decision for a tool call.

        Args:
            tool_name: The tool being called
            query_text: Extracted natural language query (if any)
            team_id: The team making the request
            session_tier: Current tier for the session
            session_prompted: Whether prompt was shown for current query
            cooldown_until: When cooldown expires (if in cooldown)

        Returns:
            GuardrailDecision with action and any response
        """
        # Check if this tool should be guarded
        if not self.config.should_guard(tool_name):
            return GuardrailDecision(action="allow")

        # Get mode for this team
        mode = self.config.get_team_mode(team_id)

        if mode == GuardrailMode.OFF:
            return GuardrailDecision(action="allow")

        elif mode == GuardrailMode.PROMPT:
            return self._get_prompt_decision(query_text, session_prompted)

        elif mode == GuardrailMode.TIERED:
            return self._get_tiered_decision(session_tier)

        elif mode == GuardrailMode.COOLDOWN:
            return self._get_cooldown_decision(cooldown_until)

        return GuardrailDecision(action="allow")

    def _get_prompt_decision(
        self,
        query_text: str | None,
        session_prompted: bool,
    ) -> GuardrailDecision:
        """Get decision for prompt mode.

        Args:
            query_text: The query text
            session_prompted: Whether we already prompted for this query

        Returns:
            GuardrailDecision
        """
        # If already prompted, allow
        if session_prompted:
            return GuardrailDecision(action="allow")

        # Check for bypass indicators
        if self.config.has_bypass_indicator(query_text):
            return GuardrailDecision(action="allow")

        # Return prompt
        return GuardrailDecision(
            action="prompt",
            response=self.config.attempt_first_prompt,
        )

    def _get_tiered_decision(self, session_tier: int) -> GuardrailDecision:
        """Get decision for tiered mode.

        Args:
            session_tier: Current tier (1-4)

        Returns:
            GuardrailDecision with tier info
        """
        tier_config = self.config.get_tier_config(session_tier)

        if tier_config and tier_config.prompt_suffix:
            return GuardrailDecision(
                action="tier",
                tier=session_tier,
                tier_suffix=tier_config.prompt_suffix,
            )

        # Tier 4 or no config: full response
        return GuardrailDecision(action="allow", tier=session_tier)

    def _get_cooldown_decision(
        self,
        cooldown_until: datetime | None,
    ) -> GuardrailDecision:
        """Get decision for cooldown mode.

        Args:
            cooldown_until: When current cooldown expires

        Returns:
            GuardrailDecision
        """
        now = _utcnow()

        if cooldown_until and cooldown_until > now:
            remaining = int((cooldown_until - now).total_seconds())
            prompt = self.config.cooldown_reflection_prompt.format(
                remaining_seconds=remaining
            )
            return GuardrailDecision(
                action="cooldown",
                response=prompt,
            )

        # Not in cooldown, allow but start new cooldown
        return GuardrailDecision(action="cooldown_start")

    def calculate_cooldown_end(self) -> datetime:
        """Calculate when a new cooldown should end.

        Returns:
            datetime when cooldown expires
        """
        return _utcnow() + timedelta(seconds=self.config.cooldown_delay_seconds)
