"""
tests/test_registry.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for the ToolRegistry.

Tests verify:
  - All tools are registered on build
  - Unknown tool execution returns an error ToolResult (no crash)
  - OpenAI function spec format is correct
  - Tool lookup works by name

Run with:
  cd ai-service
  pytest tests/test_registry.py -v
"""

import pytest
from app.orchestrator.tool_registry import build_registry, ToolRegistry
from app.schemas.responses import ToolResult


class TestToolRegistry:

    def setup_method(self):
        self.registry = build_registry()

    def test_all_three_tools_registered(self):
        names = self.registry.list_tool_names()
        # Specialist analysis tools
        assert "analyze_image" in names
        assert "detect_change" in names
        assert "analyze_sar_optical" in names
        # Satellite acquisition tools
        assert "fetch_sentinel1" in names
        assert "fetch_sentinel2" in names
        assert "fetch_landsat" in names
        assert "fetch_viirs_modis" in names

    def test_list_tool_names_returns_list(self):
        assert isinstance(self.registry.list_tool_names(), list)
        assert len(self.registry.list_tool_names()) >= 7  # 4 acquisition + 3 specialist

    def test_get_tool_returns_tool(self):
        tool = self.registry.get_tool("analyze_image")
        assert tool is not None
        assert tool.name == "analyze_image"

    def test_get_unknown_tool_returns_none(self):
        tool = self.registry.get_tool("nonexistent_tool")
        assert tool is None

    def test_execute_known_tool(self):
        result = self.registry.execute(
            "analyze_image",
            {"query": "What do you see?"}
        )
        assert isinstance(result, ToolResult)
        assert result.tool == "analyze_image"

    def test_execute_unknown_tool_returns_error_result(self):
        """Calling an unknown tool must return ToolResult with error, not raise."""
        result = self.registry.execute("fake_tool", {"query": "test"})
        assert isinstance(result, ToolResult)
        assert result.error is not None
        assert "not registered" in result.error.lower() or "unknown" in result.error.lower()

    def test_to_openai_tools_format(self):
        """OpenAI tool spec must have the correct structure for function calling."""
        tools = self.registry.to_openai_tools()
        assert isinstance(tools, list)
        assert len(tools) == 8  # 5 acquisition (incl. fetch_multitemporal_sentinel2) + 3 specialist

        for tool_spec in tools:
            assert tool_spec["type"] == "function"
            assert "function" in tool_spec
            fn = tool_spec["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            assert fn["parameters"]["type"] == "object"
            assert "properties" in fn["parameters"]

    def test_register_new_tool(self):
        """Adding a new tool should work without touching existing code."""
        from app.tools.base import BaseTool
        from app.schemas.responses import ToolResult

        class DummyTool(BaseTool):
            @property
            def name(self): return "dummy_tool"
            @property
            def description(self): return "A dummy tool for testing"
            @property
            def input_schema(self):
                return {"type": "object", "properties": {"query": {"type": "string"}}}
            def execute(self, args):
                return ToolResult(tool="dummy_tool", model="dummy", mode="mock", answer="dummy")

        registry = ToolRegistry()
        registry.register(DummyTool())
        assert "dummy_tool" in registry.list_tool_names()
        result = registry.execute("dummy_tool", {"query": "test"})
        assert result.tool == "dummy_tool"
