# girafMCP-py Research Features Specification

## Overview

This document specifies extensions to girafMCP-py to support the DFF research projects on AI-mediated knowledge continuity and skill development.

### Strategic Context

As AI systems increasingly automate code generation, the skills that remain exclusively human become more critical: **verification** (is this code correct?), **system understanding** (how does this fit together?), **debugging** (what went wrong?), and **specification** (what should we build?). Our research infrastructure must:

1. **Track meta-skill development** — Not just what students ask, but whether they verify, debug, and reason
2. **Test resilience** — Can students function when AI is unavailable or produces incorrect output?
3. **Preserve institutional knowledge** — Capture the human knowledge layer that gives code meaning
4. **Support cross-disciplinary transfer** — Knowledge must work across CS, Interaction Design, Business, and Health backgrounds

### Feature Areas

Five feature areas are defined:

1. **Query Logging** — Persistent storage of all tool invocations with meta-skill indicators
2. **Guardrails System** — Scaffolded responses to build skills, not dependency
3. **Resilience Testing** — Failure injection and AI-unavailable scenarios *(NEW)*
4. **Knowledge Capture** — Tools for capturing architectural decisions and retrospective learnings
5. **Cross-Disciplinary Framing** — Multi-perspective knowledge representation *(NEW)*

All features follow the existing hexagonal architecture patterns.

---

## 1. Query Logging Extension

### 1.1 Purpose

Enable research analysis of student-AI interaction patterns, specifically:
- Drifting detection (ratio of "explain" vs "write for me" queries)
- Usage patterns by role (PO/SM/Dev) and discipline (CS/ID)
- Session-level interaction sequences (Lag Sequential Analysis)

### 1.2 Data Model

**New file:** `core/types.py` (extend existing)

```python
@dataclass
class QueryLog:
    """Immutable record of a single tool invocation"""
    id: str                          # UUID
    timestamp: datetime              # UTC
    session_id: str                  # Groups queries within a session

    # Research metadata (from client headers or config)
    team_id: str | None              # Anonymized team identifier
    role: Literal["po", "sm", "dev", "unknown"] | None
    discipline: Literal["cs", "id", "business", "health", "unknown"] | None

    # Query data
    tool_name: str                   # e.g., "search_code", "get_file"
    arguments: dict[str, Any]        # Tool arguments (sanitized)
    query_text: str | None           # Extracted natural language query if present

    # Response data
    response_length: int             # Character count of response
    result_count: int | None         # Number of results returned (if applicable)
    duration_ms: int                 # Processing time
    error: str | None                # Error message if failed

    # Classification (computed)
    query_type: Literal[
        "explanation",    # "explain", "what does", "how does"
        "generation",     # "write", "create", "implement"
        "navigation",     # "find", "where is", "list"
        "debugging",      # "why doesn't", "fix", "error"
        "verification",   # "is this correct", "does this work", "check" (NEW)
        "unknown"
    ] | None

    # Meta-skill indicators (NEW - critical for resilience research)
    meta_skills: MetaSkillIndicators | None


@dataclass
class MetaSkillIndicators:
    """Indicators of meta-skill engagement beyond surface productivity"""

    # Verification behavior
    verification_attempted: bool     # Did student try to verify before asking?
    test_run_before_query: bool      # Evidence of running tests first
    error_description_quality: Literal["none", "vague", "specific", "diagnostic"] | None

    # System understanding
    references_existing_code: bool   # Does query reference existing codebase?
    asks_about_integration: bool     # Concerned with how pieces fit together?
    architectural_awareness: bool    # Shows understanding of system structure?

    # Debugging engagement
    hypothesis_present: bool         # Does student have a theory about the problem?
    isolation_attempted: bool        # Has student tried to isolate the issue?

    # Independence indicators
    follow_up_depth: int             # How many follow-ups on same topic (0 = resolved quickly)
    accepted_without_verification: bool  # DRIFTING: Took answer without checking

    # Cross-disciplinary indicators
    discipline_translation_needed: bool  # Query uses discipline-specific jargon
    requests_alternative_framing: bool   # "Explain this for a designer"
```

**Query type classification heuristics:**

| Type | Trigger patterns in query_text or arguments |
|------|---------------------------------------------|
| `explanation` | "explain", "what does", "how does", "why", "understand" |
| `generation` | "write", "create", "implement", "generate", "make" |
| `navigation` | "find", "where", "list", "show me", "locate" |
| `debugging` | "error", "fix", "wrong", "doesn't work", "bug" |
| `verification` | "is this correct", "does this work", "check", "verify", "validate", "review my" |
| `unknown` | No pattern matched |

**Meta-skill detection heuristics:**

| Indicator | Detection Method |
|-----------|------------------|
| `verification_attempted` | Query contains "I tried", "I tested", "I ran", "output was" |
| `test_run_before_query` | Query references test results or error output |
| `error_description_quality` | NLP classification: none (no error), vague ("it doesn't work"), specific ("returns null on line 42"), diagnostic ("null because X is undefined when Y") |
| `references_existing_code` | Query mentions file paths, function names, or class names from codebase |
| `hypothesis_present` | Query contains "I think", "maybe because", "could it be" |
| `accepted_without_verification` | Session analysis: no follow-up verification query after receiving code |

### 1.3 Storage Adapter

**New file:** `adapters/query_log_adapter.py`

```python
class QueryLogAdapter:
    """Persists query logs to local SQLite database"""

    def __init__(self, db_path: Path):
        """
        Initialize with path to SQLite database.
        Creates tables if they don't exist.
        """
        pass

    async def log_query(self, log: QueryLog) -> None:
        """Insert a query log record"""
        pass

    async def get_session_queries(self, session_id: str) -> list[QueryLog]:
        """Retrieve all queries for a session"""
        pass

    async def get_queries_by_team(
        self,
        team_id: str,
        start: datetime | None = None,
        end: datetime | None = None
    ) -> list[QueryLog]:
        """Retrieve queries for a team within optional time range"""
        pass

    async def get_query_type_counts(
        self,
        team_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None
    ) -> dict[str, int]:
        """Aggregate query counts by type for analysis"""
        pass

    async def export_csv(self, output_path: Path, **filters) -> int:
        """Export logs to CSV for external analysis. Returns row count."""
        pass
```

**SQLite Schema:**

```sql
CREATE TABLE query_logs (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,           -- ISO 8601
    session_id TEXT NOT NULL,
    team_id TEXT,
    role TEXT,
    discipline TEXT,
    tool_name TEXT NOT NULL,
    arguments TEXT NOT NULL,           -- JSON
    query_text TEXT,
    response_length INTEGER NOT NULL,
    result_count INTEGER,
    duration_ms INTEGER NOT NULL,
    error TEXT,
    query_type TEXT,

    -- Indexes for common queries
    INDEX idx_session (session_id),
    INDEX idx_team_time (team_id, timestamp),
    INDEX idx_query_type (query_type, timestamp)
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    team_id TEXT,
    role TEXT,
    discipline TEXT,
    metadata TEXT                      -- JSON for extensibility
);
```

