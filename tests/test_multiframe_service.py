"""Tests for multiframe service.

Tests cover:
- MultiFrameConfig loading and validation
- Discipline profile access
- Concept translation
- Response adaptation
- Multi-framed explanation generation
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from girafmcp.core.services.multiframe_service import (
    MultiFrameService,
    MultiFrameConfig,
    Discipline,
    DisciplineProfile,
    ExplanationStyle,
    CodeDepth,
    FramedExplanation,
)


class TestMultiFrameConfig:
    """Tests for MultiFrameConfig."""

    @pytest.fixture
    def sample_config(self) -> dict:
        """Sample configuration for testing."""
        return {
            "enabled": True,
            "default_discipline": "cs",
            "disciplines": {
                "cs": {
                    "name": "Computer Science",
                    "vocabulary_emphasis": ["algorithms", "data structures"],
                    "explanation_style": "technical_precise",
                    "default_code_depth": "detailed",
                    "assumed_knowledge": ["programming", "git"],
                    "translation_hints": {},
                },
                "id": {
                    "name": "Interaction Design",
                    "vocabulary_emphasis": ["user experience", "accessibility"],
                    "explanation_style": "conceptual_visual",
                    "default_code_depth": "high_level",
                    "assumed_knowledge": ["design thinking"],
                    "translation_hints": {
                        "API": "The language apps use to talk to servers",
                        "component": "A reusable UI building block",
                    },
                },
                "business": {
                    "name": "Business/IT",
                    "vocabulary_emphasis": ["ROI", "scalability"],
                    "explanation_style": "outcome_focused",
                    "default_code_depth": "overview",
                    "assumed_knowledge": ["project management"],
                    "translation_hints": {
                        "refactoring": "Reorganizing code to reduce maintenance costs",
                    },
                },
            },
            "concept_translations": {
                "dependency injection": {
                    "cs": "A design pattern for loose coupling",
                    "id": "The app gets its tools handed to it",
                    "business": "Components are interchangeable",
                },
                "API": {
                    "cs": "Application Programming Interface",
                    "id": "The language apps use to communicate",
                    "business": "Contract for system connections",
                },
            },
        }

    @pytest.fixture
    def config_path(self, sample_config: dict) -> Path:
        """Create a temporary config file."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "discipline_profiles.yaml"
            with open(path, "w") as f:
                yaml.safe_dump(sample_config, f)
            yield path

    def test_load_config(self, config_path: Path) -> None:
        """Config should load from YAML file."""
        config = MultiFrameConfig(config_path)
        assert config.enabled is True
        assert config.default_discipline == "cs"

    def test_missing_config_file(self) -> None:
        """Missing config file should use safe defaults."""
        config = MultiFrameConfig(Path("/nonexistent/path/config.yaml"))
        assert config.enabled is False

    def test_get_profile(self, config_path: Path) -> None:
        """Should return discipline profile."""
        config = MultiFrameConfig(config_path)
        profile = config.get_profile("cs")

        assert profile is not None
        assert profile.name == "Computer Science"
        assert profile.discipline == Discipline.CS
        assert profile.explanation_style == ExplanationStyle.TECHNICAL_PRECISE
        assert profile.default_code_depth == CodeDepth.DETAILED

    def test_get_all_profiles(self, config_path: Path) -> None:
        """Should return all profiles."""
        config = MultiFrameConfig(config_path)
        profiles = config.get_all_profiles()

        assert len(profiles) == 3
        assert "cs" in profiles
        assert "id" in profiles
        assert "business" in profiles

    def test_get_translation(self, config_path: Path) -> None:
        """Should return concept translation."""
        config = MultiFrameConfig(config_path)
        translation = config.get_translation("dependency injection")

        assert translation is not None
        assert "cs" in translation.translations
        assert "id" in translation.translations
        assert translation.translations["cs"] == "A design pattern for loose coupling"

    def test_get_translation_case_insensitive(self, config_path: Path) -> None:
        """Translation lookup should be case-insensitive."""
        config = MultiFrameConfig(config_path)
        translation = config.get_translation("DEPENDENCY INJECTION")

        assert translation is not None


