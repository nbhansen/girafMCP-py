"""GitHub adapter implementing RepositoryPort.

Provides access to GitHub repositories for the GIRAF organization,
with support for fetching files and generating permalinks for citations.
"""

import asyncio
import base64
import logging
import os
import time

import httpx

from girafmcp.core import (
    CodeSearchResult,
    FileContent,
    Repository,
    RepositoryPort,
    WikiPage,
    WikiSearchResult,
)

logger = logging.getLogger(__name__)

# How long a fetched wiki file listing is reused before asking GitHub again
WIKI_TREE_TTL_SECONDS = 300.0


class GitHubAPIError(Exception):
    """A GitHub API request failed in a way the caller should report."""


def _raise_for_status(response: httpx.Response) -> None:
    """Raise a GitHubAPIError with a readable message for failed responses."""
    if response.is_success:
        return
    status = response.status_code
    if status == 401:
        raise GitHubAPIError("GitHub API 401: missing or invalid GITHUB_TOKEN")
    if status in (403, 429) and response.headers.get("x-ratelimit-remaining") == "0":
        reset = response.headers.get("x-ratelimit-reset")
        when = f"; resets at {time.strftime('%H:%M:%S', time.localtime(int(reset)))}" if reset else ""
        raise GitHubAPIError(f"GitHub API {status}: rate limit exceeded{when}")
    try:
        detail = response.json().get("message", "")
    except ValueError:
        detail = response.text[:200]
    raise GitHubAPIError(f"GitHub API {status} for {response.request.url.path}: {detail}")


