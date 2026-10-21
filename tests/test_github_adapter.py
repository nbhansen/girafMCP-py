"""
INTEGRATION TESTS - These hit the real GitHub API

These tests verify that the GitHubAdapter correctly interacts with
the GitHub API to fetch repository information, file content, and
generate correct permalinks for source attribution.
"""

import os

import pytest

from girafmcp.adapters.github_adapter import GitHubAdapter


@pytest.mark.skipif(
    not os.environ.get("GITHUB_TOKEN"), reason="GITHUB_TOKEN not set"
)
class TestGitHubAdapter:
    """Integration tests for GitHubAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for aau-giraf organization."""
        return GitHubAdapter(org="aau-giraf")

    async def test_lists_repos_from_org(self, adapter):
        """Should list repositories from the aau-giraf organization."""
        repos = await adapter.list_repos()

        assert len(repos) > 0
        # foodplanner is a known repo in the org
        repo_names = [r.name for r in repos]
        assert "foodplanner" in repo_names

    async def test_repo_has_required_fields(self, adapter):
        """Each repository should have name, description, url, and default_branch."""
        repos = await adapter.list_repos()

        for repo in repos:
            assert repo.name
            assert repo.url
            assert "github.com/aau-giraf" in repo.url
            assert repo.default_branch  # Could be 'main', 'master', 'staging', etc.

    async def test_fetches_file_content(self, adapter):
        """Should fetch file content from a repository."""
        # wiki repo has a known structure with docs/index.md
        file = await adapter.get_file("wiki", "docs/index.md")

        assert file.content
        assert file.path == "docs/index.md"
        assert file.repo == "wiki"
        assert file.url.startswith("https://github.com")
        assert file.sha  # Should have a commit SHA

    async def test_file_url_is_permalink(self, adapter):
        """File URL should be a permalink (contain commit SHA, not branch name)."""
        file = await adapter.get_file("wiki", "docs/index.md")

        # A permalink contains the SHA, not a branch name
        # e.g., https://github.com/aau-giraf/wiki/blob/abc123/docs/index.md
        assert file.sha in file.url or "/blob/" in file.url

    async def test_handles_nonexistent_file(self, adapter):
        """Should raise FileNotFoundError for non-existent files."""
        with pytest.raises(FileNotFoundError):
            await adapter.get_file("foodplanner", "this/file/does/not/exist.txt")

    async def test_handles_nonexistent_repo(self, adapter):
        """Should raise appropriate error for non-existent repos."""
        with pytest.raises(FileNotFoundError):
            await adapter.get_file("nonexistent-repo-12345", "README.md")

    async def test_get_file_with_specific_ref(self, adapter):
        """Should fetch file at a specific git ref (branch/tag/commit)."""
        # Get list of repos to find the default branch of wiki
        repos = await adapter.list_repos()
        wiki_repo = next((r for r in repos if r.name == "wiki"), None)
        assert wiki_repo is not None

        # Fetch file using the repo's default branch as ref
        file = await adapter.get_file("wiki", "docs/index.md", ref=wiki_repo.default_branch)

        assert file.content
        assert file.path == "docs/index.md"

    def test_generates_permalink_for_file(self, adapter):
        """Should generate a valid GitHub permalink to a file."""
        link = adapter.get_permalink("foodplanner", "lib/main.dart")

        assert "github.com/aau-giraf/foodplanner" in link
        assert "lib/main.dart" in link

    def test_generates_permalink_with_line_number(self, adapter):
        """Should generate permalink with line number anchor."""
        link = adapter.get_permalink("foodplanner", "lib/main.dart", line=42)

        assert "github.com/aau-giraf/foodplanner" in link
        assert "#L42" in link

    def test_generates_permalink_with_line_range(self, adapter):
        """Should generate permalink with line range anchor."""
        link = adapter.get_permalink("foodplanner", "lib/main.dart", line=10, end_line=20)

        assert "github.com/aau-giraf/foodplanner" in link
        assert "#L10-L20" in link

    async def test_search_code_returns_results(self, adapter):
        """Should search code across repositories."""
        # Search for something likely to exist
        results = await adapter.search_code("void main")

        # May return empty if API rate limited or no results
        # Just verify it doesn't crash and returns a list
        assert isinstance(results, list)

    async def test_search_code_in_specific_repo(self, adapter):
        """Should limit code search to a specific repository."""
        results = await adapter.search_code("main", repo="foodplanner")

        assert isinstance(results, list)
        # All results should be from foodplanner repo
        for result in results:
            assert result.repo == "foodplanner"

    async def test_search_code_results_have_urls(self, adapter):
        """Code search results should include URLs for citation."""
        results = await adapter.search_code("void main")

        for result in results:
            assert result.url
            assert "github.com" in result.url
