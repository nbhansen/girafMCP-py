# GIRAF MCP Server - Implementation Plan

## Overview

MCP server to help students working on the GIRAF project at Aalborg University. Provides:
- Technical assistance with precise source attribution (GitHub permalinks)
- Domain knowledge about autism and visual schedules
- Project context (semester focus, known issues, decisions)
- Multi-discipline support via personas (CS students vs pedagogy students)

## Architecture

**Hexagonal Architecture** with ports/adapters pattern:
- `core/ports.py` - Abstract interfaces
- `core/types.py` - Domain types
- `adapters/` - Implementations (GitHub, ChromaDB, File)
- `server.py` - MCP server with tools

## Implementation Status

### Phase 1: Project Setup [DONE]
- [x] Python project with pyproject.toml
- [x] Dependencies: mcp, chromadb, httpx, pyyaml
- [x] Hexagonal architecture structure
- [x] pytest configuration

### Phase 2: GitHub Adapter [DONE]
- [x] List repositories from aau-giraf org
- [x] Get file content with permalinks
- [x] Search code across repos
- [x] Generate permalinks with line numbers
- [x] Tests (pass when not rate-limited)

### Phase 3: ChromaDB Adapter [DONE]
- [x] Ephemeral mode for testing
- [x] Persistent mode for production
- [x] CRUD operations for documents
- [x] Semantic search with scores
- [x] Full test coverage (16 tests)

### Phase 4: MCP Server Core [DONE]
- [x] Server initialization
- [x] Tool definitions with JSON schemas
- [x] Tool handlers
- [x] Entry point (giraf-mcp command)

### Phase 5: Project Context & Personas [DONE]
- [x] FileAdapter for YAML files
- [x] data/context.yaml - semester info, priorities, gotchas
- [x] data/personas.yaml - 4 personas with styles
- [x] get_project_context tool
- [x] list_personas tool
- [x] get_persona tool

### Phase 6: Domain Knowledge [DONE]
- [x] data/domain/ directory structure
- [x] autism-basics.md
- [x] visual-schedules.md
- [x] sensory-considerations.md
- [x] search_domain_knowledge tool
- [x] list_domain_topics tool

### Phase 7: Wiki Ingestion [TODO]
- [ ] Fetch wiki pages from aau-giraf.github.io
- [ ] Parse markdown content
- [ ] Chunk into semantic sections
- [ ] Populate ChromaDB with embeddings
- [ ] Add source URLs for attribution

### Phase 8: Documentation Search Enhancement [TODO]
- [ ] Improve search_documentation to use populated ChromaDB
- [ ] Add filtering by wiki section
- [ ] Include relevance explanations

### Phase 9: Integration & Testing [TODO]
- [ ] End-to-end MCP client testing
- [ ] Claude Desktop configuration
- [ ] Performance optimization
- [ ] Error handling improvements

### Phase 10: Deployment [TODO]
- [ ] README with setup instructions
- [ ] Environment variable documentation
- [ ] Example queries and responses
- [ ] Contribution guidelines

## Current Tools (10 total)

| Tool | Status | Description |
|------|--------|-------------|
| list_repositories | Done | List GIRAF GitHub repos |
| get_file | Done | Get file with permalink |
| search_code | Done | Search code in repos |
| search_documentation | Done | Semantic search (needs data) |
| get_permalink | Done | Generate citation links |
| get_project_context | Done | Semester focus, priorities |
| list_personas | Done | List available personas |
| get_persona | Done | Get persona details |
| search_domain_knowledge | Done | Search autism/GIRAF domain |
| list_domain_topics | Done | List domain topics |

## Next Steps

1. **Wiki Ingestion** - Populate ChromaDB with wiki content
2. **README** - Setup and usage documentation
3. **Testing with Claude** - Verify MCP integration works

## Data Files

```
data/
├── context.yaml      # Project context overlay
├── personas.yaml     # User persona definitions
└── domain/
    ├── autism-basics.md
    ├── visual-schedules.md
    └── sensory-considerations.md
```
