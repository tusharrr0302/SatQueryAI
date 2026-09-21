"""
app/orchestrator/tool_registry.py
─────────────────────────────────────────────────────────────────────────────
The Tool Registry: a central directory of all available tools.

WHY THIS EXISTS:
  Instead of the orchestrator knowing about each tool individually, it asks
  the registry: "What tools do you have?" The registry returns a list that
  can be sent directly to GPT-OSS (OpenAI format) or to LangGraph (LangChain
  StructuredTool format).

  When GPT-OSS decides to call a tool, the orchestrator asks the registry:
  "Execute this tool with these arguments." The registry finds the right
  tool and runs it.

HOW TO ADD A NEW TOOL:
  1. Create your tool class in app/tools/
  2. Import it below (see REGISTERED TOOLS section)
  3. Add an instance to the TOOLS list
  That's all.

IMPORTANT:
  This registry is the ONLY place tool-to-name mapping is defined.
  The orchestrator never imports individual tool classes directly.

CURRENT TOOL CATALOG (8 tools):
  -- Satellite Data Acquisition --
  fetch_sentinel1              Copernicus OData → Sentinel-1 SAR
  fetch_sentinel2              Copernicus OData → Sentinel-2 optical (single window)
  fetch_multitemporal_sentinel2 Copernicus OData → 4-frame Sentinel-2 stack (Prithvi)
  fetch_landsat                USGS M2M API     → Landsat 8/9
  fetch_viirs_modis            NASA CMR API     → VIIRS/MODIS

  -- Specialist Analysis (Remote GPU Workers) --
  analyze_image        EarthDial-4B-MS  → single-image VQA (replaces GeoChat)
  detect_change        VisTA/Prithvi    → bi-temporal change detection
  analyze_sar_optical  CLOSP/TerraFM   → SAR+optical cross-modal fusion
"""
from __future__ import annotations

import json
from typing import Any
from loguru import logger

from langchain_core.tools import StructuredTool

from app.tools.base import BaseTool
from app.schemas.responses import ToolResult

# -- Satellite acquisition tools -----------------------------------------------
from app.tools.fetch_sentinel1 import FetchSentinel1Tool
from app.tools.fetch_sentinel2 import FetchSentinel2Tool
from app.tools.fetch_multitemporal_sentinel2 import FetchMultitemporalSentinel2Tool
from app.tools.fetch_landsat import FetchLandsatTool
from app.tools.fetch_viirs_modis import FetchViirsModisTool

# ── Specialist analysis tools (remote GPU workers) ────────────────────────────
from app.tools.analyze_image import AnalyzeImageTool
from app.tools.detect_change import DetectChangeTool
from app.tools.analyze_sar_optical import AnalyzeSarOpticalTool