**Why SQLite over ChromaDB:**
- Query logs are relational, not semantic
- Need aggregation queries (COUNT, GROUP BY)
- Need time-range filtering
- No embedding/similarity search needed
- Easy CSV export for R/Python analysis

### 1.4 Logging Middleware

**Modified file:** `server.py`

```python
# New imports
from girafmcp.adapters.query_log_adapter import QueryLogAdapter
from girafmcp.core.types import QueryLog
from girafmcp.core.services.query_classifier import classify_query_type

# New global
_query_log_adapter: QueryLogAdapter | None = None

def get_query_log_adapter() -> QueryLogAdapter:
    global _query_log_adapter
    if _query_log_adapter is None:
        db_path = Path(os.getenv("GIRAF_QUERY_LOG_DB", "data/query_logs.db"))
        _query_log_adapter = QueryLogAdapter(db_path)
    return _query_log_adapter

# Session state (per-connection in HTTP mode, global in stdio)
_current_session: dict[str, Any] = {}

def get_or_create_session() -> str:
    """Get current session ID or create new one"""
    if "session_id" not in _current_session:
        _current_session["session_id"] = str(uuid.uuid4())
        _current_session["started_at"] = datetime.utcnow()
    return _current_session["session_id"]

# Wrap call_tool with logging
@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls with logging"""

    start_time = time.monotonic()
    session_id = get_or_create_session()
    error_msg = None
    result_count = None

    try:
        # Existing dispatch logic
        result = await _dispatch_tool(name, arguments)

        # Extract result count if applicable
        result_count = _extract_result_count(result)

        return result

    except Exception as e:
        error_msg = str(e)
        raise

    finally:
        # Log query (async, don't block response)
        duration_ms = int((time.monotonic() - start_time) * 1000)

        log = QueryLog(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            session_id=session_id,
            team_id=_current_session.get("team_id"),
            role=_current_session.get("role"),
            discipline=_current_session.get("discipline"),
            tool_name=name,
            arguments=_sanitize_arguments(arguments),
            query_text=_extract_query_text(name, arguments),
            response_length=sum(len(c.text) for c in result) if result else 0,
            result_count=result_count,
            duration_ms=duration_ms,
            error=error_msg,
            query_type=classify_query_type(name, arguments)
        )

        # Fire-and-forget logging (don't slow down responses)
        asyncio.create_task(get_query_log_adapter().log_query(log))


async def _dispatch_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Original tool dispatch logic extracted to separate function"""
    # ... existing if/elif chain ...
    pass


def _sanitize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Remove potentially sensitive data from arguments before logging"""
    sanitized = arguments.copy()
    # Truncate long content
    for key in ["content", "code", "body"]:
        if key in sanitized and len(str(sanitized[key])) > 500:
            sanitized[key] = str(sanitized[key])[:500] + "...[truncated]"
    return sanitized


def _extract_query_text(name: str, arguments: dict[str, Any]) -> str | None:
    """Extract the natural language query from tool arguments"""
    # Search tools have explicit query
    if "query" in arguments:
        return arguments["query"]
    # File retrieval - use path as proxy
    if name == "get_file":
        return f"get file {arguments.get('path', '')}"
    return None


def _extract_result_count(result: list[TextContent]) -> int | None:
    """Heuristically extract result count from response"""
    if not result:
        return 0
    text = result[0].text
    # Count markdown headers as results
    return text.count("\n## ") or text.count("\n### ") or None
```

### 1.5 Session Metadata Tool

**New tool** for setting research metadata at session start:

```python
# In list_tools()
Tool(
    name="set_session_metadata",
    description="Set research metadata for this session (team, role, discipline). "
                "Called once at session start for logging purposes.",
    inputSchema={
        "type": "object",
        "properties": {
            "team_id": {
                "type": "string",
                "description": "Anonymized team identifier (e.g., 'team_a', 'team_b')"
            },
            "role": {
                "type": "string",
                "enum": ["po", "sm", "dev"],
                "description": "Student's role in the project"
            },
            "discipline": {
                "type": "string",
                "enum": ["cs", "id"],
                "description": "Student's discipline (CS or Interaction Design)"
            }
        },
        "required": []
    }
)

# Handler
async def handle_set_session_metadata(
    team_id: str | None = None,
    role: str | None = None,
    discipline: str | None = None
) -> list[TextContent]:
    """Store session metadata for logging"""
    global _current_session

    if team_id:
        _current_session["team_id"] = team_id
    if role:
        _current_session["role"] = role
    if discipline:
        _current_session["discipline"] = discipline

    return [TextContent(
        type="text",
        text=f"Session metadata updated: team={team_id}, role={role}, discipline={discipline}"
    )]
```

### 1.6 Analysis Export Tool

**New tool** for researchers to export data:

```python
Tool(
    name="export_query_logs",
    description="Export query logs to CSV for research analysis. Requires supervisor role.",
    inputSchema={
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "Start date (ISO 8601, e.g., '2025-02-01')"
            },
            "end_date": {
                "type": "string",
                "description": "End date (ISO 8601)"
            },
            "team_id": {
                "type": "string",
                "description": "Filter by team (optional)"
            }
        },
        "required": []
    }
)
```

### 1.7 Configuration

**New environment variables:**

```bash
# Enable/disable query logging (default: enabled)
GIRAF_QUERY_LOGGING_ENABLED=true

# Path to SQLite database
GIRAF_QUERY_LOG_DB=data/query_logs.db

# Consent requirement (if true, requires set_session_metadata call before logging)
GIRAF_REQUIRE_LOGGING_CONSENT=true
```

---

## 2. Guardrails System

### 2.1 Purpose

Implement scaffolded responses during the onboarding period (weeks 1-3) to:
- Prompt reflection before providing direct solutions
- Provide tiered hints instead of immediate answers
- Reduce passive "drifting" behavior

### 2.2 Guardrail Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `off` | Standard behavior, no guardrails | Control group, post-onboarding |
| `prompt` | Ask "What have you tried?" before answering | Light intervention |
| `tiered` | Provide hints in escalating detail | Main intervention |
| `cooldown` | Add reflection delay before full solutions | Strongest intervention |

### 2.3 Configuration Model

**New file:** `data/guardrails.yaml`

