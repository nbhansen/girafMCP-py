"""Tests for server dependency injection and tool wiring."""

import pytest
from mcp.types import Tool

from girafmcp.server import list_tools, call_tool


class TestServerWiring:
    """Tests for the server module's DI and tool dispatch."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self, patch_server_container):
        """list_tools should aggregate tools from all modules."""
        tools = await list_tools()
        
        # We expect a substantial number of tools (36 in total as per docs)
        assert len(tools) >= 36
        
        tool_names = [t.name for t in tools]
        assert "list_repositories" in tool_names
        assert "search_documentation" in tool_names
        assert "capture_decision" in tool_names
        assert "report_error_found" in tool_names

    @pytest.mark.asyncio
    async def test_call_tool_dispatches_correctly(self, patch_server_container, mock_container):
        """call_tool should dispatch to the correct handler using container dependencies."""
        
        # Test GitHub dispatch
        mock_container.github_adapter.list_repos.return_value = []
        await call_tool("list_repositories", {})
        mock_container.github_adapter.list_repos.assert_called_once()

        # Test Context dispatch
        await call_tool("get_project_context", {})
        mock_container.file_adapter.get_context.assert_called_once()
        
        # Test Knowledge dispatch
        # (We need to ensure list_decisions returns something mockable if awaited)
        # But our mock_research_data_adapter is a real instance with a temp DB, so it works!
        await call_tool("list_decisions", {})
        # Since it's a real instance on a temp DB, it will just return empty list, which is fine.

    @pytest.mark.asyncio
    async def test_unknown_tool(self, patch_server_container):
        """Calling an unknown tool should return an error message."""
        result = await call_tool("nonexistent_tool", {})
        assert result[0].text.startswith("Unknown tool")
