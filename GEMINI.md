# GIRAF MCP Server

## Project Overview

**GIRAF MCP Server** (`girafMCP-py`) is an AI-powered knowledge assistant designed for the GIRAF project at Aalborg University. It serves as a bridge between AI assistants (like Claude) and the GIRAF ecosystem, enabling easy access to codebases, documentation, domain knowledge, and project context. This helps new students onboard and contribute effectively to building accessible apps for children with autism.

### Key Technologies
*   **Language:** Python 3.11+
*   **Protocol:** [Model Context Protocol (MCP)](https://modelcontextprotocol.io)
*   **Vector Store:** ChromaDB (for semantic search)
*   **PDF Processing:** pdfplumber
*   **Networking:** httpx

### Architecture
The project follows a **Hexagonal Architecture**:
*   **Server (`src/girafmcp/server.py`):** Defines the MCP tools, handles dispatch, and manages startup/initialization.
*   **Tools (`src/girafmcp/tools/`):** Contains specialized tool handlers (github, search, context).
*   **Core (`src/girafmcp/core/`):** Contains business logic, ports (interfaces), and types.
*   **Adapters (`src/girafmcp/adapters/`):** Implements interfaces for external systems (GitHub, ChromaDB, File System, PDF processing).
*   **Data (`data/`):** Stores domain knowledge (Markdown), project context (YAML), and personas (YAML).

## Building and Running

### Prerequisites
*   Python 3.11 or higher
*   A GitHub Personal Access Token (for API access)

### Installation
1.  **Clone and setup virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    ```
2.  **Configuration:**
    Create a `.env` file based on `.env.example`:
    ```bash
    GITHUB_TOKEN=ghp_...
    # Optional: Path to directory containing PDFs for semantic search
    GIRAF_DOCUMENTS_DIR=/path/to/documents
    ```

### Running the Server
*   **Standard Mode (stdio):**
    ```bash
    giraf-mcp
    ```
*   **HTTP Mode (for remote/shared access):**
    ```bash
    pip install -e ".[http]"
    giraf-mcp --http --port 8000
    ```

### Testing
*   **Run all tests:**
    ```bash
    pytest
    ```
*   **Run with coverage:**
    ```bash
    pytest --cov=girafmcp
    ```

### Linting and Type Checking
*   **Linting:**
    ```bash
    ruff check src/
    ```
*   **Formatting:**
    ```bash
    ruff format src/
    ```
*   **Type Checking:**
    ```bash
    mypy src/
    ```

## Development Conventions

### Code Structure
*   **`src/girafmcp/`**: Main source code.
    *   `adapters/`: Implementations for external interactions (GitHub, Chroma, etc.).
    *   `core/`: Application core, including ports and services.
    *   `tools/`: Tool definitions and handlers (if separated).
*   **`data/`**: Static data files.
    *   `domain/`: Markdown files explaining autism and accessibility concepts.
    *   `context.yaml`: Current semester focus and priorities.
    *   `personas.yaml`: User persona definitions.
*   **`tests/`**: Pytest-based test suite.

### Contribution Guidelines
*   **Domain Knowledge:** Add Markdown files to `data/domain/` with clear H1/H2 headings.
*   **Project Context:** Update `data/context.yaml` at the start of semesters or when priorities change.
*   **Personas:** Add new personas to `data/personas.yaml` following the existing format.
*   **Code:**
    *   Follow the hexagonal architecture.
    *   Ensure all tests pass (`pytest`).
    *   Adhere to linting standards (`ruff`).
    *   Add new tools by defining them in `server.py` and implementing a handler.

## Key Files
*   `README.md`: General project introduction and usage.
*   `CONTRIBUTING.md`: Detailed guide for contributors.
*   `pyproject.toml`: Dependency and build configuration.
*   `src/girafmcp/server.py`: Entry point for the MCP server.
*   `data/context.yaml`: Dynamic project context.

## Improvement Plan

The following improvements are planned to enhance the project's quality and deployability:

1.  **Refactor `server.py` (Completed):** Modularize tool handlers into `src/girafmcp/tools/` to prevent a "God Object" anti-pattern and improve maintainability.
2.  **Add CI/CD Pipeline (Next):** Implement GitHub Actions workflows (`.github/workflows/ci.yml`) to automate:
    *   Running tests (`pytest`)
    *   Linting code (`ruff check`)
    *   Type checking (`mypy`)
3.  **Containerization (Planned):** Create a `Dockerfile` to containerize the application, simplifying deployment for the HTTP server mode.
4.  **Consistent Logging (Planned):** Integrate the standard `logging` module throughout tool handlers to replace simple error strings with structured logs for better debugging.