class TestMultiFrameService:
    """Tests for MultiFrameService."""

    @pytest.fixture
    def service(self) -> MultiFrameService:
        """Create service with test config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "discipline_profiles.yaml"
            config_data = {
                "enabled": True,
                "default_discipline": "cs",
                "disciplines": {
                    "cs": {
                        "name": "Computer Science",
                        "vocabulary_emphasis": ["algorithms"],
                        "explanation_style": "technical_precise",
                        "default_code_depth": "detailed",
                        "assumed_knowledge": ["programming"],
                        "translation_hints": {},
                    },
                    "id": {
                        "name": "Interaction Design",
                        "vocabulary_emphasis": ["user experience"],
                        "explanation_style": "conceptual_visual",
                        "default_code_depth": "high_level",
                        "assumed_knowledge": ["design thinking"],
                        "translation_hints": {
                            "API": "The language apps use to talk to servers",
                            "callback": "Code that runs when something happens",
                        },
                    },
                },
                "concept_translations": {
                    "dependency injection": {
                        "cs": "A design pattern for loose coupling",
                        "id": "The app gets its tools handed to it",
                    },
                },
            }
            with open(config_path, "w") as f:
                yaml.safe_dump(config_data, f)

            config = MultiFrameConfig(config_path)
            yield MultiFrameService(config)

    def test_get_discipline_profile(self, service: MultiFrameService) -> None:
        """Should return discipline profile."""
        profile = service.get_discipline_profile("cs")

        assert profile is not None
        assert profile.name == "Computer Science"

    def test_get_unknown_discipline(self, service: MultiFrameService) -> None:
        """Should return None for unknown discipline."""
        profile = service.get_discipline_profile("unknown")
        assert profile is None

    def test_get_all_disciplines(self, service: MultiFrameService) -> None:
        """Should return list of disciplines."""
        disciplines = service.get_all_disciplines()

        assert "cs" in disciplines
        assert "id" in disciplines

    def test_translate_concept(self, service: MultiFrameService) -> None:
        """Should translate concept for discipline."""
        translation = service.translate_concept("dependency injection", "id")

        assert translation == "The app gets its tools handed to it"

    def test_translate_concept_unknown(self, service: MultiFrameService) -> None:
        """Should return None for unknown concept."""
        translation = service.translate_concept("unknown concept", "id")
        assert translation is None

    def test_get_all_translations_for_concept(self, service: MultiFrameService) -> None:
        """Should return all translations for a concept."""
        translations = service.get_all_translations_for_concept("dependency injection")

        assert "cs" in translations
        assert "id" in translations

    def test_get_explanation_style(self, service: MultiFrameService) -> None:
        """Should return explanation style for discipline."""
        style = service.get_explanation_style("cs")
        assert style == ExplanationStyle.TECHNICAL_PRECISE

        style = service.get_explanation_style("id")
        assert style == ExplanationStyle.CONCEPTUAL_VISUAL

    def test_get_code_depth(self, service: MultiFrameService) -> None:
        """Should return code depth for discipline."""
        depth = service.get_code_depth("cs")
        assert depth == CodeDepth.DETAILED

        depth = service.get_code_depth("id")
        assert depth == CodeDepth.HIGH_LEVEL

    def test_should_translate_term(self, service: MultiFrameService) -> None:
        """Should check if term needs translation."""
        assert service.should_translate_term("API", "id") is True
        assert service.should_translate_term("unknown", "id") is False

    def test_get_translation_hint(self, service: MultiFrameService) -> None:
        """Should return translation hint for term."""
        hint = service.get_translation_hint("API", "id")
        assert hint == "The language apps use to talk to servers"

    def test_get_translation_hint_unknown(self, service: MultiFrameService) -> None:
        """Should return None for unknown term."""
        hint = service.get_translation_hint("unknown", "id")
        assert hint is None


class TestResponseAdaptation:
    """Tests for response adaptation."""

    @pytest.fixture
    def service(self) -> MultiFrameService:
        """Create service with test config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "discipline_profiles.yaml"
            config_data = {
                "enabled": True,
                "disciplines": {
                    "cs": {
                        "name": "Computer Science",
                        "explanation_style": "technical_precise",
                        "default_code_depth": "detailed",
                        "translation_hints": {},
                    },
                    "id": {
                        "name": "Interaction Design",
                        "explanation_style": "conceptual_visual",
                        "default_code_depth": "high_level",
                        "translation_hints": {
                            "API": "The language apps use to talk to servers",
                            "callback": "Code that runs when something happens",
                        },
                    },
                },
            }
            with open(config_path, "w") as f:
                yaml.safe_dump(config_data, f)

            config = MultiFrameConfig(config_path)
            yield MultiFrameService(config)

    def test_adapt_response_adds_translation(self, service: MultiFrameService) -> None:
        """Should add translation notes for technical terms."""
        response = "The component uses an API to fetch data."
        adapted = service.adapt_response_for_discipline(response, "id")

        assert "API" in adapted
        assert "The language apps use to talk to servers" in adapted

    def test_adapt_response_cs_unchanged(self, service: MultiFrameService) -> None:
        """CS responses should not be adapted."""
        response = "The API uses a callback pattern."
        adapted = service.adapt_response_for_discipline(response, "cs")

        assert adapted == response

    def test_adapt_response_only_first_occurrence(
        self, service: MultiFrameService
    ) -> None:
        """Should only add translation to first occurrence."""
        response = "API call 1 and API call 2"
        adapted = service.adapt_response_for_discipline(response, "id")

        # Count occurrences of the translation
        count = adapted.count("The language apps use to talk to servers")
        assert count == 1


