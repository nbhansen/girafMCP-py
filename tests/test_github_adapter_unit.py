"""Unit tests for GitHubAdapter using a mock HTTP transport (no network)."""

import base64
from collections import Counter

import httpx
import pytest

from girafmcp.adapters.github_adapter import GitHubAdapter, GitHubAPIError

WIKI_FILES = {
    "docs/index.md": ("sha-home", "Welcome to the GIRAF wiki"),
    "docs/Backend/Weekplanner_API.md": ("sha-api", "The weekplanner API uses JWT auth"),
    "docs/Legacy/old.md": ("sha-old", "Legacy JWT notes"),
    "docs/.hidden/secret.md": ("sha-hidden", "JWT hidden"),
}


def _tree() -> dict[str, object]:
    tree = [{"path": path, "type": "blob", "sha": sha} for path, (sha, _) in WIKI_FILES.items()]
    tree.append({"path": "docs/Backend", "type": "tree", "sha": "sha-dir"})
    tree.append({"path": "mkdocs.yml", "type": "blob", "sha": "sha-cfg"})
    return {"tree": tree, "truncated": False}


def _blob(sha: str) -> dict[str, str]:
    content = next(text for s, text in WIKI_FILES.values() if s == sha)
    return {"content": base64.b64encode(content.encode()).decode()}


class FakeGitHub:
    """Records requests and serves canned wiki responses."""

    def __init__(self, fail_blobs: bool = False) -> None:
        self.calls: Counter[str] = Counter()
        self.fail_blobs = fail_blobs

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls[path] += 1
        if path.endswith("/git/trees/HEAD"):
            return httpx.Response(200, json=_tree())
        if "/git/blobs/" in path:
            if self.fail_blobs:
                return httpx.Response(500, json={"message": "boom"})
            return httpx.Response(200, json=_blob(path.rsplit("/", 1)[-1]))
        return httpx.Response(404, json={"message": "Not Found"})


def _adapter(handler: object) -> GitHubAdapter:
    return GitHubAdapter(org="aau-giraf", token="t", transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


class TestCodeSearchErrors:
    """search_code must report API failures instead of returning no results."""

    async def test_missing_token_raises(self):
        adapter = _adapter(lambda r: httpx.Response(401, json={"message": "Requires authentication"}))
        with pytest.raises(GitHubAPIError, match="GITHUB_TOKEN"):
            await adapter.search_code("jwt")

    async def test_rate_limit_raises(self):
        adapter = _adapter(
            lambda r: httpx.Response(
                403,
                headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1700000000"},
                json={"message": "API rate limit exceeded"},
            )
        )
        with pytest.raises(GitHubAPIError, match="rate limit"):
            await adapter.search_code("jwt")

    async def test_other_errors_include_status_and_message(self):
        adapter = _adapter(lambda r: httpx.Response(422, json={"message": "Validation Failed"}))
        with pytest.raises(GitHubAPIError, match="422.*Validation Failed"):
            await adapter.search_code("jwt")


class TestWikiSearch:
    """Wiki search lists pages via one tree call and caches page contents."""

    async def test_lists_markdown_pages_and_skips_legacy_and_hidden(self):
        adapter = _adapter(FakeGitHub())
        pages = await adapter.list_wiki_pages()
        assert {p.path for p in pages} == {"docs/index.md", "docs/Backend/Weekplanner_API.md"}

    async def test_include_legacy(self):
        adapter = _adapter(FakeGitHub())
        pages = await adapter.list_wiki_pages(include_legacy=True)
        assert "docs/Legacy/old.md" in {p.path for p in pages}

    async def test_builds_titles_and_urls(self):
        adapter = _adapter(FakeGitHub())
        pages = {p.path: p for p in await adapter.list_wiki_pages()}
        home = pages["docs/index.md"]
        api = pages["docs/Backend/Weekplanner_API.md"]
        assert home.title == "Home"
        assert home.url == "https://aau-giraf.github.io/wiki/"
        assert api.title == "Weekplanner Api"
        assert api.url == "https://aau-giraf.github.io/wiki/Backend/Weekplanner_API/"

    async def test_finds_matching_page(self):
        adapter = _adapter(FakeGitHub())
        results = await adapter.search_wiki("jwt")
        assert [r.page.path for r in results] == ["docs/Backend/Weekplanner_API.md"]
        assert "JWT" in results[0].matches[0]

    async def test_repeat_search_hits_cache(self):
        fake = FakeGitHub()
        adapter = _adapter(fake)
        await adapter.search_wiki("jwt")
        first = sum(fake.calls.values())
        await adapter.search_wiki("weekplanner")
        assert sum(fake.calls.values()) == first

    async def test_all_pages_failing_raises(self):
        adapter = _adapter(FakeGitHub(fail_blobs=True))
        with pytest.raises(GitHubAPIError, match="Could not fetch any wiki page"):
            await adapter.search_wiki("jwt")

    async def test_tree_failure_raises(self):
        adapter = _adapter(lambda r: httpx.Response(401, json={"message": "Bad credentials"}))
        with pytest.raises(GitHubAPIError):
            await adapter.search_wiki("jwt")
