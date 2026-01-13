# GIRAF MCP Server (`girafMCP-py`)

## Project Overview

`girafMCP-py` is a Python-based **Model Context Protocol (MCP) server** designed to act as an AI-powered knowledge assistant for the **GIRAF project** at Aalborg University. GIRAF is an app environment helping children with autism structure their daily lives.

This server connects AI agents (like Gemini, Claude) to the GIRAF project's ecosystem, providing access to:
*   **Codebase:** Search and retrieval from GitHub repositories.
*   **Documentation:** Live search of the project Wiki and semantic search of static PDF documents (handover reports, research papers).
*   **Domain Knowledge:** Contextual information about autism, visual schedules, and accessibility.
*   **Research Features:** Experimental features for studying AI-assisted learning, including guardrails, resilience testing, and cross-disciplinary framing.

The project follows a **Hexagonal Architecture** pattern to separate domain logic from external tools and adapters.

## Architecture

*   **Core (`src/girafmcp/core/`):** Contains business logic, interfaces (ports), domain types, and the Dependency Injection container.
*   **Adapters (`src/girafmcp/adapters/`):** Implementations of ports for external systems (GitHub API, ChromaDB, File System, SQLite).
*   **Tools (`src/girafmcp/tools/`):** MCP tool definitions and handlers, organized by domain (search, github, knowledge, etc.).
*   **Middleware (`src/girafmcp/middleware/`):** Intercepts tool calls for logging, guardrails, and response adaptation.
*   **Server (`src/girafmcp/server.py`):** The application entry point, wiring everything together using `mcp.server`.

## Key Technologies

*   **Language:** Python 3.11+
*   **MCP SDK:** `mcp` library for Model Context Protocol implementation.
*   **Vector Database:** `chromadb` for semantic search of documentation.
*   **PDF Extraction:** `pymupdf4llm` for high-quality Markdown extraction and `pymupdf-layout` for layout analysis.
*   **Database:** `aiosqlite` for structured data (query logs, knowledge capture).
*   **Web Server:** `starlette` / `uvicorn` (for HTTP mode).
*   **Testing:** `pytest`, `pytest-cov`.
*   **Quality:** `ruff` (linting/formatting), `mypy` (static typing).

## Building and Running

### Prerequisites
*   Python 3.11 or higher
*   `pip`
*   Git

### Setup

1.  **Clone and Navigate:**
    ```bash
    # (Assuming you are already in the directory)
    cd girafMCP-py
    ```

2.  **Create Virtual Environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -e ".[dev]"
    ```
    *   `.[dev]` installs development tools (pytest, ruff, mypy).
    *   `.[http]` installs HTTP server dependencies.

4.  **Configuration:**
    Create a `.env` file (copy from `.env.example`) and configure:
    *   `GITHUB_TOKEN`: Required for GitHub tools.
    *   `GIRAF_DOCUMENTS_DIR`: Path to PDF documents for ingestion.
    *   Research feature flags (optional): `GIRAF_GUARDRAILS_ENABLED`, `GIRAF_RESILIENCE_ENABLED`, etc.

### Execution

*   **Standard Mode (Stdio):**
    Used by MCP clients (like Claude Desktop) to communicate via standard input/output.
    ```bash
    giraf-mcp
    ```

*   **HTTP Mode:**
    Runs a web server (SSE/POST) for remote access.
    ```bash
    giraf-mcp --http --port 8000
    ```

*   **Document Ingestion:**
    Ingests PDFs from `GIRAF_DOCUMENTS_DIR` into the vector database.
    ```bash
    giraf-mcp --ingest
    ```

### Docker

```bash
docker build -t giraf-mcp .
docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/app/data giraf-mcp
```

## Development Conventions

*   **Code Style:** Adhere to `ruff` formatting and linting rules.
    *   Run check: `ruff check src/`
    *   Format: `ruff format src/`
*   **Type Safety:** Strict type checking with `mypy` is enforced.
    *   Run check: `mypy src/`
*   **Testing:** Comprehensive test suite using `pytest`.
    *   Run tests: `pytest`
    *   Coverage: `pytest --cov=girafmcp`
*   **Dependency Injection:** Use `src/girafmcp/core/container.py` for managing dependencies. Avoid global state where possible, except for the container instance itself.
*   **Tool Definition:** New tools should be defined in `src/girafmcp/tools/` and registered in `server.py`.

## Directory Structure

*   `src/girafmcp/`: Source code.
*   `data/`: Configuration files (`personas.yaml`, `context.yaml`, `guardrails.yaml`) and domain knowledge (Markdown).
*   `tests/`: Unit and integration tests.
*   `chroma_data/`: Persisted Vector DB data.
*   `docs/`: Project documentation.
