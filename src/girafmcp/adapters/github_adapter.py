"""GitHub adapter implementing RepositoryPort.

Provides access to GitHub repositories for the GIRAF organization,
with support for fetching files and generating permalinks for citations.
"""

import base64
import os

import httpx

import re

from girafmcp.core import (
    CodeSearchResult,
    FileContent,
    Repository,
    RepositoryPort,
    WikiPage,
    WikiSearchResult,
)


class GitHubAdapter(RepositoryPort):
    """GitHub API adapter for repository operations."""

    def __init__(self, org: str, token: str | None = None):
        """Initialize the adapter.

        Args:
            org: GitHub organization name (e.g., 'aau-giraf')
            token: Optional GitHub token for authenticated requests.
                   Falls back to GITHUB_TOKEN environment variable.
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

    async def list_repos(self) -> list[Repository]:
        """List all repositories in the organization."""
        repos: list[Repository] = []

        async with httpx.AsyncClient() as client:
            # Paginate through all repos
            page = 1
            while True:
                response = await client.get(
                    f"{self.base_url}/orgs/{self.org}/repos",
                    headers=self._headers,
                    params={"page": page, "per_page": 100},
                )
                response.raise_for_status()
                data = response.json()

                if not data:
                    break

                for repo in data:
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
        async with httpx.AsyncClient() as client:
            # Build URL with optional ref
            url = f"{self.base_url}/repos/{self.org}/{repo}/contents/{path}"
            params = {}
            if ref:
                params["ref"] = ref

            response = await client.get(url, headers=self._headers, params=params)

            if response.status_code == 404:
                raise FileNotFoundError(f"File not found: {repo}/{path}")

            response.raise_for_status()
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
        self, query: str, repo: str | None = None
    ) -> list[CodeSearchResult]:
        """Search for code across repositories.

        Note: GitHub code search requires authentication and may be rate limited.

        Args:
            query: Search query
            repo: Optional repository to limit search to
        """
        results: list[CodeSearchResult] = []

        # Build search query
        search_query = f"{query} org:{self.org}"
        if repo:
            search_query = f"{query} repo:{self.org}/{repo}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/search/code",
                    headers=self._headers,
                    params={"q": search_query, "per_page": 30},
                )

                # Code search requires authentication - return empty if 401
                if response.status_code == 401:
                    return []

                response.raise_for_status()
                data = response.json()

                for item in data.get("items", []):
                    repo_name = item["repository"]["name"]
                    file_path = item["path"]

                    results.append(
                        CodeSearchResult(
                            repo=repo_name,
                            path=file_path,
                            url=item["html_url"],
                            matches=[],  # GitHub API doesn't return match snippets in search
                        )
                    )

            except httpx.HTTPStatusError:
                # Return empty on API errors (rate limiting, etc.)
                pass

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

    async def list_wiki_pages(self, repo: str = "wiki") -> list[WikiPage]:
        """List all markdown pages in the wiki.

        Args:
            repo: Repository containing the wiki (default: 'wiki')

        Returns:
            List of WikiPage objects
        """
        pages: list[WikiPage] = []

        async with httpx.AsyncClient() as client:
            await self._fetch_wiki_pages_recursive(client, repo, "docs", pages)

        return pages

    async def _fetch_wiki_pages_recursive(
        self,
        client: httpx.AsyncClient,
        repo: str,
        path: str,
        pages: list[WikiPage],
    ) -> None:
        """Recursively fetch wiki pages from a directory."""
        response = await client.get(
            f"{self.base_url}/repos/{self.org}/{repo}/contents/{path}",
            headers=self._headers,
        )

        if response.status_code != 200:
            return

        items = response.json()
        for item in items:
            if item["type"] == "dir" and not item["name"].startswith("."):
                # Recurse into subdirectories
                await self._fetch_wiki_pages_recursive(
                    client, repo, item["path"], pages
                )
            elif item["type"] == "file" and item["name"].endswith(".md"):
                # Extract title from path
                name = item["name"].replace(".md", "").replace("_", " ")
                if name == "index":
                    # Use parent folder name for index files
                    parts = item["path"].split("/")
                    if len(parts) > 2:
                        name = parts[-2].replace("_", " ")
                    else:
                        name = "Home"

                # Build wiki URL (MkDocs style)
                wiki_path = item["path"].replace("docs/", "").replace(".md", "/")
                if wiki_path.endswith("index/"):
                    wiki_path = wiki_path.replace("index/", "")

                pages.append(
                    WikiPage(
                        path=item["path"],
                        title=name.title(),
                        url=f"https://aau-giraf.github.io/wiki/{wiki_path}",
                        github_url=item["html_url"],
                    )
                )

    async def search_wiki(
        self, query: str, repo: str = "wiki", limit: int = 10
    ) -> list[WikiSearchResult]:
        """Search wiki pages by keyword.

        Fetches wiki pages live and performs keyword search.
        Uses parallel fetching for performance.

        Args:
            query: Search query (keywords)
            repo: Repository containing the wiki
            limit: Maximum results to return

        Returns:
            List of WikiSearchResult sorted by relevance
        """
        import asyncio

        pages = await self.list_wiki_pages(repo)
        query_terms = query.lower().split()

        # Semaphore to limit concurrent requests (avoid rate limiting)
        semaphore = asyncio.Semaphore(10)

        async def search_page(
            client: httpx.AsyncClient, page: WikiPage
        ) -> WikiSearchResult | None:
            """Search a single page for matches."""
            async with semaphore:
                try:
                    response = await client.get(
                        f"{self.base_url}/repos/{self.org}/{repo}/contents/{page.path}",
                        headers=self._headers,
                    )
                    if response.status_code != 200:
                        return None

                    data = response.json()
                    content = ""
                    if data.get("content"):
                        content = base64.b64decode(data["content"]).decode("utf-8")

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

                    if term_hits > 0:
                        relevance = min(1.0, term_hits / (len(query_terms) * 5))
                        return WikiSearchResult(
                            page=page,
                            matches=matches[:5],
                            relevance=relevance,
                        )
                except Exception:
                    pass
                return None

        # Fetch and search all pages in parallel
        async with httpx.AsyncClient() as client:
            tasks = [search_page(client, page) for page in pages]
            results_raw = await asyncio.gather(*tasks)

        # Filter out None results and sort
        results = [r for r in results_raw if r is not None]
        results.sort(key=lambda r: r.relevance, reverse=True)
        return results[:limit]
