"""Resilience testing service for research assessment.

Manages intentional failure injection and AI unavailability scenarios
to test student verification skills, debugging ability, and independence.

WARNING: This feature should only be enabled during controlled assessment
periods with proper ethical oversight.
"""

import logging
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, cast

import yaml

logger = logging.getLogger(__name__)


class ResilienceMode(Enum):
    """Operating modes for resilience testing."""

    NORMAL = "normal"  # Standard AI assistance
    DEGRADED = "degraded"  # Intentionally flawed responses
    UNAVAILABLE = "unavailable"  # AI returns unavailable message
    DELAYED = "delayed"  # AI responds after significant delay


class ErrorType(str, Enum):
    """Types of errors that can be injected."""

    OFF_BY_ONE = "off_by_one"
    NULL_CHECK_MISSING = "null_check_missing"
    WRONG_VARIABLE = "wrong_variable"
    LOGIC_INVERSION = "logic_inversion"
    API_MISUSE = "api_misuse"


class ErrorDifficulty(str, Enum):
    """How obvious the injected error is."""

    OBVIOUS = "obvious"  # Easy to spot
    MODERATE = "moderate"  # Requires careful reading
    SUBTLE = "subtle"  # Requires testing to detect


@dataclass
class InjectedError:
    """Record of an intentionally injected error."""

    id: str
    timestamp: datetime
    session_id: str
    tool_name: str
    error_type: ErrorType
    difficulty: ErrorDifficulty
    original_response: str
    modified_response: str
    error_description: str
    detected: bool = False
    detection_time: datetime | None = None
    detection_method: str | None = None  # "testing", "review", "peer", "none"


@dataclass
class ErrorReport:
    """Student report of a detected error."""

    id: str
    timestamp: datetime
    session_id: str
    tool_name: str
    error_description: str
    proposed_fix: str | None = None
    # Filled in by system after matching
    matched_injection_id: str | None = None
    is_true_positive: bool | None = None  # Did they find a real injected error?


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(UTC)