class TestMultiFrameExplanation:
    """Tests for multi-framed explanation generation."""

    @pytest.fixture
    def service(self) -> MultiFrameService:
        """Create service with test config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "discipline_profiles.yaml"
            config_data = {
                "enabled": True,
                "disciplines": {
                    "cs": {
                        "name": "Computer Science",
                        "vocabulary_emphasis": ["algorithms"],
                        "explanation_style": "technical_precise",
                        "default_code_depth": "detailed",
                    },
                    "id": {
                        "name": "Interaction Design",
                        "vocabulary_emphasis": ["user experience"],
                        "explanation_style": "conceptual_visual",
                        "default_code_depth": "high_level",
                    },
                },
                "concept_translations": {
                    "dependency injection": {
                        "cs": "A design pattern for loose coupling",
                        "id": "The app gets its tools handed to it",
                    },
                },
            }
            with open(config_path, "w") as f:
                yaml.safe_dump(config_data, f)

            config = MultiFrameConfig(config_path)
            yield MultiFrameService(config)

    def test_generate_multiframe_explanation(self, service: MultiFrameService) -> None:
        """Should generate explanation for all disciplines."""
        framed = service.generate_multiframe_explanation("dependency injection")

        assert isinstance(framed, FramedExplanation)
        assert framed.concept == "dependency injection"
        assert "cs" in framed.frames
        assert "id" in framed.frames

    def test_multiframe_uses_translations(self, service: MultiFrameService) -> None:
        """Should use predefined translations when available."""
        framed = service.generate_multiframe_explanation("dependency injection")

        assert framed.frames["cs"] == "A design pattern for loose coupling"
        assert framed.frames["id"] == "The app gets its tools handed to it"

    def test_compare_perspectives(self, service: MultiFrameService) -> None:
        """Should return perspectives from all disciplines."""
        perspectives = service.compare_perspectives("dependency injection")

        assert "cs" in perspectives
        assert "id" in perspectives

    def test_compare_perspectives_unknown_topic(
        self, service: MultiFrameService
    ) -> None:
        """Should generate perspectives for unknown topics."""
        perspectives = service.compare_perspectives("unknown topic")

        # Should still return something for each discipline
        assert len(perspectives) == 2


class TestServiceDisabled:
    """Tests for disabled service."""

    @pytest.fixture
    def disabled_service(self) -> MultiFrameService:
        """Create disabled service."""
        config = MultiFrameConfig(None)  # No config = disabled
        return MultiFrameService(config)

    def test_disabled_service_not_enabled(
        self, disabled_service: MultiFrameService
    ) -> None:
        """Disabled service should report not enabled."""
        assert disabled_service.enabled is False

    def test_disabled_service_returns_original(
        self, disabled_service: MultiFrameService
    ) -> None:
        """Disabled service should return original response."""
        response = "The API uses callbacks."
        adapted = disabled_service.adapt_response_for_discipline(response, "id")
        assert adapted == response
