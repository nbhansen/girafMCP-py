"""Multi-frame service for cross-disciplinary framing.

Provides discipline-aware explanations and vocabulary translations
to support knowledge transfer across CS, Interaction Design,
Business, and Health backgrounds.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, cast

import yaml

logger = logging.getLogger(__name__)


class Discipline(Enum):
    """Supported disciplines for framing."""

    CS = "cs"
    ID = "id"  # Interaction Design
    BUSINESS = "business"
    HEALTH = "health"


class ExplanationStyle(Enum):
    """Explanation styles for different disciplines."""

    TECHNICAL_PRECISE = "technical_precise"
    CONCEPTUAL_VISUAL = "conceptual_visual"
    OUTCOME_FOCUSED = "outcome_focused"
    CLINICAL_CONTEXT = "clinical_context"


class CodeDepth(Enum):
    """Code detail levels for explanations."""

    DETAILED = "detailed"
    MODERATE = "moderate"
    HIGH_LEVEL = "high_level"
    OVERVIEW = "overview"


@dataclass
class DisciplineProfile:
    """Profile for a specific discipline."""

    name: str
    discipline: Discipline
    vocabulary_emphasis: list[str] = field(default_factory=list)
    explanation_style: ExplanationStyle = ExplanationStyle.TECHNICAL_PRECISE
    default_code_depth: CodeDepth = CodeDepth.DETAILED
    assumed_knowledge: list[str] = field(default_factory=list)
    translation_hints: dict[str, str] = field(default_factory=dict)


@dataclass
class FramedExplanation:
    """Same concept explained for different disciplines."""

    concept: str
    context: str
    frames: dict[str, str]  # discipline -> explanation
    default_frame: str


@dataclass
class ConceptTranslation:
    """Translation of a concept across disciplines."""

    concept: str
    translations: dict[str, str]  # discipline -> translation


class MultiFrameConfig:
    """Configuration loader for discipline profiles."""

    def __init__(self, config_path: Path | None = None):
        """Initialize config from YAML file.

        Args:
            config_path: Path to discipline_profiles.yaml
        """
        self._config: dict[str, Any] = {}
        self._profiles: dict[str, DisciplineProfile] = {}
        self._translations: dict[str, ConceptTranslation] = {}

        if config_path and config_path.exists():
            self._load_config(config_path)
        else:
            self._set_defaults()

    def _load_config(self, path: Path) -> None:
        """Load configuration from YAML file."""
        try:
            with open(path) as f:
                self._config = yaml.safe_load(f) or {}
            self._parse_profiles()
            self._parse_translations()
            logger.info(f"Loaded discipline profiles from {path}")
        except Exception as e:
            logger.warning(f"Failed to load discipline profiles: {e}")
            self._set_defaults()

    def _set_defaults(self) -> None:
        """Set safe defaults when config unavailable."""
        self._config = {"enabled": False}
        self._profiles = {}
        self._translations = {}

    def _parse_profiles(self) -> None:
        """Parse discipline profiles from config."""
        disciplines = self._config.get("disciplines", {})
        for key, data in disciplines.items():
            try:
                discipline = Discipline(key)
                style = ExplanationStyle(
                    data.get("explanation_style", "technical_precise")
                )
                depth = CodeDepth(data.get("default_code_depth", "detailed"))

                profile = DisciplineProfile(
                    name=data.get("name", key.upper()),
                    discipline=discipline,
                    vocabulary_emphasis=data.get("vocabulary_emphasis", []),
                    explanation_style=style,
                    default_code_depth=depth,
                    assumed_knowledge=data.get("assumed_knowledge", []),
                    translation_hints=data.get("translation_hints", {}),
                )
                self._profiles[key] = profile
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid discipline profile '{key}': {e}")

    def _parse_translations(self) -> None:
        """Parse concept translations from config."""
        translations = self._config.get("concept_translations", {})
        for concept, trans in translations.items():
            self._translations[concept.lower()] = ConceptTranslation(
                concept=concept,
                translations=trans,
            )

    @property
    def enabled(self) -> bool:
        """Check if multi-frame features are enabled."""
        env_enabled = os.environ.get("GIRAF_DISCIPLINE_ENABLED", "").lower()
        if env_enabled:
            return env_enabled in ("true", "1", "yes")
        return cast(bool, self._config.get("enabled", False))

    @property
    def default_discipline(self) -> str:
        """Get default discipline."""
        return cast(str, self._config.get("default_discipline", "cs"))

    def get_profile(self, discipline: str) -> DisciplineProfile | None:
        """Get profile for a discipline."""
        return self._profiles.get(discipline)

    def get_all_profiles(self) -> dict[str, DisciplineProfile]:
        """Get all discipline profiles."""
        return self._profiles.copy()

    def get_translation(self, concept: str) -> ConceptTranslation | None:
        """Get translation for a concept."""
        return self._translations.get(concept.lower())

    def get_all_translations(self) -> dict[str, ConceptTranslation]:
        """Get all concept translations."""
        return self._translations.copy()


class MultiFrameService:
    """Provides discipline-aware explanations and translations."""

    def __init__(self, config: MultiFrameConfig):
        """Initialize service with configuration.

        Args:
            config: MultiFrameConfig instance
        """
        self.config = config

    @property
    def enabled(self) -> bool:
        """Check if service is enabled."""
        return self.config.enabled

    def get_discipline_profile(self, discipline: str) -> DisciplineProfile | None:
        """Get profile for a discipline.

        Args:
            discipline: Discipline identifier (cs, id, business, health)

        Returns:
            DisciplineProfile if found, None otherwise
        """
        return self.config.get_profile(discipline)

    def get_all_disciplines(self) -> list[str]:
        """Get list of all supported disciplines."""
        return list(self.config.get_all_profiles().keys())

    def translate_concept(
        self, concept: str, target_discipline: str
    ) -> str | None:
        """Translate a technical concept for a specific discipline.

        Args:
            concept: Technical concept to translate
            target_discipline: Target discipline for translation

        Returns:
            Translated explanation or None if not available
        """
        translation = self.config.get_translation(concept)
        if translation:
            return translation.translations.get(target_discipline)
        return None

    def get_all_translations_for_concept(self, concept: str) -> dict[str, str]:
        """Get all discipline translations for a concept.

        Args:
            concept: Technical concept

        Returns:
            Dict of discipline -> translation
        """
        translation = self.config.get_translation(concept)
        if translation:
            return translation.translations.copy()
        return {}

    def get_explanation_style(self, discipline: str) -> ExplanationStyle:
        """Get preferred explanation style for discipline.

        Args:
            discipline: Discipline identifier

        Returns:
            ExplanationStyle enum value
        """
        profile = self.get_discipline_profile(discipline)
        if profile:
            return profile.explanation_style
        return ExplanationStyle.TECHNICAL_PRECISE

    def get_code_depth(self, discipline: str) -> CodeDepth:
        """Get appropriate code detail level for discipline.

        Args:
            discipline: Discipline identifier

        Returns:
            CodeDepth enum value
        """
        profile = self.get_discipline_profile(discipline)
        if profile:
            return profile.default_code_depth
        return CodeDepth.DETAILED

    def should_translate_term(self, term: str, discipline: str) -> bool:
        """Check if a term needs translation for this discipline.

        Args:
            term: Technical term to check
            discipline: Target discipline

        Returns:
            True if translation hint exists for this term
        """
        profile = self.get_discipline_profile(discipline)
        if profile:
            return term.lower() in {k.lower() for k in profile.translation_hints}
        return False

    def get_translation_hint(self, term: str, discipline: str) -> str | None:
        """Get translation hint for a term in a discipline.

        Args:
            term: Technical term
            discipline: Target discipline

        Returns:
            Translation hint or None
        """
        profile = self.get_discipline_profile(discipline)
        if profile:
            # Case-insensitive lookup
            for key, hint in profile.translation_hints.items():
                if key.lower() == term.lower():
                    return hint
        return None

    def adapt_response_for_discipline(
        self,
        response: str,
        target_discipline: str,
    ) -> str:
        """Adapt a response for a specific discipline.

        Adjusts vocabulary by adding translation hints for technical terms.

        Args:
            response: Original response text
            target_discipline: Target discipline (cs, id, business, health)

        Returns:
            Adapted response with translation notes
        """
        if not self.enabled:
            return response

        profile = self.get_discipline_profile(target_discipline)
        if not profile or target_discipline == "cs":
            # CS doesn't need adaptations
            return response

        # Add translation hints for technical terms found in response
        adapted = response
        hints = profile.translation_hints

        for term, translation in hints.items():
            # Find term in response (case-insensitive, whole word)
            pattern = rf"\b{re.escape(term)}\b"
            if re.search(pattern, adapted, re.IGNORECASE):
                # Add translation note after first occurrence
                def add_note(match: re.Match[str]) -> str:
                    return f"{match.group(0)} (*{translation}*)"

                adapted = re.sub(
                    pattern, add_note, adapted, count=1, flags=re.IGNORECASE
                )

        return adapted

    def generate_multiframe_explanation(
        self,
        concept: str,
        context: str = "",
    ) -> FramedExplanation:
        """Generate explanation of a concept for all disciplines.

        Args:
            concept: Technical concept to explain
            context: Additional context for the explanation

        Returns:
            FramedExplanation with perspectives for all disciplines
        """
        frames: dict[str, str] = {}

        # Check if we have a predefined translation
        translation = self.config.get_translation(concept)

        for discipline in self.get_all_disciplines():
            profile = self.get_discipline_profile(discipline)
            if not profile:
                continue

            if translation and discipline in translation.translations:
                # Use predefined translation
                frames[discipline] = translation.translations[discipline]
            else:
                # Generate a frame based on profile characteristics
                frames[discipline] = self._generate_frame(
                    concept, context, profile
                )

        # Default to CS frame or first available
        default = frames.get("cs", list(frames.values())[0] if frames else "")

        return FramedExplanation(
            concept=concept,
            context=context,
            frames=frames,
            default_frame=default,
        )

    def _generate_frame(
        self,
        concept: str,
        context: str,
        profile: DisciplineProfile,
    ) -> str:
        """Generate a discipline-specific frame for a concept.

        Args:
            concept: Technical concept
            context: Additional context
            profile: Target discipline profile

        Returns:
            Framed explanation
        """
        # Build explanation based on profile style
        style = profile.explanation_style

        if style == ExplanationStyle.TECHNICAL_PRECISE:
            return f"{concept}: A technical concept. {context}"
        elif style == ExplanationStyle.CONCEPTUAL_VISUAL:
            return f"{concept}: Think of this as a building block in the system. {context}"
        elif style == ExplanationStyle.OUTCOME_FOCUSED:
            return f"{concept}: A pattern that affects maintainability and costs. {context}"
        elif style == ExplanationStyle.CLINICAL_CONTEXT:
            return f"{concept}: Important for system reliability and safety. {context}"

        return f"{concept}: {context}"

    def compare_perspectives(self, topic: str) -> dict[str, str]:
        """Get perspectives on a topic from all disciplines.

        Args:
            topic: Topic or decision to analyze

        Returns:
            Dict of discipline -> perspective
        """
        perspectives: dict[str, str] = {}

        # Check for predefined translation first
        translation = self.config.get_translation(topic)
        if translation:
            return translation.translations.copy()

        # Generate perspectives based on profiles
        for discipline in self.get_all_disciplines():
            profile = self.get_discipline_profile(discipline)
            if not profile:
                continue

            perspectives[discipline] = self._generate_perspective(topic, profile)

        return perspectives

    def _generate_perspective(
        self, topic: str, profile: DisciplineProfile
    ) -> str:
        """Generate a perspective on a topic for a discipline.

        Args:
            topic: Topic to analyze
            profile: Discipline profile

        Returns:
            Perspective text
        """
        style = profile.explanation_style
        emphasis = profile.vocabulary_emphasis[:3] if profile.vocabulary_emphasis else []

        if style == ExplanationStyle.TECHNICAL_PRECISE:
            focus = ", ".join(emphasis) if emphasis else "technical implementation"
            return f"From a {profile.name} perspective, focus on {focus} aspects of {topic}."
        elif style == ExplanationStyle.CONCEPTUAL_VISUAL:
            focus = ", ".join(emphasis) if emphasis else "user experience"
            return f"Consider the {focus} implications of {topic} for users."
        elif style == ExplanationStyle.OUTCOME_FOCUSED:
            focus = ", ".join(emphasis) if emphasis else "business value"
            return f"Evaluate {topic} in terms of {focus} and organizational impact."
        elif style == ExplanationStyle.CLINICAL_CONTEXT:
            focus = ", ".join(emphasis) if emphasis else "safety and compliance"
            return f"Assess {topic} with attention to {focus} requirements."

        return f"Consider {topic} from a {profile.name} viewpoint."
