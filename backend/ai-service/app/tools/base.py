"""
app/tools/base.py
─────────────────────────────────────────────────────────────────────────────
Defines the BaseTool abstract class that every specialist tool must inherit.

WHY THIS EXISTS:
  The orchestrator needs a uniform interface to:
    1. List available tools (for GPT-OSS to see what it can call)
    2. Validate tool arguments
    3. Execute any tool without knowing its internal implementation

  By making every tool extend BaseTool, the orchestrator can treat
  all tools identically. Adding a new tool means creating a new class
  that implements these methods — the orchestrator needs no changes.

HOW TO ADD A NEW TOOL:
  1. Create a new file in app/tools/ (e.g., calculate_ndvi.py)
  2. Define a class that extends BaseTool
  3. Implement name, description, input_schema, output_schema, and execute()
  4. Register it in app/orchestrator/tool_registry.py

That's it. The orchestrator will automatically offer it to GPT-OSS.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.responses import ToolResult


class BaseTool(ABC):
    """
    Abstract base class for all SatQuery AI tools.

    Every tool must implement:
      - name            : unique identifier string
      - description     : what this tool does (shown to GPT-OSS)
      - input_schema    : JSON Schema dict describing tool arguments
      - output_schema   : JSON Schema dict describing tool return
      - execute(args)   : the actual tool logic
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique tool name. GPT-OSS uses this exact string when it decides
        to call this tool. Must be lowercase with underscores.
        Example: "analyze_image"
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Human-readable description of what the tool does.
        This is shown directly to GPT-OSS so it can decide whether
        to use this tool. Write it clearly and precisely.
        """
        ...

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """
        JSON Schema describing the tool's input parameters.
        This is what GPT-OSS uses to know what arguments to provide.
        Must follow the OpenAI function-calling schema format.
        """
        ...

    @abstractmethod
    def execute(self, args: dict[str, Any]) -> ToolResult:
        """
        Run the tool with the given arguments.

        Args:
            args: Dictionary of arguments matching the input_schema.
                  These come from GPT-OSS's tool_call and have already
                  been validated against the Pydantic input model.

        Returns:
            ToolResult: A structured result the orchestrator can feed
                        back to GPT-OSS.

        This method should NEVER raise an unhandled exception.
        Catch errors internally and return a ToolResult with error set.
        """
        ...

    def to_openai_function(self) -> dict[str, Any]:
        """
        Convert this tool into the OpenAI function-calling format.

        This is what gets sent to GPT-OSS in the `tools` list.
        GPT-OSS reads the name, description, and parameters to decide
        whether to call this tool and what arguments to provide.

        Returns a dict in the OpenAI "function" tool spec format:
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": { <JSON Schema> }
            }
        }
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }
