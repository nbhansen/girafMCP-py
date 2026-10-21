"""Tests for GitHub Projects V2 adapter.

These tests require a GitHub token with 'read:project' scope.
Tests are skipped if the scope is not available.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from girafmcp.adapters.github_projects_adapter import GitHubProjectsAdapter
from girafmcp.core.types import Project


class TestGitHubProjectsAdapterUnit:
    """Unit tests for GitHubProjectsAdapter (no API calls)."""

    def test_init_with_token(self) -> None:
        """Adapter should accept token argument."""
        adapter = GitHubProjectsAdapter(org="test-org", token="test-token")
        assert adapter.org == "test-org"
        assert adapter.token == "test-token"
        assert "Bearer test-token" in adapter._headers["Authorization"]

    def test_init_without_token(self) -> None:
        """Adapter should fall back to environment variable."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "env-token"}):
            adapter = GitHubProjectsAdapter(org="test-org")
            assert adapter.token == "env-token"

    def test_init_no_token_available(self) -> None:
        """Adapter should handle missing token."""
        with patch.dict(os.environ, {}, clear=True):
            adapter = GitHubProjectsAdapter(org="test-org", token=None)
            assert adapter.token is None
            assert "Authorization" not in adapter._headers


class TestGitHubProjectsAdapterMocked:
    """Tests with mocked HTTP responses."""

    @pytest.fixture
    def adapter(self) -> GitHubProjectsAdapter:
        """Create adapter with test token."""
        return GitHubProjectsAdapter(org="aau-giraf", token="test-token")

    @pytest.mark.asyncio
    async def test_list_org_projects_success(self, adapter: GitHubProjectsAdapter) -> None:
        """Should parse GraphQL response correctly."""
        mock_response = {
            "data": {
                "organization": {
                    "projectsV2": {
                        "nodes": [
                            {
                                "id": "PVT_123",
                                "number": 1,
                                "title": "Sprint Board",
                                "shortDescription": "Track sprint work",
                                "url": "https://github.com/orgs/aau-giraf/projects/1",
                                "closed": False,
                                "public": True,
                                "createdAt": "2025-01-01T00:00:00Z",
                                "updatedAt": "2025-01-15T00:00:00Z",
                                "items": {"totalCount": 25},
                            }
                        ]
                    }
                }
            }
        }

        with patch.object(adapter, "_graphql_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response["data"]
            projects = await adapter.list_org_projects(limit=10)

            assert len(projects) == 1
            assert projects[0].id == "PVT_123"
            assert projects[0].number == 1
            assert projects[0].title == "Sprint Board"
            assert projects[0].items_count == 25
            assert projects[0].closed is False
            assert projects[0].public is True

    @pytest.mark.asyncio
    async def test_list_org_projects_empty(self, adapter: GitHubProjectsAdapter) -> None:
        """Should handle empty response."""
        with patch.object(adapter, "_graphql_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {"organization": {"projectsV2": {"nodes": []}}}
            projects = await adapter.list_org_projects()
            assert projects == []

    @pytest.mark.asyncio
    async def test_get_project_success(self, adapter: GitHubProjectsAdapter) -> None:
        """Should fetch single project."""
        mock_response = {
            "organization": {
                "projectV2": {
                    "id": "PVT_456",
                    "number": 2,
                    "title": "Backlog",
                    "shortDescription": None,
                    "url": "https://github.com/orgs/aau-giraf/projects/2",
                    "closed": False,
                    "public": False,
                    "createdAt": "2025-01-01T00:00:00Z",
                    "updatedAt": "2025-01-20T00:00:00Z",
                    "items": {"totalCount": 50},
                }
            }
        }

        with patch.object(adapter, "_graphql_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response
            project = await adapter.get_project(2)

            assert project is not None
            assert project.number == 2
            assert project.title == "Backlog"
            assert project.description is None
            assert project.items_count == 50

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, adapter: GitHubProjectsAdapter) -> None:
        """Should return None for missing project."""
        with patch.object(adapter, "_graphql_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {"organization": {"projectV2": None}}
            project = await adapter.get_project(999)
            assert project is None

    @pytest.mark.asyncio
    async def test_list_project_items_success(self, adapter: GitHubProjectsAdapter) -> None:
        """Should parse project items."""
        mock_project = Project(
            id="PVT_123",
            number=1,
            title="Test",
            description=None,
            url="https://example.com",
            closed=False,
            public=True,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-15T00:00:00Z",
            items_count=2,
        )

        mock_items_response = {
            "node": {
                "items": {
                    "nodes": [
                        {
                            "id": "PVTI_1",
                            "type": "ISSUE",
                            "createdAt": "2025-01-10T00:00:00Z",
                            "updatedAt": "2025-01-12T00:00:00Z",
                            "fieldValueByName": {"name": "In Progress"},
                            "content": {
                                "title": "Fix login bug",
                                "url": "https://github.com/aau-giraf/repo/issues/1",
                                "assignees": {"nodes": [{"login": "developer1"}]},
                                "labels": {"nodes": [{"name": "bug"}]},
                                "repository": {"name": "foodplanner"},
                            },
                        },
                        {
                            "id": "PVTI_2",
                            "type": "DRAFT_ISSUE",
                            "createdAt": "2025-01-11T00:00:00Z",
                            "updatedAt": "2025-01-13T00:00:00Z",
                            "fieldValueByName": {"name": "Todo"},
                            "content": {
                                "title": "Research new feature",
                                "assignees": {"nodes": []},
                            },
                        },
                    ]
                }
            }
        }

        with patch.object(adapter, "get_project", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_project
            with patch.object(adapter, "_graphql_query", new_callable=AsyncMock) as mock_query:
                mock_query.return_value = mock_items_response
                items = await adapter.list_project_items(1)

                assert len(items) == 2

                # Check first item (issue)
                assert items[0].type == "ISSUE"
                assert items[0].title == "Fix login bug"
                assert items[0].status == "In Progress"
                assert items[0].assignees == ["developer1"]
                assert items[0].labels == ["bug"]
                assert items[0].repository == "foodplanner"

                # Check second item (draft)
                assert items[1].type == "DRAFT_ISSUE"
                assert items[1].title == "Research new feature"
                assert items[1].status == "Todo"
                assert items[1].url is None

    @pytest.mark.asyncio
    async def test_list_project_items_with_filter(self, adapter: GitHubProjectsAdapter) -> None:
        """Should filter items by status."""
        mock_project = Project(
            id="PVT_123",
            number=1,
            title="Test",
            description=None,
            url="https://example.com",
            closed=False,
            public=True,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-15T00:00:00Z",
            items_count=2,
        )

        mock_items_response = {
            "node": {
                "items": {
                    "nodes": [
                        {
                            "id": "PVTI_1",
                            "type": "ISSUE",
                            "createdAt": "2025-01-10T00:00:00Z",
                            "updatedAt": "2025-01-12T00:00:00Z",
                            "fieldValueByName": {"name": "Done"},
                            "content": {
                                "title": "Completed task",
                                "url": "https://example.com/1",
                                "assignees": {"nodes": []},
                                "labels": {"nodes": []},
                                "repository": {"name": "repo"},
                            },
                        },
                        {
                            "id": "PVTI_2",
                            "type": "ISSUE",
                            "createdAt": "2025-01-11T00:00:00Z",
                            "updatedAt": "2025-01-13T00:00:00Z",
                            "fieldValueByName": {"name": "Todo"},
                            "content": {
                                "title": "Pending task",
                                "url": "https://example.com/2",
                                "assignees": {"nodes": []},
                                "labels": {"nodes": []},
                                "repository": {"name": "repo"},
                            },
                        },
                    ]
                }
            }
        }

        with patch.object(adapter, "get_project", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_project
            with patch.object(adapter, "_graphql_query", new_callable=AsyncMock) as mock_query:
                mock_query.return_value = mock_items_response
                items = await adapter.list_project_items(1, status_filter="Done")

                # Only the "Done" item should be returned
                assert len(items) == 1
                assert items[0].status == "Done"

    @pytest.mark.asyncio
    async def test_check_token_scope_no_token(self) -> None:
        """Should report missing token."""
        adapter = GitHubProjectsAdapter(org="test", token=None)
        # Clear any env var
        with patch.dict(os.environ, {}, clear=True):
            adapter.token = None  # Reset after potential env fallback
            result = await adapter.check_token_scope()
            assert result.has_project_scope is False
            assert "No GitHub token" in result.message

    @pytest.mark.asyncio
    async def test_check_token_scope_with_project_scope(
        self, adapter: GitHubProjectsAdapter
    ) -> None:
        """Should detect read:project scope."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"X-OAuth-Scopes": "repo, read:project, workflow"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await adapter.check_token_scope()

            assert result.has_project_scope is True
            assert "read:project" in result.scopes
            assert "available" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_token_scope_without_project_scope(
        self, adapter: GitHubProjectsAdapter
    ) -> None:
        """Should detect missing read:project scope."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"X-OAuth-Scopes": "repo, workflow"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await adapter.check_token_scope()

            assert result.has_project_scope is False
            assert "read:project" not in result.scopes
            assert "gh auth refresh" in result.message


# Integration tests - only run if token with proper scope is available
@pytest.mark.integration
class TestGitHubProjectsAdapterIntegration:
    """Integration tests that make real API calls.

    These tests require:
    - GITHUB_TOKEN environment variable set
    - Token must have 'read:project' scope

    Run with: pytest -m integration tests/test_github_projects_adapter.py
    """

    @pytest.fixture
    async def adapter(self) -> GitHubProjectsAdapter:
        """Create adapter and verify scope."""
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set")

        adapter = GitHubProjectsAdapter(org="aau-giraf", token=token)
        result = await adapter.check_token_scope()

        if not result.has_project_scope:
            pytest.skip(
                "Token lacks read:project scope. Run: gh auth refresh -s read:project"
            )

        return adapter

    @pytest.mark.asyncio
    async def test_list_projects_integration(
        self, adapter: GitHubProjectsAdapter
    ) -> None:
        """Should list projects from aau-giraf org."""
        projects = await adapter.list_org_projects(limit=5)
        # We expect some projects to exist, but don't fail if empty
        assert isinstance(projects, list)

    @pytest.mark.asyncio
    async def test_check_scope_integration(
        self, adapter: GitHubProjectsAdapter
    ) -> None:
        """Should report correct scope status."""
        result = await adapter.check_token_scope()
        assert result.has_project_scope is True
        assert isinstance(result.scopes, list)
