"""Filesystem anchors for the GIRAF MCP server.

Defaults are resolved from the project root, not the current working
directory, so the server reads and writes the same data wherever it is
launched from.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