```yaml
# Global guardrails configuration
enabled: true
mode: "tiered"  # off | prompt | tiered | cooldown

# Team-specific overrides (for A/B testing)
team_overrides:
  team_a:
    enabled: true
    mode: "tiered"
  team_b:
    enabled: false
    mode: "off"
  team_c:
    enabled: true
    mode: "cooldown"

# Tools that trigger guardrails
guarded_tools:
  - search_code
  - get_file
  - search_documentation

# Tools exempt from guardrails (always direct answers)
exempt_tools:
  - list_repositories
  - list_wiki_pages
  - get_project_context
  - set_session_metadata

# Tiered response configuration
tiers:
  1:
    name: "hint"
    description: "Conceptual hint without code"
    prompt_suffix: |
      Provide a brief conceptual hint about where to look or what approach to consider.
      Do NOT provide any code or specific file paths yet.
      End with: "Would you like more specific guidance?"
  2:
    name: "guidance"
    description: "Specific guidance with locations"
    prompt_suffix: |
      Provide specific guidance including relevant file paths and function names.
      Do NOT provide implementation code yet.
      End with: "Would you like to see example code?"
  3:
    name: "example"
    description: "Partial code example"
    prompt_suffix: |
      Provide a partial code example that demonstrates the pattern.
      Do NOT provide a complete copy-paste solution.
      End with: "Do you need the complete implementation?"
  4:
    name: "solution"
    description: "Full solution"
    prompt_suffix: null  # No modification, full response

# Cooldown configuration (for cooldown mode)
cooldown:
  delay_seconds: 30
  reflection_prompt: |
    Before I provide a complete solution, take a moment to consider:
    - What have you already tried?
    - What specific part is confusing?
    - Have you checked the existing codebase for similar patterns?

    I'll provide the full answer in {remaining_seconds} seconds, or you can ask
    for a hint now.

# Attempt-first prompts (for prompt mode)
attempt_first:
  prompt: |
    Before I help with this, could you share:
    - What approaches have you considered?
    - What have you tried so far?
    - What specifically is blocking you?

    This helps me give you more targeted assistance.

  # Keywords that indicate student has already tried something
  bypass_indicators:
    - "i tried"
    - "i've tried"
    - "i attempted"
    - "doesn't work"
    - "getting error"
    - "tried but"
```

### 2.4 Guardrails Service

**New file:** `core/services/guardrails_service.py`

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import yaml
from typing import Any

class GuardrailMode(Enum):
    OFF = "off"
    PROMPT = "prompt"
    TIERED = "tiered"
    COOLDOWN = "cooldown"

@dataclass
class GuardrailState:
    """Tracks guardrail state for a session"""
    session_id: str
    current_tier: int = 1           # For tiered mode
    cooldown_until: datetime | None = None  # For cooldown mode
    prompted_this_query: bool = False  # For prompt mode
    last_tool: str | None = None
    last_arguments: dict | None = None

class GuardrailsService:
    """Manages guardrail behavior for research intervention"""

    def __init__(self, config_path: Path = Path("data/guardrails.yaml")):
        self.config = self._load_config(config_path)
        self._session_states: dict[str, GuardrailState] = {}

    def _load_config(self, path: Path) -> dict:
        """Load guardrails configuration"""
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f)
        return {"enabled": False, "mode": "off"}

    def get_mode(self, team_id: str | None = None) -> GuardrailMode:
        """Get effective guardrail mode for a team"""
        if not self.config.get("enabled", False):
            return GuardrailMode.OFF

        # Check team override
        if team_id and team_id in self.config.get("team_overrides", {}):
            override = self.config["team_overrides"][team_id]
            if not override.get("enabled", True):
                return GuardrailMode.OFF
            return GuardrailMode(override.get("mode", "off"))

        return GuardrailMode(self.config.get("mode", "off"))

    def should_guard(self, tool_name: str) -> bool:
        """Check if a tool should trigger guardrails"""
        exempt = self.config.get("exempt_tools", [])
        guarded = self.config.get("guarded_tools", [])

        if tool_name in exempt:
            return False
        if guarded:
            return tool_name in guarded
        return True  # Default: guard all non-exempt tools

    def get_state(self, session_id: str) -> GuardrailState:
        """Get or create guardrail state for session"""
        if session_id not in self._session_states:
            self._session_states[session_id] = GuardrailState(session_id=session_id)
        return self._session_states[session_id]

    def check_bypass_indicators(self, query_text: str | None) -> bool:
        """Check if query indicates student has already tried something"""
        if not query_text:
            return False
        query_lower = query_text.lower()
        indicators = self.config.get("attempt_first", {}).get("bypass_indicators", [])
        return any(ind in query_lower for ind in indicators)

    def get_prompt_mode_response(self, state: GuardrailState) -> str | None:
        """
        Get attempt-first prompt if needed.
        Returns None if prompt not needed (already prompted or bypass detected).
        """
        if state.prompted_this_query:
            return None
        return self.config.get("attempt_first", {}).get("prompt")

    def get_tier_prompt_suffix(self, tier: int) -> str | None:
        """Get the prompt suffix for a given tier"""
        tiers = self.config.get("tiers", {})
        if tier in tiers:
            return tiers[tier].get("prompt_suffix")
        return None

    def get_cooldown_response(self, state: GuardrailState) -> tuple[str | None, int]:
        """
        Get cooldown response if in cooldown period.
        Returns (reflection_prompt, remaining_seconds) or (None, 0) if not in cooldown.
        """
        if not state.cooldown_until:
            return None, 0

        remaining = (state.cooldown_until - datetime.utcnow()).total_seconds()
        if remaining <= 0:
            state.cooldown_until = None
            return None, 0

        prompt = self.config.get("cooldown", {}).get("reflection_prompt", "")
        return prompt.format(remaining_seconds=int(remaining)), int(remaining)

    def start_cooldown(self, state: GuardrailState) -> None:
        """Start a cooldown period for the session"""
        delay = self.config.get("cooldown", {}).get("delay_seconds", 30)
        state.cooldown_until = datetime.utcnow() + timedelta(seconds=delay)

    def advance_tier(self, state: GuardrailState) -> int:
        """Advance to next tier, return new tier number"""
        max_tier = max(self.config.get("tiers", {}).keys(), default=4)
        state.current_tier = min(state.current_tier + 1, max_tier)
        return state.current_tier

    def reset_tier(self, state: GuardrailState) -> None:
        """Reset tier to 1 (for new query topic)"""
        state.current_tier = 1
```

### 2.5 Integration with Tool Dispatch

**Modified `server.py`:**

```python
from girafmcp.core.services.guardrails_service import GuardrailsService, GuardrailMode

_guardrails_service: GuardrailsService | None = None

