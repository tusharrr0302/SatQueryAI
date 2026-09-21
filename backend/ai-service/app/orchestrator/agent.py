"""
app/orchestrator/agent.py
─────────────────────────────────────────────────────────────────────────────
The Orchestrator Agent — powered by LangChain + LangGraph.

ARCHITECTURE:
  The legacy manual agentic loop has been replaced by a LangGraph StateGraph.
  The public interface (OrchestratorAgent.run()) is UNCHANGED, so the FastAPI
  layer (app/api/v1/chat.py) and all existing tests require zero modifications.

GRAPH STRUCTURE:
  START
    ↓
  [agent] ← ChatOpenAI with tools bound
    ↓ (tool_calls present)
  [tool_executor] ← LangGraph ToolNode (executes all registered tools)
    ↓ (loops back)
  [agent]
    ↓ (finish_reason=stop)
  END

CRITICAL RULE:
  The LLM decides which tool to call. This file contains NO if/elif chains
  like "if 'change' in query: call detect_change". The routing intelligence
  lives entirely in the LLM, which reads the tool descriptions at inference
  time and performs semantic tool selection.

SEPARATION OF CONCERNS:
  This agent knows about:
    - LangGraph (graph orchestration)
    - ToolRegistry (what tools exist, how to run them)
    - Schemas (what goes in/out)
  This agent does NOT know about:
    - FastAPI (HTTP layer)
    - EarthDial / CLOSP / TerraFM internals
    - Any specific tool's implementation
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal
from loguru import logger

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    AIMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from app.orchestrator.tool_registry import ToolRegistry, build_registry
from app.orchestrator.graph_state import AgentState
from app.orchestrator.prompts import SYSTEM_PROMPT
from app.schemas.responses import ChatResponse, ToolCallRecord, ToolResult
from app.config import settings


# Maximum number of tool-call rounds in a single conversation turn.
# Prevents the graph from looping forever if something goes wrong.
MAX_TOOL_CALL_ROUNDS = 5


class OrchestratorAgent:
    """
    The main agent that orchestrates the LLM and specialist tools via LangGraph.

    Lifecycle:
      - Created once at application startup (in app/main.py)
      - Shared across requests (stateless — conversation history is passed in)
      - Call agent.run(...) for each user message

    The public run() signature is identical to the legacy OrchestratorAgent so
    the FastAPI layer and all tests work without changes.
    """

    def __init__(self) -> None:
        logger.info("Initialising OrchestratorAgent (LangGraph)...")

        # ── Tool registry ─────────────────────────────────────────────────────
        self._registry: ToolRegistry = build_registry()

        # ── LangChain tools (LangGraph ToolNode format) ───────────────────────
        self._lc_tools = self._registry.to_langchain_tools()

        # ── LLM via ChatOpenAI (targets any OpenAI-compatible provider) ───────
        # This replaces the legacy LLMClient. The same env vars are reused:
        #   LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_MAX_TOKENS
        self._llm = ChatOpenAI(
            model=settings.llm_model,
            openai_api_key=settings.llm_api_key,
            openai_api_base=settings.llm_base_url,
            max_tokens=settings.llm_max_tokens,
            temperature=0,
        ).bind_tools(self._lc_tools)

        # ── Build and compile the LangGraph StateGraph ────────────────────────
        self._graph = self._build_graph()

        logger.info(
            f"OrchestratorAgent (LangGraph) ready | "
            f"tools={self._registry.list_tool_names()} | "
            f"model_mode={settings.model_mode}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Public interface (unchanged from legacy)
    # ─────────────────────────────────────────────────────────────────────────

    def run(
        self,
        user_message: str,
        image_path: str | None = None,
        image_url: str | None = None,
        image_path_t2: str | None = None,
        image_url_t2: str | None = None,
        sar_image_path: str | None = None,
        sar_image_url: str | None = None,
        metadata: dict[str, Any] | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        aoi: list[float] | None = None,
        date_range: list[str] | None = None,
        request_id: str | None = None,
    ) -> ChatResponse:
        """
        Run one turn of the agentic conversation via LangGraph.

        Args:
            user_message:         The user's natural-language query
            image_path:           Optional local path to the primary image
            image_url:            Optional public URL to the primary image
            image_path_t2:        Optional local path to second (t2) image
            image_url_t2:         Optional public URL to second image
            sar_image_path:       Optional local path to SAR image
            sar_image_url:        Optional public URL to SAR image
            metadata:             Optional satellite metadata dict
            conversation_history: Previous messages for multi-turn context
            aoi:                  Optional bounding box for satellite data fetching
            date_range:           Optional [start, end] ISO-8601 date strings
            request_id:           Optional client-provided request ID

        Returns:
            ChatResponse with the final answer and full tool call trace
        """
        request_id = request_id or str(uuid.uuid4())

        logger.info(f"=== NEW AGENT TURN (LangGraph) | request_id={request_id} ===")
        logger.info(f"[{request_id}] USER QUERY: {user_message}")

        # URL takes precedence over local path (remote workers need URLs)
        primary_image = image_url or image_path
        secondary_image = image_url_t2 or image_path_t2
        sar_image = sar_image_url or sar_image_path

        logger.info(
            f"[{request_id}] Images: primary={primary_image}, "
            f"t2={secondary_image}, sar={sar_image}"
        )

        # ── Build the initial graph messages ──────────────────────────────────
        # Convert legacy dict-format history to LangChain message objects
        lc_messages = self._build_lc_messages(
            user_message=user_message,
            primary_image=primary_image,
            secondary_image=secondary_image,
            sar_image=sar_image,
            metadata=metadata,
            conversation_history=conversation_history or [],
            aoi=aoi,
            date_range=date_range,
        )

        # ── Set up initial graph state ────────────────────────────────────────
        initial_state: dict[str, Any] = {
            "messages": lc_messages,
            "request_id": request_id,
            "primary_image": primary_image,
            "secondary_image": secondary_image,
            "sar_image": sar_image,
            "aoi": aoi,
            "date_range": date_range,
            "metadata": metadata or {},
            "tool_call_records": [],
            "artifacts": [],
            "error": None,
        }

        # ── Invoke the LangGraph compiled graph ───────────────────────────────
        try:
            final_state = self._graph.invoke(
                initial_state,
                config={"recursion_limit": MAX_TOOL_CALL_ROUNDS * 2 + 2},
            )
        except Exception as e:
            logger.error(f"[{request_id}] LangGraph invocation failed: {e}")
            return ChatResponse(
                answer=f"I encountered an error while processing your request: {e}",
                tool_calls=[],
                artifacts=[],
                model=settings.llm_model,
                request_id=request_id,
                error=str(e),
            )

        # ── Extract results from final state ──────────────────────────────────
        final_answer = self._extract_final_answer(final_state["messages"])
        tool_call_records = self._extract_tool_call_records(
            messages=final_state["messages"],
            request_id=request_id,
            primary_image=primary_image,
            secondary_image=secondary_image,
            sar_image=sar_image,
            metadata=metadata,
        )
        artifacts = self._collect_artifacts(tool_call_records)

        logger.info(f"[{request_id}] GPT-OSS FINAL ANSWER: {final_answer[:300]}...")
        logger.info(f"[{request_id}] === AGENT TURN COMPLETE ===")

        return ChatResponse(
            answer=final_answer,
            tool_calls=tool_call_records,
            artifacts=artifacts,
            model=settings.llm_model,
            request_id=request_id,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # LangGraph graph construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_graph(self):
        """
        Build and compile the LangGraph StateGraph.

        Graph topology:
          START → agent → (tool_calls?) → tool_executor → agent → ... → END
        """
        tool_node = ToolNode(self._lc_tools)

        graph = StateGraph(dict)

        # ── Nodes ─────────────────────────────────────────────────────────────
        graph.add_node("agent", self._agent_node)
        graph.add_node("tool_executor", tool_node)

        # ── Edges ─────────────────────────────────────────────────────────────
        graph.add_edge(START, "agent")
        graph.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "tool_executor",
                "end": END,
            },
        )
        graph.add_edge("tool_executor", "agent")

        return graph.compile()

    def _agent_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Agent node: invoke the LLM with the current message list.
        Returns an updated messages list.
        """
        messages = state["messages"]
        logger.debug(f"[agent node] Invoking LLM | message count={len(messages)}")

        response = self._llm.invoke(messages)

        logger.debug(
            f"[agent node] LLM response | "
            f"tool_calls={len(response.tool_calls) if response.tool_calls else 0}"
        )

        # Return only the new message — LangGraph's add_messages reducer
        # appends it to state["messages"] automatically.
        return {"messages": [response]}

    @staticmethod
    def _should_continue(
        state: dict[str, Any],
    ) -> Literal["continue", "end"]:
        """
        Conditional routing: if the last message has tool calls → continue.
        Otherwise the LLM produced a final text answer → end.
        """
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "continue"
        return "end"

    # ─────────────────────────────────────────────────────────────────────────
    # Message construction helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_lc_messages(
        user_message: str,
        primary_image: str | None,
        secondary_image: str | None,
        sar_image: str | None,
        metadata: dict[str, Any] | None,
        conversation_history: list[dict[str, Any]],
        aoi: list[float] | None,
        date_range: list[str] | None,
    ) -> list:
        """
        Build the LangChain message list from the ChatRequest fields.

        Structure: [SystemMessage] + [history] + [HumanMessage with context]
        """
        messages = [SystemMessage(content=SYSTEM_PROMPT)]

        # Convert legacy dict-format history to LangChain message objects
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            # tool role messages are skipped; they're not needed for new turns

        # Build the user content with geospatial context appended
        context_parts = [user_message]
        if primary_image:
            context_parts.append(f"\n[Primary image available: {primary_image}]")
        if secondary_image:
            context_parts.append(f"\n[Second image (time-2) available: {secondary_image}]")
        if sar_image:
            context_parts.append(f"\n[SAR image available: {sar_image}]")
        if metadata:
            context_parts.append(f"\n[Image metadata: {json.dumps(metadata)}]")
        if aoi:
            context_parts.append(
                f"\n[Area of interest (bounding box): {aoi} — "
                f"you can use satellite fetch tools with this bbox]"
            )
        if date_range and len(date_range) == 2:
            context_parts.append(
                f"\n[Date range: {date_range[0]} to {date_range[1]} — "
                f"use this for satellite data queries]"
            )

        messages.append(HumanMessage(content="".join(context_parts)))
        return messages

    # ─────────────────────────────────────────────────────────────────────────
    # Response extraction helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_final_answer(messages: list) -> str:
        """Extract the final text answer from the last AIMessage."""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                return msg.content
        return "I was unable to produce a final answer."

    def _extract_tool_call_records(
        self,
        messages: list,
        request_id: str,
        primary_image: str | None,
        secondary_image: str | None,
        sar_image: str | None,
        metadata: dict[str, Any] | None,
    ) -> list[ToolCallRecord]:
        """
        Reconstruct ToolCallRecord objects from the message history.

        LangGraph's ToolNode records:
          - AIMessage with tool_calls = [...] (what the LLM requested)
          - ToolMessage with content = JSON string of the result

        We pair them up to build the trace.
        """
        records: list[ToolCallRecord] = []

        # Build a map: tool_call_id → (tool_name, args)
        pending: dict[str, tuple[str, dict]] = {}

        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc["name"]
                    raw_args = tc.get("args", {})
                    # Inject image paths that the LLM may have omitted
                    resolved_args = self._inject_image_paths(
                        tool_name=tool_name,
                        tool_args=raw_args if isinstance(raw_args, dict) else {},
                        primary_image=primary_image,
                        secondary_image=secondary_image,
                        sar_image=sar_image,
                        metadata=metadata,
                    )
                    pending[tc["id"]] = (tool_name, resolved_args)

            elif isinstance(msg, ToolMessage):
                call_id = msg.tool_call_id
                if call_id in pending:
                    tool_name, args = pending.pop(call_id)

                    # Parse the ToolResult from the ToolMessage content
                    try:
                        result_dict = json.loads(msg.content)
                        tool_result = ToolResult(**result_dict)
                    except Exception:
                        # Fallback: wrap raw content in a ToolResult
                        tool_result = ToolResult(
                            tool=tool_name,
                            model="unknown",
                            mode="unknown",
                            answer=str(msg.content),
                        )

                    logger.info(
                        f"[{request_id}] TOOL RESULT: tool={tool_result.tool} | "
                        f"model={tool_result.model} | mode={tool_result.mode}"
                    )

                    records.append(
                        ToolCallRecord(
                            tool_name=tool_name,
                            arguments=args,
                            result=tool_result,
                        )
                    )

        return records

    @staticmethod
    def _collect_artifacts(tool_call_records: list[ToolCallRecord]) -> list[Any]:
        """Flatten artifacts from all tool call results."""
        artifacts: list[Any] = []
        for record in tool_call_records:
            if record.result and record.result.artifacts:
                artifacts.extend(record.result.artifacts)
        return artifacts

    @staticmethod
    def _inject_image_paths(
        tool_name: str,
        tool_args: dict[str, Any],
        primary_image: str | None,
        secondary_image: str | None,
        sar_image: str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Ensure image references from the API request reach the tool arguments.

        The LLM generates tool arguments based on its context. Sometimes it
        doesn't repeat image references (it knows they're available but the
        tool schema requires them). This method fills in missing image args.

        URL takes precedence over local path (already resolved in run()).
        """
        args = dict(tool_args)

        if tool_name == "analyze_image":
            if not args.get("image"):
                args["image"] = primary_image
            if "metadata" not in args:
                args["metadata"] = metadata or {}

        elif tool_name == "detect_change":
            if not args.get("image_t1"):
                args["image_t1"] = primary_image
            if not args.get("image_t2"):
                args["image_t2"] = secondary_image
            if "metadata_t1" not in args:
                args["metadata_t1"] = metadata or {}
            if "metadata_t2" not in args:
                args["metadata_t2"] = {}

        elif tool_name == "analyze_sar_optical":
            if not args.get("sar_image"):
                args["sar_image"] = sar_image
            if not args.get("optical_image"):
                args["optical_image"] = primary_image
            if "metadata" not in args:
                args["metadata"] = metadata or {}

        return args
