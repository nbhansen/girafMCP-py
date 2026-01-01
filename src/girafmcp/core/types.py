"""Domain types for the GIRAF MCP server."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal


class DocumentSource(str, Enum):
    """Source types for indexed documents."""

    WIKI = "wiki"
    CODE = "code"
    DOMAIN = "domain"
    HANDOVER = "handover"
    PDF = "pdf"


@dataclass
class DocumentMetadata:
    """Metadata for indexed documents - includes source information for citations."""

    source: Literal["wiki", "code", "domain", "handover", "pdf"]
    url: str  # URL to the original source (for citations)

    # For wiki/docs
    title: str | None = None
    section: str | None = None

    # For code
    repo: str | None = None
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    language: str | None = None

    # For domain knowledge
    topic: str | None = None
    tags: list[str] = field(default_factory=list)

    # For PDFs
    page: int | None = None  # Page number (1-indexed) for citations

    # Common
    last_updated: str | None = None


@dataclass
class Document:
    """A document to be stored in the vector database."""

    id: str
    content: str
    metadata: DocumentMetadata


@dataclass
class SearchResult:
    """Result from a vector search."""

    id: str
    content: str
    metadata: DocumentMetadata
    score: float  # Similarity score (0-1, higher is better)


@dataclass
class Repository:
    """A GitHub repository."""

    name: str
    description: str
    url: str
    language: str | None
    default_branch: str


@dataclass
class FileContent:
    """Content of a file from a repository."""

    content: str
    path: str
    repo: str
    url: str  # GitHub permalink
    sha: str


@dataclass
class CodeSearchResult:
    """Result from a code search."""

    repo: str
    path: str
    url: str  # Permalink to the file
    matches: list[str]  # Matching lines/snippets


@dataclass
class WikiPage:
    """A wiki documentation page."""

    path: str  # Path within docs/ folder
    title: str  # Extracted from content or filename
    url: str  # URL to the live wiki page
    github_url: str  # URL to source on GitHub


@dataclass
class WikiSearchResult:
    """Result from a wiki search."""

    page: WikiPage
    matches: list[str]  # Matching lines/snippets
    relevance: float  # 0-1 score based on keyword matches


# =============================================================================
# Research Feature Types
# =============================================================================


class QueryType(str, Enum):
    """Classification of query intent."""

    EXPLANATION = "explanation"  # "explain", "what does", "how does"
    GENERATION = "generation"  # "write", "create", "implement"
    NAVIGATION = "navigation"  # "find", "where is", "list"
    DEBUGGING = "debugging"  # "error", "fix", "wrong", "doesn't work"
    VERIFICATION = "verification"  # "is this correct", "check", "verify"
    UNKNOWN = "unknown"


@dataclass
class MetaSkillIndicators:
    """Indicators of meta-skill engagement beyond surface productivity.

    These are detected via simple pattern matching on query text.
    More complex session-level analysis can be added later.
    """

    # Verification behavior
    verification_attempted: bool = False  # "I tried", "I tested", "I ran"
    test_run_before_query: bool = False  # References test results/error output
    error_description_quality: Literal["none", "vague", "specific", "diagnostic"] = "none"

    # System understanding
    references_existing_code: bool = False  # Mentions file paths, function names
    asks_about_integration: bool = False  # How pieces fit together
    architectural_awareness: bool = False  # Shows understanding of structure

    # Debugging engagement
    hypothesis_present: bool = False  # "I think", "maybe because", "could it be"
    isolation_attempted: bool = False  # Has tried to isolate the issue

    # Independence indicators
    follow_up_depth: int = 0  # How many follow-ups on same topic
    accepted_without_verification: bool = False  # DRIFTING indicator

    # Cross-disciplinary indicators
    discipline_translation_needed: bool = False  # Uses discipline-specific jargon
    requests_alternative_framing: bool = False  # "Explain for a designer"


@dataclass
class QueryLog:
    """Immutable record of a single tool invocation for research analysis."""

    id: str  # UUID
    timestamp: datetime  # UTC
    session_id: str  # Groups queries within a session

    # Research metadata (from session state)
    team_id: str | None = None
    role: Literal["po", "sm", "dev", "unknown"] | None = None
    discipline: Literal["cs", "id", "business", "health", "unknown"] | None = None

    # Query data
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    query_text: str | None = None  # Extracted natural language query

    # Response data
    response_length: int = 0  # Character count of response
    result_count: int | None = None  # Number of results (if applicable)
    duration_ms: int = 0  # Processing time
    error: str | None = None  # Error message if failed

    # Classification (computed)
    query_type: QueryType = QueryType.UNKNOWN

    # Meta-skill indicators
    meta_skills: MetaSkillIndicators | None = None

    # Guardrail state at time of query
    guardrail_mode: str | None = None  # off, prompt, tiered, cooldown
    guardrail_tier: int | None = None
