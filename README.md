# GIRAF MCP Server

MCP (Model Context Protocol) server for the GIRAF project at Aalborg University. Helps students with technical questions, domain knowledge, and project context.

## Features

- **Code Search**: Search across GIRAF repositories with GitHub permalinks
- **Documentation**: Semantic search through wiki and documentation
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

Set environment variables:

```bash
# Optional: GitHub token for higher rate limits
export GITHUB_TOKEN="ghp_..."

# Optional: ChromaDB persistence directory
export CHROMA_PERSIST_DIR="./chroma_data"

# Optional: Custom data directory
export GIRAF_DATA_DIR="./data"
```

## Usage

### Run the MCP Server

```bash
giraf-mcp
```

### Claude Desktop Configuration

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "giraf": {
      "command": "/path/to/girafMCP-py/.venv/bin/giraf-mcp",
      "env": {
        "GITHUB_TOKEN": "ghp_..."
      }
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_repositories` | List all GIRAF GitHub repositories |
| `get_file` | Get file content with permalink for citation |
| `search_code` | Search code across repositories |
| `search_documentation` | Semantic search in wiki/docs |
| `get_permalink` | Generate GitHub permalink with line numbers |
| `get_project_context` | Get current semester focus and priorities |
| `list_personas` | List available user personas |
| `get_persona` | Get persona details for tailored responses |
| `search_domain_knowledge` | Search autism/accessibility domain knowledge |
| `list_domain_topics` | List available domain topics |

## Example Queries

**For CS Students:**
- "Where is user authentication handled in foodplanner-api?"
- "Show me the Flutter widget for displaying schedules"
- "How do I set up the development environment?"

**For Pedagogy Students:**
- "Why do children with autism benefit from visual schedules?"
- "What sensory considerations should I know about?"
- "How does the app help with transitions?"

**For Supervisors:**
- "What were the main decisions from last semester?"
- "What are the current project priorities?"
- "Show me the handover documentation"

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=girafmcp

# Type checking
mypy src/
```

## Project Structure

```
girafMCP-py/
├── src/girafmcp/
│   ├── core/
│   │   ├── ports.py      # Abstract interfaces
│   │   └── types.py      # Domain types
│   ├── adapters/
│   │   ├── github_adapter.py   # GitHub API
│   │   ├── chroma_adapter.py   # Vector store
│   │   └── file_adapter.py     # YAML/markdown files
│   └── server.py         # MCP server
├── data/
│   ├── context.yaml      # Project context
│   ├── personas.yaml     # User personas
│   └── domain/           # Domain knowledge markdown
├── tests/
└── PLAN.md               # Implementation roadmap
```

## License

Part of the GIRAF project at Aalborg University.
