"""Tests for knowledge capture functionality.

Tests cover:
- ArchitecturalDecision storage and retrieval
- RetrospectiveLearning storage and retrieval
- HandoverPackage generation and review
- Text search across decisions and learnings
"""

import uuid
from datetime import UTC, datetime

import pytest

from girafmcp.adapters.research_data_adapter import ResearchDataAdapter
from girafmcp.core.types import (
    ArchitecturalDecision,
    DecisionStatus,
    FollowUpStatus,
    HandoverPackage,
    LearningCategory,
    RetrospectiveLearning,
)


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(UTC)


class TestArchitecturalDecisions:
    """Tests for architectural decision storage."""

    @pytest.fixture
    def sample_decision(self) -> ArchitecturalDecision:
        """Create a sample decision for testing."""
        return ArchitecturalDecision(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            team_id="team_a",
            title="Use PostgreSQL for Foodplanner",
            context="We need a robust database for the food planning application.",
            decision="We will use PostgreSQL as our primary database.",
            rationale="PostgreSQL offers better JSON support and reliability.",
            alternatives=["MySQL", "SQLite", "MongoDB"],
            consequences=["Need PostgreSQL deployment", "Migration from SQLite required"],
            status=DecisionStatus.ACCEPTED,
            related_issues=["#123", "#456"],
            related_files=["src/database/config.py"],
            tags=["database", "infrastructure"],
            discipline_notes={"cs": "Standard choice", "business": "Open source, no licensing costs"},
        )

    async def test_save_and_get_decision(
        self, mock_research_data_adapter: ResearchDataAdapter, sample_decision: ArchitecturalDecision
    ) -> None:
        """Decisions should be saved and retrieved correctly."""
        adapter = mock_research_data_adapter
        await adapter.save_decision(sample_decision)

        retrieved = await adapter.get_decision(sample_decision.id)

        assert retrieved is not None
        assert retrieved.id == sample_decision.id
        assert retrieved.title == sample_decision.title
        assert retrieved.context == sample_decision.context
        assert retrieved.decision == sample_decision.decision
        assert retrieved.rationale == sample_decision.rationale
        assert retrieved.alternatives == sample_decision.alternatives
        assert retrieved.consequences == sample_decision.consequences
        assert retrieved.status == DecisionStatus.ACCEPTED
        assert retrieved.related_issues == sample_decision.related_issues
        assert retrieved.tags == sample_decision.tags
        assert retrieved.discipline_notes == sample_decision.discipline_notes

    async def test_get_nonexistent_decision(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """Getting a nonexistent decision should return None."""
        result = await mock_research_data_adapter.get_decision("nonexistent-id")
        assert result is None

    async def test_list_decisions(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """list_decisions should return all saved decisions."""
        decisions = [
            ArchitecturalDecision(
                id=str(uuid.uuid4()),
                timestamp=_utcnow(),
                title=f"Decision {i}",
                context="Context",
                decision="Decision",
                rationale="Rationale",
                status=DecisionStatus.ACCEPTED,
            )
            for i in range(3)
        ]

        for d in decisions:
            await mock_research_data_adapter.save_decision(d)

        result = await mock_research_data_adapter.list_decisions()
        assert len(result) == 3

    async def test_list_decisions_by_status(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """list_decisions should filter by status."""
        accepted = ArchitecturalDecision(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            title="Accepted Decision",
            context="Context",
            decision="Decision",
            rationale="Rationale",
            status=DecisionStatus.ACCEPTED,
        )
        deprecated = ArchitecturalDecision(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            title="Deprecated Decision",
            context="Context",
            decision="Decision",
            rationale="Rationale",
            status=DecisionStatus.DEPRECATED,
        )

        await mock_research_data_adapter.save_decision(accepted)
        await mock_research_data_adapter.save_decision(deprecated)

        result = await mock_research_data_adapter.list_decisions(status=DecisionStatus.ACCEPTED)
        assert len(result) == 1
        assert result[0].status == DecisionStatus.ACCEPTED

    async def test_list_decisions_by_tags(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """list_decisions should filter by tags."""
        db_decision = ArchitecturalDecision(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            title="Database Decision",
            context="Context",
            decision="Decision",
            rationale="Rationale",
            tags=["database", "infrastructure"],
        )
        api_decision = ArchitecturalDecision(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            title="API Decision",
            context="Context",
            decision="Decision",
            rationale="Rationale",
            tags=["api", "backend"],
        )

        await mock_research_data_adapter.save_decision(db_decision)
        await mock_research_data_adapter.save_decision(api_decision)

        result = await mock_research_data_adapter.list_decisions(tags=["database"])
        assert len(result) == 1
        assert "database" in result[0].tags

    async def test_search_decisions(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """search_decisions should find matching decisions."""
        decision = ArchitecturalDecision(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            title="PostgreSQL Migration",
            context="We need to migrate to PostgreSQL for better performance.",
            decision="Migrate to PostgreSQL",
            rationale="Better JSON support",
        )

        await mock_research_data_adapter.save_decision(decision)

        # Search in title
        result = await mock_research_data_adapter.search_decisions("PostgreSQL")
        assert len(result) == 1

        # Search in context
        result = await mock_research_data_adapter.search_decisions("better performance")
        assert len(result) == 1

        # Search with no matches
        result = await mock_research_data_adapter.search_decisions("nonexistent term xyz")
        assert len(result) == 0

    async def test_update_decision(
        self, mock_research_data_adapter: ResearchDataAdapter, sample_decision: ArchitecturalDecision
    ) -> None:
        """Saving a decision with the same ID should update it."""
        adapter = mock_research_data_adapter
        await adapter.save_decision(sample_decision)

        # Update the decision
        sample_decision.status = DecisionStatus.DEPRECATED
        sample_decision.title = "Updated Title"
        await adapter.save_decision(sample_decision)

        retrieved = await adapter.get_decision(sample_decision.id)
        assert retrieved is not None
        assert retrieved.status == DecisionStatus.DEPRECATED
        assert retrieved.title == "Updated Title"


class TestRetrospectiveLearnings:
    """Tests for retrospective learning storage."""

    @pytest.fixture
    def sample_learning(self) -> RetrospectiveLearning:
        """Create a sample learning for testing."""
        return RetrospectiveLearning(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            team_id="team_a",
            sprint="2025s1-sprint3",
            category=LearningCategory.WENT_WELL,
            description="Pair programming sessions were very productive.",
            related_decisions=[],
            follow_up_status=None,
        )

    async def test_save_and_get_learning(
        self, mock_research_data_adapter: ResearchDataAdapter, sample_learning: RetrospectiveLearning
    ) -> None:
        """Learnings should be saved and retrieved correctly."""
        adapter = mock_research_data_adapter
        await adapter.save_learning(sample_learning)

        retrieved = await adapter.get_learning(sample_learning.id)

        assert retrieved is not None
        assert retrieved.id == sample_learning.id
        assert retrieved.sprint == sample_learning.sprint
        assert retrieved.category == LearningCategory.WENT_WELL
        assert retrieved.description == sample_learning.description

    async def test_get_nonexistent_learning(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """Getting a nonexistent learning should return None."""
        result = await mock_research_data_adapter.get_learning("nonexistent-id")
        assert result is None

    async def test_get_learnings_by_sprint(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """get_learnings_by_sprint should return learnings for a specific sprint."""
        sprint1 = RetrospectiveLearning(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            sprint="2025s1-sprint1",
            category=LearningCategory.WENT_WELL,
            description="Sprint 1 learning",
        )
        sprint2 = RetrospectiveLearning(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            sprint="2025s1-sprint2",
            category=LearningCategory.INSIGHT,
            description="Sprint 2 learning",
        )

        await mock_research_data_adapter.save_learning(sprint1)
        await mock_research_data_adapter.save_learning(sprint2)

        result = await mock_research_data_adapter.get_learnings_by_sprint("2025s1-sprint1")
        assert len(result) == 1
        assert result[0].sprint == "2025s1-sprint1"

    async def test_get_learnings_by_category(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """get_learnings_by_category should filter by category."""
        went_well = RetrospectiveLearning(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            sprint="2025s1-sprint1",
            category=LearningCategory.WENT_WELL,
            description="Something good",
        )
        to_improve = RetrospectiveLearning(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            sprint="2025s1-sprint1",
            category=LearningCategory.TO_IMPROVE,
            description="Something to fix",
        )

        await mock_research_data_adapter.save_learning(went_well)
        await mock_research_data_adapter.save_learning(to_improve)

        result = await mock_research_data_adapter.get_learnings_by_category(LearningCategory.WENT_WELL)
        assert len(result) == 1
        assert result[0].category == LearningCategory.WENT_WELL

    async def test_action_item_follow_up_status(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """Action items should track follow-up status."""
        action_item = RetrospectiveLearning(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            sprint="2025s1-sprint1",
            category=LearningCategory.ACTION_ITEM,
            description="Set up CI/CD pipeline",
            follow_up_status=FollowUpStatus.PENDING,
        )

        await mock_research_data_adapter.save_learning(action_item)

        retrieved = await mock_research_data_adapter.get_learning(action_item.id)
        assert retrieved is not None
        assert retrieved.follow_up_status == FollowUpStatus.PENDING

        # Update status
        action_item.follow_up_status = FollowUpStatus.COMPLETED
        await mock_research_data_adapter.save_learning(action_item)

        retrieved = await mock_research_data_adapter.get_learning(action_item.id)
        assert retrieved is not None
        assert retrieved.follow_up_status == FollowUpStatus.COMPLETED

    async def test_search_learnings(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """search_learnings should find matching learnings."""
        learning = RetrospectiveLearning(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            sprint="2025s1-sprint1",
            category=LearningCategory.INSIGHT,
            description="Pair programming improved code quality significantly.",
        )

        await mock_research_data_adapter.save_learning(learning)

        result = await mock_research_data_adapter.search_learnings("pair programming")
        assert len(result) == 1

        result = await mock_research_data_adapter.search_learnings("nonexistent term xyz")
        assert len(result) == 0


class TestHandoverPackages:
    """Tests for handover package storage."""

    @pytest.fixture
    def sample_package(self) -> HandoverPackage:
        """Create a sample handover package."""
        return HandoverPackage(
            id=str(uuid.uuid4()),
            generated_at=_utcnow(),
            semester="2025s1",
            executive_summary="This semester we completed the food planner MVP.",
            key_decisions=["decision-1", "decision-2"],
            lessons_learned=["learning-1", "learning-2", "learning-3"],
            known_issues=["Performance issues on mobile", "Accessibility improvements needed"],
            recommended_priorities=["Complete OAuth integration", "Add offline support"],
            human_reviewed=False,
            reviewer_notes=None,
        )

    async def test_save_and_get_handover(
        self, mock_research_data_adapter: ResearchDataAdapter, sample_package: HandoverPackage
    ) -> None:
        """Handover packages should be saved and retrieved correctly."""
        await mock_research_data_adapter.save_handover(sample_package)

        retrieved = await mock_research_data_adapter.get_handover(sample_package.semester)

        assert retrieved is not None
        assert retrieved.id == sample_package.id
        assert retrieved.semester == sample_package.semester
        assert retrieved.executive_summary == sample_package.executive_summary
        assert retrieved.key_decisions == sample_package.key_decisions
        assert retrieved.lessons_learned == sample_package.lessons_learned
        assert retrieved.known_issues == sample_package.known_issues
        assert retrieved.recommended_priorities == sample_package.recommended_priorities
        assert retrieved.human_reviewed is False

    async def test_get_handover_by_id(
        self, mock_research_data_adapter: ResearchDataAdapter, sample_package: HandoverPackage
    ) -> None:
        """get_handover_by_id should find package by UUID."""
        await mock_research_data_adapter.save_handover(sample_package)

        retrieved = await mock_research_data_adapter.get_handover_by_id(sample_package.id)

        assert retrieved is not None
        assert retrieved.id == sample_package.id

    async def test_get_nonexistent_handover(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """Getting a nonexistent handover should return None."""
        result = await mock_research_data_adapter.get_handover("nonexistent-semester")
        assert result is None

    async def test_list_handovers(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """list_handovers should return all packages."""
        packages = [
            HandoverPackage(
                id=str(uuid.uuid4()),
                generated_at=_utcnow(),
                semester=f"2025s{i}",
                executive_summary=f"Summary {i}",
            )
            for i in range(3)
        ]

        for p in packages:
            await mock_research_data_adapter.save_handover(p)

        result = await mock_research_data_adapter.list_handovers()
        assert len(result) == 3

    async def test_mark_handover_reviewed(
        self, mock_research_data_adapter: ResearchDataAdapter, sample_package: HandoverPackage
    ) -> None:
        """mark_handover_reviewed should update package."""
        await mock_research_data_adapter.save_handover(sample_package)

        success = await mock_research_data_adapter.mark_handover_reviewed(
            package_id=sample_package.id,
            approved=True,
            notes="LGTM - approved for handover",
        )

        assert success is True

        retrieved = await mock_research_data_adapter.get_handover_by_id(sample_package.id)
        assert retrieved is not None
        assert retrieved.human_reviewed is True
        assert retrieved.reviewer_notes == "LGTM - approved for handover"

    async def test_mark_nonexistent_handover_reviewed(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """Marking a nonexistent package should return False."""
        success = await mock_research_data_adapter.mark_handover_reviewed(
            package_id="nonexistent-id",
            approved=True,
        )
        assert success is False

    async def test_semester_uniqueness(
        self, mock_research_data_adapter: ResearchDataAdapter, sample_package: HandoverPackage
    ) -> None:
        """Saving a package with the same semester should update it."""
        await mock_research_data_adapter.save_handover(sample_package)

        # Create a new package with the same semester
        updated_package = HandoverPackage(
            id=str(uuid.uuid4()),  # Different ID
            generated_at=_utcnow(),
            semester="2025s1",  # Same semester
            executive_summary="Updated summary",
        )
        await mock_research_data_adapter.save_handover(updated_package)

        retrieved = await mock_research_data_adapter.get_handover("2025s1")
        assert retrieved is not None
        # Should have the new ID (replaced)
        assert retrieved.id == updated_package.id
        assert retrieved.executive_summary == "Updated summary"


class TestKnowledgeIntegration:
    """Integration tests for knowledge capture workflow."""

    async def test_full_semester_workflow(self, mock_research_data_adapter: ResearchDataAdapter) -> None:
        """Test capturing decisions, learnings, and generating handover."""
        adapter = mock_research_data_adapter
        # Capture some decisions
        decision1 = ArchitecturalDecision(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            team_id="team_a",
            title="Use Flutter for mobile app",
            context="Need cross-platform mobile development",
            decision="Use Flutter framework",
            rationale="Single codebase for iOS and Android",
            tags=["mobile", "framework"],
        )
        decision2 = ArchitecturalDecision(
            id=str(uuid.uuid4()),
            timestamp=_utcnow(),
            team_id="team_a",
            title="RESTful API design",
            context="Need to define API architecture",
            decision="Use RESTful endpoints with OpenAPI spec",
            rationale="Industry standard, good tooling",
            tags=["api", "architecture"],
        )

        await adapter.save_decision(decision1)
        await adapter.save_decision(decision2)

        # Capture some learnings
        learnings = [
            RetrospectiveLearning(
                id=str(uuid.uuid4()),
                timestamp=_utcnow(),
                team_id="team_a",
                sprint="2025s1-sprint1",
                category=LearningCategory.WENT_WELL,
                description="Daily standups helped coordination",
            ),
            RetrospectiveLearning(
                id=str(uuid.uuid4()),
                timestamp=_utcnow(),
                team_id="team_a",
                sprint="2025s1-sprint2",
                category=LearningCategory.TO_IMPROVE,
                description="Need better test coverage",
            ),
            RetrospectiveLearning(
                id=str(uuid.uuid4()),
                timestamp=_utcnow(),
                team_id="team_a",
                sprint="2025s1-sprint2",
                category=LearningCategory.ACTION_ITEM,
                description="Set up code coverage reporting",
                follow_up_status=FollowUpStatus.PENDING,
            ),
        ]

        for learning in learnings:
            await adapter.save_learning(learning)

        # Verify data was stored
        decisions = await adapter.list_decisions()
        assert len(decisions) == 2

        all_learnings = await adapter.list_learnings()
        assert len(all_learnings) == 3

        # Create handover package
        package = HandoverPackage(
            id=str(uuid.uuid4()),
            generated_at=_utcnow(),
            semester="2025s1",
            executive_summary="Completed 2 architectural decisions and 3 retrospective learnings.",
            key_decisions=[d.id for d in decisions],
            lessons_learned=[learning.id for learning in learnings],
            known_issues=["Need better test coverage"],
            recommended_priorities=["Set up code coverage reporting"],
        )

        await adapter.save_handover(package)

        # Verify handover
        retrieved = await adapter.get_handover("2025s1")
        assert retrieved is not None
        assert len(retrieved.key_decisions) == 2
        assert len(retrieved.lessons_learned) == 3

        # Mark as reviewed
        await adapter.mark_handover_reviewed(
            package_id=package.id,
            approved=True,
            notes="Ready for next semester",
        )

        final = await adapter.get_handover("2025s1")
        assert final is not None
        assert final.human_reviewed is True
