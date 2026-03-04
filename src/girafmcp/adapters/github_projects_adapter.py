"""GitHub Projects V2 adapter implementing GitHubProjectsPort.

Provides read-only access to GitHub Projects V2 via GraphQL API.
GitHub Projects V2 does not have a REST API - GraphQL is required.
"""

import os
from typing import Any

import httpx

from girafmcp.core.ports import GitHubProjectsPort
from girafmcp.core.types import Project, ProjectItem, TokenScopeResult


class GitHubProjectsAdapter(GitHubProjectsPort):
    """GitHub Projects V2 adapter using GraphQL API."""

    GRAPHQL_URL = "https://api.github.com/graphql"

    def __init__(self, org: str, token: str | None = None):
        """Initialize the adapter.

        Args:
            org: GitHub organization name (e.g., 'aau-giraf')
            token: Optional GitHub token. Falls back to GITHUB_TOKEN env var.
                   Requires 'read:project' scope for Projects V2 access.
        """
        self.org = org
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self._headers["Authorization"] = f"Bearer {self.token}"

    async def _graphql_query(self, query: str, variables: dict[str, Any] | None = None) -> dict:
        """Execute a GraphQL query.

        Args:
            query: GraphQL query string.
            variables: Optional variables for the query.

        Returns:
            Response data dict.

        Raises:
            httpx.HTTPStatusError: On HTTP errors.
            ValueError: On GraphQL errors.
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.GRAPHQL_URL,
                headers=self._headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                errors = result["errors"]
                error_messages = [e.get("message", str(e)) for e in errors]
                raise ValueError(f"GraphQL errors: {'; '.join(error_messages)}")

            return result.get("data", {})

    async def list_org_projects(self, limit: int = 20) -> list[Project]:
        """List all Projects V2 in the organization."""
        query = """
        query($org: String!, $limit: Int!) {
            organization(login: $org) {
                projectsV2(first: $limit, orderBy: {field: UPDATED_AT, direction: DESC}) {
                    nodes {
                        id
                        number
                        title
                        shortDescription
                        url
                        closed
                        public
                        createdAt
                        updatedAt
                        items {
                            totalCount
                        }
                    }
                }
            }
        }
        """
        try:
            data = await self._graphql_query(query, {"org": self.org, "limit": limit})
            org_data = data.get("organization")
            if not org_data:
                return []

            projects_data = org_data.get("projectsV2", {}).get("nodes", [])
            return [
                Project(
                    id=p["id"],
                    number=p["number"],
                    title=p["title"],
                    description=p.get("shortDescription"),
                    url=p["url"],
                    closed=p["closed"],
                    public=p["public"],
                    created_at=p["createdAt"],
                    updated_at=p["updatedAt"],
                    items_count=p.get("items", {}).get("totalCount", 0),
                )
                for p in projects_data
                if p is not None
            ]
        except ValueError as e:
            if "read:project" in str(e).lower() or "insufficient" in str(e).lower():
                raise ValueError(
                    "GitHub token lacks 'read:project' scope. "
                    "Run: gh auth refresh -s read:project"
                ) from e
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ValueError("GitHub token is invalid or missing") from e
            raise

    async def get_project(self, project_number: int) -> Project | None:
        """Get a specific project by number."""
        query = """
        query($org: String!, $number: Int!) {
            organization(login: $org) {
                projectV2(number: $number) {
                    id
                    number
                    title
                    shortDescription
                    url
                    closed
                    public
                    createdAt
                    updatedAt
                    items {
                        totalCount
                    }
                }
            }
        }
        """
        try:
            data = await self._graphql_query(
                query, {"org": self.org, "number": project_number}
            )
            org_data = data.get("organization")
            if not org_data:
                return None

            p = org_data.get("projectV2")
            if not p:
                return None

            return Project(
                id=p["id"],
                number=p["number"],
                title=p["title"],
                description=p.get("shortDescription"),
                url=p["url"],
                closed=p["closed"],
                public=p["public"],
                created_at=p["createdAt"],
                updated_at=p["updatedAt"],
                items_count=p.get("items", {}).get("totalCount", 0),
            )
        except ValueError as e:
            if "read:project" in str(e).lower() or "insufficient" in str(e).lower():
                raise ValueError(
                    "GitHub token lacks 'read:project' scope. "
                    "Run: gh auth refresh -s read:project"
                ) from e
            raise

    async def list_project_items(
        self,
        project_number: int,
        limit: int = 50,
        status_filter: str | None = None,
    ) -> list[ProjectItem]:
        """List items in a project."""
        # First get the project to get its ID
        project = await self.get_project(project_number)
        if not project:
            return []

        # Query items with content details
        query = """
        query($projectId: ID!, $limit: Int!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    items(first: $limit) {
                        nodes {
                            id
                            createdAt
                            updatedAt
                            type
                            fieldValueByName(name: "Status") {
                                ... on ProjectV2ItemFieldSingleSelectValue {
                                    name
                                }
                            }
                            content {
                                ... on Issue {
                                    title
                                    url
                                    assignees(first: 10) {
                                        nodes {
                                            login
                                        }
                                    }
                                    labels(first: 10) {
                                        nodes {
                                            name
                                        }
                                    }
                                    repository {
                                        name
                                    }
                                }
                                ... on PullRequest {
                                    title
                                    url
                                    assignees(first: 10) {
                                        nodes {
                                            login
                                        }
                                    }
                                    labels(first: 10) {
                                        nodes {
                                            name
                                        }
                                    }
                                    repository {
                                        name
                                    }
                                }
                                ... on DraftIssue {
                                    title
                                    assignees(first: 10) {
                                        nodes {
                                            login
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        try:
            data = await self._graphql_query(query, {"projectId": project.id, "limit": limit})
            node = data.get("node")
            if not node:
                return []

            items_data = node.get("items", {}).get("nodes", [])
            items: list[ProjectItem] = []

            for item in items_data:
                if item is None:
                    continue

                content = item.get("content") or {}
                status_field = item.get("fieldValueByName")
                status = status_field.get("name") if status_field else None

                # Skip if status filter is applied and doesn't match
                if status_filter and status != status_filter:
                    continue

                # Extract assignees
                assignees_data = content.get("assignees", {}).get("nodes", [])
                assignees = [a["login"] for a in assignees_data if a]

                # Extract labels
                labels_data = content.get("labels", {}).get("nodes", [])
                labels = [label["name"] for label in labels_data if label]

                # Extract repository
                repo_data = content.get("repository")
                repository = repo_data.get("name") if repo_data else None

                items.append(
                    ProjectItem(
                        id=item["id"],
                        type=item["type"],
                        title=content.get("title", "Untitled"),
                        url=content.get("url"),
                        status=status,
                        assignees=assignees,
                        labels=labels,
                        repository=repository,
                        created_at=item.get("createdAt", ""),
                        updated_at=item.get("updatedAt", ""),
                    )
                )

            return items
        except ValueError as e:
            if "read:project" in str(e).lower() or "insufficient" in str(e).lower():
                raise ValueError(
                    "GitHub token lacks 'read:project' scope. "
                    "Run: gh auth refresh -s read:project"
                ) from e
            raise

    async def check_token_scope(self) -> TokenScopeResult:
        """Check if the token has required scopes for Projects V2."""
        if not self.token:
            return TokenScopeResult(
                has_project_scope=False,
                scopes=[],
                message="No GitHub token configured. Set GITHUB_TOKEN environment variable.",
            )

        # Check scopes via REST API header
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.github.com/user",
                    headers=self._headers,
                    timeout=10.0,
                )
                response.raise_for_status()

                # GitHub returns scopes in X-OAuth-Scopes header
                scopes_header = response.headers.get("X-OAuth-Scopes", "")
                scopes = [s.strip() for s in scopes_header.split(",") if s.strip()]

                has_project = "read:project" in scopes or "project" in scopes

                if has_project:
                    message = "Token has 'read:project' scope. Projects V2 access available."
                else:
                    message = (
                        "Token lacks 'read:project' scope. "
                        "Run: gh auth refresh -s read:project"
                    )

                return TokenScopeResult(
                    has_project_scope=has_project,
                    scopes=scopes,
                    message=message,
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    return TokenScopeResult(
                        has_project_scope=False,
                        scopes=[],
                        message="GitHub token is invalid or expired.",
                    )
                raise