class ToolRegistry:
    """
    Manages all registered tools and provides:
      - A list of tool definitions (for GPT-OSS to see)
      - Tool execution (by name)
    """

    def __init__(self) -> None:
        # This dict maps tool name → tool instance
        # It's populated when tools are registered via register()
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """
        Add a tool to the registry.

        Args:
            tool: An instance of a BaseTool subclass
        """
        logger.debug(f"Registering tool: {tool.name}")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool | None:
        """
        Look up a tool by name.

        Returns None if the tool doesn't exist (don't crash).
        """
        return self._tools.get(name)

    def list_tool_names(self) -> list[str]:
        """Return a list of all registered tool names."""
        return list(self._tools.keys())

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """
        Convert all registered tools to OpenAI function-calling format.

        This list is sent directly to GPT-OSS in the `tools` parameter
        of the chat completion request. GPT-OSS reads the descriptions
        and parameters to decide which tool(s) to call.

        Returns:
            List of dicts in OpenAI's tool spec format
        """
        return [tool.to_openai_function() for tool in self._tools.values()]

    def to_langchain_tools(self) -> list[StructuredTool]:
        """
        Convert all registered tools to LangChain StructuredTool objects.

        These are used by the LangGraph ToolNode to execute tools when the
        LLM emits tool_calls.  Each StructuredTool wraps the BaseTool.execute()
        method and exposes the same JSON schema the LLM already uses.

        The ToolNode calls tool.invoke({...args...}) which calls this wrapper.
        The wrapper calls registry.execute() to get a ToolResult, serialises it
        to JSON so ToolMessage.content carries the full structured result, and
        the orchestrator reconstructs ToolResult from that JSON.

        Returns:
            List of LangChain StructuredTool instances
        """
        lc_tools: list[StructuredTool] = []
        for base_tool in self._tools.values():
            # Capture the tool in the closure correctly
            _tool = base_tool

            def _make_func(t: BaseTool):
                def _execute(**kwargs: Any) -> str:
                    result: ToolResult = self.execute(t.name, kwargs)
                    return json.dumps(result.model_dump())
                _execute.__name__ = t.name
                return _execute

            lc_tool = StructuredTool(
                name=base_tool.name,
                description=base_tool.description,
                func=_make_func(_tool),
                args_schema=None,  # LangGraph will use JSON schema from description
            )
            lc_tools.append(lc_tool)

        return lc_tools

    def execute(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        """
        Execute a tool by name with the provided arguments.

        This is called by the orchestrator after GPT-OSS emits a tool_call.
        The orchestrator extracts the tool name and arguments from GPT-OSS's
        response, then calls this method.

        Args:
            tool_name: The name of the tool (must match a registered tool)
            args: Arguments dict from GPT-OSS's tool_call

        Returns:
            ToolResult: The structured output from the tool
        """
        tool = self.get_tool(tool_name)

        if tool is None:
            logger.error(f"GPT-OSS requested unknown tool: '{tool_name}'")
            return ToolResult(
                tool=tool_name,
                model="unknown",
                mode="error",
                answer=f"Tool '{tool_name}' is not registered.",
                error=f"Unknown tool: {tool_name}",
            )

        logger.info(f"Executing tool: {tool_name} | args: {args}")

        try:
            result = tool.execute(args)
            logger.info(f"Tool {tool_name} completed | mode={result.mode}")
            return result
        except Exception as e:
            logger.exception(f"Tool '{tool_name}' raised an unexpected exception")
            return ToolResult(
                tool=tool_name,
                model="unknown",
                mode="error",
                answer=f"Tool '{tool_name}' encountered an internal error.",
                error=str(e),
            )


# ─────────────────────────────────────────────────────────────────────────────
# REGISTERED TOOLS
# Create the singleton registry and register all tools.
# ─────────────────────────────────────────────────────────────────────────────

def build_registry() -> ToolRegistry:
    """
    Factory function that creates the global tool registry and registers
    all available tools.

    To add a new tool:
      1. Create the tool class in app/tools/
      2. Import it at the top of this file
      3. Add: registry.register(YourNewTool())
    """
    registry = ToolRegistry()

    # -- Satellite data acquisition tools ----------------------------------------
    # These allow GPT-OSS to autonomously fetch satellite data for text-only
    # queries (e.g. "Show deforestation in Uttarakhand 2020-2024").
    registry.register(FetchSentinel1Tool())
    registry.register(FetchSentinel2Tool())
    registry.register(FetchMultitemporalSentinel2Tool())  # 4-frame stack for Prithvi
    registry.register(FetchLandsatTool())
    registry.register(FetchViirsModisTool())

    # ── Specialist analysis tools (remote GPU workers) ────────────────────────
    # These call independent Kaggle notebooks via ngrok HTTP.
    registry.register(AnalyzeImageTool())
    registry.register(DetectChangeTool())
    registry.register(AnalyzeSarOpticalTool())

    logger.info(
        f"Tool registry built with {len(registry.list_tool_names())} tools: "
        f"{registry.list_tool_names()}"
    )
    return registry