class GitHubAdapter(RepositoryPort):
    """GitHub API adapter for repository operations."""

    def __init__(
        self,
        org: str,
        token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        """Initialize the adapter.

        Args:
            org: GitHub organization name (e.g., 'aau-giraf')
            token: Optional GitHub token for authenticated requests.
                   Falls back to GITHUB_TOKEN environment variable.
            transport: Optional httpx transport, for tests.
        """
        self.org = org
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"

        # Default headers
        self._headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self._headers["Authorization"] = f"Bearer {self.token}"

        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        # repo -> (fetched_at, all markdown pages under docs/ with blob SHAs)
        self._wiki_trees: dict[str, tuple[float, list[tuple[WikiPage, str]]]] = {}
        # blob SHA -> decoded content; SHAs are content-addressed so entries never go stale
        self._blob_cache: dict[str, str] = {}

    @property
    def _http(self) -> httpx.AsyncClient:
        """Shared HTTP client, created on first use."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=30.0,
                transport=self._transport,
            )
        return self._client

    async def aclose(self) -> None:
        """Close the shared HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def list_repos(self, include_archived: bool = False) -> list[Repository]:
        """List all repositories in the organization.

        Args:
            include_archived: If True, include archived repositories. Default False.
        """
        repos: list[Repository] = []

        # Paginate through all repos
        page = 1
        while True:
            response = await self._http.get(
                f"/orgs/{self.org}/repos",
                params={"page": page, "per_page": 100},
            )
            _raise_for_status(response)
            data = response.json()

            if not data:
                break

            for repo in data:
                # Skip archived repos unless explicitly requested
                if repo.get("archived", False) and not include_archived:
                    continue

                repos.append(
                    Repository(
                        name=repo["name"],
                        description=repo.get("description") or "",
                        url=repo["html_url"],
                        language=repo.get("language"),
                        default_branch=repo.get("default_branch", "main"),
                    )
                )

            page += 1

        return repos

    async def get_file(
        self, repo: str, path: str, ref: str | None = None
    ) -> FileContent:
        """Get file content from a repository.

        Args:
            repo: Repository name
            path: File path within the repo
            ref: Git ref (branch, tag, commit). Defaults to default branch.

        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        params = {"ref": ref} if ref else {}
        response = await self._http.get(
            f"/repos/{self.org}/{repo}/contents/{path}", params=params
        )

        if response.status_code == 404:
            raise FileNotFoundError(f"File not found: {repo}/{path}")

        _raise_for_status(response)
        data = response.json()

        # Decode base64 content
        content = ""
        if data.get("content"):
            content = base64.b64decode(data["content"]).decode("utf-8")

        # Get the SHA for permalink
        sha = data.get("sha", "")

        # Build permalink URL (using commit SHA for permanence)
        permalink = f"https://github.com/{self.org}/{repo}/blob/{sha}/{path}"

        return FileContent(
            content=content,
            path=path,
            repo=repo,
            url=permalink,
            sha=sha,
        )

    async def search_code(
        self, query: str, repo: str | None = None, include_archived: bool = False
    ) -> list[CodeSearchResult]:
        """Search for code across repositories.

        Note: GitHub code search requires authentication and may be rate limited.

        Raises:
            GitHubAPIError: On missing token, rate limiting, or other API errors.

        Args:
            query: Search query
            repo: Optional repository to limit search to
            include_archived: If True, include archived repositories. Default False.
        """
        results: list[CodeSearchResult] = []

        # Build search query
        search_query = f"{query} org:{self.org}"
        if repo:
            search_query = f"{query} repo:{self.org}/{repo}"

        # Exclude archived repos unless explicitly requested
        if not include_archived:
            search_query += " archived:false"

        response = await self._http.get(
            "/search/code", params={"q": search_query, "per_page": 30}
        )
        # Code search requires authentication; 401 surfaces as a token error
        _raise_for_status(response)
        data = response.json()

        for item in data.get("items", []):
            results.append(
                CodeSearchResult(
                    repo=item["repository"]["name"],
                    path=item["path"],
                    url=item["html_url"],
                    matches=[],  # GitHub API doesn't return match snippets in search
                )
            )

        return results

    def get_permalink(
        self,
        repo: str,
        path: str,
        line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        """Generate a permalink to a file or line range.

        Note: This generates a URL pointing to the default branch.
        For true permalinks with commit SHA, use get_file() which
        returns a URL with the specific commit.

        Args:
            repo: Repository name
            path: File path
            line: Optional start line number
            end_line: Optional end line number (for ranges)

        Returns:
            URL to the file or line range
        """
        # Base URL to file (using HEAD, not ideal for true permalinks)
        url = f"https://github.com/{self.org}/{repo}/blob/HEAD/{path}"

        # Add line anchor if specified
        if line is not None:
            if end_line is not None and end_line > line:
                url = f"{url}#L{line}-L{end_line}"
            else:
                url = f"{url}#L{line}"

        return url

    # === Wiki Methods ===

    async def list_wiki_pages(
        self, repo: str = "wiki", include_legacy: bool = False
    ) -> list[WikiPage]:
        """List all markdown pages in the wiki.

        Args:
            repo: Repository containing the wiki (default: 'wiki')
            include_legacy: If True, include legacy pages. Default False.

        Returns:
            List of WikiPage objects
        """
        return [page for page, _ in await self._wiki_pages_with_sha(repo, include_legacy)]

    async def _wiki_pages_with_sha(
        self, repo: str, include_legacy: bool
    ) -> list[tuple[WikiPage, str]]:
        """Wiki pages paired with their blob SHA, from a cached recursive tree listing."""
        cached = self._wiki_trees.get(repo)
        if cached is None or time.monotonic() - cached[0] > WIKI_TREE_TTL_SECONDS:
            cached = (time.monotonic(), await self._fetch_wiki_tree(repo))
            self._wiki_trees[repo] = cached

        return [
            (page, sha)
            for page, sha in cached[1]
            if include_legacy or "Legacy" not in page.path.split("/")[1:-1]
        ]

    async def _fetch_wiki_tree(self, repo: str) -> list[tuple[WikiPage, str]]:
        """Fetch every markdown file under docs/ with one recursive tree request."""
        response = await self._http.get(
            f"/repos/{self.org}/{repo}/git/trees/HEAD", params={"recursive": "1"}
        )
        _raise_for_status(response)
        data = response.json()
        if data.get("truncated"):
            logger.warning(f"Wiki tree for {repo} was truncated by GitHub; some pages are missing")

        pages: list[tuple[WikiPage, str]] = []
        for item in data.get("tree", []):
            path: str = item["path"]
            parts = path.split("/")
            if (
                item["type"] != "blob"
                or parts[0] != "docs"
                or not path.endswith(".md")
                or any(part.startswith(".") for part in parts)
            ):
                continue
            pages.append((self._wiki_page(repo, path), item["sha"]))
        return pages

    def _wiki_page(self, repo: str, path: str) -> WikiPage:
        """Build a WikiPage (title and MkDocs URL) from a docs/ path."""
        filename = path.rsplit("/", 1)[-1]
        name = filename.replace(".md", "").replace("_", " ")
        if name == "index":
            # Use parent folder name for index files
            parts = path.split("/")
            name = parts[-2].replace("_", " ") if len(parts) > 2 else "Home"

        # Build wiki URL (MkDocs style)
        wiki_path = path.replace("docs/", "", 1).replace(".md", "/")
        if wiki_path.endswith("index/"):
            wiki_path = wiki_path.removesuffix("index/")

        return WikiPage(
            path=path,
            title=name.title(),
            url=f"https://aau-giraf.github.io/wiki/{wiki_path}",
            github_url=f"https://github.com/{self.org}/{repo}/blob/HEAD/{path}",
        )

    async def _blob_content(self, repo: str, sha: str) -> str:
        """Decoded content of a git blob, cached by SHA."""
        if sha not in self._blob_cache:
            response = await self._http.get(f"/repos/{self.org}/{repo}/git/blobs/{sha}")
            _raise_for_status(response)
            self._blob_cache[sha] = base64.b64decode(response.json()["content"]).decode("utf-8")
        return self._blob_cache[sha]

    async def search_wiki(
        self, query: str, repo: str = "wiki", limit: int = 10, include_legacy: bool = False
    ) -> list[WikiSearchResult]:
        """Search wiki pages by keyword.

        Lists pages with one cached tree request and fetches only page contents
        not already cached, so repeated searches cost few or no API calls.

        Args:
            query: Search query (keywords)
            repo: Repository containing the wiki
            limit: Maximum results to return
            include_legacy: If True, include legacy pages. Default False.

        Returns:
            List of WikiSearchResult sorted by relevance

        Raises:
            GitHubAPIError: If the page listing fails, or no page content could be fetched.
        """
        pages = await self._wiki_pages_with_sha(repo, include_legacy)
        query_terms = query.lower().split()

        # Semaphore to limit concurrent requests (avoid rate limiting)
        semaphore = asyncio.Semaphore(10)
        failures: list[str] = []

        async def search_page(page: WikiPage, sha: str) -> WikiSearchResult | None:
            """Search a single page for matches."""
            async with semaphore:
                try:
                    content = await self._blob_content(repo, sha)
                except (httpx.HTTPError, GitHubAPIError, ValueError) as e:
                    logger.warning(f"Skipping wiki page {page.path}: {e}")
                    failures.append(str(e))
                    return None

            # Search for matches
            title_lower = page.title.lower()
            matches: list[str] = []
            term_hits = 0

            for term in query_terms:
                # Title match (weighted higher)
                if term in title_lower:
                    term_hits += 2

                # Find matching lines
                for line in content.split("\n"):
                    if term in line.lower() and line.strip():
                        clean_line = line.strip()
                        if clean_line and clean_line not in matches:
                            matches.append(clean_line[:200])
                            term_hits += 1

            if term_hits == 0:
                return None
            relevance = min(1.0, term_hits / (len(query_terms) * 5))
            return WikiSearchResult(page=page, matches=matches[:5], relevance=relevance)

        results_raw = await asyncio.gather(*(search_page(page, sha) for page, sha in pages))

        if pages and len(failures) == len(pages):
            raise GitHubAPIError(f"Could not fetch any wiki page: {failures[0]}")

        # Filter out None results and sort
        results = [r for r in results_raw if r is not None]
        results.sort(key=lambda r: r.relevance, reverse=True)
        return results[:limit]