def get_guardrails_service() -> GuardrailsService:
    global _guardrails_service
    if _guardrails_service is None:
        _guardrails_service = GuardrailsService()
    return _guardrails_service


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls with guardrails"""

    guardrails = get_guardrails_service()
    session_id = get_or_create_session()
    team_id = _current_session.get("team_id")

    mode = guardrails.get_mode(team_id)
    state = guardrails.get_state(session_id)

    # Check if this tool should be guarded
    if mode == GuardrailMode.OFF or not guardrails.should_guard(name):
        return await _dispatch_tool(name, arguments)

    query_text = _extract_query_text(name, arguments)

    # Mode-specific handling
    if mode == GuardrailMode.PROMPT:
        # Check for bypass indicators
        if not guardrails.check_bypass_indicators(query_text):
            prompt = guardrails.get_prompt_mode_response(state)
            if prompt:
                state.prompted_this_query = True
                state.last_tool = name
                state.last_arguments = arguments
                return [TextContent(type="text", text=prompt)]

        # Reset for next query
        state.prompted_this_query = False
        return await _dispatch_tool(name, arguments)

    elif mode == GuardrailMode.TIERED:
        # Get tier-appropriate response
        tier = state.current_tier
        suffix = guardrails.get_tier_prompt_suffix(tier)

        if suffix and tier < 4:
            # Get base result
            result = await _dispatch_tool(name, arguments)

            # Append tier instruction to result
            # (Claude will interpret this on next turn)
            result_text = result[0].text if result else ""
            modified_text = f"{result_text}\n\n---\n*[Tier {tier} response]*\n{suffix}"

            return [TextContent(type="text", text=modified_text)]
        else:
            # Tier 4: full response
            return await _dispatch_tool(name, arguments)

    elif mode == GuardrailMode.COOLDOWN:
        # Check if in cooldown
        reflection, remaining = guardrails.get_cooldown_response(state)
        if reflection:
            return [TextContent(type="text", text=reflection)]

        # Start cooldown for next request
        guardrails.start_cooldown(state)
        return await _dispatch_tool(name, arguments)

    # Fallback: no guardrails
    return await _dispatch_tool(name, arguments)
```

### 2.6 Tier Advancement Tool

**New tool** for students to request more detail:

```python
Tool(
    name="request_more_detail",
    description="Request more detailed guidance on the previous query. "
                "Advances through hint → guidance → example → solution.",
    inputSchema={
        "type": "object",
        "properties": {},
        "required": []
    }
)

async def handle_request_more_detail() -> list[TextContent]:
    """Advance tier and re-run previous query"""
    guardrails = get_guardrails_service()
    session_id = get_or_create_session()
    state = guardrails.get_state(session_id)

    if not state.last_tool or not state.last_arguments:
        return [TextContent(
            type="text",
            text="No previous query to elaborate on. Please ask a question first."
        )]

    # Advance tier
    new_tier = guardrails.advance_tier(state)

    # Re-run previous query with new tier
    return await call_tool(state.last_tool, state.last_arguments)
```

### 2.7 Admin Configuration Tool

**New tool** for supervisors to adjust guardrails:

```python
Tool(
    name="configure_guardrails",
    description="Configure guardrail settings for a team. Supervisor only.",
    inputSchema={
        "type": "object",
        "properties": {
            "team_id": {
                "type": "string",
                "description": "Team to configure"
            },
            "enabled": {
                "type": "boolean",
                "description": "Enable or disable guardrails for team"
            },
            "mode": {
                "type": "string",
                "enum": ["off", "prompt", "tiered", "cooldown"],
                "description": "Guardrail mode"
            }
        },
        "required": ["team_id"]
    }
)
```

---

## 3. Resilience Testing System (NEW)

### 3.1 Purpose

Test whether students can function when AI assistance is unavailable or produces incorrect output. This directly addresses RQ4 (Resilience): *Can students who learned with scaffolded AI effectively debug, verify, and reason about code when AI assistance is unavailable or produces incorrect output?*

As AI takes over more coding tasks, the ability to recognize and fix AI errors becomes critical. Students who never learn to verify AI output will deploy broken systems.

### 3.2 Resilience Test Modes

| Mode | Behavior | Research Use |
|------|----------|--------------|
| `normal` | Standard AI assistance | Control condition |
| `degraded` | AI provides intentionally flawed responses | Error detection assessment |
| `unavailable` | AI returns "service unavailable" | Independence assessment |
| `delayed` | AI responds after 60+ second delay | Patience/self-reliance assessment |

### 3.3 Failure Injection Configuration

**New file:** `data/resilience_tests.yaml`

```yaml
# Resilience testing configuration
enabled: false  # Enable only during assessment periods
mode: "normal"

# Team-specific test assignments
team_assignments:
  team_a:
    mode: "normal"
    assessment_window: null
  team_b:
    mode: "degraded"
    assessment_window:
      start: "2025-03-15T09:00:00Z"
      end: "2025-03-15T12:00:00Z"

# Degraded mode: intentional errors to inject
degraded_mode:
  error_injection_rate: 0.3  # 30% of responses contain errors
  error_types:
    - type: "off_by_one"
      description: "Loop bounds off by one"
      weight: 0.25
    - type: "null_check_missing"
      description: "Missing null/undefined check"
      weight: 0.25
    - type: "wrong_variable"
      description: "Uses wrong variable name"
      weight: 0.20
    - type: "logic_inversion"
      description: "Boolean logic inverted"
      weight: 0.15
    - type: "api_misuse"
      description: "Incorrect API usage pattern"
      weight: 0.15

  # Subtle vs obvious errors
  subtlety_distribution:
    obvious: 0.2    # Easy to spot
    moderate: 0.5   # Requires careful reading
    subtle: 0.3     # Requires testing to detect

# Unavailable mode configuration
unavailable_mode:
  message: |
    The AI assistant is temporarily unavailable.
    Please continue working using documentation,
    existing code examples, and team discussion.

  # Tools that remain available even in unavailable mode
  allowed_tools:
    - search_documentation
    - search_knowledge  # Past decisions still accessible
    - get_project_context

# Assessment tracking
assessment_tracking:
  log_all_attempts: true
  track_workarounds: true  # Did student find alternative solution?
  track_error_detection: true  # Did student notice injected errors?
```

### 3.4 Resilience Service

**New file:** `core/services/resilience_service.py`

```python
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import random

class ResilienceMode(Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DELAYED = "delayed"

@dataclass
class InjectedError:
    """Record of an intentionally injected error"""
    id: str
    error_type: str
    description: str
    subtlety: str
    original_response: str
    modified_response: str
    injected_at: datetime

@dataclass
class ErrorDetectionEvent:
    """Record of student detecting (or missing) an injected error"""
    injected_error_id: str
    session_id: str
    detected: bool
    detection_method: str | None  # "testing", "review", "peer", "none"
    time_to_detection_ms: int | None
    student_correction: str | None


class ResilienceService:
    """Manages resilience testing for research assessment"""

    def __init__(self, config_path: Path):
        self.config = self._load_config(config_path)
        self._injected_errors: dict[str, InjectedError] = {}

    def get_mode(self, team_id: str | None = None) -> ResilienceMode:
        """Get current resilience mode for a team"""
        if not self.config.get("enabled", False):
            return ResilienceMode.NORMAL

        if team_id and team_id in self.config.get("team_assignments", {}):
            assignment = self.config["team_assignments"][team_id]
            # Check if within assessment window
            if self._in_assessment_window(assignment):
                return ResilienceMode(assignment.get("mode", "normal"))

        return ResilienceMode(self.config.get("mode", "normal"))

    def should_inject_error(self) -> bool:
        """Probabilistically determine if error should be injected"""
        rate = self.config.get("degraded_mode", {}).get("error_injection_rate", 0)
        return random.random() < rate

    def inject_error(self, response: str, tool_name: str) -> tuple[str, InjectedError | None]:
        """
        Inject an error into an AI response.
        Returns (modified_response, error_record) or (original, None).
        """
        if not self.should_inject_error():
            return response, None

        error_type = self._select_error_type()
        subtlety = self._select_subtlety()

        modified, description = self._apply_error(response, error_type, subtlety)

        error = InjectedError(
            id=str(uuid.uuid4()),
            error_type=error_type,
            description=description,
            subtlety=subtlety,
            original_response=response,
            modified_response=modified,
            injected_at=datetime.utcnow()
        )

        self._injected_errors[error.id] = error
        return modified, error

    def _apply_error(
        self,
        response: str,
        error_type: str,
        subtlety: str
    ) -> tuple[str, str]:
        """Apply specific error type to response. Returns (modified, description)."""
        # Implementation varies by error type
        if error_type == "off_by_one":
            # Find loop patterns and adjust bounds
            pass
        elif error_type == "null_check_missing":
            # Remove null checks from code
            pass
        # ... etc
        return response, f"Injected {error_type} error"

    def record_detection(
        self,
        error_id: str,
        session_id: str,
        detected: bool,
        method: str | None = None
    ) -> None:
        """Record whether student detected an injected error"""
        event = ErrorDetectionEvent(
            injected_error_id=error_id,
            session_id=session_id,
            detected=detected,
            detection_method=method,
            time_to_detection_ms=self._calculate_detection_time(error_id),
            student_correction=None
        )
        # Store for analysis
        pass

    def get_unavailable_message(self) -> str:
        """Get message to show when AI is unavailable"""
        return self.config.get("unavailable_mode", {}).get("message",
            "AI assistant is temporarily unavailable.")

    def is_tool_allowed_when_unavailable(self, tool_name: str) -> bool:
        """Check if tool can be used during unavailable mode"""
        allowed = self.config.get("unavailable_mode", {}).get("allowed_tools", [])
        return tool_name in allowed
```

### 3.5 Integration with Tool Dispatch

```python
# In server.py call_tool()

resilience = get_resilience_service()
mode = resilience.get_mode(team_id)

if mode == ResilienceMode.UNAVAILABLE:
    if not resilience.is_tool_allowed_when_unavailable(name):
        return [TextContent(
            type="text",
            text=resilience.get_unavailable_message()
        )]

elif mode == ResilienceMode.DEGRADED:
    result = await _dispatch_tool(name, arguments)
    # Possibly inject error
    modified, error = resilience.inject_error(result[0].text, name)
    if error:
        # Log for later analysis
        await log_injected_error(error, session_id)
    return [TextContent(type="text", text=modified)]

elif mode == ResilienceMode.DELAYED:
    await asyncio.sleep(60)  # Force wait
    return await _dispatch_tool(name, arguments)
```

### 3.6 Assessment Tools

#### Tool: `report_error_found`

```python
Tool(
    name="report_error_found",
    description="Report that you found an error in AI-provided code. "
                "Used during resilience assessments.",
    inputSchema={
        "type": "object",
        "properties": {
            "error_description": {
                "type": "string",
                "description": "Description of the error you found"
            },
            "how_detected": {
                "type": "string",
                "enum": ["testing", "code_review", "runtime_error", "peer_review", "other"],
                "description": "How you detected the error"
            },
            "proposed_fix": {
                "type": "string",
                "description": "Your proposed fix for the error"
            }
        },
        "required": ["error_description", "how_detected"]
    }
)
```

This tool allows students to report errors they find, enabling measurement of error detection rates.

### 3.7 Resilience Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Error Detection Rate** | % of injected errors detected by students | ≥70% for scaffolded condition |
| **Detection Time** | Time from receiving error to reporting it | Lower = better |
| **Independence Score** | Task completion rate during unavailable mode | ≥50% comparable to control |
| **Workaround Quality** | Quality of solutions found without AI | Assessed by rubric |
| **False Positive Rate** | Correct code reported as errors | ≤10% |

---

## 4. Knowledge Capture Tools

### 4.1 Purpose

Capture institutional knowledge during the semester for:
- Architectural decision records (ADRs)
- Sprint retrospective learnings
- Tribal knowledge that would otherwise be lost at handover

### 3.2 Data Models

**Extend `core/types.py`:**

```python
@dataclass
class ArchitecturalDecision:
    """Record of an architectural or technical decision"""
    id: str
    timestamp: datetime
    team_id: str | None

    # Decision content
    title: str                       # Brief description
    context: str                     # Why this decision was needed
    decision: str                    # What was decided
    rationale: str                   # Why this option was chosen
    alternatives: list[str]          # Other options considered
    consequences: list[str]          # Expected impacts

    # Metadata
    status: Literal["proposed", "accepted", "deprecated", "superseded"]
    related_issues: list[str]        # GitHub issue numbers
    related_files: list[str]         # File paths affected
    tags: list[str]                  # Categorization


@dataclass
class RetrospectiveLearning:
    """Insight captured from a sprint retrospective"""
    id: str
    timestamp: datetime
    team_id: str | None
    sprint: str                      # e.g., "2025s1-sprint3"

    # Learning content
    category: Literal["went_well", "to_improve", "action_item", "insight"]
    description: str

    # Context
    related_decisions: list[str]     # Links to ArchitecturalDecision IDs
    follow_up_status: Literal["pending", "in_progress", "completed", "wont_do"] | None


@dataclass
class HandoverPackage:
    """Generated handover documentation for next semester"""
    id: str
    generated_at: datetime
    semester: str

    # Content sections
    executive_summary: str
    key_decisions: list[str]         # ArchitecturalDecision IDs
    lessons_learned: list[str]       # RetrospectiveLearning IDs
    known_issues: list[str]
    recommended_priorities: list[str]

    # Quality metadata
    human_reviewed: bool
    reviewer_notes: str | None
```

### 3.3 Knowledge Store Adapter

**New file:** `adapters/knowledge_store_adapter.py`

```python
class KnowledgeStoreAdapter:
    """
    Persists knowledge capture data.
    Uses both SQLite (structured queries) and ChromaDB (semantic search).
    """

    def __init__(
        self,
        db_path: Path,
        chroma_adapter: ChromaAdapter
    ):
        self.db_path = db_path
        self.chroma = chroma_adapter
        self._init_db()

    def _init_db(self) -> None:
        """Create SQLite tables for knowledge storage"""
        pass

    # Architectural Decisions
    async def save_decision(self, decision: ArchitecturalDecision) -> None:
        """Save decision to SQLite and index in ChromaDB for search"""
        pass

    async def get_decision(self, decision_id: str) -> ArchitecturalDecision | None:
        pass

    async def list_decisions(
        self,
        status: str | None = None,
        tags: list[str] | None = None,
        since: datetime | None = None
    ) -> list[ArchitecturalDecision]:
        pass

    async def search_decisions(self, query: str, limit: int = 5) -> list[ArchitecturalDecision]:
        """Semantic search over decisions using ChromaDB"""
        pass

    # Retrospective Learnings
    async def save_learning(self, learning: RetrospectiveLearning) -> None:
        pass

    async def get_learnings_by_sprint(self, sprint: str) -> list[RetrospectiveLearning]:
        pass

    async def get_learnings_by_category(
        self,
        category: str,
        since: datetime | None = None
    ) -> list[RetrospectiveLearning]:
        pass

    # Handover Generation
    async def generate_handover(self, semester: str) -> HandoverPackage:
        """
        Generate handover package from captured knowledge.
        Aggregates decisions, learnings, and synthesizes summary.
        """
        pass

    async def save_handover(self, package: HandoverPackage) -> None:
        pass

    async def get_handover(self, semester: str) -> HandoverPackage | None:
        pass
```

**SQLite Schema:**

```sql
CREATE TABLE architectural_decisions (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    team_id TEXT,
    title TEXT NOT NULL,
    context TEXT NOT NULL,
    decision TEXT NOT NULL,
    rationale TEXT NOT NULL,
    alternatives TEXT,              -- JSON array
    consequences TEXT,              -- JSON array
    status TEXT NOT NULL,
    related_issues TEXT,            -- JSON array
    related_files TEXT,             -- JSON array
    tags TEXT,                      -- JSON array

    INDEX idx_status (status),
    INDEX idx_timestamp (timestamp)
);

CREATE TABLE retrospective_learnings (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    team_id TEXT,
    sprint TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    related_decisions TEXT,         -- JSON array
    follow_up_status TEXT,

    INDEX idx_sprint (sprint),
    INDEX idx_category (category)
);

CREATE TABLE handover_packages (
    id TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    semester TEXT NOT NULL UNIQUE,
    executive_summary TEXT NOT NULL,
    key_decisions TEXT,             -- JSON array of IDs
    lessons_learned TEXT,           -- JSON array of IDs
    known_issues TEXT,              -- JSON array
    recommended_priorities TEXT,    -- JSON array
    human_reviewed INTEGER DEFAULT 0,
    reviewer_notes TEXT
);
```

### 3.4 Knowledge Capture Tools

#### Tool: `capture_decision`

```python
Tool(
    name="capture_decision",
    description="Record an architectural or technical decision made by the team. "
                "Creates an ADR (Architectural Decision Record) for future reference.",
    inputSchema={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Brief title for the decision (e.g., 'Use PostgreSQL for Foodplanner')"
            },
            "context": {
                "type": "string",
                "description": "Why was this decision needed? What problem does it solve?"
            },
            "decision": {
                "type": "string",
                "description": "What was decided?"
            },
            "rationale": {
                "type": "string",
                "description": "Why was this option chosen over alternatives?"
            },
            "alternatives": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Other options that were considered"
            },
            "consequences": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Expected impacts of this decision"
            },
            "related_issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Related GitHub issue numbers"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Categories (e.g., 'database', 'api', 'frontend')"
            }
        },
        "required": ["title", "context", "decision", "rationale"]
    }
)
```

**Handler:**

```python
async def handle_capture_decision(
    title: str,
    context: str,
    decision: str,
    rationale: str,
    alternatives: list[str] | None = None,
    consequences: list[str] | None = None,
    related_issues: list[str] | None = None,
    tags: list[str] | None = None
) -> list[TextContent]:
    """Capture an architectural decision"""

    store = get_knowledge_store_adapter()
    team_id = _current_session.get("team_id")

    adr = ArchitecturalDecision(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        team_id=team_id,
        title=title,
        context=context,
        decision=decision,
        rationale=rationale,
        alternatives=alternatives or [],
        consequences=consequences or [],
        status="accepted",
        related_issues=related_issues or [],
        related_files=[],
        tags=tags or []
    )

    await store.save_decision(adr)

    return [TextContent(
        type="text",
        text=f"# Decision Recorded\n\n"
             f"**{title}** (ID: `{adr.id[:8]}`)\n\n"
             f"This decision has been captured and will be included in the semester handover.\n\n"
             f"To reference this decision later, use ID: `{adr.id}`"
    )]
```

#### Tool: `capture_lesson`

```python
Tool(
    name="capture_lesson",
    description="Record a learning or insight from a sprint retrospective.",
    inputSchema={
        "type": "object",
        "properties": {
            "sprint": {
                "type": "string",
                "description": "Sprint identifier (e.g., '2025s1-sprint3')"
            },
            "category": {
                "type": "string",
                "enum": ["went_well", "to_improve", "action_item", "insight"],
                "description": "Type of learning"
            },
            "description": {
                "type": "string",
                "description": "The learning or insight"
            },
            "related_decisions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "IDs of related architectural decisions"
            }
        },
        "required": ["sprint", "category", "description"]
    }
)
```

#### Tool: `search_knowledge`

```python
Tool(
    name="search_knowledge",
    description="Search captured decisions and learnings. "
                "Useful for finding relevant past decisions when facing similar problems.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "type": {
                "type": "string",
                "enum": ["decisions", "learnings", "all"],
                "description": "What to search"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results (default: 5)"
            }
        },
        "required": ["query"]
    }
)
```

#### Tool: `generate_handover_summary`

```python
Tool(
    name="generate_handover_summary",
    description="Generate a handover package summarizing the semester's decisions, "
                "learnings, and recommendations for the next team. "
                "Typically called at semester end.",
    inputSchema={
        "type": "object",
        "properties": {
            "semester": {
                "type": "string",
                "description": "Semester identifier (e.g., '2025s1')"
            },
            "additional_notes": {
                "type": "string",
                "description": "Any additional notes to include in handover"
            }
        },
        "required": ["semester"]
    }
)
```

**Handler:**

```python
async def handle_generate_handover_summary(
    semester: str,
    additional_notes: str | None = None
) -> list[TextContent]:
    """Generate comprehensive handover package"""

    store = get_knowledge_store_adapter()

    # Generate package from stored knowledge
    package = await store.generate_handover(semester)

    # Format as markdown
    output = [
        f"# GIRAF Handover Package: {semester}",
        f"\n*Generated: {package.generated_at.isoformat()}*",
        f"\n## Executive Summary\n\n{package.executive_summary}",
        "\n## Key Decisions\n"
    ]

    for decision_id in package.key_decisions:
        decision = await store.get_decision(decision_id)
        if decision:
            output.append(f"### {decision.title}")
            output.append(f"\n**Context:** {decision.context}")
            output.append(f"\n**Decision:** {decision.decision}")
            output.append(f"\n**Rationale:** {decision.rationale}\n")

    output.append("\n## Lessons Learned\n")
    for learning_id in package.lessons_learned:
        # ... format learnings
        pass

    output.append("\n## Known Issues\n")
    for issue in package.known_issues:
        output.append(f"- {issue}")

    output.append("\n## Recommended Priorities for Next Semester\n")
    for priority in package.recommended_priorities:
        output.append(f"1. {priority}")

    output.append("\n---")
    output.append("\n*This package requires human review before finalizing.*")
    output.append(f"\n*Package ID: {package.id}*")

    return [TextContent(type="text", text="\n".join(output))]
```

#### Tool: `review_handover`

```python
Tool(
    name="review_handover",
    description="Mark a handover package as reviewed and add reviewer notes. "
                "Supervisor only.",
    inputSchema={
        "type": "object",
        "properties": {
            "package_id": {
                "type": "string",
                "description": "Handover package ID"
            },
            "approved": {
                "type": "boolean",
                "description": "Whether the package is approved"
            },
            "notes": {
                "type": "string",
                "description": "Reviewer notes and corrections"
            }
        },
        "required": ["package_id", "approved"]
    }
)
```

---

## 5. Cross-Disciplinary Framing System (NEW)

### 5.1 Purpose

Support knowledge transfer across disciplinary boundaries. Students from CS, Interaction Design, Business, and Health backgrounds approach the same codebase with different mental models, vocabularies, and learning needs. AI must function as a "boundary object" — meaningful across disciplines while supporting discipline-specific needs.

This directly addresses RQ2 (Disciplinary): *How can AI bridge knowledge gaps between people with different professional backgrounds?*

### 5.2 Discipline Profiles

**New file:** `data/discipline_profiles.yaml`

```yaml
# Discipline-specific knowledge needs and vocabulary mappings
disciplines:
  cs:
    name: "Computer Science"
    vocabulary_emphasis:
      - algorithms
      - data structures
      - complexity
      - design patterns
      - type systems
    explanation_style: "technical_precise"
    default_code_depth: "detailed"
    assumed_knowledge:
      - basic programming
      - git workflow
      - object-oriented concepts

  id:
    name: "Interaction Design"
    vocabulary_emphasis:
      - user experience
      - accessibility
      - visual hierarchy
      - interaction patterns
      - user flows
    explanation_style: "conceptual_visual"
    default_code_depth: "high_level"
    assumed_knowledge:
      - design thinking
      - prototyping
      - user research
    translation_hints:
      "repository pattern": "Like separating your design files from your prototype"
      "API endpoint": "The URL where our app talks to the server"
      "state management": "How the app remembers what the user is doing"

  business:
    name: "Business/IT"
    vocabulary_emphasis:
      - value proposition
      - stakeholders
      - requirements
      - ROI
      - scalability
    explanation_style: "outcome_focused"
    default_code_depth: "overview"
    assumed_knowledge:
      - project management
      - requirements gathering
      - business analysis
    translation_hints:
      "refactoring": "Reorganizing the code to reduce future maintenance costs"
      "technical debt": "Shortcuts that save time now but cost more later"
      "microservices": "Breaking the system into smaller, independently deployable pieces"

  health:
    name: "Health Informatics"
    vocabulary_emphasis:
      - patient safety
      - clinical workflow
      - data privacy
      - interoperability
      - FHIR/HL7
    explanation_style: "clinical_context"
    default_code_depth: "moderate"
    assumed_knowledge:
      - healthcare domain
      - privacy regulations
      - clinical workflows
    translation_hints:
      "authentication": "Like checking ID before accessing patient records"
      "data validation": "Ensuring medication dosages are within safe ranges"
      "audit logging": "Recording who accessed what patient data and when"

# Cross-discipline translation mappings
concept_translations:
  "dependency injection":
    cs: "A design pattern where dependencies are passed in rather than created internally"
    id: "The app gets its tools handed to it rather than finding them itself"
    business: "Components are interchangeable, reducing vendor lock-in"
    health: "Like how different lab systems can plug into the same hospital system"

  "null pointer exception":
    cs: "Attempting to use a reference that points to no object"
    id: "The app tried to use something that doesn't exist, like clicking a button that isn't there"
    business: "A common bug where the system expects data that wasn't provided"
    health: "Like trying to read a patient record that hasn't been created yet"
```

### 5.3 Multi-Framing Service

**New file:** `core/services/multiframe_service.py`

```python
@dataclass
class FramedExplanation:
    """Same concept explained for different disciplines"""
    concept: str
    frames: dict[str, str]  # discipline -> explanation
    default_frame: str


class MultiFrameService:
    """Provides discipline-aware explanations"""

    def __init__(self, profiles_path: Path):
        self.profiles = self._load_profiles(profiles_path)

    def get_discipline_profile(self, discipline: str) -> dict:
        """Get profile for a discipline"""
        return self.profiles.get("disciplines", {}).get(discipline, {})

    def translate_concept(self, concept: str, target_discipline: str) -> str | None:
        """Translate a technical concept for a specific discipline"""
        translations = self.profiles.get("concept_translations", {})
        if concept.lower() in translations:
            return translations[concept.lower()].get(target_discipline)
        return None

    def get_explanation_style(self, discipline: str) -> str:
        """Get preferred explanation style for discipline"""
        profile = self.get_discipline_profile(discipline)
        return profile.get("explanation_style", "technical_precise")

    def get_code_depth(self, discipline: str) -> str:
        """Get appropriate code detail level for discipline"""
        profile = self.get_discipline_profile(discipline)
        return profile.get("default_code_depth", "detailed")

    def should_translate_term(self, term: str, discipline: str) -> bool:
        """Check if a term needs translation for this discipline"""
        profile = self.get_discipline_profile(discipline)
        hints = profile.get("translation_hints", {})
        return term.lower() in hints

    def adapt_response_for_discipline(
        self,
        response: str,
        target_discipline: str
    ) -> str:
        """
        Adapt a response for a specific discipline.
        - Adjusts vocabulary
        - Adds contextual bridges
        - Modifies code detail level
        """
        profile = self.get_discipline_profile(target_discipline)
        if not profile:
            return response

        # Add translation hints for technical terms
        hints = profile.get("translation_hints", {})
        for term, translation in hints.items():
            if term in response.lower():
                response = self._add_translation_note(response, term, translation)

        return response

    def generate_multiframe_explanation(
        self,
        concept: str,
        context: str
    ) -> FramedExplanation:
        """Generate explanation of a concept for all disciplines"""
        frames = {}
        for discipline in self.profiles.get("disciplines", {}).keys():
            frames[discipline] = self._generate_frame(concept, context, discipline)

        return FramedExplanation(
            concept=concept,
            frames=frames,
            default_frame=frames.get("cs", list(frames.values())[0])
        )
```

### 5.4 Discipline-Aware Response Middleware

```python
# In server.py, after getting result but before returning

multiframe = get_multiframe_service()
discipline = _current_session.get("discipline")

if discipline and discipline != "cs":
    # Adapt response for non-CS disciplines
    adapted = multiframe.adapt_response_for_discipline(
        result[0].text,
        discipline
    )
    result = [TextContent(type="text", text=adapted)]
```

### 5.5 Cross-Discipline Tools

#### Tool: `explain_for_discipline`

```python
Tool(
    name="explain_for_discipline",
    description="Re-explain a concept or the previous response for a different "
                "disciplinary background.",
    inputSchema={
        "type": "object",
        "properties": {
            "target_discipline": {
                "type": "string",
                "enum": ["cs", "id", "business", "health"],
                "description": "Target discipline for explanation"
            },
            "concept": {
                "type": "string",
                "description": "Specific concept to explain (optional, defaults to previous response)"
            }
        },
        "required": ["target_discipline"]
    }
)
```

#### Tool: `compare_perspectives`

```python
Tool(
    name="compare_perspectives",
    description="Show how different disciplines would approach or understand "
                "a particular design decision or concept.",
    inputSchema={
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The topic or decision to analyze"
            }
        },
        "required": ["topic"]
    }
)

async def handle_compare_perspectives(topic: str) -> list[TextContent]:
    """Show multi-disciplinary perspectives on a topic"""
    multiframe = get_multiframe_service()

    perspectives = []
    for discipline in ["cs", "id", "business", "health"]:
        profile = multiframe.get_discipline_profile(discipline)
        perspectives.append(f"### {profile['name']} Perspective\n")
        # Generate discipline-specific perspective
        # ...

    return [TextContent(type="text", text="\n".join(perspectives))]
```

### 5.6 Knowledge Capture with Discipline Framing

When capturing decisions, allow multi-perspective documentation:

```python
# Extended capture_decision tool
Tool(
    name="capture_decision",
    description="Record an architectural decision with explanations for multiple disciplines.",
    inputSchema={
        "type": "object",
        "properties": {
            # ... existing properties ...
            "discipline_notes": {
                "type": "object",
                "description": "Discipline-specific explanations of this decision",
                "properties": {
                    "cs": {"type": "string"},
                    "id": {"type": "string"},
                    "business": {"type": "string"},
                    "health": {"type": "string"}
                }
            }
        }
    }
)
```

### 5.7 Cross-Disciplinary Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Translation Usage** | % of sessions using explain_for_discipline | Track patterns |
| **Discipline Gap** | Performance difference between CS and non-CS students | ≤20% difference |
| **Cross-Discipline Rating** | Usefulness rating by non-CS students | ≥4/5 |
| **Vocabulary Bridge Success** | % of translated terms rated as helpful | ≥80% |
| **Multi-Frame Decision Coverage** | % of decisions with multiple discipline explanations | ≥50% |

---

## 6. File Structure Summary

### New Files

```
girafMCP-py/
├── core/
│   ├── types.py                      # Extended with QueryLog, ArchitecturalDecision, etc.
│   └── services/
│       ├── query_classifier.py       # NEW: Query type classification
│       ├── guardrails_service.py     # NEW: Guardrails logic
│       ├── resilience_service.py     # NEW: Failure injection
│       └── multiframe_service.py     # NEW: Cross-disciplinary framing
├── adapters/
│   ├── query_log_adapter.py          # NEW: SQLite logging
│   └── knowledge_store_adapter.py    # NEW: Knowledge capture storage
├── tools/
│   ├── logging.py                    # NEW: set_session_metadata, export_query_logs
│   ├── guardrails.py                 # NEW: request_more_detail, configure_guardrails
│   ├── knowledge.py                  # NEW: capture_decision, capture_lesson, etc.
│   ├── resilience.py                 # NEW: report_error_found
│   └── discipline.py                 # NEW: explain_for_discipline, compare_perspectives
├── data/
│   ├── guardrails.yaml               # NEW: Guardrails configuration
│   ├── resilience_tests.yaml         # NEW: Failure injection configuration
│   ├── discipline_profiles.yaml      # NEW: Cross-disciplinary translation mappings
│   ├── query_logs.db                 # NEW: SQLite database (created at runtime)
│   ├── knowledge.db                  # NEW: SQLite database (created at runtime)
│   └── resilience_logs.db            # NEW: Injected errors tracking
└── server.py                         # Modified: middleware integration
```

### Modified Files

| File | Changes |
|------|---------|
| `server.py` | Add logging, guardrails, resilience, and discipline middleware; new tool registrations |
| `core/types.py` | Add `QueryLog`, `MetaSkillIndicators`, `ArchitecturalDecision`, `InjectedError`, etc. |
| `pyproject.toml` | Add `aiosqlite` dependency |

---

## 7. Configuration Reference

### Environment Variables

```bash
# Query Logging
GIRAF_QUERY_LOGGING_ENABLED=true
GIRAF_QUERY_LOG_DB=data/query_logs.db
GIRAF_REQUIRE_LOGGING_CONSENT=true

# Guardrails
GIRAF_GUARDRAILS_CONFIG=data/guardrails.yaml

# Knowledge Store
GIRAF_KNOWLEDGE_DB=data/knowledge.db

# Resilience Testing (NEW)
GIRAF_RESILIENCE_CONFIG=data/resilience_tests.yaml
GIRAF_RESILIENCE_ENABLED=false  # Enable only during assessment

# Cross-Disciplinary Framing (NEW)
GIRAF_DISCIPLINE_PROFILES=data/discipline_profiles.yaml
```

### New Dependencies

```toml
[project.dependencies]
aiosqlite = "^0.19.0"    # Async SQLite for logging and knowledge store
```

---

## 8. Implementation Priority

### Phase 1: Core Infrastructure (Days 1-3)
1. `QueryLog` and `MetaSkillIndicators` dataclasses
2. `QueryLogAdapter` with SQLite
3. Middleware in `server.py`
4. `set_session_metadata` tool
5. Query type and meta-skill classification

### Phase 2: Guardrails System (Days 4-5)
1. `guardrails.yaml` configuration
2. `GuardrailsService` class
3. Integration in `call_tool()`
4. `request_more_detail` tool
5. Team-specific override system

### Phase 3: Knowledge Capture (Days 6-7)
1. Knowledge dataclasses
2. `KnowledgeStoreAdapter`
3. Capture tools (`capture_decision`, `capture_lesson`)
4. `generate_handover_summary` tool

### Phase 4: Resilience Testing (Days 8-10) *(NEW)*
1. `resilience_tests.yaml` configuration
2. `ResilienceService` class
3. Error injection logic
4. `report_error_found` tool
5. Resilience metrics tracking

### Phase 5: Cross-Disciplinary Framing (Days 11-12) *(NEW)*
1. `discipline_profiles.yaml` configuration
2. `MultiFrameService` class
3. Response adaptation middleware
4. `explain_for_discipline` and `compare_perspectives` tools

### Phase 6: Testing & Documentation (Days 13-14)
1. Unit tests for each component
2. Integration tests
3. Resilience test scenarios
4. Cross-disciplinary validation
5. Update README with new features
6. Update CONTRIBUTING with research context

---

## 9. Research Data Access

### For Researchers

Query logs can be exported via:
1. **Tool**: `export_query_logs` (in-session CSV generation)
2. **Direct**: SQLite file at `data/query_logs.db`
3. **Script**: Add `scripts/export_research_data.py` for batch export

### Data Format for Analysis

```csv
id,timestamp,session_id,team_id,role,discipline,tool_name,query_type,duration_ms,result_count
abc123,2025-02-15T10:30:00Z,sess_001,team_a,dev,cs,search_code,navigation,245,12
def456,2025-02-15T10:30:45Z,sess_001,team_a,dev,cs,get_file,explanation,89,1
```

### Ethical Considerations

- All logging requires explicit consent via `set_session_metadata`
- Queries can be anonymized by omitting `team_id`
- Export tools require supervisor authentication
- Raw query content can be excluded from exports if needed
