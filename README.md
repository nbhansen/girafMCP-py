<p align="center">
  <img src="https://giraf.cs.aau.dk/wp-content/uploads/2020/05/cropped-girafIconAlpha.png" alt="GIRAF Logo" width="120" height="120">
</p>

<h1 align="center">GIRAF MCP Server</h1>

<p align="center">
  <strong>AI-powered knowledge assistant for the GIRAF project</strong><br>
  <em>Helping students build accessible apps for children with autism</em>
</p>

<p align="center">
  <a href="https://giraf.cs.aau.dk">Website</a> •
  <a href="https://aau-giraf.github.io/wiki/">Wiki</a> •
  <a href="https://github.com/aau-giraf">GitHub</a>
</p>

---

## About GIRAF

[GIRAF](https://giraf.cs.aau.dk) is an app environment for autistic children with minimal or no verbal communication. Developed since 2011 at Aalborg University in collaboration with Egebakken school and Børnehaven Birken kindergarten, GIRAF helps children plan their daily activities through visual schedules.

**This MCP server** connects AI assistants (like Claude) to GIRAF's codebase, documentation, and domain knowledge—making it easier for new students to onboard and contribute.

## What It Does

| Feature | Description |
|---------|-------------|
| **Code Search** | Search across active GIRAF repositories with GitHub permalinks |
| **Wiki Search** | Live search through GIRAF wiki documentation |
| **Static Documents** | Keyword search over handover reports and research papers |
| **Domain Knowledge** | Background on autism, visual schedules, and accessibility |
| **Project Context** | Current semester focus, known issues, recent decisions |
| **Personas** | Adapts responses for CS students, pedagogy students, supervisors |

> **Smart filtering**: Automatically excludes archived repositories and legacy wiki content to surface only current, relevant information.

## Quick Start

### Installation

```bash
# Clone and setup
cd girafMCP-py
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Configuration

Create a `.env` file:

```bash
# Required: GitHub token for API access
GITHUB_TOKEN=ghp_...

# Optional: Directory containing extracted markdown documents
# GIRAF_EXTRACTED_DIR=data/extracted

# Research features (all disabled by default)
GIRAF_GUARDRAILS_ENABLED=false
GIRAF_RESILIENCE_ENABLED=false
GIRAF_DISCIPLINE_ENABLED=false
```

### Run the Server

```bash
# Standard mode (stdio for Claude Desktop/Code)
giraf-mcp

# HTTP mode for remote/shared access
pip install -e ".[http]"
giraf-mcp --http --port 8000

# Docker mode
docker build -t giraf-mcp .
docker run -p 8000:8000 \
  -e GITHUB_TOKEN=your_token \
  -v $(pwd)/data:/app/data \
  giraf-mcp
```

### Claude Desktop Configuration

Add to `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "giraf": {
      "command": "/path/to/girafMCP-py/.venv/bin/giraf-mcp",
      "cwd": "/path/to/girafMCP-py",
      "env": {
        "GITHUB_TOKEN": "ghp_...",
        "GIRAF_EXTRACTED_DIR": "data/extracted"
      }
    }
  }
}
```

## Available Tools

### Repository & Code
| Tool | Description |
|------|-------------|
| `list_repositories` | List active GIRAF repositories (excludes archived) |
| `get_file` | Get file content with permalink for citation |
| `search_code` | Search code across repositories |
| `get_permalink` | Generate GitHub permalink with line numbers |

### Documentation
| Tool | Description |
|------|-------------|
| `search_wiki` | Live search GIRAF wiki (excludes legacy content) |
| `list_wiki_pages` | List all current wiki pages by section |
| `search_documentation` | Keyword search in extracted documents |
| `search_static_documents` | Search extracted documents with tag filtering |
| `list_static_documents` | List all extracted documents with tags |

### Context & Knowledge
| Tool | Description |
|------|-------------|
| `get_project_context` | Current semester focus and priorities |
| `search_domain_knowledge` | Search autism/accessibility knowledge |
| `list_domain_topics` | List available domain topics |
| `list_personas` | List available user personas |
| `get_persona` | Get persona details for tailored responses |

### Research Features

> **Note:** These features support pedagogical research on AI-assisted learning. They are disabled by default and require environment variable configuration to enable.

#### Session & Logging
| Tool | Description |
|------|-------------|
| `set_session_metadata` | Set user discipline, expertise level, and consent for analytics |

#### Guardrails System
| Tool | Description |
|------|-------------|
| `request_more_detail` | Request AI to provide more detailed explanation |
| `configure_guardrails` | Adjust guardrail sensitivity for current session |
| `get_guardrails_status` | View current guardrail configuration |
| `get_feature_status` | Check which research features are enabled |

#### Knowledge Capture
| Tool | Description |
|------|-------------|
| `capture_decision` | Record architectural decisions with rationale |
| `capture_lesson` | Document lessons learned during development |
| `search_knowledge` | Search captured decisions and lessons |
| `list_decisions` | List all recorded decisions |
| `list_learnings` | List all recorded lessons learned |
| `generate_handover_summary` | Auto-generate end-of-semester handover |
| `get_handover` | Retrieve a specific handover document |
| `review_handover` | Mark handover sections as reviewed |

#### Resilience Testing
| Tool | Description |
|------|-------------|
| `report_error_found` | Report that an injected error was discovered |
| `configure_resilience_test` | Configure error injection for assessment |
| `get_resilience_status` | Check current resilience test configuration |
| `get_resilience_metrics` | View resilience testing metrics |

#### Cross-Disciplinary Framing
| Tool | Description |
|------|-------------|
| `explain_for_discipline` | Re-explain concepts for a specific discipline |
| `compare_perspectives` | Show how different disciplines approach a topic |
| `translate_term` | Translate technical terms for non-CS backgrounds |
| `get_discipline_profile` | Get details about a discipline's learning profile |
| `list_disciplines` | List all available discipline profiles |

## Static Document Search

Extracted markdown files in `data/extracted/` are searched using keyword matching. Use `giraf-mcp --extract` to convert PDFs to markdown first.

## Development

```bash
# Run tests (249 tests)
pytest

