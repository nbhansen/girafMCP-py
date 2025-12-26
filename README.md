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
| **Static Documents** | Semantic search over PDFs, handover reports, and research papers |
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

# Optional: Directory containing PDFs for semantic search
GIRAF_DOCUMENTS_DIR=/path/to/documents
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
  -v $(pwd)/chroma_data:/app/chroma_data \
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
        "GIRAF_DOCUMENTS_DIR": "/path/to/documents"
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
| `search_documentation` | Semantic search in indexed docs |
| `search_static_documents` | Search ingested PDFs with page citations |
| `list_static_documents` | List all ingested PDFs with tags |

### Context & Knowledge
| Tool | Description |
|------|-------------|
| `get_project_context` | Current semester focus and priorities |
| `search_domain_knowledge` | Search autism/accessibility knowledge |
| `list_domain_topics` | List available domain topics |
| `list_personas` | List available user personas |
| `get_persona` | Get persona details for tailored responses |

## Static Document Search

Point `GIRAF_DOCUMENTS_DIR` to a folder with PDFs. The server auto-ingests them on startup.

```
/home/user/giraf-documents/
├── handover/
│   ├── _meta.yaml           # Tags all PDFs in folder
│   ├── FoodPlanner-SW4.pdf
│   └── VTA-IxD1.pdf
└── research/
    └── autism-study.pdf
```

**Folder tagging** with `_meta.yaml`:
```yaml
tags: ["handover", "semester", "documentation"]
```

## Development

```bash
# Run tests (57 passing)
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
│   ├── core/              # Ports, types, services
│   ├── adapters/          # GitHub, ChromaDB, PDF adapters
│   └── server.py          # MCP server (14 tools)
├── data/
│   ├── context.yaml       # Project context
│   ├── personas.yaml      # User personas
│   └── domain/            # Domain knowledge
└── tests/
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
