# Contributing to GIRAF MCP Server

This guide explains how to contribute to the GIRAF knowledge assistant.

## Types of Contributions

### 1. Adding Domain Knowledge

Domain knowledge helps explain autism, visual schedules, and accessibility concepts to students.

**Location:** `data/domain/`

**Format:** Markdown files with clear headings

**Example:** Create `data/domain/transitions.md`:

```markdown
# Transitions and Routine Changes

## Why Transitions Are Challenging

Many individuals with autism find transitions between activities
difficult because...

## Strategies for Supporting Transitions

### Visual Timers
Visual timers help by showing...

### Transition Warnings
Giving advance notice of changes...
```

**Guidelines:**
- Use H1 (`#`) for the main topic
- Use H2 (`##`) for major sections
- Keep language accessible to non-experts
- Include practical implications for GIRAF
- Cite sources where applicable

### 2. Updating Project Context

Project context captures current semester information that changes frequently.

**Location:** `data/context.yaml`

**When to update:**
- Start of each semester
- When priorities change
- When new issues/workarounds are discovered
- After major decisions

**Example:**

```yaml
# Updated: 2025-02-15
semester: "Spring 2025"
focus: "Food planner accessibility improvements"

current_priorities:
  - "Issue #123: Screen reader support"
  - "Issue #145: High contrast mode"

known_gotchas:
  - issue: "API tests flaky on CI"
    workaround: "Re-run failed tests, known timing issue"

recent_decisions:
  - date: "2025-02-10"
    decision: "Switched to GraphQL for new endpoints"
    context: "See ADR-005 in wiki"

important_links:
  - name: "Project Board"
    url: "https://github.com/orgs/aau-giraf/projects/1"
    description: "Current sprint tasks"
```

### 3. Adding or Updating Personas

Personas help tailor responses to different user backgrounds.

**Location:** `data/personas.yaml`

**Example:** Adding a new persona:

```yaml
personas:
  # Existing personas...

  accessibility_expert:
    name: "Accessibility Expert"
    description: "You're evaluating the app's accessibility"
    style:
      tone: "Technical and evaluative"
      detail_level: "High - WCAG references, specific issues"
      vocabulary: "Accessibility terminology"
    focus_areas:
      - "WCAG compliance"
      - "Screen reader compatibility"
      - "Color contrast"
      - "Keyboard navigation"
    example_responses:
      - question: "How accessible is the schedule view?"
        answer: "The schedule view has several accessibility considerations..."
```

### 4. Adding Static Documents (PDFs)

Static documents like research papers and handover reports are ingested for semantic search.

**Location:** Set via `GIRAF_DOCUMENTS_DIR` environment variable

**Structure:**

```
documents/
├── research/
│   ├── _meta.yaml          # Tags for this folder
│   ├── autism-study.pdf
│   └── visual-schedules.pdf
├── handover/
│   ├── _meta.yaml
│   └── 2024-spring.pdf
└── guides/
    └── supervisor-guide.pdf
```

**Folder tags (`_meta.yaml`):**

```yaml
tags: ["research", "academic", "autism"]
description: "Research papers on autism and visual supports"
```

**Guidelines:**
- Organize PDFs into logical folders
- Add `_meta.yaml` to enable tag-based filtering
- Use descriptive filenames
- PDFs are auto-ingested on server restart

## Code Contributions

### Setup

```bash
# Clone the repository
git clone https://github.com/aau-giraf/girafMCP-py.git
cd girafMCP-py

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env with your GITHUB_TOKEN
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=girafmcp

# Run specific test file
pytest tests/test_pdf_adapter.py

# Run with verbose output
pytest -v
```

### Code Style

We use `ruff` for linting and formatting:

```bash
# Check for issues
ruff check src/

# Auto-fix issues
ruff check --fix src/

# Format code
ruff format src/
```

### Type Checking

```bash
mypy src/
```

### Adding a New Tool

1. **Define the tool** in `server.py` under `list_tools()`:

```python
Tool(
    name="my_new_tool",
    description="What this tool does",
    inputSchema={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
        },
        "required": ["param1"],
    },
)
```

2. **Add dispatch** in `call_tool()`:

```python
elif name == "my_new_tool":
    return await handle_my_new_tool(
        param1=arguments["param1"],
    )
```

3. **Implement handler**:

```python
async def handle_my_new_tool(param1: str) -> list[TextContent]:
    # Implementation
    return [TextContent(type="text", text="Result")]
```

4. **Add tests** in `tests/test_server_tools.py`

### Architecture

The project follows hexagonal architecture:

```
┌─────────────────────────────────┐
│      MCP Server (server.py)     │  Tool definitions
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│       Tool Handlers             │  Business logic
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│    Ports (core/ports.py)        │  Interfaces
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│   Adapters (adapters/*.py)      │  External integrations
│   - GitHubAdapter               │
│   - ChromaAdapter               │
│   - FileAdapter                 │
│   - PDFAdapter                  │
└─────────────────────────────────┘
```

### Pull Request Process

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Ensure tests pass: `pytest`
4. Ensure linting passes: `ruff check src/`
5. Commit with descriptive message
6. Push and create a pull request

## Questions?

- Check existing issues on GitHub
- Ask in the GIRAF Discord/Slack
- Contact the project supervisors
