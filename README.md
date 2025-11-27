# GIRAF MCP Server

MCP (Model Context Protocol) server for the GIRAF project at Aalborg University. Helps students with technical questions, domain knowledge, and project context.

## Features

- **Code Search**: Search across GIRAF repositories with GitHub permalinks
- **Wiki Search**: Live search through the GIRAF wiki documentation
- **Static Documents**: Semantic search over PDFs and research papers
- **Domain Knowledge**: Background on autism, visual schedules, accessibility
- **Project Context**: Current semester focus, known issues, recent decisions
- **Personas**: Adapts responses for CS students, pedagogy students, supervisors

## Installation

```bash
# Clone and enter directory
cd girafMCP-py

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"
```

## Configuration

Create a `.env` file in the project root (or set environment variables):

```bash
# Required for GitHub API (higher rate limits)
GITHUB_TOKEN=ghp_...

# Optional: ChromaDB persistence directory (default: ./chroma_data)
CHROMA_PERSIST_DIR=/path/to/chroma_data

# Optional: Custom data directory for context.yaml, personas.yaml, domain/
GIRAF_DATA_DIR=/path/to/data

# Optional: Directory containing PDFs for static document search
GIRAF_DOCUMENTS_DIR=/path/to/documents
```

### Static Document Directory

The `GIRAF_DOCUMENTS_DIR` should be an **absolute path** to a folder containing PDF files you want to search. The server will automatically ingest all PDFs on startup.

**Example structure:**

```
/home/user/giraf-documents/
├── research/
│   ├── _meta.yaml           # Optional: adds tags to all PDFs in this folder
│   ├── autism-study.pdf
│   └── visual-schedules.pdf
├── handover/
│   ├── _meta.yaml
│   └── spring-2024-report.pdf
└── guides/
    └── student-handbook.pdf
```

**Folder tagging with `_meta.yaml`:**

Create a `_meta.yaml` file in any folder to add tags to all PDFs in that folder:

```yaml
tags: ["research", "academic"]
description: "Research papers and academic sources"
```

Tags can be used to filter search results with the `search_static_documents` tool.

## Usage

### Run the MCP Server

```bash
giraf-mcp
```

### Claude Desktop Configuration

Add to your Claude Desktop config (`~/.config/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "giraf": {
      "command": "/path/to/girafMCP-py/.venv/bin/giraf-mcp",
      "cwd": "/path/to/girafMCP-py",
      "env": {
        "GITHUB_TOKEN": "ghp_...",
        "GIRAF_DOCUMENTS_DIR": "/path/to/your/documents"
      }
    }
  }
}
```

**Note:** The `cwd` field ensures the server runs from the project directory, which is needed for loading `data/` files if `GIRAF_DATA_DIR` is not set.

## Available Tools (14)

| Tool | Description |
|------|-------------|
| `list_repositories` | List all GIRAF GitHub repositories |
| `get_file` | Get file content with permalink for citation |
| `search_code` | Search code across repositories |
| `search_documentation` | Semantic search in indexed wiki/docs |
| `get_permalink` | Generate GitHub permalink with line numbers |
| `get_project_context` | Get current semester focus and priorities |
| `list_personas` | List available user personas |
| `get_persona` | Get persona details for tailored responses |
| `search_domain_knowledge` | Search autism/accessibility domain knowledge |
| `list_domain_topics` | List available domain topics |
| `search_wiki` | Live search the GIRAF wiki (fetches from GitHub) |
| `list_wiki_pages` | List all wiki pages by section |
| `search_static_documents` | Semantic search over ingested PDFs |
| `list_static_documents` | List all ingested PDFs with tags |

## Example Queries and Responses

When you ask Claude a question, it uses the appropriate tools and returns structured results. Here are examples:

### Code Search

**Query:** "Where is authentication handled?"

**Tool used:** `search_code`

**Response:**
```
# Code Search Results for: authentication

## foodplanner-api/src/Auth/AuthController.cs
- URL: https://github.com/aau-giraf/foodplanner-api/blob/abc123/src/Auth/AuthController.cs

## weekplanner-api/src/Controllers/AccountController.cs
- URL: https://github.com/aau-giraf/weekplanner-api/blob/def456/src/Controllers/AccountController.cs
```

### Wiki Search

**Query:** "How do I set up the development environment?"

**Tool used:** `search_wiki`

**Response:**
```
# Wiki Search Results: development setup

## Getting Started
**URL:** https://aau-giraf.github.io/wiki/development/getting-started/
**Relevance:** 85%

**Matching content:**
> To set up your development environment, first install Flutter...
> Make sure you have Docker installed for running the API locally...
```

### Domain Knowledge

**Query:** "Why do visual schedules help children with autism?"

**Tool used:** `search_domain_knowledge`

**Response:**
```
# Domain Knowledge: visual schedules autism

## Understanding Autism - Visual Processing
**Source:** autism-basics.md
**Relevance:** 100%

Many individuals with autism are visual learners and process
visual information more easily than verbal instructions...
```

### Project Context

**Query:** "What are the current priorities?"

**Tool used:** `get_project_context`

**Response:**
```
# GIRAF Project Context

**Semester:** Spring 2025
**Focus:** Food planner accessibility improvements

## Current Priorities
- Issue #123: Screen reader support
- Issue #145: High contrast mode

## Known Issues & Workarounds
**Issue:** Dev setup docs outdated
**Workaround:** Use Docker setup instead, see foodplanner README
```

### Static Document Search

**Query:** "Search research papers for communication strategies"

**Tool used:** `search_static_documents`

**Response:**
```
# Static Document Search: communication strategies

## autism-communication-study.pdf (Page 12)
**Source:** /path/to/documents/research/autism-communication-study.pdf
**Tags:** research, academic
**Relevance:** 78%

Children with autism often benefit from augmentative and
alternative communication (AAC) strategies including...
```

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=girafmcp

# Type checking
mypy src/

# Linting
ruff check src/
```

**Test Status:** 57 tests passing

## Project Structure

```
girafMCP-py/
├── src/girafmcp/
│   ├── core/
│   │   ├── ports.py           # Abstract interfaces
│   │   ├── types.py           # Domain types
│   │   └── services/          # Business logic
│   │       └── ingestion_service.py
│   ├── adapters/
│   │   ├── github_adapter.py  # GitHub API
│   │   ├── chroma_adapter.py  # Vector store
│   │   ├── file_adapter.py    # YAML/markdown files
│   │   └── pdf_adapter.py     # PDF extraction
│   └── server.py              # MCP server (14 tools)
├── data/
│   ├── context.yaml           # Project context
│   ├── personas.yaml          # User personas
│   └── domain/                # Domain knowledge markdown
├── tests/
│   ├── test_github_adapter.py
│   ├── test_chroma_adapter.py
│   ├── test_pdf_adapter.py
│   └── test_ingestion_service.py
└── .env.example               # Environment variable template
```

## How It Works

### Static Document Ingestion

1. On server startup, if `GIRAF_DOCUMENTS_DIR` is set, the server scans for PDF files
2. Each PDF is extracted page-by-page using pdfplumber
3. Long pages are split into ~1500 character chunks with overlap
4. Documents are stored in ChromaDB with metadata (source, page number, tags)
5. File hashes track changes - unchanged files are skipped on restart
6. Search uses semantic similarity to find relevant content

### Live Wiki Search

The wiki search fetches pages directly from the `aau-giraf/wiki` GitHub repository, ensuring results are always up-to-date without needing to re-index.

## License

Part of the GIRAF project at Aalborg University.