# With coverage
pytest --cov=girafmcp

# Type checking & linting
mypy src/
ruff check src/
```

## Project Structure

```
girafMCP-py/
├── src/girafmcp/
│   ├── core/              # Ports, types, services, and DependencyContainer
│   │   └── services/      # Guardrails, resilience, multiframe services
│   ├── adapters/          # GitHub, keyword search, PDF, SQLite adapters
│   ├── middleware/        # Request/response middleware
│   ├── tools/             # Modular tool handlers & definitions by category
│   └── server.py          # MCP server entry point & tool aggregation
├── data/
│   ├── context.yaml       # Project context
│   ├── personas.yaml      # User personas
│   ├── guardrails.yaml    # Guardrails configuration
│   ├── resilience_tests.yaml  # Error injection config
│   ├── discipline_profiles.yaml  # Cross-disciplinary framing
│   └── domain/            # Domain knowledge (Markdown)
└── tests/                 # Comprehensive Pytest suite
```

## Related Projects

- [foodplanner](https://github.com/aau-giraf/foodplanner) - Food planning app (Flutter)
- [foodplanner-api](https://github.com/aau-giraf/foodplanner-api) - Food planner backend (.NET)
- [visual-tangible-artefacts](https://github.com/aau-giraf/visual-tangible-artefacts) - VTA app
- [weekplan](https://github.com/aau-giraf/weekplan) - Week planner (TypeScript)
- [wiki](https://github.com/aau-giraf/wiki) - Project documentation

---

<p align="center">
  Part of the <a href="https://giraf.cs.aau.dk">GIRAF project</a> at Aalborg University<br>
  <sub>Helping children with autism through accessible technology since 2011</sub>
</p>