class ResilienceConfig:
    """Configuration for resilience testing loaded from YAML."""

    def __init__(self, config_path: Path | None = None):
        """Load configuration from YAML file.

        Args:
            config_path: Path to resilience_tests.yaml
        """
        self._config: dict[str, Any] = {}
        self._team_overrides: dict[str, dict[str, Any]] = {}

        if config_path and config_path.exists():
            try:
                with open(config_path) as f:
                    self._config = yaml.safe_load(f) or {}
                self._team_overrides = dict(self._config.get("team_assignments", {}))
                logger.info(f"Loaded resilience config from {config_path}")
            except (OSError, yaml.YAMLError, TypeError, ValueError) as e:
                logger.warning(f"Failed to load resilience config: {e}")
                self._config = {}
        else:
            logger.info("No resilience config found, using defaults (disabled)")

    @property
    def enabled(self) -> bool:
        """Whether resilience testing is globally enabled."""
        return cast(bool, self._config.get("enabled", False))

    @property
    def mode(self) -> ResilienceMode:
        """Global resilience mode."""
        mode_str = self._config.get("mode", "normal")
        try:
            return ResilienceMode(mode_str)
        except ValueError:
            return ResilienceMode.NORMAL

    @property
    def error_injection_rate(self) -> float:
        """Probability of injecting an error in degraded mode."""
        return cast(float, self._config.get("degraded_mode", {}).get("error_injection_rate", 0.3))

    @property
    def error_types(self) -> list[dict[str, Any]]:
        """Configured error types with weights."""
        return cast(list[dict[str, Any]], self._config.get("degraded_mode", {}).get("error_types", []))

    @property
    def difficulty_distribution(self) -> dict[str, float]:
        """Distribution of error difficulties."""
        return cast(dict[str, float], self._config.get("degraded_mode", {}).get("difficulty_distribution", {
            "obvious": 0.2,
            "moderate": 0.5,
            "subtle": 0.3,
        }))

    @property
    def unavailable_message(self) -> str:
        """Message to show when AI is unavailable."""
        return cast(str, self._config.get("unavailable_mode", {}).get(
            "message",
            "The AI assistant is temporarily unavailable. "
            "Please continue working using documentation and team discussion."
        ))

    @property
    def allowed_tools_when_unavailable(self) -> list[str]:
        """Tools that remain available during unavailable mode."""
        return cast(list[str], self._config.get("unavailable_mode", {}).get("allowed_tools", [
            "search_documentation",
            "search_knowledge",
            "get_semester_context",
        ]))

    @property
    def delay_seconds(self) -> int:
        """Delay in seconds for delayed mode."""
        return cast(int, self._config.get("delayed_mode", {}).get("delay_seconds", 60))

    @property
    def delay_message(self) -> str:
        """Message to show during delayed mode."""
        return cast(str, self._config.get("delayed_mode", {}).get(
            "message_during_delay",
            "Processing your request... This may take a moment."
        ))

    def get_team_mode(self, team_id: str | None) -> ResilienceMode:
        """Get resilience mode for a specific team.

        Args:
            team_id: Team identifier

        Returns:
            Effective mode for the team
        """
        if not self.enabled:
            return ResilienceMode.NORMAL

        if team_id and team_id in self._team_overrides:
            assignment = self._team_overrides[team_id]
            # Check if within assessment window
            if self._in_assessment_window(assignment):
                mode_str = assignment.get("mode", "normal")
                try:
                    return ResilienceMode(mode_str)
                except ValueError:
                    pass

        return self.mode

    def _in_assessment_window(self, assignment: dict[str, Any]) -> bool:
        """Check if current time is within assessment window.

        Args:
            assignment: Team assignment configuration

        Returns:
            True if within window or no window specified
        """
        window = assignment.get("assessment_window")
        if not window:
            return True  # No window = always active

        now = _utcnow()
        start_str = window.get("start")
        end_str = window.get("end")

        if start_str:
            start = datetime.fromisoformat(start_str)
            if now < start:
                return False

        if end_str:
            end = datetime.fromisoformat(end_str)
            if now > end:
                return False

        return True

    def set_team_override(
        self,
        team_id: str,
        mode: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        """Set team-specific configuration.

        Args:
            team_id: Team to configure
            mode: Mode to set
            enabled: Whether to enable for this team
        """
        if team_id not in self._team_overrides:
            self._team_overrides[team_id] = {}

        if mode is not None:
            self._team_overrides[team_id]["mode"] = mode
        if enabled is not None:
            self._team_overrides[team_id]["enabled"] = enabled


class ResilienceService:
    """Manages resilience testing for research assessment.

    Handles mode determination, error injection, and error reporting
    for controlled assessment of student verification skills.
    """

    def __init__(self, config: ResilienceConfig | None = None):
        """Initialize the service.

        Args:
            config: Configuration object (or loads from default path)
        """
        if config is None:
            import os

            from girafmcp.core.paths import DATA_DIR

            config_path = os.environ.get(
                "GIRAF_RESILIENCE_CONFIG",
                str(DATA_DIR / "resilience_tests.yaml"),
            )
            config = ResilienceConfig(Path(config_path))

        self.config = config
        self._injected_errors: dict[str, InjectedError] = {}
        self._error_reports: dict[str, ErrorReport] = {}

    def get_mode(self, team_id: str | None = None) -> ResilienceMode:
        """Get current resilience mode for a team.

        Args:
            team_id: Team identifier

        Returns:
            Current mode
        """
        return self.config.get_team_mode(team_id)

    def is_tool_allowed(self, tool_name: str, team_id: str | None = None) -> bool:
        """Check if a tool can be used in current mode.

        Args:
            tool_name: Name of the tool
            team_id: Team identifier

        Returns:
            True if tool is allowed
        """
        mode = self.get_mode(team_id)

        if mode == ResilienceMode.UNAVAILABLE:
            return tool_name in self.config.allowed_tools_when_unavailable

        return True  # All tools allowed in other modes

    def should_inject_error(self) -> bool:
        """Determine if an error should be injected.

        Based on configured error_injection_rate.

        Returns:
            True if error should be injected
        """
        return random.random() < self.config.error_injection_rate

    def select_error_type(self) -> ErrorType:
        """Select an error type based on configured weights.

        Returns:
            Selected error type
        """
        error_types = self.config.error_types
        if not error_types:
            return random.choice(list(ErrorType))

        # Build weighted selection
        types = []
        weights = []
        for et in error_types:
            try:
                types.append(ErrorType(et["type"]))
                weights.append(et.get("weight", 1.0))
            except (ValueError, KeyError):
                continue

        if not types:
            return random.choice(list(ErrorType))

        return random.choices(types, weights=weights, k=1)[0]

    def select_difficulty(self) -> ErrorDifficulty:
        """Select error difficulty based on configured distribution.

        Returns:
            Selected difficulty
        """
        dist = self.config.difficulty_distribution
        difficulties = list(ErrorDifficulty)
        weights = [dist.get(d.value, 0.33) for d in difficulties]
        return random.choices(difficulties, weights=weights, k=1)[0]

    def inject_error(
        self,
        response: str,
        tool_name: str,
        session_id: str,
    ) -> tuple[str, InjectedError | None]:
        """Inject an error into an AI response.

        Args:
            response: Original response text
            tool_name: Name of the tool that produced the response
            session_id: Current session ID

        Returns:
            Tuple of (modified response, error record or None)
        """
        if not self.should_inject_error():
            return response, None

        error_type = self.select_error_type()
        difficulty = self.select_difficulty()

        # Generate error injection
        modified, description = self._apply_error(response, error_type, difficulty)

        if modified == response:
            # Failed to inject (e.g., no suitable injection point)
            return response, None

        error = InjectedError(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            session_id=session_id,
            tool_name=tool_name,
            error_type=error_type,
            difficulty=difficulty,
            original_response=response,
            modified_response=modified,
            error_description=description,
        )

        self._injected_errors[error.id] = error
        logger.info(f"Injected {error_type.value} error ({difficulty.value}) in {tool_name}")

        return modified, error

    def _apply_error(
        self,
        response: str,
        error_type: ErrorType,
        difficulty: ErrorDifficulty,
    ) -> tuple[str, str]:
        """Apply a specific error type to response.

        Args:
            response: Original response
            error_type: Type of error to inject
            difficulty: How obvious the error should be

        Returns:
            Tuple of (modified response, error description)
        """
        # Simple text-based error injection
        # In a real system, this would use AST parsing for code

        if error_type == ErrorType.OFF_BY_ONE:
            # Try to find loop patterns and modify bounds
            patterns = [
                ("< ", "<= "),
                ("<= ", "< "),
                ("> ", ">= "),
                (">= ", "> "),
                ("range(0, ", "range(1, "),
                ("range(1, ", "range(0, "),
            ]
            for old, new in patterns:
                if old in response:
                    modified = response.replace(old, new, 1)
                    return modified, f"Off-by-one: changed '{old.strip()}' to '{new.strip()}'"

        elif error_type == ErrorType.NULL_CHECK_MISSING:
            # Add a note suggesting missing null check
            if "if " in response and "null" not in response.lower() and "none" not in response.lower():
                # Inject a comment about missing check
                note = "\n\n*Note: Null/undefined checks may need to be added for production use.*"
                return response + note, "Hinted at missing null check without providing it"

        elif error_type == ErrorType.WRONG_VARIABLE:
            # Try to swap similar variable names
            var_pairs = [
                ("result", "results"),
                ("item", "items"),
                ("data", "datum"),
                ("index", "idx"),
                ("count", "counter"),
            ]
            for v1, v2 in var_pairs:
                if v1 in response and v2 not in response:
                    modified = response.replace(v1, v2, 1)
                    return modified, f"Wrong variable: changed '{v1}' to '{v2}'"

        elif error_type == ErrorType.LOGIC_INVERSION:
            # Invert boolean logic
            inversions = [
                ("== True", "== False"),
                ("== False", "== True"),
                ("is True", "is False"),
                ("is False", "is True"),
                (" and ", " or "),
                (" or ", " and "),
                ("not ", ""),
            ]
            for old, new in inversions:
                if old in response:
                    modified = response.replace(old, new, 1)
                    return modified, f"Logic inversion: changed '{old}' to '{new}'"

        elif error_type == ErrorType.API_MISUSE:
            # Suggest incorrect API usage
            if "await " in response:
                # Remove an await
                modified = response.replace("await ", "", 1)
                return modified, "API misuse: removed required 'await'"

        # No suitable injection point found
        return response, ""

    def record_error_report(
        self,
        session_id: str,
        tool_name: str,
        error_description: str,
        proposed_fix: str | None = None,
    ) -> ErrorReport:
        """Record a student's error report.

        Args:
            session_id: Current session ID
            tool_name: Tool where error was found
            error_description: Student's description of the error
            proposed_fix: Student's proposed fix

        Returns:
            The error report record
        """
        report = ErrorReport(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            session_id=session_id,
            tool_name=tool_name,
            error_description=error_description,
            proposed_fix=proposed_fix,
        )

        # Try to match with an injected error
        matched = self._match_report_to_injection(report)
        if matched:
            report.matched_injection_id = matched.id
            report.is_true_positive = True
            matched.detected = True
            matched.detection_time = report.timestamp
            matched.detection_method = "student_report"
            logger.info(f"Error report matched injection {matched.id}")
        else:
            # Could be false positive or a real bug they found
            report.is_true_positive = False
            logger.info("Error report did not match any injection")

        self._error_reports[report.id] = report
        return report

    def _match_report_to_injection(self, report: ErrorReport) -> InjectedError | None:
        """Try to match an error report to an injected error.

        Args:
            report: The error report

        Returns:
            Matched injection or None
        """
        # Simple matching: same session, same tool, not yet detected
        for error in self._injected_errors.values():
            if (
                error.session_id == report.session_id
                and error.tool_name == report.tool_name
                and not error.detected
            ):
                return error
        return None

    def get_unavailable_message(self) -> str:
        """Get message to show when AI is unavailable."""
        return self.config.unavailable_message

    def get_delay_seconds(self) -> int:
        """Get delay for delayed mode."""
        return self.config.delay_seconds

    def get_delay_message(self) -> str:
        """Get message to show during delay."""
        return self.config.delay_message

    def get_injected_errors(self, session_id: str | None = None) -> list[InjectedError]:
        """Get injected errors, optionally filtered by session.

        Args:
            session_id: Filter by session

        Returns:
            List of injected errors
        """
        errors = list(self._injected_errors.values())
        if session_id:
            errors = [e for e in errors if e.session_id == session_id]
        return errors

    def get_error_reports(self, session_id: str | None = None) -> list[ErrorReport]:
        """Get error reports, optionally filtered by session.

        Args:
            session_id: Filter by session

        Returns:
            List of error reports
        """
        reports = list(self._error_reports.values())
        if session_id:
            reports = [r for r in reports if r.session_id == session_id]
        return reports

    def get_detection_metrics(self, session_id: str | None = None) -> dict[str, Any]:
        """Calculate detection metrics for research analysis.

        Args:
            session_id: Filter by session

        Returns:
            Dict with detection metrics
        """
        errors = self.get_injected_errors(session_id)
        reports = self.get_error_reports(session_id)

        if not errors:
            return {
                "total_injected": 0,
                "detected": 0,
                "detection_rate": 0.0,
                "false_positives": len([r for r in reports if not r.is_true_positive]),
            }

        detected = [e for e in errors if e.detected]
        true_positives = [r for r in reports if r.is_true_positive]
        false_positives = [r for r in reports if not r.is_true_positive]

        # Calculate average detection time
        detection_times = []
        for e in detected:
            if e.detection_time:
                delta = (e.detection_time - e.timestamp).total_seconds()
                detection_times.append(delta)

        avg_detection_time = (
            sum(detection_times) / len(detection_times) if detection_times else None
        )

        return {
            "total_injected": len(errors),
            "detected": len(detected),
            "detection_rate": len(detected) / len(errors) if errors else 0.0,
            "true_positives": len(true_positives),
            "false_positives": len(false_positives),
            "avg_detection_time_seconds": avg_detection_time,
            "by_difficulty": {
                d.value: {
                    "injected": len([e for e in errors if e.difficulty == d]),
                    "detected": len([e for e in detected if e.difficulty == d]),
                }
                for d in ErrorDifficulty
            },
            "by_type": {
                t.value: {
                    "injected": len([e for e in errors if e.error_type == t]),
                    "detected": len([e for e in detected if e.error_type == t]),
                }
                for t in ErrorType
            },
        }
