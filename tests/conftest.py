"""Pytest configuration and fixtures."""

from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")
